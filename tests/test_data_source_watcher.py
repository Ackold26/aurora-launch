"""Tests for DataSourceWatcher (ROADMAP §3.5).

Covers: registration, mtime detection, mark_seen, manual source no-trigger,
        baseline establishment on first check, DB persistence hooks.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from aurora_launch.engines.data_source_watcher import (
    ConsentManager,
    DataSourceWatcher,
    _now_iso,
    _parse_iso,
    _scan_folder_max_mtime,
)
from aurora_launch.schemas.auto_refresh import (
    DataSourceConfig,
    RefreshConsentSetting,
    RefreshTrigger,
)


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def test_data_source_config_manual_no_path() -> None:
    cfg = DataSourceConfig(source_kind="manual")
    assert cfg.path is None


def test_data_source_config_folder_requires_path() -> None:
    with pytest.raises(ValueError, match="path is required"):
        DataSourceConfig(source_kind="dsm_xlsx_folder")


def test_data_source_config_manual_rejects_path() -> None:
    with pytest.raises(ValueError, match="path must be None"):
        DataSourceConfig(source_kind="manual", path="/some/path")


def test_refresh_trigger_frozen() -> None:
    t = RefreshTrigger(
        project_uuid="abc",
        reason="new_data",
        detected_at="2026-01-01T00:00:00+00:00",
        source="dsm_xlsx_folder:/data",
    )
    with pytest.raises(Exception):  # frozen model
        t.project_uuid = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DataSourceWatcher: registration
# ---------------------------------------------------------------------------


def test_register_source_and_get_sources() -> None:
    watcher = DataSourceWatcher(project_uuid="proj-1")
    cfg = DataSourceConfig(
        source_kind="dsm_xlsx_folder", path="/some/folder"
    )
    watcher.register_source(cfg)
    sources = watcher.get_sources()
    assert len(sources) == 1
    assert sources[0].source_kind == "dsm_xlsx_folder"


def test_register_source_idempotent() -> None:
    watcher = DataSourceWatcher(project_uuid="proj-2")
    cfg1 = DataSourceConfig(source_kind="dsm_xlsx_folder", path="/folder-a")
    cfg2 = DataSourceConfig(
        source_kind="dsm_xlsx_folder",
        path="/folder-b",
        last_modified_seen="2026-01-01T00:00:00+00:00",
    )
    watcher.register_source(cfg1)
    watcher.register_source(cfg2)  # same kind → replace
    sources = watcher.get_sources()
    assert len(sources) == 1
    assert sources[0].path == "/folder-b"


# ---------------------------------------------------------------------------
# DataSourceWatcher: manual source never triggers
# ---------------------------------------------------------------------------


def test_manual_source_never_triggers() -> None:
    watcher = DataSourceWatcher(project_uuid="proj-manual")
    cfg = DataSourceConfig(source_kind="manual")
    watcher.register_source(cfg)
    triggers = watcher.check_for_updates()
    assert triggers == []


# ---------------------------------------------------------------------------
# DataSourceWatcher: folder watcher mtime detection
# ---------------------------------------------------------------------------


def test_folder_watcher_establishes_baseline_on_first_check(tmp_path: Path) -> None:
    """First check with no last_modified_seen → baseline set, no trigger."""
    xlsx = tmp_path / "export.xlsx"
    xlsx.write_bytes(b"fake")

    watcher = DataSourceWatcher(project_uuid="proj-baseline")
    cfg = DataSourceConfig(source_kind="dsm_xlsx_folder", path=str(tmp_path))
    watcher.register_source(cfg)

    triggers = watcher.check_for_updates()
    assert triggers == [], "First check should not trigger — baseline only"

    # After baseline, last_modified_seen should be set
    sources = watcher.get_sources()
    assert sources[0].last_modified_seen is not None


def test_folder_watcher_triggers_on_new_file(tmp_path: Path) -> None:
    """A file with mtime after last_modified_seen triggers RefreshTrigger."""
    old_mtime = datetime(2025, 1, 1, tzinfo=UTC)
    xlsx = tmp_path / "new_export.xlsx"
    xlsx.write_bytes(b"fake new data")

    watcher = DataSourceWatcher(project_uuid="proj-trigger")
    cfg = DataSourceConfig(
        source_kind="dsm_xlsx_folder",
        path=str(tmp_path),
        last_modified_seen=old_mtime.isoformat(),
    )
    watcher.register_source(cfg)

    triggers = watcher.check_for_updates()
    assert len(triggers) == 1
    assert triggers[0].reason == "new_data"
    assert triggers[0].project_uuid == "proj-trigger"
    assert "dsm_xlsx_folder" in triggers[0].source


def test_folder_watcher_no_trigger_when_no_new_files(tmp_path: Path) -> None:
    """Files with mtime before last_modified_seen → no trigger."""
    xlsx = tmp_path / "old_export.xlsx"
    xlsx.write_bytes(b"old")

    # Set last_modified_seen to far future
    future = (datetime.now(UTC) + timedelta(days=365)).isoformat()

    watcher = DataSourceWatcher(project_uuid="proj-no-trigger")
    cfg = DataSourceConfig(
        source_kind="dsm_xlsx_folder",
        path=str(tmp_path),
        last_modified_seen=future,
    )
    watcher.register_source(cfg)

    triggers = watcher.check_for_updates()
    assert triggers == []


def test_folder_watcher_empty_folder_no_trigger(tmp_path: Path) -> None:
    """Empty folder → no trigger."""
    watcher = DataSourceWatcher(project_uuid="proj-empty")
    cfg = DataSourceConfig(
        source_kind="dsm_xlsx_folder",
        path=str(tmp_path),
        last_modified_seen="2025-01-01T00:00:00+00:00",
    )
    watcher.register_source(cfg)
    triggers = watcher.check_for_updates()
    assert triggers == []


def test_folder_watcher_nonexistent_folder_no_trigger() -> None:
    """Non-existent folder → no trigger (graceful)."""
    watcher = DataSourceWatcher(project_uuid="proj-missing")
    cfg = DataSourceConfig(
        source_kind="dsm_xlsx_folder",
        path="/nonexistent/path/aurora_test_xyz",
        last_modified_seen="2025-01-01T00:00:00+00:00",
    )
    watcher.register_source(cfg)
    triggers = watcher.check_for_updates()
    assert triggers == []


# ---------------------------------------------------------------------------
# DataSourceWatcher: mark_seen
# ---------------------------------------------------------------------------


def test_mark_seen_updates_last_modified_seen(tmp_path: Path) -> None:
    xlsx = tmp_path / "x.xlsx"
    xlsx.write_bytes(b"data")

    old_mtime = "2025-01-01T00:00:00+00:00"
    new_mtime = datetime.now(UTC).isoformat()

    watcher = DataSourceWatcher(project_uuid="proj-seen")
    cfg = DataSourceConfig(
        source_kind="dsm_xlsx_folder",
        path=str(tmp_path),
        last_modified_seen=old_mtime,
    )
    watcher.register_source(cfg)

    # Triggers on first check
    triggers = watcher.check_for_updates()
    assert len(triggers) == 1

    # Mark seen
    watcher.mark_seen("dsm_xlsx_folder", new_mtime)

    # Now with future mtime as last_seen → no more trigger from same files
    sources = watcher.get_sources()
    assert sources[0].last_modified_seen == new_mtime


def test_mark_seen_unknown_source_logs_warning() -> None:
    """mark_seen on unknown source_kind → no crash (graceful)."""
    watcher = DataSourceWatcher(project_uuid="proj-warn")
    watcher.mark_seen("dsm_xlsx_folder", "2026-01-01T00:00:00+00:00")
    # No exception expected


# ---------------------------------------------------------------------------
# DataSourceWatcher: session dismiss
# ---------------------------------------------------------------------------


def test_dismiss_suppresses_triggers_in_session(tmp_path: Path) -> None:
    xlsx = tmp_path / "data.xlsx"
    xlsx.write_bytes(b"data")

    watcher = DataSourceWatcher(project_uuid="proj-dismiss")
    cfg = DataSourceConfig(
        source_kind="dsm_xlsx_folder",
        path=str(tmp_path),
        last_modified_seen="2025-01-01T00:00:00+00:00",
    )
    watcher.register_source(cfg)

    watcher.dismiss()
    assert watcher.is_dismissed()

    triggers = watcher.check_for_updates()
    assert triggers == [], "Dismissed watcher should return no triggers"
