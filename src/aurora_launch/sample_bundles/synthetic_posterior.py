"""Synthetic posterior derivation от Эконометрика dataset (Phase Σ.0.4 + R-02 audit fix).

For pilot demo bundles мы НЕ запускаем real PyMC training (~5 min per scenario,
slow for onboarding UX). Instead, we derive posterior_samples synthetically
from observed correlations between adstock+hill-transformed spend и sales.

**R-02 audit fix (2026-05-15):** previous version applied ridge regression on
**raw spend** — produced β с different semantics than bayesian_engine output.
bayesian_engine fits β on `hill(adstock(spend))`. Pure_transfer_engine later
applies that same transform in forecast computation. Without matching
preprocessing here, synthetic β was 2-5× wrong magnitude, producing nonsense
sample bundle forecasts.

**Current pipeline (corrected):**

  spend → adstock(spend, decay) → hill(adstock, alpha, gamma) → ridge fit β

  β_mean[c]    = ridge coef on hill(adstock(spend_c)), normalised
  β_std[c]     = bootstrap std-error (N=200 resamples)
  alpha[c]     = default 2.0 (OTC sensible)
  gamma[c]     = default 2.0 normalised (= 2× median spend)
  decay[c]     = default 0.5 (geometric)
  intercept    = constant baseline (0 in normalised, expanded в downstream)
  control_betas = [] empty (no control variables в synthetic case)

This matches bayesian_engine output schema:
  posterior_samples = {
    media_betas, alphas, gammas, adstock_decay,
    intercept,          # R-12 fix: was missing — decomposer KeyError
    control_betas,      # R-12 fix: was missing
  }

This is NOT a substitute for real Bayesian training (that's still required
for pilot live customers). It IS sufficient for UX demo flows + integration
tests + first-run wow scenarios.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

from aurora_launch.sample_bundles.econometrica_xlsx_adapter import (
    EconometricaDataset,
)

_log = logging.getLogger(__name__)

DEFAULT_N_SAMPLES = 2000
DEFAULT_HILL_ALPHA = 2.0
DEFAULT_HILL_GAMMA_NORMALISED = 2.0  # half-saturation at 2× median spend (normalised)
DEFAULT_ADSTOCK_DECAY = 0.5
DEFAULT_RIDGE_LAMBDA = 1e-3
DEFAULT_BOOTSTRAP_N = 200
DEFAULT_INTERCEPT_STD = 0.1  # narrow prior on baseline intercept


class SyntheticPosteriorError(RuntimeError):
    """Raised on data shape / regression failure."""


@dataclass(frozen=True)
class SyntheticPosteriorResult:
    """Synthetic posterior + normalization + config — drop-in for ProxyBundle."""

    posterior_samples: dict[str, np.ndarray]
    normalization: dict[str, Any]
    config: dict[str, Any]
    media_cols: list[str]
    n_proxy_observations: int


def _apply_geometric_adstock(spend: np.ndarray, decay: float) -> np.ndarray:
    """Geometric adstock: adstock_t = spend_t + decay × adstock_{t-1}.

    Returns same shape as input. Single-channel 1D array.
    """
    if not 0.0 <= decay <= 1.0:
        raise SyntheticPosteriorError(f"decay must be в [0, 1], got {decay}")
    out = np.zeros_like(spend, dtype=float)
    if len(spend) == 0:
        return out
    out[0] = spend[0]
    for t in range(1, len(spend)):
        out[t] = spend[t] + decay * out[t - 1]
    return out


def _hill_saturation(
    adstock: np.ndarray, alpha: float, half_saturation: float
) -> np.ndarray:
    """Hill saturation: x^alpha / (x^alpha + k^alpha).

    Returns same shape as input.
    """
    if alpha <= 0 or half_saturation <= 0:
        raise SyntheticPosteriorError(
            f"alpha и half_saturation must be > 0; got {alpha}, {half_saturation}"
        )
    x = np.clip(adstock, 0.0, None)
    with np.errstate(over="ignore", invalid="ignore"):
        x_pow = np.power(x, alpha)
        k_pow = np.float64(half_saturation) ** np.float64(alpha)
    denom = x_pow + k_pow
    # Avoid divide-by-zero for all-zero spend channels
    return np.where(denom > 0, x_pow / denom, 0.0)


def _build_transformed_design_matrix(
    dataset: EconometricaDataset,
    *,
    adstock_decay: float = DEFAULT_ADSTOCK_DECAY,
    hill_alpha: float = DEFAULT_HILL_ALPHA,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """Build (X_transformed, X_normalised, y, channel_order).

    **R-02 audit fix:** transform spend → adstock → hill BEFORE returning
    design matrix. Earlier version returned raw spend, which produced β
    с wrong semantics vs bayesian_engine downstream.

    Steps per channel:
      1. raw_spend → geometric_adstock(decay)
      2. adstock → hill(alpha=2.0, half_saturation=median_adstock × 2)
         Hill half_saturation set per-channel from data so transform is
         well-conditioned regardless of spend magnitude differences.
      3. Normalise transformed values к [0, 1] range (matches bayesian downstream)

    Returns:
      X_transformed: shape (n_periods, n_channels) — hill-adstock applied
      X_normalised: shape same — normalised к unit scale (regression input)
      y: shape (n_periods,) — raw brand sales
      channel_order: list of channel IDs
    """
    channel_ids = list(dataset.channel_ids)
    if not channel_ids:
        raise SyntheticPosteriorError("Dataset has no channels")

    raw_spend = np.array(
        [dataset.spend_by_channel[ch] for ch in channel_ids], dtype=float
    ).T  # (n_periods, n_channels)
    y = np.array(dataset.sales_brand, dtype=float)

    if raw_spend.shape[0] != len(y):
        raise SyntheticPosteriorError(
            f"X rows {raw_spend.shape[0]} ≠ y length {len(y)}"
        )
    if raw_spend.shape[0] < 6:
        raise SyntheticPosteriorError(
            f"Dataset has {raw_spend.shape[0]} periods — need ≥6 для usable regression"
        )

    # Per-channel: adstock → hill transform
    n_periods, n_channels = raw_spend.shape
    X_transformed = np.zeros_like(raw_spend)
    for c in range(n_channels):
        adstocked = _apply_geometric_adstock(raw_spend[:, c], adstock_decay)
        # Half-saturation: 2× median of non-zero adstock values
        positive = adstocked[adstocked > 0]
        if len(positive) > 0:
            half_sat = 2.0 * float(np.median(positive))
        else:
            half_sat = 1.0  # all-zero channel — hill will produce all zeros
        X_transformed[:, c] = _hill_saturation(adstocked, hill_alpha, half_sat)

    # Normalise по channel means (matches bayesian_engine downstream)
    transformed_means = X_transformed.mean(axis=0)
    # Avoid divide-by-zero for all-zero channels (e.g., placeholder)
    transformed_means = np.where(transformed_means > 0, transformed_means, 1.0)
    X_normalised = X_transformed / transformed_means

    return X_transformed, X_normalised, y, channel_ids


def _ridge_solve(
    X: np.ndarray, y: np.ndarray, lam: float = DEFAULT_RIDGE_LAMBDA
) -> np.ndarray:
    """Ridge regression closed form: β = (X'X + λI)^-1 X'y."""
    n_features = X.shape[1]
    XtX = X.T @ X
    Xty = X.T @ y
    reg = lam * np.trace(XtX) / max(n_features, 1) * np.eye(n_features)
    try:
        beta = np.linalg.solve(XtX + reg, Xty)
    except np.linalg.LinAlgError as exc:
        raise SyntheticPosteriorError(f"Ridge solve failed: {exc}") from exc
    return beta


def _bootstrap_beta_std(
    X: np.ndarray, y: np.ndarray, n_bootstrap: int = DEFAULT_BOOTSTRAP_N,
    seed: int = 42,
) -> np.ndarray:
    """Bootstrap std of β by resampling rows."""
    rng = np.random.default_rng(seed)
    n_rows = X.shape[0]
    betas = np.zeros((n_bootstrap, X.shape[1]))
    for b in range(n_bootstrap):
        idx = rng.integers(0, n_rows, size=n_rows)
        X_b = X[idx]
        y_b = y[idx]
        try:
            betas[b] = _ridge_solve(X_b, y_b)
        except SyntheticPosteriorError:
            betas[b] = betas[b - 1] if b > 0 else 0.0
    return np.std(betas, axis=0)


def _generate_samples_normal(
    mean: float, std: float, n_samples: int, *, clip_negative: bool = True,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    rng = rng or np.random.default_rng(0)
    samples = rng.normal(loc=mean, scale=max(std, 1e-6), size=n_samples)
    if clip_negative:
        samples = np.clip(samples, 0.0, None)
    return samples


def derive_synthetic_posterior(
    dataset: EconometricaDataset,
    *,
    n_samples: int = DEFAULT_N_SAMPLES,
    hill_alpha: float = DEFAULT_HILL_ALPHA,
    adstock_decay: float = DEFAULT_ADSTOCK_DECAY,
    seed: int = 42,
) -> SyntheticPosteriorResult:
    """Derive synthetic posterior from Эконометрика dataset (R-02 + R-12 audit fix).

    Output schema-compatible с bayesian_engine train_model:
        posterior_samples = {
            'media_betas': ndarray(n_channels, n_samples),
            'alphas': ndarray(n_channels, n_samples),
            'gammas': ndarray(n_channels, n_samples),
            'adstock_decay': ndarray(n_channels, n_samples),
            'intercept': ndarray(n_samples,),          # R-12 fix
            'control_betas': ndarray(0, n_samples),    # R-12 fix (empty)
        }
        normalization = {'y_mean', 'y_std', ...}
        config = {'media_columns': [...], 'mode': 'sales', ...}

    Args:
        dataset: EconometricaDataset
        n_samples: posterior sample count per parameter (default 2000)
        hill_alpha: hill shape (default 2.0, OTC sensible)
        adstock_decay: adstock decay (default 0.5)
        seed: RNG seed for determinism
    """
    X_transformed, X_norm, y, channel_ids = _build_transformed_design_matrix(
        dataset, adstock_decay=adstock_decay, hill_alpha=hill_alpha
    )
    n_channels = X_norm.shape[1]

    # Normalise y for regression (bayesian_engine uses (y - mean) / std)
    y_mean = float(np.mean(y))
    y_std = float(np.std(y)) if np.std(y) > 0 else 1.0
    y_norm = (y - y_mean) / y_std

    # Ridge β with normalised transformed inputs
    beta_norm = _ridge_solve(X_norm, y_norm, lam=DEFAULT_RIDGE_LAMBDA)
    beta_std_norm = _bootstrap_beta_std(X_norm, y_norm, seed=seed)

    # Clamp betas to non-negative (Bayesian HalfNormal-style support)
    beta_means = np.clip(beta_norm, 0.0, None)
    beta_stds = np.clip(beta_std_norm, 1e-6, None)

    rng = np.random.default_rng(seed)
    media_betas_samples = np.array(
        [
            _generate_samples_normal(beta_means[i], beta_stds[i], n_samples, rng=rng)
            for i in range(n_channels)
        ]
    )

    # Hill alpha + gamma normalised
    alphas_samples = np.array(
        [
            _generate_samples_normal(hill_alpha, 0.1, n_samples, rng=rng)
            for _ in range(n_channels)
        ]
    )
    gammas_samples = np.array(
        [
            _generate_samples_normal(
                DEFAULT_HILL_GAMMA_NORMALISED, 0.2, n_samples, rng=rng
            )
            for _ in range(n_channels)
        ]
    )
    adstock_decay_samples = np.array(
        [
            np.clip(
                rng.normal(loc=adstock_decay, scale=0.05, size=n_samples),
                0.0, 1.0,
            )
            for _ in range(n_channels)
        ]
    )

    # R-12 audit fix: intercept + control_betas keys present in posterior
    # (decomposer expects these from real PyMC output; absence → KeyError).
    # PI-RESCUE-02 audit fix: cast intercept к float32 to match bayesian_engine
    # real output (line 903 of bayesian_engine.py).
    intercept_samples = _generate_samples_normal(
        mean=0.0,  # normalised intercept around zero baseline
        std=DEFAULT_INTERCEPT_STD,
        n_samples=n_samples,
        clip_negative=False,  # intercept can be negative in normalised space
        rng=rng,
    ).astype(np.float32)
    # No control variables в synthetic case — shape (0, n_samples) empty array
    control_betas_samples = np.zeros((0, n_samples), dtype=np.float32)

    posterior_samples: dict[str, np.ndarray] = {
        "media_betas": media_betas_samples,
        "alphas": alphas_samples,
        "gammas": gammas_samples,
        "adstock_decay": adstock_decay_samples,
        "intercept": intercept_samples,           # R-12 fix
        "control_betas": control_betas_samples,   # R-12 fix
    }

    normalization = {
        "y_mean": y_mean,
        "y_std": y_std,
        "media_means": {ch: float(np.mean(X_transformed[:, i]))
                        for i, ch in enumerate(channel_ids)},
        "control_means": {},
        "control_stds": {},
        "intercept_mean": 0.0,
        "control_betas_mean": [],
        "untrained_channels": [],
        "control_kinds": {},
        "holiday_cols_injected": [],
        "control_prior_mus": {},
        "untrained_controls": [],
    }

    config = {
        "media_columns": channel_ids,
        "control_columns": [],
        "mode": "sales",
        "granularity": dataset.granularity,
        "brand_id": dataset.brand_id,
        "synthetic_posterior_version": "1.1-r02-r12",  # bumped after audit fix
        "preprocessing_applied": {
            "adstock_decay": adstock_decay,
            "hill_alpha": hill_alpha,
            "hill_gamma_strategy": "2x_median_adstock_per_channel",
        },
    }

    return SyntheticPosteriorResult(
        posterior_samples=posterior_samples,
        normalization=normalization,
        config=config,
        media_cols=channel_ids,
        n_proxy_observations=dataset.n_periods,
    )
