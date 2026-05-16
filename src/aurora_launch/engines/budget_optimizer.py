"""Budget Optimizer — prescriptive spend allocation (ROADMAP §4.4).

Finds the channel spend split that **maximises total forecasted sales** for a
given budget, using random search (grid search for ≤ 2 channels).

Algorithm
---------
1. Sample `n_iterations` random budget splits subject to per-channel caps.
   Each split is a dict  { channel_id: [spend_per_period, …] }.
2. For each split call the provided ``forecast_fn`` (callable wrapping a
   LaunchOrchestrator or a test mock).
3. Rank by sum(point_forecast) across the horizon.
4. Return best + top-3 alternatives.

Design constraints
------------------
- **No external optimizer** (no scipy, no BFGS).  Grid/random search only.
  This is intentional: the skeleton intentionally trades optimality for
  simplicity and customer manual review of top-N alternatives.
- Deterministic given the same ``seed``.
- Does NOT call ProjectDB — all data arrives via arguments.
- Thread-safe: each call gets its own numpy RNG (no module-level state).

Limitations (skeleton — see ROADMAP §4.4 follow-up tasks)
-----------------------------------------------------------
- Grid search only used for ≤ 2 channels (5×5 = 25 cells).
  For 3+ channels random search is the only mode.
- No parallel evaluation (sequential; parallel variant is a follow-up).
- No progress callback / events (planned in next iteration with UI button).
- Budget split is uniform across periods (same per-period spend for all T).
  Non-uniform intra-period allocation is a future enhancement.
- Integer rounding: splits use floating-point; no lot-size constraints.
"""

from __future__ import annotations

import logging
import math
from typing import Callable, NamedTuple

import numpy as np

from aurora_launch.schemas.budget_optimization import (
    BestSpendPlan,
    BudgetSearchRequest,
    ChannelCap,
    SpendPlanAlternative,
)

_log = logging.getLogger(__name__)

# Number of grid divisions per channel axis in full-grid mode (2-channel case).
_GRID_DIVISIONS = 5

# How many top alternatives to return (beyond the best).
_N_ALTERNATIVES = 3


# ─── Internal scored candidate ────────────────────────────────────────────────


class _ScoredCandidate(NamedTuple):
    """Internal scored candidate (not a public type)."""

    score: float          # sum of point_forecast (higher = better)
    ci_lower_sum: float
    ci_upper_sum: float
    channel_split: dict[str, list[float]]
    methodology_signature: str


# ─── Public callable type alias ───────────────────────────────────────────────

# ``forecast_fn`` must accept a spend_plan dict[str, list[float]] and return a
# named result with:
#   - `forecast.points`: list of objects with .point_forecast / .ci_lower / .ci_upper
#   - `methodology_signature`: str
#
# LaunchOrchestrator.forecast_recipient returns OrchestrationResult which satisfies
# this.  Tests pass a lightweight mock.
ForecastFn = Callable[[dict[str, list[float]]], object]


# ─── Helper: generate random splits ──────────────────────────────────────────


def _random_splits(
    channels: list[str],
    caps: dict[str, ChannelCap],
    total_budget: float,
    n: int,
    rng: np.random.Generator,
) -> list[dict[str, float]]:
    """Sample `n` random budget splits (per-period spend, NOT total).

    Each split satisfies:
      cap.min ≤ channel_spend_per_period ≤ cap.max
      sum(channel_spend_per_period) ≤ total_budget_per_period

    The returned dicts map channel → per_period spend (scalar).
    Multiplication by horizon_periods converts to horizon-level budget.

    Strategy: sample Dirichlet weights, scale to [min, max], renormalize.
    Falls back to uniform if constraints are too tight.
    """
    results: list[dict[str, float]] = []
    # Compute feasible range for each channel
    per_channel_min = np.array([max(0.0, caps[ch].min) for ch in channels])
    per_channel_max = np.array([min(total_budget, caps[ch].max) for ch in channels])

    # Clip max to total_budget to avoid infeasible draws
    per_channel_max = np.minimum(per_channel_max, total_budget)

    # Guard: ensure min <= max per channel
    per_channel_max = np.maximum(per_channel_max, per_channel_min)

    slack = per_channel_max - per_channel_min  # how much above min we can spend
    total_slack = total_budget - per_channel_min.sum()

    if total_slack < 0:
        # Budget too small even for all mins → return uniform splits at min
        split = {ch: per_channel_min[i] for i, ch in enumerate(channels)}
        return [split] * n

    for _ in range(n):
        if total_slack == 0 or slack.sum() == 0:
            alloc = per_channel_min.copy()
        else:
            # Sample weights (Dirichlet gives a proper probability simplex)
            w = rng.dirichlet(np.ones(len(channels)))
            # Scale weights so total allocation = total_budget (per period)
            raw = per_channel_min + w * total_slack
            # Clip to per-channel caps
            raw = np.clip(raw, per_channel_min, per_channel_max)
            # Renormalize to satisfy total_budget (greedy: trim/expand largest)
            diff = total_budget - raw.sum()
            if abs(diff) > 1e-9:
                # Distribute residual proportionally to slack headroom
                headroom = per_channel_max - raw if diff > 0 else raw - per_channel_min
                head_sum = headroom.sum()
                if head_sum > 1e-12:
                    raw = raw + diff * headroom / head_sum
                raw = np.clip(raw, per_channel_min, per_channel_max)
            alloc = raw

        results.append({ch: float(alloc[i]) for i, ch in enumerate(channels)})

    return results


