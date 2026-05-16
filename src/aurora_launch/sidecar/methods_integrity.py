"""Async integrity-check handlers.

Handlers: start_integrity_check, cancel_integrity_check.

Module-level singletons (_integrity_threads, _integrity_cancel_flags) live in
methods.py and are accessed via late import to avoid circular dependency.
"""

from __future__ import annotations

import threading
import uuid
from typing import Any

from aurora_launch.sidecar import events


def register(name: str):
    """Proxy to methods.register."""
    from aurora_launch.sidecar.methods import register as _register
    return _register(name)


def _get_project_db():
    from aurora_launch.sidecar.methods import _get_project_db as _gpd
    return _gpd()


def _get_integrity_threads() -> dict[str, threading.Thread]:
    from aurora_launch.sidecar import methods as _m
    return _m._integrity_threads


def _get_integrity_cancel_flags() -> dict[str, threading.Event]:
    from aurora_launch.sidecar import methods as _m
    return _m._integrity_cancel_flags


# ─── Handlers ─────────────────────────────────────────────────────────────────


@register("start_integrity_check")
def _start_integrity_check(_params: dict[str, Any]) -> dict[str, Any]:
    """Run ProjectDB.check_integrity() in a background thread. Non-blocking.

    S-08: for large DBs the full integrity scan (PRAGMA integrity_check + blob
    filesystem walk) can take seconds. Running async keeps the IPC loop free.

    Emits events:
      - integrity_check_progress: {"handle", "phase", "detail"} during scan
      - integrity_check_completed: {"handle", "report"} on success
      - integrity_check_failed: {"handle", "error"} on error

    Returns:
      - integrity_handle: str (UUID) — for cancel correlation

    Raises:
      - SidecarBusyError: если cap MAX_CONCURRENT_INTEGRITY reached.
        Customer видит UX-5 toast «Aurora завершает проверку, попробуйте...»
    """
    # Phase 2.B: bounded cap (integrity=1 — DB-scan heavy task).
    from aurora_launch.sidecar import methods as _m
    _m._check_capacity(
        "проверку целостности",
        _m._integrity_threads,
        _m.MAX_CONCURRENT_INTEGRITY,
    )

    handle = str(uuid.uuid4())
    cancel = threading.Event()
    _get_integrity_cancel_flags()[handle] = cancel

    def runner() -> None:
        try:
            events.emit(
                "integrity_check_progress",
                {
                    "integrity_handle": handle,
                    "phase": "starting",
                    "detail": "Acquiring ProjectDB reference",
                },
            )

            if cancel.is_set():
                events.emit(
                    "integrity_check_cancelled",
                    {"integrity_handle": handle},
                )
                return

            # DB reads happen in the runner thread — check_integrity() is
            # read-only (no writes) so sqlite3 check_same_thread is safe when
            # ProjectDB was opened with isolation_level=None (autocommit WAL).
            db = _get_project_db()

            if cancel.is_set():
                events.emit(
                    "integrity_check_cancelled",
                    {"integrity_handle": handle},
                )
                return

            events.emit(
                "integrity_check_progress",
                {
                    "integrity_handle": handle,
                    "phase": "scanning",
                    "detail": "Running blob + ref-count checks",
                },
            )

            report = db.check_integrity()

            if cancel.is_set():
                events.emit(
                    "integrity_check_cancelled",
                    {"integrity_handle": handle},
                )
                return

            events.emit(
                "integrity_check_completed",
                {
                    "integrity_handle": handle,
                    "report": report,
                },
            )
        except Exception as exc:  # noqa: BLE001
            try:
                events.emit(
                    "integrity_check_failed",
                    {
                        "integrity_handle": handle,
                        "error": str(exc),
                        "kind": type(exc).__name__,
                    },
                )
            except (OSError, ValueError):
                pass
        finally:
            _get_integrity_cancel_flags().pop(handle, None)
            _get_integrity_threads().pop(handle, None)

    thread = threading.Thread(
        target=runner,
        name=f"aurora-integrity-{handle[:8]}",
        daemon=True,
    )
    _get_integrity_threads()[handle] = thread
    thread.start()

    return {"integrity_handle": handle}


@register("cancel_integrity_check")
def _cancel_integrity_check(params: dict[str, Any]) -> dict[str, Any]:
    """Cooperative cancel of a running integrity check.

    Sets the cancel flag; the runner thread exits at its next cancellation
    boundary. Mirrors cancel_forecast (D5: no SIGINT, no terminate).

    Params: integrity_handle: str
    Returns: {"cancelled": bool}
    """
    handle = str(params.get("integrity_handle", ""))
    flag = _get_integrity_cancel_flags().get(handle)
    if flag is None:
        return {"cancelled": False, "reason": "handle not found or already finished"}
    flag.set()
    return {"cancelled": True, "integrity_handle": handle}
