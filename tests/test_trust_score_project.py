"""Tests для project-based trust score wrapper (Sprint 2 D1')."""

from __future__ import annotations

import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aurora_launch.engines.methodology_cert import (
    build_certificate_data,
    sign_certificate_local,
)
from aurora_launch.engines.trust_score_project import (
    ProjectTrustScoreResult,
    compute_trust_score_for_project,
    extract_data_sufficiency,
    extract_methodology_certified,
    extract_model_convergence,
    extract_similarity_score,
    extract_uncertainty_inverse,
)
from aurora_launch.schemas.forecast import (
    ForecastSummary,
    ProxyMetadataSummary,
    TransferSummary,
)

# A throwaway signing key for cert fixtures; its pubkey is injected via the
# AURORA_LAUNCH_CERT_PUBLIC_KEY_HEX env (autouse fixture below) so the trust
# scorer's crypto verification uses it instead of the embedded production key.
_TEST_CERT_KEY = Ed25519PrivateKey.generate()
_TEST_CERT_PUBKEY_HEX = _TEST_CERT_KEY.public_key().public_bytes_raw().hex()


@pytest.fixture(autouse=True)
def _use_test_cert_pubkey(monkeypatch):
    monkeypatch.setenv("AURORA_LAUNCH_CERT_PUBLIC_KEY_HEX", _TEST_CERT_PUBKEY_HEX)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _empty_files() -> dict[str, bytes]:
    return {}


def _base_cert():
    return build_certificate_data(
        aurora_launch_version="1.0.0",
        bundle_hash_sha256="a" * 64,
        bundle_hash_jcs_canonical="b" * 64,
        proxy_metadata=ProxyMetadataSummary(
            proxy_code="TEST",
            similarity_score=0.7,
            verdict="Medium",
            inflation_factor_applied=1.5,
        ),
        transfer_summary=TransferSummary(
            transferred_params=["adstock_decay"],
            not_transferred=["baseline"],
            cross_category_distance=0,
        ),
        forecast_summary=ForecastSummary(
            total_forecast_12w=1.0,
            total_forecast_26w=2.0,
            total_forecast_52w=3.0,
            ci_pct_12w=15.0,
            ci_pct_26w=22.0,
            ci_pct_52w=32.0,
        ),
    )


def _diagnostics_blob(r_hat_max: float) -> bytes:
    return json.dumps({"r_hat_max": r_hat_max}).encode("utf-8")


def _forecast_blob(points: list[dict[str, float]]) -> bytes:
    return json.dumps({"weekly_points": points}).encode("utf-8")


def _cert_blob(
    *,
    local: bool = True,
    aurora: bool = True,
    pending: bool = False,
    sign_key: Ed25519PrivateKey | None = None,
) -> bytes:
    """A REAL methodology_cert.json: when local=True the cert carries a genuine
    Ed25519 signature (default the test key; pass sign_key to forge with another
    key). aurora is presence-only — the cloud half this offline path cannot verify."""
    cert = _base_cert()
    if local:
        cert, _ = sign_certificate_local(cert, private_key=sign_key or _TEST_CERT_KEY)
    update: dict = {"signature_aurora_pending": pending}
    if aurora:
        update["signature_aurora_ed25519"] = b"\xbb" * 64
    cert = cert.model_copy(update=update)
    return cert.model_dump_json().encode("utf-8")


# ─── extract_similarity_score ─────────────────────────────────────────────────


class TestExtractSimilarityScore:
    def test_prefers_proxy_similarity_score_at_0_100_scale(self) -> None:
        value, note = extract_similarity_score({"proxy_similarity_score": 75.0})
        assert value == 75.0
        assert "0..100 шкала" in note

    def test_falls_back_to_similarity_score_ratio(self) -> None:
        value, note = extract_similarity_score({"similarity_score": 0.83})
        assert value == pytest.approx(83.0)
        assert "ratio × 100" in note

    def test_default_when_neither_field_present(self) -> None:
        value, note = extract_similarity_score({})
        assert value == 0.0
        assert "по умолчанию" in note

    def test_default_when_proxy_similarity_out_of_range(self) -> None:
        value, _ = extract_similarity_score({"proxy_similarity_score": 250.0})
        # Falls through, no ratio either → default
        assert value == 0.0

    def test_default_when_invalid_type(self) -> None:
        value, _ = extract_similarity_score({"proxy_similarity_score": "high"})
        assert value == 0.0


