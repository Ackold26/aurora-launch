"""Phase Magic M-02: Bayesian+priors closed-form posterior tests."""

from __future__ import annotations

import numpy as np
import pytest

from aurora_launch.engines.bayesian_with_priors import (
    DEFAULT_POSTERIOR_SAMPLES,
    BayesianWithPriorsResult,
    fit_bayesian_with_priors,
)
from aurora_launch.engines.ols_with_priors import MIN_OBSERVATIONS


def _make_inputs(
    n_periods: int = 12,
    n_channels: int = 2,
    seed: int = 42,
    true_beta: tuple[float, ...] = (0.5, 0.3),
):
    rng = np.random.default_rng(seed)
    channel_ids = [f"ch_{i}" for i in range(n_channels)]
    adstock_decays = {c: 0.5 for c in channel_ids}
    hill_params = {c: (1.5, 100_000.0) for c in channel_ids}
    historical_spend = {
        c: rng.uniform(50_000, 200_000, size=n_periods).tolist()
        for c in channel_ids
    }
    from aurora_launch.engines.pure_transfer_engine import (
        apply_geometric_adstock,
        hill_saturation,
    )

    X = np.zeros((n_periods, n_channels))
    for k, c in enumerate(channel_ids):
        adstock = apply_geometric_adstock(historical_spend[c], 0.5)
        X[:, k] = hill_saturation(adstock, 1.5, 100_000.0)
    true_beta_arr = np.array(true_beta[:n_channels])
    y = X @ true_beta_arr + rng.normal(0, 0.01, size=n_periods)
    return {
        "recipient_y": y.tolist(),
        "historical_spend": historical_spend,
        "channel_ids": channel_ids,
        "adstock_decays": adstock_decays,
        "hill_params": hill_params,
        "proxy_beta_means": {c: 0.4 for c in channel_ids},
        "proxy_beta_stds": {c: 0.2 for c in channel_ids},
    }


class TestPosteriorShape:
    def test_returns_correct_sample_count(self) -> None:
        inputs = _make_inputs(n_periods=15)
        result = fit_bayesian_with_priors(**inputs, n_samples=300, seed=1)
        assert result.beta_samples.shape == (300, 2)
        assert result.n_samples == 300

    def test_default_sample_count_is_500(self) -> None:
        inputs = _make_inputs(n_periods=15)
        result = fit_bayesian_with_priors(**inputs, seed=1)
        assert result.n_samples == DEFAULT_POSTERIOR_SAMPLES
        assert result.beta_samples.shape[0] == DEFAULT_POSTERIOR_SAMPLES

    def test_beta_cov_is_psd_symmetric(self) -> None:
        inputs = _make_inputs(n_periods=20)
        result = fit_bayesian_with_priors(**inputs, seed=1)
        # Symmetric
        np.testing.assert_allclose(result.beta_cov, result.beta_cov.T, atol=1e-9)
        # PSD via eigenvalues
        eigvals = np.linalg.eigvalsh(result.beta_cov)
        assert all(e >= -1e-9 for e in eigvals)


class TestSampleStatistics:
    def test_sample_mean_matches_posterior_mean(self) -> None:
        inputs = _make_inputs(n_periods=20)
        result = fit_bayesian_with_priors(**inputs, n_samples=2000, seed=42)
        # Empirical mean should match beta_mean within MC error
        emp_mean = result.beta_samples.mean(axis=0)
        np.testing.assert_allclose(emp_mean, result.beta_mean, atol=0.05)

    def test_sample_cov_matches_posterior_cov(self) -> None:
        inputs = _make_inputs(n_periods=20)
        result = fit_bayesian_with_priors(**inputs, n_samples=3000, seed=42)
        emp_cov = np.cov(result.beta_samples.T)
        # Allow 30% MC error для covariance entries (3000 samples)
        diag_post = np.diag(result.beta_cov)
        diag_emp = np.diag(emp_cov)
        for i in range(len(diag_post)):
            rel_err = abs(diag_emp[i] - diag_post[i]) / max(diag_post[i], 1e-9)
            assert rel_err < 0.5, f"Channel {i} cov mismatch: {rel_err}"


class TestConvergenceDiagnostics:
    def test_r_hat_perfect_for_analytical(self) -> None:
        inputs = _make_inputs(n_periods=15)
        result = fit_bayesian_with_priors(**inputs, seed=1)
        assert result.r_hat == 1.0

    def test_ess_equals_n_samples(self) -> None:
        inputs = _make_inputs(n_periods=15)
        result = fit_bayesian_with_priors(**inputs, n_samples=750, seed=1)
        assert result.ess == 750.0

    def test_zero_divergent_transitions(self) -> None:
        inputs = _make_inputs(n_periods=15)
        result = fit_bayesian_with_priors(**inputs, seed=1)
        assert result.divergent_count == 0

    def test_converged_true(self) -> None:
        inputs = _make_inputs(n_periods=15)
        result = fit_bayesian_with_priors(**inputs, seed=1)
        assert result.converged is True


class TestInputValidation:
    def test_too_few_observations_raises(self) -> None:
        inputs = _make_inputs(n_periods=3)
        with pytest.raises(ValueError, match="observations"):
            fit_bayesian_with_priors(**inputs)

    def test_n_samples_zero_raises(self) -> None:
        inputs = _make_inputs(n_periods=10)
        with pytest.raises(ValueError, match="n_samples"):
            fit_bayesian_with_priors(**inputs, n_samples=0)


class TestReproducibility:
    def test_same_seed_produces_same_samples(self) -> None:
        inputs = _make_inputs(n_periods=15)
        r1 = fit_bayesian_with_priors(**inputs, seed=99)
        r2 = fit_bayesian_with_priors(**inputs, seed=99)
        np.testing.assert_array_equal(r1.beta_samples, r2.beta_samples)

    def test_different_seeds_produce_different_samples(self) -> None:
        inputs = _make_inputs(n_periods=15)
        r1 = fit_bayesian_with_priors(**inputs, seed=1)
        r2 = fit_bayesian_with_priors(**inputs, seed=2)
        assert not np.array_equal(r1.beta_samples, r2.beta_samples)


class TestDispatchIntegration:
    def test_mode4_routes_к_real_handler(self) -> None:
        from aurora_launch.engines.dispatch_table import _MODE_DISPATCH
        from aurora_launch.engines.router import EngineMode

        handler = _MODE_DISPATCH[EngineMode.BAYESIAN_WITH_PROXY_PRIORS]
        assert handler.__name__ == "_handle_bayesian_with_proxy_priors"

    def test_fallback_when_no_recipient_y(self) -> None:
        from aurora_launch.engines.dispatch_table import (
            _handle_bayesian_with_proxy_priors,
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
        forecast, sig = _handle_bayesian_with_proxy_priors(
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
        assert sig == "bayesian_with_proxy_priors_fallback_v1"

    def test_real_path_when_inputs_complete(self) -> None:
        from aurora_launch.engines.dispatch_table import (
            DispatchExtras,
            _handle_bayesian_with_proxy_priors,
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
        recipient_y = [50_000.0 + 100.0 * i for i in range(10)]

        warnings: list[str] = []
        forecast, sig = _handle_bayesian_with_proxy_priors(
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
        assert sig == "bayesian_with_proxy_priors_v1"
        assert any("converged" in w for w in warnings)
        assert any("R̂" in w for w in warnings)
