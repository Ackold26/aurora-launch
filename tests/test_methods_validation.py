"""Integration tests for analyze_data_file + validate_wide_table handlers.

Tests dispatch directly via dispatch("analyze_data_file", ...) / dispatch("validate_wide_table", ...).
Real in-memory ProjectDB fixture mirrors test_wizard_session_handlers.py pattern.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_module_singletons():
    """Reset singletons between tests (mirrors test_wizard_session_handlers.py)."""
    from aurora_launch.sidecar.services import reset_services_for_testing

    reset_services_for_testing()
    yield
    reset_services_for_testing()


@pytest.fixture
def tmp_project_db(tmp_path: Path) -> Any:
    """Real ProjectDB instance in tmp_path, registered via _PROJECT_DB."""
    from aurora_launch.persistence.project_db import ProjectDB
    from aurora_launch.persistence.blob_store import BlobStore
    from aurora_launch.sidecar import methods as _m

    blob_store = BlobStore(tmp_path / "blobs")
    db = ProjectDB(tmp_path / "test.db", blob_store)
    _m._PROJECT_DB = db
    yield db
    db.close()
    _m._PROJECT_DB = None


def _write_wide_xlsx(tmp_path: Path, name: str = "wide_table.xlsx") -> Path:
    """Write a 4-column wide table xlsx (date / kpi / media / control)."""
    import pandas as pd
    import numpy as np

    rng = np.random.default_rng(7)
    df = pd.DataFrame({
        "date": pd.date_range("2023-01-02", periods=52, freq="W"),
        "sales_packs": rng.integers(500, 2000, 52),
        "tv_spend": rng.uniform(100_000, 500_000, 52).round(0),
        "competitor_share": rng.uniform(0.1, 0.4, 52).round(3),
    })
    out = tmp_path / name
    df.to_excel(out, index=False)
    return out


# ─── analyze_data_file ────────────────────────────────────────────────────────

class TestAnalyzeDataFileHandler:
    def test_analyze_data_file_handler(self, tmp_project_db, tmp_path: Path) -> None:
        from aurora_launch.sidecar.methods import dispatch

        xlsx_path = _write_wide_xlsx(tmp_path)
        result = dispatch("analyze_data_file", {"path": str(xlsx_path), "n_rows": 5})

        assert result["status"] == "ok"
        assert "columns" in result
        assert "headers" in result
        assert "rows" in result
        # 4 columns: date, sales_packs, tv_spend, competitor_share
        assert len(result["columns"]) == 4
        headers = result["headers"]
        assert "date" in headers
        assert "sales_packs" in headers
        assert "tv_spend" in headers
        assert "competitor_share" in headers

    def test_analyze_data_file_columns_have_role_confidence_kind(
        self, tmp_project_db, tmp_path: Path
    ) -> None:
        from aurora_launch.sidecar.methods import dispatch

        xlsx_path = _write_wide_xlsx(tmp_path)
        result = dispatch("analyze_data_file", {"path": str(xlsx_path), "n_rows": 5})

        for col in result["columns"]:
            assert "name" in col
            assert "role" in col
            assert "confidence" in col
            assert "kind" in col
            assert col["role"] in ("kpi", "media", "control", "date", "unused", "unknown")
            assert 0.0 <= col["confidence"] <= 1.0

    def test_analyze_data_file_date_column_detected(
        self, tmp_project_db, tmp_path: Path
    ) -> None:
        from aurora_launch.sidecar.methods import dispatch

        xlsx_path = _write_wide_xlsx(tmp_path)
        result = dispatch("analyze_data_file", {"path": str(xlsx_path), "n_rows": 5})

        date_cols = [c for c in result["columns"] if c["name"] == "date"]
        assert len(date_cols) == 1
        assert date_cols[0]["role"] == "date"

    def test_analyze_data_file_missing_file(self, tmp_project_db, tmp_path: Path) -> None:
        """Non-existent path raises SidecarSecurityError (path doesn't exist
        → validate_safe_path fails before reaching data_preview)."""
        from aurora_launch.sidecar.methods import dispatch, SidecarSecurityError

        with pytest.raises(SidecarSecurityError):
            dispatch("analyze_data_file", {"path": str(tmp_path / "nonexistent.xlsx")})

    def test_analyze_data_file_empty_path_raises(self, tmp_project_db) -> None:
        from aurora_launch.sidecar.methods import dispatch

        with pytest.raises(ValueError, match="path must be non-empty"):
            dispatch("analyze_data_file", {"path": ""})


# ─── validate_wide_table ──────────────────────────────────────────────────────

class TestValidateWideTableHandler:
    def test_validate_wide_table_no_overrides(
        self, tmp_project_db, tmp_path: Path
    ) -> None:
        from aurora_launch.sidecar.methods import dispatch

        xlsx_path = _write_wide_xlsx(tmp_path)
        result = dispatch("validate_wide_table", {"path": str(xlsx_path)})

        assert result["status"] in ("ok", "warning", "error")
        assert "verdict" in result
        assert "detected" in result
        assert "columns" in result

    def test_validate_wide_table_detected_roles_present(
        self, tmp_project_db, tmp_path: Path
    ) -> None:
        from aurora_launch.sidecar.methods import dispatch

        xlsx_path = _write_wide_xlsx(tmp_path)
        result = dispatch("validate_wide_table", {"path": str(xlsx_path)})

        detected = result["detected"]
        assert "date" in detected
        assert "kpi" in detected
        assert "media" in detected
        assert "control" in detected
        assert "n_predictors" in detected
        assert "ratio" in detected
        assert "date_frequency" in detected

    def test_validate_wide_table_with_overrides(
        self, tmp_project_db, tmp_path: Path
    ) -> None:
        """User overrides tv_spend role to 'unused' — detected.media should not include it."""
        from aurora_launch.sidecar.methods import dispatch

        xlsx_path = _write_wide_xlsx(tmp_path)

        # Without override: tv_spend classified as media
        result_no_override = dispatch("validate_wide_table", {"path": str(xlsx_path)})
        assert "tv_spend" in result_no_override["detected"]["media"]

        # With override: tv_spend → unused
        result_override = dispatch("validate_wide_table", {
            "path": str(xlsx_path),
            "role_overrides": {"tv_spend": "unused"},
        })

        # tv_spend should NOT be in media after override
        assert "tv_spend" not in result_override["detected"]["media"]

        # And its confidence should be 1.0 (user override = max)
        overridden_col = next(
            c for c in result_override["columns"] if c["name"] == "tv_spend"
        )
        assert overridden_col["role"] == "unused"
        assert overridden_col["confidence"] == pytest.approx(1.0)

    def test_validate_wide_table_competitor_override_to_control(
        self, tmp_project_db, tmp_path: Path
    ) -> None:
        """competitor_share already control — override confirms confidence=1.0."""
        from aurora_launch.sidecar.methods import dispatch

        xlsx_path = _write_wide_xlsx(tmp_path)
        result = dispatch("validate_wide_table", {
            "path": str(xlsx_path),
            "role_overrides": {"competitor_share": "control"},
        })

        comp_col = next(
            c for c in result["columns"] if c["name"] == "competitor_share"
        )
        assert comp_col["role"] == "control"
        assert comp_col["confidence"] == pytest.approx(1.0)

    def test_validate_wide_table_missing_file(self, tmp_project_db, tmp_path: Path) -> None:
        """Non-existent path raises SidecarSecurityError (path doesn't exist
        → validate_safe_path fails before reaching validate_data)."""
        from aurora_launch.sidecar.methods import dispatch, SidecarSecurityError

        with pytest.raises(SidecarSecurityError):
            dispatch("validate_wide_table", {"path": str(tmp_path / "missing.xlsx")})

    def test_validate_wide_table_empty_path_raises(self, tmp_project_db) -> None:
        from aurora_launch.sidecar.methods import dispatch

        with pytest.raises(ValueError, match="path must be non-empty"):
            dispatch("validate_wide_table", {"path": ""})

    def test_validate_wide_table_invalid_role_override_rejected(
        self, tmp_project_db, tmp_path: Path
    ) -> None:
        """Audit fix 2026-05-18: role_overrides values МUST быть из whitelist."""
        from aurora_launch.sidecar.methods import dispatch

        xlsx_path = _write_wide_xlsx(tmp_path)

        with pytest.raises(ValueError, match="not a valid role"):
            dispatch("validate_wide_table", {
                "path": str(xlsx_path),
                "role_overrides": {"tv_spend": "evil_role"},
            })

    def test_validate_wide_table_all_valid_roles_accepted(
        self, tmp_project_db, tmp_path: Path
    ) -> None:
        """Все 6 канонических ролей принимаются без ValueError."""
        from aurora_launch.sidecar.methods import dispatch

        xlsx_path = _write_wide_xlsx(tmp_path)

        for role in ("kpi", "media", "control", "date", "unused", "unknown"):
            # Не должно поднять
            dispatch("validate_wide_table", {
                "path": str(xlsx_path),
                "role_overrides": {"tv_spend": role},
            })
