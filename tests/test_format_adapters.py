"""Tests for format adapter registry + DSM/Mediascope adapters."""

from __future__ import annotations

from pathlib import Path

import pytest

from aurora_launch.engines.format_adapters.dsm_v2024 import DsmAdapterV2024
from aurora_launch.engines.format_adapters.mediascope_adex import MediascopeAdExAdapterV1
from aurora_launch.engines.format_adapters.registry import (
    AdapterRegistry,
    build_default_registry,
)


class TestAdapterRegistry:
    def test_empty_registry(self) -> None:
        reg = AdapterRegistry()
        assert reg.list_adapters() == []
        assert reg.detect("any.csv") is None

    def test_register_adapter(self) -> None:
        reg = AdapterRegistry()
        reg.register(DsmAdapterV2024())
        adapters = reg.list_adapters()
        assert len(adapters) == 1
        assert adapters[0].adapter_id == "dsm_v2024"

    def test_register_idempotent_replaces_existing(self) -> None:
        reg = AdapterRegistry()
        reg.register(DsmAdapterV2024())
        reg.register(DsmAdapterV2024())  # same id — replaces
        adapters = reg.list_adapters()
        assert len(adapters) == 1

    def test_default_registry_has_builtins(self) -> None:
        reg = build_default_registry()
        ids = {a.adapter_id for a in reg.list_adapters()}
        assert "dsm_v2024" in ids
        assert "mediascope_adex_v1" in ids

    def test_get_by_id(self) -> None:
        reg = build_default_registry()
        adapter = reg.get_by_id("dsm_v2024")
        assert adapter is not None
        assert adapter.get_metadata().adapter_id == "dsm_v2024"

    def test_get_by_id_not_found(self) -> None:
        reg = build_default_registry()
        adapter = reg.get_by_id("nonexistent_adapter")
        assert adapter is None


class TestDsmAdapterV2024:
    def test_metadata(self) -> None:
        adapter = DsmAdapterV2024()
        meta = adapter.get_metadata()
        assert meta.adapter_id == "dsm_v2024"
        assert "Бренд" in meta.canonical_record_mapping
        assert meta.canonical_record_mapping["Бренд"] == "brand_name"

    def test_detect_xlsx_by_filename(self) -> None:
        adapter = DsmAdapterV2024()
        assert adapter.detect("/some/path/myfile.dsm.xlsx") is True
        assert adapter.detect("/some/path/myfile.xlsx") is False  # no .dsm marker

    def test_detect_csv_by_filename(self) -> None:
        adapter = DsmAdapterV2024()
        assert adapter.detect("/path/data_dsm_2024_q1.csv") is True
        assert adapter.detect("/path/data_dsm_2023_q1.csv") is False  # different year

    def test_detect_csv_by_header_sniff(self, tmp_path: Path) -> None:
        adapter = DsmAdapterV2024()
        csv_path = tmp_path / "ambiguous_name.csv"
        csv_path.write_text(
            "Бренд;Дата;Продажи_упаковки\nКагоцел;2024-01-01;100\n",
            encoding="utf-8-sig",
        )
        assert adapter.detect(str(csv_path)) is True

    def test_parse_csv(self, tmp_path: Path) -> None:
        adapter = DsmAdapterV2024()
        csv_path = tmp_path / "dsm_2024_test.csv"
        csv_path.write_text(
            "Бренд;Дата;Продажи_упаковки\nКагоцел;2024-01-01;100\nВенарус;2024-01-08;75\n",
            encoding="utf-8-sig",
        )
        records = adapter.parse(str(csv_path))
        assert len(records) == 2
        # Mapped to canonical names
        assert records[0]["brand_name"] == "Кагоцел"
        assert records[0]["period_date"] == "2024-01-01"
        assert records[0]["sales_volume_packs"] == "100"

    def test_parse_missing_file_raises(self) -> None:
        adapter = DsmAdapterV2024()
        with pytest.raises(FileNotFoundError):
            adapter.parse("/nonexistent/path.csv")


class TestMediascopeAdExAdapterV1:
    def test_metadata(self) -> None:
        adapter = MediascopeAdExAdapterV1()
        meta = adapter.get_metadata()
        assert meta.adapter_id == "mediascope_adex_v1"
        # Channek typo preserved in mapping
        assert "Channek" in meta.canonical_record_mapping

    def test_detect_by_filename(self) -> None:
        adapter = MediascopeAdExAdapterV1()
        assert adapter.detect("/path/q1_adex.csv") is True
        assert adapter.detect("/path/random_file.csv") is False

    def test_parse_csv(self, tmp_path: Path) -> None:
        adapter = MediascopeAdExAdapterV1()
        csv_path = tmp_path / "q1_adex.csv"
        csv_path.write_text(
            "Рекламодатель,Бренд,Channek,Период,Затраты_тыс_руб\n"
            "OBL,Венарус,TV,2024-01,500\n",
            encoding="utf-8-sig",
        )
        records = adapter.parse(str(csv_path))
        assert len(records) == 1
        assert records[0]["channel_name"] == "TV"
        assert records[0]["spend_thousand_rub"] == "500"


class TestEndToEndDetection:
    def test_dsm_file_routed_to_dsm_adapter(self, tmp_path: Path) -> None:
        reg = build_default_registry()
        csv_path = tmp_path / "data_dsm_2024.csv"
        csv_path.write_text("Бренд;Дата\nКагоцел;2024-01-01\n", encoding="utf-8-sig")

        adapter = reg.detect(str(csv_path))
        assert adapter is not None
        assert adapter.get_metadata().adapter_id == "dsm_v2024"

    def test_mediascope_file_routed_to_mediascope(self, tmp_path: Path) -> None:
        reg = build_default_registry()
        csv_path = tmp_path / "q1_adex.csv"
        csv_path.write_text(
            "Рекламодатель,Бренд,Channek\nOBL,Венарус,TV\n",
            encoding="utf-8-sig",
        )
        adapter = reg.detect(str(csv_path))
        assert adapter is not None
        assert adapter.get_metadata().adapter_id == "mediascope_adex_v1"

    def test_unknown_file_returns_none(self, tmp_path: Path) -> None:
        reg = build_default_registry()
        random_path = tmp_path / "random_data.csv"
        random_path.write_text("col1,col2\nval1,val2\n", encoding="utf-8")
        adapter = reg.detect(str(random_path))
        # No adapter matches — None
        assert adapter is None
