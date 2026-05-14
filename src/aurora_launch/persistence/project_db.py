"""Aurora Launch Planner working storage (Phase 0.1).

SQLite-backed metadata store for forecast projects and their version history.
Pairs with BlobStore for content-addressed pickle artefacts. Together they
replace per-save ZIP rewrites (Block 1A pattern) with fast working storage:

- Save new version: SQLite INSERT + (maybe) 1 blob write → <50ms
- Compare versions: pure SQL JOIN, no ZIP unpacking
- Branch (linear history): INSERT new version with parent_version_id

Concurrency model:
- WAL journal mode (single writer, concurrent readers)
- All multi-row mutations wrapped in transactions
- ProjectDB instance is NOT thread-safe; caller serialises (one per process)
- Multi-process access works (WAL handles it) но external lock recommended
  для ProjectDB.delete_project / GC

Recovery model:
- WAL recovery on open (SQLite handles unclean shutdown)
- Orphan blobs (no version_files row) detected by gc_orphan_blobs()
- Missing blobs (FK satisfied но file gone) detected by check_integrity()

API surface keep small and explicit: no magic methods, no implicit transactions
across method calls. Each public method is one transactional unit.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aurora_launch.persistence.blob_store import BlobStore, BlobStoreError

_log = logging.getLogger(__name__)

SCHEMA_FILE = Path(__file__).parent / "schema.sql"
CURRENT_SCHEMA_VERSION = 1

Granularity = str  # 'monthly' | 'weekly' — runtime check, not Literal (sqlite3 doesn't know Literal)
ALLOWED_GRANULARITIES = frozenset({"monthly", "weekly"})


class ProjectDBError(RuntimeError):
    """Raised for ProjectDB operational failures (FK violation, schema mismatch)."""


# ---------------------------------------------------------------------------
# Data classes (read-side projections)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectSummary:
    """Lightweight project info for list views."""

    project_uuid: str
    name: str
    created_at: str
    last_modified: str
    granularity: str
    current_version_id: int | None
    version_count: int


@dataclass(frozen=True)
class ProjectDetail:
    """Full project metadata + version history."""

    project_uuid: str
    name: str
    created_at: str
    last_modified: str
    aurora_app_version: str
    aurora_launch_schema_version: str
    granularity: str
    current_version_id: int | None
    metadata: dict[str, Any]
    versions: list[VersionSummary]


@dataclass(frozen=True)
class VersionSummary:
    """One version's bookkeeping (without file payloads)."""

    version_id: int
    project_uuid: str
    parent_version_id: int | None
    revision: int
    created_at: str
    label: str | None
    decision_note: str | None
    recipient_data_hash: str | None
    composite_bundle_hash: str | None
    file_count: int


@dataclass(frozen=True)
class LoadedVersion:
    """Version with file contents materialised from blob store."""

    summary: VersionSummary
    files: dict[str, bytes]  # entry_path → raw content
    schema_versions: dict[str, str | None]  # entry_path → schema_version
    metadata: dict[str, Any]


@dataclass(frozen=True)
class VersionDiff:
    """Comparison between two versions of the same project."""

    version_id_a: int
    version_id_b: int
    files_only_in_a: list[str] = field(default_factory=list)
    files_only_in_b: list[str] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)  # both have, different blob_sha256
    files_unchanged: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# ProjectDB
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    """ISO 8601 UTC with millisecond precision; matches SQLite strftime format.

    Audit P0-01 fix: single now() call to prevent inconsistent timestamps
    when second boundary crosses between two now() invocations.
    """
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


