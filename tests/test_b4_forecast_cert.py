"""B4 Forecast Report + Methodology Cert tests."""

from __future__ import annotations

import asyncio

import pytest
from hypothesis import given, settings, strategies as st

from aurora_launch.engines.launch_conformal import (
    MIN_CALIBRATION_FOR_TIGHT_INTERVALS,
    compute_conformal_intervals,
    coverage_warning_threshold,
    split_conformal_intervals,
)
from aurora_launch.engines.launch_forecast import (
    FRAMING_VISIBILITY,
    build_forecast_report,
    build_forecast_summary,
    compose_section_visibility,
    generate_forecast_report,
)
from aurora_launch.engines.methodology_cert import (
    build_certificate,
    build_certificate_data,
    cert_payload_sha256,
    compute_composite_signing_payload,
    signing_payload_bytes,
)
from aurora_launch.schemas.forecast import (
    AcademicReference,
    ForecastSummary,
    ProxyMetadataSummary,
    TransferSummary,
)
from uuid import UUID, uuid4


class TestSplitConformal:
    def test_returns_intervals_per_forecast(self) -> None:
        forecasts = [100.0, 105.0, 110.0]
        residuals = [2.0, -3.0, 5.0, -4.0, 2.5] * 12  # 60 residuals
        intervals = split_conformal_intervals(forecasts, residuals)
        assert len(intervals) == 3

    def test_bounds_ordering(self) -> None:
        forecasts = [100.0]
        residuals = [5.0] * 60
        intervals = split_conformal_intervals(forecasts, residuals)
        i = intervals[0]
        assert i.lower_bound <= i.point_forecast <= i.upper_bound

    def test_empty_calibration_falls_back_к_default(self) -> None:
        intervals = split_conformal_intervals([100.0], [])
        # ±20% default
        assert intervals[0].lower_bound == 80.0
        assert intervals[0].upper_bound == 120.0

    def test_inflated_for_small_n_cal(self) -> None:
        """Audit H4 — n_cal < 50 inflates quantile."""
        forecasts = [100.0]
        # Small calibration set
        small_residuals = [2.0, -3.0, 5.0, -4.0, 2.5]  # n=5
        # Large calibration set
        large_residuals = [2.0, -3.0, 5.0, -4.0, 2.5] * 12  # n=60

        small_intervals = split_conformal_intervals(forecasts, small_residuals)
        large_intervals = split_conformal_intervals(forecasts, large_residuals)

        # Small should be wider due to Vovk 2005 inflation
        small_width = small_intervals[0].upper_bound - small_intervals[0].lower_bound
        large_width = large_intervals[0].upper_bound - large_intervals[0].lower_bound
        assert small_width > large_width

    def test_coverage_warning_below_threshold(self) -> None:
        warning = coverage_warning_threshold(n_calibration=20)
        assert warning is not None
        assert "Vovk" in warning

    def test_no_warning_above_threshold(self) -> None:
        warning = coverage_warning_threshold(n_calibration=60)
        assert warning is None


class TestMultiHorizonConformal:
    def test_per_horizon_intervals(self) -> None:
        forecasts = {
            12: [100.0] * 12,
            26: [100.0] * 26,
            52: [100.0] * 52,
        }
        residuals = [2.0, -3.0, 5.0, -4.0, 2.5] * 12
        results = compute_conformal_intervals(forecasts, residuals)
        assert len(results[12]) == 12
        assert len(results[26]) == 26
        assert len(results[52]) == 52


class TestFramingPresets:
    def test_three_presets_registered(self) -> None:
        assert "cfo" in FRAMING_VISIBILITY
        assert "cmo" in FRAMING_VISIBILITY
        assert "balanced" in FRAMING_VISIBILITY

    def test_cfo_collapses_proxy_quality(self) -> None:
        """CFO mode collapses proxy quality details (less interesting к CFO)."""
        cfo = FRAMING_VISIBILITY["cfo"]
        assert cfo["proxy_quality"] == "collapsed"

    def test_cmo_expands_proxy_quality(self) -> None:
        cmo = FRAMING_VISIBILITY["cmo"]
        assert cmo["proxy_quality"] == "expanded"

    def test_compose_visibility_returns_per_section(self) -> None:
        sections = ["cover", "executive_summary", "forecast_12w"]
        vis = compose_section_visibility("cfo", sections)
        assert vis["cover"] == "expanded"
        assert vis["executive_summary"] == "expanded"


