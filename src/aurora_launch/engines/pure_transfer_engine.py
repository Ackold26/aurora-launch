"""Pure transfer forecast engine (Phase Π.2.2).

Implements Mode 1 of the 4-mode router (PURE_TRANSFER): forecast generation
when recipient brand has n_recipient = 0 observations — the primary Launch
Planner use case (pre-launch forecast for new brand or paused-brand relaunch).

Math architecture (per Plan v3.0 §A.2 + ADAPTATION_RULES.md S004):

  baseline_recipient_t = market_size × seasonality_t × planned_share(t)
                         × distribution(t) × pricing_factor

  pricing_factor       = (1 / pricing_index) ^ elasticity_by_category

  β_recipient[c]       = proxy_β_mean[c]
                         × (recipient_baseline_mean / proxy_baseline_mean)
                         × similarity_factor[c]

  σ_β[c]               = proxy_β_std[c] + similarity_inflation[c]

  contribution_t[c]    = β_recipient[c] × hill(adstock(spend_t[c],
                                                      λ_proxy[c]),
                                               γ_proxy[c], k_proxy[c])

  forecast_t           = baseline_recipient_t + Σ_c contribution_t[c]

CI bands propagated via independent Gaussian channel-betas:

  var_t                = Σ_c (σ_β[c])² × hill²(adstock_t[c])
                         + anchor_uncertainty_var(baseline)

  CI_lower_t / upper_t = forecast_t ∓ z_critical × √var_t

Uncertainty decomposition (transparency-as-feature, Plan v3.0 §A.5):

  proxy_uncertainty_var      = Σ_c (proxy_β_std[c])² × hill²
  transfer_assumption_var    = Σ_c (similarity_inflation[c])² × hill²
  anchor_uncertainty_var     = baseline × anchor_cv²

  decomposition_pct[k]       = var[k] / total_var × 100

This module is self-contained: no PyMC/JAX dependencies, no FastAPI.
Self-implements adstock + hill для не зависеть от sub-agent's utils
(Phase Π.1.5 mechanical port будет integrated при later refactor).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal, Mapping, Sequence

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

_FROZEN = ConfigDict(frozen=True, extra="forbid")

Granularity = Literal["monthly", "weekly"]

# Z-critical values for symmetric two-sided CI bands.
_Z_CRITICAL: dict[float, float] = {
    0.80: 1.2816,
    0.90: 1.6449,
    0.95: 1.96,
    0.99: 2.5758,
}


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


class ChannelTransferParams(BaseModel):
    """Per-channel parameters extracted from proxy posterior."""

    model_config = _FROZEN

    channel_id: str
    proxy_beta_mean: float = Field(ge=0)
    proxy_beta_std: float = Field(ge=0)
    adstock_decay: float = Field(ge=0, le=1)  # geometric decay lambda
    # PI2-B1 audit fix: cap hill_alpha to prevent numerical overflow (k^alpha
    # OverflowError при alpha~155; NaN при alpha~100). PyMC HalfStudentT priors
    # for adstock/hill typically produce alpha ∈ [0.5, 5.0]; le=20 is generous.
    hill_alpha: float = Field(gt=0, le=20.0)
    hill_half_saturation: float = Field(gt=0)
    similarity_factor: float = Field(gt=0, le=1.0, default=1.0)
    similarity_inflation: float = Field(ge=0, default=0.0)


class RecipientAnchors(BaseModel):
    """Anchor values для recipient brand (provided by user via wizard)."""

    model_config = _FROZEN

    market_size: float = Field(gt=0)
    market_size_cv: float = Field(ge=0, default=0.10)  # coefficient of variation
    planned_share_trajectory: list[float] = Field(min_length=1)
    distribution_trajectory: list[float] = Field(min_length=1)
    pricing_index: float = Field(gt=0)
    elasticity: float = Field(ge=0)  # price elasticity per category
    seasonality: list[float] | None = None  # if None, flat (1.0)

    @model_validator(mode="after")
    def trajectory_lengths_match(self) -> "RecipientAnchors":
        if len(self.planned_share_trajectory) != len(self.distribution_trajectory):
            raise ValueError(
                f"planned_share_trajectory ({len(self.planned_share_trajectory)}) "
                f"and distribution_trajectory ({len(self.distribution_trajectory)}) "
                f"must have same length"
            )
        if self.seasonality is not None and len(self.seasonality) != len(
            self.planned_share_trajectory
        ):
            raise ValueError(
                f"seasonality length {len(self.seasonality)} ≠ trajectory length "
                f"{len(self.planned_share_trajectory)}"
            )
        # Share + distribution must быть в [0, 1]
        for x in self.planned_share_trajectory:
            if not 0.0 <= x <= 1.0:
                raise ValueError(f"planned_share value {x} out of [0, 1]")
        for x in self.distribution_trajectory:
            if not 0.0 <= x <= 1.0:
                raise ValueError(f"distribution value {x} out of [0, 1]")
        return self


class TransferInputs(BaseModel):
    """Full input bundle для pure transfer forecast."""

    model_config = _FROZEN

    granularity: Granularity
    horizon_periods: int = Field(ge=1, le=60)
    channels: list[ChannelTransferParams] = Field(min_length=1)
    anchors: RecipientAnchors
    spend_plan: dict[str, list[float]] = Field(
        description="channel_id → spend per period (length = horizon_periods)"
    )
    proxy_baseline_mean: float = Field(gt=0)
    # PI2-B3 audit fix: restrict к explicitly supported coverage targets to
    # match runtime _Z_CRITICAL dict. Previous Field(ge=0.5, le=0.99) accepted
    # 0.85 which then crashed at forecast time с ValueError.
    coverage_target: Literal[0.80, 0.90, 0.95, 0.99] = 0.95

    @model_validator(mode="after")
    def spend_plan_lengths_match_horizon(self) -> "TransferInputs":
        for ch_id, plan in self.spend_plan.items():
            if len(plan) != self.horizon_periods:
                raise ValueError(
                    f"spend_plan[{ch_id}] length {len(plan)} ≠ horizon {self.horizon_periods}"
                )
            if any(x < 0 for x in plan):
                raise ValueError(f"spend_plan[{ch_id}] contains negative spend")
        channel_ids = {c.channel_id for c in self.channels}
        plan_ids = set(self.spend_plan.keys())
        if channel_ids != plan_ids:
            missing = channel_ids - plan_ids
            extra = plan_ids - channel_ids
            raise ValueError(
                f"spend_plan keys mismatch channels: missing={missing}, extra={extra}"
            )
        # Anchors trajectories must reach horizon — extend by last value if shorter.
        return self


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ForecastPoint:
    """One period's forecast point + uncertainty decomposition."""

    period_index: int
    point_forecast: float
    ci_lower: float
    ci_upper: float
    baseline: float
    per_channel_contribution: dict[str, float]


