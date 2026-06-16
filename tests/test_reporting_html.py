"""Sprint B4 deliverable #2 — the standalone HTML report (spec §2.2).

Build the 8-section Launch Forecast HTML from the real forecast fixture and assert
it is a self-contained, branded, accessible artifact built by CONSUMING the Core
design-shell (`aurora_reporting.aurora_html.design_shell`): the layout.css component
classes are present, a hash-based CSP is emitted, Core PNG charts + OFL fonts are
inlined (no external loads), and NO forbidden phrase reaches the rendered text.

Launch owns the composition; the design layer is consumed from Core (no copy-lift,
no drift with the PPTX canon).
"""

from __future__ import annotations

import re

import pytest

from aurora_launch.reporting import copy
from aurora_launch.reporting.context import build_report_context
from aurora_launch.reporting.render_html import build_launch_forecast_html
from aurora_launch.sample_bundles.report_fixture import build_sample_forecast_fixture


@pytest.fixture(scope="module")
def report(tmp_path_factory) -> dict:
    ctx = build_report_context(build_sample_forecast_fixture())
    out = tmp_path_factory.mktemp("html") / "launch_forecast.html"
    manifest = build_launch_forecast_html(
        ctx, str(out), aurora_version="v0.2.5", project_id="test-0001-acceptance",
        date_generated="2026-06-15", hash_signature="0" * 64,
    )
    return {"doc": out.read_text(encoding="utf-8"), "manifest": manifest}


class TestConsumesDesignShell:
    def test_eight_sections(self, report: dict) -> None:
        # cover + exec + proxy + caveats + 3 forecast + methodology, all .section.
        assert report["doc"].count('class="section"') == 8
        assert report["manifest"]["sections"] == 8
        assert report["manifest"]["design_shell"] is True

    def test_layout_css_components_present(self, report: dict) -> None:
        # Core layout.css component classes — proves consumption, not a hand-rolled layer.
        for cls in ("action-table", "mqs-card", "big-number", "scqar-block", "formula-box",
                    "cover-meta", "sacred-lime"):
            assert cls in report["doc"], cls

    def test_hash_based_csp_emitted(self, report: dict) -> None:
        assert report["manifest"]["csp"] is True
        assert "Content-Security-Policy" in report["doc"]
        assert "sha256-" in report["doc"]  # hash-based, not 'unsafe-inline'

    def test_five_charts_inlined(self, report: dict) -> None:
        assert report["doc"].count("data:image/png;base64,") == 5


class TestStandalone:
    def test_fonts_inlined(self, report: dict) -> None:
        assert report["doc"].count("data:font/woff2;base64,") == 6

    def test_no_external_resource_loads(self, report: dict) -> None:
        doc = report["doc"]
        # self-contained: no external script/style/font/image fetches. (A data-URI
        # favicon <link> and SVG xmlns namespaces are not network loads.)
        assert not re.search(r"<script[^>]+src=", doc)
        assert 'src="http' not in doc
        assert 'href="http' not in doc
        assert "echarts.common" not in doc  # ECharts runtime intentionally excluded


class TestAccessibilityAndHygiene:
    def test_reduced_motion_respected(self, report: dict) -> None:
        # layout.css carries the prefers-reduced-motion guard.
        assert "prefers-reduced-motion" in report["doc"]

    def test_no_forbidden_phrase_in_rendered_text(self, report: dict) -> None:
        doc = report["doc"]
        vis = re.sub(r"<style.*?</style>", " ", doc, flags=re.S)
        vis = re.sub(r"<script.*?</script>", " ", vis, flags=re.S)
        vis = re.sub(r"<[^>]+>", " ", vis)
        assert copy.find_forbidden_phrases(vis) == []


class TestPendingDataLogged:
    def test_channel_and_sensitivity_skipped(self, report: dict) -> None:
        skipped = report["manifest"]["skipped"]
        for key in ("forecast_12w", "forecast_26w", "forecast_52w"):
            assert f"{key}.channel_decomposition" in skipped
            assert f"{key}.sensitivity" in skipped
