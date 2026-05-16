"""Sidecar method handlers — JSON-RPC dispatch table.

Each method receives `params: dict[str, Any]` and returns JSON-serialisable
result OR raises an exception (caught by server, converted к error response).

Block 4 method inventory:
- `ping` — diagnostic; returns `{"pong": true, "version": ...}`
- `save_bundle` — Phase 2: Python BundleZipWriter wrapper
- `parse_data_file` — Phase 3: AdapterRegistry.detect + parse
- `start_forecast` — Phase 4: spawn forecast task, emit progress events
- `cancel_forecast` — Phase 4: cooperative cancel via atomic flag
- `get_forecast_status` — Phase 4: poll status (also event-driven)
- `inspect_bundle_entry_json` — Phase 5: Inspector tab data wiring
- `shutdown` — graceful exit signal from Rust parent

Phase Π.3b — ProjectDB wired handlers:
- `create_project` — create new project in singleton ProjectDB
- `list_projects` — list all projects
- `get_project` — get project detail + version list
- `delete_project` — delete project and all its blobs
- `list_versions` — list versions of a project
- `compare_versions` — diff two versions by file content hashes
- `import_aurora_bundle` — import .aurora ZIP bundle into ProjectDB
- `load_sample_bundle` — load pilot XLSX + derive synthetic posterior

All `cancel_forecast` cancellation goes through `_cancel_flags` dict —
cooperative pattern (D5: NO SIGINT, NO terminate).

Implementation split (Phase 1.B.2):
  methods_forecast.py      — forecast / budget-optimizer / explain / reproduce
  methods_project.py       — project CRUD / bundle / parse / inspector
  methods_integrity.py     — async integrity check
  methods_consent.py       — auto-refresh consent + data-source watcher
  methods_cross_product.py — validate_against_optimizer
  methods.py (this file)   — dispatcher + ping/negotiate/shutdown + all
                             module-level singletons + infra helpers
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

from aurora_launch import __version__
from aurora_launch.sidecar import events
from aurora_launch.sidecar.protocol_version import (
    MIN_COMPATIBLE_RUST,
    PROTOCOL_VERSION,
)
from aurora_launch.sidecar.protocol_version import (
    negotiate as _protocol_negotiate,
)
from aurora_launch.sidecar.services import (
    get_services,
    register_reset_callback,
    reset_services_for_testing,
    set_services_for_testing,
)

# ─── Method registry ──────────────────────────────────────────────────────────


_METHODS: dict[str, Callable[[dict[str, Any]], Any]] = {}
_cancel_flags: dict[str, threading.Event] = {}
_forecast_threads: dict[str, threading.Thread] = {}
_integrity_threads: dict[str, threading.Thread] = {}
_integrity_cancel_flags: dict[str, threading.Event] = {}

# Dict for in-flight optimize_budget tasks (handle → thread).
_optimize_threads: dict[str, threading.Thread] = {}
_optimize_cancel_flags: dict[str, threading.Event] = {}

# ─── Phase 2.B: bounded concurrent task caps (H-1) ───────────────────────────
# Customer запускающий 10 forecasts одновременно — DoS local machine. Cap
# защищает от resource exhaustion + UX-5: customer получает empathetic
# «подождите 20-30 секунд» вместо crash/timeout.
MAX_CONCURRENT_FORECASTS = 2
MAX_CONCURRENT_OPTIMIZE = 1
MAX_CONCURRENT_INTEGRITY = 1


class SidecarBusyError(RuntimeError):
    """Raised when concurrent task cap reached.

    Frontend ловит и показывает empathetic toast (UX-5) — non-blocking
    error, customer понимает situation.
    """

    def __init__(self, kind: str, current: int, cap: int) -> None:
        super().__init__(
            f"Aurora завершает предыдущий {kind} ({current}/{cap} активны). "
            f"Подождите 20-30 секунд и попробуйте снова."
        )
        self.kind = kind
        self.current = current
        self.cap = cap


def _check_capacity(kind: str, threads_dict: dict[str, threading.Thread], cap: int) -> None:
    """Raises SidecarBusyError если number alive threads >= cap.

    Считает только живые threads — completed threads автоматически очищаются
    через finally blocks в runner(). Это race-safe: между check и spawn
    может пробежать другой thread, но cap+1 в peak допустимо (не SLA
    violation).
    """
    alive = sum(1 for t in threads_dict.values() if t.is_alive())
    if alive >= cap:
        raise SidecarBusyError(kind, alive, cap)


# ─── ProjectDB singleton ──────────────────────────────────────────────────────


class SidecarStorageError(RuntimeError):
    """Raised when ProjectDB singleton initialization fails."""


class SidecarSecurityError(ValueError):
    """Raised when a user-supplied path violates security policy (Phase 2.C H-4)."""


def _get_allowed_roots() -> list[Path]:
    """Return allowed file I/O roots для path security.

    Mirrors Tauri capabilities scope (capabilities/default.json):
    $APPDATA / $DOCUMENT / $DOWNLOAD / $TEMP. Customer files должны быть
    в одном из этих.
    """
    roots: list[Path] = []
    if appdata := os.environ.get("APPDATA"):
        roots.append(Path(appdata))
    if userprofile := os.environ.get("USERPROFILE"):
        roots.append(Path(userprofile) / "Documents")
        roots.append(Path(userprofile) / "Downloads")
    if home := os.environ.get("HOME"):  # Unix
        roots.append(Path(home) / "Documents")
        roots.append(Path(home) / "Downloads")
        roots.append(Path(home) / ".aurora")
    # Tmp/test isolation — pytest tmp_path mostly /tmp або %TEMP%
    if tmp := os.environ.get("TEMP"):
        roots.append(Path(tmp))
    if tmpdir := os.environ.get("TMPDIR"):
        roots.append(Path(tmpdir))
    # Linux fallback
    roots.append(Path("/tmp"))
    return roots


_PROJECT_DB: Any = None  # ProjectDB | None — typed as Any to avoid top-level import
_PROJECT_DB_LOCK = threading.Lock()

# ─── AutosaveManager singleton ────────────────────────────────────────────────
# Audit A-05 fix: AutosaveManager was shipped в S-05 but never instantiated
# в sidecar; SIGTERM handler was dead code. We create the singleton lazily
# alongside ProjectDB so signal handlers ARE registered. Wizard sessions (when
# wired в Phase Premium) will call start_autosave/stop_autosave per project.
_AUTOSAVE: Any = None  # AutosaveManager | None
_AUTOSAVE_LOCK = threading.Lock()

# ─── Periodic GC thread singleton (S-07) ─────────────────────────────────────
# Daemon thread that wakes every GC_POLL_INTERVAL_S to check whether 7 days
# have passed since the last gc run. ProjectDB._maybe_gc_on_open() handles the
# startup-time trigger; this thread covers the "sidecar stays alive > 7 days"
# case. Thread is daemon so it exits with the process without explicit join.
_GC_THREAD: threading.Thread | None = None
_GC_THREAD_LOCK = threading.Lock()
_GC_STOP_EVENT: threading.Event = threading.Event()


# ─── Sample bundle paths (canonical location for monkeypatching) ──────────────
# Kept here so tests can monkeypatch ``aurora_launch.sidecar.methods._SAMPLE_BUNDLE_PATHS``.
# The handler (_load_sample_bundle) lives in methods_project.py and reads
# this dict via a late-import accessor (_get_sample_bundle_paths()).
# Audit A-06 fix: renamed misleading `afala_afalaza` к `venarus_baseline` since
# the file IS Венарус data — original key suggested wrong proxy mapping.
_SAMPLE_BUNDLE_PATHS: dict[str, Path] = {
    "kagotsel_venarus": Path(
        "C:/Users/ackol/Desktop/Аврора - материалы для обучения и тестирования"
        "/Эконометрика - тестовые файлы/XLSX"
        "/Кагоцел РФ+_данные для эконометрики + наши данные 29.08.xlsx"
    ),
    "venarus_baseline": Path(
        "C:/Users/ackol/Desktop/Аврора - материалы для обучения и тестирования"
        "/Эконометрика - тестовые файлы/XLSX"
        "/Венарус_данные для эконометрики для модели + наши данные.xlsx"
    ),
    "multi_proxy": Path(
        "C:/Users/ackol/Desktop/Аврора - материалы для обучения и тестирования"
        "/Эконометрика - тестовые файлы/XLSX/MMX 2021-2025 исходник.xlsx"
    ),
}


# Audit H-4 (этап 2.10): callback который reset_services_for_testing() вызовет
# чтобы обнулить module-level singletons (test isolation). Регистрируется
# после определения singletons (см. конец файла).
def _hard_reset_module_singletons() -> None:
    # Audit B-02 (этап 4.5): включаем _consent_manager и _dismissed_refresh
    # из §3.5. Без них tests auto-refresh заражают друг друга — _cached
    # consent от предыдущего теста + UUID из предыдущего проекта в set.
    # globals().__setitem__ позволяет обнулить переменные определённые
    # ниже в файле без forward declaration.
    g = globals()
    g["_PROJECT_DB"] = None
    g["_AUTOSAVE"] = None
    # Also reset consent singletons that live in methods_consent.py
    try:
        import aurora_launch.sidecar.methods_consent as _mc
        _mc._consent_manager = None
        _mc._dismissed_refresh = set()
    except ImportError:
        pass


# How often the GC thread wakes to check. 1 hour is fine — 7-day window means
# worst-case skew is 1 hour, which is acceptable. Sleeping in short intervals
# (rather than one 7-day sleep) allows clean daemon shutdown without blocking.
GC_POLL_INTERVAL_S: float = 3600.0  # 1 hour
# GC threshold in seconds, mirrors ProjectDB.GC_INTERVAL_SECONDS.
GC_INTERVAL_S: float = 7 * 24 * 3600.0  # 7 days


def _get_autosave_manager() -> Any:
    """Return AutosaveManager singleton (lazy init).

    DI-aware (ROADMAP 2.7): checks ServiceContainer first; falls back to the
    module-level _AUTOSAVE singleton so existing call sites and tests that
    pre-load _AUTOSAVE directly continue to work unchanged.

    Singleton ensures SIGTERM/atexit handlers registered ONCE per sidecar
    process. Currently no wizard session manager wires individual project
    autosave timers — those will be added в Phase Premium when wizard state
    becomes persistent. For now: signal handlers register; no active timers.
    """
    # 1. DI container check — tests may inject a mock AutosaveManager.
    _svc = get_services()
    _container_mgr = _svc.get_autosave_manager()
    if _container_mgr is not None:
        return _container_mgr

    global _AUTOSAVE  # noqa: PLW0603

    if _AUTOSAVE is not None:
        return _AUTOSAVE

    with _AUTOSAVE_LOCK:
        if _AUTOSAVE is not None:
            return _AUTOSAVE
        try:
            from aurora_launch.persistence.autosave import AutosaveManager

            # Resolve data root same way as ProjectDB so session marker
            # co-locates с the DB file.
            env_path = os.environ.get("AURORA_PROJECT_DB_PATH")
            if env_path:
                data_root = Path(env_path)
            else:
                try:
                    import platformdirs  # type: ignore[import-untyped]

                    data_root = Path(platformdirs.user_data_dir("Aurora Launch"))
                except ImportError:
                    data_root = Path.home() / ".aurora-launch"
            autosave_dir = data_root / "autosaves"
            autosave_dir.mkdir(parents=True, exist_ok=True)

            _AUTOSAVE = AutosaveManager(
                autosave_dir=autosave_dir,
                register_signal_handlers=True,
            )
            return _AUTOSAVE
        except Exception as exc:
            raise SidecarStorageError(f"Cannot initialize AutosaveManager: {exc}") from exc


def _get_project_db() -> Any:
    """Return ProjectDB singleton; initialize on first call.

    DI-aware (ROADMAP 2.7): checks ServiceContainer first so tests can inject
    a mock without touching global state.  Falls back to the module-level
    _PROJECT_DB singleton for full backward-compatibility.

    Path resolution priority (production path):
      1. ServiceContainer.project_db if set (test injection)
      2. _PROJECT_DB module-level var if already initialized
      3. AURORA_PROJECT_DB_PATH env var (tests / staging override)
      4. platformdirs.user_data_dir("Aurora Launch") if platformdirs available
      5. ~/.aurora-launch/ fallback

    Per INV-11: explicit exception wrapping, no bare pass.
    """
    # 1. DI container check — tests may inject a mock ProjectDB.
    _svc = get_services()
    _container_db = _svc.get_project_db()
    if _container_db is not None:
        return _container_db

    global _PROJECT_DB  # noqa: PLW0603

    if _PROJECT_DB is not None:
        return _PROJECT_DB

    with _PROJECT_DB_LOCK:
        # Double-checked locking (another thread may have initialized while waiting)
        if _PROJECT_DB is not None:
            return _PROJECT_DB

        try:
            from aurora_launch.persistence.blob_store import BlobStore
            from aurora_launch.persistence.project_db import ProjectDB

            env_path = os.environ.get("AURORA_PROJECT_DB_PATH")
            if env_path:
                data_root = Path(env_path)
            else:
                try:
                    import platformdirs  # type: ignore[import-untyped]

                    data_root = Path(platformdirs.user_data_dir("Aurora Launch"))
                except ImportError:
                    data_root = Path.home() / ".aurora-launch"

            data_root.mkdir(parents=True, exist_ok=True)
            blobs_dir = data_root / "blobs"
            blobs_dir.mkdir(parents=True, exist_ok=True)

            blob_store = BlobStore(blobs_dir)
            # AURORA_PROJECT_DB_KEY env override:
            #   "none"  → unencrypted (CI без sqlcipher3, tests) — DEV-ONLY
            #   "auto"  → keychain-backed (default production)
            #   hex64   → explicit key (advanced ops)
            #
            # QW1 hardening: PRODUCTION binary REFUSES к start если "none"
            # set без explicit dev/test marker. Previously: silent downgrade
            # к "auto" с warning log (which nobody reads → potential plaintext
            # data leak on dev's machine misconfigured). Now: loud SystemExit.
            key_env = os.environ.get("AURORA_PROJECT_DB_KEY", "auto").strip().lower()
            if key_env == "none":
                is_dev_profile = os.environ.get("AURORA_BUILD_PROFILE", "").lower() == "dev"
                is_testing = bool(os.environ.get("AURORA_LAUNCH_TESTING"))
                if not (is_dev_profile or is_testing):
                    import sys as _sys

                    msg = (
                        "FATAL: AURORA_PROJECT_DB_KEY=none requires explicit "
                        "AURORA_BUILD_PROFILE=dev OR AURORA_LAUNCH_TESTING=1. "
                        "Refusing к boot с unencrypted DB в production context. "
                        "Unset AURORA_PROJECT_DB_KEY or set к 'auto' (keychain) "
                        "or 64-char hex."
                    )
                    print(f"[aurora-sidecar] {msg}", file=_sys.stderr, flush=True)
                    raise SidecarStorageError(msg)
                encryption_key: str | None = None
            elif key_env == "auto":
                encryption_key = "auto"
            else:
                encryption_key = key_env  # explicit hex passed through
            db = ProjectDB(
                data_root / "projects.db",
                blob_store,
                encryption_key=encryption_key,
            )
            _PROJECT_DB = db
            # S-07: spawn periodic GC thread lazily alongside ProjectDB init.
            _start_gc_thread()
            return _PROJECT_DB
        except Exception as exc:
            raise SidecarStorageError(f"Cannot initialize ProjectDB: {exc}") from exc


def _gc_thread_body() -> None:
    """Periodic GC worker. Runs while sidecar is alive (daemon thread).

    QW8 refactor (was 1h poll with 60s slices = 10080 wakes/week burning
    laptop battery): now computes next_gc_at and sleeps single time until
    then. Wakes from sleep ONLY on stop event OR scheduled GC time.

    Per INV-14 no-lying-progress: silent in idle, log only on actual GC run.
    """
    import logging as _logging

    _gc_log = _logging.getLogger(__name__ + ".gc_thread")
    _gc_log.info("GC background thread started (interval=%ss)", GC_INTERVAL_S)

    # Audit B-2 (этап 2.10): GC thread должен использовать DI container
    # вместо прямого _PROJECT_DB. Иначе тесты с set_services_for_testing
    # не изолированы — GC продолжает стучаться в реальный singleton (или
    # уже закрытый), вплоть до use-after-free на shutdown.
    def _resolve_db() -> Any:
        svc_db = get_services().get_project_db()
        if svc_db is not None:
            return svc_db
        return _PROJECT_DB

    while not _GC_STOP_EVENT.is_set():
        # Compute next gc time. If never ran → run immediately.
        sleep_for = 0.0
        db = _resolve_db()
        if db is not None:
            try:
                from datetime import datetime

                last_ran_at, _ = db.get_gc_metadata()
                if last_ran_at:
                    last_dt = datetime.fromisoformat(last_ran_at.replace("Z", "+00:00"))
                    elapsed_s = (datetime.now(UTC) - last_dt).total_seconds()
                    sleep_for = max(0.0, GC_INTERVAL_S - elapsed_s)
            except (ValueError, TypeError) as exc:
                _gc_log.warning("GC thread: metadata parse error: %s", exc)
                sleep_for = GC_INTERVAL_S  # back off full interval

        # Single sleep. Returns True if stop event set; False on timeout.
        if _GC_STOP_EVENT.wait(timeout=sleep_for):
            break

        # Re-resolve после сна (DI container мог поменяться).
        db = _resolve_db()
        if db is None:
            # Re-loop с short sleep чтобы wait для DB init
            if _GC_STOP_EVENT.wait(timeout=60.0):
                break
            continue

        try:
            _gc_log.info("Periodic GC: running gc_orphan_blobs")
            collected = db.gc_orphan_blobs()
            db._update_gc_metadata(collected)  # noqa: SLF001
            _gc_log.info("Periodic GC: collected %d orphan(s)", collected)
        except Exception as exc:  # noqa: BLE001
            _gc_log.warning("GC thread: unexpected error (non-fatal): %s", exc)

    _gc_log.info("GC background thread stopped")


def _start_gc_thread() -> None:
    """Spawn the periodic GC daemon thread if not already running (S-07).

    Per INV-04 lazy thread spawn: called once from _get_project_db() after
    ProjectDB is initialised. Idempotent (double-checked locking).
    """
    global _GC_THREAD  # noqa: PLW0603

    if _GC_THREAD is not None and _GC_THREAD.is_alive():
        return

    with _GC_THREAD_LOCK:
        if _GC_THREAD is not None and _GC_THREAD.is_alive():
            return
        _GC_STOP_EVENT.clear()
        t = threading.Thread(
            target=_gc_thread_body,
            name="aurora-gc-periodic",
            daemon=True,
        )
        _GC_THREAD = t
        t.start()


def register(name: str):
    def decorator(fn: Callable[[dict[str, Any]], Any]):
        _METHODS[name] = fn
        return fn

    return decorator


def list_methods() -> list[str]:
    return sorted(_METHODS.keys())


def dispatch(method: str, params: dict[str, Any]) -> Any:
    if method not in _METHODS:
        raise MethodNotFoundError(method)
    return _METHODS[method](params)


class MethodNotFoundError(LookupError):
    def __init__(self, method: str) -> None:
        super().__init__(f"unknown method: {method}")
        self.method = method


# ─── Diagnostic ───────────────────────────────────────────────────────────────


@register("ping")
def _ping(_params: dict[str, Any]) -> dict[str, Any]:
    return {
        "pong": True,
        "version": __version__,
        "protocol_version": list(PROTOCOL_VERSION),
        "min_compatible_rust": list(MIN_COMPATIBLE_RUST),
        "methods": list_methods(),
    }


@register("negotiate")
def _negotiate(params: dict[str, Any]) -> dict[str, Any]:
    """Version negotiation handshake.

    Rust shell calls this at startup to confirm compatibility before issuing
    any other methods.  See protocol_version.negotiate() for contract details.

    Params:
      - rust_version: str — Rust Tauri shell semver (e.g. "0.1.0")
    Returns:
      - compatible: bool
      - reason: str | None
      - advice: str | None
    """
    rust_version = str(params.get("rust_version", "")).strip()
    if not rust_version:
        return {
            "compatible": False,
            "reason": "rust_version param missing or empty",
            "advice": "Pass rust_version as the Tauri shell semver string.",
        }
    return _protocol_negotiate(rust_version)


# ─── Lifecycle ────────────────────────────────────────────────────────────────


_SHUTDOWN_PER_FORECAST_TIMEOUT_S = 5.0


@register("shutdown")
def _shutdown(_params: dict[str, Any]) -> dict[str, Any]:
    """Graceful shutdown signal — drains in-flight forecasts, then server loop
    exits после returning result.

    Drain protocol (D5 cooperative — NO SIGINT, NO terminate):
      1. Set cancel flag on every active forecast handle (mirrors `cancel_forecast`).
      2. Join each forecast thread with a per-thread timeout
         (`_SHUTDOWN_PER_FORECAST_TIMEOUT_S`). Sampler threads exit on next
         iteration boundary; 5s budget covers a single sample's max latency
         observed in Block 4 audit.
      3. Return per-forecast status (`signaled`, `joined`, `timed_out`) so Rust
         parent can log a structured exit event.

    Threads still alive after timeout are abandoned — Python interpreter
    teardown handles them. The Rust parent should treat any `timed_out` entry
    as a hint that the next start should not depend on shared on-disk state
    being fully released yet (e.g., bundle staging path locks).

    Future work (handed off to MM): wire this to
    `aurora_common.updates.shutdown.GracefulShutdownCoordinator` once
    `aurora-common` becomes a dependency of `aurora-launch`. The coordinator
    would add module-pluggable handlers (training queue drain, telemetry flush)
    which today are not registered in Aurora Launch.

    Concurrency note: we take a single snapshot of forecast handles from
    `_forecast_threads.keys()` and use it for BOTH cancel-flag setting and
    join-waiting. Iterating `_cancel_flags` and `_forecast_threads`
    independently could observe a freshly-registered handle in one dict but
    not the other (start_forecast registers both, but Python lacks an atomic
    multi-dict write). One snapshot eliminates that window — any handle
    registered after the snapshot is simply not drained by this call.
    """
    handles = list(_forecast_threads.keys())

    forecasts_signaled: list[str] = []
    forecasts_joined: list[str] = []
    forecasts_timed_out: list[str] = []

    for handle in handles:
        flag = _cancel_flags.get(handle)
        if flag is not None:
            flag.set()
            forecasts_signaled.append(handle)

    for handle in handles:
        thread = _forecast_threads.get(handle)
        if thread is None:
            continue
        thread.join(timeout=_SHUTDOWN_PER_FORECAST_TIMEOUT_S)
        if thread.is_alive():
            forecasts_timed_out.append(handle)
        else:
            forecasts_joined.append(handle)

    # Cancel any in-flight async integrity checks (S-08) — same cooperative pattern.
    integrity_handles = list(_integrity_threads.keys())
    for ihandle in integrity_handles:
        iflag = _integrity_cancel_flags.get(ihandle)
        if iflag is not None:
            iflag.set()
    for ihandle in integrity_handles:
        ithread = _integrity_threads.get(ihandle)
        if ithread is not None:
            ithread.join(timeout=_SHUTDOWN_PER_FORECAST_TIMEOUT_S)

    # H-3 (audit 4.5 / Phase 1.A): drain optimize_budget threads — раньше пропущены.
    # Без этого budget optimizer mid-search мог продолжать после _PROJECT_DB.close()
    # → SQLite use-after-free risk. Same cooperative cancel-flag + join pattern.
    optimize_handles = list(_optimize_threads.keys())
    for ohandle in optimize_handles:
        oflag = _optimize_cancel_flags.get(ohandle)
        if oflag is not None:
            oflag.set()
    for ohandle in optimize_handles:
        othread = _optimize_threads.get(ohandle)
        if othread is not None:
            othread.join(timeout=_SHUTDOWN_PER_FORECAST_TIMEOUT_S)

    # Stop periodic GC thread (S-07).
    _GC_STOP_EVENT.set()
    global _GC_THREAD  # noqa: PLW0603
    with _GC_THREAD_LOCK:
        if _GC_THREAD is not None and _GC_THREAD.is_alive():
            _GC_THREAD.join(timeout=10.0)
        _GC_THREAD = None

    # Close AutosaveManager singleton (cancels timers, clears session marker).
    # Audit A-05 fix: explicit shutdown path so SIGTERM handler isn't only
    # exit path. Idempotent — if shutdown() already ran, this is a no-op.
    global _AUTOSAVE  # noqa: PLW0603
    with _AUTOSAVE_LOCK:
        if _AUTOSAVE is not None:
            try:
                _AUTOSAVE.shutdown()
            except Exception as exc:  # noqa: BLE001
                import logging as _logging

                _logging.getLogger(__name__).warning("AutosaveManager shutdown raised: %s", exc)
            _AUTOSAVE = None

    # Close ProjectDB singleton so WAL checkpoint + file locks release cleanly.
    global _PROJECT_DB  # noqa: PLW0603
    with _PROJECT_DB_LOCK:
        if _PROJECT_DB is not None:
            try:
                _PROJECT_DB.close()
            except Exception as exc:  # noqa: BLE001
                import logging as _logging

                _logging.getLogger(__name__).warning(
                    "ProjectDB close during shutdown raised: %s", exc
                )
            _PROJECT_DB = None

    # Clear the DI container so it doesn't hold stale references to the
    # now-closed DB / AutosaveManager after shutdown.  This mirrors the
    # module-level var reset above and lets tests re-init cleanly.
    get_services().clear()

    return {
        "shutting_down": True,
        "forecasts_signaled": forecasts_signaled,
        "forecasts_joined": forecasts_joined,
        "forecasts_timed_out": forecasts_timed_out,
    }


# ─── Late imports: trigger @register side-effects in feature modules ──────────
# These imports MUST come AFTER register() and all module-level singletons are
# defined, so that feature-module decorators can call register() successfully.
# Circular import is broken by the feature modules using late imports (inside
# functions) to access singletons defined here.

import aurora_launch.sidecar.methods_forecast  # noqa: E402, F401
import aurora_launch.sidecar.methods_project  # noqa: E402, F401
import aurora_launch.sidecar.methods_integrity  # noqa: E402, F401
import aurora_launch.sidecar.methods_consent  # noqa: E402, F401
import aurora_launch.sidecar.methods_cross_product  # noqa: E402, F401
import aurora_launch.sidecar.methods_license  # noqa: E402, F401  Phase 2.A

# Re-export symbols that external modules (server.py, tests) import from here
# for backward-compatibility with the pre-split layout.
from aurora_launch.sidecar.methods_project import UnsupportedFormatError  # noqa: E402, F401

# Audit H-4 (этап 2.10): регистрация reset callback должна произойти после
# определения _hard_reset_module_singletons (выше) и singletons _PROJECT_DB /
# _AUTOSAVE. Однократная регистрация, идемпотентна.
register_reset_callback(_hard_reset_module_singletons)
