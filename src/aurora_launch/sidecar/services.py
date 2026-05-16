"""Dependency-injection container for Aurora Launch sidecar singleton services.

ROADMAP item 2.7: four module-level singletons in methods.py are wrapped in a
ServiceContainer so tests can inject mocks without touching global state.

Design constraints:
- Backward-compatible: _get_project_db() / _get_autosave_manager() in methods.py
  continue to work unchanged; they are re-routed to call the container.
- Thread-safe: each service slot has its own lock (mirrors existing pattern).
- Test escape hatch: set_services_for_testing() replaces the module-level
  container; reset_services_for_testing() restores the default singleton.
- Production path: lazy init logic stays in methods.py getters; ServiceContainer
  only holds the already-initialized instances (no init logic here).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# ServiceContainer
# ---------------------------------------------------------------------------


@dataclass
class ServiceContainer:
    """Holds references to the four sidecar singleton services.

    All slots default to None (lazy init by methods.py getters).  Tests can
    supply pre-built mocks via the constructor or via ``set_*`` helpers.

    Thread-safety: each slot is protected by its own lock so concurrent
    handlers can read without contention across slots.
    """

    # Service slots (typed as Any to avoid top-level circular imports — the
    # concrete types live in aurora_launch.persistence.*)
    project_db: Any = field(default=None)
    autosave_manager: Any = field(default=None)
    # GC thread is managed directly in methods.py; exposed here for test reset.
    gc_thread: Any = field(default=None)

    # Per-slot locks (not part of DI interface; internal to thread-safety).
    _project_db_lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)
    _autosave_lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    # ---------------------------------------------------------------------------
    # project_db accessor
    # ---------------------------------------------------------------------------

    def get_project_db(self) -> Any:
        """Return project_db if already set; returns None if not yet initialized.

        The actual lazy-init logic lives in methods._get_project_db(); this
        method is just a thread-safe getter for the already-set instance.
        """
        if self.project_db is not None:
            return self.project_db
        with self._project_db_lock:
            return self.project_db  # may still be None — caller handles

    def set_project_db(self, db: Any) -> None:
        """Set the project_db slot (used by methods._get_project_db after init)."""
        with self._project_db_lock:
            self.project_db = db

    # ---------------------------------------------------------------------------
    # autosave_manager accessor
    # ---------------------------------------------------------------------------

    def get_autosave_manager(self) -> Any:
        """Return autosave_manager if already set; returns None if not yet initialized."""
        if self.autosave_manager is not None:
            return self.autosave_manager
        with self._autosave_lock:
            return self.autosave_manager  # may still be None

    def set_autosave_manager(self, mgr: Any) -> None:
        """Set the autosave_manager slot (used by methods._get_autosave_manager after init)."""
        with self._autosave_lock:
            self.autosave_manager = mgr

    # ---------------------------------------------------------------------------
    # Reset helpers (tests)
    # ---------------------------------------------------------------------------

    def clear(self) -> None:
        """Reset all slots to None without closing resources.

        WARNING: call close() before clear() in production code so DB locks
        are released; in tests with mock objects clear() alone is fine.
        """
        with self._project_db_lock:
            self.project_db = None
        with self._autosave_lock:
            self.autosave_manager = None
        self.gc_thread = None


# ---------------------------------------------------------------------------
# Module-level container (the one real singleton — wraps the four services)
# ---------------------------------------------------------------------------

_services: ServiceContainer = ServiceContainer()
_services_lock: threading.Lock = threading.Lock()


def get_services() -> ServiceContainer:
    """Return the current active ServiceContainer.

    Production code: always returns the module-level singleton.
    Test code: returns whatever was installed via set_services_for_testing().
    """
    return _services


def set_services_for_testing(svc: ServiceContainer) -> None:
    """Replace the active ServiceContainer with a test-supplied one.

    Call reset_services_for_testing() in test teardown to restore the default.

    Example::

        container = ServiceContainer(project_db=MockProjectDB())
        set_services_for_testing(container)
        ...
        reset_services_for_testing()
    """
    global _services  # noqa: PLW0603
    with _services_lock:
        _services = svc


# Audit H-4 (этап 2.10): reset должен также обнулять module-level
# singletons в methods.py чтобы test isolation была полной. Через
# callback-registration избегаем circular import (services.py не должна
# импортировать methods.py).
_external_reset_callbacks: list[Any] = []


def register_reset_callback(cb: Any) -> None:
    """Регистрирует функцию которая будет вызвана при reset_services_for_testing.

    Используется methods.py чтобы зарегистрировать обнуление _PROJECT_DB /
    _AUTOSAVE module-level vars. Идемпотентно — повторная регистрация той же
    функции игнорируется.
    """
    if cb not in _external_reset_callbacks:
        _external_reset_callbacks.append(cb)


def reset_services_for_testing() -> None:
    """Restore the default (empty) ServiceContainer + reset external module-level singletons.

    Idempotent — safe to call even if set_services_for_testing() was never
    called. Также вызывает все registered reset_callbacks (см. register_reset_callback)
    чтобы methods.py обнулил _PROJECT_DB / _AUTOSAVE / _GC_THREAD module-level vars.
    """
    global _services  # noqa: PLW0603
    with _services_lock:
        _services = ServiceContainer()
    # Внешние reset callbacks (best-effort, не падаем на failed callback)
    for cb in _external_reset_callbacks:
        try:
            cb()
        except Exception:
            pass
