"""Mediascope AdEx V1 format adapter (B0.5 §4.1).

Mediascope AdEx tracks advertising spend per advertiser/brand × media channel
× period. V1 format: CSV with "Channek" typo signature column header (legacy).

Per spec §4.1 — built-in adapter alongside DSM.
"""

from __future__ import annotations

from pathlib import Path

from aurora_launch.schemas.synthetic_corpus import FormatAdapterContract


class MediascopeAdExAdapterV1:
    """Mediascope AdEx V1 format adapter."""

    def __init__(self) -> None:
        self._metadata = FormatAdapterContract(
            adapter_id="mediascope_adex_v1",
            adapter_version="0.1.0",
            schema_version="adex_v1",
            sample_files_glob=["*adex*.csv", "*adex*.xlsx", "*mediascope_adex*"],
            canonical_record_mapping={
                "Рекламодатель": "advertiser_name",
                "Бренд": "brand_name",
                "Channek": "channel_name",  # legacy typo preserved
                "Медиа_тип": "media_type",
                "Период": "period_date",
                "Затраты_тыс_руб": "spend_thousand_rub",
                "GRP": "grp",
                "TVR": "tvr",
            },
            detected_signatures=[
                "Mediascope AdEx V1",
                "channek_typo",
            ],
        )

    def detect(self, file_path: str) -> bool:
        """Detect if file matches Mediascope AdEx V1.

        Signature: "Channek" typo in headers OR filename contains 'adex' + V1 markers.
        """
        path = Path(file_path)
        name_lower = path.name.lower()

        if "adex" in name_lower and path.suffix.lower() in (".csv", ".xlsx"):
            # Header sniff for "Channek" signature (V1 typo)
            if path.exists() and path.suffix.lower() == ".csv":
                try:
                    with path.open("r", encoding="utf-8-sig") as f:
                        header = f.readline()
                    if "Channek" in header or "Рекламодатель" in header:
                        return True
                except (OSError, UnicodeDecodeError):
                    pass
            else:
                # XLSX или missing file — match по name
                return True

        return False

    def parse(self, file_path: str) -> list[dict]:
        """Parse Mediascope AdEx V1 file into canonical records.

        Refuses files >256 MB (`MAX_INPUT_FILE_BYTES`) — see
        format_adapters/__init__.py.
        """
        from aurora_launch.engines.format_adapters import assert_file_size_ok

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Mediascope AdEx file not found: {file_path}")

        assert_file_size_ok(path)

        if path.suffix.lower() != ".csv":
            raise NotImplementedError(
                f"Mediascope AdEx XLSX parsing pending Phase B+ "
                f"(stub adapter, only CSV in v0.1.0-b05). Got: {path.suffix}"
            )

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
                records.append(record)

        return records

    def get_metadata(self) -> FormatAdapterContract:
        return self._metadata