class ProjectDB:
    """Aurora Launch Planner project database (working storage)."""

    def __init__(self, db_path: Path, blob_store: BlobStore) -> None:
        """Open or initialise database at db_path. blob_store stores artefacts.

        Schema is applied on first open. WAL mode enabled for concurrent reads.
        """
        self.db_path = Path(db_path)
        self.blob_store = blob_store
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(
            str(self.db_path),
            isolation_level=None,  # explicit transaction control via BEGIN/COMMIT
            detect_types=0,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA synchronous = NORMAL")  # WAL: NORMAL safe per SQLite docs
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._apply_schema()

    def _apply_schema(self) -> None:
        """Apply schema DDL idempotently. Future migrations gated by schema_version.

        Note: `executescript` issues its own COMMIT after each DDL statement,
        so wrapping it в explicit BEGIN/COMMIT raises 'no transaction is active'.
        We rely on `CREATE TABLE IF NOT EXISTS` + `INSERT OR IGNORE` for idempotency.
        """
        ddl = SCHEMA_FILE.read_text(encoding="utf-8")
        self._conn.executescript(ddl)
        current = self._conn.execute(
            "SELECT MAX(version) AS v FROM schema_version"
        ).fetchone()
        v = current["v"] if current and current["v"] is not None else 0
        if v > CURRENT_SCHEMA_VERSION:
            raise ProjectDBError(
                f"Database schema version {v} is newer than supported "
                f"{CURRENT_SCHEMA_VERSION}. Upgrade Aurora Launch."
            )

    def close(self) -> None:
        """Close database connection. Safe to call multiple times."""
        if self._conn is not None:
            try:
                self._conn.close()
            except sqlite3.Error as exc:
                _log.warning("Error closing ProjectDB: %s", exc)
            self._conn = None  # type: ignore[assignment]

    def __enter__(self) -> ProjectDB:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # ---- transaction helper ------------------------------------------------

    class _TxContext:
        def __init__(self, conn: sqlite3.Connection) -> None:
            self._conn = conn

        def __enter__(self) -> sqlite3.Connection:
            self._conn.execute("BEGIN IMMEDIATE")
            return self._conn

        def __exit__(self, exc_type, exc_val, exc_tb) -> None:
            if exc_type is None:
                self._conn.execute("COMMIT")
            else:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error as rollback_exc:
                    _log.error("Rollback failed: %s", rollback_exc)

    def _tx(self) -> ProjectDB._TxContext:
        return ProjectDB._TxContext(self._conn)

    # ---- Project CRUD ------------------------------------------------------

    def create_project(
        self,
        name: str,
        aurora_app_version: str,
        *,
        granularity: str = "monthly",
        metadata: dict[str, Any] | None = None,
        project_uuid: str | None = None,
    ) -> str:
        """Create new project; returns its UUID."""
        if not name.strip():
            raise ValueError("Project name must be non-empty")
        if granularity not in ALLOWED_GRANULARITIES:
            raise ValueError(
                f"granularity must be one of {sorted(ALLOWED_GRANULARITIES)}, "
                f"got {granularity!r}"
            )
        uid = project_uuid or str(uuid.uuid4())
        now = _utc_now_iso()
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)

        with self._tx():
            self._conn.execute(
                """
                INSERT INTO projects (
                    project_uuid, name, created_at, last_modified,
                    aurora_app_version, granularity, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (uid, name, now, now, aurora_app_version, granularity, meta_json),
            )
        _log.info("Created project %s (%s)", uid, name)
        return uid

    def list_projects(self) -> list[ProjectSummary]:
        """List all projects ordered by last_modified DESC."""
        rows = self._conn.execute(
            """
            SELECT p.*,
                   (SELECT COUNT(*) FROM versions v WHERE v.project_uuid = p.project_uuid) AS vcount
            FROM projects p
            ORDER BY p.last_modified DESC
            """
        ).fetchall()
        return [
            ProjectSummary(
                project_uuid=r["project_uuid"],
                name=r["name"],
                created_at=r["created_at"],
                last_modified=r["last_modified"],
                granularity=r["granularity"],
                current_version_id=r["current_version_id"],
                version_count=r["vcount"],
            )
            for r in rows
        ]

    def get_project(self, project_uuid: str) -> ProjectDetail:
        """Full project detail (metadata + all versions, no file payloads)."""
        row = self._conn.execute(
            "SELECT * FROM projects WHERE project_uuid = ?", (project_uuid,)
        ).fetchone()
        if row is None:
            raise ProjectDBError(f"Project not found: {project_uuid}")

        versions = self.list_versions(project_uuid)
        return ProjectDetail(
            project_uuid=row["project_uuid"],
            name=row["name"],
            created_at=row["created_at"],
            last_modified=row["last_modified"],
            aurora_app_version=row["aurora_app_version"],
            aurora_launch_schema_version=row["aurora_launch_schema_version"],
            granularity=row["granularity"],
            current_version_id=row["current_version_id"],
            metadata=json.loads(row["metadata_json"]),
            versions=versions,
        )

    def update_project_metadata(
        self,
        project_uuid: str,
        metadata: dict[str, Any] | None = None,
        *,
        name: str | None = None,
    ) -> None:
        """Update mutable project fields. Touches last_modified."""
        updates: list[str] = []
        params: list[Any] = []
        if metadata is not None:
            updates.append("metadata_json = ?")
            params.append(json.dumps(metadata, ensure_ascii=False))
        if name is not None:
            if not name.strip():
                raise ValueError("Project name must be non-empty")
            updates.append("name = ?")
            params.append(name)
        if not updates:
            return
        updates.append("last_modified = ?")
        params.append(_utc_now_iso())
        params.append(project_uuid)

        with self._tx():
            cur = self._conn.execute(
                f"UPDATE projects SET {', '.join(updates)} WHERE project_uuid = ?",
                params,
            )
            if cur.rowcount == 0:
                raise ProjectDBError(f"Project not found: {project_uuid}")

    def delete_project(self, project_uuid: str) -> None:
        """Delete project, all versions, decrement blob ref-counts (GC after).

        Audit P0-03 fix: use MAX(ref_count - 1, 0) to guard против underflow
        в случае двойного delete от concurrent processes (WAL BEGIN IMMEDIATE
        защищает single-process; cross-process needs explicit clamp).
        Schema has CHECK (ref_count >= 0) as defense-in-depth.
        """
        with self._tx():
            # Verify project exists (raise raньше чем DELETE для clear error)
            row = self._conn.execute(
                "SELECT 1 FROM projects WHERE project_uuid = ?", (project_uuid,)
            ).fetchone()
            if row is None:
                raise ProjectDBError(f"Project not found: {project_uuid}")

            # Decrement ref_count for blobs referenced by versions of this project.
            # MAX(.., 0) clamps к нулю — schema CHECK would reject negative anyway,
            # но clamp keeps the update idempotent under race conditions.
            self._conn.execute(
                """
                UPDATE blobs SET ref_count = MAX(ref_count - 1, 0)
                WHERE sha256 IN (
                    SELECT vf.blob_sha256 FROM version_files vf
                    JOIN versions v ON vf.version_id = v.version_id
                    WHERE v.project_uuid = ?
                )
                """,
                (project_uuid,),
            )
            self._conn.execute(
                "DELETE FROM projects WHERE project_uuid = ?", (project_uuid,)
            )
        _log.info("Deleted project %s", project_uuid)

    # ---- Version operations ------------------------------------------------

    def save_version(
        self,
        project_uuid: str,
        files: dict[str, bytes],
        *,
        label: str | None = None,
        decision_note: str | None = None,
        parent_version_id: int | None = None,
        recipient_data_hash: str | None = None,
        composite_bundle_hash: str | None = None,
        schema_versions: dict[str, str | None] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Persist a new project version.

        Files are stored as content-addressed blobs (deduplicated). Blob
        ref-counts incremented atomically. Returns new version_id.

        Validates project exists. Computes revision = max(existing) + 1.
        Updates project.current_version_id to point к new version (HEAD).
        """
        if not files:
            raise ValueError("Cannot save version with zero files")
        schema_versions = schema_versions or {}
        metadata = metadata or {}
        now = _utc_now_iso()

        # Pre-compute blob hashes (caller-safe — operation purely functional)
        prepared: list[tuple[str, bytes, str]] = []
        for file_path, content in files.items():
            sha = self.blob_store.compute_hash(content)
            prepared.append((file_path, content, sha))

        with self._tx():
            # Validate project exists и compute next revision
            row = self._conn.execute(
                "SELECT 1 FROM projects WHERE project_uuid = ?", (project_uuid,)
            ).fetchone()
            if row is None:
                raise ProjectDBError(f"Project not found: {project_uuid}")

            if parent_version_id is not None:
                parent_row = self._conn.execute(
                    "SELECT project_uuid FROM versions WHERE version_id = ?",
                    (parent_version_id,),
                ).fetchone()
                if parent_row is None:
                    raise ProjectDBError(
                        f"parent_version_id {parent_version_id} does not exist"
                    )
                if parent_row["project_uuid"] != project_uuid:
                    raise ProjectDBError(
                        f"parent_version_id {parent_version_id} belongs to another project"
                    )

            rev_row = self._conn.execute(
                "SELECT MAX(revision) AS rmax FROM versions WHERE project_uuid = ?",
                (project_uuid,),
            ).fetchone()
            next_rev = (rev_row["rmax"] or 0) + 1

            cur = self._conn.execute(
                """
                INSERT INTO versions (
                    project_uuid, parent_version_id, revision, created_at,
                    label, decision_note, recipient_data_hash,
                    composite_bundle_hash, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_uuid,
                    parent_version_id,
                    next_rev,
                    now,
                    label,
                    decision_note,
                    recipient_data_hash,
                    composite_bundle_hash,
                    json.dumps(metadata, ensure_ascii=False),
                ),
            )
            version_id = cur.lastrowid

            # Store blobs + version_files rows. Dedup: if blob already exists
            # we increment ref_count instead of inserting.
            for file_path, content, sha in prepared:
                self._upsert_blob(sha, content)
                self._conn.execute(
                    """
                    INSERT INTO version_files (
                        version_id, file_path, blob_sha256, schema_version
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        version_id,
                        file_path,
                        sha,
                        schema_versions.get(file_path),
                    ),
                )

            # Move HEAD to new version + touch last_modified
            self._conn.execute(
                """
                UPDATE projects SET current_version_id = ?, last_modified = ?
                WHERE project_uuid = ?
                """,
                (version_id, now, project_uuid),
            )

        _log.info(
            "Saved version %d (revision %d) for project %s with %d files",
            version_id,
            next_rev,
            project_uuid,
            len(files),
        )
        return version_id

    def _upsert_blob(self, sha: str, content: bytes) -> None:
        """Insert blob row + write file; or increment ref_count if exists.

        Must be called inside an active transaction.
        """
        existing = self._conn.execute(
            "SELECT ref_count FROM blobs WHERE sha256 = ?", (sha,)
        ).fetchone()
        if existing is not None:
            # Already known — increment ref_count and ensure file exists on disk
            self._conn.execute(
                "UPDATE blobs SET ref_count = ref_count + 1 WHERE sha256 = ?",
                (sha,),
            )
            if not self.blob_store.exists(sha):
                # File deleted but DB still has row — heal by re-writing
                _log.warning(
                    "Blob row exists для %s но file missing — re-writing",
                    sha[:12],
                )
                self.blob_store.store(content)
            return

        info = self.blob_store.store(content)
        self._conn.execute(
            """
            INSERT INTO blobs (sha256, size_bytes, ref_count, created_at, storage_path)
            VALUES (?, ?, 1, ?, ?)
            """,
            (
                sha,
                info.size_bytes,
                _utc_now_iso(),
                str(info.storage_path.relative_to(self.blob_store.blobs_dir.parent))
                if info.storage_path.is_relative_to(self.blob_store.blobs_dir.parent)
                else str(info.storage_path),
            ),
        )

    def load_version(self, version_id: int) -> LoadedVersion:
        """Load version + all file payloads from blob store."""
        v_row = self._conn.execute(
            "SELECT * FROM versions WHERE version_id = ?", (version_id,)
        ).fetchone()
        if v_row is None:
            raise ProjectDBError(f"Version not found: {version_id}")

        file_rows = self._conn.execute(
            """
            SELECT file_path, blob_sha256, schema_version
            FROM version_files WHERE version_id = ?
            ORDER BY file_path
            """,
            (version_id,),
        ).fetchall()

        files: dict[str, bytes] = {}
        schemas: dict[str, str | None] = {}
        for fr in file_rows:
            try:
                files[fr["file_path"]] = self.blob_store.load(fr["blob_sha256"])
            except BlobStoreError as exc:
                raise ProjectDBError(
                    f"Cannot load blob {fr['blob_sha256']} for version {version_id} "
                    f"file {fr['file_path']!r}: {exc}"
                ) from exc
            schemas[fr["file_path"]] = fr["schema_version"]

        summary = self._row_to_version_summary(v_row, file_count=len(files))
        return LoadedVersion(
            summary=summary,
            files=files,
            schema_versions=schemas,
            metadata=json.loads(v_row["metadata_json"]),
        )

    def list_versions(self, project_uuid: str) -> list[VersionSummary]:
        """List versions of a project (chronological ascending by revision)."""
        rows = self._conn.execute(
            """
            SELECT v.*,
                   (SELECT COUNT(*) FROM version_files vf WHERE vf.version_id = v.version_id) AS fc
            FROM versions v
            WHERE v.project_uuid = ?
            ORDER BY v.revision ASC
            """,
            (project_uuid,),
        ).fetchall()
        return [self._row_to_version_summary(r, file_count=r["fc"]) for r in rows]

    @staticmethod
    def _row_to_version_summary(row: sqlite3.Row, *, file_count: int) -> VersionSummary:
        return VersionSummary(
            version_id=row["version_id"],
            project_uuid=row["project_uuid"],
            parent_version_id=row["parent_version_id"],
            revision=row["revision"],
            created_at=row["created_at"],
            label=row["label"],
            decision_note=row["decision_note"],
            recipient_data_hash=row["recipient_data_hash"],
            composite_bundle_hash=row["composite_bundle_hash"],
            file_count=file_count,
        )

    def compare_versions(self, version_id_a: int, version_id_b: int) -> VersionDiff:
        """Diff two versions by file_path и blob_sha256.

        Identical blob_sha256 → unchanged.
        Different blob_sha256 on same file_path → changed.
        Only in one side → added/removed.
        """
        a_files = {
            r["file_path"]: r["blob_sha256"]
            for r in self._conn.execute(
                "SELECT file_path, blob_sha256 FROM version_files WHERE version_id = ?",
                (version_id_a,),
            ).fetchall()
        }
        b_files = {
            r["file_path"]: r["blob_sha256"]
            for r in self._conn.execute(
                "SELECT file_path, blob_sha256 FROM version_files WHERE version_id = ?",
                (version_id_b,),
            ).fetchall()
        }

        only_a = sorted(set(a_files) - set(b_files))
        only_b = sorted(set(b_files) - set(a_files))
        common = set(a_files) & set(b_files)
        changed = sorted(p for p in common if a_files[p] != b_files[p])
        unchanged = sorted(p for p in common if a_files[p] == b_files[p])

        return VersionDiff(
            version_id_a=version_id_a,
            version_id_b=version_id_b,
            files_only_in_a=only_a,
            files_only_in_b=only_b,
            files_changed=changed,
            files_unchanged=unchanged,
        )

    def set_current_version(self, project_uuid: str, version_id: int) -> None:
        """Move project HEAD pointer to a specific version (for revert / branch switch)."""
        with self._tx():
            v_row = self._conn.execute(
                "SELECT project_uuid FROM versions WHERE version_id = ?",
                (version_id,),
            ).fetchone()
            if v_row is None:
                raise ProjectDBError(f"Version not found: {version_id}")
            if v_row["project_uuid"] != project_uuid:
                raise ProjectDBError(
                    f"Version {version_id} belongs to project {v_row['project_uuid']!r}, "
                    f"not {project_uuid!r}"
                )
            self._conn.execute(
                """
                UPDATE projects SET current_version_id = ?, last_modified = ?
                WHERE project_uuid = ?
                """,
                (version_id, _utc_now_iso(), project_uuid),
            )

    # ---- Maintenance -------------------------------------------------------

    def gc_orphan_blobs(self) -> int:
        """Delete blobs with ref_count = 0 (from disk + DB row).

        Returns count of blobs reclaimed. Idempotent; safe to call anytime.
        """
        rows = self._conn.execute(
            "SELECT sha256 FROM blobs WHERE ref_count <= 0"
        ).fetchall()
        if not rows:
            return 0

        count = 0
        with self._tx():
            for r in rows:
                sha = r["sha256"]
                try:
                    self.blob_store.delete(sha)
                except BlobStoreError as exc:
                    _log.warning("Failed to delete orphan blob %s: %s", sha[:12], exc)
                    continue
                self._conn.execute("DELETE FROM blobs WHERE sha256 = ?", (sha,))
                count += 1
        _log.info("GC reclaimed %d orphan blob(s)", count)
        return count

    def check_integrity(self) -> dict[str, list[str]]:
        """Verify DB consistency и blob filesystem state.

        Returns dict with keys:
        - missing_blobs: blob_sha256 referenced by version_files но not on disk
        - orphan_files: blob files on disk но not in DB
        - dangling_refs: version_files rows whose blob_sha256 has no blobs row
        - ref_count_drift: blob rows whose ref_count != actual reference count
        """
        report: dict[str, list[str]] = {
            "missing_blobs": [],
            "orphan_files": [],
            "dangling_refs": [],
            "ref_count_drift": [],
        }

        db_blobs = {
            r["sha256"]: r["ref_count"]
            for r in self._conn.execute(
                "SELECT sha256, ref_count FROM blobs"
            ).fetchall()
        }
        for sha in db_blobs:
            if not self.blob_store.exists(sha):
                report["missing_blobs"].append(sha)

        for info in self.blob_store.list_all():
            if info.sha256 not in db_blobs:
                report["orphan_files"].append(info.sha256)

        # Dangling FK refs (sqlite enforces FK only if pragma on; we still cross-check)
        dangling = self._conn.execute(
            """
            SELECT DISTINCT vf.blob_sha256
            FROM version_files vf
            LEFT JOIN blobs b ON b.sha256 = vf.blob_sha256
            WHERE b.sha256 IS NULL
            """
        ).fetchall()
        report["dangling_refs"] = [r["blob_sha256"] for r in dangling]

        # ref_count drift: count actual references
        drift = self._conn.execute(
            """
            SELECT b.sha256 AS s,
                   b.ref_count AS claimed,
                   COUNT(vf.version_id) AS actual
            FROM blobs b
            LEFT JOIN version_files vf ON vf.blob_sha256 = b.sha256
            GROUP BY b.sha256
            HAVING b.ref_count != COUNT(vf.version_id)
            """
        ).fetchall()
        report["ref_count_drift"] = [r["s"] for r in drift]

        return report

    def reconcile_ref_counts(self) -> int:
        """Recompute ref_count from version_files reality. Returns rows fixed."""
        with self._tx():
            cur = self._conn.execute(
                """
                UPDATE blobs SET ref_count = (
                    SELECT COUNT(*) FROM version_files vf WHERE vf.blob_sha256 = blobs.sha256
                )
                WHERE blobs.ref_count != (
                    SELECT COUNT(*) FROM version_files vf WHERE vf.blob_sha256 = blobs.sha256
                )
                """
            )
            return cur.rowcount

    def vacuum(self) -> None:
        """SQLite VACUUM — reclaim space, defragment. Cannot run in transaction."""
        # VACUUM не работает inside transaction; close any implicit one.
        self._conn.execute("VACUUM")
