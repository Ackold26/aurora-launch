"""Sprint B4 report-prep: forecast fixture (E2E smoke) + RU copy + context adapter.

These are the Launch-local report pieces built ahead of the Core aurora_reporting
primitives: a real end-to-end forecast fixture, the customer-facing RU copy +
forbidden-phrase guard (spec §4.2/§4.3), and the forecast→8-section context adapter.
The fixture test doubles as an E2E smoke of the forecast pipeline.
"""

from __future__ import annotations

import pytest

from aurora_launch.reporting import context, copy
from aurora_launch.sample_bundles.report_fixture import build_sample_forecast_fixture


# Real E2E forecast — built once for the module (proxy → anchors → orchestrator).
@pytest.fixture(scope="module")
def fixture() -> dict:
    return build_sample_forecast_fixture()


# ── Fixture: E2E forecast smoke ──────────────────────────────────────────────


class TestForecastFixture:
    def test_three_horizons_present(self, fixture: dict) -> None:
        weeks = sorted(h["horizon_weeks"] for h in fixture["horizons"])
        assert weeks == [12, 26, 52]

    def test_each_horizon_has_valid_ci_points(self, fixture: dict) -> None:
        for h in fixture["horizons"]:
            assert len(h["points"]) == h["horizon_weeks"]
            for p in h["points"]:
                assert p["ci_lower"] <= p["mean"] <= p["ci_upper"]

    def test_totals_increase_with_horizon(self, fixture: dict) -> None:
        by_weeks = {h["horizon_weeks"]: h["total_forecast"] for h in fixture["horizons"]}
        assert by_weeks[12] < by_weeks[26] < by_weeks[52]

    def test_real_orchestrator_run_not_faked(self, fixture: dict) -> None:
        # A genuine pure-transfer orchestrator run carries its methodology signature.
        for h in fixture["horizons"]:
            assert h["mode"] == "pure_transfer"
            assert h["methodology_signature"] == "pure_transfer_v1"

    def test_summary_keys(self, fixture: dict) -> None:
        s = fixture["summary"]
        for h in (12, 26, 52):
            assert f"total_forecast_{h}w" in s
            assert f"ci_pct_{h}w" in s


# ── Copy: phrases + forbidden guard + tier mapping ───────────────────────────


class TestReportCopy:
    def test_tier_thresholds(self) -> None:
        assert copy.tier_from_similarity(0.90) == "gold"
        assert copy.tier_from_similarity(0.70) == "silver"
        assert copy.tier_from_similarity(0.55) == "bronze"
        assert copy.tier_from_similarity(0.10) == "bronze"

    def test_tier_labels_are_text_not_emoji(self) -> None:
        # Core correction П.7: badges are vector chips, copy carries text only.
        for tier in ("gold", "silver", "bronze"):
            label = copy.tier_label(tier)
            assert label
            assert "🥇" not in label and "🥈" not in label and "🥉" not in label

    def test_headline_matches_spec_shape(self) -> None:
        line = copy.headline_forecast(12, 165_914_363.0, 25.8)
        assert "недель" in line
        assert "млн" in line and "₽" in line
        assert "доверительный" in line

    def test_format_rub_millions(self) -> None:
        out = copy.format_rub_millions(165_914_363.0)
        assert out == "165,9" + chr(0xA0) + "млн" + chr(0xA0) + "₽"

    def test_forbidden_phrases_detected(self) -> None:
        assert copy.find_forbidden_phrases("Это гарантированный результат")
        assert copy.find_forbidden_phrases("Точный прогноз продаж")
        assert copy.find_forbidden_phrases("Бренд превзойдёт конкурентов")

    def test_assert_client_safe_raises_on_forbidden(self) -> None:
        with pytest.raises(ValueError, match="Запрещённые формулировки"):
            copy.assert_client_safe("Aurora даёт точный прогноз")

    def test_assert_client_safe_passes_honest_copy(self) -> None:
        # The spec's own honest phrasing must pass.
        copy.assert_client_safe(
            "Прогноз продаж с уверенностью 95% при заданных предпосылках",
            copy.posterior_update_reminder(),
            copy.transfer_caveat("KAG-2024-anonymized"),
        )


# ── Context adapter: 8 sections + client-safe gate ───────────────────────────


class TestReportContext:
    def test_builds_eight_sections(self, fixture: dict) -> None:
        ctx = context.build_report_context(fixture)
        for key in (
            "cover",
            "executive_summary",
            "proxy_quality",
            "transfer_caveats",
            "forecast_12w",
            "forecast_26w",
            "forecast_52w",
            "methodology",
        ):
            assert key in ctx and ctx[key] is not None

    def test_tier_consistent_with_similarity(self, fixture: dict) -> None:
        ctx = context.build_report_context(fixture)
        # Fixture aggregate 0.70 → silver (Medium).
        assert ctx["executive_summary"]["tier"]["key"] == "silver"

    def test_key_metrics_three_rows(self, fixture: dict) -> None:
        ctx = context.build_report_context(fixture)
        rows = ctx["executive_summary"]["key_metrics"]
        assert [r["period_weeks"] for r in rows] == [12, 26, 52]
        assert all("млн" in r["total_display"] and "₽" in r["total_display"] for r in rows)

    def test_cone_data_shape_for_renderer(self, fixture: dict) -> None:
        ctx = context.build_report_context(fixture)
        cone = ctx["forecast_12w"]["cone"]
        assert len(cone) == 12
        for pt in cone:
            assert pt["lo"] <= pt["mean"] <= pt["hi"]

    def test_radar_six_dimensions(self, fixture: dict) -> None:
        ctx = context.build_report_context(fixture)
        assert len(ctx["proxy_quality"]["radar"]["dimensions"]) == 6

    def test_uncertainty_four_source_sums_to_one(self, fixture: dict) -> None:
        ctx = context.build_report_context(fixture)
        unc = ctx["transfer_caveats"]["uncertainty"]
        assert set(unc) == {"proxy", "transfer", "anchor", "sampling"}
        assert abs(sum(unc.values()) - 1.0) < 1e-9

    def test_context_is_client_safe(self, fixture: dict) -> None:
        # build_report_context runs assert_client_safe internally; if a forbidden
        # phrase slipped into any composed string this would raise.
        context.build_report_context(fixture)
