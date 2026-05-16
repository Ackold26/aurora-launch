"""Phase 1.C.2 — extended parse_data_file contract для column mapping UI (BTA-6).

Verifies sidecar `parse_data_file` возвращает source_columns + suggested_mapping
+ preview_rows + available_canonical_fields helper'ы, которые wizard Step 1
использует для auto-mapping UI.
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


def _write_dsm_v2024_csv(tmp_path: Path) -> Path:
    """Создаёт минимальный DSM V2024 CSV (semicolon separator, ISO date)."""
    csv_path = tmp_path / "sample.dsm.csv"
    csv_path.write_text(
        "Бренд;Производитель;Дата;Продажи_упаковки;Продажи_рубли;Доля_рынка;АТХ_код\n"
        "Кагоцел;Ниармедик;2024-01-01;100;50000;1.2;J05AX\n"
        "Кагоцел;Ниармедик;2024-01-08;120;60000;1.4;J05AX\n",
        encoding="utf-8-sig",
    )
    return csv_path


class TestParseDataFileColumnMappingContract:
    def test_returns_source_columns_from_adapter_mapping(self, tmp_path: Path) -> None:
        from aurora_launch.sidecar.methods import dispatch

        csv_path = _write_dsm_v2024_csv(tmp_path)
        result = dispatch("parse_data_file", {"path": str(csv_path)})

        assert "source_columns" in result
        assert isinstance(result["source_columns"], list)
        # DSM V2024 source columns
        assert "Бренд" in result["source_columns"]
        assert "Дата" in result["source_columns"]
        assert "Продажи_рубли" in result["source_columns"]

    def test_returns_suggested_mapping_source_to_canonical(self, tmp_path: Path) -> None:
        from aurora_launch.sidecar.methods import dispatch

        csv_path = _write_dsm_v2024_csv(tmp_path)
        result = dispatch("parse_data_file", {"path": str(csv_path)})

        assert "suggested_mapping" in result
        mapping = result["suggested_mapping"]
        # Adapter's canonical_record_mapping — source → canonical
        assert mapping["Бренд"] == "brand_name"
        assert mapping["Дата"] == "period_date"
        assert mapping["Продажи_рубли"] == "sales_value_rub"
        assert mapping["АТХ_код"] == "atc_code"

    def test_returns_preview_rows_max_5(self, tmp_path: Path) -> None:
        from aurora_launch.sidecar.methods import dispatch

        csv_path = _write_dsm_v2024_csv(tmp_path)
        result = dispatch("parse_data_file", {"path": str(csv_path)})

        assert "preview_rows" in result
        assert isinstance(result["preview_rows"], list)
        # Файл имеет 2 records — preview всё ≤ 5
        assert len(result["preview_rows"]) == 2
        assert result["preview_rows"][0]["brand_name"] == "Кагоцел"

    def test_returns_available_canonical_fields_registry(self, tmp_path: Path) -> None:
        from aurora_launch.sidecar.methods import dispatch

        csv_path = _write_dsm_v2024_csv(tmp_path)
        result = dispatch("parse_data_file", {"path": str(csv_path)})

        assert "available_canonical_fields" in result
        fields = result["available_canonical_fields"]
        assert isinstance(fields, list)
        # Минимум 18 канонических полей зарегистрировано
        assert len(fields) >= 18

        # Каждое поле имеет required keys
        for f in fields:
            assert "id" in f and "label_ru" in f and "group" in f

        # Critical fields присутствуют
        ids = {f["id"] for f in fields}
        assert "brand_name" in ids
        assert "period_date" in ids
        assert "sales_value_rub" in ids
        assert "atc_code" in ids
        assert "channel_name" in ids
        assert "grp" in ids

    def test_canonical_fields_grouped_correctly(self, tmp_path: Path) -> None:
        """5 категорий: identity / period / sales / media / category."""
        from aurora_launch.sidecar.methods import dispatch

        csv_path = _write_dsm_v2024_csv(tmp_path)
        result = dispatch("parse_data_file", {"path": str(csv_path)})

        groups = {f["group"] for f in result["available_canonical_fields"]}
        assert groups == {"identity", "period", "sales", "media", "category"}

    def test_labels_in_russian(self, tmp_path: Path) -> None:
        """Premium UX: customer видит русские labels в dropdown."""
        from aurora_launch.sidecar.methods import dispatch

        csv_path = _write_dsm_v2024_csv(tmp_path)
        result = dispatch("parse_data_file", {"path": str(csv_path)})

        labels = {f["id"]: f["label_ru"] for f in result["available_canonical_fields"]}
        assert labels["brand_name"] == "Бренд"
        assert labels["period_date"] == "Период / Дата"
        assert labels["sales_value_rub"] == "Продажи (рубли)"
        assert labels["atc_code"] == "АТХ-код"

    def test_existing_fields_still_present(self, tmp_path: Path) -> None:
        """1.C.2 не должна сломать existing contract (legacy callers)."""
        from aurora_launch.sidecar.methods import dispatch

        csv_path = _write_dsm_v2024_csv(tmp_path)
        result = dispatch("parse_data_file", {"path": str(csv_path)})

        # Legacy fields
        assert "adapter_id" in result
        assert result["adapter_id"] == "dsm_v2024"
        assert "adapter_metadata" in result
        assert "record_count" in result
        assert result["record_count"] == 2
        assert "records" in result
        assert len(result["records"]) == 2
