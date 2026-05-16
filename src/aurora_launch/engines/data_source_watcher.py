"""DataSourceWatcher — local folder watcher for automatic forecast refresh.

Architecture (ROADMAP §3.5):
- Pluggable adapter pattern: source_kind determines which detection strategy runs.
- For "dsm_xlsx_folder" / "mediascope_xlsx_folder": scans folder for .xlsx/.xls
  files whose mtime is AFTER last_modified_seen. Uses pathlib.Path.stat().
- For "manual": never triggers; customer imports manually via wizard.
- Persistent state (last_modified_seen, last_checked_at) is stored in the
  ProjectDB metadata column via DI container (services.py).
- Thread-safe: internal _lock guards _sources and _dismissed sets.

152-FZ compliance:
- Watcher ONLY reads local filesystem mtimes — no network, no telemetry.
- All triggers are opt-in gated: callers check RefreshConsentSetting.enabled
  before acting on triggers. Watcher itself is consent-agnostic.

DSM / Mediascope API (DEFERRED):
  When real HTTP API access becomes available, implement:
    class DsmApiAdapter: adapter for DSM REST endpoint
    class MediascopeApiAdapter: adapter for Mediascope SOAP/REST endpoint
  Register under new source_kind values ("dsm_api", "mediascope_api").
  Plug in via register_source(DataSourceConfig(source_kind="dsm_api", ...)).
  No changes to DataSourceWatcher core needed (open/closed principle).
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from aurora_launch.engines.path_security import (
    PathSecurityError,
    validate_safe_path,
)
from aurora_launch.schemas.auto_refresh import (
    DataSourceConfig,
    RefreshConsentSetting,
    RefreshTrigger,
)

logger = logging.getLogger(__name__)

# Key in ProjectDB.metadata where we persist watcher state per project.
# Value: dict[source_kind, {last_checked_at, last_modified_seen}]
_METADATA_KEY = "auto_refresh_watcher_state"

# Key for consent setting (stored globally, not per-project).
_CONSENT_KEY = "auto_refresh_consent"

# Supported file extensions for DSM / Mediascope XLSX exports.
_XLSX_EXTENSIONS = frozenset({".xlsx", ".xls"})


def _now_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(UTC).isoformat()


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    """Parse ISO-8601 string → datetime (UTC-aware).  Returns None on failure."""
    if s is None:
        return None
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        logger.warning("DataSourceWatcher: could not parse datetime %r", s)
        return None


# Audit H-02 (этап 4.5): limit iter чтобы customer положивший 10k+ XLSX
# в watched folder не получал O(N) freeze при каждом scan. Если limit
# превышен — warning + scan ограничивается этим числом (sample). Для
# realistic DSM/Mediascope folders ~100 XLSX в год — limit избыточен.
_MAX_FOLDER_SCAN_FILES = 5000


def _scan_folder_max_mtime(folder: Path) -> Optional[datetime]:
    """Return the latest mtime among .xlsx/.xls files in folder.

    Returns None if folder does not exist, is not a directory, or has no
    matching files. Errors on individual stat() calls are logged and skipped
    so a single unreadable file does not abort the scan.

    Audit H-02: capped at _MAX_FOLDER_SCAN_FILES, warns if customer's folder
    exceeds (расход stat()-calls O(N), 5000 даёт ~50-100ms на SSD, acceptable).
    """
    if not folder.is_dir():
        logger.debug("DataSourceWatcher: folder %s does not exist or is not a dir", folder)
        return None

    max_mtime: Optional[datetime] = None
    n_scanned = 0
    for child in folder.iterdir():
        if child.suffix.lower() not in _XLSX_EXTENSIONS:
            continue
        if n_scanned >= _MAX_FOLDER_SCAN_FILES:
            logger.warning(
                "DataSourceWatcher: folder %s contains >%d xlsx files. "
                "Truncating scan для performance. Создайте отдельную папку "
                "для актуальных данных.",
                folder,
                _MAX_FOLDER_SCAN_FILES,
            )
            break
        try:
            mtime = datetime.fromtimestamp(child.stat().st_mtime, tz=UTC)
        except OSError as exc:
            logger.warning("DataSourceWatcher: stat failed for %s: %s", child, exc)
            continue
        if max_mtime is None or mtime > max_mtime:
            max_mtime = mtime
        n_scanned += 1

    return max_mtime


class DataSourceWatcher:
    """Watches configured data-source folders for new XLSX exports.

    Lifecycle:
        watcher = DataSourceWatcher(project_uuid, db=project_db_instance)
        watcher.register_source(DataSourceConfig(...))
        triggers = watcher.check_for_updates()
        # show banner / prompt user
        watcher.mark_seen("dsm_xlsx_folder", new_mtime_iso)

    DI integration:
        The ``db`` parameter accepts any object with a ``get_project`` and
        ``update_project_metadata`` method (matches ProjectDB interface).
        Pass None in tests — state is kept in-memory only.
    """

    def __init__(
        self,
        project_uuid: str,
        db: Any = None,
    ) -> None:
        self._project_uuid = project_uuid
        self._db = db
        self._lock = threading.Lock()
        # source_kind → DataSourceConfig
        self._sources: dict[str, DataSourceConfig] = {}
        # project_uuids dismissed in THIS session (not persisted between restarts)
        self._dismissed: set[str] = set()

        # Load persisted state from DB if available
        self._load_from_db()

    # -------------------------------------------------------------------------
    # Source registration
    # -------------------------------------------------------------------------

    def register_source(self, config: DataSourceConfig) -> None:
        """Register or replace a watched source.

        Idempotent: calling twice with the same source_kind replaces config.
        """
        with self._lock:
            self._sources[config.source_kind] = config
            logger.debug(
                "DataSourceWatcher[%s]: registered source %s path=%s",
                self._project_uuid,
                config.source_kind,
                config.path,
            )

    def get_sources(self) -> list[DataSourceConfig]:
        """Return a snapshot of currently registered sources."""
        with self._lock:
            return list(self._sources.values())

    # -------------------------------------------------------------------------
    # Update detection
    # -------------------------------------------------------------------------

    def check_for_updates(self) -> list[RefreshTrigger]:
        """Scan all registered sources; return triggers for sources with new data.

        - "manual" sources are never triggered.
        - Folder sources: triggers if max_mtime_in_folder > last_modified_seen.
        - Updates last_checked_at on every check (regardless of trigger result).
        - Persists updated last_checked_at to DB if db is configured.

        Returns list may be empty (no new data) or contain 1+ triggers.
        """
        if self._project_uuid in self._dismissed:
            return []

        triggers: list[RefreshTrigger] = []
        now = _now_iso()

        with self._lock:
            sources_snapshot = list(self._sources.items())

        for source_kind, config in sources_snapshot:
            trigger = self._check_source(source_kind, config, now)
            if trigger is not None:
                triggers.append(trigger)

        # Persist updated last_checked_at for all sources
        self._persist_state()

        return triggers

    def _check_source(
        self,
        source_kind: str,
        config: DataSourceConfig,
        now: str,
    ) -> Optional[RefreshTrigger]:
        """Check a single source.  Returns trigger or None.  Updates config in-place."""
        if source_kind == "manual":
            # Manual imports never auto-trigger.
            return None

        if source_kind in ("dsm_xlsx_folder", "mediascope_xlsx_folder"):
            return self._check_folder_source(source_kind, config, now)

        # Unknown / future source kinds: log and skip gracefully.
        logger.debug(
            "DataSourceWatcher[%s]: unknown source_kind %r — skipping",
            self._project_uuid,
            source_kind,
        )
        return None

    def _check_folder_source(
        self,
        source_kind: str,
        config: DataSourceConfig,
        now: str,
    ) -> Optional[RefreshTrigger]:
        """Check a folder-watch source.  Mutates config.last_checked_at in-place."""
        assert config.path is not None  # validated by schema

        folder = Path(config.path)

        # Phase 2.C H-4: validate folder path against symlink/junction/traversal.
        # Folders are "read" context: use is_write=False — folder must exist and
        # be under allowed roots. If folder doesn't exist or is outside roots,
        # log warning and treat as "no trigger" (same as non-existent folder).
        from aurora_launch.sidecar.methods import _get_allowed_roots
        try:
            validate_safe_path(folder, _get_allowed_roots(), is_write=False)
        except PathSecurityError as exc:
            logger.warning(
                "DataSourceWatcher[%s]: folder path rejected by security policy "
                "(%s) — source_kind=%r skipped",
                self._project_uuid,
                exc,
                source_kind,
            )
            return None

        max_mtime = _scan_folder_max_mtime(folder)

        # Update last_checked_at regardless of whether new data found
        with self._lock:
            updated = DataSourceConfig(
                source_kind=config.source_kind,  # type: ignore[arg-type]
                path=config.path,
                last_checked_at=now,
                last_modified_seen=config.last_modified_seen,
            )
            self._sources[source_kind] = updated

        if max_mtime is None:
            # Folder empty or doesn't exist → no trigger
            return None

        last_seen = _parse_iso(config.last_modified_seen)

        if last_seen is None:
            # First ever check — establish baseline, no trigger (avoid spurious
            # "new data" on first run which would just show everything).
            logger.info(
                "DataSourceWatcher[%s]: establishing baseline mtime=%s for %s",
                self._project_uuid,
                max_mtime.isoformat(),
                source_kind,
            )
            with self._lock:
                self._sources[source_kind] = DataSourceConfig(
                    source_kind=config.source_kind,  # type: ignore[arg-type]
                    path=config.path,
                    last_checked_at=now,
                    last_modified_seen=max_mtime.isoformat(),
                )
            return None

        if max_mtime > last_seen:
            logger.info(
                "DataSourceWatcher[%s]: new data detected in %s "
                "(max_mtime=%s > last_seen=%s)",
                self._project_uuid,
                source_kind,
                max_mtime.isoformat(),
                last_seen.isoformat(),
            )
            return RefreshTrigger(
                project_uuid=self._project_uuid,
                reason="new_data",
                detected_at=now,
                source=f"{source_kind}:{config.path}",
            )

        return None

    # -------------------------------------------------------------------------
    # mark_seen
    # -------------------------------------------------------------------------

    def mark_seen(self, source_kind: str, modified_time_iso: str) -> None:
        """Record that the customer has acknowledged data up to modified_time_iso.

        Called after the user accepts a refresh prompt or after a re-forecast
        completes. Updates last_modified_seen → prevents repeated triggers for
        same data.
        """
        with self._lock:
            config = self._sources.get(source_kind)
            if config is None:
                logger.warning(
                    "DataSourceWatcher[%s]: mark_seen called for unregistered source %r",
                    self._project_uuid,
                    source_kind,
                )
                return
            updated = DataSourceConfig(
                source_kind=config.source_kind,  # type: ignore[arg-type]
                path=config.path,
                last_checked_at=config.last_checked_at,
                last_modified_seen=modified_time_iso,
            )
            self._sources[source_kind] = updated

        self._persist_state()
        logger.debug(
            "DataSourceWatcher[%s]: mark_seen %s → %s",
            self._project_uuid,
            source_kind,
            modified_time_iso,
        )

    # -------------------------------------------------------------------------
    # Session-level dismiss
    # -------------------------------------------------------------------------

    def dismiss(self) -> None:
        """Suppress triggers for this project for the remainder of the session.

        Does NOT change consent settings — user is saying "not now", not "never".
        Persisted across process restarts only if caller also calls
        set_consent_setting(enabled=False).
        """
        self._dismissed.add(self._project_uuid)
        logger.debug(
            "DataSourceWatcher[%s]: dismissed for this session", self._project_uuid
        )

    def is_dismissed(self) -> bool:
        """Return True if this project's triggers are suppressed for this session."""
        return self._project_uuid in self._dismissed

    # -------------------------------------------------------------------------
    # DB persistence (optional — graceful if db is None)
    # -------------------------------------------------------------------------

    def _load_from_db(self) -> None:
        """Load last_checked_at / last_modified_seen from ProjectDB metadata."""
        if self._db is None:
            return
        try:
            project = self._db.get_project(self._project_uuid)
            if project is None:
                return
            metadata = getattr(project, "metadata", None) or {}
            watcher_state: dict[str, Any] = metadata.get(_METADATA_KEY, {})
            with self._lock:
                for kind, state in watcher_state.items():
                    if kind not in self._sources:
                        continue
                    existing = self._sources[kind]
                    updated = DataSourceConfig(
                        source_kind=existing.source_kind,  # type: ignore[arg-type]
                        path=existing.path,
                        last_checked_at=state.get("last_checked_at"),
                        last_modified_seen=state.get("last_modified_seen"),
                    )
                    self._sources[kind] = updated
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "DataSourceWatcher[%s]: failed to load state from DB: %s",
                self._project_uuid,
                exc,
            )

    def _persist_state(self) -> None:
        """Persist last_checked_at / last_modified_seen to ProjectDB metadata."""
        if self._db is None:
            return
        with self._lock:
            state_to_save = {
                kind: {
                    "last_checked_at": cfg.last_checked_at,
                    "last_modified_seen": cfg.last_modified_seen,
                }
                for kind, cfg in self._sources.items()
            }
        try:
            self._db.update_project_metadata(
                self._project_uuid,
                {_METADATA_KEY: state_to_save},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "DataSourceWatcher[%s]: failed to persist state to DB: %s",
                self._project_uuid,
                exc,
            )


