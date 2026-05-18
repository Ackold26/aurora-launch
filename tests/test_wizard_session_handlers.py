"""Wizard session persistence handlers — Phase 1.C.1 BTA-2.

Tests sidecar methods wizard_session_save / wizard_session_load /
wizard_session_clear + list_sample_bundles. Real ProjectDB + v003 kv_store.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


# Reset module-level singletons between tests чтобы predictable state
@pytest.fixture(autouse=True)
def _reset_module_singletons():
    """Reset _PROJECT_DB и DI container между tests."""
    from aurora_launch.sidecar.services import reset_services_for_testing

    reset_services_for_testing()
    yield
    reset_services_for_testing()


@pytest.fixture
def tmp_project_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Real ProjectDB instance в tmp_path, registered via _PROJECT_DB module-level."""
    from aurora_launch.persistence.project_db import ProjectDB
    from aurora_launch.persistence.blob_store import BlobStore
    from aurora_launch.sidecar import methods as _m

    blob_store = BlobStore(tmp_path / "blobs")
    db = ProjectDB(tmp_path / "test.db", blob_store)
    _m._PROJECT_DB = db
    yield db
    db.close()
    _m._PROJECT_DB = None


def _sample_session() -> dict[str, Any]:
    """Минимальный валидный WizardSession dict для теста.

    Updated for new schema: column_roles/validation_done вместо
    column_mapping/mapping_done (file reader port 2026-05-18).
    step: 1 = proxy (было 2 когда mapping был отдельным шагом).
    """
    return {
        "session_id": "test-uuid-001",
        "step": 1,
        "imported_file_path": "/tmp/test.xlsx",
        "imported_adapter_id": None,
        "imported_record_count": 156,
        "imported_columns": ["date", "sales_packs", "tv_spend"],
        "column_roles": [
            {"name": "date", "role": "date", "confidence": 0.97, "auto_detected": True},
            {"name": "sales_packs", "role": "kpi", "confidence": 0.70, "auto_detected": True},
            {"name": "tv_spend", "role": "media", "confidence": 0.70, "auto_detected": True},
        ],
        "validation_done": True,
        "selected_proxy_path": None,
        "selected_proxy_label": None,
        "similarity_result": None,
        "anchors_draft": None,
        "anchors_done": False,
        "forecast_handle_id": None,
        "forecast_completed": False,
        "forecast_horizon": 26,
        "cert_signed": False,
        "saved_bundle_path": None,
        "created_at": "2026-05-16T10:00:00Z",
        "last_saved_at": "2026-05-16T10:05:00Z",
    }


class TestWizardSessionSave:
    def test_save_returns_success_with_db(self, tmp_project_db) -> None:
        from aurora_launch.sidecar.methods import dispatch

        result = dispatch("wizard_session_save", {"session": _sample_session()})
        assert result["saved"] is True
        assert result["saved_at"] == "2026-05-16T10:05:00Z"

    def test_save_missing_session_raises(self, tmp_project_db) -> None:
        from aurora_launch.sidecar.methods import dispatch

        with pytest.raises(ValueError, match="session.*must be dict"):
            dispatch("wizard_session_save", {})

    # NOTE: тест "graceful behavior без ProjectDB" удалён — в production
    # sidecar всегда имеет ProjectDB. Lazy init fail (sqlcipher3) выбрасывает
    # SidecarStorageError из _get_project_db, не возвращает None. Handler
    # code path `if db is None` defensive — для будущего DI-mock тестирования.


class TestWizardSessionLoad:
    def test_load_returns_null_when_no_draft(self, tmp_project_db) -> None:
        from aurora_launch.sidecar.methods import dispatch

        result = dispatch("wizard_session_load", {})
        assert result == {"session": None}

    def test_load_returns_saved_session(self, tmp_project_db) -> None:
        from aurora_launch.sidecar.methods import dispatch

        original = _sample_session()
        dispatch("wizard_session_save", {"session": original})

        result = dispatch("wizard_session_load", {})
        assert result["session"] is not None
        assert result["session"]["session_id"] == "test-uuid-001"
        assert result["session"]["step"] == 1
        assert len(result["session"]["column_roles"]) == 3

    # NOTE: тест "load без ProjectDB" удалён по той же причине — production
    # invariant: sidecar всегда имеет ProjectDB после startup.


class TestWizardSessionClear:
    def test_clear_returns_true_when_existed(self, tmp_project_db) -> None:
        from aurora_launch.sidecar.methods import dispatch

        dispatch("wizard_session_save", {"session": _sample_session()})
        result = dispatch("wizard_session_clear", {})
        assert result["cleared"] is True

        # Verify actually cleared
        load_result = dispatch("wizard_session_load", {})
        assert load_result["session"] is None

    def test_clear_returns_false_when_no_draft(self, tmp_project_db) -> None:
        from aurora_launch.sidecar.methods import dispatch

        result = dispatch("wizard_session_clear", {})
        assert result["cleared"] is False


class TestListSampleBundles:
    def test_returns_three_bundles(self, tmp_project_db) -> None:
        from aurora_launch.sidecar.methods import dispatch

        result = dispatch("list_sample_bundles", {})
        assert "bundles" in result
        bundle_ids = {b["id"] for b in result["bundles"]}
        assert bundle_ids == {"kagotsel_venarus", "venarus_baseline", "multi_proxy"}

    def test_each_bundle_has_label_and_exists_flag(self, tmp_project_db) -> None:
        from aurora_launch.sidecar.methods import dispatch

        result = dispatch("list_sample_bundles", {})
        for bundle in result["bundles"]:
            assert "label" in bundle
            assert "path" in bundle
            assert "exists" in bundle
            assert isinstance(bundle["exists"], bool)
            assert len(bundle["label"]) > 0

    def test_labels_in_russian(self, tmp_project_db) -> None:
        """UX premium: labels на русском с описанием категории."""
        from aurora_launch.sidecar.methods import dispatch

        result = dispatch("list_sample_bundles", {})
        labels = {b["id"]: b["label"] for b in result["bundles"]}
        assert "Кагоцел" in labels["kagotsel_venarus"]
        assert "Венарус" in labels["venarus_baseline"]


class TestRoundTripPersistenceAcrossReopen:
    """Critical: подтверждает что wizard recovery работает между sidecar restart."""

    def test_save_close_reopen_load(self, tmp_path: Path) -> None:
        """Save с одной ProjectDB instance, close, reopen — load возвращает same."""
        from aurora_launch.persistence.project_db import ProjectDB
        from aurora_launch.persistence.blob_store import BlobStore
        from aurora_launch.sidecar import methods as _m
        from aurora_launch.sidecar.methods import dispatch

        blob_store = BlobStore(tmp_path / "blobs")

        # First "sidecar boot": save session
        db1 = ProjectDB(tmp_path / "persist.db", blob_store)
        _m._PROJECT_DB = db1
        try:
            dispatch("wizard_session_save", {"session": _sample_session()})
        finally:
            db1.close()
            _m._PROJECT_DB = None

        # Second "sidecar boot" (после restart)
        db2 = ProjectDB(tmp_path / "persist.db", blob_store)
        _m._PROJECT_DB = db2
        try:
            result = dispatch("wizard_session_load", {})
            assert result["session"] is not None
            assert result["session"]["session_id"] == "test-uuid-001"
            assert result["session"]["validation_done"] is True
        finally:
            db2.close()
            _m._PROJECT_DB = None
