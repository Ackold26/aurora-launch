"""Mediascope TV Index V1 format adapter.

TV Index — телесмотрение panel data. Per memory `project_aurora_data_studio_concept`
v0.3 spec v0.1: multi-row header (2-3 rows) + variable audiences (2-4+ groups
per file) + «Channek» typo signature column header (legacy carries from AdEx).

Production parsing requires:
- Multi-row header detection (look для blank cells signalling group separators)
- Audience block extraction (one block per audience group)
- Long-format normalization (channel × audience × period → record per row)

V0.1 implementation handles common case (single audience group, 2-row header).
Multi-audience parsing is Phase B+ deliverable.
"""

from __future__ import annotations

from pathlib import Path

from aurora_launch.schemas.synthetic_corpus import FormatAdapterContract


class MediascopeTvIndexAdapterV1:
    """Mediascope TV Index V1 (multi-row header, GRP/TVR/Reach metrics)."""

    def __init__(self) -> None:
        self._metadata = FormatAdapterContract(
            adapter_id="mediascope_tv_index_v1",
            adapter_version="0.1.0",
            schema_version="tv_index_v1",
            sample_files_glob=["*tv_index*.csv", "*tv_index*.xlsx", "*PaloMars*", "*tv_panel*"],
            canonical_record_mapping={
                "Канал": "channel_name",
                "Channek": "channel_name",  # legacy typo carries from AdEx
                "Период": "period_date",
                "Дата": "period_date",
                "TVR": "tvr",
                "GRP": "grp",
                "Reach": "reach_pct",
                "Reach_1+": "reach_pct",
                "Audience": "audience_group",
                "Аудитория": "audience_group",
            },
            detected_signatures=[
                "Mediascope TV Index V1",
                "multi_row_header",
                "channek_typo",
            ],
        )

    def detect(self, file_path: str) -> bool:
        path = Path(file_path)
        name_lower = path.name.lower()

        # Filename hints (TV Index typical names)
        if any(s in name_lower for s in ("tv_index", "tv_panel", "palomars")):
            if path.suffix.lower() in (".csv", ".xlsx"):
                return True

        # Header sniff
        if path.exists() and path.suffix.lower() == ".csv":
            try:
                with path.open("r", encoding="utf-8-sig") as f:
                    header = f.readline()
                if "TVR" in header and ("Канал" in header or "Channek" in header):
                    return True
            except (OSError, UnicodeDecodeError):
                pass

        return False

    def parse(self, file_path: str) -> list[dict]:
        """Parse TV Index file into canonical records.

        V0.1: single-audience parsing (2-row header). Multi-audience blocks
        extraction → Phase B+.
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"TV Index file not found: {file_path}")

        if path.suffix.lower() != ".csv":
            raise NotImplementedError(
                "TV Index XLSX parsing pending Phase B+ "
                "(multi-row header + variable audiences). v0.1.0-b05 ships CSV only."
            )

        records: list[dict] = []
        with path.open("r", encoding="utf-8-sig") as f:
            lines = [line.strip() for line in f if line.strip()]

        if not lines:
            return []

        # Heuristic: detect single-row vs multi-row header
        # Single-row: first line has «TVR» / «GRP» metric columns
        first_line = lines[0]
        if "TVR" in first_line or "GRP" in first_line:
            # Single-row header
            header_idx = 0
        else:
            # Two-row header: row 0 = audience labels, row 1 = metric labels
            # Use row 1 as canonical header
            header_idx = 1

        headers = [h.strip() for h in lines[header_idx].split(",")]

        mapping = self._metadata.canonical_record_mapping
        canonical_headers = [mapping.get(h, h) for h in headers]

        for line in lines[header_idx + 1:]:
            values = [v.strip() for v in line.split(",")]
            if len(values) != len(headers):
                continue
            record = dict(zip(canonical_headers, values, strict=False))
            records.append(record)

        return records

    def get_metadata(self) -> FormatAdapterContract:
        return self._metadata
