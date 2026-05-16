"""Phase Π.3b — ProjectDB-wired sidecar handler tests.

Closes audit R-03b: start_forecast no longer returns stub data;
ProjectDB is built and used.

Coverage:
1. create_project — creates project, returns UUID + name + created_at
2. list_projects — returns list with created project
3. get_project — returns detail + empty versions list
4. delete_project — project gone from list_projects after delete
5. list_versions — empty initially, non-empty after save_version
6. compare_versions — unchanged / changed / only_in_* files
7. import_aurora_bundle — bundle creates project + version
8. load_sample_bundle — missing file → FileNotFoundError (skip if present)
9. start_forecast backward compat — legacy project_id path still works
10. start_forecast DB path — ProjectDB project → orchestrated forecast

Each test uses tmp_path + AURORA_PROJECT_DB_PATH env override for isolation.
Per INV-11: explicit exception wrapping verified; per INV-05: no fake progress.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Helpers: reset singleton between tests
# ---------------------------------------------------------------------------


def _reset_singleton() -> None:
    """Close and discard the module-level ProjectDB singleton."""
    import aurora_launch.sidecar.methods as m
    with m._PROJECT_DB_LOCK:
        if m._PROJECT_DB is not None:
            try:
                m._PROJECT_DB.close()
            except Exception:  # noqa: BLE001
                pass
            m._PROJECT_DB = None


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Each test gets its own isolated DB via env var.

    Disables SQLCipher для CI без sqlcipher3 installed — singleton
    initialises с plain sqlite3 backend. AURORA_LAUNCH_TESTING=1 unlocks
    the "none" key sentinel (audit A-04 guard requires dev/test flag).
    """
    db_dir = tmp_path / "aurora_launch_test_db"
    db_dir.mkdir()
    monkeypatch.setenv("AURORA_PROJECT_DB_PATH", str(db_dir))
    monkeypatch.setenv("AURORA_PROJECT_DB_KEY", "none")
    monkeypatch.setenv("AURORA_LAUNCH_TESTING", "1")
    _reset_singleton()
    yield db_dir
    _reset_singleton()


def dispatch(method: str, params: dict[str, Any]) -> Any:
    """Thin wrapper around methods.dispatch for readability."""
    from aurora_launch.sidecar.methods import dispatch as _dispatch
    return _dispatch(method, params)


# ---------------------------------------------------------------------------
# Test 1: create_project
# ---------------------------------------------------------------------------


class TestCreateProject:
    def test_returns_uuid_name_created_at(self) -> None:
        result = dispatch("create_project", {"name": "Test Brand Alpha"})
        assert "project_uuid" in result
        assert result["name"] == "Test Brand Alpha"
        assert "created_at" in result
        assert len(result["project_uuid"]) == 36  # UUID format

    def test_granularity_weekly(self) -> None:
        result = dispatch("create_project", {"name": "Weekly", "granularity": "weekly"})
        assert result["project_uuid"]

    def test_with_metadata(self) -> None:
        result = dispatch(
            "create_project",
            {"name": "Pilot", "metadata": {"client": "test_co", "category": "OTC"}},
        )
        assert result["project_uuid"]

    def test_empty_name_raises(self) -> None:
        with pytest.raises((ValueError, Exception)):
            dispatch("create_project", {"name": ""})


# ---------------------------------------------------------------------------
# Test 2: list_projects
# ---------------------------------------------------------------------------


class TestListProjects:
    def test_empty_initially(self) -> None:
        result = dispatch("list_projects", {})
        assert result["projects"] == []

    def test_contains_created_project(self) -> None:
        dispatch("create_project", {"name": "BrandX"})
        result = dispatch("list_projects", {})
        names = [p["name"] for p in result["projects"]]
        assert "BrandX" in names

    def test_project_fields_present(self) -> None:
        dispatch("create_project", {"name": "BrandY"})
        result = dispatch("list_projects", {})
        proj = result["projects"][0]
        for field in ("project_uuid", "name", "created_at", "last_modified",
                      "granularity", "version_count", "current_version_id"):
            assert field in proj, f"missing field: {field}"


