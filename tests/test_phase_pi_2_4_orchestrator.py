"""Phase Π.2.4 — LaunchOrchestrator integration tests.

Smoke / integration tests для orchestrator gluing:
- Router → engine dispatch correct
- All 4 modes route to a working forecast (current fallbacks для 3-4)
- Bias check for mode 2
- ProxyBundle validation
- shrinkage propagation
"""

from __future__ import annotations

import numpy as np
import pytest

from aurora_launch.engines.launch_orchestrator import (
    LaunchOrchestrator,
    OrchestrationResult,
    OrchestratorError,
    ProxyBundle,
)
from aurora_launch.engines.pure_transfer_engine import RecipientAnchors
from aurora_launch.engines.router import EngineMode


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_proxy_bundle(
    n_channels: int = 2, n_samples: int = 5000, n_obs: int = 104
) -> ProxyBundle:
    rng = np.random.default_rng(42)
    beta_means = [0.2, 0.1][:n_channels]
    beta_stds = [0.05, 0.02][:n_channels]
    alpha_values = [2.0, 1.5][:n_channels]
    gamma_values = [100.0, 50.0][:n_channels]
    decay_values = [0.5, 0.2][:n_channels]
    media_cols = ["tv", "digital"][:n_channels]

    return ProxyBundle(
        posterior_samples={
            "media_betas": np.array(
                [
                    rng.normal(loc=beta_means[i], scale=beta_stds[i], size=n_samples)
                    for i in range(n_channels)
                ]
            ),
            "alphas": np.array(
                [
                    rng.normal(loc=alpha_values[i], scale=0.1, size=n_samples)
                    for i in range(n_channels)
                ]
            ),
            "gammas": np.array(
                [
                    rng.normal(loc=gamma_values[i], scale=5.0, size=n_samples)
                    for i in range(n_channels)
                ]
            ),
            "adstock_decay": np.array(
                [
                    np.clip(
                        rng.normal(loc=decay_values[i], scale=0.05, size=n_samples),
                        0.0,
                        1.0,
                    )
                    for i in range(n_channels)
                ]
            ),
        },
        media_cols=media_cols,
        normalization={"y_mean": 500_000.0, "y_std": 50_000.0},
        config={},
        proxy_brand_id="KAG-2024-anonymized",
        n_proxy_observations=n_obs,
    )


def _make_anchors(horizon: int = 12) -> RecipientAnchors:
    return RecipientAnchors(
        market_size=10_000_000.0,
        market_size_cv=0.10,
        planned_share_trajectory=[0.05] * horizon,
        distribution_trajectory=[0.70] * horizon,
        pricing_index=1.0,
        elasticity=0.5,
        seasonality=[1.0] * horizon,
    )


def _make_spend_plan(horizon: int = 12) -> dict[str, list[float]]:
    return {"tv": [200.0] * horizon, "digital": [80.0] * horizon}


# ---------------------------------------------------------------------------
# Mode routing
# ---------------------------------------------------------------------------