class TestForecastSummary:
    def test_aggregates_per_horizon(self) -> None:
        residuals = [2.0, -3.0, 5.0, -4.0, 2.5] * 12
        intervals = compute_conformal_intervals(
            forecasts_per_horizon={
                12: [100.0] * 12,
                26: [100.0] * 26,
                52: [100.0] * 52,
            },
            calibration_residuals=residuals,
        )
        summary = build_forecast_summary(intervals)
        # 12 weeks × 100 = 1200
        assert abs(summary.total_forecast_12w - 1200.0) < 0.01
        assert abs(summary.total_forecast_52w - 5200.0) < 0.01

    def test_empty_horizon_zero_summary(self) -> None:
        summary = build_forecast_summary({})
        assert summary.total_forecast_12w == 0.0
        assert summary.ci_pct_12w == 0.0


class TestBuildForecastReport:
    def test_builds_8_sections(self) -> None:
        cert_id = uuid4()
        report = build_forecast_report(
            point_forecasts_per_horizon={
                12: [100.0] * 12,
                26: [100.0] * 26,
                52: [100.0] * 52,
            },
            calibration_residuals=[2.0, -3.0, 5.0] * 20,
            methodology_cert_id=cert_id,
            framing="balanced",
        )
        assert len(report.sections) == 8

    def test_three_horizons_present(self) -> None:
        cert_id = uuid4()
        report = build_forecast_report(
            point_forecasts_per_horizon={
                12: [100.0] * 12,
                26: [100.0] * 26,
                52: [100.0] * 52,
            },
            calibration_residuals=[2.0] * 60,
            methodology_cert_id=cert_id,
        )
        horizons = sorted(h.horizon_weeks for h in report.forecast_horizons)
        assert horizons == [12, 26, 52]


class TestForecastReportHandler:
    def test_handler_returns_structured_result(self) -> None:
        result = asyncio.run(generate_forecast_report(ctx=None))
        assert result["step_type"] == "forecast_report"
        assert result["stub"] is False
        assert result["framing"] == "balanced"
        assert result["n_sections"] == 8
        assert result["n_horizons"] == 3


class TestCompositeSigningPayload:
    def test_three_inputs_concatenated(self) -> None:
        payload = compute_composite_signing_payload(
            bundle_hash_sha256="a" * 64,
            bundle_hash_jcs_canonical="b" * 64,
            aurora_launch_version="0.1.x",
        )
        # Format: hash | jcs | version
        assert "|" in payload
        parts = payload.split("|")
        assert len(parts) == 3
        assert parts[0] == "a" * 64
        assert parts[1] == "b" * 64
        assert parts[2] == "0.1.x"

    def test_rejects_pipe_in_input(self) -> None:
        """Defense-in-depth — separator collision protection."""
        with pytest.raises(ValueError, match="separator"):
            compute_composite_signing_payload(
                bundle_hash_sha256="a|b",  # contains '|'
                bundle_hash_jcs_canonical="c" * 64,
                aurora_launch_version="0.1.x",
            )


class TestBuildCertificateData:
    def _basic_inputs(self) -> dict:
        return dict(
            aurora_launch_version="0.1.x-b05",
            bundle_hash_sha256="a" * 64,
            bundle_hash_jcs_canonical="b" * 64,
            proxy_metadata=ProxyMetadataSummary(
                proxy_code="KAG-2024",
                similarity_score=0.92,
                verdict="High",
                inflation_factor_applied=1.2,
            ),
            transfer_summary=TransferSummary(
                transferred_params=["adstock_decay", "hill_gamma"],
                not_transferred=["baseline"],
                cross_category_distance=0,
            ),
            forecast_summary=ForecastSummary(
                total_forecast_12w=1_000_000.0,
                total_forecast_26w=2_000_000.0,
                total_forecast_52w=4_000_000.0,
                ci_pct_12w=15.0,
                ci_pct_26w=22.0,
                ci_pct_52w=32.0,
            ),
        )

    def test_returns_typed_cert_data(self) -> None:
        cert = build_certificate_data(**self._basic_inputs())
        assert cert.aurora_launch_version == "0.1.x-b05"
        assert cert.proxy_metadata_summary.proxy_code == "KAG-2024"

    def test_default_methodology_references_present(self) -> None:
        cert = build_certificate_data(**self._basic_inputs())
        # Tibshirani / Konstantinopoulos / Hanssens / Vovk
        assert len(cert.methodology_references) >= 4
        dois = [r.doi for r in cert.methodology_references]
        assert any("Tibshirani" in r.citation for r in cert.methodology_references)

    def test_repro_recipe_includes_cli_command(self) -> None:
        cert = build_certificate_data(**self._basic_inputs())
        assert "aurora-launch-reproduce" in cert.reproducibility_recipe.cli_command
        assert "a" * 64 in cert.reproducibility_recipe.cli_command


