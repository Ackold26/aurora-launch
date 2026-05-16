"""DB migration system integration tests (ROADMAP 2.5).

Verifies the schema migration pipeline that protects pilot customers'
project databases from breaking when Aurora Launch ships new versions.

Architecture recap (as implemented):
- `schema_version` table (not `_db_meta`) tracks applied migrations.
- `migrator.apply_pending_migrations()` is called from `ProjectDB._apply_schema()`
  on every open — idempotent, forward-only.
- Migration scripts live in `persistence/migrations/vNNN_<desc>.sql`.
- `CURRENT_SCHEMA_VERSION` constant in project_db.py tracks expected ceiling.

Test matrix
-----------
Test 1  — fresh DB gets `schema_version` table with MAX(version) == CURRENT_SCHEMA_VERSION
Test 2  — legacy DB (no `schema_version` table) gets migrated on ProjectDB open
Test 3  — repeated ProjectDB open on same file: idempotent, no error, no duplicate rows
Test 4  — adding a synthetic v003 SQL migration to a temp dir applies it and
           bumps MAX(version) to 3 (verifies the extensible skeleton works)
Test 5  — DB created at schema version N, but code reports CURRENT_SCHEMA_VERSION < N:
           ProjectDB raises ProjectDBError (newer-than-supported guard)
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path
from textwrap import dedent

import pytest

from aurora_launch.persistence.blob_store import BlobStore
from aurora_launch.persistence.migrator import (
    apply_pending_migrations,
    get_current_version,
)
from aurora_launch.persistence.project_db import (
    CURRENT_SCHEMA_VERSION,
    MIGRATIONS_DIR,
    ProjectDB,
    ProjectDBError,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def blob_store(tmp_path: Path) -> BlobStore:
    blobs_dir = tmp_path / "blobs"
    blobs_dir.mkdir()
    return BlobStore(blobs_dir)


def _open_db(db_path: Path, blob_store: BlobStore) -> ProjectDB:
    """Helper: open ProjectDB and return it; caller must close."""
    return ProjectDB(db_path, blob_store)


# ---------------------------------------------------------------------------
# Test 1 — fresh DB initialises schema_version to CURRENT_SCHEMA_VERSION
# ---------------------------------------------------------------------------


class TestFreshDbSchemaVersion:
    """ROADMAP 2.5 / Test 1: first open of a brand-new database."""

    def test_schema_version_table_exists(self, tmp_path: Path, blob_store: BlobStore) -> None:
        db = _open_db(tmp_path / "projects.db", blob_store)
        try:
            row = db._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
            ).fetchone()
            assert row is not None, "schema_version table must exist after fresh open"
        finally:
            db.close()

    def test_schema_version_equals_current(self, tmp_path: Path, blob_store: BlobStore) -> None:
        db = _open_db(tmp_path / "projects.db", blob_store)
        try:
            row = db._conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS v FROM schema_version"
            ).fetchone()
            assert row["v"] == CURRENT_SCHEMA_VERSION, (
                f"Expected schema version {CURRENT_SCHEMA_VERSION}, got {row['v']}"
            )
        finally:
            db.close()

    def test_all_expected_tables_created(self, tmp_path: Path, blob_store: BlobStore) -> None:
        """v001 + v002 migrations create the full set of tables."""
        db = _open_db(tmp_path / "projects.db", blob_store)
        try:
            tables = {
                r[0]
                for r in db._conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            required = {"projects", "versions", "version_files", "blobs", "schema_version", "gc_metadata"}
            assert required <= tables, f"Missing tables: {required - tables}"
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Test 2 — legacy DB (no schema_version table) migrates on open
# ---------------------------------------------------------------------------


class TestLegacyDbMigration:
    """ROADMAP 2.5 / Test 2: simulate a DB from before the migration system existed."""

    def _make_legacy_db(self, db_path: Path) -> None:
        """Create a minimal pre-migration SQLite file (no schema_version table)."""
        conn = sqlite3.connect(str(db_path))
        conn.executescript(dedent("""
            CREATE TABLE projects (
                project_uuid TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_modified TEXT NOT NULL,
                aurora_app_version TEXT NOT NULL,
                aurora_launch_schema_version TEXT NOT NULL DEFAULT '1.0',
                current_version_id INTEGER,
                granularity TEXT NOT NULL DEFAULT 'monthly',
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE versions (
                version_id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_uuid TEXT NOT NULL,
                parent_version_id INTEGER,
                revision INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                label TEXT,
                decision_note TEXT,
                recipient_data_hash TEXT,
                composite_bundle_hash TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                UNIQUE (project_uuid, revision)
            );
            CREATE TABLE version_files (
                version_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                blob_sha256 TEXT NOT NULL,
                schema_version TEXT,
                PRIMARY KEY (version_id, file_path)
            );
            CREATE TABLE blobs (
                sha256 TEXT PRIMARY KEY,
                size_bytes INTEGER NOT NULL,
                ref_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                storage_path TEXT NOT NULL
            );
        """))
        conn.close()

    def test_legacy_db_opens_without_error(self, tmp_path: Path, blob_store: BlobStore) -> None:
        db_path = tmp_path / "legacy.db"
        self._make_legacy_db(db_path)
        # Should not raise — migrator detects missing schema_version and applies all migrations
        db = _open_db(db_path, blob_store)
        db.close()

    def test_legacy_db_gets_schema_version_after_open(
        self, tmp_path: Path, blob_store: BlobStore
    ) -> None:
        db_path = tmp_path / "legacy.db"
        self._make_legacy_db(db_path)

        # Verify legacy state: no schema_version table
        conn_check = sqlite3.connect(str(db_path))
        pre = conn_check.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchone()
        conn_check.close()
        assert pre is None, "Precondition: legacy DB must not have schema_version table"

        # Open via ProjectDB — migration must run
        db = _open_db(db_path, blob_store)
        try:
            row = db._conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS v FROM schema_version"
            ).fetchone()
            assert row["v"] == CURRENT_SCHEMA_VERSION, (
                f"Legacy DB should have been migrated to v{CURRENT_SCHEMA_VERSION}, got {row['v']}"
            )
        finally:
            db.close()

    def test_legacy_db_preserves_existing_data(self, tmp_path: Path, blob_store: BlobStore) -> None:
        """Migration must not destroy pre-existing project rows."""
        db_path = tmp_path / "legacy.db"
        self._make_legacy_db(db_path)

        # Manually insert a project row before migration
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO projects VALUES (?,?,?,?,?,?,?,?,?)",
            ("uuid-legacy-001", "Old Project", "2026-01-01T00:00:00Z",
             "2026-01-01T00:00:00Z", "0.0.1", "1.0", None, "monthly", "{}"),
        )
        conn.commit()
        conn.close()

        db = _open_db(db_path, blob_store)
        try:
            projects = db.list_projects()
            assert any(p.project_uuid == "uuid-legacy-001" for p in projects), (
                "Migration must not destroy existing project data"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Test 3 — idempotency: second open on same DB is a no-op
# ---------------------------------------------------------------------------


class TestMigrationIdempotency:
    """ROADMAP 2.5 / Test 3: repeated open must not error or duplicate rows."""

    def test_second_open_same_schema_version(self, tmp_path: Path, blob_store: BlobStore) -> None:
        db_path = tmp_path / "projects.db"

        db1 = _open_db(db_path, blob_store)
        db1.close()

        db2 = _open_db(db_path, blob_store)
        try:
            row = db2._conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS v FROM schema_version"
            ).fetchone()
            assert row["v"] == CURRENT_SCHEMA_VERSION
        finally:
            db2.close()

    def test_no_duplicate_schema_version_rows(self, tmp_path: Path, blob_store: BlobStore) -> None:
        """schema_version uses INTEGER PRIMARY KEY — duplicates would raise.
        We verify the count equals exactly the number of migrations applied."""
        db_path = tmp_path / "projects.db"

        # Open three times
        for _ in range(3):
            db = _open_db(db_path, blob_store)
            db.close()

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            count = conn.execute("SELECT COUNT(*) AS n FROM schema_version").fetchone()["n"]
            # Each migration file inserts exactly one row; CURRENT_SCHEMA_VERSION == number of migrations
            assert count == CURRENT_SCHEMA_VERSION, (
                f"Expected {CURRENT_SCHEMA_VERSION} rows in schema_version, got {count}"
            )
        finally:
            conn.close()

    def test_projects_survive_multi_open(self, tmp_path: Path, blob_store: BlobStore) -> None:
        """Existing project data must not be affected by repeated migrations."""
        db_path = tmp_path / "projects.db"

        db1 = _open_db(db_path, blob_store)
        pid = db1.create_project("Idempotency Test", "0.1.0")
        db1.close()

        db2 = _open_db(db_path, blob_store)
        db2.close()

        db3 = _open_db(db_path, blob_store)
        try:
            projects = db3.list_projects()
            assert any(p.project_uuid == pid for p in projects)
        finally:
            db3.close()


# ---------------------------------------------------------------------------
# Test 4 — synthetic future migration skeleton (dry-run v004, since v003
# became real in Phase 1.B.1 — kv_store)
# ---------------------------------------------------------------------------


class TestFutureMigrationSkeleton:
    """ROADMAP 2.5 / Test 4: confirm that adding a new SQL file to migrations/
    is all it takes to extend the schema. Uses a temp copy of migrations dir.

    Synthetic version bumped to v004 since v003 (kv_store) became real в
    Phase 1.B.1 для ConsentManager persistence.
    """

    def test_new_sql_migration_bumps_schema_version(self, tmp_path: Path) -> None:
        """Copy real migrations dir, add synthetic v004, run migrator on a
        bare connection.

        Validates the extensible skeleton: anyone adding a new SQL file
        in the future gets automatic pick-up on next app launch.
        """
        mig_copy = tmp_path / "migrations"
        shutil.copytree(MIGRATIONS_DIR, mig_copy)

        # Write synthetic v004 migration (next after real v003 _kv_store)
        (mig_copy / "v004_test_column.sql").write_text(
            dedent("""
                -- Test migration: add optional tag to projects
                ALTER TABLE projects ADD COLUMN _test_tag TEXT;
                INSERT OR REPLACE INTO schema_version (version, applied_at)
                VALUES (4, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
            """),
            encoding="utf-8",
        )

        # Build a real DB that is already at v1 + v2 + v3 (use real migrations)
        conn = sqlite3.connect(str(tmp_path / "test_v004.db"))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")

        try:
            # Apply real v001 + v002 + v003 first
            real_mig_dir = MIGRATIONS_DIR
            apply_pending_migrations(conn, real_mig_dir)
            assert get_current_version(conn) == CURRENT_SCHEMA_VERSION

            # Now apply real + synthetic v004 from the copy
            applied = apply_pending_migrations(conn, mig_copy)
            assert len(applied) == 1, f"Expected 1 new migration applied, got {len(applied)}"
            assert applied[0].version == 4

            assert get_current_version(conn) == 4

            # v004 table alteration must have taken effect
            cols = [
                r[1]
                for r in conn.execute("PRAGMA table_info(projects)").fetchall()
            ]
            assert "_test_tag" in cols, "Column _test_tag must exist after v004 migration"
        finally:
            conn.close()

    def test_empty_migrations_dict_constant_ready(self) -> None:
        """Verifies MIGRATIONS_DIR constant is accessible from project_db module
        and points to an existing directory — the 'skeleton is ready' contract."""
        assert MIGRATIONS_DIR.is_dir(), f"MIGRATIONS_DIR not found: {MIGRATIONS_DIR}"
        sql_files = sorted(MIGRATIONS_DIR.glob("v*.sql"))
        assert len(sql_files) >= 1, "At least one migration SQL file must exist"
        # Filenames follow vNNN_ convention
        for f in sql_files:
            assert f.name.startswith("v"), f"Migration file {f.name} must start with 'v'"


# ---------------------------------------------------------------------------
# Test 5 — ProjectDB rejects DB newer than CURRENT_SCHEMA_VERSION
# ---------------------------------------------------------------------------


class TestFutureSchemaGuard:
    """ROADMAP 2.5 bonus: guard against opening a DB from a newer app version."""

    def test_newer_schema_raises_project_db_error(
        self, tmp_path: Path, blob_store: BlobStore
    ) -> None:
        """Simulate a DB stamped with a future schema version that the current
        binary doesn't know about. ProjectDB must refuse to open it."""
        db_path = tmp_path / "future.db"

        # Bootstrap a valid v1+v2 DB first
        db = _open_db(db_path, blob_store)
        db.close()

        # Manually inject a fake v999 record to simulate a newer binary having run
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (999, 'future')"
        )
        conn.commit()
        conn.close()

        with pytest.raises(ProjectDBError, match="newer than supported"):
            _open_db(db_path, blob_store)


# ---------------------------------------------------------------------------
# Test 6 — v003 _kv_store + kv_get/kv_set methods (Phase 1.B.1 C-2 fix)
# ---------------------------------------------------------------------------


class TestKvStoreV003:
    """Phase 1.B.1 / C-2 audit fix: v003 migration creates _kv_store table +
    ProjectDB.kv_get/kv_set methods provide real persistence для
    ConsentManager (auto-refresh §3.5), wizard recovery (1.C BTA-2), tip
    dismissals (UX-3), telemetry tier (Phase 2.D.2).
    """

    def test_kv_store_table_created_after_v003(
        self, tmp_path: Path, blob_store: BlobStore
    ) -> None:
        """Fresh DB должен иметь таблицу _kv_store (создаётся v003 migration)."""
        db_path = tmp_path / "kv.db"
        db = _open_db(db_path, blob_store)
        try:
            row = db._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='_kv_store'"
            ).fetchone()
            assert row is not None, "_kv_store table должна существовать после v003"
        finally:
            db.close()

    def test_kv_set_then_get_round_trip(
        self, tmp_path: Path, blob_store: BlobStore
    ) -> None:
        db = _open_db(tmp_path / "kv.db", blob_store)
        try:
            db.kv_set("test_key", {"foo": "bar", "n": 42})
            result = db.kv_get("test_key")
            assert result == {"foo": "bar", "n": 42}
        finally:
            db.close()

    def test_kv_get_missing_returns_none(
        self, tmp_path: Path, blob_store: BlobStore
    ) -> None:
        db = _open_db(tmp_path / "kv.db", blob_store)
        try:
            assert db.kv_get("never_set") is None
        finally:
            db.close()

    def test_kv_set_updates_existing_key(
        self, tmp_path: Path, blob_store: BlobStore
    ) -> None:
        """INSERT OR REPLACE pattern: повторный set перезаписывает значение."""
        db = _open_db(tmp_path / "kv.db", blob_store)
        try:
            db.kv_set("counter", {"value": 1})
            db.kv_set("counter", {"value": 99})
            assert db.kv_get("counter") == {"value": 99}
        finally:
            db.close()

    def test_kv_set_non_dict_raises_type_error(
        self, tmp_path: Path, blob_store: BlobStore
    ) -> None:
        """Defensive type check: ProjectDB только dict хранит, не arbitrary JSON."""
        db = _open_db(tmp_path / "kv.db", blob_store)
        try:
            with pytest.raises(TypeError, match="kv_set value must be dict"):
                db.kv_set("bad", "not a dict")  # type: ignore[arg-type]
        finally:
            db.close()

    def test_kv_delete_returns_true_if_existed(
        self, tmp_path: Path, blob_store: BlobStore
    ) -> None:
        db = _open_db(tmp_path / "kv.db", blob_store)
        try:
            db.kv_set("ephemeral", {"x": 1})
            assert db.kv_delete("ephemeral") is True
            assert db.kv_get("ephemeral") is None
            # Repeat delete on missing key → False
            assert db.kv_delete("ephemeral") is False
        finally:
            db.close()

    def test_kv_persistence_across_db_close_reopen(
        self, tmp_path: Path, blob_store: BlobStore
    ) -> None:
        """The actual C-2 fix verification: данные переживают close + reopen.
        Раньше ConsentManager использовал _DbKvShim который проглатывал
        AttributeError — после restart consent был None."""
        db_path = tmp_path / "persist.db"
        db1 = _open_db(db_path, blob_store)
        db1.kv_set("consent", {"enabled": True, "frequency": "weekly"})
        db1.close()

        db2 = _open_db(db_path, blob_store)
        try:
            assert db2.kv_get("consent") == {"enabled": True, "frequency": "weekly"}
        finally:
            db2.close()

    def test_kv_get_invalid_json_returns_none(
        self, tmp_path: Path, blob_store: BlobStore
    ) -> None:
        """Если в _kv_store попал invalid JSON (corruption) — graceful None,
        не crash. Логирование через _log.warning."""
        db = _open_db(tmp_path / "kv.db", blob_store)
        try:
            # Bypass normal kv_set → write garbage directly
            db._conn.execute(
                "INSERT INTO _kv_store (key, value_json, updated_at) "
                "VALUES ('garbage', '{not valid json', '2026-01-01T00:00:00Z')"
            )
            db._conn.commit()
            assert db.kv_get("garbage") is None
        finally:
            db.close()
