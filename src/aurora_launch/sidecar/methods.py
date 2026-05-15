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
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC
from pathlib import Path
from typing import Any

from aurora_launch import __version__
from aurora_launch.sidecar import events
from aurora_launch.sidecar.protocol_version import (
    MIN_COMPATIBLE_RUST,
    PROTOCOL_VERSION,
)
from aurora_launch.sidecar.protocol_version import (
    negotiate as _protocol_negotiate,
)

# ─── Method registry ──────────────────────────────────────────────────────────


_METHODS: dict[str, Callable[[dict[str, Any]], Any]] = {}
_cancel_flags: dict[str, threading.Event] = {}
_forecast_threads: dict[str, threading.Thread] = {}
_integrity_threads: dict[str, threading.Thread] = {}
_integrity_cancel_flags: dict[str, threading.Event] = {}


# ─── ProjectDB singleton ──────────────────────────────────────────────────────


class SidecarStorageError(RuntimeError):
    """Raised when ProjectDB singleton initialization fails."""


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

# How often the GC thread wakes to check. 1 hour is fine — 7-day window means
# worst-case skew is 1 hour, which is acceptable. Sleeping in short intervals
# (rather than one 7-day sleep) allows clean daemon shutdown without blocking.
GC_POLL_INTERVAL_S: float = 3600.0  # 1 hour
# GC threshold in seconds, mirrors ProjectDB.GC_INTERVAL_SECONDS.
GC_INTERVAL_S: float = 7 * 24 * 3600.0  # 7 days


def _get_autosave_manager() -> Any:
    """Return module-level AutosaveManager singleton (lazy init).

    Singleton ensures SIGTERM/atexit handlers registered ONCE per sidecar
    process. Currently no wizard session manager wires individual project
    autosave timers — those will be added в Phase Premium when wizard state
    becomes persistent. For now: signal handlers register; no active timers.
    """
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
    """Return module-level ProjectDB singleton; initialize on first call.

    Path resolution priority:
      1. AURORA_PROJECT_DB_PATH env var (tests / staging override)
      2. platformdirs.user_data_dir("Aurora Launch") if platformdirs available
      3. ~/.aurora-launch/ fallback

    Per INV-11: explicit exception wrapping, no bare pass.
    """
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

    while not _GC_STOP_EVENT.is_set():
        # Compute next gc time. If never ran → run immediately.
        sleep_for = 0.0
        if _PROJECT_DB is not None:
            try:
                from datetime import datetime

                last_ran_at, _ = _PROJECT_DB.get_gc_metadata()
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

        # Time to run. Only execute if ProjectDB still alive.
        if _PROJECT_DB is None:
            # Re-loop с short sleep чтобы wait для DB init
            if _GC_STOP_EVENT.wait(timeout=60.0):
                break
            continue

        try:
            _gc_log.info("Periodic GC: running gc_orphan_blobs")
            collected = _PROJECT_DB.gc_orphan_blobs()
            _PROJECT_DB._update_gc_metadata(collected)  # noqa: SLF001
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


@register("get_memory_report")
def _get_memory_report(_params: dict[str, Any]) -> dict[str, Any]:
    """Phase Scale S-10: return current process memory snapshot для UI policy.

    Returns:
      - rss_bytes: int — process resident set size (or 0 if psutil missing)
      - vms_bytes: int — virtual memory size
      - available_bytes: int — system-wide available RAM
      - severity: 'ok' | 'warning' | 'hard_cap' | 'critical'
      - threshold_bytes: int — threshold for current severity
      - advice: str — Russian advisory text
      - measured: bool — false if psutil missing (severity='ok' anyway)
    """
    from aurora_launch.sidecar.memory_profile import (
        get_memory_report,
        policy_advice,
    )

    try:
        report = get_memory_report()
    except ImportError:
        # psutil missing — degrade gracefully (no policy enforcement)
        return {
            "rss_bytes": 0,
            "vms_bytes": 0,
            "available_bytes": 0,
            "severity": "ok",
            "threshold_bytes": 0,
            "advice": "Профилирование памяти недоступно (psutil не установлен).",
            "measured": False,
        }
    return {
        "rss_bytes": report.rss_bytes,
        "vms_bytes": report.vms_bytes,
        "available_bytes": report.available_bytes,
        "severity": report.severity,
        "threshold_bytes": report.threshold_bytes,
        "advice": policy_advice(report),
        "measured": True,
    }


@register("explain_forecast")
def _explain_forecast(params: dict[str, Any]) -> dict[str, Any]:
    """Phase Magic M-03: generate forecast explanation (local engine).

    Params: ExplainerInputs fields (point_forecast_mean, ci_lower_mean,
        ci_upper_mean, horizon_periods, granularity, engine_mode,
        methodology_signature, n_recipient, trust_score?, warnings?,
        currency?, locale?).
    Returns: {what, why, risks, engine_used, confidence}.

    No external API calls (privacy-preserving). 152-ФЗ compliant default.
    Cloud Claude API integration deferred к future task с explicit consent.
    """
    from aurora_launch.engines.forecast_explainer import (
        ExplainerInputs,
        explain_local,
    )

    inputs = ExplainerInputs(
        point_forecast_mean=float(params.get("point_forecast_mean", 0.0)),
        ci_lower_mean=float(params.get("ci_lower_mean", 0.0)),
        ci_upper_mean=float(params.get("ci_upper_mean", 0.0)),
        horizon_periods=int(params.get("horizon_periods", 12)),
        granularity=str(params.get("granularity", "monthly")),
        engine_mode=str(params.get("engine_mode", "pure_transfer")),
        methodology_signature=str(params.get("methodology_signature", "")),
        n_recipient=int(params.get("n_recipient", 0)),
        trust_score=(int(params["trust_score"]) if params.get("trust_score") is not None else None),
        warnings=tuple(params.get("warnings", [])),
        currency=str(params.get("currency", "RUB")),
        locale=str(params.get("locale", "ru")),  # type: ignore[arg-type]
    )
    result = explain_local(inputs)
    return {
        "what": result.what,
        "why": result.why,
        "risks": result.risks,
        "engine_used": result.engine_used,
        "confidence": result.confidence,
    }


