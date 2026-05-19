"""Adapter — Launch's MMM decomposition entry point (Sprint 0 wire 2026-05-19).

Delegates decompose к shared aurora_engines.decompose OR legacy local fallback
based on USE_SHARED_ENGINES env var.

USE_SHARED_ENGINES (default "1"):
    "1" — use aurora_engines.decompose (canonical shared library)
    "0" — use aurora_launch.engines.legacy.decompose.decompose

Public API preserved: decompose(project_dir, unit_costs_override=None,
unit_cost_inflation_pct=None) → dict[str, Any].

Note: shared accepts also kpi_unit_cost_override (4th positional), Launch caller
doesn't pass it — defaults None. Backward-compatible forward.

Refs: ~/.claude/plans/skeleton-squishy-quill.md Sprint 0,
aurora-meta INBOX_TO_MM 5cec585 (MN feature flag ack).
"""
from __future__ import annotations

import os
from typing import Any

__all__ = ["decompose", "compute_roi_verdict"]

# Re-export compute_roi_verdict from the active backend at import time
# so callers (and INV-02 smoke tests) can do: from aurora_launch.engines.decompose import compute_roi_verdict
if os.environ.get("USE_SHARED_ENGINES", "1") == "1":
    from aurora_engines import compute_roi_verdict as compute_roi_verdict  # noqa: F401
else:
    from aurora_launch.engines.legacy.decompose import compute_roi_verdict as compute_roi_verdict  # noqa: F401


def decompose(
    project_dir: str,
    unit_costs_override: dict | None = None,
    unit_cost_inflation_pct: dict | None = None,
) -> dict[str, Any]:
    """Decompose KPI into baseline + channel contributions — delegates per USE_SHARED_ENGINES.

    Args:
        project_dir: Path к project с models/latest.pkl
        unit_costs_override: Optional override для config.unit_costs из pickle
        unit_cost_inflation_pct: Optional per-channel cost inflation factor

    Returns:
        JSON с waterfall data, ROI, share of spend vs effect
    """
    if os.environ.get("USE_SHARED_ENGINES", "1") == "1":
        from aurora_engines import decompose as _impl
    else:
        from aurora_launch.engines.legacy.decompose import decompose as _impl
    return _impl(project_dir, unit_costs_override, unit_cost_inflation_pct)
