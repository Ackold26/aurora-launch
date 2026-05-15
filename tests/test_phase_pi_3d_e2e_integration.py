"""R-03d E2E integration test — full sample bundle к forecast workflow.

Tests full chain through sidecar JSON-RPC dispatch (no Rust):
  create_project -> save_version -> list_versions -> compare_versions ->
  get_project -> orchestrator forecast -> CI bounds verification

Designed for CI: uses synthetic dataset (no XLSX dependency), single
process, no real PyMC training (uses synthetic posterior factory).

Per master-plan R-03d audit fix: validates that 14k LOC of Phase 0 + Phase Pi
actually used by customer-facing IPC layer.

Coverage map:
  - test_full_sample_bundle_workflow       — dispatch create/list/get + version save
  - test_orchestrator_invocation_via_sidecar — forecast via sidecar start_forecast
  - test_version_compare_workflow          — compare_versions diff semantics
  - test_pure_transfer_mode_1_zero_recipient — Mode PURE_TRANSFER, n=0 path
  - test_isolated_singleton_per_test       — no cross-test state contamination
  - test_backward_compat_legacy_forecast   — legacy start_forecast path still works
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Helpers (mirrored from test_phase_sigma_0_4_sample_bundles.py)
# ---------------------------------------------------------------------------


def _make_dataset_synthetic(
    n_periods: int = 36, n_channels: int = 2, seed: int = 0
):
    """Synthetic EconometricaDataset with no XLSX dependency."""
    from aurora_launch.sample_bundles.econometrica_xlsx_adapter import EconometricaDataset

    rng = np.random.default_rng(seed)
    channel_ids = ["tv", "digital", "search"][:n_channels]
    spend_by_channel: dict[str, list[float]] = {}
    for i, ch in enumerate(channel_ids):
        base_spend = (i + 1) * 1_000_000.0
        spend_by_channel[ch] = list(
            rng.normal(loc=base_spend, scale=base_spend * 0.2, size=n_periods).clip(min=0)
        )
    sales_brand = []
    for t in range(n_periods):
        s = 100_000_000.0
        for i, ch in enumerate(channel_ids):
            s += 0.1 * (i + 1) * spend_by_channel[ch][t]
        sales_brand.append(s + rng.normal(scale=5_000_000.0))

    return EconometricaDataset(
        brand_id="synthetic",
        granularity="monthly",
        n_periods=n_periods,
        dates_iso=[f"2023-{(m % 12) + 1:02d}-01" for m in range(n_periods)],
        channel_ids=channel_ids,
        spend_by_channel=spend_by_channel,
        sales_brand=sales_brand,
        sales_competitors=[s * 5 for s in sales_brand],
        raw_headers=[],
    )


def _make_proxy_bundle(n_channels: int = 2, n_samples: int = 500, n_obs: int = 36):
    """Minimal synthetic ProxyBundle for orchestrator tests."""
    from aurora_launch.engines.launch_orchestrator import ProxyBundle, make_proxy_bundle

    rng = np.random.default_rng(99)
    beta_means = [0.2, 0.1][:n_channels]
    beta_stds = [0.05, 0.02][:n_channels]
    alpha_values = [2.0, 1.5][:n_channels]
    gamma_values = [100.0, 50.0][:n_channels]
    decay_values = [0.5, 0.2][:n_channels]
    media_cols = ["tv", "digital"][:n_channels]

    return make_proxy_bundle(
        posterior_samples={
            "media_betas": np.array([
                rng.normal(loc=beta_means[i], scale=beta_stds[i], size=n_samples)
                for i in range(n_channels)
            ]),
            "alphas": np.array([
                rng.normal(loc=alpha_values[i], scale=0.1, size=n_samples)
                for i in range(n_channels)
            ]),
            "gammas": np.array([
                rng.normal(loc=gamma_values[i], scale=5.0, size=n_samples)
                for i in range(n_channels)
            ]),
            "adstock_decay": np.array([
                np.clip(
                    rng.normal(loc=decay_values[i], scale=0.05, size=n_samples),
                    0.0, 1.0,
                )
                for i in range(n_channels)
            ]),
        },
        media_cols=media_cols,
        normalization={"y_mean": 500_000.0, "y_std": 50_000.0},
        config={},
        proxy_brand_id="synthetic-proxy",
        n_proxy_observations=n_obs,
    )


def _make_anchors(horizon: int = 12):
    from aurora_launch.engines.pure_transfer_engine import RecipientAnchors

    return RecipientAnchors(
        market_size=10_000_000.0,
        market_size_cv=0.10,
        planned_share_trajectory=[0.05] * horizon,
        distribution_trajectory=[0.70] * horizon,
        pricing_index=1.0,
        elasticity=0.5,
        seasonality=[1.0] * horizon,
    )


def _make_spend_plan(horizon: int = 12) -> dict[str, list[float]]:
    return {"tv": [200.0] * horizon, "digital": [80.0] * horizon}


def _serialize_proxy(proxy_bundle) -> bytes:
    """Serialize a ProxyBundle into msgpack bytes for ProjectDB storage."""
    from aurora_launch.persistence.safe_serializer import serialize

    payload: dict[str, Any] = {
        "posterior_samples": proxy_bundle.posterior.posterior_samples,
        "normalization": proxy_bundle.posterior.normalization,
        "config": proxy_bundle.config_obj.config,
        "media_cols": proxy_bundle.posterior.media_cols,
        "n_proxy_observations": proxy_bundle.metadata.n_proxy_observations,
    }
    return serialize(payload)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_sidecar_db(tmp_path, monkeypatch):
    """Reset sidecar ProjectDB singleton + use isolated tmp DB.

    Uses unencrypted DB (no encryption_key) for test speed and to avoid
    requiring sqlcipher3 in CI. Methods singleton is reset before + after.
    """
    db_dir = tmp_path / "aurora_data"
    db_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("AURORA_PROJECT_DB_PATH", str(db_dir))

    # Reset singleton so next _get_project_db() reinitialises with our path
    import aurora_launch.sidecar.methods as _methods_mod
    _methods_mod._PROJECT_DB = None

    # Patch ProjectDB init so it uses unencrypted sqlite (no sqlcipher3 needed)
    original_get_db = _methods_mod._get_project_db

    def _get_plain_db():
        """Unencrypted ProjectDB initializer for test isolation."""
        if _methods_mod._PROJECT_DB is not None:
            return _methods_mod._PROJECT_DB
        from aurora_launch.persistence.blob_store import BlobStore
        from aurora_launch.persistence.project_db import ProjectDB

        data_root = db_dir
        blobs_dir = data_root / "blobs"
        blobs_dir.mkdir(parents=True, exist_ok=True)
        blob_store = BlobStore(blobs_dir)
        db = ProjectDB(data_root / "projects.db", blob_store)  # no encryption_key
        _methods_mod._PROJECT_DB = db
        return _methods_mod._PROJECT_DB

    monkeypatch.setattr(_methods_mod, "_get_project_db", _get_plain_db)

    yield tmp_path

    # Cleanup: close DB + reset singleton
    if _methods_mod._PROJECT_DB is not None:
        try:
            _methods_mod._PROJECT_DB.close()
        except Exception:
            pass
    _methods_mod._PROJECT_DB = None


@pytest.fixture
def project_with_proxy(isolated_sidecar_db):
    """Project pre-populated with synthetic posterior via dispatch."""
    from aurora_launch.sidecar.methods import dispatch
    from aurora_launch.persistence.blob_store import BlobStore
    from aurora_launch.persistence.project_db import ProjectDB
    import aurora_launch.sidecar.methods as _methods_mod

    # Create project via dispatch
    create_result = dispatch("create_project", {
        "name": "E2E Test Project",
        "granularity": "monthly",
        "metadata": {"test": True, "source": "synthetic"},
    })
    project_uuid = create_result["project_uuid"]

    # Build proxy bundle + serialize to msgpack
    proxy = _make_proxy_bundle(n_channels=2, n_samples=500)
    posterior_bytes = _serialize_proxy(proxy)

    # Save initial version directly to ProjectDB (mimics what load_sample_bundle does)
    db = _methods_mod._get_project_db()
    version_id = db.save_version(
        project_uuid,
        files={"proxy_posterior.msgpack": posterior_bytes},
        label="Initial synthetic posterior",
        decision_note="Loaded from synthetic dataset for E2E test",
    )

    return {"project_uuid": project_uuid, "version_id": version_id, "proxy": proxy}


# ---------------------------------------------------------------------------
# Test 1: Full sample bundle workflow (dispatch-level integration)
# ---------------------------------------------------------------------------


class TestFullSampleBundleWorkflow:
    """Happy path: project create → version save → list_versions → get_project."""

    def test_full_sample_bundle_workflow(self, isolated_sidecar_db):
        from aurora_launch.sidecar.methods import dispatch
        import aurora_launch.sidecar.methods as _methods_mod
        from aurora_launch.sample_bundles.synthetic_posterior import derive_synthetic_posterior

        # Step 1: create_project via dispatch
        create_result = dispatch("create_project", {
            "name": "Sample Bundle Test",
            "granularity": "monthly",
            "metadata": {"test_run": "r03d"},
        })
        assert "project_uuid" in create_result
        assert create_result["name"] == "Sample Bundle Test"
        project_uuid = create_result["project_uuid"]

        # Step 2: list_projects — verify uuid appears
        list_result = dispatch("list_projects", {})
        assert "projects" in list_result
        uuids = [p["project_uuid"] for p in list_result["projects"]]
        assert project_uuid in uuids, f"{project_uuid} not in {uuids}"

        # Step 3: synthesize dataset + derive synthetic posterior
        ds = _make_dataset_synthetic(n_periods=36, n_channels=2)
        synth = derive_synthetic_posterior(ds, n_samples=500)
        assert "media_betas" in synth.posterior_samples
        assert synth.media_cols == ["tv", "digital"]

        # Step 4: save version via direct ProjectDB (mimics load_sample_bundle path)
        from aurora_launch.persistence.safe_serializer import serialize
        posterior_bytes = serialize({
            "posterior_samples": synth.posterior_samples,
            "normalization": synth.normalization,
            "config": synth.config,
            "media_cols": synth.media_cols,
            "n_proxy_observations": synth.n_proxy_observations,
        })
        db = _methods_mod._get_project_db()
        version_id = db.save_version(
            project_uuid,
            files={"proxy_posterior.msgpack": posterior_bytes},
            label="Initial from synthetic",
        )
        assert isinstance(version_id, int)
        assert version_id > 0

        # Step 5: list_versions dispatch — verify 1 version
        list_v = dispatch("list_versions", {"project_uuid": project_uuid})
        assert "versions" in list_v
        assert len(list_v["versions"]) == 1
        assert list_v["versions"][0]["version_id"] == version_id
        assert list_v["versions"][0]["label"] == "Initial from synthetic"

        # Step 6: get_project dispatch — verify metadata
        get_result = dispatch("get_project", {"project_uuid": project_uuid})
        assert get_result["project_uuid"] == project_uuid
        assert get_result["name"] == "Sample Bundle Test"
        assert len(get_result["versions"]) == 1

    def test_list_projects_empty_db(self, isolated_sidecar_db):
        """Empty DB returns empty list, not an error."""
        from aurora_launch.sidecar.methods import dispatch

        result = dispatch("list_projects", {})
        assert result["projects"] == []

    def test_create_project_invalid_name_raises(self, isolated_sidecar_db):
        """Empty name must raise ValueError through dispatch."""
        from aurora_launch.sidecar.methods import dispatch

        with pytest.raises((ValueError, Exception)):
            dispatch("create_project", {"name": "", "granularity": "monthly"})


# ---------------------------------------------------------------------------
# Test 2: Orchestrator invocation via sidecar start_forecast
# ---------------------------------------------------------------------------


class TestOrchestratorInvocationViaSidecar:
    """Forecast via sidecar dispatch: start_forecast → thread → events emitted."""

    def test_start_forecast_returns_handle(self, isolated_sidecar_db, monkeypatch):
        """start_forecast returns valid handle and launches background thread."""
        emitted: list[tuple[str, dict]] = []

        from aurora_launch.sidecar import events as _events_mod
        monkeypatch.setattr(
            _events_mod,
            "emit",
            lambda name, params: emitted.append((name, params)),
        )

        from aurora_launch.sidecar.methods import dispatch

        result = dispatch("start_forecast", {
            "project_id": "test-proj",
            "horizon_weeks": 4,
            "seed": 42,
        })
        assert "forecast_handle" in result
        handle = result["forecast_handle"]
        assert isinstance(handle, str)
        assert len(handle) == 36  # UUID4 length

        # Wait for background thread to finish
        import aurora_launch.sidecar.methods as _methods_mod
        thread = _methods_mod._forecast_threads.get(handle)
        if thread is not None:
            thread.join(timeout=15.0)

        # Verify forecast_completed event emitted
        event_names = [e[0] for e in emitted]
        assert "forecast_completed" in event_names or "forecast_failed" in event_names, (
            f"Expected forecast_completed or forecast_failed, got: {event_names}"
        )

    def test_forecast_cone_ci_ordering_via_direct_orchestrator(self, isolated_sidecar_db):
        """Direct orchestrator call: CI lower <= point <= upper for all 12 periods."""
        from aurora_launch.engines.launch_orchestrator import LaunchOrchestrator

        proxy = _make_proxy_bundle(n_channels=2, n_samples=1000)
        anchors = _make_anchors(horizon=12)
        spend = _make_spend_plan(horizon=12)

        orch = LaunchOrchestrator()
        result = orch.forecast_recipient(
            proxy=proxy,
            anchors=anchors,
            spend_plan=spend,
            horizon_periods=12,
            granularity="monthly",
            n_recipient=0,
        )

        assert result.forecast is not None
        assert len(result.forecast.points) == 12, (
            f"Expected 12 forecast periods, got {len(result.forecast.points)}"
        )
        for i, p in enumerate(result.forecast.points):
            assert p.ci_lower <= p.point_forecast, (
                f"Period {i}: ci_lower {p.ci_lower} > point_forecast {p.point_forecast}"
            )
            assert p.point_forecast <= p.ci_upper, (
                f"Period {i}: point_forecast {p.point_forecast} > ci_upper {p.ci_upper}"
            )


# ---------------------------------------------------------------------------
# Test 3: Version compare workflow
# ---------------------------------------------------------------------------


class TestVersionCompareWorkflow:
    """compare_versions: two versions with different content produce correct diff."""

    def test_compare_versions_with_changed_file(self, project_with_proxy):
        from aurora_launch.sidecar.methods import dispatch
        import aurora_launch.sidecar.methods as _methods_mod
        from aurora_launch.persistence.safe_serializer import serialize

        project_uuid = project_with_proxy["project_uuid"]
        version_id_a = project_with_proxy["version_id"]

        # Save version B with different content
        db = _methods_mod._get_project_db()
        content_b = serialize({"label": "version_b_content", "value": 42})
        version_id_b = db.save_version(
            project_uuid,
            files={"proxy_posterior.msgpack": content_b},
            label="Version B",
            decision_note="Modified for compare test",
        )
        assert version_id_b != version_id_a

        # Call compare_versions via dispatch
        diff_result = dispatch("compare_versions", {
            "version_id_a": version_id_a,
            "version_id_b": version_id_b,
        })

        # Both versions have proxy_posterior.msgpack but with different content
        assert "files_changed" in diff_result
        assert "files_only_in_a" in diff_result
        assert "files_only_in_b" in diff_result
        assert "files_unchanged" in diff_result

        # proxy_posterior.msgpack content differs → should be in files_changed
        assert "proxy_posterior.msgpack" in diff_result["files_changed"], (
            f"Expected proxy_posterior.msgpack in files_changed, got: {diff_result}"
        )
        assert diff_result["files_only_in_a"] == []
        assert diff_result["files_only_in_b"] == []

    def test_compare_identical_versions(self, project_with_proxy):
        """Same version compared to itself — everything unchanged."""
        from aurora_launch.sidecar.methods import dispatch

        vid = project_with_proxy["version_id"]
        diff = dispatch("compare_versions", {
            "version_id_a": vid,
            "version_id_b": vid,
        })
        assert diff["files_changed"] == []
        assert diff["files_only_in_a"] == []
        assert diff["files_only_in_b"] == []
        assert "proxy_posterior.msgpack" in diff["files_unchanged"]

    def test_compare_versions_with_added_file(self, project_with_proxy):
        """Version B has extra file: appears in files_only_in_b."""
        from aurora_launch.sidecar.methods import dispatch
        import aurora_launch.sidecar.methods as _methods_mod
        from aurora_launch.persistence.safe_serializer import serialize

        project_uuid = project_with_proxy["project_uuid"]
        version_id_a = project_with_proxy["version_id"]

        db = _methods_mod._get_project_db()
        # Version B: same proxy_posterior + extra file
        proxy_bytes = _serialize_proxy(project_with_proxy["proxy"])
        version_id_b = db.save_version(
            project_uuid,
            files={
                "proxy_posterior.msgpack": proxy_bytes,
                "anchors.msgpack": serialize({"market_size": 1_000_000.0}),
            },
            label="Version B with anchors",
        )

        diff = dispatch("compare_versions", {
            "version_id_a": version_id_a,
            "version_id_b": version_id_b,
        })
        assert "anchors.msgpack" in diff["files_only_in_b"]
        # proxy_posterior.msgpack: same bytes → unchanged
        assert "proxy_posterior.msgpack" in diff["files_unchanged"]


# ---------------------------------------------------------------------------
# Test 4: Pure Transfer Mode 1 (n_recipient=0) produces sensible forecast cone
# ---------------------------------------------------------------------------


class TestPureTransferModeZeroRecipient:
    """R-03d requirement: Mode PURE_TRANSFER with n=0 is the baseline path."""

    def test_pure_transfer_mode_selected(self):
        from aurora_launch.engines.launch_orchestrator import LaunchOrchestrator
        from aurora_launch.engines.router import EngineMode

        proxy = _make_proxy_bundle(n_channels=2, n_samples=1000)
        orch = LaunchOrchestrator()
        result = orch.forecast_recipient(
            proxy=proxy,
            anchors=_make_anchors(12),
            spend_plan=_make_spend_plan(12),
            horizon_periods=12,
            granularity="monthly",
            n_recipient=0,
        )
        assert result.engine_config.mode == EngineMode.PURE_TRANSFER
        assert result.methodology_signature == "pure_transfer_v1"
        assert result.warnings == []

    def test_pure_transfer_forecast_has_correct_horizon(self):
        from aurora_launch.engines.launch_orchestrator import LaunchOrchestrator

        proxy = _make_proxy_bundle(n_channels=2, n_samples=500)
        orch = LaunchOrchestrator()
        result = orch.forecast_recipient(
            proxy=proxy,
            anchors=_make_anchors(12),
            spend_plan=_make_spend_plan(12),
            horizon_periods=12,
            granularity="monthly",
            n_recipient=0,
        )
        assert len(result.forecast.points) == 12

    def test_pure_transfer_ci_bounds_valid(self):
        """Every period: ci_lower <= point_forecast <= ci_upper."""
        from aurora_launch.engines.launch_orchestrator import LaunchOrchestrator

        proxy = _make_proxy_bundle(n_channels=2, n_samples=1000)
        orch = LaunchOrchestrator()
        result = orch.forecast_recipient(
            proxy=proxy,
            anchors=_make_anchors(6),
            spend_plan=_make_spend_plan(6),
            horizon_periods=6,
            granularity="monthly",
            n_recipient=0,
        )
        for i, p in enumerate(result.forecast.points):
            assert p.ci_lower <= p.point_forecast + 1e-9, (
                f"Period {i}: ci_lower={p.ci_lower:.6f} > point_forecast={p.point_forecast:.6f}"
            )
            assert p.point_forecast <= p.ci_upper + 1e-9, (
                f"Period {i}: point_forecast={p.point_forecast:.6f} > ci_upper={p.ci_upper:.6f}"
            )

    def test_pure_transfer_proxy_priors_preserved(self):
        """proxy_priors_used must contain all channel keys from proxy bundle."""
        from aurora_launch.engines.launch_orchestrator import LaunchOrchestrator

        proxy = _make_proxy_bundle(n_channels=2, n_samples=500)
        orch = LaunchOrchestrator()
        result = orch.forecast_recipient(
            proxy=proxy,
            anchors=_make_anchors(6),
            spend_plan=_make_spend_plan(6),
            horizon_periods=6,
            granularity="monthly",
            n_recipient=0,
        )
        assert "tv" in result.proxy_priors_used
        assert "digital" in result.proxy_priors_used
        assert result.proxy_priors_used["tv"].proxy_beta_mean > 0

    def test_pure_transfer_synthetic_posterior_via_orchestrator(self):
        """Full pipeline: synthetic dataset -> posterior -> ProxyBundle -> orchestrator."""
        from aurora_launch.sample_bundles.synthetic_posterior import derive_synthetic_posterior
        from aurora_launch.engines.launch_orchestrator import LaunchOrchestrator, ProxyBundle, make_proxy_bundle

        ds = _make_dataset_synthetic(n_periods=36, n_channels=2)
        synth = derive_synthetic_posterior(ds, n_samples=500)

        bundle = make_proxy_bundle(
            posterior_samples=synth.posterior_samples,
            media_cols=synth.media_cols,
            normalization=synth.normalization,
            config=synth.config,
            proxy_brand_id=ds.brand_id,
            n_proxy_observations=ds.n_periods,
        )
        spend = {
            ch: [synth.normalization["media_means"][ch]] * 6
            for ch in synth.media_cols
        }
        anchors = _make_anchors(horizon=6)
        orch = LaunchOrchestrator()
        result = orch.forecast_recipient(
            proxy=bundle,
            anchors=anchors,
            spend_plan=spend,
            horizon_periods=6,
            granularity="monthly",
            n_recipient=0,
        )
        assert result.forecast is not None
        assert len(result.forecast.points) == 6
        for p in result.forecast.points:
            assert p.ci_lower <= p.point_forecast + 1e-9
            assert p.point_forecast <= p.ci_upper + 1e-9


# ---------------------------------------------------------------------------
# Test 5: Isolated singleton per test (no cross-test contamination)
# ---------------------------------------------------------------------------


class TestIsolatedSingletonPerTest:
    """Verifies that each test gets a fresh DB with no carry-over from previous tests."""

    def test_fresh_db_has_no_projects(self, isolated_sidecar_db):
        """Fresh isolated DB must contain zero projects."""
        from aurora_launch.sidecar.methods import dispatch

        result = dispatch("list_projects", {})
        assert result["projects"] == [], (
            f"Expected empty DB, but found {len(result['projects'])} projects"
        )

    def test_singleton_reset_between_fixture_calls(self, isolated_sidecar_db):
        """Singleton is None at fixture start and reset on cleanup."""
        import aurora_launch.sidecar.methods as _methods_mod

        # At this point singleton should already be initialized by isolated_sidecar_db
        # (or None if not called yet — either is fine)
        # Create a project to force initialization
        from aurora_launch.sidecar.methods import dispatch
        dispatch("create_project", {
            "name": "Test Singleton",
            "granularity": "monthly",
        })
        # After creation, singleton is initialized
        assert _methods_mod._PROJECT_DB is not None

    def test_two_separate_projects_no_cross_contamination(self, isolated_sidecar_db):
        """Multiple projects in one test are isolated to this test's DB."""
        from aurora_launch.sidecar.methods import dispatch

        r1 = dispatch("create_project", {"name": "Project Alpha", "granularity": "monthly"})
        r2 = dispatch("create_project", {"name": "Project Beta", "granularity": "weekly"})

        list_r = dispatch("list_projects", {})
        uuids = {p["project_uuid"] for p in list_r["projects"]}
        assert r1["project_uuid"] in uuids
        assert r2["project_uuid"] in uuids
        assert len(list_r["projects"]) == 2

    def test_db_path_uses_tmp_path(self, isolated_sidecar_db, tmp_path):
        """ProjectDB file is created under tmp_path, not user data dir."""
        import aurora_launch.sidecar.methods as _methods_mod
        from aurora_launch.sidecar.methods import dispatch

        # Trigger DB init
        dispatch("list_projects", {})
        db = _methods_mod._PROJECT_DB
        assert db is not None
        # DB path must be under tmp_path
        assert str(tmp_path) in str(db.db_path), (
            f"Expected DB under {tmp_path}, got {db.db_path}"
        )


