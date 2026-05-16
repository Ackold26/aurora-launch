"""Cross-product validation handler.

Handlers: validate_against_optimizer.

Accesses ServiceContainer via methods.get_services() through late import.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register(name: str):
    """Proxy to methods.register."""
    from aurora_launch.sidecar.methods import register as _register
    return _register(name)


def _get_services():
    from aurora_launch.sidecar.services import get_services
    return get_services()


# ─── Handlers ─────────────────────────────────────────────────────────────────


@register("validate_against_optimizer")
def _validate_against_optimizer(params: dict[str, Any]) -> dict[str, Any] | None:
    """Cross-product calibration: compare Launch forecast against Optimizer actuals.

    ROADMAP §3.4 — «Перекрёстная сверка между Launch Planner и Optimizer».

    Params:
      - launch_forecast_value: float — Launch point forecast (units/revenue)
      - proxy_brand_code: str — brand_code of the proxy brand in Optimizer
      - horizon_weeks: int — forecast horizon (default 12); used for confidence calc
      - period_start: str | null — ISO date; defaults to 52 weeks ago
      - period_end: str | null — ISO date; defaults to today

    Returns dict with ``available: true`` and CrossProductValidation fields on
    success, or ``available: false`` + ``reason`` on graceful degradation
    (Optimizer not configured, brand not found, zero actuals).
    """
    from datetime import date as _date
    from datetime import datetime, timedelta, timezone

    from aurora_launch.schemas.cross_product import (
        CrossProductValidation,
        OptimizerHistoryQuery,
    )
    from aurora_launch.services.optimizer_client import OptimizerNotConfigured

    # ── Resolve optimizer client from DI container ─────────────────────────
    svc = _get_services()
    client = svc.get_optimizer_client()

    if client is None:
        logger.warning(
            "validate_against_optimizer: no OptimizerClient in ServiceContainer — "
            "cross-product validation is not available"
        )
        return {"available": False, "reason": "optimizer_not_configured"}

    # ── Parse params ──────────────────────────────────────────────────────
    try:
        launch_value = float(params["launch_forecast_value"])
        proxy_brand_code = str(params["proxy_brand_code"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"validate_against_optimizer: invalid params — {exc}") from exc

    horizon_weeks = int(params.get("horizon_weeks", 12))

    today = datetime.now(tz=timezone.utc).date()
    period_start_raw = params.get("period_start")
    period_end_raw = params.get("period_end")
    period_end = _date.fromisoformat(str(period_end_raw)) if period_end_raw else today
    period_start = (
        _date.fromisoformat(str(period_start_raw))
        if period_start_raw
        else period_end - timedelta(weeks=52)
    )

    # ── Query Optimizer ────────────────────────────────────────────────────
    query = OptimizerHistoryQuery(
        brand_code=proxy_brand_code,
        period_start=period_start,
        period_end=period_end,
    )

    try:
        history = client.get_history(query)
    except OptimizerNotConfigured as exc:
        logger.warning("validate_against_optimizer: OptimizerNotConfigured — %s", exc)
        return {"available": False, "reason": "optimizer_not_configured"}

    if history is None:
        logger.warning(
            "validate_against_optimizer: brand_code=%r not found in Optimizer",
            proxy_brand_code,
        )
        return {"available": False, "reason": "brand_not_found", "brand_code": proxy_brand_code}

    if not history.weekly_actuals:
        logger.warning(
            "validate_against_optimizer: brand_code=%r returned 0 weekly actuals",
            proxy_brand_code,
        )
        return {"available": False, "reason": "no_actuals", "brand_code": proxy_brand_code}

    # ── Compute mean actuals over comparison window ────────────────────────
    optimizer_actual = sum(w.sales for w in history.weekly_actuals) / len(history.weekly_actuals)

    if optimizer_actual == 0.0:
        logger.warning(
            "validate_against_optimizer: mean actuals=0 for brand_code=%r — cannot compute deviation",
            proxy_brand_code,
        )
        return {"available": False, "reason": "zero_actuals", "brand_code": proxy_brand_code}

    deviation_pct = (launch_value - optimizer_actual) / optimizer_actual * 100.0

    # ── Deviation severity (mirrors CrossProductValidation.severity_consistent) ─
    abs_dev = abs(deviation_pct)
    if abs_dev < 15.0:
        severity: str = "low"
    elif abs_dev < 35.0:
        severity = "medium"
    else:
        severity = "high"

    # ── Confidence: n_observations relative to horizon ────────────────────
    n = history.n_observations
    if n >= horizon_weeks:
        confidence = 1.0
    elif n < 4:
        confidence = 0.3
    else:
        # Linear interpolation between 0.3 (n=4) and 1.0 (n=horizon_weeks)
        confidence = 0.3 + 0.7 * (n - 4) / max(horizon_weeks - 4, 1)
    confidence = round(min(max(confidence, 0.0), 1.0), 4)

    # ── Build validated schema object ─────────────────────────────────────
    result = CrossProductValidation(
        proxy_brand=proxy_brand_code,
        launch_forecast_value=launch_value,
        optimizer_actual_value=round(optimizer_actual, 4),
        deviation_pct=round(deviation_pct, 4),
        deviation_severity=severity,  # type: ignore[arg-type]
        confidence=confidence,
    )

    return {
        "available": True,
        "proxy_brand": result.proxy_brand,
        "launch_forecast_value": result.launch_forecast_value,
        "optimizer_actual_value": result.optimizer_actual_value,
        "deviation_pct": result.deviation_pct,
        "deviation_severity": result.deviation_severity,
        "confidence": result.confidence,
    }