def _grid_splits_2ch(
    ch0: str,
    ch1: str,
    caps: dict[str, ChannelCap],
    total_budget: float,
    divisions: int,
) -> list[dict[str, float]]:
    """Full-grid search for exactly 2 channels.

    Creates a `divisions × divisions` grid of (ch0_spend, ch1_spend) pairs
    where ch0 + ch1 = total_budget and both respect their caps.
    """
    ch0_min, ch0_max = caps[ch0].min, min(caps[ch0].max, total_budget)
    results: list[dict[str, float]] = []

    for i in range(divisions + 1):
        t = i / divisions
        ch0_spend = ch0_min + t * (ch0_max - ch0_min)
        ch1_spend = total_budget - ch0_spend
        ch1_min = caps[ch1].min
        ch1_max = min(caps[ch1].max, total_budget)
        if ch1_min <= ch1_spend <= ch1_max:
            results.append({ch0: ch0_spend, ch1: ch1_spend})

    # Deduplicate (floating-point equality is fine for a grid)
    seen: set[tuple[float, float]] = set()
    unique: list[dict[str, float]] = []
    for r in results:
        k = (r[ch0], r[ch1])
        if k not in seen:
            seen.add(k)
            unique.append(r)

    return unique


# ─── Main public function ─────────────────────────────────────────────────────