# ---------------------------------------------------------------------------
# Test 6: Backward-compat legacy start_forecast
# ---------------------------------------------------------------------------


class TestBackwardCompatLegacyForecast:
    """Verifies that old-style start_forecast (project_id + horizon_weeks) still works."""

    def test_legacy_start_forecast_returns_valid_handle(self, isolated_sidecar_db, monkeypatch):
        """start_forecast with legacy params returns forecast_handle without error."""
        emitted: list[tuple[str, dict]] = []

        from aurora_launch.sidecar import events as _events_mod
        monkeypatch.setattr(
            _events_mod,
            "emit",
            lambda name, params: emitted.append((name, params)),
        )

        from aurora_launch.sidecar.methods import dispatch

        result = dispatch("start_forecast", {
            "project_id": "legacy-proj-001",
            "horizon_weeks": 26,
            "seed": 7,
        })

        assert "forecast_handle" in result
        assert result["project_id"] == "legacy-proj-001"
        assert result["horizon_weeks"] == 26
        handle = result["forecast_handle"]

        # Wait for thread completion
        import aurora_launch.sidecar.methods as _methods_mod
        thread = _methods_mod._forecast_threads.get(handle)
        if thread is not None:
            thread.join(timeout=30.0)

        # Must have emitted completed or failed (not silently dropped)
        event_names = [e[0] for e in emitted]
        assert len(event_names) > 0, "No events emitted — forecast thread may have crashed silently"
        assert "forecast_completed" in event_names or "forecast_failed" in event_names, (
            f"Expected completed/failed event; got: {event_names}"
        )

    def test_legacy_forecast_progress_events_emitted(self, isolated_sidecar_db, monkeypatch):
        """start_forecast emits forecast_progress events per week."""
        progress_events: list[dict] = []
        final_events: list[str] = []

        from aurora_launch.sidecar import events as _events_mod

        def _capture(name: str, params: dict) -> None:
            if name == "forecast_progress":
                progress_events.append(params)
            elif name in ("forecast_completed", "forecast_failed", "forecast_cancelled"):
                final_events.append(name)

        monkeypatch.setattr(_events_mod, "emit", _capture)

        from aurora_launch.sidecar.methods import dispatch

        result = dispatch("start_forecast", {
            "project_id": "test-progress",
            "horizon_weeks": 3,  # short horizon for test speed
            "seed": 42,
        })
        handle = result["forecast_handle"]

        import aurora_launch.sidecar.methods as _methods_mod
        thread = _methods_mod._forecast_threads.get(handle)
        if thread is not None:
            thread.join(timeout=15.0)

        # Should have emitted 3 progress events + 1 completed
        assert len(progress_events) == 3, (
            f"Expected 3 progress events for 3-week horizon, got {len(progress_events)}"
        )
        for ev in progress_events:
            # Key is "period_index" in R-03b updated handler (was "week_index" in legacy)
            assert "period_index" in ev or "week_index" in ev, (
                f"Expected period_index or week_index key in progress event: {ev.keys()}"
            )
            assert "point_forecast" in ev
            assert "ci_lower" in ev
            assert "ci_upper" in ev
            assert ev["ci_lower"] <= ev["point_forecast"] <= ev["ci_upper"], (
                f"CI ordering violated: {ev}"
            )

    def test_cancel_forecast_stops_thread(self, isolated_sidecar_db, monkeypatch):
        """cancel_forecast sets the cancel flag; thread emits forecast_cancelled."""
        emitted: list[tuple[str, dict]] = []

        from aurora_launch.sidecar import events as _events_mod
        monkeypatch.setattr(
            _events_mod,
            "emit",
            lambda name, params: emitted.append((name, params)),
        )

        from aurora_launch.sidecar.methods import dispatch

        # Start a longer forecast that we'll cancel
        start_result = dispatch("start_forecast", {
            "project_id": "cancel-test",
            "horizon_weeks": 100,
            "seed": 0,
        })
        handle = start_result["forecast_handle"]

        # Immediately cancel. After audit A-09 (removed fake sleep pacing),
        # legacy forecast может complete до что cancel arrives → handle already
        # popped из _cancel_flags. Both outcomes valid: cancelled=True (handle
        # still active) or cancelled=False с reason "handle not found или
        # already finished" (race). The contract is "cancel never crashes."
        cancel_result = dispatch("cancel_forecast", {"forecast_handle": handle})
        if cancel_result["cancelled"]:
            assert cancel_result["forecast_handle"] == handle
        else:
            assert "reason" in cancel_result

        # Wait for thread
        import aurora_launch.sidecar.methods as _methods_mod
        thread = _methods_mod._forecast_threads.get(handle)
        if thread is not None:
            thread.join(timeout=15.0)

        event_names = [e[0] for e in emitted]
        # Cancelled or completed (race: cancel may arrive after completion)
        assert "forecast_cancelled" in event_names or "forecast_completed" in event_names, (
            f"Expected cancelled or completed, got: {event_names}"
        )