# ─── extract_methodology_certified ────────────────────────────────────────────


class TestExtractMethodologyCertified:
    def test_full_credit_when_both_signatures_present(self) -> None:
        files = {"methodology_cert.json": _cert_blob(local=True, aurora=True, pending=False)}
        value, note = extract_methodology_certified(files)
        assert value == 1.0
        assert "ed25519" in note

    def test_partial_credit_when_only_local_signed(self) -> None:
        files = {"methodology_cert.json": _cert_blob(local=True, aurora=False, pending=False)}
        value, _ = extract_methodology_certified(files)
        assert value == 0.5

    def test_partial_credit_when_aurora_pending(self) -> None:
        files = {"methodology_cert.json": _cert_blob(local=True, aurora=True, pending=True)}
        value, note = extract_methodology_certified(files)
        assert value == 0.5
        assert "ожидает aurora" in note

    def test_partial_credit_when_only_pdf_present(self) -> None:
        files = {"methodology_cert.pdf": b"%PDF-1.7\n..."}
        value, note = extract_methodology_certified(files)
        assert value == 0.5
        assert "PDF" in note

    def test_zero_when_cert_corrupt_json(self) -> None:
        files = {"methodology_cert.json": b"\xff\xfeNOT_JSON"}
        value, note = extract_methodology_certified(files)
        assert value == 0.0
        assert "повреждён" in note

    def test_zero_when_no_cert_at_all(self) -> None:
        value, note = extract_methodology_certified({})
        assert value == 0.0
        assert "не сгенерирован" in note

    def test_zero_when_local_signature_forged(self) -> None:
        # A present-but-INVALID local signature (signed by a non-vendor key) must
        # score 0.0 — presence is not proof. Closes the forgery gap that the old
        # presence check left open (any non-null signature earned 0.5).
        forger = Ed25519PrivateKey.generate()
        files = {
            "methodology_cert.json": _cert_blob(local=True, aurora=False, sign_key=forger)
        }
        value, note = extract_methodology_certified(files)
        assert value == 0.0
        assert "недействительна" in note

    def test_partial_credit_when_local_verified_no_aurora(self) -> None:
        # Genuine local signature, no aurora half → honest pilot half-credit.
        files = {"methodology_cert.json": _cert_blob(local=True, aurora=False)}
        value, note = extract_methodology_certified(files)
        assert value == 0.5
        assert "pilot release" in note


# ─── extract_model_convergence ────────────────────────────────────────────────


class TestExtractModelConvergence:
    def test_full_credit_when_r_hat_below_full_threshold(self) -> None:
        files = {"models/diagnostics.json": _diagnostics_blob(1.02)}
        value, note = extract_model_convergence(files)
        assert value == 1.0
        assert "1.020" in note or "1.02" in note

    def test_partial_credit_in_marginal_band(self) -> None:
        files = {"models/diagnostics.json": _diagnostics_blob(1.08)}
        value, note = extract_model_convergence(files)
        assert value == 0.5
        assert "частичная" in note

    def test_zero_credit_above_partial_threshold(self) -> None:
        files = {"models/diagnostics.json": _diagnostics_blob(1.50)}
        value, note = extract_model_convergence(files)
        assert value == 0.0
        assert "не сошлась" in note

    def test_alternative_diagnostics_filename(self) -> None:
        files = {"models/proxy_posterior_diagnostics.json": _diagnostics_blob(1.04)}
        value, _ = extract_model_convergence(files)
        assert value == 1.0

    def test_default_when_no_diagnostics_file(self) -> None:
        value, note = extract_model_convergence({})
        # Default-toward-trust matches frontend hardcode behaviour
        assert value == 1.0
        assert "детерминированный proxy-transfer" in note

    def test_alternative_rhat_key_names(self) -> None:
        # Some saved diagnostics use `r_hat` or `rhat_max` instead of `r_hat_max`
        files = {"models/diagnostics.json": json.dumps({"rhat_max": 1.01}).encode("utf-8")}
        value, _ = extract_model_convergence(files)
        assert value == 1.0