class TestModeRouting:
    def test_pure_transfer_n_zero(self) -> None:
        orch = LaunchOrchestrator()
        result = orch.forecast_recipient(
            proxy=_make_proxy_bundle(),
            anchors=_make_anchors(12),
            spend_plan=_make_spend_plan(12),
            horizon_periods=12,
            granularity="monthly",
            n_recipient=0,
        )
        assert result.engine_config.mode == EngineMode.PURE_TRANSFER
        assert result.forecast is not None
        assert result.methodology_signature == "pure_transfer_v1"
        assert result.warnings == []

    def test_transfer_with_bias_check_routing(self) -> None:
        orch = LaunchOrchestrator()
        result = orch.forecast_recipient(
            proxy=_make_proxy_bundle(),
            anchors=_make_anchors(12),
            spend_plan=_make_spend_plan(12),
            horizon_periods=12,
            granularity="monthly",
            n_recipient=2,  # → TRANSFER_WITH_BIAS_CHECK (monthly: ols_low=3)
        )
        assert result.engine_config.mode == EngineMode.TRANSFER_WITH_BIAS_CHECK
        assert result.methodology_signature == "transfer_with_bias_check_v1"

    def test_ols_with_proxy_priors_fallback(self) -> None:
        orch = LaunchOrchestrator()
        result = orch.forecast_recipient(
            proxy=_make_proxy_bundle(),
            anchors=_make_anchors(12),
            spend_plan=_make_spend_plan(12),
            horizon_periods=12,
            granularity="monthly",
            n_recipient=5,  # → OLS+priors (monthly: bayesian=7)
        )
        assert result.engine_config.mode == EngineMode.OLS_WITH_PROXY_PRIORS
        assert result.methodology_signature == "ols_with_proxy_priors_fallback_v1"
        # Fallback emits warning
        assert any("OLS+priors" in w for w in result.warnings)

    def test_bayesian_with_proxy_priors_fallback(self) -> None:
        orch = LaunchOrchestrator()
        result = orch.forecast_recipient(
            proxy=_make_proxy_bundle(),
            anchors=_make_anchors(12),
            spend_plan=_make_spend_plan(12),
            horizon_periods=12,
            granularity="monthly",
            n_recipient=10,  # → Bayesian+priors (monthly: bayesian=7)
        )
        assert result.engine_config.mode == EngineMode.BAYESIAN_WITH_PROXY_PRIORS
        assert result.methodology_signature == "bayesian_with_proxy_priors_fallback_v1"
        assert any("Bayesian+priors" in w for w in result.warnings)


class TestForecastQuality:
    def test_forecast_shape_correct(self) -> None:
        orch = LaunchOrchestrator()
        result = orch.forecast_recipient(
            proxy=_make_proxy_bundle(),
            anchors=_make_anchors(12),
            spend_plan=_make_spend_plan(12),
            horizon_periods=12,
            granularity="monthly",
            n_recipient=0,
        )
        assert len(result.forecast.points) == 12
        for p in result.forecast.points:
            assert p.ci_lower <= p.point_forecast <= p.ci_upper

    def test_proxy_priors_preserved_в_result(self) -> None:
        orch = LaunchOrchestrator()
        result = orch.forecast_recipient(
            proxy=_make_proxy_bundle(),
            anchors=_make_anchors(6),
            spend_plan=_make_spend_plan(6),
            horizon_periods=6,
            granularity="monthly",
            n_recipient=0,
        )
        assert "tv" in result.proxy_priors_used
        assert "digital" in result.proxy_priors_used
        assert result.proxy_priors_used["tv"].proxy_beta_mean > 0


class TestBiasCheck:
    def test_bias_check_within_threshold(self) -> None:
        orch = LaunchOrchestrator()
        # First run dry to get expected forecast magnitude
        dry = orch.forecast_recipient(
            proxy=_make_proxy_bundle(),
            anchors=_make_anchors(6),
            spend_plan=_make_spend_plan(6),
            horizon_periods=6,
            granularity="monthly",
            n_recipient=0,
        )
        predicted_mean = sum(p.point_forecast for p in dry.forecast.points[:2]) / 2
        # Observed close к predicted → no warning
        observed_y = [predicted_mean] * 2
        result = orch.forecast_recipient(
            proxy=_make_proxy_bundle(),
            anchors=_make_anchors(6),
            spend_plan=_make_spend_plan(6),
            horizon_periods=6,
            granularity="monthly",
            n_recipient=2,
            recipient_y=observed_y,
        )
        # No bias warning (но Mode 2 без recipient_y warning may appear if y empty)
        assert not any("deviates" in w for w in result.warnings)

    def test_mode_2_without_recipient_y_emits_warning(self) -> None:
        """PI2-M3 audit fix: Mode 2 selected без y → explicit warning."""
        orch = LaunchOrchestrator()
        result = orch.forecast_recipient(
            proxy=_make_proxy_bundle(),
            anchors=_make_anchors(6),
            spend_plan=_make_spend_plan(6),
            horizon_periods=6,
            granularity="monthly",
            n_recipient=2,
            recipient_y=None,
        )
        assert any("recipient_y" in w and "skipped" in w for w in result.warnings)

    def test_bias_check_exceeds_threshold(self) -> None:
        orch = LaunchOrchestrator()
        # Observed массивно больше прогноза → bias warning
        result = orch.forecast_recipient(
            proxy=_make_proxy_bundle(),
            anchors=_make_anchors(6),
            spend_plan=_make_spend_plan(6),
            horizon_periods=6,
            granularity="monthly",
            n_recipient=2,
            recipient_y=[100_000_000.0, 100_000_000.0],  # huge deviation
        )
        assert any("Bias check" in w and "%" in w for w in result.warnings)


