"""Lazy PyMC import wrapper (Phase Π.5.1).

Closes audit Pf-03 (cold start ≤2s): PyMC takes 3-5s к import (numpy / scipy /
pytensor backend setup). For Launch Planner, this delays Tauri webview ready
event by perceived 5-7s — unacceptable for premium first-run wow.

Solution: defer PyMC import к first actual training call (proxy Bayesian
training is rare event, typically once per pilot). UI shows "Starting Aurora"
shimmer for ~500ms (sidecar spawn + light imports), then immediately presents
welcome / onboarding screen.

Usage:
    from aurora_launch.engines.lazy_pymc import lazy_pymc

    pm = lazy_pymc()  # First call: 3-5s; subsequent: cached module
    with pm.Model() as model:
        ...

Module-level imports должны use direct `import pymc as pm` ONLY if они
already в the slow path. Hot-path code (sidecar startup, IPC handlers,
schema validation, pure_transfer forecast) avoids PyMC entirely.
"""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)

_pymc_module: Any = None
_pytensor_module: Any = None
_arviz_module: Any = None


def lazy_pymc() -> Any:
    """Return cached pymc module. First call imports (slow); subsequent are O(1)."""
    global _pymc_module
    if _pymc_module is None:
        _log.info("Importing pymc (first call, may take 3-5s)...")
        import pymc as pm  # type: ignore[import-not-found]
        _pymc_module = pm
        _log.info("pymc imported")
    return _pymc_module


def lazy_pytensor() -> Any:
    """Return cached pytensor module."""
    global _pytensor_module
    if _pytensor_module is None:
        _log.info("Importing pytensor (first call)...")
        import pytensor  # type: ignore[import-not-found]
        _pytensor_module = pytensor
    return _pytensor_module


def lazy_arviz() -> Any:
    """Return cached arviz module."""
    global _arviz_module
    if _arviz_module is None:
        _log.info("Importing arviz (first call)...")
        import arviz  # type: ignore[import-not-found]
        _arviz_module = arviz
    return _arviz_module


def pymc_loaded() -> bool:
    """Check без triggering import — useful for diagnostics."""
    return _pymc_module is not None


def reset_for_testing() -> None:
    """Reset cached modules. Tests only."""
    global _pymc_module, _pytensor_module, _arviz_module
    _pymc_module = None
    _pytensor_module = None
    _arviz_module = None
