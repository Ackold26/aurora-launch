"""Auto-refresh consent and data-source update handlers.

Handlers: get_refresh_consent, set_refresh_consent,
          check_data_source_updates, dismiss_refresh_trigger.
Helper:   _get_consent_manager().

Module-level singletons (_consent_manager, _dismissed_refresh) live in
methods.py; this module accesses them via ``import aurora_launch.sidecar.methods
as _m``.  The ``register`` decorator also lives in methods.py and is imported
here so that @register side-effects fire when methods.py does its late import of
this module at the bottom.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)


# ─── Imports from dispatcher module (late-binding avoids circular import) ──────

def _m():
    """Return the methods module (late import to break circular dependency)."""
    from aurora_launch.sidecar import methods as _methods_mod
    return _methods_mod


def register(name: str):
    """Proxy to methods.register — called at import time when methods.py does
    its late import of this module."""
    from aurora_launch.sidecar.methods import register as _register
    return _register(name)


# ─── Singleton helpers (delegated to methods module) ──────────────────────────

def _get_project_db():
    from aurora_launch.sidecar.methods import _get_project_db as _gpd
    return _gpd()


# ─── ConsentManager singleton ─────────────────────────────────────────────────
# Per-session in-memory dismissed set. When the user clicks «Позже» the
# project UUID is added here; watcher.check_for_updates() returns [] for
# dismissed projects in this session. Restarting the sidecar resets the set
# — intentional so "Later" means "later this session", not "forever".
_dismissed_refresh: set[str] = set()

# Module-level ConsentManager singleton (lazy-init on first call).
_consent_manager: Any = None
_consent_lock = threading.Lock()


def _get_consent_manager() -> Any:
    """Return ConsentManager singleton (lazy-init).

    DI-aware: tests may set the singleton directly.
    Store backend: ProjectDB напрямую (kv_get/kv_set методы реализованы
    после v003 migration — см. Phase 1.B.1). В тестах ConsentManager
    может принять in-memory dict shim или None.

    C-2 fix (audit 4.5 / Phase 1.B.1): убрана _DbKvShim wrapper которая
    проглатывала AttributeError при отсутствии kv_get/kv_set. Теперь
    ProjectDB имеет эти методы, передаём её напрямую.
    """
    global _consent_manager  # noqa: PLW0603
    if _consent_manager is not None:
        return _consent_manager
    with _consent_lock:
        if _consent_manager is not None:
            return _consent_manager
        try:
            from aurora_launch.engines.data_source_watcher import ConsentManager

            db = _get_project_db()  # may be None — ConsentManager handles gracefully
            _consent_manager = ConsentManager(db_store=db)
        except Exception as exc:
            logger.warning("_get_consent_manager init failed: %s", exc)
            from aurora_launch.engines.data_source_watcher import ConsentManager

            _consent_manager = ConsentManager(db_store=None)
    return _consent_manager


# ─── Handlers ─────────────────────────────────────────────────────────────────


@register("get_refresh_consent")
def _get_refresh_consent(params: dict[str, Any]) -> Any:
    """Return the current RefreshConsentSetting or null (first-run).

    Params: {}
    Returns: {enabled, frequency, last_prompted_at} | null
    """
    mgr = _get_consent_manager()
    setting = mgr.get()
    if setting is None:
        return None
    return setting.model_dump()


@register("set_refresh_consent")
def _set_refresh_consent(params: dict[str, Any]) -> dict[str, Any]:
    """Persist RefreshConsentSetting (user opt-in).

    Params: { enabled: bool, frequency?: "daily"|"weekly"|"monthly" }
    Returns: updated {enabled, frequency, last_prompted_at}

    152-FZ §9: consent must be explicit (enabled=True means user clicked opt-in).
    """
    enabled = bool(params.get("enabled", False))
    frequency = str(params.get("frequency", "weekly"))
    mgr = _get_consent_manager()
    updated = mgr.set(enabled=enabled, frequency=frequency)
    return updated.model_dump()


@register("check_data_source_updates")
def _check_data_source_updates(params: dict[str, Any]) -> dict[str, Any]:
    """Check all registered data sources for new data.

    Params: {
        project_uuid: str,
        sources: list[{source_kind, path?, last_modified_seen?}]
    }
    Returns: { triggers: list[{project_uuid, reason, detected_at, source}] }

    Workflow:
    1. Consent check — if no consent or disabled, returns [] immediately.
    2. Build DataSourceWatcher with provided source configs.
    3. Run check_for_updates().
    4. Return triggers (empty list if none detected).

    NOTE: does NOT auto-trigger re-forecast.  Caller (frontend) shows the
    RefreshAvailableBanner and waits for user confirmation.
    """
    from aurora_launch.engines.data_source_watcher import DataSourceWatcher
    from aurora_launch.schemas.auto_refresh import DataSourceConfig

    # Consent check
    mgr = _get_consent_manager()
    consent = mgr.get()
    if consent is None or not consent.enabled:
        return {"triggers": []}

    project_uuid = str(params.get("project_uuid", ""))
    raw_sources: list[dict[str, Any]] = params.get("sources", [])

    db = _get_project_db()
    watcher = DataSourceWatcher(project_uuid=project_uuid, db=db)

    for raw in raw_sources:
        try:
            cfg = DataSourceConfig.model_validate(raw)
            watcher.register_source(cfg)
        except Exception as exc:
            logger.warning(
                "check_data_source_updates: invalid source config %r — %s", raw, exc
            )

    # Apply session dismissal
    if project_uuid in _dismissed_refresh:
        return {"triggers": []}

    triggers = watcher.check_for_updates()
    return {"triggers": [t.model_dump() for t in triggers]}


@register("dismiss_refresh_trigger")
def _dismiss_refresh_trigger(params: dict[str, Any]) -> dict[str, Any]:
    """Suppress refresh triggers for a project for the rest of this session.

    Params: { project_uuid: str }
    Returns: { dismissed: true }

    «Позже» button: user is saying "not now, remind me next session", not "never".
    To permanently disable: call set_refresh_consent({enabled: false}).
    """
    project_uuid = str(params.get("project_uuid", ""))
    _dismissed_refresh.add(project_uuid)
    logger.debug("dismiss_refresh_trigger: %s suppressed for this session", project_uuid)
    return {"dismissed": True}
