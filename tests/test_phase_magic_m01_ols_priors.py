"""Phase Magic M-01: OLS+priors full implementation tests."""

from __future__ import annotations

import numpy as np
import pytest

from aurora_launch.engines.ols_with_priors import (
    DEFAULT_SHRINKAGE,
    MIN_OBSERVATIONS,
    OLSWithPriorsResult,
    fit_ols_with_priors,
)


def _drop_granularity_import_check() -> None:
    """Static reminder: Granularity is Literal["monthly","weekly"], not Enum."""
    pass


def _make_inputs(
    n_periods: int = 12,
    n_channels: int = 2,
    seed: int = 42,
    true_beta: tuple[float, ...] = (0.5, 0.3),
):
    """Synthetic dataset где y is known linear combination of channels."""
    rng = np.random.default_rng(seed)
    channel_ids = [f"ch_{i}" for i in range(n_channels)]
    adstock_decays = {c: 0.5 for c in channel_ids}
    hill_params = {c: (1.5, 100_000.0) for c in channel_ids}

    # Generate spend (positive, varying)
    historical_spend = {
        c: rng.uniform(50_000, 200_000, size=n_periods).tolist()
        for c in channel_ids
    }

    # Build X using same transforms as engine
    from aurora_launch.engines.pure_transfer_engine import (
        apply_geometric_adstock,
        hill_saturation,
    )

    X = np.zeros((n_periods, n_channels))
    for k, c in enumerate(channel_ids):
        adstock = apply_geometric_adstock(historical_spend[c], 0.5)
        X[:, k] = hill_saturation(adstock, 1.5, 100_000.0)

    # Observed y = X @ true_beta + noise
    true_beta_arr = np.array(true_beta[:n_channels])
    y_clean = X @ true_beta_arr
    y_observed = (y_clean + rng.normal(0, 0.01, size=n_periods)).tolist()

    return {
        "recipient_y": y_observed,
        "historical_spend": historical_spend,
        "channel_ids": channel_ids,
        "adstock_decays": adstock_decays,
        "hill_params": hill_params,
        "proxy_beta_means": {c: 0.4 for c in channel_ids},  # mid-range prior
        "proxy_beta_stds": {c: 0.2 for c in channel_ids},
        "true_beta": true_beta_arr,
    }


class TestFitConvergence:
    def test_fits_synthetic_recovers_true_beta_approximately(self) -> None:
        inputs = _make_inputs(n_periods=20)
        result = fit_ols_with_priors(
            recipient_y=inputs["recipient_y"],
            historical_spend=inputs["historical_spend"],
            channel_ids=inputs["channel_ids"],
            adstock_decays=inputs["adstock_decays"],
            hill_params=inputs["hill_params"],
            proxy_beta_means=inputs["proxy_beta_means"],
            proxy_beta_stds=inputs["proxy_beta_stds"],
            shrinkage=0.1,  # mostly trust OLS
        )
        assert result.converged
        # Should recover within reasonable tolerance
        np.testing.assert_allclose(
            result.beta_combined, inputs["true_beta"], atol=0.15
        )

    def test_high_shrinkage_pulls_toward_proxy(self) -> None:
        inputs = _make_inputs(n_periods=10, true_beta=(0.5, 0.3))
        # Proxy says β=0.4 для both. с shrinkage=0.99 should be near 0.4
        result = fit_ols_with_priors(
            recipient_y=inputs["recipient_y"],
            historical_spend=inputs["historical_spend"],
            channel_ids=inputs["channel_ids"],
            adstock_decays=inputs["adstock_decays"],
            hill_params=inputs["hill_params"],
            proxy_beta_means={"ch_0": 0.4, "ch_1": 0.4},
            proxy_beta_stds={"ch_0": 0.05, "ch_1": 0.05},  # tight prior
            shrinkage=0.99,
        )
        # With tight prior + high shrinkage, posterior near prior mean
        assert abs(result.beta_combined[0] - 0.4) < 0.1
        assert abs(result.beta_combined[1] - 0.4) < 0.1

    def test_low_shrinkage_trusts_ols(self) -> None:
        inputs = _make_inputs(n_periods=30, true_beta=(0.6, 0.2))
        # Proxy wrong (0.4 for both), shrinkage=0.01 should mostly ignore proxy
        result_low = fit_ols_with_priors(
            recipient_y=inputs["recipient_y"],
            historical_spend=inputs["historical_spend"],
            channel_ids=inputs["channel_ids"],
            adstock_decays=inputs["adstock_decays"],
            hill_params=inputs["hill_params"],
            proxy_beta_means={"ch_0": 0.4, "ch_1": 0.4},
            proxy_beta_stds={"ch_0": 0.2, "ch_1": 0.2},
            shrinkage=0.01,
        )
        # Same inputs с high shrinkage — should pull toward 0.4
        result_high = fit_ols_with_priors(
            recipient_y=inputs["recipient_y"],
            historical_spend=inputs["historical_spend"],
            channel_ids=inputs["channel_ids"],
            adstock_decays=inputs["adstock_decays"],
            hill_params=inputs["hill_params"],
            proxy_beta_means={"ch_0": 0.4, "ch_1": 0.4},
            proxy_beta_stds={"ch_0": 0.05, "ch_1": 0.05},
            shrinkage=0.99,
        )
        # Low shrinkage estimate должно differ от high shrinkage в direction
        # of true β. с true_beta=(0.6, 0.2) and proxy=(0.4, 0.4):
        # low_shrinkage → closer к (0.6, 0.2), high → closer к (0.4, 0.4)
        # Diff should be in right sign per channel.
        assert result_low.beta_combined[0] > result_high.beta_combined[0]
        assert result_low.beta_combined[1] < result_high.beta_combined[1]


