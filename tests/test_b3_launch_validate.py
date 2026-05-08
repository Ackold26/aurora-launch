"""B3 launch_validate tests — prior predictive + sensitivity + heatmap."""

from __future__ import annotations

import asyncio

import pytest

from aurora_launch.engines.launch_adapt import extract_proxy_priors_from_posterior
from aurora_launch.engines.launch_validate import (
    per_channel_transfer_heatmap_real,
    prior_predictive_samples_real,
    sensitivity_analysis_real,
    validate_transfer,
)
from aurora_launch.schemas.adaptation import PriorParam


def _basic_priors() -> dict:
    return {
        "adstock_decay": {ch: {"mean": 0.4, "std": 0.05, "ess": 800} for ch in ["TV", "Digital"]},
        "hill_gamma": {ch: {"mean": 2.0, "std": 0.3, "ess": 750} for ch in ["TV", "Digital"]},
        "hill_k": {ch: {"mean": 0.8, "std": 0.15, "ess": 760} for ch in ["TV", "Digital"]},
        "seasonality_52w": [0.0] * 52,
        "trend_slope": {"mean": 0.001, "std": 0.0005, "ess": 1200},
    }


class TestPriorPredictiveSamples:
    def test_returns_n_samples(self) -> None:
        priors = {"trend_slope": PriorParam(mean=0.001, std=0.0005, source="proxy_transferred")}
        samples = prior_predictive_samples_real(
            recipient_priors=priors, horizon_weeks=26, n_samples=50, seed=42
        )
        assert len(samples) == 50

    def test_each_sample_has_correct_horizon(self) -> None:
        priors = {"trend_slope": PriorParam(mean=0.0, std=0.001, source="proxy_transferred")}
        samples = prior_predictive_samples_real(
            recipient_priors=priors, horizon_weeks=12, n_samples=20, seed=42
        )
        for s in samples:
            assert len(s.weekly_values) == 12

    def test_deterministic_seed(self) -> None:
        priors = {"trend_slope": PriorParam(mean=0.001, std=0.0005, source="proxy_transferred")}
        samples_a = prior_predictive_samples_real(priors, horizon_weeks=12, n_samples=10, seed=42)
        samples_b = prior_predictive_samples_real(priors, horizon_weeks=12, n_samples=10, seed=42)
        # Same seed → identical output
        for a, b in zip(samples_a, samples_b, strict=False):
            assert a.weekly_values == b.weekly_values

    def test_different_seeds_different_samples(self) -> None:
        priors = {"trend_slope": PriorParam(mean=0.001, std=0.0005, source="proxy_transferred")}
        samples_a = prior_predictive_samples_real(priors, horizon_weeks=12, n_samples=10, seed=42)
        samples_b = prior_predictive_samples_real(priors, horizon_weeks=12, n_samples=10, seed=100)
        # Different seed → different samples
        assert samples_a[0].weekly_values != samples_b[0].weekly_values

    def test_all_values_non_negative(self) -> None:
        priors = {"trend_slope": PriorParam(mean=0.0, std=0.001, source="proxy_transferred")}
        samples = prior_predictive_samples_real(priors, horizon_weeks=20, n_samples=30, seed=42)
        for s in samples:
            for v in s.weekly_values:
                assert v >= 0


