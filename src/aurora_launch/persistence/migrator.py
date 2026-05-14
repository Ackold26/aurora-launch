"""Simple monotonic schema migrator (S-01 audit fix).

Per master-plan v3.0 decision D-A8: simple version column + idempotent DDL files
вместо Alembic. No new dependencies, forward-only migrations, plain SQL files
в migrations/ directory.

File naming convention:
    migrations/v001_initial.sql       — version 1 baseline schema
    migrations/v002_add_telemetry.sql — version 2 incremental change
    migrations/vNNN_<description>.sql — vNNN starts at 1, monotonic

Migrator queries `schema_version` table for current `MAX(version)`, then
applies all files with version > current в lexicographic order. Each file
script SHOULD include `INSERT INTO schema_version (version, applied_at)`
at the end so future runs skip it.

Atomicity: each migration runs in its own transaction. If a migration fails,
the failing transaction rolls back; previous migrations remain applied.

Forward-only: no downgrade scripts (consistent с desktop app reality —
customers don't roll back).
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

_log = logging.getLogger(__name__)

# Filename pattern: vNNN_anything.sql (1-4 digits)
_MIGRATION_FILENAME_RE = re.compile(r"^v(\d{1,4})_[a-z0-9_]+\.sql$", re.IGNORECASE)


class MigrationError(RuntimeError):
    """Raised on migration application failure."""


@dataclass(frozen=True)
class Migration:
    """A single migration script discovered в migrations/ directory."""

    version: int
    name: str  # e.g., "v001_initial"
    path: Path

    @classmethod
    def from_path(cls, path: Path) -> "Migration | None":
        """Parse migration metadata from filename. Returns None if не matches pattern."""
        match = _MIGRATION_FILENAME_RE.match(path.name)
        if not match:
            return None
        return cls(
            version=int(match.group(1)),
            name=path.stem,
            path=path,
        )


def discover_migrations(migrations_dir: Path) -> list[Migration]:
    """Find all migration scripts в directory, sorted by version ascending."""
    if not migrations_dir.exists():
        raise MigrationError(f"Migrations directory not found: {migrations_dir}")

    migrations: list[Migration] = []
    for path in migrations_dir.iterdir():
        if not path.is_file() or path.suffix.lower() != ".sql":
            continue
        m = Migration.from_path(path)
        if m is None:
            _log.warning("Skipping non-conforming migration filename: %s", path.name)
            continue
        migrations.append(m)

    migrations.sort(key=lambda m: m.version)

    # Verify uniqueness + sequence (no gaps allowed)
    seen = set()
    for m in migrations:
        if m.version in seen:
            raise MigrationError(
                f"Duplicate migration version {m.version}: {m.path.name}"
            )
        seen.add(m.version)

    # Check for gaps: versions must be 1..N contiguous
    if migrations:
        expected = set(range(1, max(seen) + 1))
        missing = expected - seen
        if missing:
            raise MigrationError(
                f"Migration version gap detected. Missing: {sorted(missing)}"
            )

    return migrations


def get_current_version(conn) -> int:
    """Return MAX(version) from schema_version table, or 0 if не exists / empty.

    Note: `conn` may be sqlite3 OR sqlcipher3 connection — duck typed.
    We check table existence via sqlite_master to avoid catching different
    OperationalError classes from each library.
    """
    # First check if schema_version table exists. Works for both libs.
    has_table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ).fetchone()
    if not has_table:
        return 0
    row = conn.execute(
        "SELECT COALESCE(MAX(version), 0) AS v FROM schema_version"
    ).fetchone()
    if row is None:
        return 0
    return int(row[0]) if not hasattr(row, "keys") else int(row["v"])


_SQL_STATEMENT_SEPARATOR = ";"


def _split_sql_statements(sql: str) -> list[str]:
    """Naive SQL splitter — splits on `;` outside string literals + comments.

    Conservative: handles single-line `--` comments + single-quoted strings.
    Does NOT handle multi-line `/* ... */` comments or nested escapes —
    migration scripts должны avoid those constructs. Empty trimmed statements
    are filtered out.
    """
    statements: list[str] = []
    buf: list[str] = []
    in_string = False
    i = 0
    while i < len(sql):
        ch = sql[i]
        if not in_string and ch == "-" and i + 1 < len(sql) and sql[i + 1] == "-":
            # Single-line comment — skip к next newline
            nl = sql.find("\n", i)
            if nl == -1:
                break
            i = nl + 1
            buf.append("\n")
            continue
        if ch == "'":
            in_string = not in_string
            buf.append(ch)
            i += 1
            continue
        if ch == _SQL_STATEMENT_SEPARATOR and not in_string:
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def apply_migration(conn: sqlite3.Connection, migration: Migration) -> None:
    """Apply a single migration script atomically.

    Audit A-02 fix: `executescript` issues implicit COMMIT before execution,
    breaking transaction atomicity. We split на individual statements and run
    inside explicit BEGIN/COMMIT (or ROLLBACK on failure) so partial DDL never
    survives a mid-script error.

    Migration script SHOULD include `INSERT INTO schema_version` at end.
    Caller verifies version recorded после execution.
    """
    sql = migration.path.read_text(encoding="utf-8")
    statements = _split_sql_statements(sql)
    if not statements:
        raise MigrationError(
            f"Migration v{migration.version:03d} ({migration.name}) is empty"
        )
    _log.info(
        "Applying migration v%03d (%s) — %d statement(s)",
        migration.version,
        migration.name,
        len(statements),
    )

    # Begin explicit transaction. sqlite3 в Python uses implicit transactions
    # for DML by default; for DDL we must invoke BEGIN explicitly. The
    # isolation_level might be set to None (autocommit) by ProjectDB; we
    # don't rely on it. SAVEPOINT works across both modes.
    conn.execute("SAVEPOINT migration_apply")
    try:
        for stmt in statements:
            conn.execute(stmt)
    except sqlite3.Error as exc:
        conn.execute("ROLLBACK TO SAVEPOINT migration_apply")
        conn.execute("RELEASE SAVEPOINT migration_apply")
        raise MigrationError(
            f"Migration v{migration.version:03d} ({migration.name}) failed: {exc}"
        ) from exc
    else:
        conn.execute("RELEASE SAVEPOINT migration_apply")


def apply_pending_migrations(
    conn: sqlite3.Connection, migrations_dir: Path
) -> list[Migration]:
    """Discover + apply all migrations с version > current. Returns applied list.

    Idempotent: re-running after success applies nothing.
    """
    current = get_current_version(conn)
    all_migrations = discover_migrations(migrations_dir)
    pending = [m for m in all_migrations if m.version > current]

    if not pending:
        _log.debug(
            "No pending migrations. Current version: %d, available: %d",
            current,
            max((m.version for m in all_migrations), default=0),
        )
        return []

    _log.info(
        "Applying %d pending migration(s): v%03d → v%03d",
        len(pending),
        current,
        pending[-1].version,
    )

    applied: list[Migration] = []
    for migration in pending:
        apply_migration(conn, migration)
        # Verify migration registered itself
        new_current = get_current_version(conn)
        if new_current < migration.version:
            _log.warning(
                "Migration %s did not self-register; injecting schema_version row",
                migration.name,
            )
            conn.execute(
                "INSERT OR IGNORE INTO schema_version (version, applied_at) "
                "VALUES (?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))",
                (migration.version,),
            )
        applied.append(migration)

    final = get_current_version(conn)
    _log.info("Migration complete. Final version: v%03d (%d applied)", final, len(applied))
    return applied
