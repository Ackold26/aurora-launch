"""Pre-computed sensitivity grid cache (Phase Π.5).

Implements audit P-23 fix: real-time sensitivity slider <100ms requires
pre-computation. Without caching, each slider move triggers OLS+decompose
+ cone = 1-2s = laggy UX.

Strategy:
1. At Sensitivity Dashboard open, dispatch background compute of grid:
   6 dimensions × 5 levels = 30 perturbation runs
2. Cache в memory (frozen dataclass), invalidate on project change
3. Slider movement = O(1) lookup в grid, не recompute

Per Plan v3.0 §A.5 + audit P-07: 3 pre-defined scenarios are default UX
(Pessimistic / Base / Optimistic). 6-slider Expert mode opt-in uses грид.

Dimensions perturbed (per ADAPTATION_RULES.md):
  1. proxy_similarity  (-20% / -10% / 0 / +5% / +10%)
  2. market_size_cv    (0.05 / 0.10 / 0.15 / 0.20 / 0.25)
  3. pricing_index     (0.8 / 0.9 / 1.0 / 1.1 / 1.2)
  4. distribution      (-20% / -10% / 0 / +10% / +20% relative)
  5. adstock_decay     (0.3 / 0.4 / 0.5 / 0.6 / 0.7)
  6. hill_alpha        (1.0 / 1.5 / 2.0 / 2.5 / 3.0)

S-16: Interpolation upgrade (Phase Scale)
-----------------------------------------
``SensitivityGrid.lookup(dimension, level, interpolate=True)`` now supports
1D linear interpolation between adjacent pre-computed grid levels.

  - ``interpolate=True`` (default): when ``level`` falls between two adjacent
    pre-computed levels A and B, return a synthetic ``SensitivityGridPoint``
    whose ``point_forecast_total`` and ``ci_width_total`` are linearly
    weighted between A and B.

  - ``interpolate=False``: strict nearest-neighbour behaviour (legacy).

  - Out-of-range (below min level or above max level): raises ``ValueError``
    regardless of ``interpolate`` flag — silent extrapolation is not allowed
    because sensitivity at boundary extremes frequently exceeds the linear
    regime.

2D bilinear interpolation:
  Not implemented in this version.  The current grid stores 1D slices
  (one dimension perturbed at a time, others at baseline).  2D bilinear
  requires a full grid of (dim_A × dim_B) points.  When the compute_sensitivity_grid
  caller stores 2D cross-dimension points (future work), extend this class
  with ``lookup_2d(dim_a, level_a, dim_b, level_b, interpolate=True)``
  and delegate to ``_bilinear_interp``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

_log = logging.getLogger(__name__)

# Pre-defined scenario cards (per audit P-07 + INV-25 dual-mode UX)
SCENARIO_PESSIMISTIC: dict[str, float] = {
    "proxy_similarity": -0.10,
    "distribution": -0.15,
    "pricing_index": 1.10,
    "market_size_cv": 0.20,
}

SCENARIO_BASE: dict[str, float] = {
    "proxy_similarity": 0.0,
    "distribution": 0.0,
    "pricing_index": 1.0,
    "market_size_cv": 0.10,
}

SCENARIO_OPTIMISTIC: dict[str, float] = {
    "proxy_similarity": 0.05,
    "distribution": 0.10,
    "pricing_index": 0.95,
    "market_size_cv": 0.08,
}

DEFAULT_PERTURBATION_LEVELS: dict[str, list[float]] = {
    "proxy_similarity": [-0.20, -0.10, 0.0, 0.05, 0.10],
    "market_size_cv": [0.05, 0.10, 0.15, 0.20, 0.25],
    "pricing_index_relative": [0.8, 0.9, 1.0, 1.1, 1.2],
    "distribution_relative": [-0.20, -0.10, 0.0, 0.10, 0.20],
    "adstock_decay": [0.3, 0.4, 0.5, 0.6, 0.7],
    "hill_alpha": [1.0, 1.5, 2.0, 2.5, 3.0],
}


@dataclass(frozen=True)
class SensitivityGridPoint:
    """One point в pre-computed grid: dimension + level → forecast statistic."""

    dimension: str  # 'proxy_similarity' | 'market_size_cv' | ...
    level: float
    point_forecast_total: float  # sum across horizon
    ci_width_total: float  # ci_upper - ci_lower sum


@dataclass(frozen=True)
class SensitivityGrid:
    """Pre-computed grid of sensitivity perturbations.

    Slider lookup: grid.lookup(dimension, level) — interpolates between
    nearest pre-computed levels (typical 5 levels per dimension covers
    realistic UI slider range).
    """

    baseline_total: float
    baseline_ci_width: float
    points: list[SensitivityGridPoint]
    dimensions: list[str] = field(default_factory=list)

    def lookup(
        self,
        dimension: str,
        level: float,
        interpolate: bool = True,
    ) -> SensitivityGridPoint:
        """Find (or interpolate) a grid point for ``(dimension, level)``.

        Args:
            dimension: name of the perturbation dimension.
            level: requested level value (may be between pre-computed levels).
            interpolate: when True (default), linearly interpolate between
                adjacent pre-computed levels.  When False, return the strict
                nearest neighbour (legacy behaviour, useful for exact-match
                assertions in tests).

        Returns:
            A ``SensitivityGridPoint`` with ``level`` set to the requested
            value (not necessarily a pre-computed anchor).

        Raises:
            ValueError: if ``dimension`` is not in the grid, or if ``level``
                is outside the range [min_level, max_level] for the dimension.
                Out-of-range values are rejected — extrapolation is unreliable
                in the non-linear sensitivity regime.
        """
        matching = sorted(
            [p for p in self.points if p.dimension == dimension],
            key=lambda p: p.level,
        )
        if not matching:
            raise ValueError(
                f"Dimension {dimension!r} not в grid (available: {self.dimensions})"
            )

        min_level = matching[0].level
        max_level = matching[-1].level

        # Out-of-range check (applies regardless of interpolate flag).
        if level < min_level - 1e-10 or level > max_level + 1e-10:
            raise ValueError(
                f"Level {level!r} is out of range [{min_level}, {max_level}] "
                f"for dimension {dimension!r}. "
                f"Extrapolation beyond precomputed grid is not supported."
            )

        # Clamp tiny floating-point overshoots at exact boundaries.
        level = max(min_level, min(max_level, level))

        if not interpolate:
            # Strict nearest-neighbour (legacy).
            return min(matching, key=lambda p: abs(p.level - level))

        # --- 1D linear interpolation ---
        # Find the two adjacent anchors that bracket ``level``.
        lo: SensitivityGridPoint | None = None
        hi: SensitivityGridPoint | None = None
        for p in matching:
            if p.level <= level + 1e-12:
                lo = p
            if hi is None and p.level >= level - 1e-12:
                hi = p

        # Exact hit (or floating-point coincidence): return anchor directly.
        if lo is not None and hi is not None and abs(lo.level - hi.level) < 1e-12:
            return lo

        if lo is None:
            return matching[0]  # clamp to lower boundary (safety)
        if hi is None:
            return matching[-1]  # clamp to upper boundary (safety)

        # Linear weight: t=0 → lo, t=1 → hi.
        span = hi.level - lo.level
        t = (level - lo.level) / span  # span > 0 guaranteed by above checks

        interp_forecast = lo.point_forecast_total + t * (
            hi.point_forecast_total - lo.point_forecast_total
        )
        interp_ci = lo.ci_width_total + t * (hi.ci_width_total - lo.ci_width_total)

        return SensitivityGridPoint(
            dimension=dimension,
            level=level,
            point_forecast_total=interp_forecast,
            ci_width_total=interp_ci,
        )

    def relative_impact_pct(
        self,
        dimension: str,
        level: float,
        interpolate: bool = True,
    ) -> float:
        """Compute relative impact (%) vs baseline for UI bar chart.

        Uses ``lookup(interpolate=interpolate)`` internally.
        """
        point = self.lookup(dimension, level, interpolate=interpolate)
        if self.baseline_total == 0:
            return 0.0
        return 100.0 * (point.point_forecast_total - self.baseline_total) / self.baseline_total


def compute_sensitivity_grid(
    forecast_fn: Callable[[dict[str, float]], tuple[float, float]],
    *,
    dimensions: list[str] | None = None,
    perturbation_levels: dict[str, list[float]] | None = None,
    baseline_params: dict[str, float] | None = None,
) -> SensitivityGrid:
    """Pre-compute sensitivity grid by running forecast_fn at each (dim, level).

    forecast_fn(params) returns (point_forecast_total, ci_width_total) — sum
    across forecast horizon for one parameter perturbation.

    Args:
        forecast_fn: callable that takes parameter overrides dict и returns
            forecast statistics
        dimensions: list of dimension names к perturb. Defaults к all 6.
        perturbation_levels: per-dimension level lists. Defaults к standard 5-level.
        baseline_params: parameter values at baseline (default mid-level)

    Returns:
        SensitivityGrid с baseline + N×M grid points.
    """
    if dimensions is None:
        dimensions = list(DEFAULT_PERTURBATION_LEVELS.keys())
    if perturbation_levels is None:
        perturbation_levels = DEFAULT_PERTURBATION_LEVELS
    baseline_params = baseline_params or {}

    # Baseline computation
    baseline_total, baseline_ci = forecast_fn(baseline_params)

    points: list[SensitivityGridPoint] = []
    for dim in dimensions:
        levels = perturbation_levels.get(dim)
        if levels is None:
            _log.warning("No levels defined для dimension %s, skipping", dim)
            continue
        for level in levels:
            params = dict(baseline_params)
            params[dim] = level
            try:
                point_total, ci_width = forecast_fn(params)
            except Exception as exc:
                _log.warning(
                    "Sensitivity compute failed for %s=%s: %s", dim, level, exc
                )
                continue
            points.append(
                SensitivityGridPoint(
                    dimension=dim,
                    level=level,
                    point_forecast_total=point_total,
                    ci_width_total=ci_width,
                )
            )

    return SensitivityGrid(
        baseline_total=baseline_total,
        baseline_ci_width=baseline_ci,
        points=points,
        dimensions=dimensions,
    )


def get_scenario_params(scenario_name: str) -> dict[str, float]:
    """Return scenario card parameters (Manager mode default UX, audit P-07)."""
    scenarios = {
        "pessimistic": SCENARIO_PESSIMISTIC,
        "base": SCENARIO_BASE,
        "optimistic": SCENARIO_OPTIMISTIC,
    }
    if scenario_name.lower() not in scenarios:
        raise ValueError(
            f"Unknown scenario {scenario_name!r}. Options: {list(scenarios.keys())}"
        )
    return scenarios[scenario_name.lower()]
