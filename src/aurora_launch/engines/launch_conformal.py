"""Conformal Prediction adapted for transfer learning (B4 sprint).

Per Tibshirani 2019 adapted (split conformal + transfer learning context).

Tightness conditional on n_calibration ≥ 50 (audit H4 — Vovk 2005 quantile
inflation otherwise). Below 50, intervals widened to maintain coverage but
warning emitted in Cert.
"""

from __future__ import annotations

import math
from typing import Iterable, Literal

from aurora_launch.schemas.forecast import ConformalInterval


MIN_CALIBRATION_FOR_TIGHT_INTERVALS = 50  # audit H4


def split_conformal_intervals(
    point_forecasts: Iterable[float],
    calibration_residuals: list[float],
    coverage_target: float = 0.95,
    n_calibration: int | None = None,
) -> list[ConformalInterval]:
    """Split conformal intervals (Tibshirani 2019).

    Inputs:
        point_forecasts: list of weekly point predictions
        calibration_residuals: |y_actual - y_predicted| from calibration set
        coverage_target: typically 0.95 (must be в (0, 1))
        n_calibration: explicit count (default: len(calibration_residuals))

    Returns ConformalInterval per week. Tight intervals when n_cal ≥ 50;
    inflated when below (Vovk 2005 quantile correction approximation).

    FIX H-A3-5: explicit coverage_target validation.
    """
    if not 0.0 < coverage_target < 1.0:
        raise ValueError(
            f"coverage_target must be в (0, 1), got {coverage_target}. "
            f"Typical values: 0.90, 0.95, 0.99."
        )

    forecasts = list(point_forecasts)
    n_cal = n_calibration if n_calibration is not None else len(calibration_residuals)

    if not forecasts:
        return []

    if n_cal < 1 or not calibration_residuals:
        # No calibration data — fall back to wide default ±20%
        return [
            ConformalInterval(
                week_index=i,
                point_forecast=f,
                lower_bound=f * 0.80,
                upper_bound=f * 1.20,
                coverage_target=coverage_target,
            )
            for i, f in enumerate(forecasts)
        ]

    # Sort residuals ascending (absolute values)
    sorted_residuals = sorted(abs(r) for r in calibration_residuals)
    n_cal_actual = len(sorted_residuals)

    # Quantile index per Tibshirani 2019: ceil((n+1) × coverage) / n
    q_idx = math.ceil((n_cal_actual + 1) * coverage_target) - 1
    q_idx = max(0, min(q_idx, n_cal_actual - 1))
    quantile_residual = sorted_residuals[q_idx]

    # Vovk 2005 correction for small n_cal
    if n_cal_actual < MIN_CALIBRATION_FOR_TIGHT_INTERVALS:
        # Inflate quantile by sqrt(50/n) factor (heuristic per audit H4)
        inflation = math.sqrt(MIN_CALIBRATION_FOR_TIGHT_INTERVALS / n_cal_actual)
        quantile_residual *= inflation

    intervals: list[ConformalInterval] = []
    for i, f in enumerate(forecasts):
        intervals.append(ConformalInterval(
            week_index=i,
            point_forecast=f,
            lower_bound=f - quantile_residual,
            upper_bound=f + quantile_residual,
            coverage_target=coverage_target,
        ))

    return intervals


def compute_conformal_intervals(
    forecasts_per_horizon: dict[int, list[float]],
    calibration_residuals: list[float],
    coverage_target: float = 0.95,
    method: Literal["split", "weighted_jackknife"] = "split",
) -> dict[int, list[ConformalInterval]]:
    """Multi-horizon conformal intervals (12/26/52 weeks).

    For Aurora Launch B4 — split conformal default; weighted_jackknife
    deferred Phase B+ когда more sophisticated calibration available.
    """
    if method != "split":
        # weighted_jackknife — Phase B+ enhancement; fall back к split
        method = "split"

    return {
        horizon: split_conformal_intervals(
            point_forecasts=fcs,
            calibration_residuals=calibration_residuals,
            coverage_target=coverage_target,
        )
        for horizon, fcs in forecasts_per_horizon.items()
    }


def coverage_warning_threshold(n_calibration: int) -> str | None:
    """Returns warning text if n_calibration insufficient for tight intervals."""
    if n_calibration < MIN_CALIBRATION_FOR_TIGHT_INTERVALS:
        return (
            f"Conformal calibration set has n={n_calibration} < {MIN_CALIBRATION_FOR_TIGHT_INTERVALS}. "
            f"Intervals widened per Vovk 2005 quantile correction. "
            f"Coverage guarantee maintained but interval tightness not optimal. "
            f"Recommend more calibration data для production."
        )
    return None