# ─── extract_data_sufficiency ─────────────────────────────────────────────────


class TestExtractDataSufficiency:
    def test_full_when_periods_meet_monthly_minimum(self) -> None:
        value, note = extract_data_sufficiency({"n_periods": 12, "granularity": "monthly"})
        assert value == 1.0
        assert "100% достаточности" in note

    def test_full_when_periods_exceed_minimum(self) -> None:
        value, _ = extract_data_sufficiency({"n_periods": 24, "granularity": "monthly"})
        assert value == 1.0

    def test_partial_when_below_monthly_minimum(self) -> None:
        value, _ = extract_data_sufficiency({"n_periods": 6, "granularity": "monthly"})
        assert value == pytest.approx(0.5)

    def test_weekly_uses_higher_minimum(self) -> None:
        value, _ = extract_data_sufficiency({"n_periods": 13, "granularity": "weekly"})
        assert value == pytest.approx(0.5)

    def test_granularity_hint_overrides_metadata(self) -> None:
        value, _ = extract_data_sufficiency(
            {"n_periods": 13, "granularity": "monthly"},
            granularity_hint="weekly",
        )
        assert value == pytest.approx(0.5)

    def test_zero_when_n_periods_is_zero(self) -> None:
        value, note = extract_data_sufficiency({"n_periods": 0})
        assert value == 0.0
        assert "данных нет" in note

    def test_default_when_n_periods_missing(self) -> None:
        value, note = extract_data_sufficiency({})
        assert value == 1.0
        assert "не сохранён" in note

    def test_default_when_invalid_n_periods_type(self) -> None:
        value, note = extract_data_sufficiency({"n_periods": "twelve"})
        assert value == 1.0
        assert "невалидный тип" in note


# ─── extract_uncertainty_inverse ──────────────────────────────────────────────


class TestExtractUncertaintyInverse:
    def test_tight_ci_gives_high_score(self) -> None:
        points = [
            {"point_forecast": 100.0, "ci_lower": 95.0, "ci_upper": 105.0},
            {"point_forecast": 200.0, "ci_lower": 190.0, "ci_upper": 210.0},
        ]
        files = {"forecast.json": _forecast_blob(points)}
        value, _ = extract_uncertainty_inverse(files)
        # Mean width = 0.1 → inverse = 0.9
        assert value == pytest.approx(0.9, abs=0.01)

    def test_wide_ci_gives_low_score(self) -> None:
        points = [
            {"point_forecast": 100.0, "ci_lower": 20.0, "ci_upper": 180.0},
        ]
        files = {"forecast.json": _forecast_blob(points)}
        value, _ = extract_uncertainty_inverse(files)
        # Width = 1.6 → clamped к 0
        assert value == 0.0

    def test_alternative_point_key_name(self) -> None:
        # Some emitters use `point` instead of `point_forecast`
        points = [{"point": 100.0, "ci_lower": 95.0, "ci_upper": 105.0}]
        files = {"forecast.json": _forecast_blob(points)}
        value, _ = extract_uncertainty_inverse(files)
        assert value == pytest.approx(0.9, abs=0.01)

    def test_default_when_forecast_missing(self) -> None:
        value, note = extract_uncertainty_inverse({})
        assert value == 0.5
        assert "отсутствует" in note

    def test_default_when_forecast_corrupt(self) -> None:
        files = {"forecast.json": b"\xff\xfeNOT_JSON"}
        value, _ = extract_uncertainty_inverse(files)
        assert value == 0.5

    def test_default_when_no_valid_points(self) -> None:
        files = {"forecast.json": _forecast_blob([])}
        value, note = extract_uncertainty_inverse(files)
        assert value == 0.5
        assert "не содержит валидных" in note