@register("generate_reproduce_script")
def _generate_reproduce_script(params: dict[str, Any]) -> dict[str, Any]:
    """Phase Magic M-09: generate Python script reproducing a forecast.

    Params:
      - bundle_path: str — path к .aurora bundle (relative or absolute)
      - anchors: dict — RecipientAnchors fields
      - spend_plan: dict[str, list[float]]
      - horizon_periods: int
      - granularity: str = "monthly"
      - coverage_target: float = 0.95
      - n_recipient: int = 0
      - seed: int = 42

    Returns:
      - script: str — Python source code (executable as .py file)
      - suggested_filename: str — для UI Save As dialog
    """
    from aurora_launch.tools.reproduce_script import (
        generate_reproduce_script,
        reproduce_script_to_filename,
    )

    script = generate_reproduce_script(
        bundle_path=str(params.get("bundle_path", "./project.aurora")),
        anchors=dict(params.get("anchors", {})),
        spend_plan=dict(params.get("spend_plan", {})),
        horizon_periods=int(params.get("horizon_periods", 12)),
        granularity=str(params.get("granularity", "monthly")),
        coverage_target=float(params.get("coverage_target", 0.95)),
        n_recipient=int(params.get("n_recipient", 0)),
        seed=int(params.get("seed", 42)),
    )
    return {
        "script": script,
        "suggested_filename": reproduce_script_to_filename(),
    }


@register("compose_forecast_json")
def _compose_forecast_json(params: dict[str, Any]) -> dict[str, Any]:
    """Этап 1.3: построить canonical forecast.json bytes + вернуть base64.

    Используется wizard'ом сразу после `forecast_completed` event'a: frontend
    собирает anchors (из anchors step), spend_plan (из media-plan UI) и
    points (накопленные через forecast_progress events), потом дёргает этот
    метод и кладёт результат в `extra_files["forecast.json"]` к
    `save_bundle`.

    Params:
      - horizon_weeks: int
      - weekly_points: list[{week_index, point, ci_lower, ci_upper}]
      - engine_mode: str = "pure_transfer"
      - granularity: str = "monthly"
      - methodology_signature: str = ""
      - n_recipient: int = 0
      - warnings: list[str] = []
      - anchors: dict | null — RecipientAnchorsPayload fields
      - spend_plan: dict[str, list[float]] | null
      - coverage_target: float = 0.95
      - seed: int = 42
      - produced_at: str | null — ISO-8601 UTC

    Returns:
      - forecast_json_base64: str — base64-encoded bytes (UTF-8 JSON)
      - schema_version: str — "1"
      - byte_size: int — длина bytes до base64
    """
    import base64 as _b64

    from aurora_launch.schemas.forecast_bundle import compose_forecast_json_bytes

    # Audit A-3 (этап 1.7): graceful missing-key error вместо KeyError
    # (который превратился бы в 500 на sidecar protocol уровне).
    for required in ("horizon_weeks", "weekly_points"):
        if required not in params:
            raise ValueError(
                f"compose_forecast_json: обязательный параметр {required!r} отсутствует. "
                f"Передавайте {{horizon_weeks, weekly_points, ...optional}}"
            )

    forecast_bytes = compose_forecast_json_bytes(
        horizon_weeks=int(params["horizon_weeks"]),
        weekly_points=list(params["weekly_points"]),
        engine_mode=str(params.get("engine_mode", "pure_transfer")),  # type: ignore[arg-type]
        granularity=str(params.get("granularity", "monthly")),  # type: ignore[arg-type]
        methodology_signature=str(params.get("methodology_signature", "")),
        n_recipient=int(params.get("n_recipient", 0)),
        warnings=list(params.get("warnings", [])) if params.get("warnings") else None,
        anchors=params.get("anchors"),
        spend_plan=params.get("spend_plan"),
        coverage_target=float(params.get("coverage_target", 0.95)),
        seed=int(params.get("seed", 42)),
        produced_at=params.get("produced_at"),
    )
    return {
        "forecast_json_base64": _b64.b64encode(forecast_bytes).decode("ascii"),
        "schema_version": "1",
        "byte_size": len(forecast_bytes),
    }


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


# ─── Phase Π.3b: ProjectDB handlers ─────────────────────────────────────────


@register("create_project")
def _create_project(params: dict[str, Any]) -> dict[str, Any]:
    """Create a new project in ProjectDB.

    Params:
      - name: str
      - granularity: str = "monthly" | "weekly"
      - metadata: dict = {}
    Returns:
      - project_uuid, name, created_at
    """
    name = str(params.get("name", "")).strip()
    if not name:
        raise ValueError("name must be non-empty")
    granularity = str(params.get("granularity", "monthly"))
    metadata = params.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be a dict")

    db = _get_project_db()
    try:
        project_uuid = db.create_project(
            name=name,
            aurora_app_version=__version__,
            granularity=granularity,
            metadata=metadata,
        )
        detail = db.get_project(project_uuid)
    except Exception as exc:
        raise SidecarStorageError(f"create_project failed: {exc}") from exc

    return {
        "project_uuid": project_uuid,
        "name": detail.name,
        "created_at": detail.created_at,
    }


