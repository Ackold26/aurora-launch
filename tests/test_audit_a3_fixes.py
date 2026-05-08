"""Audit A3 fix verification tests.

Tests for B-A3-1/2/3 BLOCKER fixes + H-A3-1/2/4/5 HIGH fixes + M-A3-1/5/6.
"""

from __future__ import annotations

import asyncio
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import StringIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from aurora_launch.engines.customer_success import CustomerSuccessTracker
from aurora_launch.engines.launch_conformal import split_conformal_intervals
from aurora_launch.engines.launch_posterior_update import (
    detect_drift,
    should_trigger_auto_suggestion,
)
from aurora_launch.engines.methodology_cert import (
    build_certificate_data,
    signing_payload_bytes,
)
from aurora_launch.engines.similarity_calculator import _get_weight_profile_id
from aurora_launch.schemas.customer_success import ConsultingLogEntry
from aurora_launch.schemas.forecast import (
    AcademicReference,
    ForecastSummary,
    ProxyMetadataSummary,
    TransferSummary,
)
from aurora_launch.schemas.posterior_update import DriftDiagnostics


class TestBA31DriftRealCoverage:
    """B-A3-1 FIX: detect_drift uses real CI coverage when bounds provided."""

    def test_uses_ci_bounds_when_provided(self) -> None:
        # Forecast=100 points, actual matches each, CI bounds provide loose interval
        forecasts = [100.0] * 12
        actuals = [99.0, 102.0, 95.0, 108.0, 101.0, 100.0, 103.0, 97.0, 100.0, 99.0, 101.0, 102.0]
        ci_lo = [80.0] * 12
        ci_hi = [120.0] * 12  # Generous bounds

        drift = detect_drift(
            proxy_baseline_forecast=forecasts,
            recipient_actual=actuals,
            forecast_ci_lower=ci_lo,
            forecast_ci_upper=ci_hi,
        )
        # All actuals within [80, 120] CI → coverage = 1.0 → normal severity
        assert drift.coverage_observed == 1.0
        assert drift.severity == "normal"

    def test_some_actuals_outside_ci(self) -> None:
        forecasts = [100.0] * 12
        # Half outside, half inside
        actuals = [200.0, 200.0, 100.0, 100.0, 200.0, 200.0, 100.0, 100.0, 200.0, 200.0, 100.0, 100.0]
        ci_lo = [80.0] * 12
        ci_hi = [120.0] * 12

        drift = detect_drift(
            proxy_baseline_forecast=forecasts,
            recipient_actual=actuals,
            forecast_ci_lower=ci_lo,
            forecast_ci_upper=ci_hi,
        )
        # 6 of 12 within CI → coverage = 0.5 → severe
        assert abs(drift.coverage_observed - 0.5) < 0.01
        assert drift.severity == "severe"

    def test_falls_back_к_relative_diff_when_no_ci(self) -> None:
        """Backward compat: no CI bounds → relative diff approximation."""
        forecasts = [100.0] * 12
        actuals = [105.0] * 12  # within ±20%

        drift = detect_drift(
            proxy_baseline_forecast=forecasts,
            recipient_actual=actuals,
            # No CI bounds → fallback
        )
        assert drift.severity == "normal"


class TestBA32CertSignatureCollision:
    """B-A3-2 FIX: References use length-prefixed encoding."""

    def _basic_inputs(self, refs: list[AcademicReference]) -> dict:
        return dict(
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
            methodology_references=refs,
        )

    def test_pipe_in_citation_doesnt_collide(self) -> None:
        """Length-prefix encoding prevents '|' citation collision."""
        # Reference with '|' в citation — would collide pre-fix
        refs_a = [
            AcademicReference(
                citation="Authors|Title (Year)",  # contains '|'
                doi="10.1234/test1",
                relevance="testing",
            ),
        ]
        # Different reference where '|' shifted differently
        refs_b = [
            AcademicReference(
                citation="Authors",  # no '|'
                doi="10.1234/test1|Title (Year)",  # '|' moved into doi
                relevance="testing",
            ),
        ]

        cert_a = build_certificate_data(**self._basic_inputs(refs_a))
        cert_b = build_certificate_data(**self._basic_inputs(refs_b))

        payload_a = signing_payload_bytes(cert_a)
        payload_b = signing_payload_bytes(cert_b)

        # Length prefixes encode unambiguously — different inputs produce different payloads
        assert payload_a != payload_b

    def test_payload_includes_length_prefix(self) -> None:
        """Verify payload format includes length prefix for each reference."""
        refs = [
            AcademicReference(
                citation="Test Citation",
                doi="10.1234/example",
                relevance="testing",
            ),
        ]
        cert = build_certificate_data(**self._basic_inputs(refs))
        payload = signing_payload_bytes(cert)
        # Length-prefix format: "<n>:<value>"
        assert b"REFS:" in payload  # marker для refs section
        # Length prefix appears (e.g., "15:" for "10.1234/example")
        assert b"15:10.1234/example" in payload  # doi length-prefixed