# ---------------------------------------------------------------------------
# Global consent helper (not per-project — one setting for all projects)
# ---------------------------------------------------------------------------


class ConsentManager:
    """Manages the global RefreshConsentSetting stored in a key-value store.

    db_store: any object with kv_get(key) → dict|None и kv_set(key, dict) → None
    semantics. В production — ProjectDB напрямую (после v003 migration имеет
    kv_get/kv_set). В тестах — простой dict-shim предоставляющий те же методы.

    Phase 1.B.1 C-2 fix: до этого ConsentManager вызывал self._store.get/set
    через _DbKvShim wrapper в methods.py — ProjectDB не имел kv_get/kv_set,
    AttributeError проглатывался, persistence не работала. Сейчас прямой
    вызов kv_get/kv_set + ProjectDB методы существуют → реальная persistence.
    """

    def __init__(self, db_store: Any = None) -> None:
        self._store = db_store
        self._lock = threading.Lock()
        self._cached: Optional[RefreshConsentSetting] = None

    def get(self) -> Optional[RefreshConsentSetting]:
        """Return current consent setting.  None = never configured (first-run).

        Audit H-06 (этап 4.5): чтение _cached было вне lock'а, что создавало
        race условие при concurrent calls (один thread reads None, второй
        already set'нул через .set() но до записи в _cached). Сейчас весь
        read-through-cache pattern под единым lock'ом.
        """
        with self._lock:
            if self._cached is not None:
                return self._cached
            if self._store is None:
                return None
            try:
                raw = self._store.kv_get(_CONSENT_KEY)
                if raw is None:
                    return None
                self._cached = RefreshConsentSetting.model_validate(raw)
                return self._cached
            except Exception as exc:  # noqa: BLE001
                logger.warning("ConsentManager.get failed: %s", exc)
                return None

    def set(self, enabled: bool, frequency: str = "weekly") -> RefreshConsentSetting:
        """Persist consent setting and return updated value."""
        now = _now_iso()
        setting = RefreshConsentSetting(
            enabled=enabled,
            frequency=frequency,  # type: ignore[arg-type]
            last_prompted_at=now,
        )
        with self._lock:
            self._cached = setting
        if self._store is not None:
            try:
                self._store.kv_set(_CONSENT_KEY, setting.model_dump())
            except Exception as exc:  # noqa: BLE001
                logger.warning("ConsentManager.set persist failed: %s", exc)
        return setting
