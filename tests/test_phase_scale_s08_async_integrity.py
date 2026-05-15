"""S-08 — check_integrity async tests.

Coverage:
- start_integrity_check returns integrity_handle
- Progress event emitted during run
- cancel_integrity_check stops background thread (sets cancel flag)
- Async result matches sync result on same DB
- cancel_integrity_check for unknown handle returns cancelled=False
- Thread is registered in _integrity_threads and cleaned up after run
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from aurora_launch.persistence.blob_store import BlobStore
from aurora_launch.persistence.project_db import ProjectDB


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_storage(tmp_path: Path) -> tuple[Path, BlobStore, ProjectDB]:
    root = tmp_path / "aurora_s08"
    root.mkdir()
    (root / "blobs").mkdir()
    blob_store = BlobStore(root / "blobs")
    db = ProjectDB(root / "projects.db", blob_store)
    return root, blob_store, db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def storage(tmp_path: Path):
    root, blob_store, db = _make_storage(tmp_path)
    yield root, blob_store, db
    db.close()


# ---------------------------------------------------------------------------
# Direct method tests (without sidecar singleton plumbing)
# ---------------------------------------------------------------------------


class TestCheckIntegrityAsync:
    def test_start_integrity_check_returns_handle(self, storage: tuple) -> None:
        """start_integrity_check IPC handler returns an integrity_handle string."""
        _root, _blob_store, db = storage
        emitted: list[dict] = []

        from aurora_launch.sidecar import methods as _methods

        # Patch _get_project_db to return our test DB.
        original_db = _methods._PROJECT_DB  # noqa: SLF001
        _methods._PROJECT_DB = db  # noqa: SLF001
        try:
            result = _methods.dispatch("start_integrity_check", {})
            assert "integrity_handle" in result
            handle = result["integrity_handle"]
            assert isinstance(handle, str) and len(handle) > 0

            # Wait for thread to complete (it runs fast on empty DB).
            thread = _methods._integrity_threads.get(handle)  # noqa: SLF001
            if thread is not None:
                thread.join(timeout=5.0)
        finally:
            _methods._PROJECT_DB = original_db  # noqa: SLF001

    def test_cancel_integrity_check_unknown_handle(self) -> None:
        """cancel_integrity_check for unknown handle returns cancelled=False."""
        from aurora_launch.sidecar import methods as _methods

        result = _methods.dispatch(
            "cancel_integrity_check", {"integrity_handle": "nonexistent-handle"}
        )
        assert result["cancelled"] is False

    def test_cancel_integrity_check_sets_flag(self, storage: tuple) -> None:
        """cancel_integrity_check sets the cancel flag on a running check."""
        _root, _blob_store, db = storage

        from aurora_launch.sidecar import methods as _methods

        # Inject a slow integrity check by patching check_integrity.
        barrier_enter = threading.Event()
        barrier_proceed = threading.Event()
        original_check = db.check_integrity

        def slow_check():
            barrier_enter.set()
            barrier_proceed.wait(timeout=5.0)
            return original_check()

        original_db = _methods._PROJECT_DB  # noqa: SLF001
        _methods._PROJECT_DB = db  # noqa: SLF001
        try:
            with patch.object(db, "check_integrity", side_effect=slow_check):
                result = _methods.dispatch("start_integrity_check", {})
                handle = result["integrity_handle"]

                # Wait until runner is inside check_integrity.
                barrier_enter.wait(timeout=3.0)

                # Cancel.
                cancel_result = _methods.dispatch(
                    "cancel_integrity_check", {"integrity_handle": handle}
                )
                assert cancel_result["cancelled"] is True

                # Let slow check complete.
                barrier_proceed.set()

                # Thread should complete.
                thread = _methods._integrity_threads.get(handle)
                if thread is not None:
                    thread.join(timeout=5.0)
        finally:
            _methods._PROJECT_DB = original_db  # noqa: SLF001

    def test_async_result_matches_sync_result(self, storage: tuple) -> None:
        """Async integrity check result matches synchronous check_integrity() output."""
        _root, _blob_store, db = storage

        from aurora_launch.sidecar import methods as _methods

        # Get sync result first.
        sync_report = db.check_integrity()

        # Capture events emitted by async check.
        captured_events: list[dict] = []
        original_emit = __import__("aurora_launch.sidecar.events", fromlist=["emit"]).emit

        def capturing_emit(event_name: str, params: dict | None = None) -> None:
            captured_events.append({"event": event_name, "params": params or {}})

        original_db = _methods._PROJECT_DB  # noqa: SLF001
        _methods._PROJECT_DB = db  # noqa: SLF001
        try:
            import aurora_launch.sidecar.events as _events

            with patch.object(_events, "emit", side_effect=capturing_emit):
                result = _methods.dispatch("start_integrity_check", {})
                handle = result["integrity_handle"]

                # Wait for completion.
                thread = _methods._integrity_threads.get(handle)
                if thread is not None:
                    thread.join(timeout=10.0)

        finally:
            _methods._PROJECT_DB = original_db  # noqa: SLF001

        # Find completed event.
        completed = [
            e for e in captured_events
            if e["event"] == "integrity_check_completed"
        ]
        assert len(completed) == 1, (
            f"Expected 1 integrity_check_completed event, got {len(completed)}. "
            f"All events: {[e['event'] for e in captured_events]}"
        )

        async_report = completed[0]["params"]["report"]

        # Compare keys and values — async should match sync.
        for key in sync_report:
            assert key in async_report, f"Missing key {key!r} in async report"
            assert sorted(async_report[key]) == sorted(sync_report[key]), (
                f"Mismatch for {key!r}: async={async_report[key]}, sync={sync_report[key]}"
            )

    def test_progress_events_emitted(self, storage: tuple) -> None:
        """At least one integrity_check_progress event is emitted during run."""
        _root, _blob_store, db = storage

        from aurora_launch.sidecar import methods as _methods

        captured_events: list[str] = []

        def capturing_emit(event_name: str, params: dict | None = None) -> None:
            captured_events.append(event_name)

        original_db = _methods._PROJECT_DB  # noqa: SLF001
        _methods._PROJECT_DB = db  # noqa: SLF001
        try:
            import aurora_launch.sidecar.events as _events

            with patch.object(_events, "emit", side_effect=capturing_emit):
                result = _methods.dispatch("start_integrity_check", {})
                handle = result["integrity_handle"]
                thread = _methods._integrity_threads.get(handle)
                if thread is not None:
                    thread.join(timeout=10.0)
        finally:
            _methods._PROJECT_DB = original_db  # noqa: SLF001

        progress_events = [e for e in captured_events if e == "integrity_check_progress"]
        assert len(progress_events) >= 1, (
            f"Expected at least 1 progress event. Got: {captured_events}"
        )

    def test_thread_cleaned_up_after_completion(self, storage: tuple) -> None:
        """_integrity_threads entry is removed after the runner finishes."""
        _root, _blob_store, db = storage

        from aurora_launch.sidecar import methods as _methods

        original_db = _methods._PROJECT_DB  # noqa: SLF001
        _methods._PROJECT_DB = db  # noqa: SLF001
        try:
            result = _methods.dispatch("start_integrity_check", {})
            handle = result["integrity_handle"]

            # Wait for thread cleanup (finally block in runner removes the entry).
            deadline = time.monotonic() + 5.0
            while handle in _methods._integrity_threads and time.monotonic() < deadline:  # noqa: SLF001
                time.sleep(0.05)
        finally:
            _methods._PROJECT_DB = original_db  # noqa: SLF001

        assert handle not in _methods._integrity_threads, (  # noqa: SLF001
            "integrity_threads entry should be removed after runner completes"
        )

    def test_start_and_cancel_integrity_check_registered_methods(self) -> None:
        """Both IPC methods are registered in the dispatch table."""
        from aurora_launch.sidecar.methods import list_methods

        methods = list_methods()
        assert "start_integrity_check" in methods
        assert "cancel_integrity_check" in methods
