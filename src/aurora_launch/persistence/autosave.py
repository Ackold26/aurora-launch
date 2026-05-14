"""Autosave + crash recovery (Phase 0.2).

Provides safety net против customer data loss between explicit ProjectDB.save_version
calls. Captures working state каждые 30 секунд into rolling JSON delta files,
detects unclean exit on startup и offers recovery wizard.

Design (per plan v3.0 §A.7):
- Autosave granularity = JSON state (NOT pickle) — readable for inspect & recovery
- 30s interval — balance between data safety и I/O churn
- 3 rolling files (`<uuid>.autosave-1.json` newest, `-3.json` oldest)
- Atomic write (tmp + rename) — partial-write resilient
- Unclean-exit detection via session marker file
- Recovery wizard: presents autosave timestamps + "Restore" / "Discard" choices

Recovery flow:
1. On startup: AutosaveManager.detect_pending_recovery() returns list of
   project_uuids with un-claimed autosave files
2. UI shows recovery dialog: "Found unsaved work for N projects. Recover?"
3. On confirm: AutosaveManager.recover(uuid) → returns latest autosave state
4. On dismiss: AutosaveManager.discard(uuid) → cleans autosave files

Working state schema (autosave JSON):
{
    "project_uuid": "...",
    "session_id": "...",          // unique per app launch
    "saved_at": "ISO 8601 UTC",
    "version_seed_id": int | null,  // version_id last loaded; recovery rebases here
    "working_state": {            // arbitrary serializable working data
        "wizard_step": "ProxySelection",
        "anchors_form": {...},
        "selected_proxy_id": "...",
        // any UI-side state needed to resume
    },
}
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_log = logging.getLogger(__name__)

DEFAULT_AUTOSAVE_INTERVAL_S = 30.0
DEFAULT_ROLLING_COUNT = 3
AUTOSAVE_FILE_SUFFIX = ".autosave.json"
SESSION_MARKER_FILENAME = "session.lock"
MAX_RECOVERY_AGE_DAYS = 30  # autosaves older than this считаются stale


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@dataclass(frozen=True)
class AutosaveSnapshot:
    """A single autosave file's payload."""

    project_uuid: str
    session_id: str
    saved_at: str
    version_seed_id: int | None
    working_state: dict[str, Any]
    file_path: Path


@dataclass(frozen=True)
class PendingRecovery:
    """Unclean-exit recovery candidate for one project."""

    project_uuid: str
    most_recent_snapshot: AutosaveSnapshot
    all_snapshots: list[AutosaveSnapshot] = field(default_factory=list)
    is_stale: bool = False  # older than MAX_RECOVERY_AGE_DAYS


class AutosaveError(RuntimeError):
    """Raised for autosave failures (cannot write, corrupted file)."""


