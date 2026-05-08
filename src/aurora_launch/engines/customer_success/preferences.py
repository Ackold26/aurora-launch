"""User preferences store с cross-device sync foundation (B1.5)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional
from uuid import UUID

from aurora_launch.schemas.customer_success import UserPreferences


_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_preferences (
    customer_id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    sync_status TEXT NOT NULL DEFAULT 'pending'
);
"""


class PreferencesStore:
    """SQLite-backed user preferences. Last-write-wins conflict resolution."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def load(self, customer_id: UUID) -> UserPreferences:
        """Load preferences. Returns defaults если not set."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT payload_json FROM user_preferences WHERE customer_id = ?",
                (str(customer_id),),
            )
            row = cursor.fetchone()
        finally:
            conn.close()

        if row is None:
            return UserPreferences(customer_id=customer_id)

        payload = json.loads(row[0])
        return UserPreferences(**payload)

    def save(self, prefs: UserPreferences) -> None:
        """Save с last-write-wins (replaces existing)."""
        from datetime import datetime, timezone
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO user_preferences "
                "(customer_id, payload_json, updated_at, sync_status) "
                "VALUES (?, ?, ?, 'pending')",
                (
                    str(prefs.customer_id),
                    prefs.model_dump_json(),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_pending_sync(self) -> list[UserPreferences]:
        """Fetch preferences not yet synced."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT payload_json FROM user_preferences WHERE sync_status = 'pending'"
            )
            rows = cursor.fetchall()
        finally:
            conn.close()

        return [UserPreferences(**json.loads(r[0])) for r in rows]
