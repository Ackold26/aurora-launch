"""Phase Magic M-02: Bayesian linear regression on recipient_y с proxy priors.

This implements Mode 4 (BAYESIAN_WITH_PROXY_PRIORS) using the closed-form
analytical posterior of Bayesian linear regression с Gaussian priors and
Gaussian likelihood (conjugate case).

Math (same ridge as M-01 но treated as Bayesian posterior):

  Prior:       β ~ N(μ_proxy, Ω)
  Likelihood:  y | β ~ N(Xβ, σ² I)
  Posterior:   β | y ~ N(β̂, Σ̂)

  where:
    β̂ = Σ̂ (Ω⁻¹ μ_proxy + Xᵀy / σ²)
    Σ̂ = (Ω⁻¹ + XᵀX / σ²)⁻¹

The ridge formulation:
  β̂ = (XᵀX + λΩ⁻¹)⁻¹ (Xᵀy + λΩ⁻¹ μ_proxy)
  Σ̂ = σ² (XᵀX + λΩ⁻¹)⁻¹

is mathematically equivalent (с λ playing the role of relative weighting
between proxy and data) and matches M-01 exactly.

Difference from M-01:
  - M-01 returns point estimate (β̂) + standard error (σ_β̂)
  - M-02 returns S posterior samples drawn from N(β̂, Σ̂)
  - Samples used downstream by decomposer / sensitivity / scenario engines
    which expect posterior_samples_real format

When real MCMC needed (non-Gaussian priors, non-conjugate likelihood):
  - bayesian_engine.train_model PyMC path remains available для full MCMC
  - Phase Magic-Math future: add `use_real_mcmc=True` parameter что delegates
    к real PyMC sampling. Costs 30-60s per fit vs ~1ms for analytical.

Per INV-04: lazy imports inside functions.
Per INV-11: explicit narrow except clauses.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from aurora_launch.engines.ols_with_priors import (
    MIN_OBSERVATIONS,
    DEFAULT_SHRINKAGE,
    fit_ols_with_priors,
)

_log = logging.getLogger(__name__)

# Default posterior sample count. 500 samples is enough для CI band
# estimation with negligible Monte Carlo error (analytical Gaussian).
DEFAULT_POSTERIOR_SAMPLES: int = 500


@dataclass(frozen=True)
class BayesianWithPriorsResult:
    """Output of fit_bayesian_with_priors — full posterior samples."""

    beta_mean: np.ndarray  # K-vector — posterior mean per channel
    beta_cov: np.ndarray  # K×K posterior covariance matrix
    beta_samples: np.ndarray  # S×K — posterior samples
    sigma_residual: float
    n_observations: int
    n_samples: int
    shrinkage_used: float
    converged: bool
    r_hat: float  # diagnostic — analytical Gaussian → 1.0 always
    ess: float  # effective sample size — analytical → n_samples
    divergent_count: int  # MCMC divergences — analytical → 0


def fit_bayesian_with_priors(
    recipient_y: Sequence[float],
    historical_spend: dict[str, Sequence[float]],
    channel_ids: list[str],
    adstock_decays: dict[str, float],
    hill_params: dict[str, tuple[float, float]],
    proxy_beta_means: dict[str, float],
    proxy_beta_stds: dict[str, float],
    shrinkage: float = DEFAULT_SHRINKAGE,
    n_samples: int = DEFAULT_POSTERIOR_SAMPLES,
    seed: int | None = None,
) -> BayesianWithPriorsResult:
    """Fit Bayesian linear regression на recipient_y с proxy β priors.

    Returns posterior samples in same format as bayesian_engine PyMC path
    (decomposer-compatible).

    Args:
        Same as fit_ols_with_priors, plus:
        n_samples: number of posterior samples to draw from analytical
            Gaussian posterior. 500 default — overhead negligible.
        seed: RNG seed для reproducibility.

    Returns:
        BayesianWithPriorsResult с posterior_samples shape (S, K).

    Raises:
        ValueError: insufficient observations или invalid input (same as M-01).
        np.linalg.LinAlgError: singular Σ̂ (rare after ridge regularisation).
    """
    if n_samples < 1:
        raise ValueError(f"n_samples must be >= 1, got {n_samples}")

    # Reuse M-01 fit logic — math identical, just need full Σ̂ matrix.
    # We re-compute here because fit_ols_with_priors only returns diagonal σ.
    ols_result = fit_ols_with_priors(
        recipient_y=recipient_y,
        historical_spend=historical_spend,
        channel_ids=channel_ids,
        adstock_decays=adstock_decays,
        hill_params=hill_params,
        proxy_beta_means=proxy_beta_means,
        proxy_beta_stds=proxy_beta_stds,
        shrinkage=shrinkage,
    )

    # Reconstruct full Σ̂ for sample correlation structure.
    from aurora_launch.engines.ols_with_priors import _build_design_matrix

    T = len(recipient_y)
    K = len(channel_ids)
    X = _build_design_matrix(
        historical_spend, channel_ids, adstock_decays, hill_params, T
    )

    proxy_var = np.array(
        [proxy_beta_stds[c] ** 2 for c in channel_ids], dtype=np.float64
    )
    proxy_var_safe = np.where(proxy_var > 1e-12, proxy_var, 1e-12)
    Omega_inv = np.diag(1.0 / proxy_var_safe)
    A = X.T @ X + shrinkage * Omega_inv

    try:
        A_inv = np.linalg.inv(A)
    except np.linalg.LinAlgError:
        A_inv = np.linalg.inv(A + 1e-8 * np.eye(K))

    sigma2 = float(ols_result.sigma_residual ** 2)
    beta_cov = sigma2 * A_inv  # K × K full posterior covariance

    # Symmetrise for numerical stability (numpy multivariate_normal needs PSD)
    beta_cov_sym = 0.5 * (beta_cov + beta_cov.T)

    rng = np.random.default_rng(seed)
    try:
        beta_samples = rng.multivariate_normal(
            mean=ols_result.beta_combined,
            cov=beta_cov_sym,
            size=n_samples,
            check_valid="warn",
            tol=1e-6,
        )
    except (np.linalg.LinAlgError, ValueError) as exc:
        # Fall back к diagonal sampling если Σ̂ not PSD (numerical edge case)
        _log.warning(
            "Bayesian+priors posterior covariance not PSD (%s) — "
            "falling back к diagonal independent sampling",
            exc,
        )
        beta_samples = np.zeros((n_samples, K))
        for k in range(K):
            beta_samples[:, k] = rng.normal(
                loc=ols_result.beta_combined[k],
                scale=ols_result.sigma_beta_combined[k],
                size=n_samples,
            )

    return BayesianWithPriorsResult(
        beta_mean=ols_result.beta_combined,
        beta_cov=beta_cov_sym,
        beta_samples=beta_samples,
        sigma_residual=ols_result.sigma_residual,
        n_observations=T,
        n_samples=n_samples,
        shrinkage_used=shrinkage,
        converged=True,
        r_hat=1.0,  # analytical Gaussian → perfect convergence by construction
        ess=float(n_samples),  # iid samples → ESS = N
        divergent_count=0,
    )
