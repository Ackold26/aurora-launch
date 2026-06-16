"""Sprint B4 deliverable #4 — the Methodology Certificate PDF (spec §3, ADR-006).

Build the certificate from the real forecast context and assert: the cert data is
composed correctly from the context, the local Ed25519 signature round-trips (and a
tamper is rejected), and the ReportLab PDF is a valid artifact with the bundle hash
embedded in its metadata.

CI-safe: the custody signing key (~/.secrets) and the bundled brand TTFs may be
absent on a runner, so the signing round-trip uses an EPHEMERAL key (the on-disk
custody crypto is covered by tests/test_cert_local_signing.py) and the PDF assertions
hold regardless of key/font availability.
"""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aurora_launch.engines.methodology_cert import (
    sign_certificate_local,
    verify_certificate_local,
)
from aurora_launch.reporting.context import build_report_context
from aurora_launch.reporting.render_cert import _build_cert_data, build_methodology_cert_pdf
from aurora_launch.sample_bundles.report_fixture import build_sample_forecast_fixture


@pytest.fixture(scope="module")
def ctx() -> dict:
    return build_report_context(build_sample_forecast_fixture())


class TestCertComposition:
    def test_forecast_and_proxy_mapped_from_context(self, ctx: dict) -> None:
        cert, _ = _build_cert_data(ctx, aurora_version="v0.2.5", bundle_hash="a" * 64, jcs_hash=None)
        km = {r["period_weeks"]: r for r in ctx["executive_summary"]["key_metrics"]}
        assert cert.forecast_summary.total_forecast_12w == km[12]["total_rub"]
        assert cert.forecast_summary.total_forecast_52w == km[52]["total_rub"]
        assert cert.proxy_metadata_summary.proxy_code == ctx["proxy_quality"]["proxy_brand"]
        assert cert.proxy_metadata_summary.inflation_factor_applied >= 1.0
        # composite signing payload encodes the bundle hash + version (domain-checked).
        assert cert.bundle_hash_sha256 == "a" * 64


class TestSigningRoundTrip:
    """Hermetic: sign with an ephemeral key (independent of the box's custody key)."""

    def test_signature_verifies_then_tamper_rejected(self, ctx: dict) -> None:
        cert, _ = _build_cert_data(ctx, aurora_version="v0.2.5", bundle_hash="b" * 64, jcs_hash=None)
        key = Ed25519PrivateKey.generate()
        signed, ok = sign_certificate_local(cert, private_key=key)
        assert ok and signed.signature_local_ed25519 is not None
        pub = key.public_key()
        assert verify_certificate_local(signed, public_key=pub) is True
        # Tampering with signed content invalidates the signature.
        tampered = signed.model_copy(update={"aurora_launch_version": "v9.9.9-evil"})
        assert verify_certificate_local(tampered, public_key=pub) is False


class TestPdfArtifact:
    @pytest.fixture(scope="class")
    def pdf(self, ctx: dict, tmp_path_factory) -> dict:
        out = tmp_path_factory.mktemp("cert") / "cert.pdf"
        manifest = build_methodology_cert_pdf(ctx, str(out), aurora_version="v0.2.5",
                                              bundle_hash="c" * 64)
        return {"path": str(out), "manifest": manifest, "raw": out.read_bytes()}

    def test_valid_pdf(self, pdf: dict) -> None:
        assert pdf["raw"][:5] == b"%PDF-"
        assert pdf["manifest"]["renderer"] == "reportlab"

    def test_hash_embedded_in_metadata(self, pdf: dict) -> None:
        # spec §3.4: hash in PDF metadata, not only visible text.
        assert b"c" * 64 in pdf["raw"]
        assert pdf["manifest"]["bundle_hash"] == "c" * 64

    def test_manifest_reports_signing_state(self, pdf: dict) -> None:
        # local_signed is box-dependent (custody key presence); must be an honest bool,
        # and when signed a key id is surfaced.
        signed = pdf["manifest"]["local_signed"]
        assert isinstance(signed, bool)
        if signed:
            assert pdf["manifest"]["signature_pubkey_id"]