def find_best_spend_plan(
    *,
    forecast_fn: ForecastFn,
    request: BudgetSearchRequest,
) -> tuple[BestSpendPlan, list[SpendPlanAlternative]]:
    """Find the spend split that maximises total forecasted sales.

    Parameters
    ----------
    forecast_fn:
        Callable ``(spend_plan: dict[str, list[float]]) -> result`` where
        ``result.forecast.points`` is a sequence of objects with attributes
        ``point_forecast``, ``ci_lower``, ``ci_upper``, and
        ``result.methodology_signature`` is a str.

        In production: partial(orchestrator.forecast_recipient, proxy=…, anchors=…, …).
        In tests: a lightweight mock.

    request:
        ``BudgetSearchRequest`` with total_budget, channel_caps, horizon etc.

    Returns
    -------
    (best, alternatives)
        ``best`` is a ``BestSpendPlan``; ``alternatives`` is a list of up to
        ``_N_ALTERNATIVES`` ``SpendPlanAlternative`` objects (rank 2, 3, 4).

    Raises
    ------
    ValueError
        If channel_caps is empty, total_budget ≤ 0, or all evaluations fail.
    """
    channels = sorted(request.channel_caps.keys())
    n_channels = len(channels)
    horizon = request.horizon_periods
    rng = np.random.default_rng(request.seed)

    if n_channels == 0:
        raise ValueError("channel_caps must not be empty")
    if request.total_budget <= 0:
        raise ValueError(f"total_budget must be > 0, got {request.total_budget}")

    _log.info(
        "Budget optimizer: channels=%s, budget=%.2f, horizon=%d, n_iter=%d, seed=%d",
        channels,
        request.total_budget,
        horizon,
        request.n_iterations,
        request.seed,
    )

    # ── Generate candidate splits ─────────────────────────────────────────────
    if n_channels == 2:
        # Use grid search for 2-channel case (deterministic, exhaustive)
        grid_splits = _grid_splits_2ch(
            channels[0],
            channels[1],
            request.channel_caps,
            request.total_budget,
            _GRID_DIVISIONS,
        )
        # Supplement with random draws to meet n_iterations quota
        extra_splits = _random_splits(
            channels,
            request.channel_caps,
            request.total_budget,
            max(0, request.n_iterations - len(grid_splits)),
            rng,
        )
        per_period_splits = grid_splits + extra_splits
    else:
        per_period_splits = _random_splits(
            channels,
            request.channel_caps,
            request.total_budget,
            request.n_iterations,
            rng,
        )

    # ── Evaluate each split ───────────────────────────────────────────────────
    scored: list[_ScoredCandidate] = []
    n_ok = 0
    n_fail = 0

    for per_period in per_period_splits:
        # Expand per-period scalar → list[float] of length horizon (uniform)
        spend_plan: dict[str, list[float]] = {
            ch: [float(v)] * horizon for ch, v in per_period.items()
        }
        try:
            result = forecast_fn(spend_plan)
            # Extract forecast points — support both OrchestrationResult and mock
            pts = _extract_points(result)
            score = float(sum(p[0] for p in pts))
            ci_lo = float(sum(p[1] for p in pts))
            ci_hi = float(sum(p[2] for p in pts))
            sig = _extract_signature(result)

            if not (math.isfinite(score) and math.isfinite(ci_lo) and math.isfinite(ci_hi)):
                _log.warning("Skipping non-finite forecast for split %s", per_period)
                n_fail += 1
                continue

            scored.append(
                _ScoredCandidate(
                    score=score,
                    ci_lower_sum=ci_lo,
                    ci_upper_sum=ci_hi,
                    channel_split=spend_plan,
                    methodology_signature=sig,
                )
            )
            n_ok += 1
        except Exception as exc:  # noqa: BLE001
            _log.warning("Forecast failed for split %s: %s", per_period, exc)
            n_fail += 1

    if n_ok == 0:
        raise ValueError(
            f"All {n_fail} budget-split evaluations failed — cannot produce a plan. "
            "Check proxy / anchors data consistency."
        )

    _log.info(
        "Budget optimizer: evaluated %d/%d splits successfully (%d failed)",
        n_ok,
        len(per_period_splits),
        n_fail,
    )

    # ── Rank by score (descending) ────────────────────────────────────────────
    scored.sort(key=lambda c: c.score, reverse=True)

    best_c = scored[0]
    best = BestSpendPlan(
        channel_split=best_c.channel_split,
        expected_total_sales=best_c.score,
        ci_lower=best_c.ci_lower_sum,
        ci_upper=best_c.ci_upper_sum,
        methodology_signature=best_c.methodology_signature,
        n_iterations_used=n_ok,
    )

    alternatives: list[SpendPlanAlternative] = []
    for rank_idx, cand in enumerate(scored[1: _N_ALTERNATIVES + 1], start=2):
        alternatives.append(
            SpendPlanAlternative(
                channel_split=cand.channel_split,
                expected_total_sales=cand.score,
                ci_lower=cand.ci_lower_sum,
                ci_upper=cand.ci_upper_sum,
                methodology_signature=cand.methodology_signature,
                n_iterations_used=n_ok,
                rank=rank_idx,
            )
        )

    return best, alternatives


# ─── Private extraction helpers ───────────────────────────────────────────────


def _extract_points(result: object) -> list[tuple[float, float, float]]:
    """Extract (point_forecast, ci_lower, ci_upper) tuples from result.

    Supports:
    - OrchestrationResult (has .forecast.points with ForecastPoint objects)
    - Dict with 'points' key (test mocks)
    - Dict with 'forecast' → 'points' nesting
    """
    # OrchestrationResult path
    forecast_attr = getattr(result, "forecast", None)
    if forecast_attr is not None:
        pts = getattr(forecast_attr, "points", None)
        if pts is not None:
            return [
                (
                    float(p.point_forecast),
                    float(p.ci_lower),
                    float(p.ci_upper),
                )
                for p in pts
            ]

    # Dict-based mock path
    if isinstance(result, dict):
        pts_raw = result.get("forecast", {}).get("points") or result.get("points")
        if pts_raw is not None:
            out: list[tuple[float, float, float]] = []
            for p in pts_raw:
                if isinstance(p, dict):
                    out.append((
                        float(p["point_forecast"]),
                        float(p["ci_lower"]),
                        float(p["ci_upper"]),
                    ))
                elif isinstance(p, (list, tuple)) and len(p) >= 3:
                    out.append((float(p[0]), float(p[1]), float(p[2])))
                else:
                    raise TypeError(
                        f"Cannot parse forecast point from {type(p).__name__}: {p!r}"
                    )
            return out

    raise TypeError(
        f"Cannot extract forecast points from result type {type(result).__name__}. "
        "Expected OrchestrationResult or dict with 'points' key."
    )


def _extract_signature(result: object) -> str:
    """Extract methodology_signature string from result."""
    sig = getattr(result, "methodology_signature", None)
    if sig is not None:
        return str(sig)
    if isinstance(result, dict):
        return str(result.get("methodology_signature", "budget_optimizer_search_v1"))
    return "budget_optimizer_search_v1"
