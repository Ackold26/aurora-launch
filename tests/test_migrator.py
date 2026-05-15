"""S-01 schema migrator tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from aurora_launch.persistence.migrator import (
    Migration,
    MigrationError,
    apply_migration,
    apply_pending_migrations,
    discover_migrations,
    get_current_version,
)


class TestMigrationFromPath:
    def test_valid_filename(self) -> None:
        m = Migration.from_path(Path("v001_initial.sql"))
        assert m is not None
        assert m.version == 1
        assert m.name == "v001_initial"

    def test_4_digit_version(self) -> None:
        m = Migration.from_path(Path("v0042_add_telemetry.sql"))
        assert m is not None
        assert m.version == 42

    def test_invalid_filename_returns_none(self) -> None:
        assert Migration.from_path(Path("schema.sql")) is None
        assert Migration.from_path(Path("v_initial.sql")) is None
        assert Migration.from_path(Path("v001.sql")) is None  # missing description


class TestDiscoverMigrations:
    def test_discovers_sorted(self, tmp_path: Path) -> None:
        (tmp_path / "v001_initial.sql").write_text("SELECT 1;", encoding="utf-8")
        (tmp_path / "v002_second.sql").write_text("SELECT 2;", encoding="utf-8")
        (tmp_path / "v003_third.sql").write_text("SELECT 3;", encoding="utf-8")
        migs = discover_migrations(tmp_path)
        assert [m.version for m in migs] == [1, 2, 3]

    def test_missing_directory_raises(self, tmp_path: Path) -> None:
        with pytest.raises(MigrationError, match="not found"):
            discover_migrations(tmp_path / "nonexistent")

    def test_duplicate_version_raises(self, tmp_path: Path) -> None:
        (tmp_path / "v001_initial.sql").write_text("--", encoding="utf-8")
        (tmp_path / "v001_other.sql").write_text("--", encoding="utf-8")
        with pytest.raises(MigrationError, match="Duplicate"):
            discover_migrations(tmp_path)

    def test_gap_detected(self, tmp_path: Path) -> None:
        (tmp_path / "v001_initial.sql").write_text("--", encoding="utf-8")
        (tmp_path / "v003_third.sql").write_text("--", encoding="utf-8")
        with pytest.raises(MigrationError, match="gap"):
            discover_migrations(tmp_path)

    def test_skips_non_sql_files(self, tmp_path: Path) -> None:
        (tmp_path / "v001_initial.sql").write_text("SELECT 1;", encoding="utf-8")
        (tmp_path / "README.md").write_text("docs", encoding="utf-8")
        (tmp_path / "old.txt").write_text("note", encoding="utf-8")
        migs = discover_migrations(tmp_path)
        assert len(migs) == 1


class TestGetCurrentVersion:
    def test_fresh_db_returns_zero(self, tmp_path: Path) -> None:
        conn = sqlite3.connect(tmp_path / "test.db")
        conn.row_factory = sqlite3.Row
        try:
            assert get_current_version(conn) == 0
        finally:
            conn.close()

    def test_returns_max_version(self, tmp_path: Path) -> None:
        conn = sqlite3.connect(tmp_path / "test.db")
        conn.row_factory = sqlite3.Row
        try:
            conn.executescript("""
                CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT);
                INSERT INTO schema_version VALUES (1, '2026-01-01');
                INSERT INTO schema_version VALUES (3, '2026-01-03');
                INSERT INTO schema_version VALUES (2, '2026-01-02');
            """)
            assert get_current_version(conn) == 3
        finally:
            conn.close()


class TestApplyMigration:
    def test_applies_sql_script(self, tmp_path: Path) -> None:
        script = tmp_path / "v001_test.sql"
        script.write_text(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL
            );
            INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (1, 'now');
            CREATE TABLE foo (id INTEGER PRIMARY KEY);
            """,
            encoding="utf-8",
        )
        conn = sqlite3.connect(tmp_path / "test.db")
        conn.row_factory = sqlite3.Row
        try:
            m = Migration.from_path(script)
            assert m is not None
            apply_migration(conn, m)
            # Verify foo table exists
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='foo'"
            ).fetchone()
            assert row is not None
        finally:
            conn.close()


