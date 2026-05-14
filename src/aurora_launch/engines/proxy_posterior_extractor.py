"""Extract per-channel transfer params из proxy Bayesian posterior (Phase Π.2.3).

Bridges bayesian_engine output (PyMC posterior samples) к pure_transfer_engine
input (ChannelTransferParams). Pulls posterior mean/std per channel и optionally
shrinks the std distribution toward the mean (informative prior weighting).

Used by launch_orchestrator (Π.2.4) when wiring proxy training → recipient
transfer. Standalone module — testable без actually running PyMC training.

Schema contract (bayesian_engine.py output):

    posterior_samples = {
        "media_betas":     ndarray shape (n_channels, n_samples),
        "alphas":          ndarray shape (n_channels, n_samples),
        "gammas":          ndarray shape (n_channels, n_samples),
        "adstock_decay":   ndarray shape (n_channels, n_samples),
        ...
    }
    channel_params = {
        channel_id: {
            "beta": float, "alpha": float, "gamma": float, "decay": float,
            "adstock_mean_posterior": float, ...
        }
    }

Shrinkage formula (Plan v3.0 §A.2 + Optimizer's transfer doctrine):

    σ_β_recipient = σ_β_proxy × (1 - shrinkage) + ε_floor

    shrinkage = 0.0 → keep proxy uncertainty as is (conservative)
    shrinkage = 1.0 → maximally informative (uses only proxy mean, sigma → 0)
    shrinkage = 0.5 → balanced (default per D-01 + audit P-02)

Lower shrinkage values trust proxy LESS (wider recipient CIs).
Higher shrinkage values trust proxy MORE (narrower recipient CIs).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

# Numerical floor для σ (prevent division by zero downstream)
_SIGMA_FLOOR = 1e-6


@dataclass(frozen=True)
class ProxyChannelPrior:
    """Per-channel transfer prior derived из proxy posterior."""

    channel_id: str
    proxy_beta_mean: float
    proxy_beta_std: float
    adstock_decay: float
    hill_alpha: float
    hill_half_saturation: float
    n_samples: int


class ProxyExtractionError(ValueError):
    """Raised on schema mismatch / invalid posterior bundle."""


def _validate_posterior_schema(
    posterior_samples: Mapping[str, np.ndarray],
    media_cols: list[str],
) -> None:
    """Verify posterior dict has all required keys + consistent shapes."""
    required = {"media_betas", "alphas", "gammas", "adstock_decay"}
    missing = required - set(posterior_samples.keys())
    if missing:
        raise ProxyExtractionError(
            f"posterior_samples missing required keys: {sorted(missing)}"
        )

    n_channels_expected = len(media_cols)
    shapes: dict[str, tuple[int, ...]] = {}
    for key in required:
        arr = np.asarray(posterior_samples[key])
        shapes[key] = arr.shape
        if arr.ndim != 2:
            raise ProxyExtractionError(
                f"posterior_samples[{key!r}] must be 2-D (n_channels, n_samples), "
                f"got shape {arr.shape}"
            )
        if arr.shape[0] != n_channels_expected:
            raise ProxyExtractionError(
                f"posterior_samples[{key!r}] shape[0]={arr.shape[0]} ≠ "
                f"len(media_cols)={n_channels_expected}"
            )

    # All arrays must have same n_samples
    sample_counts = {k: s[1] for k, s in shapes.items()}
    if len(set(sample_counts.values())) > 1:
        raise ProxyExtractionError(
            f"Inconsistent n_samples across posterior keys: {sample_counts}"
        )


def extract_proxy_priors(
    posterior_samples: Mapping[str, np.ndarray],
    media_cols: list[str],
) -> dict[str, ProxyChannelPrior]:
    """Extract per-channel transfer priors из proxy posterior.

    Args:
        posterior_samples: dict from bayesian_engine output (see contract above)
        media_cols: ordered list of channel IDs corresponding to posterior axis 0

    Returns:
        dict[channel_id, ProxyChannelPrior] — keyed by channel ID, contains
        posterior mean + std per parameter

    Raises:
        ProxyExtractionError: schema mismatch (missing keys, shape, n_samples)
    """
    if not media_cols:
        raise ProxyExtractionError("media_cols must be non-empty")
    if len(media_cols) != len(set(media_cols)):
        raise ProxyExtractionError(
            f"media_cols must be unique, got duplicates: "
            f"{[c for c in media_cols if media_cols.count(c) > 1]}"
        )

    _validate_posterior_schema(posterior_samples, media_cols)

    betas = np.asarray(posterior_samples["media_betas"])
    alphas = np.asarray(posterior_samples["alphas"])
    gammas = np.asarray(posterior_samples["gammas"])
    decays = np.asarray(posterior_samples["adstock_decay"])
    n_samples = betas.shape[1]

    priors: dict[str, ProxyChannelPrior] = {}
    for i, channel_id in enumerate(media_cols):
        # PI2-B2 audit fix: detect NaN propagation early с explicit message,
        # вместо silently converting к NaN and crashing downstream Pydantic.
        if np.any(np.isnan(betas[i])):
            raise ProxyExtractionError(
                f"Channel {channel_id!r}: NaN found в media_betas posterior samples. "
                f"Check PyMC convergence — divergent transitions can corrupt posterior."
            )
        beta_mean = float(np.mean(betas[i]))
        beta_std = float(np.std(betas[i], ddof=1)) if n_samples > 1 else 0.0
        # σ floor — pure zero std means perfect knowledge что вычислительно
        # фрагильно downstream (division в CI propagation).
        beta_std = max(beta_std, _SIGMA_FLOOR)
        # PyMC's HalfNormal/HalfStudentT priors can produce slightly negative
        # tail samples из numerical artefacts; clamp к non-negative.
        beta_mean = max(beta_mean, 0.0)

        # Defence-in-depth for alpha/gamma/decay: NaN check before mean
        for param_name, arr in (("alphas", alphas[i]), ("gammas", gammas[i]),
                                 ("adstock_decay", decays[i])):
            if np.any(np.isnan(arr)):
                raise ProxyExtractionError(
                    f"Channel {channel_id!r}: NaN found в {param_name} posterior. "
                    f"Check PyMC convergence."
                )

        # PI2-B1 hill_alpha cap aligned с ChannelTransferParams.hill_alpha le=20
        hill_alpha = min(max(float(np.mean(alphas[i])), 0.01), 20.0)

        priors[channel_id] = ProxyChannelPrior(
            channel_id=channel_id,
            proxy_beta_mean=beta_mean,
            proxy_beta_std=beta_std,
            adstock_decay=float(np.clip(np.mean(decays[i]), 0.0, 1.0)),
            hill_alpha=hill_alpha,
            hill_half_saturation=max(float(np.mean(gammas[i])), _SIGMA_FLOOR),
            n_samples=n_samples,
        )

    return priors


def shrink_proxy_priors(
    priors: Mapping[str, ProxyChannelPrior],
    shrinkage_factor: float,
) -> dict[str, ProxyChannelPrior]:
    """Apply shrinkage к proxy std distributions.

    Higher shrinkage_factor → tighter prior (more trust в proxy).
    Lower shrinkage_factor → keep posterior std as observed (conservative).

    Args:
        priors: extracted ProxyChannelPrior dict
        shrinkage_factor: [0.0, 1.0]. 0=no shrinkage, 1=delta function at mean
            (sigma → _SIGMA_FLOOR). Default in router: 0.5.

    Returns:
        New dict с shrunk priors (input unchanged — frozen dataclass).

    Raises:
        ValueError: shrinkage_factor outside [0.0, 1.0]
    """
    if not 0.0 <= shrinkage_factor <= 1.0:
        raise ValueError(
            f"shrinkage_factor must be в [0.0, 1.0], got {shrinkage_factor}"
        )

    shrunk: dict[str, ProxyChannelPrior] = {}
    for channel_id, prior in priors.items():
        new_std = max(
            prior.proxy_beta_std * (1.0 - shrinkage_factor),
            _SIGMA_FLOOR,
        )
        shrunk[channel_id] = ProxyChannelPrior(
            channel_id=prior.channel_id,
            proxy_beta_mean=prior.proxy_beta_mean,
            proxy_beta_std=new_std,
            adstock_decay=prior.adstock_decay,
            hill_alpha=prior.hill_alpha,
            hill_half_saturation=prior.hill_half_saturation,
            n_samples=prior.n_samples,
        )
    return shrunk


def proxy_baseline_from_normalization(
    normalization: Mapping[str, Any],
) -> float:
    """Read proxy baseline (y_mean) из bayesian_engine normalization dict.

    Used by pure_transfer_engine to compute recipient/proxy baseline ratio.

    Args:
        normalization: dict с at least 'y_mean' key (output of bayesian_engine)

    Returns:
        proxy baseline value (float, > 0)

    Raises:
        ProxyExtractionError: y_mean missing или non-positive
    """
    if "y_mean" not in normalization:
        raise ProxyExtractionError("normalization dict missing 'y_mean' key")
    val = float(normalization["y_mean"])
    if val <= 0:
        raise ProxyExtractionError(
            f"proxy y_mean must be > 0 для baseline ratio, got {val}"
        )
    return val


def to_channel_transfer_params(
    priors: Mapping[str, ProxyChannelPrior],
    similarity_factors: Mapping[str, float] | None = None,
    similarity_inflations: Mapping[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Convert ProxyChannelPrior dict к pure_transfer_engine ChannelTransferParams
    dict list ready для validation.

    Args:
        priors: shrunk (or raw) priors
        similarity_factors: optional per-channel similarity factor (default 0.85)
        similarity_inflations: optional per-channel inflation (default 0.15)

    Returns:
        list of dicts compatible с ChannelTransferParams Pydantic model
    """
    sim_factors = similarity_factors or {}
    sim_inflations = similarity_inflations or {}

    results = []
    for channel_id, prior in priors.items():
        results.append(
            {
                "channel_id": channel_id,
                "proxy_beta_mean": prior.proxy_beta_mean,
                "proxy_beta_std": prior.proxy_beta_std,
                "adstock_decay": prior.adstock_decay,
                "hill_alpha": prior.hill_alpha,
                "hill_half_saturation": prior.hill_half_saturation,
                "similarity_factor": sim_factors.get(channel_id, 0.85),
                "similarity_inflation": sim_inflations.get(channel_id, 0.15),
            }
        )
    return results