def _autosave_filename(project_uuid: str, slot: int) -> str:
    """slot=1 newest, slot=N oldest."""
    return f"{project_uuid}.autosave-{slot}{AUTOSAVE_FILE_SUFFIX}"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """JSON atomic write through tmp + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    try:
        with tmp.open("wb") as f:
            f.write(data)
            f.flush()
            try:
                os.fsync(f.fileno())
            except (OSError, AttributeError):
                pass
        os.replace(tmp, path)
    except OSError as exc:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError as cleanup_exc:
                _log.warning("Failed to cleanup tmp %s: %s", tmp, cleanup_exc)
        raise AutosaveError(f"Cannot write autosave {path}: {exc}") from exc


class AutosaveManager:
    """Coordinates per-project autosave + crash recovery.

    Lifecycle:
    1. App start: create AutosaveManager(autosave_dir, session_id=uuid)
    2. App start: pending = manager.detect_pending_recovery()
       UI offers recovery if pending != []
    3. Customer opens project: manager.start_autosave(project_uuid, state_provider)
    4. Background timer writes autosave каждые 30s
    5. Customer Save → manager.stop_autosave(project_uuid)
    6. App quit graceful: manager.shutdown() — clears session marker

    Crash detection:
    - On clean shutdown: session_marker file deleted
    - On crash: session_marker remains → next start detects orphan autosaves
      for the dead session_id и offers recovery

    Thread safety: timer thread accesses state via self._lock.
    """

    def __init__(
        self,
        autosave_dir: Path,
        *,
        session_id: str | None = None,
        interval_s: float = DEFAULT_AUTOSAVE_INTERVAL_S,
        rolling_count: int = DEFAULT_ROLLING_COUNT,
        register_signal_handlers: bool = False,
    ) -> None:
        self.autosave_dir = Path(autosave_dir)
        self.autosave_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id or str(uuid.uuid4())
        self.interval_s = float(interval_s)
        self.rolling_count = int(rolling_count)
        if self.rolling_count < 1:
            raise ValueError("rolling_count must be ≥ 1")

        # Session marker — presence on disk indicates ongoing session.
        # If next start finds it, previous shutdown was unclean.
        self._session_marker = self.autosave_dir / SESSION_MARKER_FILENAME
        self._write_session_marker()

        # Per-project state providers (callbacks returning current working state)
        self._providers: dict[str, Callable[[], tuple[int | None, dict[str, Any]]]] = {}
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()
        self._shutdown_flag = threading.Event()

        # S-05 audit fix: register signal handlers for graceful shutdown
        # (SIGTERM, SIGINT). Triggered atexit too. Without these, daemon
        # timer threads get killed mid-flight and session marker remains
        # as if crashed.
        if register_signal_handlers:
            self._install_signal_handlers()

    def _install_signal_handlers(self) -> None:
        """Register SIGTERM/SIGINT/atexit handlers для graceful flush."""
        import atexit
        import signal

        atexit.register(self.shutdown)
        # Only register signal handlers on main thread (signal module limitation).
        if threading.current_thread() is threading.main_thread():
            try:
                signal.signal(signal.SIGTERM, lambda _s, _f: self.shutdown())
                if hasattr(signal, "SIGINT"):
                    # SIGINT default raises KeyboardInterrupt — keep that behaviour
                    # but ensure we shutdown cleanly first via atexit.
                    pass  # atexit covers это
            except (ValueError, OSError) as exc:
                _log.warning("Cannot install signal handlers: %s", exc)

    # ---- session lifecycle -------------------------------------------------

    def _write_session_marker(self) -> None:
        payload = {
            "session_id": self.session_id,
            "started_at": _utc_now_iso(),
            "pid": os.getpid(),
        }
        try:
            _atomic_write_json(self._session_marker, payload)
        except AutosaveError as exc:
            _log.warning("Cannot write session marker: %s", exc)

    def _clear_session_marker(self) -> None:
        try:
            self._session_marker.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            _log.warning("Cannot clear session marker: %s", exc)

    def shutdown(self) -> None:
        """Graceful shutdown — cancel timers, clear session marker."""
        self._shutdown_flag.set()
        with self._lock:
            for timer in self._timers.values():
                timer.cancel()
            self._timers.clear()
            self._providers.clear()
        self._clear_session_marker()

    def __enter__(self) -> AutosaveManager:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.shutdown()

    # ---- per-project autosave control --------------------------------------

    def start_autosave(
        self,
        project_uuid: str,
        state_provider: Callable[[], tuple[int | None, dict[str, Any]]],
    ) -> None:
        """Register a state provider и start the timer for this project.

        state_provider returns (version_seed_id, working_state) каждый tick.
        Returning the same state two ticks in a row is fine — we still write
        (idempotent, latest timestamp wins on recovery).
        """
        with self._lock:
            if project_uuid in self._timers:
                # Replace existing — cancel old timer
                self._timers[project_uuid].cancel()
            self._providers[project_uuid] = state_provider
            self._schedule_next(project_uuid)

    def stop_autosave(self, project_uuid: str, *, discard: bool = False) -> None:
        """Stop autosave for project. If discard, deletes autosave files."""
        with self._lock:
            timer = self._timers.pop(project_uuid, None)
            if timer is not None:
                timer.cancel()
            self._providers.pop(project_uuid, None)
        if discard:
            self.discard(project_uuid)

    def _schedule_next(self, project_uuid: str) -> None:
        """Schedule next autosave tick (must hold self._lock)."""
        if self._shutdown_flag.is_set():
            return
        timer = threading.Timer(
            self.interval_s, self._tick, args=(project_uuid,)
        )
        timer.daemon = True
        self._timers[project_uuid] = timer
        timer.start()

    def _tick(self, project_uuid: str) -> None:
        """Timer callback — write one autosave for this project."""
        if self._shutdown_flag.is_set():
            return
        try:
            provider = self._providers.get(project_uuid)
            if provider is None:
                return  # stopped
            try:
                version_seed_id, working_state = provider()
            except Exception as exc:
                # Provider exceptions must not kill the timer permanently;
                # log + reschedule. INV-feedback_silent_error_swallowing:
                # we log explicitly, never silent.
                _log.warning(
                    "Autosave state provider failed for %s: %s",
                    project_uuid,
                    exc,
                )
            else:
                try:
                    self.write_snapshot(project_uuid, version_seed_id, working_state)
                except AutosaveError as exc:
                    _log.warning("Autosave write failed for %s: %s", project_uuid, exc)
        finally:
            with self._lock:
                # Only reschedule if still registered (not stopped)
                if project_uuid in self._providers:
                    self._schedule_next(project_uuid)

    # ---- snapshot write (public for forced-save) ----------------------------

    def write_snapshot(
        self,
        project_uuid: str,
        version_seed_id: int | None,
        working_state: dict[str, Any],
    ) -> Path:
        """Write one snapshot now (synchronous). Rotates rolling files.

        Returns Path of the newest snapshot file.
        """
        # Rotate: ...-2 → -3, -1 → -2, drop oldest
        oldest = self.autosave_dir / _autosave_filename(project_uuid, self.rolling_count)
        if oldest.exists():
            try:
                oldest.unlink()
            except OSError as exc:
                _log.warning("Cannot drop oldest autosave %s: %s", oldest, exc)

        for i in range(self.rolling_count - 1, 0, -1):
            src = self.autosave_dir / _autosave_filename(project_uuid, i)
            dst = self.autosave_dir / _autosave_filename(project_uuid, i + 1)
            if src.exists():
                try:
                    os.replace(src, dst)
                except OSError as exc:
                    _log.warning("Cannot rotate %s → %s: %s", src, dst, exc)

        # Write newest
        newest = self.autosave_dir / _autosave_filename(project_uuid, 1)
        payload = {
            "project_uuid": project_uuid,
            "session_id": self.session_id,
            "saved_at": _utc_now_iso(),
            "version_seed_id": version_seed_id,
            "working_state": working_state,
        }
        _atomic_write_json(newest, payload)
        _log.debug("Autosaved %s → %s", project_uuid, newest.name)
        return newest

    # ---- recovery ----------------------------------------------------------

    def detect_pending_recovery(self) -> list[PendingRecovery]:
        """Scan autosave_dir for orphan autosaves (different session_id или stale).

        Called at app startup. Returns list of recovery candidates for UI dialog.
        Excludes autosaves from the current session (those are live, not orphan).
        """
        candidates: dict[str, list[AutosaveSnapshot]] = {}
        if not self.autosave_dir.exists():
            return []

        for path in self.autosave_dir.iterdir():
            if not path.is_file() or not path.name.endswith(AUTOSAVE_FILE_SUFFIX):
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                _log.warning("Cannot read autosave %s: %s", path, exc)
                continue

            try:
                snap = AutosaveSnapshot(
                    project_uuid=str(payload["project_uuid"]),
                    session_id=str(payload["session_id"]),
                    saved_at=str(payload["saved_at"]),
                    version_seed_id=payload.get("version_seed_id"),
                    working_state=payload.get("working_state", {}),
                    file_path=path,
                )
            except KeyError as exc:
                _log.warning("Autosave %s missing field %s — skipping", path, exc)
                continue

            # Skip live autosaves (current session)
            if snap.session_id == self.session_id:
                continue

            candidates.setdefault(snap.project_uuid, []).append(snap)

        # Build PendingRecovery per project, sorted by saved_at DESC
        results: list[PendingRecovery] = []
        for project_uuid, snaps in candidates.items():
            snaps.sort(key=lambda s: s.saved_at, reverse=True)
            most_recent = snaps[0]
            stale = _is_stale(most_recent.saved_at)
            results.append(
                PendingRecovery(
                    project_uuid=project_uuid,
                    most_recent_snapshot=most_recent,
                    all_snapshots=snaps,
                    is_stale=stale,
                )
            )

        # Sort recoveries by most-recent first
        results.sort(key=lambda r: r.most_recent_snapshot.saved_at, reverse=True)
        return results

    def recover(self, project_uuid: str, *, snapshot_index: int = 0) -> AutosaveSnapshot:
        """Load a specific orphan snapshot. Default snapshot_index=0 = newest.

        After successful recovery, caller should call `claim_recovery(project_uuid)`
        to move orphan files away (so next startup doesn't re-offer recovery).
        """
        pending = self.detect_pending_recovery()
        match = next((p for p in pending if p.project_uuid == project_uuid), None)
        if match is None:
            raise AutosaveError(f"No pending recovery for project {project_uuid}")
        if snapshot_index < 0 or snapshot_index >= len(match.all_snapshots):
            raise AutosaveError(
                f"snapshot_index {snapshot_index} out of range "
                f"[0, {len(match.all_snapshots)})"
            )
        return match.all_snapshots[snapshot_index]

    def claim_recovery(self, project_uuid: str) -> int:
        """Mark recovered autosaves as consumed (delete orphan files).

        Returns count of files removed. Idempotent.
        """
        count = 0
        for path in self.autosave_dir.iterdir():
            if not path.is_file() or not path.name.startswith(f"{project_uuid}."):
                continue
            if not path.name.endswith(AUTOSAVE_FILE_SUFFIX):
                continue
            # Only delete OTHER-session files (live current-session autosaves stay)
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if payload.get("session_id") == self.session_id:
                    continue  # don't delete our own live autosaves
            except (OSError, json.JSONDecodeError):
                pass  # corrupted — still safe to delete (no info)
            try:
                path.unlink()
                count += 1
            except OSError as exc:
                _log.warning("Cannot delete recovered autosave %s: %s", path, exc)
        return count

    def discard(self, project_uuid: str) -> int:
        """Discard all autosaves for a project. Returns deletion count.

        Used когда customer chooses "не восстанавливать" в recovery wizard, OR
        когда explicit save_version succeeds and we want to clean up.
        """
        return self.claim_recovery(project_uuid)


def _is_stale(saved_at_iso: str) -> bool:
    """Check if a saved_at timestamp is older than MAX_RECOVERY_AGE_DAYS."""
    try:
        # Truncate microseconds для fromisoformat compat (Python 3.11+ handles Z)
        ts = datetime.fromisoformat(saved_at_iso.replace("Z", "+00:00"))
    except ValueError:
        return True  # corrupted timestamp → treat as stale
    age = datetime.now(timezone.utc) - ts
    return age.days > MAX_RECOVERY_AGE_DAYS