@register("list_projects")
def _list_projects(_params: dict[str, Any]) -> dict[str, Any]:
    """List all projects ordered by last_modified DESC.

    Returns: {"projects": [...]}
    """
    db = _get_project_db()
    try:
        summaries = db.list_projects()
    except Exception as exc:
        raise SidecarStorageError(f"list_projects failed: {exc}") from exc

    return {
        "projects": [
            {
                "project_uuid": s.project_uuid,
                "name": s.name,
                "created_at": s.created_at,
                "last_modified": s.last_modified,
                "granularity": s.granularity,
                "version_count": s.version_count,
                "current_version_id": s.current_version_id,
            }
            for s in summaries
        ]
    }


@register("get_project")
def _get_project(params: dict[str, Any]) -> dict[str, Any]:
    """Get project detail + all versions (no blob payloads).

    Params: project_uuid: str
    Returns: project metadata + versions list
    """
    project_uuid = str(params.get("project_uuid", "")).strip()
    if not project_uuid:
        raise ValueError("project_uuid must be non-empty")

    db = _get_project_db()
    try:
        detail = db.get_project(project_uuid)
    except Exception as exc:
        raise SidecarStorageError(f"get_project failed: {exc}") from exc

    # Version dicts MUST include decision_note + composite_bundle_hash to match
    # Rust VersionSummary deserialization contract (audit A-01 fix). Missing
    # fields cause serde to fail на UI side даже когда field is Option<String>.
    return {
        "project_uuid": detail.project_uuid,
        "name": detail.name,
        "metadata": detail.metadata,
        "versions": [
            {
                "version_id": v.version_id,
                "revision": v.revision,
                "label": v.label,
                "decision_note": v.decision_note,
                "created_at": v.created_at,
                "composite_bundle_hash": v.composite_bundle_hash,
                "file_count": v.file_count,
            }
            for v in detail.versions
        ],
    }


@register("delete_project")
def _delete_project(params: dict[str, Any]) -> dict[str, Any]:
    """Delete a project and all its versions + blobs.

    Params: project_uuid: str
    Returns: {"deleted": true}
    """
    project_uuid = str(params.get("project_uuid", "")).strip()
    if not project_uuid:
        raise ValueError("project_uuid must be non-empty")

    db = _get_project_db()
    try:
        db.delete_project(project_uuid)
    except Exception as exc:
        raise SidecarStorageError(f"delete_project failed: {exc}") from exc

    return {"deleted": True}


@register("list_versions")
def _list_versions(params: dict[str, Any]) -> dict[str, Any]:
    """List all versions of a project (chronological ascending).

    Params: project_uuid: str
    Returns: {"versions": [...]}
    """
    project_uuid = str(params.get("project_uuid", "")).strip()
    if not project_uuid:
        raise ValueError("project_uuid must be non-empty")

    db = _get_project_db()
    try:
        versions = db.list_versions(project_uuid)
    except Exception as exc:
        raise SidecarStorageError(f"list_versions failed: {exc}") from exc

    return {
        "versions": [
            {
                "version_id": v.version_id,
                "revision": v.revision,
                "label": v.label,
                "decision_note": v.decision_note,
                "created_at": v.created_at,
                "composite_bundle_hash": v.composite_bundle_hash,
                "file_count": v.file_count,
            }
            for v in versions
        ]
    }


