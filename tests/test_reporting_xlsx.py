"""Sprint B4 deliverable #3 — the analyst XLSX workbook (spec §2.3).

Build the 8-sheet Launch Forecast workbook from the real forecast fixture and
assert structure, real data in the populated sheets, on-brand header styling, and
that data-gated sheets are present-but-flagged (never silently dropped).
"""

from __future__ import annotations

import pytest

from openpyxl import load_workbook

from aurora_launch.reporting.context import build_report_context
from aurora_launch.reporting.render_xlsx import build_launch_forecast_xlsx
from aurora_launch.sample_bundles.report_fixture import build_sample_forecast_fixture


@pytest.fixture(scope="module")
def workbook(tmp_path_factory) -> dict:
    ctx = build_report_context(build_sample_forecast_fixture())
    out = tmp_path_factory.mktemp("xlsx") / "launch_forecast.xlsx"
    manifest = build_launch_forecast_xlsx(ctx, str(out))
    return {"path": str(out), "manifest": manifest, "wb": load_workbook(str(out))}


class TestWorkbookStructure:
    def test_eight_sheets_in_spec_order(self, workbook: dict) -> None:
        assert workbook["wb"].sheetnames == [
            "Summary", "12w forecast", "26w forecast", "52w forecast",
            "Channel decomposition", "Anchors", "Proxy summary", "Diagnostics",
        ]

    def test_summary_has_real_metrics(self, workbook: dict) -> None:
        ws = workbook["wb"]["Summary"]
        # header + 3 horizons.
        assert ws.max_row == 4
        # 12w total is a real forecast number (≈166M ₽), not a placeholder.
        assert ws["B2"].value > 1_000_000
        assert ws["B2"].number_format.endswith('"₽"')

    def test_weekly_sheets_full_horizon(self, workbook: dict) -> None:
        # 12 / 26 / 52 weekly rows + header each.
        for title, weeks in (("12w forecast", 12), ("26w forecast", 26), ("52w forecast", 52)):
            assert workbook["wb"][title].max_row == weeks + 1

    def test_proxy_sheet_includes_six_dimensions(self, workbook: dict) -> None:
        ws = workbook["wb"]["Proxy summary"]
        # 5 base params + 6 similarity dimensions + header = 12 rows.
        assert ws.max_row == 12


class TestBrandStyling:
    def test_header_uses_aurora_deep_fill(self, workbook: dict) -> None:
        ws = workbook["wb"]["Summary"]
        # Aurora Deep #0A1628 → ARGB FF0A1628.
        assert ws["A1"].fill.fgColor.rgb == "FF0A1628"
        assert ws.freeze_panes == "A2"


class TestPendingSheetsFlagged:
    def test_data_gated_sheets_reported_not_dropped(self, workbook: dict) -> None:
        pending = workbook["manifest"]["pending"]
        assert set(pending) == {"Channel decomposition", "Anchors", "Diagnostics"}

    def test_pending_sheet_has_note_not_fabricated_data(self, workbook: dict) -> None:
        ws = workbook["wb"]["Channel decomposition"]
        # header row + a single note row, no fabricated numbers.
        assert ws.max_row == 2
        assert isinstance(ws["A2"].value, str) and ws["A2"].value