class TestSensitivityAnalysis:
    def test_default_4_perturbations(self) -> None:
        results = sensitivity_analysis_real()
        # 4 anchors × 4 perturbations
        assert len(results) == 16

    def test_custom_perturbations(self) -> None:
        results = sensitivity_analysis_real(perturbation_pcts=[-30, 30])
        # 4 anchors × 2 perturbations
        assert len(results) == 8

    def test_market_size_sensitivity_linear(self) -> None:
        results = sensitivity_analysis_real(perturbation_pcts=[10, 20])
        market_results = [r for r in results if r.anchor_field == "market_size"]
        assert len(market_results) == 2
        # Linear: 20% perturbation → 20% delta (sens=1.0)
        delta_20 = next(r for r in market_results if r.perturbation_pct == 20).forecast_delta_pct
        assert delta_20 == 20.0

    def test_pricing_sensitivity_lower_than_market_size(self) -> None:
        results = sensitivity_analysis_real(perturbation_pcts=[20])
        market = next(r for r in results if r.anchor_field == "market_size")
        pricing = next(r for r in results if r.anchor_field == "pricing_index")
        # Pricing sens=0.5 < market sens=1.0
        assert abs(pricing.forecast_delta_pct) < abs(market.forecast_delta_pct)

    def test_ci_widening_grows_с_perturbation(self) -> None:
        results = sensitivity_analysis_real(perturbation_pcts=[10, 30])
        market_results = [r for r in results if r.anchor_field == "market_size"]
        ci_10 = next(r for r in market_results if r.perturbation_pct == 10).ci_widening_pct
        ci_30 = next(r for r in market_results if r.perturbation_pct == 30).ci_widening_pct
        assert ci_30 > ci_10


class TestHeatmap:
    def test_heatmap_returns_per_channel_strength(self) -> None:
        priors = extract_proxy_priors_from_posterior(_basic_priors(), ["TV", "Digital"], "test")
        heatmap = per_channel_transfer_heatmap_real(priors)

        assert heatmap.channels == ["TV", "Digital"]
        assert len(heatmap.transfer_strength) == 2
        assert len(heatmap.rationale) == 2
        # All в [0, 1] range
        for s in heatmap.transfer_strength:
            assert 0.0 <= s <= 1.0

    def test_tighter_posterior_higher_strength(self) -> None:
        # Build two priors: tight std vs loose std
        tight_summary = _basic_priors()
        loose_summary = _basic_priors()
        loose_summary["adstock_decay"]["TV"]["std"] = 0.50  # very loose

        tight_priors = extract_proxy_priors_from_posterior(tight_summary, ["TV", "Digital"], "tight")
        loose_priors = extract_proxy_priors_from_posterior(loose_summary, ["TV", "Digital"], "loose")

        tight_heatmap = per_channel_transfer_heatmap_real(tight_priors)
        loose_heatmap = per_channel_transfer_heatmap_real(loose_priors)

        tight_tv_strength = tight_heatmap.transfer_strength[tight_heatmap.channels.index("TV")]
        loose_tv_strength = loose_heatmap.transfer_strength[loose_heatmap.channels.index("TV")]

        # Tighter posterior → higher transfer confidence
        assert tight_tv_strength >= loose_tv_strength

    def test_empty_priors_returns_empty_heatmap(self) -> None:
        from aurora_launch.schemas.adaptation import ProxyPriors
        empty_priors = ProxyPriors(
            adstock_decay_per_channel={},
            hill_gamma_per_channel={},
            hill_half_saturation_per_channel={},
            category_seasonality=[0.0] * 52,
            long_term_trend_slope=0.0,
            proxy_model_hash="empty",
            extraction_method="posterior_mean_std",
        )
        heatmap = per_channel_transfer_heatmap_real(empty_priors)
        assert heatmap.channels == []
        assert heatmap.transfer_strength == []


class TestValidateTransferHandler:
    def test_handler_returns_full_report(self) -> None:
        result = asyncio.run(validate_transfer(ctx=None))
        assert result["step_type"] == "transfer_validate"
        assert result["stub"] is False  # real implementation, not stub
        assert result["prior_predictive_samples_generated"] >= 50
        assert "sensitivity_results" in result
        assert "per_channel_heatmap" in result
        assert "anchor_uncertainty_decomp" in result

    def test_handler_uncertainty_decomp_sums_к_unity(self) -> None:
        result = asyncio.run(validate_transfer(ctx=None))
        decomp = result["anchor_uncertainty_decomp"]
        total = (
            decomp["market_size_contribution"] + decomp["distribution_contribution"]
            + decomp["pricing_contribution"] + decomp["creative_contribution"]
            + decomp["competitive_contribution"] + decomp["proxy_transfer_contribution"]
        )
        assert abs(total - 1.0) < 0.05
