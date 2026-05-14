"""DSM Group 2023 format adapter.

V2023 differs from V2024 в:
- Comma separator (vs V2024 semicolon)
- DD.MM.YYYY date format (vs V2024 ISO 8601)
- Slightly different column names (`Дата_продажи` vs V2024 `Дата`)

Otherwise structurally similar; subclasses V2024 adapter for canonical mapping
+ overrides format-specific bits.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from aurora_launch.engines.format_adapters.dsm_v2024 import DsmAdapterV2024
from aurora_launch.schemas.synthetic_corpus import FormatAdapterContract

_log = logging.getLogger(__name__)


class DsmAdapterV2023(DsmAdapterV2024):
    """DSM Group 2023 format adapter (subclasses V2024 for canonical mapping)."""

    def __init__(self) -> None:
        super().__init__()
        # Override metadata
        self._metadata = FormatAdapterContract(
            adapter_id="dsm_v2023",
            adapter_version="0.1.0",
            schema_version="2023",
            sample_files_glob=["*_dsm_2023_*.csv", "*.dsm.2023.xlsx"],
            canonical_record_mapping={
                "Бренд": "brand_name",
                "Производитель": "manufacturer_name",
                "Дата_продажи": "period_date",  # V2023 column name (vs V2024 «Дата»)
                "Продажи_упаковки": "sales_volume_packs",
                "Продажи_рубли": "sales_value_rub",
                "Доля_рынка": "market_share_pct",
                "АТХ_код": "atc_code",
            },
            detected_signatures=[
                "DSM Group 2023",
                "ddmmyyyy_dates",
                "csv_separator=,",
            ],
        )

    def detect(self, file_path: str) -> bool:
        path = Path(file_path)
        name_lower = path.name.lower()

        if "dsm_2023" in name_lower and path.suffix.lower() in (".csv", ".xlsx"):
            return True

        if path.suffix.lower() == ".csv" and ".dsm" in name_lower and "2023" in name_lower:
            return True

        # Header sniff (V2023 signature: comma separator + Дата_продажи column)
        if path.exists() and path.suffix.lower() == ".csv":
            try:
                with path.open("r", encoding="utf-8-sig") as f:
                    header = f.readline()
                if "," in header and "Дата_продажи" in header:
                    return True
            except (OSError, UnicodeDecodeError):
                pass

        return False

    def _parse_csv(self, path: Path) -> list[dict]:
        """V2023 uses comma separator + DD.MM.YYYY date format.

        Refuses files >256 MB (`MAX_INPUT_FILE_BYTES`).
        """
        from aurora_launch.engines.format_adapters import assert_file_size_ok

        assert_file_size_ok(path)

        records: list[dict] = []
        with path.open("r", encoding="utf-8-sig") as f:
            header_line = f.readline().strip()
            headers = [h.strip() for h in header_line.split(",")]

            mapping = self._metadata.canonical_record_mapping
            canonical_headers = [mapping.get(h, h) for h in headers]

            for line in f:
                values = [v.strip() for v in line.strip().split(",")]
                if len(values) != len(headers):
                    continue
                record = dict(zip(canonical_headers, values, strict=False))
                # Convert DD.MM.YYYY → ISO YYYY-MM-DD if period_date present
                if "period_date" in record:
                    record["period_date"] = self._normalize_date(record["period_date"])
                records.append(record)

        return records

    def _normalize_date(self, raw_date: str) -> str:
        """DD.MM.YYYY → YYYY-MM-DD.

        H-A2-6 fix: log warning if format unexpected (was: silent passthrough).
        Customer / dev gets visibility on data quality issues при ingestion.
        """
        try:
            dt = datetime.strptime(raw_date, "%d.%m.%Y")
            return dt.date().isoformat()
        except ValueError:
            _log.warning(
                "DSM V2023 date format unexpected: %r — expected DD.MM.YYYY. "
                "Passing through unchanged; downstream parsers may fail.",
                raw_date,
            )
            return raw_date
