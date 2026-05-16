"""Phase 3 — persisted data sources per project (DataSourceWatcher backend).

Раньше frontend управлял sources только в-памяти / localStorage. Теперь
sidecar handlers get_data_sources / set_data_sources persist через v003
_kv_store (key = `data_sources.{project_uuid}`). Cross-machine sync
включён когда customer установит Aurora на 2 машинах.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _reset_module_singletons():
    from aurora_launch.sidecar.services import reset_services_for_testing

    reset_services_for_testing()
    yield
    reset_services_for_testing()


@pytest.fixture
def tmp_project_db(tmp_path: Path):
    """Real ProjectDB в tmp_path, registered via _PROJECT_DB module-level."""
    from aurora_launch.persistence.blob_store import BlobStore
    from aurora_launch.persistence.project_db import ProjectDB
    from aurora_launch.sidecar import methods as _m

    blob_store = BlobStore(tmp_path / "blobs")
    db = ProjectDB(tmp_path / "test.db", blob_store)
    _m._PROJECT_DB = db
    yield db
    db.close()
    _m._PROJECT_DB = None


class TestGetDataSources:
    def test_returns_empty_for_unknown_project(self, tmp_project_db) -> None:
        from aurora_launch.sidecar.methods import dispatch

        result = dispatch("get_data_sources", {"project_uuid": "never-seen"})
        assert result == {"sources": []}

    def test_rejects_missing_project_uuid(self, tmp_project_db) -> None:
        from aurora_launch.sidecar.methods import dispatch

        with pytest.raises(ValueError, match="project_uuid.*non-empty"):
            dispatch("get_data_sources", {})

    def test_rejects_empty_project_uuid(self, tmp_project_db) -> None:
        from aurora_launch.sidecar.methods import dispatch

        with pytest.raises(ValueError, match="project_uuid.*non-empty"):
            dispatch("get_data_sources", {"project_uuid": "  "})


class TestSetDataSources:
    def test_saves_and_loads_roundtrip(self, tmp_project_db) -> None:
        from aurora_launch.sidecar.methods import dispatch

        sources = [
            {"source_kind": "dsm_xlsx_folder", "path": "/tmp/dsm"},
            {"source_kind": "mediascope_xlsx_folder", "path": "/tmp/mediascope"},
        ]
        save_result = dispatch(
            "set_data_sources",
            {"project_uuid": "proj-1", "sources": sources},
        )
        assert save_result["saved"] is True
        assert save_result["count"] == 2

        load_result = dispatch("get_data_sources", {"project_uuid": "proj-1"})
        assert len(load_result["sources"]) == 2
        kinds = {s["source_kind"] for s in load_result["sources"]}
        assert kinds == {"dsm_xlsx_folder", "mediascope_xlsx_folder"}

    def test_empty_list_overwrites_existing(self, tmp_project_db) -> None:
        from aurora_launch.sidecar.methods import dispatch

        dispatch(
            "set_data_sources",
            {
                "project_uuid": "proj-2",
                "sources": [{"source_kind": "dsm_xlsx_folder", "path": "/x"}],
            },
        )
        # Customer removed all sources
        dispatch("set_data_sources", {"project_uuid": "proj-2", "sources": []})

        result = dispatch("get_data_sources", {"project_uuid": "proj-2"})
        assert result == {"sources": []}

    def test_per_project_isolation(self, tmp_project_db) -> None:
        """proj-A sources не влияют на proj-B."""
        from aurora_launch.sidecar.methods import dispatch

        dispatch(
            "set_data_sources",
            {
                "project_uuid": "proj-A",
                "sources": [{"source_kind": "dsm_xlsx_folder", "path": "/a"}],
            },
        )
        dispatch(
            "set_data_sources",
            {
                "project_uuid": "proj-B",
                "sources": [{"source_kind": "mediascope_xlsx_folder", "path": "/b"}],
            },
        )

        result_a = dispatch("get_data_sources", {"project_uuid": "proj-A"})
        result_b = dispatch("get_data_sources", {"project_uuid": "proj-B"})

        assert result_a["sources"][0]["source_kind"] == "dsm_xlsx_folder"
        assert result_b["sources"][0]["source_kind"] == "mediascope_xlsx_folder"

    def test_rejects_non_list_sources(self, tmp_project_db) -> None:
        from aurora_launch.sidecar.methods import dispatch

        with pytest.raises(ValueError, match="sources.*list"):
            dispatch(
                "set_data_sources", {"project_uuid": "proj", "sources": "not-a-list"}
            )

    def test_rejects_invalid_source_kind(self, tmp_project_db) -> None:
        from aurora_launch.sidecar.methods import dispatch

        with pytest.raises(Exception):  # Pydantic ValidationError
            dispatch(
                "set_data_sources",
                {
                    "project_uuid": "proj",
                    "sources": [{"source_kind": "unknown_kind", "path": "/x"}],
                },
            )


class TestPersistenceAcrossDbReopen:
    """Cross-restart persistence verified (real db close + reopen)."""

    def test_save_close_reopen_load(self, tmp_path: Path) -> None:
        from aurora_launch.persistence.blob_store import BlobStore
        from aurora_launch.persistence.project_db import ProjectDB
        from aurora_launch.sidecar import methods as _m
        from aurora_launch.sidecar.methods import dispatch

        blob_store = BlobStore(tmp_path / "blobs")
        sources = [{"source_kind": "dsm_xlsx_folder", "path": "/persist/test"}]

        # First "sidecar boot"
        db1 = ProjectDB(tmp_path / "persist.db", blob_store)
        _m._PROJECT_DB = db1
        try:
            dispatch(
                "set_data_sources",
                {"project_uuid": "proj-persist", "sources": sources},
            )
        finally:
            db1.close()
            _m._PROJECT_DB = None

        # Second "sidecar boot" после restart
        db2 = ProjectDB(tmp_path / "persist.db", blob_store)
        _m._PROJECT_DB = db2
        try:
            result = dispatch(
                "get_data_sources", {"project_uuid": "proj-persist"}
            )
            assert len(result["sources"]) == 1
            assert result["sources"][0]["path"] == "/persist/test"
        finally:
            db2.close()
            _m._PROJECT_DB = None
