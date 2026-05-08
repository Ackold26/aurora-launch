"""Customer Success consulting log tracker (B1.5).

SQLite local store + sync queue. Real implementation — replaces v0.1.x B1.5 stubs.

Per audit M12: cross-device sync via aurora-platform-core C5 license module.
Local SQLite = cache + offline buffer; sync to staging/prod при online.
"""

from __future__ import annotations

import csv
import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import StringIO
from pathlib import Path
from typing import Optional
from uuid import UUID

from aurora_launch.schemas.customer_success import (
    ConsultingLogEntry,
    EventType,
    UsageSummary,
)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS consulting_log (
    event_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    machine_id TEXT NOT NULL,
    timestamp_start TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    project_id TEXT,
    notes TEXT,
    consulting_hours_charged TEXT NOT NULL,
    sync_status TEXT NOT NULL DEFAULT 'pending'
);
CREATE INDEX IF NOT EXISTS ix_consulting_log_customer
    ON consulting_log(customer_id, timestamp_start);
CREATE INDEX IF NOT EXISTS ix_consulting_log_sync
    ON consulting_log(sync_status);
"""


class CustomerSuccessTracker:
    """SQLite-backed consulting log tracker.

    Idempotent — same event_id won't double-log (per audit AC1.5.8).
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def log_event(self, entry: ConsultingLogEntry) -> bool:
        """Insert event. Returns True if new, False if duplicate event_id (idempotent)."""
        conn = sqlite3.connect(self.db_path)
        try:
            try:
                conn.execute(
                    "INSERT INTO consulting_log "
                    "(event_id, customer_id, machine_id, timestamp_start, duration_minutes, "
                    "event_type, project_id, notes, consulting_hours_charged, sync_status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')",
                    (
                        str(entry.event_id),
                        str(entry.customer_id),
                        str(entry.machine_id),
                        entry.timestamp_start.isoformat(),
                        entry.duration_minutes,
                        entry.event_type,
                        str(entry.project_id) if entry.project_id else None,
                        entry.notes,
                        str(entry.consulting_hours_charged),
                    ),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                # Duplicate event_id — idempotent no-op
                return False
        finally:
            conn.close()

    def get_usage_summary(
        self,
        customer_id: UUID,
        period_start: datetime,
        period_end: datetime,
        total_hours_allowed: Decimal,
    ) -> UsageSummary:
        """Aggregate usage для period."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT event_type, duration_minutes, consulting_hours_charged, project_id "
                "FROM consulting_log "
                "WHERE customer_id = ? AND timestamp_start >= ? AND timestamp_start < ?",
                (str(customer_id), period_start.isoformat(), period_end.isoformat()),
            )
            rows = list(cursor.fetchall())
        finally:
            conn.close()

        total_hours = sum((Decimal(r[2]) for r in rows), Decimal("0"))
        breakdown: dict[str, Decimal] = {}
        for row in rows:
            event_type = row[0]
            hours = Decimal(row[2])
            breakdown[event_type] = breakdown.get(event_type, Decimal("0")) + hours

        # Count distinct projects → launches
        project_ids = {r[3] for r in rows if r[3] is not None}
        n_launches_initiated = len(project_ids)

        # Heuristic: launches "completed" = projects with report_review event
        n_launches_completed = sum(
            1 for r in rows if r[0] == "report_review"
        )

        n_posterior_updates = sum(1 for r in rows if r[0] == "posterior_update")

        return UsageSummary(
            period_start=period_start,
            period_end=period_end,
            total_hours_used=total_hours,
            total_hours_allowed=total_hours_allowed,
            breakdown_by_event_type=breakdown,
            n_launches_initiated=n_launches_initiated,
            n_launches_completed=n_launches_completed,
            n_posterior_updates=n_posterior_updates,
        )

    def get_pending_sync_entries(self, limit: int = 100) -> list[ConsultingLogEntry]:
        """Fetch entries not yet synced к aurora-platform staging/prod."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT event_id, customer_id, machine_id, timestamp_start, duration_minutes, "
                "event_type, project_id, notes, consulting_hours_charged "
                "FROM consulting_log "
                "WHERE sync_status = 'pending' "
                "ORDER BY timestamp_start "
                "LIMIT ?",
                (limit,),
            )
            rows = list(cursor.fetchall())
        finally:
            conn.close()

        entries: list[ConsultingLogEntry] = []
        for row in rows:
            entries.append(ConsultingLogEntry(
                event_id=UUID(row[0]),
                customer_id=UUID(row[1]),
                machine_id=UUID(row[2]),
                timestamp_start=datetime.fromisoformat(row[3]),
                duration_minutes=row[4],
                event_type=row[5],
                project_id=UUID(row[6]) if row[6] else None,
                notes=row[7],
                consulting_hours_charged=Decimal(row[8]),
            ))
        return entries

    def mark_synced(self, event_ids: list[UUID]) -> int:
        """Mark events as synced (called after successful upload к platform)."""
        if not event_ids:
            return 0
        conn = sqlite3.connect(self.db_path)
        try:
            placeholders = ",".join("?" * len(event_ids))
            cursor = conn.execute(
                f"UPDATE consulting_log SET sync_status = 'synced' "
                f"WHERE event_id IN ({placeholders})",
                [str(eid) for eid in event_ids],
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def predict_depletion(
        self,
        customer_id: UUID,
        hours_remaining: Decimal,
        lookback_weeks: int = 4,
    ) -> Optional[int]:
        """Linear extrapolation от recent usage rate.

        Returns ETA в days, или None if no recent activity.
        """
        period_end = datetime.now(timezone.utc)
        period_start = period_end - timedelta(weeks=lookback_weeks)

        summary = self.get_usage_summary(
            customer_id=customer_id,
            period_start=period_start,
            period_end=period_end,
            total_hours_allowed=Decimal("0"),  # not used
        )

        if summary.total_hours_used == Decimal("0"):
            return None

        # Hours per day (rolling rate)
        days_elapsed = (period_end - period_start).total_seconds() / 86400
        hours_per_day = summary.total_hours_used / Decimal(days_elapsed)

        if hours_per_day == Decimal("0"):
            return None

        days_until_depletion = hours_remaining / hours_per_day
        return int(days_until_depletion)

    def export_csv(
        self,
        customer_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> str:
        """CSV export для billing."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT event_id, timestamp_start, event_type, duration_minutes, "
                "project_id, notes, consulting_hours_charged "
                "FROM consulting_log "
                "WHERE customer_id = ? AND timestamp_start >= ? AND timestamp_start < ? "
                "ORDER BY timestamp_start",
                (str(customer_id), period_start.isoformat(), period_end.isoformat()),
            )
            rows = list(cursor.fetchall())
        finally:
            conn.close()

        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "event_id", "timestamp_start", "event_type", "duration_minutes",
            "project_id", "notes", "consulting_hours_charged",
        ])
        writer.writerows(rows)
        return buf.getvalue()


# Module-level convenience function
_default_tracker: Optional[CustomerSuccessTracker] = None


def log_event(
    entry: ConsultingLogEntry,
    db_path: Optional[Path] = None,
) -> bool:
    """Convenience function — uses default tracker если db_path не provided."""
    global _default_tracker
    if db_path:
        tracker = CustomerSuccessTracker(db_path)
    else:
        if _default_tracker is None:
            raise RuntimeError(
                "No default tracker initialized; provide db_path or initialize"
            )
        tracker = _default_tracker
    return tracker.log_event(entry)