class TestSigningScope:
    def test_signing_payload_excludes_timestamps(self) -> None:
        """Audit B4 — timestamp NOT in signed payload."""
        from datetime import datetime, timezone

        cert_a = build_certificate_data(
            aurora_launch_version="0.1.x",
            bundle_hash_sha256="a" * 64,
            bundle_hash_jcs_canonical="b" * 64,
            proxy_metadata=ProxyMetadataSummary(
                proxy_code="K-1", similarity_score=0.9, verdict="High",
                inflation_factor_applied=1.2,
            ),
            transfer_summary=TransferSummary(
                transferred_params=["a"], not_transferred=["b"],
                cross_category_distance=0,
            ),
            forecast_summary=ForecastSummary(
                total_forecast_12w=1.0, total_forecast_26w=2.0, total_forecast_52w=3.0,
                ci_pct_12w=10, ci_pct_26w=15, ci_pct_52w=20,
            ),
        )
        # Mutate generated_at — should NOT change signing payload
        # (cert_a is frozen, but model_copy works)
        payload_a = signing_payload_bytes(cert_a)

        cert_b = cert_a.model_copy(update={"generated_at": datetime.now(timezone.utc)})
        payload_b = signing_payload_bytes(cert_b)

        # Payloads identical despite different timestamps
        assert payload_a == payload_b

    def test_payload_hash_deterministic(self) -> None:
        kwargs = dict(
            aurora_launch_version="0.1.x",
            bundle_hash_sha256="a" * 64,
            bundle_hash_jcs_canonical="b" * 64,
            proxy_metadata=ProxyMetadataSummary(
                proxy_code="K-1", similarity_score=0.9, verdict="High",
                inflation_factor_applied=1.2,
            ),
            transfer_summary=TransferSummary(
                transferred_params=["a"], not_transferred=["b"],
                cross_category_distance=0,
            ),
            forecast_summary=ForecastSummary(
                total_forecast_12w=1.0, total_forecast_26w=2.0, total_forecast_52w=3.0,
                ci_pct_12w=10, ci_pct_26w=15, ci_pct_52w=20,
            ),
        )
        cert_1 = build_certificate_data(**kwargs)
        # Same inputs except cert_id (UUID auto-gen) — but cert_id NOT in signing scope
        # So payload hashes differ only via cert_id... actually cert_id IS hashed
        # via composite_signing_payload? No — cert_id not part of payload.
        # Let me verify via direct сравнение
        cert_2 = build_certificate_data(**kwargs)
        h1 = cert_payload_sha256(cert_1)
        h2 = cert_payload_sha256(cert_2)
        # Should match — same content (cert_id not в signing scope)
        assert h1 == h2


class TestCertHandler:
    def test_handler_returns_full_cert_metadata(self) -> None:
        result = asyncio.run(build_certificate(ctx=None))
        assert result["step_type"] == "cert_sign"
        assert result["stub"] is False
        assert "cert_id" in result
        assert "cert_payload_sha256" in result
        assert result["tier_independent"] is True
        assert result["pdf_renderer_used"] == "tauri_webview"
        # 3 verifier formats (HIGH H3)
        urls = result["verifier_urls"]
        assert "web_verifier_url" in urls
        assert "standalone_html_download_url" in urls
        assert "cli_tool_download_url" in urls

    def test_handler_dual_signature_pending_in_stub(self) -> None:
        """Until C7 deployment — Aurora signature pending."""
        result = asyncio.run(build_certificate(ctx=None))
        # Local + Aurora both pending until signing service deployed
        assert result["dual_signature_status"]["aurora_pending"] is True
