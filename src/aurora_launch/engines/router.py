"""4-mode dual-math routing для Aurora Launch Planner forecast engines (Phase Π.2).

Selects appropriate forecast engine based on recipient data sufficiency.
Critical: Launch's recipient brand often has 0-12 months of post-launch
data (or none — pre-launch forecast). Pure-OLS fails on n=0 case
(no y vector). 4-mode routing closes this gap.

Modes (per Plan v3.0 §A.2 + audit P-02 fix):

  Mode 1 — PURE_TRANSFER (n_recipient = 0)
    No fitting. Scaled proxy posterior × recipient anchors.
    Math: β_recipient[c] = proxy_β[c] × (recipient_baseline / proxy_baseline)
                           × similarity_factor[c]
          σ_β[c]        = proxy_β_std[c] + similarity_inflation[c]

  Mode 2 — TRANSFER_WITH_BIAS_CHECK (1 ≤ n_recipient < threshold_ols_low)
    Pure transfer + bias check on observed baseline vs predicted.
    σ_β inflated by observed bias magnitude. Warning if bias >30%.

  Mode 3 — OLS_WITH_PROXY_PRIORS (threshold_ols_low ≤ n_recipient < threshold_bayesian)
    OLS on recipient y, SE inflated by proxy posterior std.
    Adstock + hill fixed from proxy (insufficient n for joint fit).
    Frequentist CI + bootstrap ROI + conformal PI.

  Mode 4 — BAYESIAN_WITH_PROXY_PRIORS (n_recipient ≥ threshold_bayesian)
    Full PyMC Bayesian on recipient with informative priors from proxy.
    shrinkage_factor controls trust-в-proxy (0.5-0.7 default).

Granularity-aware thresholds (D-06 dual-granularity decision):

                                  monthly    weekly
  threshold_pure_transfer         0          0
  threshold_ols_low               1          1
  threshold_bayesian              7          20

Per Аnton's decision 2026-05-14: monthly И weekly both first-class.
Routing thresholds re-calibrated при first-class monthly support
(7 months ≈ 30 weeks of data, but Bayesian needs fewer monthly
observations because each carries more signal).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

Granularity = Literal["monthly", "weekly"]
ALLOWED_GRANULARITIES: frozenset[str] = frozenset({"monthly", "weekly"})


class EngineMode(Enum):
    """One of four routing modes для recipient training."""

    PURE_TRANSFER = "pure_transfer"
    TRANSFER_WITH_BIAS_CHECK = "transfer_with_bias_check"
    OLS_WITH_PROXY_PRIORS = "ols_with_proxy_priors"
    BAYESIAN_WITH_PROXY_PRIORS = "bayesian_with_proxy_priors"


# ---------------------------------------------------------------------------
# Granularity-aware thresholds
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoutingThresholds:
    """Per-granularity n_recipient thresholds для mode transitions.

    Values represent the FIRST n_recipient в каждом range:
      [0]                                  → PURE_TRANSFER
      [ols_low, bayesian)                  → OLS_WITH_PROXY_PRIORS
      [bayesian, ∞)                        → BAYESIAN_WITH_PROXY_PRIORS

    TRANSFER_WITH_BIAS_CHECK occupies (0, ols_low).
    """

    ols_low: int  # min n_recipient для OLS path (smaller → transfer+bias)
    bayesian: int  # min n_recipient для Bayesian (smaller → OLS+priors)


THRESHOLDS_MONTHLY = RoutingThresholds(ols_low=3, bayesian=7)
THRESHOLDS_WEEKLY = RoutingThresholds(ols_low=8, bayesian=20)


def thresholds_for(granularity: Granularity) -> RoutingThresholds:
    if granularity == "monthly":
        return THRESHOLDS_MONTHLY
    if granularity == "weekly":
        return THRESHOLDS_WEEKLY
    raise ValueError(
        f"granularity must be 'monthly' or 'weekly', got {granularity!r}"
    )


# ---------------------------------------------------------------------------
# Engine config (router output)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EngineConfig:
    """Router decision + diagnostic info passed to forecast orchestrator."""

    mode: EngineMode
    granularity: Granularity
    n_recipient: int
    n_proxy: int
    thresholds: RoutingThresholds
    banner_message: str  # UX-friendly explanation для wizard banner
    banner_tone: Literal["good", "warn", "bad"]
    user_override_allowed: bool  # True if user can opt to upgrade/downgrade mode
    user_override_modes: tuple[EngineMode, ...] = field(default_factory=tuple)
    # Shrinkage factor для Bayesian mode — how much trust the proxy posterior.
    # Default 0.5 = informative но не dominating; can be tuned by Expert mode.
    shrinkage_factor: float = 0.5


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


def select_engine(
    n_recipient: int,
    n_proxy: int,
    granularity: Granularity = "monthly",
    *,
    user_override: EngineMode | None = None,
    shrinkage_factor: float = 0.5,
) -> EngineConfig:
    """Select the forecast engine mode based на data sufficiency.

    Args:
        n_recipient: number of recipient observations (months или weeks).
        n_proxy: number of proxy observations. Must be ≥ minimum для Bayesian
            training (4 chains × ~25 observations recommended; we enforce
            soft floor of 24 monthly или 52 weekly).
        granularity: 'monthly' или 'weekly' (D-06).
        user_override: optional explicit mode override. Only honored if
            data is sufficient для that mode (e.g., can't force Bayesian с n=1).
        shrinkage_factor: weight на proxy informative priors when applicable.
            Range [0.0, 1.0]. 0 = ignore proxy, 1 = full trust. Default 0.5.

    Returns:
        EngineConfig с mode + banner + override permissions.

    Raises:
        ValueError: granularity invalid, n_proxy too small, shrinkage out of range.
    """
    if granularity not in ALLOWED_GRANULARITIES:
        raise ValueError(
            f"granularity must be one of {sorted(ALLOWED_GRANULARITIES)}, "
            f"got {granularity!r}"
        )
    if n_recipient < 0:
        raise ValueError(f"n_recipient must be ≥ 0, got {n_recipient}")
    if not (0.0 <= shrinkage_factor <= 1.0):
        raise ValueError(
            f"shrinkage_factor must be в [0.0, 1.0], got {shrinkage_factor}"
        )

    # Proxy must have enough data — minimum threshold per granularity.
    proxy_min = 24 if granularity == "monthly" else 52
    if n_proxy < proxy_min:
        raise ValueError(
            f"Proxy needs ≥{proxy_min} {granularity} observations для reliable Bayesian "
            f"training (got n_proxy={n_proxy})"
        )

    th = thresholds_for(granularity)

    # Determine baseline mode из data sufficiency alone (без user_override).
    if n_recipient == 0:
        baseline_mode = EngineMode.PURE_TRANSFER
        banner = (
            f"Прогноз основан на proxy adaptation. Данных recipient ещё нет — "
            f"forecast будет уточняться по мере поступления."
        )
        banner_tone: Literal["good", "warn", "bad"] = "warn"
        override_allowed = False
        override_modes: tuple[EngineMode, ...] = ()
    elif n_recipient < th.ols_low:
        baseline_mode = EngineMode.TRANSFER_WITH_BIAS_CHECK
        banner = (
            f"Recipient: {n_recipient} {granularity}. Используется proxy transfer "
            f"с bias-check. Минимум {th.ols_low} для OLS-режима."
        )
        banner_tone = "warn"
        override_allowed = False
        override_modes = ()
    elif n_recipient < th.bayesian:
        baseline_mode = EngineMode.OLS_WITH_PROXY_PRIORS
        banner = (
            f"Recipient: {n_recipient} {granularity}. OLS-режим с proxy priors. "
            f"Минимум {th.bayesian} для Bayesian-режима."
        )
        banner_tone = "good"
        override_allowed = False
        override_modes = ()
    else:
        baseline_mode = EngineMode.BAYESIAN_WITH_PROXY_PRIORS
        banner = (
            f"Recipient: {n_recipient} {granularity}. Bayesian-режим с proxy priors. "
            f"Все математические преимущества доступны."
        )
        banner_tone = "good"
        override_allowed = True
        override_modes = (
            EngineMode.OLS_WITH_PROXY_PRIORS,
            EngineMode.BAYESIAN_WITH_PROXY_PRIORS,
        )

    # Apply user_override если допустимо.
    final_mode = baseline_mode
    if user_override is not None:
        if user_override == baseline_mode:
            # Same as baseline — fine.
            pass
        elif user_override in override_modes:
            final_mode = user_override
            banner = f"{banner} [Manual override: {user_override.value}]"
        else:
            # Override not allowed at this data sufficiency level
            raise ValueError(
                f"user_override={user_override.value} not allowed with "
                f"n_recipient={n_recipient} {granularity}. "
                f"Allowed overrides: {[m.value for m in override_modes]}"
            )

    return EngineConfig(
        mode=final_mode,
        granularity=granularity,
        n_recipient=n_recipient,
        n_proxy=n_proxy,
        thresholds=th,
        banner_message=banner,
        banner_tone=banner_tone,
        user_override_allowed=override_allowed,
        user_override_modes=override_modes,
        shrinkage_factor=shrinkage_factor,
    )


# ---------------------------------------------------------------------------
# Convenience: introspection
# ---------------------------------------------------------------------------


def describe_thresholds(granularity: Granularity) -> dict[str, Any]:
    """Human-readable threshold description (for UI banner tooltip)."""
    th = thresholds_for(granularity)
    return {
        "granularity": granularity,
        "pure_transfer": "n_recipient = 0",
        "transfer_with_bias_check": f"1 ≤ n < {th.ols_low}",
        "ols_with_proxy_priors": f"{th.ols_low} ≤ n < {th.bayesian}",
        "bayesian_with_proxy_priors": f"n ≥ {th.bayesian}",
        "proxy_minimum": 24 if granularity == "monthly" else 52,
    }
