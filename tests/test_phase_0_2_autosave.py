"""Phase 0.2 — Autosave + recovery wizard tests.

Coverage:
- Snapshot write + atomic semantics
- Rolling 3-file rotation
- Session marker лifecycle (clean shutdown clears, unclean leaves)
- Recovery detection (orphan sessions surface, current session hidden)
- Multi-project recovery candidate list
- Stale autosave detection (>30 days)
- Recovery flow: detect → recover → claim → next detect finds nothing
- Timer scheduling (use short interval для test latency)
- Provider exception resilience
"""

from __future__ import annotations

import json
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from aurora_launch.persistence.autosave import (
    DEFAULT_AUTOSAVE_INTERVAL_S,
    AutosaveError,
    AutosaveManager,
    AutosaveSnapshot,
    _autosave_filename,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def autosave_dir(tmp_path: Path) -> Path:
    d = tmp_path / "autosave"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Snapshot write + rotation
# ---------------------------------------------------------------------------


class TestSnapshotWrite:
    def test_write_snapshot_creates_slot_1(self, autosave_dir: Path) -> None:
        with AutosaveManager(autosave_dir, session_id="sess-1") as mgr:
            project = "proj-abc"
            path = mgr.write_snapshot(project, version_seed_id=5, working_state={"step": "A"})
            assert path.name == _autosave_filename(project, 1)
            payload = json.loads(path.read_text(encoding="utf-8"))
            assert payload["project_uuid"] == project
            assert payload["session_id"] == "sess-1"
            assert payload["version_seed_id"] == 5
            assert payload["working_state"] == {"step": "A"}

    def test_rolling_rotation(self, autosave_dir: Path) -> None:
        with AutosaveManager(autosave_dir, session_id="s") as mgr:
            project = "proj-r"
            mgr.write_snapshot(project, None, {"v": 1})
            mgr.write_snapshot(project, None, {"v": 2})
            mgr.write_snapshot(project, None, {"v": 3})
            mgr.write_snapshot(project, None, {"v": 4})

            # slot 1 = newest (v4), slot 2 = v3, slot 3 = v2; v1 dropped
            p1 = autosave_dir / _autosave_filename(project, 1)
            p2 = autosave_dir / _autosave_filename(project, 2)
            p3 = autosave_dir / _autosave_filename(project, 3)
            assert p1.exists() and p2.exists() and p3.exists()
            # slot 4 should not exist
            assert not (autosave_dir / _autosave_filename(project, 4)).exists()

            assert json.loads(p1.read_text())["working_state"] == {"v": 4}
            assert json.loads(p2.read_text())["working_state"] == {"v": 3}
            assert json.loads(p3.read_text())["working_state"] == {"v": 2}

    def test_atomic_write_no_partial_files(self, autosave_dir: Path) -> None:
        with AutosaveManager(autosave_dir, session_id="s") as mgr:
            mgr.write_snapshot("p", None, {"k": "v"})
            tmps = list(autosave_dir.glob("*.tmp"))
            assert tmps == [], f"Unexpected tmp files: {tmps}"

    def test_custom_rolling_count(self, autosave_dir: Path) -> None:
        with AutosaveManager(autosave_dir, session_id="s", rolling_count=5) as mgr:
            for i in range(7):
                mgr.write_snapshot("p", None, {"i": i})
            slots = [
                autosave_dir / _autosave_filename("p", k)
                for k in range(1, 7)
            ]
            assert slots[0].exists()  # 1
            assert slots[4].exists()  # 5
            assert not slots[5].exists()  # 6 not allowed

    def test_invalid_rolling_count(self, autosave_dir: Path) -> None:
        with pytest.raises(ValueError, match="≥ 1"):
            AutosaveManager(autosave_dir, rolling_count=0)


# ---------------------------------------------------------------------------
# Session marker + recovery
# ---------------------------------------------------------------------------


class TestSessionMarker:
    def test_marker_written_on_init(self, autosave_dir: Path) -> None:
        mgr = AutosaveManager(autosave_dir, session_id="s1")
        marker = autosave_dir / "session.lock"
        assert marker.exists()
        payload = json.loads(marker.read_text(encoding="utf-8"))
        assert payload["session_id"] == "s1"
        mgr.shutdown()
        assert not marker.exists()  # cleared on shutdown

    def test_marker_persists_on_crash(self, autosave_dir: Path) -> None:
        """Simulate crash by skipping shutdown — marker остаётся."""
        mgr = AutosaveManager(autosave_dir, session_id="crashed")
        marker = autosave_dir / "session.lock"
        assert marker.exists()
        # No shutdown call — simulating crash
        del mgr
        assert marker.exists()


class TestRecoveryDetection:
    def test_no_pending_when_clean(self, autosave_dir: Path) -> None:
        with AutosaveManager(autosave_dir, session_id="s1") as mgr:
            assert mgr.detect_pending_recovery() == []

    def test_detects_orphan_from_previous_session(self, autosave_dir: Path) -> None:
        # Session 1 writes autosave (simulated crash — no shutdown)
        mgr1 = AutosaveManager(autosave_dir, session_id="sess-crashed")
        mgr1.write_snapshot("proj-1", version_seed_id=10, working_state={"step": "C"})
        # No shutdown — marker stays, autosaves stay

        # Session 2 starts
        mgr2 = AutosaveManager(autosave_dir, session_id="sess-new")
        pending = mgr2.detect_pending_recovery()
        assert len(pending) == 1
        assert pending[0].project_uuid == "proj-1"
        assert pending[0].most_recent_snapshot.session_id == "sess-crashed"
        assert pending[0].most_recent_snapshot.version_seed_id == 10
        assert not pending[0].is_stale
        mgr2.shutdown()

    def test_hides_current_session_autosaves(self, autosave_dir: Path) -> None:
        with AutosaveManager(autosave_dir, session_id="alive") as mgr:
            mgr.write_snapshot("p1", None, {"current": True})
            # Should NOT appear in pending — это live, not orphan
            assert mgr.detect_pending_recovery() == []

    def test_multiple_projects_orphan(self, autosave_dir: Path) -> None:
        mgr_dead = AutosaveManager(autosave_dir, session_id="dead")
        mgr_dead.write_snapshot("p1", None, {"k": 1})
        mgr_dead.write_snapshot("p2", None, {"k": 2})
        mgr_dead.write_snapshot("p3", None, {"k": 3})
        del mgr_dead  # crash

        with AutosaveManager(autosave_dir, session_id="alive") as mgr:
            pending = mgr.detect_pending_recovery()
            assert len(pending) == 3
            assert {p.project_uuid for p in pending} == {"p1", "p2", "p3"}

    def test_stale_autosave_flagged(self, autosave_dir: Path) -> None:
        """Autosaves >30 дней old marked is_stale."""
        # Manually write a "stale" autosave with old timestamp
        old_ts = (datetime.now(timezone.utc) - timedelta(days=60)).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        stale_path = autosave_dir / _autosave_filename("p-old", 1)
        stale_path.write_text(
            json.dumps(
                {
                    "project_uuid": "p-old",
                    "session_id": "ancient",
                    "saved_at": old_ts,
                    "version_seed_id": None,
                    "working_state": {},
                }
            ),
            encoding="utf-8",
        )

        with AutosaveManager(autosave_dir, session_id="now") as mgr:
            pending = mgr.detect_pending_recovery()
            assert len(pending) == 1
            assert pending[0].is_stale

    def test_corrupted_autosave_skipped(self, autosave_dir: Path) -> None:
        bad = autosave_dir / _autosave_filename("p-bad", 1)
        bad.write_text("{not valid json", encoding="utf-8")
        with AutosaveManager(autosave_dir, session_id="now") as mgr:
            assert mgr.detect_pending_recovery() == []

    def test_autosave_missing_field_skipped(self, autosave_dir: Path) -> None:
        partial = autosave_dir / _autosave_filename("p-partial", 1)
        partial.write_text(json.dumps({"project_uuid": "p-partial"}), encoding="utf-8")
        with AutosaveManager(autosave_dir, session_id="now") as mgr:
            assert mgr.detect_pending_recovery() == []


class TestRecoveryFlow:
    def test_recover_returns_newest_by_default(self, autosave_dir: Path) -> None:
        # Crashed session writes 3 snapshots
        mgr_dead = AutosaveManager(autosave_dir, session_id="dead")
        mgr_dead.write_snapshot("p1", None, {"v": 1})
        time.sleep(0.01)  # ensure timestamp ordering
        mgr_dead.write_snapshot("p1", None, {"v": 2})
        time.sleep(0.01)
        mgr_dead.write_snapshot("p1", None, {"v": 3})
        del mgr_dead

        with AutosaveManager(autosave_dir, session_id="alive") as mgr:
            recovered = mgr.recover("p1")
            assert recovered.working_state["v"] == 3

    def test_recover_specific_snapshot(self, autosave_dir: Path) -> None:
        mgr_dead = AutosaveManager(autosave_dir, session_id="dead")
        mgr_dead.write_snapshot("p1", None, {"v": 1})
        time.sleep(0.01)
        mgr_dead.write_snapshot("p1", None, {"v": 2})
        time.sleep(0.01)
        mgr_dead.write_snapshot("p1", None, {"v": 3})
        del mgr_dead

        with AutosaveManager(autosave_dir, session_id="alive") as mgr:
            # snapshot_index=1 → second-newest (v=2)
            recovered = mgr.recover("p1", snapshot_index=1)
            assert recovered.working_state["v"] == 2

    def test_recover_unknown_project_raises(self, autosave_dir: Path) -> None:
        with AutosaveManager(autosave_dir, session_id="alive") as mgr:
            with pytest.raises(AutosaveError, match="No pending recovery"):
                mgr.recover("nonexistent")

    def test_recover_out_of_range_raises(self, autosave_dir: Path) -> None:
        mgr_dead = AutosaveManager(autosave_dir, session_id="dead")
        mgr_dead.write_snapshot("p", None, {"v": 1})
        del mgr_dead
        with AutosaveManager(autosave_dir, session_id="alive") as mgr:
            with pytest.raises(AutosaveError, match="out of range"):
                mgr.recover("p", snapshot_index=99)

    def test_claim_recovery_removes_orphan_files(self, autosave_dir: Path) -> None:
        mgr_dead = AutosaveManager(autosave_dir, session_id="dead")
        mgr_dead.write_snapshot("p", None, {"v": 1})
        mgr_dead.write_snapshot("p", None, {"v": 2})
        del mgr_dead

        with AutosaveManager(autosave_dir, session_id="alive") as mgr:
            assert len(mgr.detect_pending_recovery()) == 1
            removed = mgr.claim_recovery("p")
            assert removed == 2  # slot-1 + slot-2
            assert mgr.detect_pending_recovery() == []

    def test_claim_does_not_remove_live_session_files(self, autosave_dir: Path) -> None:
        # Orphan from dead session
        mgr_dead = AutosaveManager(autosave_dir, session_id="dead")
        mgr_dead.write_snapshot("p", None, {"v": "old"})
        del mgr_dead

        # New session writes its own autosave для same project
        with AutosaveManager(autosave_dir, session_id="alive") as mgr:
            mgr.write_snapshot("p", None, {"v": "live"})
            # claim_recovery should remove dead's file но NOT live one
            mgr.claim_recovery("p")

            # Live autosave should still exist
            slot1 = autosave_dir / _autosave_filename("p", 1)
            assert slot1.exists()
            payload = json.loads(slot1.read_text())
            assert payload["session_id"] == "alive"

    def test_discard_alias_for_claim(self, autosave_dir: Path) -> None:
        mgr_dead = AutosaveManager(autosave_dir, session_id="dead")
        mgr_dead.write_snapshot("p", None, {"v": 1})
        del mgr_dead
        with AutosaveManager(autosave_dir, session_id="alive") as mgr:
            assert mgr.discard("p") == 1


# ---------------------------------------------------------------------------
# Timer scheduling
# ---------------------------------------------------------------------------


class TestTimerScheduling:
    def test_start_autosave_fires_periodically(self, autosave_dir: Path) -> None:
        with AutosaveManager(
            autosave_dir, session_id="t", interval_s=0.1
        ) as mgr:
            counter = {"n": 0}

            def provider() -> tuple[int | None, dict]:
                counter["n"] += 1
                return None, {"tick": counter["n"]}

            mgr.start_autosave("p", provider)
            # Wait for at least 2 ticks. Margin generous (1.0s) для CI / heavy load —
            # OS scheduler can delay threading.Timer past nominal interval when many
            # tests run в parallel. Pf-09 hardening.
            time.sleep(1.0)
            mgr.stop_autosave("p")

            assert counter["n"] >= 2, f"Expected ≥2 ticks within 1.0s, got {counter['n']}"
            slot1 = autosave_dir / _autosave_filename("p", 1)
            assert slot1.exists()

    def test_stop_cancels_timer(self, autosave_dir: Path) -> None:
        with AutosaveManager(autosave_dir, session_id="t", interval_s=0.1) as mgr:
            counter = {"n": 0}

            def provider() -> tuple[int | None, dict]:
                counter["n"] += 1
                return None, {}

            mgr.start_autosave("p", provider)
            time.sleep(0.15)
            mgr.stop_autosave("p")
            ticks_at_stop = counter["n"]
            time.sleep(0.25)
            # No additional ticks после stop
            assert counter["n"] == ticks_at_stop

    def test_provider_exception_does_not_kill_timer(
        self, autosave_dir: Path
    ) -> None:
        with AutosaveManager(autosave_dir, session_id="t", interval_s=0.05) as mgr:
            attempts = {"n": 0}

            def flaky_provider() -> tuple[int | None, dict]:
                attempts["n"] += 1
                if attempts["n"] == 1:
                    raise RuntimeError("boom")
                return None, {"ok": True}

            mgr.start_autosave("p", flaky_provider)
            time.sleep(0.2)
            mgr.stop_autosave("p")
            # Provider called at least twice (first failed, second succeeded)
            assert attempts["n"] >= 2

    @pytest.mark.skipif(
        sys.platform == "darwin",
        reason=(
            "Timer-driven autosave file path lookup races на macOS GitHub Actions "
            "runners (private tmp dir cleanup behavior). Sprint Buffer item: "
            "stabilize timer mocks или use polling assertion."
        ),
    )
    def test_replace_provider(self, autosave_dir: Path) -> None:
        with AutosaveManager(autosave_dir, session_id="t", interval_s=0.05) as mgr:
            mgr.start_autosave("p", lambda: (None, {"v": "first"}))
            time.sleep(0.07)
            mgr.start_autosave("p", lambda: (None, {"v": "second"}))
            time.sleep(0.07)
            mgr.stop_autosave("p")

            slot1 = autosave_dir / _autosave_filename("p", 1)
            payload = json.loads(slot1.read_text())
            assert payload["working_state"]["v"] == "second"

    def test_shutdown_cancels_all_timers(self, autosave_dir: Path) -> None:
        mgr = AutosaveManager(autosave_dir, session_id="t", interval_s=0.05)
        counter = {"n": 0}

        def provider() -> tuple[int | None, dict]:
            counter["n"] += 1
            return None, {}

        mgr.start_autosave("p1", provider)
        mgr.start_autosave("p2", provider)
        time.sleep(0.08)
        ticks_before = counter["n"]
        mgr.shutdown()
        time.sleep(0.15)
        # No more ticks after shutdown
        assert counter["n"] == ticks_before
