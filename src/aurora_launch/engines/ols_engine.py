"""Adapter — Launch's MMM OLS training entry point (Sprint 0 wire 2026-05-19).

Delegates train_ols к shared aurora_engines.train_ols OR legacy local fallback
based on USE_SHARED_ENGINES env var.

USE_SHARED_ENGINES (default "1"):
    "1" — use aurora_engines.train_ols (canonical shared library)
    "0" — use aurora_launch.engines.legacy.ols_engine.train_ols

Public API preserved: train_ols(config, project_dir, progress_callback=None)
→ dict[str, Any]. EXACT signature match с shared.

Refs: ~/.claude/plans/skeleton-squishy-quill.md Sprint 0,
aurora-meta INBOX_TO_MM 5cec585 (MN feature flag ack).
"""
from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

__all__ = ["train_ols", "recommend_engine"]

# recommend_engine is a pure Launch routing utility (not in shared library).
# Always re-exported from legacy regardless of USE_SHARED_ENGINES.
from aurora_launch.engines.legacy.ols_engine import recommend_engine  # noqa: E402


def train_ols(
    config: dict,
    project_dir: str,
    progress_callback: Callable[[float, str], None] | None = None,
) -> dict[str, Any]:
    """Train OLS small-data fallback model — delegates per USE_SHARED_ENGINES.

    Args:
        config: training config dict (same shape as Bayesian train_model)
        project_dir: path к project workspace
        progress_callback: optional progress reporter

    Returns:
        Training result dict с trained OLS model artifacts.
    """
    if os.environ.get("USE_SHARED_ENGINES", "1") == "1":
        from aurora_engines import train_ols as _impl
    else:
        from aurora_launch.engines.legacy.ols_engine import train_ols as _impl
    return _impl(config, project_dir, progress_callback)
