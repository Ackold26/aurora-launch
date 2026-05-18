"""Unit tests for ported validator.py + column_detection.py (file reader port 2026-05-18).

Tests:
- detect_column_role_with_confidence: exact patterns
- data_preview: xlsx fixture + unsupported format
- validate_data: smoke with date+kpi+media+control columns
"""
from __future__ import annotations

from pathlib import Path

import pytest


# ─── detect_column_role_with_confidence ──────────────────────────────────────

class TestDetectColumnRole:
    def test_detect_column_role_date_exact(self) -> None:
        from aurora_launch.engines.validator import detect_column_role_with_confidence

        role, confidence = detect_column_role_with_confidence("date")
        assert role == "date"
        assert confidence == pytest.approx(0.97)

    def test_detect_column_role_kpi(self) -> None:
        from aurora_launch.engines.validator import detect_column_role_with_confidence

        role, confidence = detect_column_role_with_confidence("sales_packs")
        assert role == "kpi"
        assert confidence > 0.55

    def test_detect_column_role_media(self) -> None:
        from aurora_launch.engines.validator import detect_column_role_with_confidence

        role, confidence = detect_column_role_with_confidence("tv_grp")
        assert role == "media"
        assert confidence > 0.0

    def test_detect_column_role_control_competitor(self) -> None:
        from aurora_launch.engines.validator import detect_column_role_with_confidence

        role, confidence = detect_column_role_with_confidence("competitor_share")
        assert role == "control"
        assert confidence == pytest.approx(0.90)

    def test_detect_column_role_unknown(self) -> None:
        from aurora_launch.engines.validator import detect_column_role_with_confidence

        role, confidence = detect_column_role_with_confidence("xyz123")
        assert role == "unknown"
        assert confidence == pytest.approx(0.0)

    def test_detect_column_role_unused_som(self) -> None:
        from aurora_launch.engines.validator import detect_column_role_with_confidence

        role, confidence = detect_column_role_with_confidence("market_share")
        assert role == "unused"
        assert confidence == pytest.approx(0.85)


# ─── data_preview ─────────────────────────────────────────────────────────────

class TestDataPreview:
    def _write_sample_xlsx(self, tmp_path: Path) -> Path:
        """Write a minimal wide-table xlsx with 5 columns and 10 rows."""
        import pandas as pd
        import numpy as np

        rng = np.random.default_rng(42)
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=10, freq="W"),
            "sales_packs": rng.integers(100, 500, 10),
            "tv_grp": rng.uniform(50, 200, 10).round(1),
            "olv_impressions": rng.integers(10000, 50000, 10),
            "competitor_share": rng.uniform(0.1, 0.3, 10).round(3),
        })
        out = tmp_path / "sample.xlsx"
        df.to_excel(out, index=False)
        return out

    def test_data_preview_xlsx(self, tmp_path: Path) -> None:
        from aurora_launch.engines.validator import data_preview

        xlsx_path = self._write_sample_xlsx(tmp_path)
        result = data_preview(str(xlsx_path), n_rows=5)

        assert result["status"] == "ok"
        assert "headers" in result
        assert "rows" in result
        assert "dtypes" in result
        assert "shape" in result
        assert "file_name" in result
        assert "size_kb" in result
        assert len(result["headers"]) == 5
        assert len(result["rows"]) == 5  # n_rows=5

    def test_data_preview_unsupported_format(self, tmp_path: Path) -> None:
        from aurora_launch.engines.validator import data_preview

        txt_file = tmp_path / "data.txt"
        txt_file.write_text("some,content\n1,2\n")

        result = data_preview(str(txt_file))
        assert result["status"] == "error"
        assert "message" in result

    def test_data_preview_missing_file(self, tmp_path: Path) -> None:
        from aurora_launch.engines.validator import data_preview

        result = data_preview(str(tmp_path / "nonexistent.xlsx"))
        assert result["status"] == "error"


# ─── validate_data ────────────────────────────────────────────────────────────

class TestValidateData:
    def _write_wide_table(self, tmp_path: Path) -> Path:
        """Write a valid wide table: date + kpi + media + control (52 rows)."""
        import pandas as pd
        import numpy as np

        rng = np.random.default_rng(0)
        df = pd.DataFrame({
            "date": pd.date_range("2023-01-02", periods=52, freq="W"),
            "sales_packs": rng.integers(500, 2000, 52),
            "tv_spend": rng.uniform(100_000, 500_000, 52).round(0),
            "olv_impressions": rng.integers(50_000, 200_000, 52),
            "competitor_share": rng.uniform(0.1, 0.4, 52).round(3),
            "distribution": rng.uniform(0.6, 0.95, 52).round(3),
        })
        out = tmp_path / "wide_table.xlsx"
        df.to_excel(out, index=False)
        return out

    def test_validate_data_full(self, tmp_path: Path) -> None:
        from aurora_launch.engines.validator import validate_data

        xlsx_path = self._write_wide_table(tmp_path)
        result = validate_data(str(xlsx_path))

        # Top-level keys present
        assert "status" in result
        assert "verdict" in result
        assert "columns" in result
        assert "detected" in result
        assert "file" in result

        # Verdict text is one of the known values
        assert result["verdict"] in (
            "ГОТОВ К МОДЕЛИРОВАНИЮ",
            "ГОТОВ К МОДЕЛИРОВАНИЮ (с оговорками)",
            "ТРЕБУЕТ ДОРАБОТКИ",
        )

        # Column roles detected
        detected = result["detected"]
        assert detected["date"] == "date"
        assert "sales_packs" in detected["kpi"]
        # media columns
        assert len(detected["media"]) >= 1
        media_names = detected["media"]
        assert any("spend" in m or "impressions" in m for m in media_names)