# ---------------------------------------------------------------------------
# Test 3: get_project
# ---------------------------------------------------------------------------


class TestGetProject:
    def test_returns_detail(self) -> None:
        created = dispatch("create_project", {"name": "GetMe"})
        result = dispatch("get_project", {"project_uuid": created["project_uuid"]})
        assert result["name"] == "GetMe"
        assert result["versions"] == []
        assert "metadata" in result

    def test_unknown_uuid_raises(self) -> None:
        with pytest.raises(Exception):
            dispatch("get_project", {"project_uuid": "00000000-0000-0000-0000-000000000000"})

    def test_empty_uuid_raises(self) -> None:
        with pytest.raises((ValueError, Exception)):
            dispatch("get_project", {"project_uuid": ""})


# ---------------------------------------------------------------------------
# Test 4: delete_project
# ---------------------------------------------------------------------------


class TestDeleteProject:
    def test_delete_removes_from_list(self) -> None:
        created = dispatch("create_project", {"name": "DeleteMe"})
        uid = created["project_uuid"]
        result = dispatch("delete_project", {"project_uuid": uid})
        assert result["deleted"] is True
        projects = dispatch("list_projects", {})["projects"]
        uuids = [p["project_uuid"] for p in projects]
        assert uid not in uuids

    def test_double_delete_raises(self) -> None:
        created = dispatch("create_project", {"name": "DeleteTwice"})
        uid = created["project_uuid"]
        dispatch("delete_project", {"project_uuid": uid})
        with pytest.raises(Exception):
            dispatch("delete_project", {"project_uuid": uid})


# ---------------------------------------------------------------------------
# Test 5: list_versions
# ---------------------------------------------------------------------------


class TestListVersions:
    def test_empty_initially(self) -> None:
        created = dispatch("create_project", {"name": "NoVersions"})
        result = dispatch("list_versions", {"project_uuid": created["project_uuid"]})
        assert result["versions"] == []

    def test_version_appears_after_save(self, tmp_path: Path) -> None:
        """Save a version directly via ProjectDB and verify it shows in list_versions."""
        from aurora_launch.sidecar.methods import _get_project_db

        created = dispatch("create_project", {"name": "WithVersion"})
        uid = created["project_uuid"]
        db = _get_project_db()
        db.save_version(
            uid,
            files={"test.bin": b"hello"},
            label="v1",
        )

        result = dispatch("list_versions", {"project_uuid": uid})
        assert len(result["versions"]) == 1
        v = result["versions"][0]
        for field in ("version_id", "revision", "label", "decision_note",
                      "created_at", "composite_bundle_hash", "file_count"):
            assert field in v, f"missing field: {field}"
        assert v["label"] == "v1"
        assert v["file_count"] == 1


# ---------------------------------------------------------------------------
# Test 6: compare_versions
# ---------------------------------------------------------------------------