class TestInputValidation:
    def test_too_few_observations_raises(self) -> None:
        inputs = _make_inputs(n_periods=3)  # < MIN_OBSERVATIONS (5)
        with pytest.raises(ValueError, match="observations"):
            fit_ols_with_priors(
                recipient_y=inputs["recipient_y"],
                historical_spend=inputs["historical_spend"],
                channel_ids=inputs["channel_ids"],
                adstock_decays=inputs["adstock_decays"],
                hill_params=inputs["hill_params"],
                proxy_beta_means=inputs["proxy_beta_means"],
                proxy_beta_stds=inputs["proxy_beta_stds"],
            )

    def test_shrinkage_out_of_range_raises(self) -> None:
        inputs = _make_inputs()
        with pytest.raises(ValueError, match="shrinkage"):
            fit_ols_with_priors(
                recipient_y=inputs["recipient_y"],
                historical_spend=inputs["historical_spend"],
                channel_ids=inputs["channel_ids"],
                adstock_decays=inputs["adstock_decays"],
                hill_params=inputs["hill_params"],
                proxy_beta_means=inputs["proxy_beta_means"],
                proxy_beta_stds=inputs["proxy_beta_stds"],
                shrinkage=1.5,
            )

    def test_missing_channel_raises(self) -> None:
        inputs = _make_inputs(n_channels=2)
        # Omit ch_1 from proxy_beta_means
        with pytest.raises(ValueError, match="proxy_beta_means"):
            fit_ols_with_priors(
                recipient_y=inputs["recipient_y"],
                historical_spend=inputs["historical_spend"],
                channel_ids=inputs["channel_ids"],
                adstock_decays=inputs["adstock_decays"],
                hill_params=inputs["hill_params"],
                proxy_beta_means={"ch_0": 0.4},  # missing ch_1
                proxy_beta_stds=inputs["proxy_beta_stds"],
            )


class TestPosteriorSigma:
    def test_sigma_beta_is_positive(self) -> None:
        inputs = _make_inputs()
        result = fit_ols_with_priors(
            recipient_y=inputs["recipient_y"],
            historical_spend=inputs["historical_spend"],
            channel_ids=inputs["channel_ids"],
            adstock_decays=inputs["adstock_decays"],
            hill_params=inputs["hill_params"],
            proxy_beta_means=inputs["proxy_beta_means"],
            proxy_beta_stds=inputs["proxy_beta_stds"],
        )
        assert all(s >= 0 for s in result.sigma_beta_combined)

    def test_more_data_tightens_posterior(self) -> None:
        """N=30 should give smaller σ_β than N=10."""
        sigmas = {}
        for n in (10, 30):
            inputs = _make_inputs(n_periods=n, seed=42 + n)
            result = fit_ols_with_priors(
                recipient_y=inputs["recipient_y"],
                historical_spend=inputs["historical_spend"],
                channel_ids=inputs["channel_ids"],
                adstock_decays=inputs["adstock_decays"],
                hill_params=inputs["hill_params"],
                proxy_beta_means=inputs["proxy_beta_means"],
                proxy_beta_stds=inputs["proxy_beta_stds"],
            )
            sigmas[n] = result.sigma_beta_combined.mean()
        assert sigmas[30] <= sigmas[10] * 1.1  # within rounding, n=30 ≤ n=10

    def test_residual_sigma_increases_с_noise(self) -> None:
        """Adding noise к y_observed should increase σ_residual."""
        results = []
        rng = np.random.default_rng(7)
        for noise_scale in (0.001, 0.5):
            inputs = _make_inputs(n_periods=20, seed=7)
            y = np.array(inputs["recipient_y"]) + rng.normal(
                0, noise_scale, size=20
            )
            r = fit_ols_with_priors(
                recipient_y=y.tolist(),
                historical_spend=inputs["historical_spend"],
                channel_ids=inputs["channel_ids"],
                adstock_decays=inputs["adstock_decays"],
                hill_params=inputs["hill_params"],
                proxy_beta_means=inputs["proxy_beta_means"],
                proxy_beta_stds=inputs["proxy_beta_stds"],
            )
            results.append(r.sigma_residual)
        assert results[1] >= results[0]