class TestApplyPendingMigrations:
    def test_fresh_db_applies_all(self, tmp_path: Path) -> None:
        mig_dir = tmp_path / "migrations"
        mig_dir.mkdir()
        (mig_dir / "v001_initial.sql").write_text("""
            CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT);
            INSERT INTO schema_version VALUES (1, 'now');
            CREATE TABLE t1 (id INTEGER);
        """, encoding="utf-8")
        (mig_dir / "v002_add_t2.sql").write_text("""
            INSERT INTO schema_version VALUES (2, 'now');
            CREATE TABLE t2 (id INTEGER);
        """, encoding="utf-8")

        conn = sqlite3.connect(tmp_path / "test.db")
        conn.row_factory = sqlite3.Row
        try:
            applied = apply_pending_migrations(conn, mig_dir)
            assert len(applied) == 2
            assert [m.version for m in applied] == [1, 2]
            assert get_current_version(conn) == 2
        finally:
            conn.close()

    def test_idempotent_second_run(self, tmp_path: Path) -> None:
        mig_dir = tmp_path / "migrations"
        mig_dir.mkdir()
        (mig_dir / "v001_initial.sql").write_text("""
            CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT);
            INSERT OR IGNORE INTO schema_version VALUES (1, 'now');
        """, encoding="utf-8")

        conn = sqlite3.connect(tmp_path / "test.db")
        conn.row_factory = sqlite3.Row
        try:
            applied1 = apply_pending_migrations(conn, mig_dir)
            applied2 = apply_pending_migrations(conn, mig_dir)
            assert len(applied1) == 1
            assert len(applied2) == 0  # already applied
        finally:
            conn.close()

    def test_partial_applied_adds_only_new(self, tmp_path: Path) -> None:
        mig_dir = tmp_path / "migrations"
        mig_dir.mkdir()
        (mig_dir / "v001_initial.sql").write_text("""
            CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT);
            INSERT OR IGNORE INTO schema_version VALUES (1, 'now');
        """, encoding="utf-8")

        conn = sqlite3.connect(tmp_path / "test.db")
        conn.row_factory = sqlite3.Row
        try:
            apply_pending_migrations(conn, mig_dir)
            # Now add a new migration v002
            (mig_dir / "v002_added.sql").write_text("""
                INSERT INTO schema_version VALUES (2, 'now');
                CREATE TABLE added_table (id INTEGER);
            """, encoding="utf-8")
            applied = apply_pending_migrations(conn, mig_dir)
            assert len(applied) == 1
            assert applied[0].version == 2
        finally:
            conn.close()

    def test_self_registers_if_script_forgot(self, tmp_path: Path) -> None:
        """If migration script lacks INSERT INTO schema_version, migrator injects."""
        mig_dir = tmp_path / "migrations"
        mig_dir.mkdir()
        # First migration sets up table
        (mig_dir / "v001_setup.sql").write_text("""
            CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT);
            INSERT INTO schema_version VALUES (1, 'now');
        """, encoding="utf-8")
        # Second forgets to register
        (mig_dir / "v002_forgetful.sql").write_text("""
            CREATE TABLE forgotten (id INTEGER);
        """, encoding="utf-8")

        conn = sqlite3.connect(tmp_path / "test.db")
        conn.row_factory = sqlite3.Row
        try:
            apply_pending_migrations(conn, mig_dir)
            assert get_current_version(conn) == 2
        finally:
            conn.close()


class TestProjectDBIntegration:
    def test_real_v001_initial_applies(self, tmp_path: Path) -> None:
        """Verify real Aurora Launch migrations apply cleanly through ProjectDB.

        Updated for v002 (S-07 gc_metadata): version is now 2 after open.
        """
        from aurora_launch.persistence.blob_store import BlobStore
        from aurora_launch.persistence.project_db import CURRENT_SCHEMA_VERSION, ProjectDB

        bs_dir = tmp_path / "blobs"
        bs_dir.mkdir()
        bs = BlobStore(bs_dir)
        db = ProjectDB(tmp_path / "projects.db", bs)
        try:
            # Migrator ran in __init__. Version should match CURRENT_SCHEMA_VERSION.
            row = db._conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
            assert row["v"] == CURRENT_SCHEMA_VERSION
            # Core tables exist (v001) + gc_metadata (v002)
            tables = {
                r["name"]
                for r in db._conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            assert {
                "projects", "versions", "version_files", "blobs",
                "schema_version", "gc_metadata",
            } <= tables
        finally:
            db.close()
