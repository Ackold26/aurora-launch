"""Adapter — Launch's MMM Bayesian training entry point (Sprint 0 wire 2026-05-19).

Delegates train_model к shared aurora_engines.train_model OR legacy local fallback
based on USE_SHARED_ENGINES env var.

USE_SHARED_ENGINES (default "1"):
    "1" — use aurora_engines.train_model (canonical shared library)
    "0" — use aurora_launch.engines.legacy.bayesian_engine.train_model

Public API preserved: train_model(config, project_dir, progress_callback=None) → dict[str, Any].

Refs: ~/.claude/plans/skeleton-squishy-quill.md Sprint 0,
aurora-meta INBOX_TO_MM 5cec585 (MN feature flag ack on per-package wiring).
"""
from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

__all__ = ["train_model"]


def train_model(
    config: dict,
    project_dir: str,
    progress_callback: Callable[[float, str], None] | None = None,
) -> dict[str, Any]:
    """Train Bayesian MMM model — delegates per USE_SHARED_ENGINES env flag.

    Args:
        config: training config dict (see modeler.py for full schema)
        project_dir: path к project workspace
        progress_callback: optional progress reporter, swallows exceptions

    Returns:
        Training result dict с trained model artifacts.
    """
    if os.environ.get("USE_SHARED_ENGINES", "1") == "1":
        from aurora_engines import train_model as _impl
    else:
        from aurora_launch.engines.legacy.bayesian_engine import train_model as _impl
    return _impl(config, project_dir, progress_callback)