class TestBA33CosmeticsWeightProfile:
    """B-A3-3 FIX: Mass cosmetics use FMCG_STAPLES weights."""

    def test_premium_skincare_uses_premium_profile(self) -> None:
        profile = _get_weight_profile_id("Cosmetics", "skincare_premium")
        assert profile == "PREMIUM_COSMETICS"

    def test_mass_cosmetics_uses_fmcg_staples(self) -> None:
        profile = _get_weight_profile_id("Cosmetics", "cosmetics_mass")
        assert profile == "FMCG_STAPLES"

    def test_mass_haircare_uses_fmcg_staples(self) -> None:
        # Subcategory containing "mass" routes к FMCG_STAPLES
        profile = _get_weight_profile_id("Cosmetics", "haircare_mass_market")
        assert profile == "FMCG_STAPLES"


class TestHA31CsvInjection:
    """H-A3-1 FIX: CSV injection protection."""

    def test_formula_prefix_escaped(self, tmp_path: Path) -> None:
        tracker = CustomerSuccessTracker(tmp_path / "log.db")
        cust = uuid4()
        machine = uuid4()
        # Notes с CSV formula injection
        entry = ConsultingLogEntry(
            customer_id=cust,
            machine_id=machine,
            timestamp_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            duration_minutes=60,
            event_type="proxy_review",
            notes="=cmd|/c calc!A1",  # injection attempt
            consulting_hours_charged=Decimal("1.0"),
        )
        tracker.log_event(entry)

        csv_text = tracker.export_csv(
            customer_id=cust,
            period_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        # Formula prefix should be escaped с apostrophe
        assert "'=cmd" in csv_text or "='" in csv_text or "'=" in csv_text


class TestHA32CsvUtf8Bom:
    """H-A3-2 FIX: UTF-8 BOM для Russian Excel."""

    def test_csv_starts_with_bom(self, tmp_path: Path) -> None:
        tracker = CustomerSuccessTracker(tmp_path / "log.db")
        cust = uuid4()
        machine = uuid4()
        tracker.log_event(ConsultingLogEntry(
            customer_id=cust,
            machine_id=machine,
            timestamp_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            duration_minutes=60,
            event_type="proxy_review",
            notes="Тестовая запись на русском",
            consulting_hours_charged=Decimal("1.0"),
        ))

        csv_text = tracker.export_csv(
            customer_id=cust,
            period_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        # UTF-8 BOM = U+FEFF prefix
        assert csv_text.startswith("﻿")


class TestHA35ConformalCoverageValidation:
    """H-A3-5 FIX: coverage_target validated."""

    def test_invalid_zero(self) -> None:
        with pytest.raises(ValueError, match="coverage_target"):
            split_conformal_intervals(
                point_forecasts=[100.0],
                calibration_residuals=[1.0, 2.0, 3.0],
                coverage_target=0.0,
            )

    def test_invalid_one(self) -> None:
        with pytest.raises(ValueError, match="coverage_target"):
            split_conformal_intervals(
                point_forecasts=[100.0],
                calibration_residuals=[1.0, 2.0, 3.0],
                coverage_target=1.0,
            )

    def test_invalid_negative(self) -> None:
        with pytest.raises(ValueError, match="coverage_target"):
            split_conformal_intervals(
                point_forecasts=[100.0],
                calibration_residuals=[1.0, 2.0, 3.0],
                coverage_target=-0.5,
            )

    def test_valid_typical(self) -> None:
        # Should NOT raise
        intervals = split_conformal_intervals(
            point_forecasts=[100.0],
            calibration_residuals=[1.0, 2.0, 3.0],
            coverage_target=0.95,
        )
        assert len(intervals) == 1


class TestMA35TimezoneNormalization:
    """M-A3-5 FIX: timezone-naive last_dismissal handled gracefully."""

    def test_naive_datetime_does_not_crash(self) -> None:
        drift = DriftDiagnostics(
            coverage_observed=0.85,
            n_weeks_evaluated=12,
            severity="mild",
            is_unknown_due_to_few_weeks=False,
        )
        # Naive datetime — would have crashed pre-fix
        naive_dismissal = datetime(2030, 1, 1)  # no tzinfo
        result = should_trigger_auto_suggestion(
            drift=drift,
            n_new_weeks=4,
            estimated_ci_tightening_pct=12.0,
            project_id=uuid4(),
            last_dismissal=naive_dismissal,
        )
        # Future-dated dismissal — should suppress trigger без TypeError
        assert result is None


class TestMA36IntegrityErrorNarrowing:
    """M-A3-6 FIX: only PRIMARY KEY duplicates treated as no-op."""

    def test_duplicate_event_id_returns_false(self, tmp_path: Path) -> None:
        tracker = CustomerSuccessTracker(tmp_path / "log.db")
        entry = ConsultingLogEntry(
            customer_id=uuid4(),
            machine_id=uuid4(),
            timestamp_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            duration_minutes=60,
            event_type="proxy_review",
            consulting_hours_charged=Decimal("1.0"),
        )
        # First insert succeeds
        assert tracker.log_event(entry) is True
        # Same event_id — idempotent no-op
        assert tracker.log_event(entry) is False


class TestCrossSprintIntegration:
    """End-to-end sprint chain integration test (H-A3-6 fix).

    Exercises B2 similarity → B3 adapt → B3 validate → B4 forecast → B4 cert
    chain. Catches interaction bugs that isolated unit tests miss.
    """

    def test_full_sprint_chain_end_to_end(self) -> None:
        from aurora_launch.engines.engine_selector import select_engine
        from aurora_launch.engines.launch_adapt import (
            apply_recipient_magnitudes_real,
            extract_proxy_priors_from_posterior,
        )
        from aurora_launch.engines.launch_forecast import build_forecast_report
        from aurora_launch.engines.methodology_cert import build_certificate_data
        from aurora_launch.engines.similarity_calculator import (
            compute_aggregate_score,
            compute_dimension_scores,
            determine_verdict,
            _get_weights,
        )
        from aurora_launch.schemas.proxy import ProxyEntry

        # Step 1 (B2): similarity scoring
        recipient = ProxyEntry(
            proxy_brand_name="Recipient", proxy_brand_code="REC-2026",
            category_l1="FMCG_beverage", category_l2="beverage_energy",
            category_l3="energy_caffeine",
            pricing_tier="PREMIUM", brand_size="CHALLENGER",
            distribution="NATIONAL", media_maturity="ALWAYS_ON",
            lifecycle="GROWING",
        )
        proxy = ProxyEntry(
            proxy_brand_name="Proxy", proxy_brand_code="PRX-2026",
            category_l1="FMCG_beverage", category_l2="beverage_energy",
            category_l3="energy_caffeine",
            pricing_tier="PREMIUM", brand_size="LEADER",
            distribution="NATIONAL", media_maturity="ALWAYS_ON",
            lifecycle="MATURE",
        )

        weights = _get_weights(recipient.category_l1, recipient.category_l2)
        dim_scores = compute_dimension_scores(recipient, proxy)
        score = compute_aggregate_score(dim_scores, weights)
        verdict = determine_verdict(score)

        # Step 2 (B3): engine selection
        engine_decision = select_engine(
            n_proxies=1,
            individual_scores=[score],
        )
        assert engine_decision.selected_engine == "single"

        # Step 3 (B3): extract priors + apply magnitudes
        posterior_summary = {
            "adstock_decay": {"TV": {"mean": 0.4, "std": 0.05, "ess": 800},
                              "Digital": {"mean": 0.3, "std": 0.04, "ess": 800}},
            "hill_gamma": {"TV": {"mean": 2.0, "std": 0.3, "ess": 750},
                           "Digital": {"mean": 1.8, "std": 0.25, "ess": 760}},
            "hill_k": {"TV": {"mean": 0.8, "std": 0.15, "ess": 760},
                       "Digital": {"mean": 0.7, "std": 0.12, "ess": 760}},
            "seasonality_52w": [0.0] * 52,
            "trend_slope": {"mean": 0.001, "std": 0.0005, "ess": 1200},
        }
        priors = extract_proxy_priors_from_posterior(
            posterior_summary, ["TV", "Digital"], "stub_hash"
        )
        recipient_priors = apply_recipient_magnitudes_real(
            priors=priors,
            similarity_score=score,
            similarity_label=verdict if verdict in ("High", "Medium", "Low") else "Medium",
            cross_category_distance=0,
            pooling_weight_proxy=1.0,
        )
        assert "adstock_decay__TV" in recipient_priors

        # Step 4 (B4): forecast + cert composition
        from uuid import uuid4
        cert_id = uuid4()
        report = build_forecast_report(
            point_forecasts_per_horizon={
                12: [100_000.0] * 12,
                26: [100_000.0] * 26,
                52: [100_000.0] * 52,
            },
            calibration_residuals=[2000.0, -1500.0, 3000.0] * 20,
            methodology_cert_id=cert_id,
            framing="balanced",
        )
        assert len(report.sections) == 8
        assert len(report.forecast_horizons) == 3

        cert = build_certificate_data(
            aurora_launch_version="0.1.x-b05",
            bundle_hash_sha256="a" * 64,
            bundle_hash_jcs_canonical="b" * 64,
            proxy_metadata=ProxyMetadataSummary(
                proxy_code=proxy.proxy_brand_code,
                similarity_score=score,
                verdict=verdict if verdict in ("High", "Medium", "Low", "Insufficient") else "Medium",
                inflation_factor_applied=1.5,
            ),
            transfer_summary=TransferSummary(
                transferred_params=["adstock_decay", "hill_gamma", "hill_k"],
                not_transferred=["beta_coefficients"],
                cross_category_distance=0,
            ),
            forecast_summary=ForecastSummary(
                total_forecast_12w=1.2e6,
                total_forecast_26w=2.6e6,
                total_forecast_52w=5.2e6,
                ci_pct_12w=15, ci_pct_26w=22, ci_pct_52w=32,
            ),
        )
        # End-to-end chain produced complete cert
        assert cert.aurora_launch_version == "0.1.x-b05"
        assert cert.proxy_metadata_summary.proxy_code == proxy.proxy_brand_code
        assert "adstock_decay" in cert.transfer_summary.transferred_params
