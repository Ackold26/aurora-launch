"""Sprint B4 deliverable #2 — the standalone HTML report (spec §2.2).

Build the 8-section Launch Forecast HTML from the real forecast fixture and assert
it is a self-contained, accessible, on-brand artifact: all sections present, Core
PNG charts inlined, OFL fonts inlined (no brotli / no network), reduced-motion
respected, and NO forbidden phrase in the rendered text.

Launch owns this composition (Core `build_html` is MMM-pipeline-shaped); the design
tokens are generated from the Core AURORA_HYBRID theme and the fonts reuse the
Core-bundled woff2 — DRY with the Core design SSOT.
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


class TestHtmlStructure:
    def test_russian_lang(self, report: dict) -> None:
        assert 'lang="ru"' in report["doc"]

    def test_eight_sections_present(self, report: dict) -> None:
        # cover is a <header>; the 7 <section>s = exec, proxy, caveats, 3 forecast,
        # methodology — the 8-section template (cover + 7).
        assert report["doc"].count("<section>") == 7

    def test_five_charts_inlined(self, report: dict) -> None:
        # radar + 3 forecast cones + uncertainty donut, all Core PNG primitives.
        assert report["doc"].count("data:image/png;base64,") == 5


class TestStandaloneAndBranded:
    def test_fonts_inlined_no_network(self, report: dict) -> None:
        assert report["doc"].count("data:font/woff2;base64,") == 6
        assert report["manifest"]["fonts_inlined"] == 6

    def test_no_external_resource_references(self, report: dict) -> None:
        # standalone: no http(s) src/href and no external script/link tags.
        assert "http://" not in report["doc"] and "https://" not in report["doc"]
        assert "<script" not in report["doc"]

    def test_tokens_from_core_theme(self, report: dict) -> None:
        # :root generated from AURORA_HYBRID — Aurora Deep + Sacred Lime present.
        assert "--deep-100:#0A1628" in report["doc"]
        assert "--lime:#CCFF00" in report["doc"]


class TestAccessibilityAndHygiene:
    def test_reduced_motion_respected(self, report: dict) -> None:
        assert "prefers-reduced-motion" in report["doc"]

    def test_no_forbidden_phrase_in_rendered_text(self, report: dict) -> None:
        visible = re.sub(r"<style.*?</style>", " ", report["doc"], flags=re.S)
        visible = re.sub(r"<[^>]+>", " ", visible)
        assert copy.find_forbidden_phrases(visible) == []


class TestPendingDataLogged:
    def test_channel_and_sensitivity_skipped(self, report: dict) -> None:
        skipped = report["manifest"]["skipped"]
        for key in ("forecast_12w", "forecast_26w", "forecast_52w"):
            assert f"{key}.channel_decomposition" in skipped
            assert f"{key}.sensitivity" in skipped