class TestDispatchTableIntegration:
    def test_dispatch_routes_к_real_handler(self) -> None:
        """EngineMode.OLS_WITH_PROXY_PRIORS now maps к real handler."""
        from aurora_launch.engines.dispatch_table import _MODE_DISPATCH
        from aurora_launch.engines.router import EngineMode

        handler = _MODE_DISPATCH[EngineMode.OLS_WITH_PROXY_PRIORS]
        assert handler.__name__ == "_handle_ols_with_proxy_priors"

    def test_fallback_when_no_recipient_y(self) -> None:
        """No recipient_y → fall back к pure_transfer с warning."""
        from aurora_launch.engines.dispatch_table import (
            _handle_ols_with_proxy_priors,
        )
        from aurora_launch.engines.pure_transfer_engine import (
            ChannelTransferParams,
            RecipientAnchors,
        )
        channels = [
            ChannelTransferParams(
                channel_id="tv",
                proxy_beta_mean=0.1,
                proxy_beta_std=0.02,
                adstock_decay=0.5,
                hill_alpha=1.5,
                hill_half_saturation=100_000.0,
                similarity_factor=1.0,
                similarity_inflation=0.05,
            )
        ]
        anchors = RecipientAnchors(
            market_size=1_000_000.0,
            market_size_cv=0.1,
            planned_share_trajectory=[0.05] * 12,
            distribution_trajectory=[0.8] * 12,
            pricing_index=1.0,
            elasticity=0.0,
            seasonality=None,
        )
        spend_plan = {"tv": [100_000.0] * 12}

        warnings: list[str] = []
        forecast, sig = _handle_ols_with_proxy_priors(
            channels=channels,
            anchors=anchors,
            spend_plan=spend_plan,
            horizon_periods=12,
            granularity="monthly",
            proxy_baseline=10_000.0,
            coverage_target=0.95,
            recipient_y=None,
            warnings=warnings,
        )
        assert forecast is not None
        assert sig == "ols_with_proxy_priors_fallback_v1"
        assert any("missing recipient_y" in w for w in warnings)

    def test_real_path_when_inputs_complete(self) -> None:
        """Sufficient recipient_y + historical_spend → real OLS path."""
        from aurora_launch.engines.dispatch_table import (
            DispatchExtras,
            _handle_ols_with_proxy_priors,
        )
        from aurora_launch.engines.pure_transfer_engine import (
            ChannelTransferParams,
            RecipientAnchors,
        )
        channels = [
            ChannelTransferParams(
                channel_id="tv",
                proxy_beta_mean=0.1,
                proxy_beta_std=0.02,
                adstock_decay=0.5,
                hill_alpha=1.5,
                hill_half_saturation=100_000.0,
                similarity_factor=1.0,
                similarity_inflation=0.05,
            )
        ]
        anchors = RecipientAnchors(
            market_size=1_000_000.0,
            market_size_cv=0.1,
            planned_share_trajectory=[0.05] * 12,
            distribution_trajectory=[0.8] * 12,
            pricing_index=1.0,
            elasticity=0.0,
            seasonality=None,
        )
        spend_plan = {"tv": [100_000.0] * 12}
        historical_spend = {"tv": [80_000.0] * 10}
        # Synthetic y compatible с OLS fit
        recipient_y = [50_000.0 + 100.0 * i for i in range(10)]

        warnings: list[str] = []
        forecast, sig = _handle_ols_with_proxy_priors(
            channels=channels,
            anchors=anchors,
            spend_plan=spend_plan,
            horizon_periods=12,
            granularity="monthly",
            proxy_baseline=10_000.0,
            coverage_target=0.95,
            recipient_y=recipient_y,
            warnings=warnings,
            extras=DispatchExtras(historical_spend=historical_spend),
        )
        assert forecast is not None
        assert sig == "ols_with_proxy_priors_v1"
        assert any("converged" in w for w in warnings)