@dataclass(frozen=True)
class UncertaintyDecomposition:
    """Sources of forecast uncertainty (% breakdown)."""

    proxy_uncertainty_pct: float
    transfer_assumption_pct: float
    anchor_uncertainty_pct: float


@dataclass(frozen=True)
class TransferForecast:
    """Full forecast cone result."""

    granularity: Granularity
    horizon_periods: int
    coverage_target: float
    z_critical: float
    points: list[ForecastPoint]
    uncertainty_decomposition: UncertaintyDecomposition
    methodology_signature: str  # tag для tracing — "pure_transfer_v1"


# ---------------------------------------------------------------------------
# Math helpers (self-contained — не зависит от utils/adstock.py)
# ---------------------------------------------------------------------------


def apply_geometric_adstock(spend: Sequence[float], decay: float) -> np.ndarray:
    """Apply geometric adstock с decay rate `decay` ∈ [0, 1].

    Adstock_t = spend_t + decay × Adstock_{t-1}, Adstock_0 = spend_0.
    Returns same length as input.
    """
    if not 0.0 <= decay <= 1.0:
        raise ValueError(f"decay must be в [0, 1], got {decay}")
    spend_arr = np.asarray(list(spend), dtype=float)
    if spend_arr.ndim != 1:
        raise ValueError(f"spend must be 1-D, got shape {spend_arr.shape}")
    out = np.zeros_like(spend_arr)
    if len(spend_arr) == 0:
        return out
    out[0] = spend_arr[0]
    for t in range(1, len(spend_arr)):
        out[t] = spend_arr[t] + decay * out[t - 1]
    return out


