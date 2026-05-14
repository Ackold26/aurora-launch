"""Phase Π.2.2 — Pure transfer engine tests.

Coverage:
- Math helpers (adstock geometric carryover, hill saturation)
- TransferInputs validation (lengths, share/distribution bounds, spend_plan keys)
- Recipient baseline computation
- Forecast cone end-to-end (n_recipient=0 case)
- CI bands ordering (lower ≤ point ≤ upper)
- Uncertainty decomposition sums к 100%
- Per-channel contributions sum к (forecast - baseline)
- Methodology signature stable

Per INV-05: attack scenarios first для validators.
Per INV-08: full pytest coverage.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from aurora_launch.engines.pure_transfer_engine import (
    ChannelTransferParams,
    ForecastPoint,
    RecipientAnchors,
    TransferForecast,
    TransferInputs,
    apply_geometric_adstock,
    compute_recipient_baseline,
    forecast_pure_transfer,
    hill_saturation,
)


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------


class TestApplyGeometricAdstock:
    def test_zero_decay_returns_passthrough(self) -> None:
        out = apply_geometric_adstock([1.0, 2.0, 3.0], decay=0.0)
        np.testing.assert_allclose(out, [1.0, 2.0, 3.0])

    def test_full_decay_accumulates(self) -> None:
        # decay=1.0 → adstock accumulates without decay
        out = apply_geometric_adstock([1.0, 2.0, 3.0], decay=1.0)
        np.testing.assert_allclose(out, [1.0, 3.0, 6.0])

    def test_half_decay(self) -> None:
        out = apply_geometric_adstock([1.0, 0.0, 0.0], decay=0.5)
        # adstock_0=1, adstock_1=0 + 0.5*1=0.5, adstock_2=0 + 0.5*0.5=0.25
        np.testing.assert_allclose(out, [1.0, 0.5, 0.25])

    def test_empty_input(self) -> None:
        out = apply_geometric_adstock([], decay=0.5)
        assert len(out) == 0

    def test_invalid_decay(self) -> None:
        with pytest.raises(ValueError, match="decay"):
            apply_geometric_adstock([1.0], decay=1.5)
        with pytest.raises(ValueError, match="decay"):
            apply_geometric_adstock([1.0], decay=-0.1)

    def test_length_preserved(self) -> None:
        out = apply_geometric_adstock([1.0, 2.0, 3.0, 4.0, 5.0], decay=0.3)
        assert len(out) == 5


class TestHillSaturation:
    def test_zero_at_zero(self) -> None:
        out = hill_saturation(np.array([0.0]), alpha=2.0, half_saturation=1.0)
        np.testing.assert_allclose(out, [0.0])

    def test_half_at_half_saturation(self) -> None:
        out = hill_saturation(np.array([1.0]), alpha=2.0, half_saturation=1.0)
        np.testing.assert_allclose(out, [0.5])

    def test_monotonically_increasing(self) -> None:
        x = np.linspace(0, 10, 50)
        y = hill_saturation(x, alpha=1.5, half_saturation=2.0)
        diffs = np.diff(y)
        assert (diffs >= -1e-9).all(), "Hill must be monotonic non-decreasing"

    def test_bounded_zero_to_one(self) -> None:
        x = np.linspace(0, 1000, 100)
        y = hill_saturation(x, alpha=2.0, half_saturation=5.0)
        assert (y >= 0).all()
        assert (y <= 1.0 + 1e-9).all()

    def test_asymptote_approaches_one(self) -> None:
        out = hill_saturation(np.array([1e6]), alpha=2.0, half_saturation=1.0)
        assert out[0] > 0.99

    def test_invalid_alpha(self) -> None:
        with pytest.raises(ValueError, match="alpha"):
            hill_saturation(np.array([1.0]), alpha=0.0, half_saturation=1.0)

    def test_invalid_half_saturation(self) -> None:
        with pytest.raises(ValueError, match="half_saturation"):
            hill_saturation(np.array([1.0]), alpha=2.0, half_saturation=0.0)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


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


def _make_channels() -> list[ChannelTransferParams]:
    return [
        ChannelTransferParams(
            channel_id="tv",
            proxy_beta_mean=0.2,
            proxy_beta_std=0.04,
            adstock_decay=0.5,
            hill_alpha=2.0,
            hill_half_saturation=100.0,
            similarity_factor=0.85,
            similarity_inflation=0.15,
        ),
        ChannelTransferParams(
            channel_id="digital",
            proxy_beta_mean=0.1,
            proxy_beta_std=0.02,
            adstock_decay=0.2,
            hill_alpha=1.5,
            hill_half_saturation=50.0,
            similarity_factor=0.85,
            similarity_inflation=0.15,
        ),
    ]


def _make_inputs(horizon: int = 12) -> TransferInputs:
    return TransferInputs(
        granularity="monthly",
        horizon_periods=horizon,
        channels=_make_channels(),
        anchors=_make_anchors(horizon),
        spend_plan={
            "tv": [200.0] * horizon,
            "digital": [80.0] * horizon,
        },
        proxy_baseline_mean=500_000.0,
        coverage_target=0.95,
    )


class TestAnchorValidation:
    def test_trajectories_same_length(self) -> None:
        with pytest.raises(ValueError, match="same length"):
            RecipientAnchors(
                market_size=1_000_000,
                planned_share_trajectory=[0.05, 0.06],
                distribution_trajectory=[0.7, 0.8, 0.9],
                pricing_index=1.0,
                elasticity=0.5,
            )

    def test_seasonality_length_must_match(self) -> None:
        with pytest.raises(ValueError, match="seasonality"):
            RecipientAnchors(
                market_size=1_000_000,
                planned_share_trajectory=[0.05, 0.06, 0.07],
                distribution_trajectory=[0.7, 0.8, 0.9],
                pricing_index=1.0,
                elasticity=0.5,
                seasonality=[1.0, 1.1],
            )

    def test_share_must_be_in_zero_one(self) -> None:
        with pytest.raises(ValueError, match="planned_share"):
            RecipientAnchors(
                market_size=1_000_000,
                planned_share_trajectory=[0.05, 1.5],
                distribution_trajectory=[0.7, 0.8],
                pricing_index=1.0,
                elasticity=0.5,
            )

    def test_distribution_must_be_in_zero_one(self) -> None:
        with pytest.raises(ValueError, match="distribution"):
            RecipientAnchors(
                market_size=1_000_000,
                planned_share_trajectory=[0.05, 0.06],
                distribution_trajectory=[0.7, 1.2],
                pricing_index=1.0,
                elasticity=0.5,
            )

    def test_market_size_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            RecipientAnchors(
                market_size=0,
                planned_share_trajectory=[0.05],
                distribution_trajectory=[0.7],
                pricing_index=1.0,
                elasticity=0.5,
            )

    def test_pricing_index_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            RecipientAnchors(
                market_size=1_000_000,
                planned_share_trajectory=[0.05],
                distribution_trajectory=[0.7],
                pricing_index=0.0,
                elasticity=0.5,
            )


class TestInputsValidation:
    def test_spend_plan_length_must_match_horizon(self) -> None:
        with pytest.raises(ValueError, match="length"):
            TransferInputs(
                granularity="monthly",
                horizon_periods=12,
                channels=_make_channels(),
                anchors=_make_anchors(12),
                spend_plan={"tv": [200.0] * 6, "digital": [80.0] * 12},
                proxy_baseline_mean=500_000.0,
            )

    def test_spend_plan_keys_must_match_channels(self) -> None:
        with pytest.raises(ValueError, match="spend_plan"):
            TransferInputs(
                granularity="monthly",
                horizon_periods=12,
                channels=_make_channels(),
                anchors=_make_anchors(12),
                spend_plan={"tv": [200.0] * 12},  # missing 'digital'
                proxy_baseline_mean=500_000.0,
            )

    def test_negative_spend_rejected(self) -> None:
        plan = [100.0] * 12
        plan[5] = -50.0
        with pytest.raises(ValueError, match="negative"):
            TransferInputs(
                granularity="monthly",
                horizon_periods=12,
                channels=_make_channels(),
                anchors=_make_anchors(12),
                spend_plan={"tv": plan, "digital": [80.0] * 12},
                proxy_baseline_mean=500_000.0,
            )

    def test_horizon_bounds(self) -> None:
        # Lower bound: 1
        TransferInputs(
            granularity="monthly",
            horizon_periods=1,
            channels=_make_channels(),
            anchors=_make_anchors(1),
            spend_plan={"tv": [100.0], "digital": [50.0]},
            proxy_baseline_mean=500_000.0,
        )
        # Upper bound: 60
        with pytest.raises(ValueError):
            TransferInputs(
                granularity="monthly",
                horizon_periods=61,
                channels=_make_channels(),
                anchors=_make_anchors(61),
                spend_plan={"tv": [100.0] * 61, "digital": [50.0] * 61},
                proxy_baseline_mean=500_000.0,
            )


# ---------------------------------------------------------------------------
# Baseline computation
# ---------------------------------------------------------------------------


class TestRecipientBaseline:
    def test_flat_baseline(self) -> None:
        anchors = _make_anchors(6)
        baseline = compute_recipient_baseline(anchors, 6)
        assert baseline.shape == (6,)
        # market_size × seasonality (1.0) × share (0.05) × distribution (0.70)
        # × pricing_factor (1/1.0)^0.5 = 1.0
        # = 10M × 1 × 0.05 × 0.70 × 1 = 350_000
        np.testing.assert_allclose(baseline, [350_000.0] * 6)

    def test_pricing_factor_applied(self) -> None:
        # pricing_index=2.0 (recipient priced 2× proxy), elasticity=0.5
        # pricing_factor = (1/2)^0.5 = 0.7071
        anchors = RecipientAnchors(
            market_size=10_000_000,
            planned_share_trajectory=[0.05],
            distribution_trajectory=[0.70],
            pricing_index=2.0,
            elasticity=0.5,
            seasonality=[1.0],
        )
        baseline = compute_recipient_baseline(anchors, 1)
        expected = 10_000_000 * 1.0 * 0.05 * 0.70 * math.sqrt(0.5)
        np.testing.assert_allclose(baseline[0], expected)

    def test_seasonality_modulates(self) -> None:
        anchors = _make_anchors(4)
        # Replace flat seasonality с seasonal pattern
        anchors = RecipientAnchors(
            market_size=anchors.market_size,
            planned_share_trajectory=anchors.planned_share_trajectory,
            distribution_trajectory=anchors.distribution_trajectory,
            pricing_index=anchors.pricing_index,
            elasticity=anchors.elasticity,
            seasonality=[0.8, 1.2, 1.0, 0.9],
        )
        baseline = compute_recipient_baseline(anchors, 4)
        # Baseline ratios должны соответствовать seasonality ratios
        ratios = baseline / baseline.mean()
        seasonality_ratios = np.array([0.8, 1.2, 1.0, 0.9])
        seasonality_ratios = seasonality_ratios / seasonality_ratios.mean()
        np.testing.assert_allclose(ratios, seasonality_ratios, atol=1e-9)


# ---------------------------------------------------------------------------
# Pure transfer forecast end-to-end
# ---------------------------------------------------------------------------


class TestForecastPureTransfer:
    def test_returns_correct_shape(self) -> None:
        inputs = _make_inputs(horizon=12)
        result = forecast_pure_transfer(inputs)
        assert isinstance(result, TransferForecast)
        assert result.granularity == "monthly"
        assert result.horizon_periods == 12
        assert len(result.points) == 12
        assert all(isinstance(p, ForecastPoint) for p in result.points)

    def test_ci_bands_ordering(self) -> None:
        """Audit P0-attack: lower ≤ point ≤ upper invariant."""
        inputs = _make_inputs(horizon=12)
        result = forecast_pure_transfer(inputs)
        for p in result.points:
            assert p.ci_lower <= p.point_forecast <= p.ci_upper, (
                f"CI ordering broken at t={p.period_index}: "
                f"{p.ci_lower} <= {p.point_forecast} <= {p.ci_upper}"
            )

    def test_forecast_greater_than_baseline(self) -> None:
        """Adding non-zero media spend should boost forecast above baseline."""
        inputs = _make_inputs(horizon=12)
        result = forecast_pure_transfer(inputs)
        for p in result.points:
            assert p.point_forecast >= p.baseline, (
                f"Forecast {p.point_forecast} < baseline {p.baseline} at t={p.period_index}"
            )

    def test_zero_spend_returns_baseline_only(self) -> None:
        """If all spends are zero, forecast = baseline (no media effect)."""
        inputs = TransferInputs(
            granularity="monthly",
            horizon_periods=6,
            channels=_make_channels(),
            anchors=_make_anchors(6),
            spend_plan={"tv": [0.0] * 6, "digital": [0.0] * 6},
            proxy_baseline_mean=500_000.0,
        )
        result = forecast_pure_transfer(inputs)
        for p in result.points:
            np.testing.assert_allclose(p.point_forecast, p.baseline, atol=1e-9)

    def test_per_channel_contributions_sum_to_total(self) -> None:
        inputs = _make_inputs(horizon=12)
        result = forecast_pure_transfer(inputs)
        for p in result.points:
            total_channels = sum(p.per_channel_contribution.values())
            np.testing.assert_allclose(
                p.point_forecast,
                p.baseline + total_channels,
                rtol=1e-9,
                err_msg=f"Channel sum mismatch at t={p.period_index}",
            )

    def test_uncertainty_decomposition_sums_to_100(self) -> None:
        inputs = _make_inputs(horizon=12)
        result = forecast_pure_transfer(inputs)
        d = result.uncertainty_decomposition
        total = (
            d.proxy_uncertainty_pct
            + d.transfer_assumption_pct
            + d.anchor_uncertainty_pct
        )
        np.testing.assert_allclose(total, 100.0, atol=1e-6)

    def test_methodology_signature_present(self) -> None:
        inputs = _make_inputs(horizon=6)
        result = forecast_pure_transfer(inputs)
        assert result.methodology_signature == "pure_transfer_v1"

    def test_z_critical_matches_coverage(self) -> None:
        inputs = _make_inputs(horizon=6)
        result = forecast_pure_transfer(inputs)
        # Default 0.95 → z=1.96
        assert result.z_critical == 1.96

    def test_coverage_target_changes_ci_width(self) -> None:
        inputs_95 = _make_inputs(horizon=6)
        inputs_80 = TransferInputs(
            granularity="monthly",
            horizon_periods=6,
            channels=_make_channels(),
            anchors=_make_anchors(6),
            spend_plan={"tv": [200.0] * 6, "digital": [80.0] * 6},
            proxy_baseline_mean=500_000.0,
            coverage_target=0.80,
        )
        r95 = forecast_pure_transfer(inputs_95)
        r80 = forecast_pure_transfer(inputs_80)
        # 95% CI должен быть шире чем 80% при одинаковых данных
        width_95 = r95.points[0].ci_upper - r95.points[0].ci_lower
        width_80 = r80.points[0].ci_upper - r80.points[0].ci_lower
        assert width_95 > width_80

    def test_unsupported_coverage_target_raises(self) -> None:
        inputs = TransferInputs(
            granularity="monthly",
            horizon_periods=6,
            channels=_make_channels(),
            anchors=_make_anchors(6),
            spend_plan={"tv": [200.0] * 6, "digital": [80.0] * 6},
            proxy_baseline_mean=500_000.0,
            coverage_target=0.85,  # not в _Z_CRITICAL dict
        )
        with pytest.raises(ValueError, match="coverage_target"):
            forecast_pure_transfer(inputs)


class TestSimilarityImpact:
    """Lower similarity → higher uncertainty + lower point forecast."""

    def test_low_similarity_higher_ci_width(self) -> None:
        base = _make_inputs(horizon=6)
        low_sim_channels = [
            ChannelTransferParams(
                channel_id=c.channel_id,
                proxy_beta_mean=c.proxy_beta_mean,
                proxy_beta_std=c.proxy_beta_std,
                adstock_decay=c.adstock_decay,
                hill_alpha=c.hill_alpha,
                hill_half_saturation=c.hill_half_saturation,
                similarity_factor=0.5,
                similarity_inflation=0.30,
            )
            for c in base.channels
        ]
        low_sim_inputs = TransferInputs(
            granularity=base.granularity,
            horizon_periods=base.horizon_periods,
            channels=low_sim_channels,
            anchors=base.anchors,
            spend_plan=base.spend_plan,
            proxy_baseline_mean=base.proxy_baseline_mean,
            coverage_target=base.coverage_target,
        )
        base_result = forecast_pure_transfer(base)
        low_result = forecast_pure_transfer(low_sim_inputs)

        # Low similarity → wider CI (more transfer uncertainty)
        base_width = base_result.points[0].ci_upper - base_result.points[0].ci_lower
        low_width = low_result.points[0].ci_upper - low_result.points[0].ci_lower
        assert low_width > base_width

    def test_low_similarity_factor_lowers_point_forecast(self) -> None:
        base = _make_inputs(horizon=6)
        low_sim_channels = [
            ChannelTransferParams(
                channel_id=c.channel_id,
                proxy_beta_mean=c.proxy_beta_mean,
                proxy_beta_std=c.proxy_beta_std,
                adstock_decay=c.adstock_decay,
                hill_alpha=c.hill_alpha,
                hill_half_saturation=c.hill_half_saturation,
                similarity_factor=0.5,  # lower
                similarity_inflation=0.0,  # zero inflation isolates the factor effect
            )
            for c in base.channels
        ]
        low_sim_inputs = TransferInputs(
            granularity=base.granularity,
            horizon_periods=base.horizon_periods,
            channels=low_sim_channels,
            anchors=base.anchors,
            spend_plan=base.spend_plan,
            proxy_baseline_mean=base.proxy_baseline_mean,
            coverage_target=base.coverage_target,
        )
        base_result = forecast_pure_transfer(base)
        low_result = forecast_pure_transfer(low_sim_inputs)
        # Lower similarity_factor scales β_recipient down → lower point forecast
        # (channel contributions smaller, baseline unchanged)
        for b, l in zip(base_result.points, low_result.points):
            assert l.point_forecast < b.point_forecast


class TestGranularityAware:
    def test_weekly_granularity_accepted(self) -> None:
        inputs = TransferInputs(
            granularity="weekly",
            horizon_periods=12,
            channels=_make_channels(),
            anchors=_make_anchors(12),
            spend_plan={"tv": [200.0] * 12, "digital": [80.0] * 12},
            proxy_baseline_mean=500_000.0,
        )
        result = forecast_pure_transfer(inputs)
        assert result.granularity == "weekly"
        assert result.horizon_periods == 12