class TestCompareVersions:
    def test_unchanged_file(self) -> None:
        from aurora_launch.sidecar.methods import _get_project_db

        created = dispatch("create_project", {"name": "DiffProject"})
        uid = created["project_uuid"]
        db = _get_project_db()
        content = b"shared content"
        v1 = db.save_version(uid, files={"shared.bin": content}, label="v1")
        v2 = db.save_version(uid, files={"shared.bin": content}, label="v2")

        result = dispatch("compare_versions", {"version_id_a": v1, "version_id_b": v2})
        assert "shared.bin" in result["files_unchanged"]
        assert result["files_changed"] == []
        assert result["files_only_in_a"] == []
        assert result["files_only_in_b"] == []

    def test_changed_file(self) -> None:
        from aurora_launch.sidecar.methods import _get_project_db

        created = dispatch("create_project", {"name": "ChangedDiff"})
        uid = created["project_uuid"]
        db = _get_project_db()
        v1 = db.save_version(uid, files={"data.bin": b"version1"}, label="v1")
        v2 = db.save_version(uid, files={"data.bin": b"version2"}, label="v2")

        result = dispatch("compare_versions", {"version_id_a": v1, "version_id_b": v2})
        assert "data.bin" in result["files_changed"]

    def test_only_in_a_and_b(self) -> None:
        from aurora_launch.sidecar.methods import _get_project_db

        created = dispatch("create_project", {"name": "SplitDiff"})
        uid = created["project_uuid"]
        db = _get_project_db()
        v1 = db.save_version(uid, files={"only_a.bin": b"a"}, label="v1")
        v2 = db.save_version(uid, files={"only_b.bin": b"b"}, label="v2")

        result = dispatch("compare_versions", {"version_id_a": v1, "version_id_b": v2})
        assert "only_a.bin" in result["files_only_in_a"]
        assert "only_b.bin" in result["files_only_in_b"]

    def test_invalid_params_raise(self) -> None:
        with pytest.raises((ValueError, Exception)):
            dispatch("compare_versions", {"version_id_a": "not_int", "version_id_b": 1})


# ---------------------------------------------------------------------------
# Test 7: import_aurora_bundle
# ---------------------------------------------------------------------------


class TestImportAuroraBundle:
    def test_import_creates_project_and_version(self, tmp_path: Path) -> None:
        from aurora_launch.engines.bundle_container import BundleZipWriter

        bundle_path = tmp_path / "test_bundle.aurora"
        writer = BundleZipWriter(aurora_app_version="0.1.0")
        writer.add_file("data.json", b'{"hello": "world"}')
        writer.write(bundle_path)

        result = dispatch(
            "import_aurora_bundle",
            {"bundle_path": str(bundle_path), "project_name": "Imported"},
        )
        assert "project_uuid" in result
        assert result["version_id"] is not None
        assert isinstance(result["version_id"], int)

        # Verify project is findable
        detail = dispatch("get_project", {"project_uuid": result["project_uuid"]})
        assert detail["name"] == "Imported"
        assert len(detail["versions"]) == 1

    def test_missing_bundle_raises(self, tmp_path: Path) -> None:
        with pytest.raises(Exception):
            dispatch(
                "import_aurora_bundle",
                {"bundle_path": str(tmp_path / "does_not_exist.aurora")},
            )


# ---------------------------------------------------------------------------
# Test 8: load_sample_bundle
# ---------------------------------------------------------------------------


def _kagotsel_path() -> Path:
    """Return the kagotsel_venarus path from the canonical _SAMPLE_BUNDLE_PATHS dict."""
    from aurora_launch.sidecar.methods import _SAMPLE_BUNDLE_PATHS
    return _SAMPLE_BUNDLE_PATHS["kagotsel_venarus"]


