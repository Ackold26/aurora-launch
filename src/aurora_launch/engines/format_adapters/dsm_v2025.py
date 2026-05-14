"""DSM Group 2025 format adapter (forward-compat for anticipated 2025 spec).

V2025 introduces (anticipated based on industry trends):
- Tab separator (more robust for multilingual data)
- ISO 8601 datetime с timezone (vs V2024 plain ISO date)
- Additional columns: SKU_id, Region_code, Pricing_segment

Subclasses V2024 for canonical mapping; overrides format-specific bits.
This is forward-compat scaffolding — actual V2025 spec может adjust on real
file release.
"""

from __future__ import annotations

from pathlib import Path

from aurora_launch.engines.format_adapters.dsm_v2024 import DsmAdapterV2024
from aurora_launch.schemas.synthetic_corpus import FormatAdapterContract


class DsmAdapterV2025(DsmAdapterV2024):
    """DSM Group 2025 format adapter (anticipated spec, may adjust on release)."""

    def __init__(self) -> None:
        super().__init__()
        # Override metadata
        self._metadata = FormatAdapterContract(
            adapter_id="dsm_v2025",
            adapter_version="0.1.0",
            schema_version="2025",
            sample_files_glob=["*_dsm_2025_*.csv", "*_dsm_2025_*.tsv", "*.dsm.2025.xlsx"],
            canonical_record_mapping={
                "Бренд": "brand_name",
                "Производитель": "manufacturer_name",
                "SKU": "sku",
                "Регион": "region",
                "Дата_время": "period_date",  # V2025 ISO 8601 datetime (UTC)
                "Продажи_упаковки": "sales_volume_packs",
                "Продажи_рубли": "sales_value_rub",
                "Доля_рынка": "market_share_pct",
                "Ценовой_сегмент": "pricing_segment",
                "АТХ_код": "atc_code",
            },
            detected_signatures=[
                "DSM Group 2025",
                "iso8601_datetime_utc",
                "tab_separator",
            ],
        )

    def detect(self, file_path: str) -> bool:
        path = Path(file_path)
        name_lower = path.name.lower()

        if "dsm_2025" in name_lower and path.suffix.lower() in (".csv", ".tsv", ".xlsx"):
            return True

        # Header sniff (V2025 signature: tab separator + Дата_время column)
        if path.exists() and path.suffix.lower() in (".csv", ".tsv"):
            try:
                with path.open("r", encoding="utf-8-sig") as f:
                    header = f.readline()
                if "\t" in header and "Дата_время" in header:
                    return True
            except (OSError, UnicodeDecodeError):
                pass

        return False

    def parse(self, file_path: str) -> list[dict]:
        """Override parse() for accept .tsv (V2025 specific extension).

        Refuses files >256 MB.
        """
        from aurora_launch.engines.format_adapters import assert_file_size_ok

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"DSM file not found: {file_path}")

        assert_file_size_ok(path)

        if path.suffix.lower() in (".csv", ".tsv"):
            return self._parse_csv(path)
        if path.suffix.lower() in (".xlsx", ".xls"):
            return self._parse_xlsx(path)
        raise ValueError(f"Unsupported DSM V2025 file format: {path.suffix}")

    def _parse_csv(self, path: Path) -> list[dict]:
        """V2025 uses tab separator (works for both .csv and .tsv)."""
        records: list[dict] = []
        with path.open("r", encoding="utf-8-sig") as f:
            header_line = f.readline().strip()
            # Auto-detect: tab if в header, else comma fallback
            sep = "\t" if "\t" in header_line else ","
            headers = [h.strip() for h in header_line.split(sep)]

            mapping = self._metadata.canonical_record_mapping
            canonical_headers = [mapping.get(h, h) for h in headers]

            for line in f:
                values = [v.strip() for v in line.strip().split(sep)]
                if len(values) != len(headers):
                    continue
                record = dict(zip(canonical_headers, values, strict=False))
                records.append(record)

        return records