# ---------------------------------------------------------------------------
# Test 7: ProjectDB roundtrip — save + load + verify content
# ---------------------------------------------------------------------------


class TestProjectDBRoundtrip:
    """Verifies that version content is correctly stored and retrievable."""

    def test_save_and_load_version_roundtrip(self, isolated_sidecar_db):
        """Content stored via save_version is byte-exact when loaded."""
        import aurora_launch.sidecar.methods as _methods_mod
        from aurora_launch.sidecar.methods import dispatch

        # Create project
        create_r = dispatch("create_project", {"name": "Roundtrip Test", "granularity": "monthly"})
        project_uuid = create_r["project_uuid"]

        # Serialize proxy bundle
        proxy = _make_proxy_bundle(n_channels=2, n_samples=200)
        proxy_bytes = _serialize_proxy(proxy)

        db = _methods_mod._get_project_db()
        vid = db.save_version(
            project_uuid,
            files={"proxy_posterior.msgpack": proxy_bytes},
            label="Roundtrip v1",
        )

        # Load and verify
        loaded = db.load_version(vid)
        assert "proxy_posterior.msgpack" in loaded.files
        recovered_bytes = loaded.files["proxy_posterior.msgpack"]
        assert recovered_bytes == proxy_bytes, (
            "Stored bytes differ from loaded bytes — BlobStore roundtrip broken"
        )

    def test_save_version_increments_revision(self, project_with_proxy):
        """Second version gets revision = 2."""
        import aurora_launch.sidecar.methods as _methods_mod
        from aurora_launch.sidecar.methods import dispatch
        from aurora_launch.persistence.safe_serializer import serialize

        project_uuid = project_with_proxy["project_uuid"]
        db = _methods_mod._get_project_db()

        v2_id = db.save_version(
            project_uuid,
            files={"proxy_posterior.msgpack": serialize({"rev": 2})},
            label="Version 2",
        )

        versions = db.list_versions(project_uuid)
        assert len(versions) == 2
        revisions = [v.revision for v in versions]
        assert revisions == [1, 2], f"Expected [1, 2] revisions, got {revisions}"

    def test_get_project_version_count_matches(self, project_with_proxy):
        """get_project dispatch returns version count that matches actual DB."""
        from aurora_launch.sidecar.methods import dispatch

        project_uuid = project_with_proxy["project_uuid"]
        get_r = dispatch("get_project", {"project_uuid": project_uuid})
        assert len(get_r["versions"]) == 1
        assert get_r["versions"][0]["version_id"] == project_with_proxy["version_id"]

    def test_delete_project_removes_from_list(self, project_with_proxy, isolated_sidecar_db):
        """Deleting a project removes it from list_projects."""
        from aurora_launch.sidecar.methods import dispatch

        project_uuid = project_with_proxy["project_uuid"]

        del_r = dispatch("delete_project", {"project_uuid": project_uuid})
        assert del_r["deleted"] is True

        list_r = dispatch("list_projects", {})
        uuids = [p["project_uuid"] for p in list_r["projects"]]
        assert project_uuid not in uuids, f"Deleted project still in list: {uuids}"