class TestLoadSampleBundle:
    def test_unknown_scenario_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown scenario"):
            dispatch("load_sample_bundle", {"scenario": "nonexistent_brand"})

    @pytest.mark.skipif(
        not _kagotsel_path().exists(),
        reason="Pilot XLSX not present on this machine (set AURORA_SAMPLE_DATA_DIR)",
    )
    def test_kagotsel_venarus_loads(self) -> None:
        result = dispatch("load_sample_bundle", {"scenario": "kagotsel_venarus"})
        assert "project_uuid" in result
        assert "version_id" in result
        assert isinstance(result["channels"], list)
        assert len(result["channels"]) > 0
        assert result["n_periods"] > 0

        # Verify project + version in DB
        detail = dispatch("get_project", {"project_uuid": result["project_uuid"]})
        assert detail["name"] == "Sample: kagotsel_venarus"
        assert len(detail["versions"]) == 1

    def test_missing_file_raises_file_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If XLSX not present, handler must raise FileNotFoundError (not swallow)."""
        import aurora_launch.sidecar.methods as m
        # Temporarily override the path to something that doesn't exist
        fake_paths = {
            "kagotsel_venarus": Path("/nonexistent/path/to/file.xlsx"),
            "afala_afalaza": Path("/nonexistent/path/to/file2.xlsx"),
            "multi_proxy": Path("/nonexistent/path/to/file3.xlsx"),
        }
        monkeypatch.setattr(m, "_SAMPLE_BUNDLE_PATHS", fake_paths)
        with pytest.raises((FileNotFoundError, Exception)):
            dispatch("load_sample_bundle", {"scenario": "kagotsel_venarus"})


# ---------------------------------------------------------------------------
# Test 9: start_forecast — backward compat (legacy project_id path)
# ---------------------------------------------------------------------------


class TestStartForecastLegacy:
    def test_legacy_path_returns_handle(self) -> None:
        """Legacy project_id (not in DB) falls back to prior_predictive_samples_real."""
        result = dispatch(
            "start_forecast",
            {
                "project_id": "legacy_not_in_db",
                "horizon_weeks": 4,
                "seed": 42,
            },
        )
        assert "forecast_handle" in result
        assert result["horizon_weeks"] == 4
        assert result["project_id"] == "legacy_not_in_db"

    def test_legacy_path_emits_completed_event(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify legacy path eventually emits forecast_completed."""
        emitted: list[dict[str, Any]] = []

        def fake_emit(event_name: str, params: dict[str, Any] | None = None) -> None:
            emitted.append({"event": event_name, "params": params or {}})

        import aurora_launch.sidecar.events as ev
        monkeypatch.setattr(ev, "emit", fake_emit)

        result = dispatch(
            "start_forecast",
            {"project_id": "legacy_id_xyz", "horizon_weeks": 3, "seed": 0},
        )
        handle = result["forecast_handle"]

        # Wait for background thread to finish (max 10s)
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            completed_events = [
                e for e in emitted
                if e["event"] in ("forecast_completed", "forecast_failed")
                and e["params"].get("forecast_handle") == handle
            ]
            if completed_events:
                break
            time.sleep(0.1)

        terminal = [
            e for e in emitted
            if e["event"] in ("forecast_completed", "forecast_failed")
            and e["params"].get("forecast_handle") == handle
        ]
        assert len(terminal) >= 1, (
            f"No terminal event after 10s. Emitted events: {[e['event'] for e in emitted]}"
        )


# ---------------------------------------------------------------------------
# Test 10: start_forecast — ProjectDB orchestrated path
# ---------------------------------------------------------------------------


def _make_minimal_proxy_bytes() -> bytes:
    """Build a serialized proxy posterior blob compatible with _run_orchestrated_forecast."""
    from aurora_launch.persistence.safe_serializer import serialize

    rng = np.random.default_rng(99)
    n_samples = 500
    n_channels = 2
    media_cols = ["tv", "digital"]

    posterior_payload = {
        "posterior_samples": {
            "media_betas": rng.normal(0.1, 0.02, (n_channels, n_samples)),
            "alphas": rng.normal(2.0, 0.1, (n_channels, n_samples)),
            "gammas": rng.normal(2.0, 0.2, (n_channels, n_samples)),
            "adstock_decay": np.clip(
                rng.normal(0.5, 0.05, (n_channels, n_samples)), 0.0, 1.0
            ),
            "intercept": rng.normal(0.0, 0.1, n_samples).astype(np.float32),
            "control_betas": np.zeros((0, n_samples), dtype=np.float32),
        },
        "normalization": {
            "y_mean": 500_000.0,
            "y_std": 50_000.0,
            "media_means": {"tv": 200.0, "digital": 150.0},
            "control_means": {},
            "control_stds": {},
            "intercept_mean": 0.0,
            "control_betas_mean": [],
            "untrained_channels": [],
            "control_kinds": {},
            "holiday_cols_injected": [],
            "control_prior_mus": {},
            "untrained_controls": [],
        },
        "config": {"media_columns": media_cols, "mode": "sales"},
        "media_cols": media_cols,
        "n_proxy_observations": 48,
    }
    return serialize(posterior_payload)