class TestGranularityAware:
    def test_weekly_routing(self) -> None:
        orch = LaunchOrchestrator()
        bundle = _make_proxy_bundle(n_obs=104)  # ≥52 weekly minimum
        result = orch.forecast_recipient(
            proxy=bundle,
            anchors=_make_anchors(12),
            spend_plan=_make_spend_plan(12),
            horizon_periods=12,
            granularity="weekly",
            n_recipient=7,  # weekly: ols_low=8 → TRANSFER_WITH_BIAS_CHECK
        )
        assert result.engine_config.mode == EngineMode.TRANSFER_WITH_BIAS_CHECK
        assert result.engine_config.granularity == "weekly"


class TestShrinkagePropagation:
    def test_high_shrinkage_tighter_ci(self) -> None:
        orch = LaunchOrchestrator()
        # Compare results с shrinkage 0.0 vs 0.9
        low_shrink = orch.forecast_recipient(
            proxy=_make_proxy_bundle(),
            anchors=_make_anchors(6),
            spend_plan=_make_spend_plan(6),
            horizon_periods=6,
            granularity="monthly",
            n_recipient=0,
            shrinkage_factor=0.0,
        )
        high_shrink = orch.forecast_recipient(
            proxy=_make_proxy_bundle(),
            anchors=_make_anchors(6),
            spend_plan=_make_spend_plan(6),
            horizon_periods=6,
            granularity="monthly",
            n_recipient=0,
            shrinkage_factor=0.9,
        )
        # High shrinkage → tighter CI bands (smaller width)
        low_width = (
            low_shrink.forecast.points[0].ci_upper
            - low_shrink.forecast.points[0].ci_lower
        )
        high_width = (
            high_shrink.forecast.points[0].ci_upper
            - high_shrink.forecast.points[0].ci_lower
        )
        assert high_width < low_width


class TestProxyExtractionErrors:
    def test_invalid_proxy_bundle_missing_keys(self) -> None:
        orch = LaunchOrchestrator()
        bundle = _make_proxy_bundle()
        # Corrupt
        bad_bundle = ProxyBundle(
            posterior_samples={"media_betas": bundle.posterior_samples["media_betas"]},
            media_cols=bundle.media_cols,
            normalization=bundle.normalization,
            n_proxy_observations=bundle.n_proxy_observations,
        )
        with pytest.raises(OrchestratorError, match="proxy priors"):
            orch.forecast_recipient(
                proxy=bad_bundle,
                anchors=_make_anchors(6),
                spend_plan=_make_spend_plan(6),
                horizon_periods=6,
                granularity="monthly",
                n_recipient=0,
            )

    def test_missing_y_mean_in_normalization(self) -> None:
        orch = LaunchOrchestrator()
        bundle = _make_proxy_bundle()
        bad_bundle = ProxyBundle(
            posterior_samples=bundle.posterior_samples,
            media_cols=bundle.media_cols,
            normalization={"y_std": 50000.0},  # missing y_mean
            n_proxy_observations=bundle.n_proxy_observations,
        )
        with pytest.raises(OrchestratorError, match="proxy baseline"):
            orch.forecast_recipient(
                proxy=bad_bundle,
                anchors=_make_anchors(6),
                spend_plan=_make_spend_plan(6),
                horizon_periods=6,
                granularity="monthly",
                n_recipient=0,
            )