# ─── compute_trust_score_for_project — wrapper integration ────────────────────


class TestComputeTrustScoreForProject:
    def test_combines_extractors_into_canonical_result(self) -> None:
        metadata = {"proxy_similarity_score": 80.0, "n_periods": 12, "granularity": "monthly"}
        files = {
            "methodology_cert.json": _cert_blob(local=True, aurora=True, pending=False),
            "models/diagnostics.json": _diagnostics_blob(1.02),
            "forecast.json": _forecast_blob(
                [{"point_forecast": 100.0, "ci_lower": 95.0, "ci_upper": 105.0}]
            ),
        }
        result = compute_trust_score_for_project(metadata, files)
        assert isinstance(result, ProjectTrustScoreResult)
        # All five dimensions strong → score ≥ 90
        assert result.score >= 90
        assert result.tier in ("Очень высокий", "Высокий")
        assert len(result.diagnostics) == 5
        assert all(src == "project_state" for src in result.sources.values())

    def test_overrides_take_precedence_over_extraction(self) -> None:
        metadata = {"proxy_similarity_score": 80.0}
        files = _empty_files()
        result = compute_trust_score_for_project(
            metadata,
            files,
            overrides={"proxy_similarity_score": 20.0},
        )
        assert result.sources["proxy_similarity_score"] == "override"

    def test_override_invalid_type_raises(self) -> None:
        with pytest.raises(ValueError, match="not float-coercible"):
            compute_trust_score_for_project(
                {},
                {},
                overrides={"proxy_similarity_score": "high"},
            )

    def test_empty_project_uses_defaults(self) -> None:
        result = compute_trust_score_for_project({}, {})
        # similarity=0, cert=0, conv=1.0 default, data=1.0 default, unc=0.5 default
        assert result.sources["proxy_similarity_score"] == "default"
        assert result.sources["methodology_certified"] == "default"
        assert result.sources["model_convergence_passed"] == "default"
        assert result.sources["data_sufficiency"] == "default"
        assert result.sources["uncertainty_pct_inverse"] == "default"
        # Result still computable — score reflects defaults
        assert 0 <= result.score <= 100

    def test_source_notes_populated_for_every_dimension(self) -> None:
        metadata = {"proxy_similarity_score": 80.0, "n_periods": 12}
        files = _empty_files()
        result = compute_trust_score_for_project(metadata, files)
        assert set(result.source_notes.keys()) == {
            "proxy_similarity_score",
            "methodology_certified",
            "model_convergence_passed",
            "data_sufficiency",
            "uncertainty_pct_inverse",
        }
        for note in result.source_notes.values():
            assert isinstance(note, str)
            assert len(note) > 0

    def test_mixed_provenance_tagged_correctly(self) -> None:
        # similarity from project_state, others mostly default, conv overridden
        metadata = {"proxy_similarity_score": 75.0}
        files = _empty_files()
        result = compute_trust_score_for_project(
            metadata,
            files,
            overrides={"model_convergence_passed": 0.5},
        )
        assert result.sources["proxy_similarity_score"] == "project_state"
        assert result.sources["model_convergence_passed"] == "override"
        assert result.sources["methodology_certified"] == "default"

    def test_result_is_frozen_dataclass(self) -> None:
        from dataclasses import FrozenInstanceError

        result = compute_trust_score_for_project({}, {})
        with pytest.raises(FrozenInstanceError):
            result.score = 999  # type: ignore[misc]

    def test_diagnostic_count_matches_existing_compute_trust_score(self) -> None:
        result = compute_trust_score_for_project({}, {})
        assert len(result.diagnostics) == 5

    def test_partial_overrides_other_dims_still_extracted(self) -> None:
        metadata = {"proxy_similarity_score": 60.0, "n_periods": 12}
        result = compute_trust_score_for_project(
            metadata,
            {},
            overrides={"methodology_certified": 1.0},
        )
        assert result.sources["methodology_certified"] == "override"
        assert result.sources["proxy_similarity_score"] == "project_state"
        assert result.sources["data_sufficiency"] == "project_state"