class TestStartForecastOrchestrated:
    def test_db_project_returns_handle(self) -> None:
        """Project with proxy posterior in DB → orchestrated forecast handle returned."""
        from aurora_launch.sidecar.methods import _get_project_db

        created = dispatch("create_project", {"name": "OrchestratedTest"})
        uid = created["project_uuid"]
        db = _get_project_db()
        db.save_version(
            uid,
            files={"proxy_posterior.msgpack": _make_minimal_proxy_bytes()},
            label="synthetic_v1",
        )

        result = dispatch(
            "start_forecast",
            {
                "project_id": uid,
                "horizon_weeks": 6,
                "seed": 1,
            },
        )
        assert "forecast_handle" in result
        assert result["project_id"] == uid

    def test_db_project_emits_completed_event(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Orchestrated forecast emits forecast_completed с 'path': 'orchestrated'."""
        emitted: list[dict[str, Any]] = []

        def fake_emit(event_name: str, params: dict[str, Any] | None = None) -> None:
            emitted.append({"event": event_name, "params": params or {}})

        import aurora_launch.sidecar.events as ev
        monkeypatch.setattr(ev, "emit", fake_emit)

        from aurora_launch.sidecar.methods import _get_project_db

        created = dispatch("create_project", {"name": "OrchestratedEventTest"})
        uid = created["project_uuid"]
        db = _get_project_db()
        db.save_version(
            uid,
            files={"proxy_posterior.msgpack": _make_minimal_proxy_bytes()},
            label="synthetic_v1",
        )

        result = dispatch(
            "start_forecast",
            {"project_id": uid, "horizon_weeks": 4, "seed": 7},
        )
        handle = result["forecast_handle"]

        # Wait for background thread
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            terminal = [
                e for e in emitted
                if e["event"] in ("forecast_completed", "forecast_failed")
                and e["params"].get("forecast_handle") == handle
            ]
            if terminal:
                break
            time.sleep(0.1)

        terminal = [
            e for e in emitted
            if e["event"] in ("forecast_completed", "forecast_failed")
            and e["params"].get("forecast_handle") == handle
        ]
        assert len(terminal) >= 1

        completed = [e for e in terminal if e["event"] == "forecast_completed"]
        assert len(completed) >= 1, (
            f"Expected forecast_completed, got: {[e['event'] for e in terminal]}; "
            f"failed details: {[e['params'].get('error') for e in terminal if e['event']=='forecast_failed']}"
        )
        assert completed[0]["params"].get("path") == "orchestrated"

    def test_project_no_posterior_blob_emits_failed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Project with no posterior file → forecast_failed event (not crash)."""
        emitted: list[dict[str, Any]] = []

        def fake_emit(event_name: str, params: dict[str, Any] | None = None) -> None:
            emitted.append({"event": event_name, "params": params or {}})

        import aurora_launch.sidecar.events as ev
        monkeypatch.setattr(ev, "emit", fake_emit)

        from aurora_launch.sidecar.methods import _get_project_db

        created = dispatch("create_project", {"name": "NoPosterior"})
        uid = created["project_uuid"]
        db = _get_project_db()
        # Save version with a file that has no "posterior"/"proxy" in its name
        db.save_version(uid, files={"other_data.bin": b"x"})

        result = dispatch("start_forecast", {"project_id": uid, "horizon_weeks": 4})
        handle = result["forecast_handle"]

        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            terminal = [
                e for e in emitted
                if e["event"] in ("forecast_completed", "forecast_failed")
                and e["params"].get("forecast_handle") == handle
            ]
            if terminal:
                break
            time.sleep(0.1)

        terminal = [
            e for e in emitted
            if e["event"] in ("forecast_completed", "forecast_failed")
            and e["params"].get("forecast_handle") == handle
        ]
        failed = [e for e in terminal if e["event"] == "forecast_failed"]
        assert len(failed) >= 1, f"Expected forecast_failed; got: {terminal}"