def hill_saturation(
    adstock: np.ndarray,
    alpha: float,
    half_saturation: float,
) -> np.ndarray:
    """Hill saturation function (S-shaped response curve).

    hill(x) = x^alpha / (x^alpha + k^alpha)

    Monotonic non-decreasing, asymptote = 1.0, hill(k) = 0.5.

    PI2-B1 audit fix: numpy float64 для k_pow (вместо Python float) prevents
    OverflowError при alpha ≥ ~155. Handle inf/inf NaN: when both x_pow и
    k_pow → inf, fall back на ratio sign (x > k → asymptote, x < k → 0).
    """
    if alpha <= 0:
        raise ValueError(f"alpha must be > 0, got {alpha}")
    if half_saturation <= 0:
        raise ValueError(f"half_saturation must be > 0, got {half_saturation}")
    arr = np.asarray(adstock, dtype=float)
    x = np.clip(arr, 0.0, None)
    # Use numpy float64 for k_pow to get inf (not OverflowError) при extreme alpha
    with np.errstate(over="ignore", invalid="ignore"):
        x_pow = np.power(x, alpha)
        k_pow = np.float64(half_saturation) ** np.float64(alpha)
    # Handle pathological combinations: both inf → fall back to sign of (x - k)
    both_inf = np.isinf(x_pow) & np.isinf(k_pow)
    only_x_inf = np.isinf(x_pow) & ~np.isinf(k_pow)
    only_k_inf = ~np.isinf(x_pow) & np.isinf(k_pow)
    normal_path = x_pow / (x_pow + k_pow)
    # When both inf: compare base values (x > k → 1, x < k → 0, equal → 0.5)
    both_inf_fallback = np.where(x > half_saturation, 1.0, np.where(x < half_saturation, 0.0, 0.5))
    result = np.where(both_inf, both_inf_fallback,
                      np.where(only_x_inf, 1.0,
                               np.where(only_k_inf, 0.0, normal_path)))
    return result


# ---------------------------------------------------------------------------
# Core forecast pipeline
# ---------------------------------------------------------------------------


def _extend_trajectory(traj: list[float], horizon: int) -> np.ndarray:
    """Extend trajectory by repeating last value if shorter than horizon."""
    arr = np.asarray(traj, dtype=float)
    if len(arr) >= horizon:
        return arr[:horizon]
    # Pad с last value
    pad = np.full(horizon - len(arr), arr[-1])
    return np.concatenate([arr, pad])


def _seasonality_array(anchors: RecipientAnchors, horizon: int) -> np.ndarray:
    if anchors.seasonality is None:
        return np.ones(horizon)
    return _extend_trajectory(anchors.seasonality, horizon)


def compute_recipient_baseline(
    anchors: RecipientAnchors, horizon: int
) -> np.ndarray:
    """Per-period recipient baseline (sales floor without media)."""
    share = _extend_trajectory(anchors.planned_share_trajectory, horizon)
    distribution = _extend_trajectory(anchors.distribution_trajectory, horizon)
    seasonality = _seasonality_array(anchors, horizon)
    pricing_factor = (1.0 / anchors.pricing_index) ** anchors.elasticity
    return anchors.market_size * seasonality * share * distribution * pricing_factor


