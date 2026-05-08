"""B1.5 Customer Success Lite tests."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import StringIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from aurora_launch.engines.customer_success import (
    CustomerSuccessTracker,
    PreferencesStore,
)
from aurora_launch.schemas.customer_success import (
    ConsultingLogEntry,
    UserPreferences,
)


@pytest.fixture
def tracker(tmp_path: Path) -> CustomerSuccessTracker:
    return CustomerSuccessTracker(tmp_path / "consulting.db")


@pytest.fixture
def customer_id() -> UUID:
    return UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def machine_id() -> UUID:
    return UUID("11111111-1111-1111-1111-111111111111")


def _make_entry(
    customer_id: UUID,
    machine_id: UUID,
    event_type: str = "proxy_review",
    duration_minutes: int = 60,
    hours_charged: str = "1.0",
    timestamp: datetime | None = None,
    project_id: UUID | None = None,
) -> ConsultingLogEntry:
    return ConsultingLogEntry(
        customer_id=customer_id,
        machine_id=machine_id,
        timestamp_start=timestamp or datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
        duration_minutes=duration_minutes,
        event_type=event_type,
        project_id=project_id,
        consulting_hours_charged=Decimal(hours_charged),
    )


class TestTrackerLogEvent:
    def test_log_returns_true_for_new(
        self, tracker: CustomerSuccessTracker, customer_id: UUID, machine_id: UUID
    ) -> None:
        entry = _make_entry(customer_id, machine_id)
        result = tracker.log_event(entry)
        assert result is True

    def test_log_idempotent_returns_false(
        self, tracker: CustomerSuccessTracker, customer_id: UUID, machine_id: UUID
    ) -> None:
        entry = _make_entry(customer_id, machine_id)
        tracker.log_event(entry)
        # Same event_id — should be no-op
        result = tracker.log_event(entry)
        assert result is False

    def test_multiple_distinct_events(
        self, tracker: CustomerSuccessTracker, customer_id: UUID, machine_id: UUID
    ) -> None:
        for i in range(5):
            entry = _make_entry(
                customer_id, machine_id,
                timestamp=datetime(2026, 5, 1, 10 + i, 0, tzinfo=timezone.utc),
            )
            assert tracker.log_event(entry) is True


class TestUsageSummary:
    def test_empty_period(
        self, tracker: CustomerSuccessTracker, customer_id: UUID
    ) -> None:
        summary = tracker.get_usage_summary(
            customer_id=customer_id,
            period_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 6, 1, tzinfo=timezone.utc),
            total_hours_allowed=Decimal("30"),
        )
        assert summary.total_hours_used == Decimal("0")
        assert summary.n_launches_initiated == 0

    def test_hours_aggregation(
        self, tracker: CustomerSuccessTracker, customer_id: UUID, machine_id: UUID
    ) -> None:
        for i, hours in enumerate(["1.5", "2.0", "0.5"]):
            tracker.log_event(_make_entry(
                customer_id, machine_id,
                hours_charged=hours,
                timestamp=datetime(2026, 5, 1 + i, 10, 0, tzinfo=timezone.utc),
            ))

        summary = tracker.get_usage_summary(
            customer_id=customer_id,
            period_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 6, 1, tzinfo=timezone.utc),
            total_hours_allowed=Decimal("30"),
        )
        assert summary.total_hours_used == Decimal("4.0")

    def test_breakdown_by_event_type(
        self, tracker: CustomerSuccessTracker, customer_id: UUID, machine_id: UUID
    ) -> None:
        tracker.log_event(_make_entry(
            customer_id, machine_id, event_type="proxy_review", hours_charged="2",
            timestamp=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
        ))
        tracker.log_event(_make_entry(
            customer_id, machine_id, event_type="posterior_update", hours_charged="3",
            timestamp=datetime(2026, 5, 2, 10, 0, tzinfo=timezone.utc),
        ))

        summary = tracker.get_usage_summary(
            customer_id=customer_id,
            period_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 6, 1, tzinfo=timezone.utc),
            total_hours_allowed=Decimal("30"),
        )
        assert summary.breakdown_by_event_type["proxy_review"] == Decimal("2")
        assert summary.breakdown_by_event_type["posterior_update"] == Decimal("3")

    def test_count_distinct_launches(
        self, tracker: CustomerSuccessTracker, customer_id: UUID, machine_id: UUID
    ) -> None:
        proj1 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        proj2 = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        for i, proj_id in enumerate([proj1, proj1, proj2]):
            tracker.log_event(_make_entry(
                customer_id, machine_id, project_id=proj_id,
                timestamp=datetime(2026, 5, 1, 10, 0 + i * 5, tzinfo=timezone.utc),
            ))
        summary = tracker.get_usage_summary(
            customer_id=customer_id,
            period_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 6, 1, tzinfo=timezone.utc),
            total_hours_allowed=Decimal("30"),
        )
        assert summary.n_launches_initiated == 2  # 2 distinct projects


class TestPredictDepletion:
    def test_no_recent_activity_returns_none(
        self, tracker: CustomerSuccessTracker, customer_id: UUID
    ) -> None:
        result = tracker.predict_depletion(customer_id, Decimal("8"))
        assert result is None

    def test_linear_extrapolation_at_known_rate(
        self, tracker: CustomerSuccessTracker, customer_id: UUID, machine_id: UUID
    ) -> None:
        # Log 4 hours over last 4 weeks → 1 hr/week → ~7 hrs/week consumption rate
        # Wait, 4 hours / 28 days = ~0.143 hrs/day
        # 8 hours remaining / 0.143 = ~56 days
        now = datetime.now(timezone.utc)
        for i in range(4):
            tracker.log_event(_make_entry(
                customer_id, machine_id,
                hours_charged="1.0",
                timestamp=now - timedelta(days=7 * (i + 1)),
            ))
        eta_days = tracker.predict_depletion(customer_id, Decimal("8"))
        assert eta_days is not None
        # Rough bounds — actual value depends on lookback window calc precision
        assert 30 <= eta_days <= 90


class TestSyncQueue:
    def test_pending_entries_returned(
        self, tracker: CustomerSuccessTracker, customer_id: UUID, machine_id: UUID
    ) -> None:
        for i in range(3):
            tracker.log_event(_make_entry(
                customer_id, machine_id,
                timestamp=datetime(2026, 5, 1 + i, 10, 0, tzinfo=timezone.utc),
            ))
        pending = tracker.get_pending_sync_entries()
        assert len(pending) == 3

    def test_mark_synced_removes_from_queue(
        self, tracker: CustomerSuccessTracker, customer_id: UUID, machine_id: UUID
    ) -> None:
        entry = _make_entry(customer_id, machine_id)
        tracker.log_event(entry)
        pending = tracker.get_pending_sync_entries()
        assert len(pending) == 1

        tracker.mark_synced([entry.event_id])
        pending_after = tracker.get_pending_sync_entries()
        assert len(pending_after) == 0


class TestCsvExport:
    def test_csv_export_format(
        self, tracker: CustomerSuccessTracker, customer_id: UUID, machine_id: UUID
    ) -> None:
        tracker.log_event(_make_entry(
            customer_id, machine_id, event_type="proxy_review", hours_charged="1.5",
            timestamp=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
        ))
        csv_text = tracker.export_csv(
            customer_id=customer_id,
            period_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        reader = csv.reader(StringIO(csv_text))
        rows = list(reader)
        assert rows[0] == [
            "event_id", "timestamp_start", "event_type", "duration_minutes",
            "project_id", "notes", "consulting_hours_charged",
        ]
        assert len(rows) == 2  # header + 1 entry


class TestPreferencesStore:
    def test_load_defaults_for_new_customer(self, tmp_path: Path) -> None:
        store = PreferencesStore(tmp_path / "prefs.db")
        cust = uuid4()
        prefs = store.load(cust)
        assert prefs.customer_id == cust
        assert prefs.preferred_audience_framing == "balanced"
        assert prefs.notifications_enabled is True

    def test_save_and_reload(self, tmp_path: Path) -> None:
        store = PreferencesStore(tmp_path / "prefs.db")
        cust = uuid4()
        prefs = UserPreferences(
            customer_id=cust,
            preferred_audience_framing="cfo",
            chart_color_palette="color_blind_safe",
            favorite_proxies=["KAG-2024", "VEN-2024"],
        )
        store.save(prefs)
        reloaded = store.load(cust)
        assert reloaded.preferred_audience_framing == "cfo"
        assert reloaded.chart_color_palette == "color_blind_safe"
        assert reloaded.favorite_proxies == ["KAG-2024", "VEN-2024"]

    def test_save_replaces_existing(self, tmp_path: Path) -> None:
        store = PreferencesStore(tmp_path / "prefs.db")
        cust = uuid4()
        store.save(UserPreferences(customer_id=cust, preferred_audience_framing="cfo"))
        store.save(UserPreferences(customer_id=cust, preferred_audience_framing="cmo"))
        reloaded = store.load(cust)
        assert reloaded.preferred_audience_framing == "cmo"

    def test_pending_sync_includes_unsynced(self, tmp_path: Path) -> None:
        store = PreferencesStore(tmp_path / "prefs.db")
        cust = uuid4()
        store.save(UserPreferences(customer_id=cust))
        pending = store.get_pending_sync()
        assert len(pending) == 1
        assert pending[0].customer_id == cust
