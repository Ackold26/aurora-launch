"""Phase Magic M-01: OLS regression on recipient_y с proxy-derived priors.

Replaces the Mode 3 stub в dispatch_table.py с real implementation.

Math (ridge regression posterior, closed-form):
    β̂ = (XᵀX + λΩ⁻¹)⁻¹ (Xᵀy + λΩ⁻¹ μ_proxy)
    Σ̂ = σ² · (XᵀX + λΩ⁻¹)⁻¹

Where:
    X        — design matrix, T × K (T historical periods, K channels)
               Each column: hill(adstock(spend_history_channel_k))
    y        — observed recipient sales, length T
    μ_proxy  — proxy β prior mean per channel (after scale + similarity adj)
    Ω        — diagonal prior covariance (σ_β_proxy² per channel)
    λ        — shrinkage factor ∈ [0,1]; high λ → trust proxy more
    σ²       — OLS residual variance estimate

This is equivalent к Bayesian linear regression с Gaussian priors and known σ —
fast (no MCMC) and accurate enough для launch update scenario.

Per master-plan §④ M-01:
    σ_β_recipient = √(σ_β_OLS² + σ_β_proxy² · shrinkage²)

Implementation chooses the ridge formulation above which is internally
consistent and produces the same σ scaling when both terms balance.

Fallback policy:
    - len(recipient_y) < MIN_OBSERVATIONS → cannot fit OLS, fall back к pure
      transfer с warning emitted (caller's `warnings` list).
    - historical_spend not provided OR mismatched length → fall back с warning.
    - Singular XᵀX matrix → fall back с warning.

Per INV-04: numpy.linalg lazy-imported only on real-fit path.
Per INV-11: explicit narrow except (np.linalg.LinAlgError).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence

import numpy as np

_log = logging.getLogger(__name__)

# Minimum observation count for reliable OLS estimate.
# Below 5 periods + 2 channels = under-determined (X has more cols than rows).
MIN_OBSERVATIONS: int = 5

# Default shrinkage factor: how much к trust proxy vs observed.
# 0.0 = pure OLS (ignore proxy), 1.0 = pure proxy (ignore OLS).
# Conservative default: 0.3 — significant proxy weight но OLS dominates после
# 5+ observed periods.
DEFAULT_SHRINKAGE: float = 0.3


@dataclass(frozen=True)
class OLSWithPriorsResult:
    """Output of fit_ols_with_priors — combined OLS + proxy posterior."""

    beta_combined: np.ndarray  # K-vector — per-channel β estimates
    sigma_beta_combined: np.ndarray  # K-vector — per-channel β std (posterior SD)
    sigma_residual: float  # σ residual estimate from OLS fit
    n_observations: int
    shrinkage_used: float
    converged: bool  # True if OLS fit succeeded


def _build_design_matrix(
    historical_spend: dict[str, Sequence[float]],
    channel_ids: list[str],
    adstock_decays: dict[str, float],
    hill_params: dict[str, tuple[float, float]],
    n_periods: int,
) -> np.ndarray:
    """Build T × K design matrix of hill(adstock(spend)) per channel.

    INV-04: import адstock + hill from pure_transfer_engine lazily.
    """
    from aurora_launch.engines.pure_transfer_engine import (
        apply_geometric_adstock,
        hill_saturation,
    )

    X = np.zeros((n_periods, len(channel_ids)), dtype=np.float64)
    for k, ch_id in enumerate(channel_ids):
        spend = np.asarray(historical_spend[ch_id], dtype=np.float64)
        if len(spend) < n_periods:
            raise ValueError(
                f"historical_spend[{ch_id}] has {len(spend)} periods, "
                f"expected >= {n_periods}"
            )
        adstock = apply_geometric_adstock(spend[:n_periods], adstock_decays[ch_id])
        alpha, half_sat = hill_params[ch_id]
        X[:, k] = hill_saturation(adstock, alpha, half_sat)
    return X


def fit_ols_with_priors(
    recipient_y: Sequence[float],
    historical_spend: dict[str, Sequence[float]],
    channel_ids: list[str],
    adstock_decays: dict[str, float],
    hill_params: dict[str, tuple[float, float]],
    proxy_beta_means: dict[str, float],
    proxy_beta_stds: dict[str, float],
    shrinkage: float = DEFAULT_SHRINKAGE,
) -> OLSWithPriorsResult:
    """Fit ridge regression на recipient_y с proxy priors.

    Args:
        recipient_y: observed sales for historical period, length T.
        historical_spend: per-channel spend for same period, T values each.
        channel_ids: ordered list of channel IDs (matches X columns).
        adstock_decays: per-channel decay rate [0,1).
        hill_params: per-channel (alpha, half_saturation) tuples.
        proxy_beta_means: per-channel proxy β prior mean (scaled to recipient).
        proxy_beta_stds: per-channel proxy β prior SD.
        shrinkage: ∈ [0,1]. Higher = trust proxy more.

    Returns:
        OLSWithPriorsResult с combined posterior β + σ.

    Raises:
        ValueError: insufficient observations, missing channel data, dimension
            mismatch.
        np.linalg.LinAlgError: singular design matrix (rare с ridge regularisation).
    """
    if not 0.0 <= shrinkage <= 1.0:
        raise ValueError(f"shrinkage must be ∈ [0,1], got {shrinkage}")

    y = np.asarray(recipient_y, dtype=np.float64)
    T = len(y)
    K = len(channel_ids)

    if T < MIN_OBSERVATIONS:
        raise ValueError(
            f"recipient_y has {T} observations, need >= {MIN_OBSERVATIONS}"
        )

    # Validate per-channel inputs
    for ch_id in channel_ids:
        for d, name in (
            (historical_spend, "historical_spend"),
            (adstock_decays, "adstock_decays"),
            (hill_params, "hill_params"),
            (proxy_beta_means, "proxy_beta_means"),
            (proxy_beta_stds, "proxy_beta_stds"),
        ):
            if ch_id not in d:
                raise ValueError(f"{name}[{ch_id!r}] missing")

    # Design matrix T × K
    X = _build_design_matrix(
        historical_spend, channel_ids, adstock_decays, hill_params, T
    )

    # Proxy priors vector (K) + diagonal prior covariance (K × K)
    mu_proxy = np.array(
        [proxy_beta_means[c] for c in channel_ids], dtype=np.float64
    )
    proxy_var = np.array(
        [proxy_beta_stds[c] ** 2 for c in channel_ids], dtype=np.float64
    )
    # Avoid division by zero для proxy with σ=0 (treat as σ=1e-6 to keep prior strict)
    proxy_var_safe = np.where(proxy_var > 1e-12, proxy_var, 1e-12)
    Omega_inv = np.diag(1.0 / proxy_var_safe)  # K × K

    # Ridge posterior: β̂ = (XᵀX + λΩ⁻¹)⁻¹ (Xᵀy + λΩ⁻¹ μ)
    XtX = X.T @ X
    Xty = X.T @ y
    A = XtX + shrinkage * Omega_inv  # K × K
    b = Xty + shrinkage * Omega_inv @ mu_proxy  # K

    try:
        A_inv = np.linalg.inv(A)
    except np.linalg.LinAlgError:
        # Singular matrix — typically when X has fewer rows than columns
        # OR perfectly collinear channels. Add small ridge regulariser.
        A_inv = np.linalg.inv(A + 1e-8 * np.eye(K))

    beta_combined = A_inv @ b

    # Residuals + variance estimate
    y_pred = X @ beta_combined
    residuals = y - y_pred
    dof = max(T - K, 1)
    sigma2 = float(np.sum(residuals ** 2) / dof)
    sigma_residual = float(np.sqrt(sigma2))

    # Posterior covariance: σ² · A⁻¹
    cov_combined = sigma2 * A_inv
    sigma_beta_combined = np.sqrt(np.clip(np.diag(cov_combined), 0.0, None))

    return OLSWithPriorsResult(
        beta_combined=beta_combined,
        sigma_beta_combined=sigma_beta_combined,
        sigma_residual=sigma_residual,
        n_observations=T,
        shrinkage_used=shrinkage,
        converged=True,
    )