def forecast_pure_transfer(inputs: TransferInputs) -> TransferForecast:
    """Generate forecast cone via pure transfer (no recipient y data).

    Used when n_recipient = 0 (router PURE_TRANSFER mode).

    Args:
        inputs: validated TransferInputs

    Returns:
        TransferForecast с per-period points + uncertainty decomposition
    """
    horizon = inputs.horizon_periods
    z = _Z_CRITICAL.get(round(inputs.coverage_target, 2))
    if z is None:
        # We only support the 4 standard coverage targets. Adding scipy as a
        # dep just for stats.norm.ppf is overkill for desktop bundle size.
        raise ValueError(
            f"coverage_target {inputs.coverage_target} not supported. "
            f"Allowed: {sorted(_Z_CRITICAL.keys())}"
        )

    # Baseline trajectory
    baseline = compute_recipient_baseline(inputs.anchors, horizon)
    recipient_baseline_mean = float(np.mean(baseline))

    # Scale factor: recipient/proxy baseline ratio
    if inputs.proxy_baseline_mean <= 0:
        raise ValueError("proxy_baseline_mean must be > 0")
    scale_ratio = recipient_baseline_mean / inputs.proxy_baseline_mean

    # Per-channel computations
    point_forecast = baseline.copy()
    proxy_uncertainty_var = np.zeros(horizon)
    transfer_assumption_var = np.zeros(horizon)
    per_channel_contributions: list[dict[str, np.ndarray]] = []

    for channel in inputs.channels:
        spend = np.asarray(inputs.spend_plan[channel.channel_id], dtype=float)
        adstock = apply_geometric_adstock(spend, channel.adstock_decay)
        hill_resp = hill_saturation(
            adstock, channel.hill_alpha, channel.hill_half_saturation
        )

        beta_recipient = (
            channel.proxy_beta_mean * scale_ratio * channel.similarity_factor
        )
        sigma_beta = channel.proxy_beta_std + channel.similarity_inflation

        contribution = beta_recipient * hill_resp
        point_forecast += contribution
        per_channel_contributions.append(
            {channel.channel_id: contribution}
        )

        # Variance contributions per uncertainty source
        # Squared because variance combines additively in independent Gaussian channels
        proxy_uncertainty_var += (channel.proxy_beta_std * scale_ratio) ** 2 * hill_resp ** 2
        transfer_assumption_var += channel.similarity_inflation ** 2 * hill_resp ** 2

    # Anchor uncertainty: market_size_cv applied as multiplicative noise on baseline.
    anchor_uncertainty_var = (anchor_cv := inputs.anchors.market_size_cv) ** 2 * baseline ** 2

    # R-08 audit fix: independent-Gaussian assumption produces overconfident CI bands.
    # Real-world channels exhibit positive covariance (TV/Digital share consumer journey).
    # Without full posterior covariance matrix available here, apply conservative
    # 20% variance inflation. Honest disclosure: CI accounts for typical cross-channel
    # correlation magnitude observed в Optimizer historical data.
    _COVARIANCE_INFLATION_FACTOR = 1.20  # 20% variance inflation
    total_var = (
        proxy_uncertainty_var + transfer_assumption_var + anchor_uncertainty_var
    ) * _COVARIANCE_INFLATION_FACTOR
    total_std = np.sqrt(total_var)

    ci_lower = point_forecast - z * total_std
    ci_upper = point_forecast + z * total_std

    # Assemble per-period points
    points: list[ForecastPoint] = []
    for t in range(horizon):
        per_channel_at_t = {
            ch.channel_id: float(per_channel_contributions[i][ch.channel_id][t])
            for i, ch in enumerate(inputs.channels)
        }
        points.append(
            ForecastPoint(
                period_index=t,
                point_forecast=float(point_forecast[t]),
                ci_lower=float(ci_lower[t]),
                ci_upper=float(ci_upper[t]),
                baseline=float(baseline[t]),
                per_channel_contribution=per_channel_at_t,
            )
        )

    # Decomposition % across horizon (averaged across periods)
    total_proxy = float(np.sum(proxy_uncertainty_var))
    total_transfer = float(np.sum(transfer_assumption_var))
    total_anchor = float(np.sum(anchor_uncertainty_var))
    grand = max(total_proxy + total_transfer + total_anchor, 1e-12)
    decomp = UncertaintyDecomposition(
        proxy_uncertainty_pct=100.0 * total_proxy / grand,
        transfer_assumption_pct=100.0 * total_transfer / grand,
        anchor_uncertainty_pct=100.0 * total_anchor / grand,
    )

    return TransferForecast(
        granularity=inputs.granularity,
        horizon_periods=horizon,
        coverage_target=inputs.coverage_target,
        z_critical=z,
        points=points,
        uncertainty_decomposition=decomp,
        methodology_signature="pure_transfer_v1",
    )
