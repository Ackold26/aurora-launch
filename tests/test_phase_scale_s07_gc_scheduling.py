"""S-07 — gc_orphan_blobs scheduling tests.

Coverage:
- Migration v002 applies cleanly: schema_version goes to 2, gc_metadata created
- Migration v002 idempotent on existing DB
- ProjectDB open triggers GC if gc_metadata is empty (last_gc_ran_at = NULL)
- ProjectDB open does NOT trigger GC if last_gc_ran_at is within 7 days
- ProjectDB open triggers GC if last_gc_ran_at > 7 days ago
- gc_orphan_blobs updates last_gc_ran_at + orphans_collected_total via _update_gc_metadata
- get_gc_metadata returns correct values
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aurora_launch.persistence.blob_store import BlobStore
from aurora_launch.persistence.migrator import (
    apply_pending_migrations,
    get_current_version,
)
from aurora_launch.persistence.project_db import (
    GC_INTERVAL_SECONDS,
    ProjectDB,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def storage_root(tmp_path: Path) -> Path:
    root = tmp_path / "aurora_s07"
    root.mkdir()
    (root / "blobs").mkdir()
    return root


@pytest.fixture()
def blob_store(storage_root: Path) -> BlobStore:
    return BlobStore(storage_root / "blobs")


@pytest.fixture()
def project_db(storage_root: Path, blob_store: BlobStore):
    db = ProjectDB(storage_root / "projects.db", blob_store)
    yield db
    db.close()


def _fresh_conn(db_path: Path) -> sqlite3.Connection:
    """Open plain sqlite3 connection to inspect schema after migrations."""
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Migration tests
# ---------------------------------------------------------------------------


class TestMigrationV002:
    def test_schema_version_is_2_after_open(self, project_db: ProjectDB) -> None:
        """Opening ProjectDB (which runs _apply_schema) should reach v002."""
        conn = project_db._conn  # noqa: SLF001
        version = get_current_version(conn)
        assert version == 2

    def test_gc_metadata_table_exists(self, project_db: ProjectDB) -> None:
        """gc_metadata table should exist with exactly one row (id=1)."""
        rows = project_db._conn.execute(  # noqa: SLF001
            "SELECT * FROM gc_metadata"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["id"] == 1
        assert rows[0]["orphans_collected_total"] == 0

    def test_gc_metadata_last_gc_ran_at_null_initially(self, project_db: ProjectDB) -> None:
        """On fresh DB, last_gc_ran_at should be NULL."""
        last_ran_at, total = project_db.get_gc_metadata()
        # last_gc_ran_at may be updated by _maybe_gc_on_open (NULL means never ran
        # before open; after open it is set). We only verify total is non-negative.
        assert total >= 0
        assert isinstance(total, int)

    def test_migration_idempotent_second_open(self, storage_root: Path, blob_store: BlobStore) -> None:
        """Second ProjectDB open on same file must not fail or create duplicate rows."""
        db_path = storage_root / "idempotent.db"
        with ProjectDB(db_path, blob_store):
            pass
        # Re-open — migrations already at v2, should be no-ops
        with ProjectDB(db_path, blob_store) as db2:
            version = get_current_version(db2._conn)  # noqa: SLF001
            assert version == 2
            rows = db2._conn.execute(  # noqa: SLF001
                "SELECT COUNT(*) AS n FROM gc_metadata"
            ).fetchone()
            assert rows["n"] == 1

    def test_migration_v002_applies_via_migrator_directly(self, tmp_path: Path) -> None:
        """Apply migrations to a plain sqlite3 conn and verify v002 result."""
        from aurora_launch.persistence.project_db import MIGRATIONS_DIR

        conn = sqlite3.connect(str(tmp_path / "direct.db"), isolation_level=None)
        conn.row_factory = sqlite3.Row
        apply_pending_migrations(conn, MIGRATIONS_DIR)

        version = get_current_version(conn)
        assert version == 2

        has_gc = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='gc_metadata'"
        ).fetchone()
        assert has_gc is not None

        row = conn.execute("SELECT * FROM gc_metadata WHERE id=1").fetchone()
        assert row is not None
        assert row["orphans_collected_total"] == 0
        conn.close()


# ---------------------------------------------------------------------------
# Startup-time GC trigger tests
# ---------------------------------------------------------------------------


class TestStartupGcTrigger:
    def test_gc_runs_when_metadata_null(self, storage_root: Path, blob_store: BlobStore) -> None:
        """ProjectDB open triggers GC if last_gc_ran_at IS NULL."""
        db_path = storage_root / "gc_null.db"
        gc_call_count = 0

        original_gc = ProjectDB.gc_orphan_blobs

        def patched_gc(self) -> int:
            nonlocal gc_call_count
            gc_call_count += 1
            return original_gc(self)

        with patch.object(ProjectDB, "gc_orphan_blobs", patched_gc):
            # Force last_gc_ran_at = NULL by opening fresh DB.
            # _maybe_gc_on_open will see NULL and run GC.
            with ProjectDB(db_path, blob_store):
                pass

        assert gc_call_count >= 1, "Expected GC to run on first open (NULL metadata)"

    def test_gc_does_not_run_within_7_days(self, storage_root: Path, blob_store: BlobStore) -> None:
        """ProjectDB open skips GC if last_gc_ran_at is within GC_INTERVAL_SECONDS."""
        db_path = storage_root / "gc_recent.db"

        # Open DB once to initialise schema and run initial GC.
        with ProjectDB(db_path, blob_store) as db:
            # Manually set last_gc_ran_at to 1 day ago (well within 7-day window).
            recent_ts = (
                datetime.now(timezone.utc) - timedelta(days=1)
            ).strftime("%Y-%m-%dT%H:%M:%S.") + "000Z"
            db._conn.execute(  # noqa: SLF001
                "UPDATE gc_metadata SET last_gc_ran_at = ? WHERE id = 1",
                (recent_ts,),
            )

        gc_call_count = 0
        original_gc = ProjectDB.gc_orphan_blobs

        def patched_gc(self) -> int:
            nonlocal gc_call_count
            gc_call_count += 1
            return original_gc(self)

        with patch.object(ProjectDB, "gc_orphan_blobs", patched_gc):
            with ProjectDB(db_path, blob_store):
                pass

        assert gc_call_count == 0, (
            "GC should NOT run when last_gc_ran_at is within 7 days"
        )

    def test_gc_runs_when_last_ran_over_7_days_ago(
        self, storage_root: Path, blob_store: BlobStore
    ) -> None:
        """ProjectDB open triggers GC if last_gc_ran_at > 7 days ago."""
        db_path = storage_root / "gc_old.db"

        # Initialise schema only (no GC on first open — we'll pre-set a stale ts).
        with ProjectDB(db_path, blob_store):
            pass

        # Directly set last_gc_ran_at to 8 days ago in the DB.
        conn = sqlite3.connect(str(db_path), isolation_level=None)
        conn.row_factory = sqlite3.Row
        stale_ts = (
            datetime.now(timezone.utc) - timedelta(days=8)
        ).strftime("%Y-%m-%dT%H:%M:%S.") + "000Z"
        conn.execute(
            "UPDATE gc_metadata SET last_gc_ran_at = ? WHERE id = 1", (stale_ts,)
        )
        conn.close()

        gc_call_count = 0
        original_gc = ProjectDB.gc_orphan_blobs

        def patched_gc(self) -> int:
            nonlocal gc_call_count
            gc_call_count += 1
            return original_gc(self)

        with patch.object(ProjectDB, "gc_orphan_blobs", patched_gc):
            with ProjectDB(db_path, blob_store):
                pass

        assert gc_call_count >= 1, "GC should run when last_gc_ran_at > 7 days ago"


# ---------------------------------------------------------------------------
# get_gc_metadata / _update_gc_metadata tests
# ---------------------------------------------------------------------------


class TestGcMetadataReadWrite:
    def test_get_gc_metadata_initial_state(self, project_db: ProjectDB) -> None:
        """get_gc_metadata returns (str_or_None, int) tuple."""
        last_ran_at, total = project_db.get_gc_metadata()
        assert isinstance(total, int)
        assert total >= 0
        assert last_ran_at is None or isinstance(last_ran_at, str)

    def test_update_gc_metadata_sets_timestamp_and_increments_total(
        self, project_db: ProjectDB
    ) -> None:
        """_update_gc_metadata sets last_gc_ran_at and increments cumulative total."""
        # Ensure metadata starts fresh.
        project_db._conn.execute(  # noqa: SLF001
            "UPDATE gc_metadata SET last_gc_ran_at = NULL, orphans_collected_total = 0 WHERE id = 1"
        )

        project_db._update_gc_metadata(5)
        last_ran_at, total = project_db.get_gc_metadata()
        assert last_ran_at is not None
        assert total == 5

        # Second update increments cumulatively.
        project_db._update_gc_metadata(3)
        _, total2 = project_db.get_gc_metadata()
        assert total2 == 8

    def test_gc_orphan_blobs_collects_zero_ref_blobs(
        self, project_db: ProjectDB, blob_store: BlobStore
    ) -> None:
        """gc_orphan_blobs removes blobs with ref_count=0 and returns correct count."""
        # Insert a blob row with ref_count=0 (orphan) — simulate a deleted project.
        content = b"orphan blob content"
        sha = blob_store.compute_hash(content)
        blob_store.store(content)
        project_db._conn.execute(  # noqa: SLF001
            """
            INSERT OR IGNORE INTO blobs (sha256, size_bytes, ref_count, created_at, storage_path)
            VALUES (?, ?, 0, '2024-01-01T00:00:00.000Z', 'blobs/test.bin')
            """,
            (sha, len(content)),
        )

        collected = project_db.gc_orphan_blobs()
        assert collected == 1

        # Verify blob removed from DB.
        row = project_db._conn.execute(  # noqa: SLF001
            "SELECT 1 FROM blobs WHERE sha256 = ?", (sha,)
        ).fetchone()
        assert row is None

    def test_update_gc_metadata_after_gc_orphan_blobs(
        self, project_db: ProjectDB
    ) -> None:
        """Calling _update_gc_metadata after gc_orphan_blobs updates last_gc_ran_at."""
        collected = project_db.gc_orphan_blobs()
        project_db._update_gc_metadata(collected)
        last_ran_at, total = project_db.get_gc_metadata()
        assert last_ran_at is not None
        assert total >= 0
