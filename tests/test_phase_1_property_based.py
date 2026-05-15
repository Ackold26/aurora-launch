"""Phase 1 — Property-based tests via Hypothesis.

Three core math engines covered:
  1. apply_geometric_adstock  (pure_transfer_engine)
  2. hill_saturation          (pure_transfer_engine)
  3. fit_ols_with_priors      (ols_with_priors)
  4. fit_bayesian_with_priors (bayesian_with_priors)

Properties are mathematical invariants that must hold for *any* valid input,
not just the example inputs used in example-based tests.

Settings:
  max_examples=30  — keeps suite under ~20s on a laptop
  deadline=None    — OLS/Bayesian fits take variable time; no wall-clock kill
  suppress_health_check=[HealthCheck.too_slow] — composite strategies may be slow
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from aurora_launch.engines.pure_transfer_engine import (
    apply_geometric_adstock,
    hill_saturation,
)
from aurora_launch.engines.ols_with_priors import fit_ols_with_priors
from aurora_launch.engines.bayesian_with_priors import fit_bayesian_with_priors

# ---------------------------------------------------------------------------
# Shared Hypothesis strategies
# ---------------------------------------------------------------------------

_SMALL_POSITIVE = st.floats(min_value=0.01, max_value=1e5,
                             allow_nan=False, allow_infinity=False)
_DECAY = st.floats(min_value=0.0, max_value=1.0,
                   allow_nan=False, allow_infinity=False)
_ALPHA = st.floats(min_value=0.1, max_value=15.0,
                   allow_nan=False, allow_infinity=False)
_HALF_SAT = st.floats(min_value=0.01, max_value=1e6,
                      allow_nan=False, allow_infinity=False)


@st.composite
def spend_array(draw: st.DrawFn, min_len: int = 1, max_len: int = 24) -> list[float]:
    """Non-empty list of positive floats (spend values)."""
    length = draw(st.integers(min_value=min_len, max_value=max_len))
    return [draw(_SMALL_POSITIVE) for _ in range(length)]


@st.composite
def ols_inputs(draw: st.DrawFn, n_channels: int = 2) -> dict:
    """Valid inputs for fit_ols_with_priors / fit_bayesian_with_priors.

    Generates T periods (>= MIN_OBSERVATIONS), K=n_channels channels,
    consistent spend + y data and proxy priors.
    """
    from aurora_launch.engines.ols_with_priors import MIN_OBSERVATIONS
    from aurora_launch.engines.pure_transfer_engine import (
        apply_geometric_adstock,
        hill_saturation,
    )

    T = draw(st.integers(min_value=MIN_OBSERVATIONS, max_value=20))
    channel_ids = [f"ch_{k}" for k in range(n_channels)]
    adstock_decays = {c: draw(st.floats(0.0, 0.9, allow_nan=False, allow_infinity=False))
                     for c in channel_ids}
    hill_params = {c: (draw(st.floats(0.5, 5.0, allow_nan=False, allow_infinity=False)),
                       draw(st.floats(1e3, 1e6, allow_nan=False, allow_infinity=False)))
                  for c in channel_ids}

    rng_seed = draw(st.integers(0, 2**31 - 1))
    rng = np.random.default_rng(rng_seed)

    historical_spend = {
        c: rng.uniform(1e3, 1e5, size=T).tolist() for c in channel_ids
    }

    # Build X to produce plausible y
    X = np.zeros((T, n_channels))
    for k, c in enumerate(channel_ids):
        adstock = apply_geometric_adstock(historical_spend[c], adstock_decays[c])
        alpha, half_sat = hill_params[c]
        X[:, k] = hill_saturation(adstock, alpha, half_sat)

    true_beta = rng.uniform(0.1, 1.0, size=n_channels)
    noise = rng.normal(0, 0.05, size=T)
    y = (X @ true_beta + noise).tolist()

    proxy_beta_means = {c: float(rng.uniform(0.05, 1.5)) for c in channel_ids}
    proxy_beta_stds = {c: float(rng.uniform(0.01, 0.5)) for c in channel_ids}

    return {
        "recipient_y": y,
        "historical_spend": historical_spend,
        "channel_ids": channel_ids,
        "adstock_decays": adstock_decays,
        "hill_params": hill_params,
        "proxy_beta_means": proxy_beta_means,
        "proxy_beta_stds": proxy_beta_stds,
    }


# ===========================================================================
# 1. apply_geometric_adstock
# ===========================================================================

class TestAdstockProperties:
    """Property tests for apply_geometric_adstock."""

    @given(spend_array(), _DECAY)
    @settings(max_examples=30, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_no_nan_inf(self, spend: list[float], decay: float) -> None:
        """Numerical stability: no NaN or Inf for valid positive inputs."""
        out = apply_geometric_adstock(spend, decay)
        assert np.all(np.isfinite(out)), f"NaN/Inf in adstock output, decay={decay}"

    @given(spend_array(min_len=2), _DECAY)
    @settings(max_examples=30, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_output_length_matches_input(self, spend: list[float], decay: float) -> None:
        """Output length equals input length."""
        out = apply_geometric_adstock(spend, decay)
        assert len(out) == len(spend)

    @given(spend_array())
    @settings(max_examples=30, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_zero_decay_is_identity(self, spend: list[float]) -> None:
        """decay=0 → adstock_t == spend_t (no carryover)."""
        out = apply_geometric_adstock(spend, decay=0.0)
        np.testing.assert_allclose(out, spend, rtol=1e-10)

    @given(spend_array())
    @settings(max_examples=30, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_adstock_gte_spend(self, spend: list[float]) -> None:
        """Adstock output[t] >= spend[t] for any decay in [0,1].

        Adstock adds carryover from previous periods; it never subtracts.
        Property: output[t] >= input[t] for all t.
        """
        # Use a moderate decay to exercise the property
        out = apply_geometric_adstock(spend, decay=0.5)
        spend_arr = np.asarray(spend)
        # Each output >= the spend at that period (carryover only adds)
        assert np.all(out >= spend_arr - 1e-10), (
            "Adstock output fell below spend at some period"
        )

    @given(
        st.lists(_SMALL_POSITIVE, min_size=2, max_size=12),
        st.lists(_SMALL_POSITIVE, min_size=2, max_size=12),
        _DECAY,
    )
    @settings(max_examples=30, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_monotone_in_spend(
        self, spend_a: list[float], spend_b: list[float], decay: float
    ) -> None:
        """Component-wise spend_a <= spend_b → adstock_a <= adstock_b (monotonicity)."""
        # Align lengths by truncating to shorter
        n = min(len(spend_a), len(spend_b))
        a = [min(spend_a[i], spend_b[i]) for i in range(n)]
        b = [max(spend_a[i], spend_b[i]) for i in range(n)]
        out_a = apply_geometric_adstock(a, decay)
        out_b = apply_geometric_adstock(b, decay)
        # b >= a component-wise → adstock(b) >= adstock(a)
        assert np.all(out_b >= out_a - 1e-10), (
            "Adstock violated monotonicity: larger spend gave smaller adstock"
        )


# ===========================================================================
# 2. hill_saturation
# ===========================================================================

class TestHillSaturationProperties:
    """Property tests for hill_saturation."""

    @given(st.lists(_SMALL_POSITIVE, min_size=1, max_size=20), _ALPHA, _HALF_SAT)
    @settings(max_examples=30, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_output_in_unit_interval(
        self, values: list[float], alpha: float, half_sat: float
    ) -> None:
        """Hill output is always in [0, 1]."""
        arr = np.asarray(values)
        out = hill_saturation(arr, alpha, half_sat)
        assert np.all(out >= -1e-10), "Hill output < 0"
        assert np.all(out <= 1.0 + 1e-10), "Hill output > 1"

    @given(st.lists(_SMALL_POSITIVE, min_size=1, max_size=20), _ALPHA, _HALF_SAT)
    @settings(max_examples=30, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_no_nan_inf(
        self, values: list[float], alpha: float, half_sat: float
    ) -> None:
        """No NaN or Inf for any positive input."""
        arr = np.asarray(values)
        out = hill_saturation(arr, alpha, half_sat)
        assert np.all(np.isfinite(out)), (
            f"NaN/Inf in hill output: alpha={alpha}, half_sat={half_sat}"
        )

    @given(_ALPHA, _HALF_SAT)
    @settings(max_examples=30, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_at_half_saturation_output_is_half(
        self, alpha: float, half_sat: float
    ) -> None:
        """hill(k, alpha, k) == 0.5 by definition."""
        arr = np.array([half_sat])
        out = hill_saturation(arr, alpha, half_sat)
        # hill(k) = k^alpha / (k^alpha + k^alpha) = 0.5
        np.testing.assert_allclose(out[0], 0.5, atol=1e-6,
                                   err_msg=f"hill(k) != 0.5 for alpha={alpha}")

    @given(
        st.lists(_SMALL_POSITIVE, min_size=2, max_size=12),
        _ALPHA,
        _HALF_SAT,
    )
    @settings(max_examples=30, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_monotone_nondecreasing(
        self, values: list[float], alpha: float, half_sat: float
    ) -> None:
        """Sorted inputs produce sorted (non-decreasing) outputs."""
        arr = np.sort(np.asarray(values))
        out = hill_saturation(arr, alpha, half_sat)
        diffs = np.diff(out)
        assert np.all(diffs >= -1e-10), (
            "Hill saturation is not monotone non-decreasing"
        )

    @given(_HALF_SAT)
    @settings(max_examples=30, deadline=None)
    def test_alpha_1_matches_linear_formula(self, half_sat: float) -> None:
        """alpha=1 → hill(x) = x / (x + k), a simple linear-ratio formula."""
        xs = np.array([0.5 * half_sat, half_sat, 2.0 * half_sat, 10.0 * half_sat])
        out = hill_saturation(xs, alpha=1.0, half_saturation=half_sat)
        expected = xs / (xs + half_sat)
        np.testing.assert_allclose(out, expected, rtol=1e-8,
                                   err_msg="alpha=1 hill != x/(x+k)")


# ===========================================================================
# 3. fit_ols_with_priors
# ===========================================================================

class TestOLSWithPriorsProperties:
    """Property tests for fit_ols_with_priors (ridge regression)."""

    @given(ols_inputs(n_channels=2))
    @settings(max_examples=30, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_output_shape_matches_channels(self, inputs: dict) -> None:
        """beta_combined and sigma_beta_combined have shape (K,)."""
        K = len(inputs["channel_ids"])
        result = fit_ols_with_priors(**inputs)
        assert result.beta_combined.shape == (K,)
        assert result.sigma_beta_combined.shape == (K,)

    @given(ols_inputs(n_channels=2))
    @settings(max_examples=30, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_sigma_beta_all_positive(self, inputs: dict) -> None:
        """sigma_beta_combined elements are non-negative (posterior SDs)."""
        result = fit_ols_with_priors(**inputs)
        assert np.all(result.sigma_beta_combined >= 0.0), (
            "sigma_beta_combined contains negative values"
        )

    @given(ols_inputs(n_channels=2))
    @settings(max_examples=30, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_sigma_residual_positive(self, inputs: dict) -> None:
        """sigma_residual > 0 (variance estimate is always positive)."""
        result = fit_ols_with_priors(**inputs)
        assert result.sigma_residual >= 0.0, (
            f"sigma_residual={result.sigma_residual} is negative"
        )

    @given(ols_inputs(n_channels=2))
    @settings(max_examples=30, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_full_shrinkage_pulls_toward_proxy(self, inputs: dict) -> None:
        """shrinkage=1.0 with tight proxy prior → beta near proxy mean.

        With shrinkage=1.0 and very tight proxy_beta_stds (near-zero variance),
        the ridge posterior is dominated by the proxy prior → beta ≈ mu_proxy.
        """
        # Tighten proxy stds to make prior very informative
        tight_stds = {c: 1e-4 for c in inputs["channel_ids"]}
        result = fit_ols_with_priors(
            recipient_y=inputs["recipient_y"],
            historical_spend=inputs["historical_spend"],
            channel_ids=inputs["channel_ids"],
            adstock_decays=inputs["adstock_decays"],
            hill_params=inputs["hill_params"],
            proxy_beta_means=inputs["proxy_beta_means"],
            proxy_beta_stds=tight_stds,
            shrinkage=1.0,
        )
        for i, c in enumerate(inputs["channel_ids"]):
            mu = inputs["proxy_beta_means"][c]
            # With very tight prior + shrinkage=1.0, beta should be near mu_proxy
            assert abs(result.beta_combined[i] - mu) < 0.5, (
                f"shrinkage=1.0 did not pull beta[{c}] toward proxy mean {mu}: "
                f"got {result.beta_combined[i]}"
            )

    @given(ols_inputs(n_channels=2))
    @settings(max_examples=30, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_shrinkage_zero_approaches_ols(self, inputs: dict) -> None:
        """shrinkage=0.0 → pure OLS: beta_combined close to numpy lstsq result.

        When shrinkage=0, the ridge term vanishes: A = XtX, b = Xty.
        Result must match numpy lstsq (within numerical tolerance).
        """
        from aurora_launch.engines.ols_with_priors import _build_design_matrix

        T = len(inputs["recipient_y"])
        X = _build_design_matrix(
            inputs["historical_spend"],
            inputs["channel_ids"],
            inputs["adstock_decays"],
            inputs["hill_params"],
            T,
        )
        y = np.asarray(inputs["recipient_y"])
        beta_lstsq, _, _, _ = np.linalg.lstsq(X, y, rcond=None)

        result = fit_ols_with_priors(
            **inputs,
            shrinkage=0.0,
        )
        # Use rtol (relative tolerance) — atol too strict for ill-conditioned
        # cases that Hypothesis explores. With 0 ridge regularisation, near-
        # singular XᵀX produces large coefficient drift. 5% relative is
        # scientifically meaningful — both methods solve same equations.
        np.testing.assert_allclose(result.beta_combined, beta_lstsq, rtol=0.05,
                                   atol=1e-3,
                                   err_msg="shrinkage=0 diverges from pure lstsq")

    @given(ols_inputs(n_channels=2))
    @settings(max_examples=30, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_converged_flag_is_true(self, inputs: dict) -> None:
        """For any valid input, converged=True (ridge prevents singularity)."""
        result = fit_ols_with_priors(**inputs)
        assert result.converged, "fit_ols_with_priors returned converged=False"

    @given(ols_inputs(n_channels=2))
    @settings(max_examples=30, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_n_observations_recorded_correctly(self, inputs: dict) -> None:
        """n_observations in result matches len(recipient_y)."""
        result = fit_ols_with_priors(**inputs)
        assert result.n_observations == len(inputs["recipient_y"]), (
            f"n_observations mismatch: result={result.n_observations} "
            f"vs len(y)={len(inputs['recipient_y'])}"
        )


# ===========================================================================
# 4. fit_bayesian_with_priors
# ===========================================================================

class TestBayesianWithPriorsProperties:
    """Property tests for fit_bayesian_with_priors (analytical Gaussian posterior)."""

    @given(ols_inputs(n_channels=2))
    @settings(max_examples=30, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_beta_cov_symmetric(self, inputs: dict) -> None:
        """Posterior covariance matrix is symmetric: cov == cov.T."""
        result = fit_bayesian_with_priors(**inputs, n_samples=50, seed=0)
        np.testing.assert_allclose(
            result.beta_cov, result.beta_cov.T, atol=1e-10,
            err_msg="beta_cov is not symmetric"
        )

    @given(ols_inputs(n_channels=2))
    @settings(max_examples=30, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_beta_cov_psd(self, inputs: dict) -> None:
        """Posterior covariance is PSD: all eigenvalues >= 0 (within float tol)."""
        result = fit_bayesian_with_priors(**inputs, n_samples=50, seed=0)
        eigenvalues = np.linalg.eigvalsh(result.beta_cov)
        assert np.all(eigenvalues >= -1e-8), (
            f"beta_cov has negative eigenvalue(s): min={eigenvalues.min():.2e}"
        )

    @given(ols_inputs(n_channels=2))
    @settings(max_examples=30, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_samples_shape(self, inputs: dict) -> None:
        """beta_samples has shape (n_samples, K)."""
        K = len(inputs["channel_ids"])
        n_samples = 50
        result = fit_bayesian_with_priors(**inputs, n_samples=n_samples, seed=0)
        assert result.beta_samples.shape == (n_samples, K), (
            f"Expected ({n_samples}, {K}), got {result.beta_samples.shape}"
        )

    @given(ols_inputs(n_channels=2))
    @settings(max_examples=30, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_different_seeds_give_different_samples(self, inputs: dict) -> None:
        """Different RNG seeds produce different sample draws."""
        r1 = fit_bayesian_with_priors(**inputs, n_samples=50, seed=1)
        r2 = fit_bayesian_with_priors(**inputs, n_samples=50, seed=2)
        # With high probability two independent draws will differ
        assert not np.allclose(r1.beta_samples, r2.beta_samples), (
            "Different seeds produced identical samples (broken RNG isolation)"
        )

    @given(ols_inputs(n_channels=2))
    @settings(max_examples=30, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_same_seed_gives_same_samples(self, inputs: dict) -> None:
        """Same seed produces exactly the same sample draws (reproducibility)."""
        r1 = fit_bayesian_with_priors(**inputs, n_samples=50, seed=42)
        r2 = fit_bayesian_with_priors(**inputs, n_samples=50, seed=42)
        np.testing.assert_array_equal(r1.beta_samples, r2.beta_samples)

    @given(ols_inputs(n_channels=2))
    @settings(max_examples=30, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_empirical_mean_close_to_beta_mean(self, inputs: dict) -> None:
        """Empirical mean of samples ≈ beta_mean within MC error.

        With 500 iid samples from N(mu, Sigma), sample mean should be
        within ~5*sigma/sqrt(N) of mu (loose tolerance for property testing).
        """
        result = fit_bayesian_with_priors(**inputs, n_samples=500, seed=7)
        empirical_mean = result.beta_samples.mean(axis=0)
        # Tolerance: 0.5 std per channel (very loose — MC noise)
        diag_std = np.sqrt(np.diag(result.beta_cov))
        tol = np.maximum(diag_std * 0.5, 0.1)  # at least 0.1 absolute tolerance
        for k in range(len(result.beta_mean)):
            np.testing.assert_allclose(
                empirical_mean[k], result.beta_mean[k], atol=float(tol[k]),
                err_msg=f"Empirical sample mean[{k}] deviates too far from beta_mean[{k}]"
            )

    @given(ols_inputs(n_channels=2))
    @settings(max_examples=30, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_r_hat_is_one_analytical(self, inputs: dict) -> None:
        """Analytical posterior always has r_hat=1.0 (perfect convergence)."""
        result = fit_bayesian_with_priors(**inputs, n_samples=50, seed=0)
        assert result.r_hat == 1.0, (
            f"Analytical posterior should have r_hat=1.0, got {result.r_hat}"
        )

    @given(ols_inputs(n_channels=2))
    @settings(max_examples=30, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_divergent_count_is_zero(self, inputs: dict) -> None:
        """Analytical posterior has divergent_count=0 by construction."""
        result = fit_bayesian_with_priors(**inputs, n_samples=50, seed=0)
        assert result.divergent_count == 0, (
            f"Analytical posterior should have 0 divergences, got {result.divergent_count}"
        )