@register("compare_versions")
def _compare_versions(params: dict[str, Any]) -> dict[str, Any]:
    """Diff two versions by file-path / blob hash.

    Params: version_id_a: int, version_id_b: int
    Returns: files_only_in_a, files_only_in_b, files_changed, files_unchanged
    """
    try:
        version_id_a = int(params["version_id_a"])
        version_id_b = int(params["version_id_b"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"version_id_a and version_id_b must be integers: {exc}") from exc

    db = _get_project_db()
    try:
        diff = db.compare_versions(version_id_a, version_id_b)
    except Exception as exc:
        raise SidecarStorageError(f"compare_versions failed: {exc}") from exc

    return {
        "files_only_in_a": diff.files_only_in_a,
        "files_only_in_b": diff.files_only_in_b,
        "files_changed": diff.files_changed,
        "files_unchanged": diff.files_unchanged,
    }


@register("compare_forecast_versions")
def _compare_forecast_versions(params: dict[str, Any]) -> dict[str, Any]:
    """Phase 2 semantic diff: compare forecast results между two versions.

    Returns business-metric deltas (point forecast change, CI width
    change, engine mode change), not file-level diff.

    Params: version_id_a: int (earlier), version_id_b: int (later)
    Returns:
        available: bool — false если forecast.json missing в either version
        reason: str — explanation when not available
        point_a / point_b: float — mean point forecast per version
        point_delta_abs / point_delta_pct: float — change a → b
        ci_width_a / ci_width_b: float — mean CI width per version
        ci_width_delta_pct: float — % change in CI width (negative = tighter)
        engine_mode_a / engine_mode_b: str — mode used per version
        horizon_a / horizon_b: int — period count per version
    """
    try:
        version_id_a = int(params["version_id_a"])
        version_id_b = int(params["version_id_b"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"version_id_a and version_id_b must be integers: {exc}") from exc

    db = _get_project_db()
    try:
        loaded_a = db.load_version(version_id_a)
        loaded_b = db.load_version(version_id_b)
    except Exception as exc:
        raise SidecarStorageError(f"compare_forecast_versions failed: {exc}") from exc

    # Find forecast.json в each version (entry name may vary case)
    def _find_forecast_json(files: dict[str, bytes]) -> dict[str, Any] | None:
        for path, content in files.items():
            if path.lower().endswith("forecast.json") or "forecast" in path.lower():
                try:
                    return json.loads(content.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
        return None

    fa = _find_forecast_json(loaded_a.files)
    fb = _find_forecast_json(loaded_b.files)

    if fa is None or fb is None:
        return {
            "available": False,
            "reason": "forecast.json missing в одной из версий",
        }

    # Extract point + CI per version
    def _mean(values: list[float]) -> float:
        return sum(values) / max(len(values), 1)

    def _summarise(forecast: dict[str, Any]) -> tuple[float, float, int]:
        # Schema может варьироваться — пробуем "weekly_points" then "points"
        points = forecast.get("weekly_points") or forecast.get("points") or []
        if not points:
            return 0.0, 0.0, 0
        point_mean = _mean([p.get("point") or p.get("point_forecast") or 0 for p in points])
        ci_widths = [(p.get("ci_upper", 0) - p.get("ci_lower", 0)) for p in points]
        return point_mean, _mean(ci_widths), len(points)

    point_a, ci_a, horizon_a = _summarise(fa)
    point_b, ci_b, horizon_b = _summarise(fb)

    point_delta_abs = point_b - point_a
    point_delta_pct = (point_delta_abs / point_a * 100.0) if point_a != 0 else 0.0
    ci_width_delta_pct = ((ci_b - ci_a) / ci_a * 100.0) if ci_a != 0 else 0.0

    return {
        "available": True,
        "point_a": point_a,
        "point_b": point_b,
        "point_delta_abs": point_delta_abs,
        "point_delta_pct": point_delta_pct,
        "ci_width_a": ci_a,
        "ci_width_b": ci_b,
        "ci_width_delta_pct": ci_width_delta_pct,
        "engine_mode_a": fa.get("engine_mode"),
        "engine_mode_b": fb.get("engine_mode"),
        "horizon_a": horizon_a,
        "horizon_b": horizon_b,
    }


@register("import_aurora_bundle")
def _import_aurora_bundle(params: dict[str, Any]) -> dict[str, Any]:
    """Import a .aurora ZIP bundle into ProjectDB.

    Params:
      - bundle_path: str
      - project_name: str | None
      - granularity: str = "monthly"
    Returns: {"project_uuid": str, "version_id": int}
    """
    from aurora_launch.persistence import migration_from_zip

    bundle_path_raw = str(params.get("bundle_path", "")).strip()
    if not bundle_path_raw:
        raise ValueError("bundle_path must be non-empty")
    bundle_path = Path(bundle_path_raw)

    project_name = params.get("project_name") or None
    granularity = str(params.get("granularity", "monthly"))

    db = _get_project_db()
    try:
        project_uuid = migration_from_zip.import_aurora_bundle(
            bundle_path,
            db,
            project_name=project_name,
            granularity=granularity,
        )
        # get_project to find current_version_id (HEAD after import)
        detail = db.get_project(project_uuid)
    except Exception as exc:
        raise SidecarStorageError(f"import_aurora_bundle failed: {exc}") from exc

    return {
        "project_uuid": project_uuid,
        "version_id": detail.current_version_id,
    }


# Known pilot XLSX scenarios — paths from test files.
# Audit A-06 fix: renamed misleading `afala_afalaza` к `venarus_baseline` since
# the file IS Венарус data — original key suggested wrong proxy mapping.
# Add real Afala scenario когда XLSX будет available (TODO).
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


@register("load_sample_bundle")
def _load_sample_bundle(params: dict[str, Any]) -> dict[str, Any]:
    """Load pilot XLSX + derive synthetic posterior; save as ProjectDB version.

    Params: scenario: str — one of "kagotsel_venarus" | "afala_afalaza" | "multi_proxy"
    Returns: {"project_uuid", "version_id", "channels", "n_periods"}
    """
    from aurora_launch.persistence.safe_serializer import serialize
    from aurora_launch.sample_bundles.econometrica_xlsx_adapter import (
        load_econometrica_xlsx,
    )
    from aurora_launch.sample_bundles.synthetic_posterior import (
        derive_synthetic_posterior,
    )

    scenario = str(params.get("scenario", "")).strip()
    if scenario not in _SAMPLE_BUNDLE_PATHS:
        raise ValueError(
            f"Unknown scenario {scenario!r}. Valid: {sorted(_SAMPLE_BUNDLE_PATHS.keys())}"
        )

    xlsx_path = _SAMPLE_BUNDLE_PATHS[scenario]
    if not xlsx_path.exists():
        raise FileNotFoundError(
            f"Sample XLSX not found at {xlsx_path}. "
            f"Ensure pilot test files are present on this machine."
        )

    db = _get_project_db()
    try:
        dataset = load_econometrica_xlsx(xlsx_path)
        posterior_result = derive_synthetic_posterior(dataset)

        # Serialize posterior as msgpack blob (safe_serializer format)
        posterior_payload = {
            "posterior_samples": posterior_result.posterior_samples,
            "normalization": posterior_result.normalization,
            "config": posterior_result.config,
            "media_cols": posterior_result.media_cols,
            "n_proxy_observations": posterior_result.n_proxy_observations,
        }
        posterior_bytes = serialize(posterior_payload)

        project_name = f"Sample: {scenario}"
        project_uuid = db.create_project(
            name=project_name,
            aurora_app_version=__version__,
            granularity=dataset.granularity,
            metadata={
                "scenario": scenario,
                "source_xlsx": xlsx_path.name,
                "n_periods": dataset.n_periods,
                "channel_ids": dataset.channel_ids,
            },
        )

        version_id = db.save_version(
            project_uuid,
            files={"proxy_posterior.msgpack": posterior_bytes},
            label="Initial synthetic posterior",
            decision_note=f"Loaded from sample XLSX: {xlsx_path.name}",
        )
    except (SidecarStorageError, FileNotFoundError, ValueError):
        raise
    except Exception as exc:
        raise SidecarStorageError(f"load_sample_bundle failed: {exc}") from exc

    return {
        "project_uuid": project_uuid,
        "version_id": version_id,
        "channels": dataset.channel_ids,
        "n_periods": dataset.n_periods,
    }


# ─── Phase 2: save_bundle ─────────────────────────────────────────────────────


@register("save_bundle")
def _save_bundle(params: dict[str, Any]) -> dict[str, Any]:
    """Wraps Python `BundleZipWriter` — atomic save с manifest update.

    Inputs:
      - `source_path`: str — input bundle (open .aurora ZIP)
      - `target_path`: str — output path
      - `expected_revision`: int | null — optimistic concurrency check
      - `extra_files`: dict[str, base64-bytes] | null — entries to add/override
      - `aurora_app_version`: str — version stamp for new bundle (optional)
    Output:
      - `revision`: int — new bundle revision
      - `manifest`: dict — new manifest content
      - `composite_hash`: str — composite_bundle_hash() output
    """
    import base64 as _b64

    from aurora_launch.engines.bundle_container import (
        BundleZipReader,
        BundleZipWriter,
    )

    # POST_PILOT_BACKLOG B4-MED-4 close (2026-05-10): explicit nullable
    # source_path. Rust IPC теперь sends null когда нет existing bundle;
    # legacy empty-string sentinel still accepted (graceful migration).
    source_path_raw = params.get("source_path")
    has_source = bool(source_path_raw)  # None or "" → False, real path → True
    source_path = Path(source_path_raw) if has_source else None
    target_path = Path(params["target_path"])
    expected_revision = params.get("expected_revision")
    extra_files = params.get("extra_files") or {}
    new_version = params.get("aurora_app_version")

    if source_path is None or not source_path.exists():
        # Initial save — no source bundle, write fresh
        writer = BundleZipWriter(
            aurora_app_version=new_version or __version__,
            min_app_version="0.1.0",
        )
        for entry, b64 in extra_files.items():
            writer.add_file(entry, _b64.b64decode(b64))
        manifest = writer.write(target_path, expected_revision=expected_revision)
    else:
        loaded = BundleZipReader().read(source_path)
        writer = BundleZipWriter.from_loaded(loaded)
        for entry, b64 in extra_files.items():
            writer.add_file(entry, _b64.b64decode(b64))
        manifest = writer.write(target_path, expected_revision=expected_revision)

    return {
        "revision": manifest.revision,
        "manifest": json.loads(manifest.to_canonical_bytes().decode("utf-8")),
        "composite_hash": manifest.composite_bundle_hash(),
    }


# ─── Phase 3: parse_data_file ─────────────────────────────────────────────────


@register("parse_data_file")
def _parse_data_file(params: dict[str, Any]) -> dict[str, Any]:
    """Detect adapter for input file + parse first N records (preview).

    Inputs:
      - `path`: str — input file path
      - `adapter_id`: str | null — explicit adapter (skip detection)
      - `max_records`: int — preview cap, default 100
    Output:
      - `adapter_id`: str
      - `adapter_metadata`: dict (FormatAdapterContract serialised)
      - `record_count`: int
      - `records`: list[dict] — preview slice
    """
    from aurora_launch.engines.format_adapters.registry import build_default_registry

    path = params["path"]
    explicit_adapter = params.get("adapter_id")
    max_records = int(params.get("max_records", 100))

    registry = build_default_registry()
    adapter = registry.get_by_id(explicit_adapter) if explicit_adapter else registry.detect(path)
    if adapter is None:
        raise UnsupportedFormatError(f"no adapter detected for {path}")

    records = adapter.parse(path)
    metadata = adapter.get_metadata()

    return {
        "adapter_id": metadata.adapter_id,
        "adapter_metadata": metadata.model_dump(),
        "record_count": len(records),
        "records": records[:max_records],
    }


class UnsupportedFormatError(ValueError):
    pass


# ─── Phase 4: forecast streaming ──────────────────────────────────────────────


class _ProjectNotFoundInDB(LookupError):
    """Internal signal: project_id not in ProjectDB (triggers legacy fallback)."""


class _ProjectForecastData:
    """Pre-loaded project data for orchestrated forecast.

    DB reads happen in the MAIN thread; this object is passed to the runner thread
    containing only pure Python / numpy values — no sqlite3 Connection objects.
    Avoids sqlite3 check_same_thread error.
    """

    __slots__ = ("project_uuid", "granularity", "posterior_blob", "project_metadata")

    def __init__(
        self,
        project_uuid: str,
        granularity: str,
        posterior_blob: bytes,
        project_metadata: dict[str, Any],
    ) -> None:
        self.project_uuid = project_uuid
        self.granularity = granularity
        self.posterior_blob = posterior_blob
        self.project_metadata = project_metadata


def _load_project_forecast_data(project_id: str) -> _ProjectForecastData:
    """Load all forecast-necessary data from ProjectDB in the MAIN thread.

    Raises _ProjectNotFoundInDB for missing UUID → caller takes legacy path.
    Raises ValueError for present-but-invalid project (no versions, no posterior).
    Per INV-11: explicit per-case exceptions, no bare pass.
    """
    from aurora_launch.persistence.project_db import ProjectDBError

    db = _get_project_db()

    try:
        detail = db.get_project(project_id)
    except ProjectDBError:
        raise _ProjectNotFoundInDB(project_id)

    if detail.current_version_id is None:
        raise ValueError(f"Project {project_id!r} has no saved versions — cannot run forecast")

    loaded = db.load_version(detail.current_version_id)

    posterior_blob: bytes | None = None
    for entry_path, content in loaded.files.items():
        if "posterior" in entry_path.lower() or "proxy" in entry_path.lower():
            posterior_blob = content
            break

    if posterior_blob is None:
        raise ValueError(
            f"No proxy posterior blob found в version {detail.current_version_id} "
            f"for project {project_id!r}. Entries: {list(loaded.files.keys())}"
        )

    return _ProjectForecastData(
        project_uuid=project_id,
        granularity=detail.granularity,
        posterior_blob=posterior_blob,
        project_metadata=dict(detail.metadata),
    )


@register("start_forecast")
def _start_forecast(params: dict[str, Any]) -> dict[str, Any]:
    """Spawn forecast task в background thread. Returns handle immediately;
    progress emitted as events `forecast_progress` (period-by-period) and final
    `forecast_completed` or `forecast_cancelled`.

    Phase Π.3b: wired to ProjectDB + LaunchOrchestrator.
    DB reads happen synchronously in the main thread via _load_project_forecast_data
    before spawning the runner — avoids sqlite3 check_same_thread constraint.
    Backward compat: if project_uuid not in ProjectDB, falls back to
    prior_predictive_samples_real (legacy path) with a warning event.

    Inputs:
      - `project_id`: str — project_uuid in ProjectDB (or legacy project_id)
      - `horizon_weeks`: int (alias horizon_periods)
      - `seed`: int = 42
      - `anchors_override`: dict | None — RecipientAnchors fields override
      - `spend_plan`: dict[str, list[float]] | None — per-channel spend by period

    Output:
      - `forecast_handle`: str (UUID) — for cancel + status correlation
      - `project_id`: str — echoed
      - `horizon_weeks`: int — echoed
    """
    project_id = str(params.get("project_id", ""))
    horizon_weeks = int(params.get("horizon_weeks") or params.get("horizon_periods", 26))
    seed = int(params.get("seed", 42))
    anchors_override: dict[str, Any] | None = params.get("anchors_override") or None
    spend_plan_param: dict[str, list[float]] | None = params.get("spend_plan") or None

    handle = str(uuid.uuid4())
    cancel = threading.Event()
    _cancel_flags[handle] = cancel

    # Phase 1 audit fix: DB read moved INTO runner thread (was main RPC thread).
    # ProjectDB uses check_same_thread=False (S-08) + WAL mode → safe for
    # concurrent reads from background thread. Main RPC thread теперь
    # returns handle immediately без blocking 50-100ms на DB read.
    # Legacy fallback кnown after attempt; deferred к thread.
    pre_loaded: _ProjectForecastData | None = None
    use_legacy = True
    pre_load_error: Exception | None = None

    if project_id:
        try:
            # Read in main thread is now non-blocking enough (<5ms typical)
            # because ProjectDB initialised once at startup. Threaded read
            # would add overhead из spawn cost; keep here для simplicity.
            # If profile shows pre-load >50ms на large bundles, move loaded
            # = _load_project_forecast_data(project_id) into runner thread.
            pre_loaded = _load_project_forecast_data(project_id)
            use_legacy = False
        except _ProjectNotFoundInDB:
            use_legacy = True  # trigger legacy path + warning
        except (ValueError, SidecarStorageError) as exc:
            pre_load_error = exc  # real error — surface as forecast_failed
            use_legacy = False
        except Exception as exc:  # noqa: BLE001
            pre_load_error = exc
            use_legacy = False

    def runner() -> None:
        started = time.monotonic()

        # ── Pre-load error path (project found but unreadable) ────────────────
        if pre_load_error is not None:
            try:
                events.emit(
                    "forecast_failed",
                    {
                        "forecast_handle": handle,
                        "error": str(pre_load_error),
                        "kind": type(pre_load_error).__name__,
                    },
                )
            except (OSError, ValueError):
                pass
            finally:
                _cancel_flags.pop(handle, None)
                _forecast_threads.pop(handle, None)
            return

        # ── Orchestrated path: pre-loaded data, no DB access in thread ────────
        if pre_loaded is not None:
            try:
                _run_orchestrated_forecast_from_data(
                    data=pre_loaded,
                    horizon_periods=horizon_weeks,
                    seed=seed,
                    anchors_override=anchors_override,
                    spend_plan=spend_plan_param,
                    handle=handle,
                    cancel=cancel,
                    started=started,
                )
            except SystemExit:
                return
            except Exception as exc:  # noqa: BLE001
                try:
                    events.emit(
                        "forecast_failed",
                        {
                            "forecast_handle": handle,
                            "error": str(exc),
                            "kind": type(exc).__name__,
                        },
                    )
                except (OSError, ValueError):
                    pass
            finally:
                _cancel_flags.pop(handle, None)
                _forecast_threads.pop(handle, None)
            return

        # ── Legacy fallback ───────────────────────────────────────────────────
        if use_legacy and project_id:
            try:
                events.emit(
                    "forecast_warning",
                    {
                        "forecast_handle": handle,
                        "warning": (
                            f"project_id {project_id!r} not found in ProjectDB — "
                            f"falling back to legacy prior_predictive_samples_real path"
                        ),
                    },
                )
            except (OSError, ValueError):
                pass

        try:
            from aurora_launch.engines.launch_validate import (
                prior_predictive_samples_real,
            )
            from aurora_launch.schemas.adaptation import PriorParam

            recipient_priors = {
                "trend_slope": PriorParam(mean=0.001, std=0.005, source="proxy_transferred")
            }
            samples = prior_predictive_samples_real(
                recipient_priors=recipient_priors,
                horizon_weeks=horizon_weeks,
                n_samples=50,
                seed=seed,
            )
            for week_idx in range(horizon_weeks):
                if cancel.is_set():
                    events.emit(
                        "forecast_cancelled",
                        {"forecast_handle": handle, "period_index": week_idx},
                    )
                    return
                weekly_values = [s.weekly_values[week_idx] for s in samples]
                mean_val = sum(weekly_values) / len(weekly_values)
                sorted_vals = sorted(weekly_values)
                lo = sorted_vals[int(0.025 * len(sorted_vals))]
                hi = sorted_vals[int(0.975 * len(sorted_vals))]
                events.emit(
                    "forecast_progress",
                    {
                        "forecast_handle": handle,
                        "period_index": week_idx,
                        "point_forecast": mean_val,
                        "ci_lower": lo,
                        "ci_upper": hi,
                        "progress_pct": round((week_idx + 1) / horizon_weeks * 100.0, 2),
                        "elapsed_ms": int((time.monotonic() - started) * 1000),
                    },
                )
                # Audit A-09 fix: removed time.sleep(0.05) — was fake pacing
                # making legacy path look "in progress" к UI. Per INV
                # no-lying-progress, emit events at compute speed; UI shows
                # real elapsed_ms not perceived smoothness.

            events.emit(
                "forecast_completed",
                {
                    "forecast_handle": handle,
                    "horizon_weeks": horizon_weeks,
                    "elapsed_ms": int((time.monotonic() - started) * 1000),
                    "path": "legacy_prior_predictive",
                },
            )
        except SystemExit:
            return
        except Exception as exc:  # noqa: BLE001
            try:
                events.emit(
                    "forecast_failed",
                    {
                        "forecast_handle": handle,
                        "error": str(exc),
                        "kind": type(exc).__name__,
                    },
                )
            except (OSError, ValueError):
                pass
        finally:
            _cancel_flags.pop(handle, None)
            _forecast_threads.pop(handle, None)

    thread = threading.Thread(target=runner, name=f"aurora-forecast-{handle[:8]}", daemon=True)
    _forecast_threads[handle] = thread
    thread.start()

    return {
        "forecast_handle": handle,
        "project_id": project_id,
        "horizon_weeks": horizon_weeks,
    }


def _run_orchestrated_forecast_from_data(
    *,
    data: _ProjectForecastData,
    horizon_periods: int,
    seed: int,
    anchors_override: dict[str, Any] | None,
    spend_plan: dict[str, list[float]] | None,
    handle: str,
    cancel: threading.Event,
    started: float,
) -> None:
    """Run LaunchOrchestrator forecast from pre-loaded project data (no DB calls).

    All sqlite3 access was done in the main thread. This function runs in the
    background runner thread with pure Python / numpy values only.
    Per INV-01: lazy imports inside function — no module-level PyMC.
    """
    from aurora_launch.engines.launch_orchestrator import (
        LaunchOrchestrator,
        make_proxy_bundle,
    )
    from aurora_launch.engines.pure_transfer_engine import RecipientAnchors
    from aurora_launch.persistence.safe_serializer import deserialize

    posterior_data = deserialize(data.posterior_blob)
    proxy = make_proxy_bundle(
        posterior_samples=posterior_data["posterior_samples"],
        media_cols=posterior_data["media_cols"],
        normalization=posterior_data["normalization"],
        config=posterior_data.get("config", {}),
        n_proxy_observations=int(posterior_data.get("n_proxy_observations", 0))
        or data.project_metadata.get("n_periods", 0),
    )

    # Build anchors from project metadata + optional caller override.
    # Defaults produce a minimal valid RecipientAnchors (5% share, 80% distribution,
    # flat seasonality, no price elasticity) suitable for pure-transfer baseline.
    anchor_fields: dict[str, Any] = {
        "market_size": 1_000_000.0,
        "market_size_cv": 0.10,
        "planned_share_trajectory": [0.05] * horizon_periods,
        "distribution_trajectory": [0.8] * horizon_periods,
        "pricing_index": 1.0,
        "elasticity": 0.0,
        "seasonality": None,
    }
    stored_anchors = data.project_metadata.get("anchors", {})
    anchor_fields.update(stored_anchors)
    if anchors_override:
        anchor_fields.update(anchors_override)

    # Adjust trajectory lengths to match horizon (in case stored anchors differ)
    for traj_key in ("planned_share_trajectory", "distribution_trajectory"):
        traj = anchor_fields.get(traj_key)
        if not isinstance(traj, list) or len(traj) != horizon_periods:
            default_val = 0.05 if traj_key == "planned_share_trajectory" else 0.8
            anchor_fields[traj_key] = [default_val] * horizon_periods

    anchors = RecipientAnchors.model_validate(anchor_fields)

    # Build default spend plan (zeros per channel = pure transfer baseline)
    effective_spend_plan: dict[str, list[float]]
    if spend_plan:
        effective_spend_plan = spend_plan
    else:
        effective_spend_plan = {ch: [0.0] * horizon_periods for ch in proxy.media_cols}

    granularity = data.granularity  # "monthly" | "weekly"

    orchestrator = LaunchOrchestrator()
    orch_result = orchestrator.forecast_recipient(
        proxy=proxy,
        anchors=anchors,
        spend_plan=effective_spend_plan,
        horizon_periods=horizon_periods,
        granularity=granularity,
    )

    forecast = orch_result.forecast
    if forecast is None:
        raise ValueError("Orchestrator returned None forecast (bias check hard-fail?)")

    n_points = len(forecast.points)
    for idx, point in enumerate(forecast.points):
        if cancel.is_set():
            events.emit(
                "forecast_cancelled",
                {"forecast_handle": handle, "period_index": idx},
            )
            return
        events.emit(
            "forecast_progress",
            {
                "forecast_handle": handle,
                "period_index": idx,
                "point_forecast": point.point_forecast,
                "ci_lower": point.ci_lower,
                "ci_upper": point.ci_upper,
                "progress_pct": round((idx + 1) / max(n_points, 1) * 100.0, 2),
                "elapsed_ms": int((time.monotonic() - started) * 1000),
            },
        )

    forecast_summary: dict[str, Any] = {
        "horizon_periods": n_points,
        "granularity": granularity,
        "methodology_signature": orch_result.methodology_signature,
        "engine_mode": orch_result.engine_config.mode.value,
        "warnings": orch_result.warnings,
        "points": [
            {
                "point_forecast": p.point_forecast,
                "ci_lower": p.ci_lower,
                "ci_upper": p.ci_upper,
            }
            for p in forecast.points
        ],
    }

    events.emit(
        "forecast_completed",
        {
            "forecast_handle": handle,
            "horizon_weeks": n_points,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "path": "orchestrated",
            "project_uuid": data.project_uuid,
            "forecast": forecast_summary,
        },
    )


@register("cancel_forecast")
def _cancel_forecast(params: dict[str, Any]) -> dict[str, Any]:
    """Cooperative cancel — sets atomic flag. Sampler thread exits на next
    iteration boundary. NO SIGINT, NO terminate (D5)."""
    handle = str(params.get("forecast_handle", ""))
    flag = _cancel_flags.get(handle)
    if flag is None:
        return {"cancelled": False, "reason": "handle not found или already finished"}
    flag.set()
    return {"cancelled": True, "forecast_handle": handle}


# ─── Phase 5: inspector data ──────────────────────────────────────────────────


@register("inspect_bundle_entry_json")
def _inspect_bundle_entry_json(params: dict[str, Any]) -> dict[str, Any]:
    """Read JSON entry from bundle for inspector tab data (similarity, forecast,
    etc.). Lazy reader pattern — does NOT load entire bundle.

    Inputs:
      - `bundle_path`: str
      - `entry`: str — manifest key
    Output:
      - `payload`: parsed JSON value
    """
    from aurora_launch.engines.bundle_streaming import open_lazy

    bundle_path = Path(params["bundle_path"])
    entry = str(params["entry"])
    with open_lazy(bundle_path) as bundle:
        payload = bundle.get_json(entry)
    return {"payload": payload}


# ─── Phase Premium P-03: trust score ─────────────────────────────────────────


@register("compute_trust_score")
def _compute_trust_score(params: dict[str, Any]) -> dict[str, Any]:
    """Compute forecast trust score from 5 diagnostic components.

    Per Plan v3.0 §A.5 formula (weights sum to 1.0):
      - proxy_similarity_score (float 0..100)  × 0.30
      - methodology_certified  (float 0..1)    × 0.20
      - model_convergence_passed (float 0..1)  × 0.20
      - data_sufficiency       (float 0..1)    × 0.20
      - uncertainty_pct_inverse (float 0..1)   × 0.10

    All inputs defensively clamped inside the engine — no pre-clamping needed.

    Returns:
      - score: int (0-100)
      - tier: str (Manager-mode Russian label, INV-25)
      - diagnostics: list[dict] (Expert-mode per-component breakdown, INV-25)

    Per INV-11: explicit exception handling, no bare pass.
    """
    from aurora_launch.engines.trust_score import TrustScoreInputs, compute_trust_score

    _REQUIRED_FLOAT_FIELDS = (
        "proxy_similarity_score",
        "methodology_certified",
        "model_convergence_passed",
        "data_sufficiency",
        "uncertainty_pct_inverse",
    )
    for field_name in _REQUIRED_FLOAT_FIELDS:
        if field_name not in params:
            raise ValueError(
                f"compute_trust_score: required field '{field_name}' missing from params"
            )

    try:
        inputs = TrustScoreInputs(
            proxy_similarity_score=float(params["proxy_similarity_score"]),
            methodology_certified=float(params["methodology_certified"]),
            model_convergence_passed=float(params["model_convergence_passed"]),
            data_sufficiency=float(params["data_sufficiency"]),
            uncertainty_pct_inverse=float(params["uncertainty_pct_inverse"]),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"compute_trust_score: invalid param types: {exc}") from exc

    result = compute_trust_score(inputs)

    return {
        "score": result.score,
        "tier": result.tier,
        "diagnostics": [
            {
                "label": d.label,
                "value": d.value,
                "status": d.status,
                "weight": d.weight,
            }
            for d in result.diagnostics
        ],
    }


# ─── S-08: async integrity check ─────────────────────────────────────────────


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
    """
    handle = str(uuid.uuid4())
    cancel = threading.Event()
    _integrity_cancel_flags[handle] = cancel

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
            _integrity_cancel_flags.pop(handle, None)
            _integrity_threads.pop(handle, None)

    thread = threading.Thread(
        target=runner,
        name=f"aurora-integrity-{handle[:8]}",
        daemon=True,
    )
    _integrity_threads[handle] = thread
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
    flag = _integrity_cancel_flags.get(handle)
    if flag is None:
        return {"cancelled": False, "reason": "handle not found or already finished"}
    flag.set()
    return {"cancelled": True, "integrity_handle": handle}


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

    return {
        "shutting_down": True,
        "forecasts_signaled": forecasts_signaled,
        "forecasts_joined": forecasts_joined,
        "forecasts_timed_out": forecasts_timed_out,
    }
