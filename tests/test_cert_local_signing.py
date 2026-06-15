"""Local Ed25519 certificate signer (Phase D variant B) — attack-scenario tests.

Per INV-02 (cryptographic claims get attack-scenario tests before/with impl):
prove the local cert signer round-trips, rejects tampering, and — critically —
emits an HONESTLY-UNSIGNED certificate when no vendor key is present (never a
fabricated signature). The production custody key lives behind a key ceremony;
these run on an EPHEMERAL key so correctness is provable without it.
"""
from __future__ import annotations

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aurora_launch.engines.methodology_cert import (
    build_certificate_data,
    cert_pubkey_id,
    cert_signing_input,
    load_cert_signing_key,
    sign_certificate_local,
    verify_certificate_local,
)
from aurora_launch.schemas.forecast import (
    ForecastSummary,
    ProxyMetadataSummary,
    TransferSummary,
)


def _cert(bundle_hash: str = "a" * 64):
    """A minimal, schema-valid certificate to sign."""
    return build_certificate_data(
        aurora_launch_version="1.0.0",
        bundle_hash_sha256=bundle_hash,
        bundle_hash_jcs_canonical="b" * 64,
        proxy_metadata=ProxyMetadataSummary(
            proxy_code="TEST-2026",
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


def test_local_signature_round_trips_with_ephemeral_key():
    key = Ed25519PrivateKey.generate()
    cert = _cert()
    signed, ok = sign_certificate_local(cert, private_key=key)

    assert ok is True
    assert signed.signature_local_ed25519 is not None
    assert len(signed.signature_local_ed25519) == 64
    assert signed.signature_local_pubkey_id == cert_pubkey_id(key.public_key())
    # The signature verifies against the public key over the documented input.
    key.public_key().verify(signed.signature_local_ed25519, cert_signing_input(cert))


def test_tampered_cert_fails_verification():
    # A signature over one cert must NOT verify against a different cert's input.
    key = Ed25519PrivateKey.generate()
    signed, _ = sign_certificate_local(_cert(bundle_hash="a" * 64), private_key=key)
    forged_input = cert_signing_input(_cert(bundle_hash="c" * 64))
    with pytest.raises(InvalidSignature):
        key.public_key().verify(signed.signature_local_ed25519, forged_input)


def test_no_key_yields_honestly_unsigned_cert(monkeypatch, tmp_path):
    # Point the custody path at a non-existent file → no key, no signature.
    monkeypatch.setenv(
        "AURORA_LAUNCH_CERT_SIGNING_KEY_PATH", str(tmp_path / "absent.key")
    )
    cert = _cert()
    out, ok = sign_certificate_local(cert)  # no key param → loads (absent)

    assert ok is False
    assert out.signature_local_ed25519 is None  # never fabricated
    assert out is cert  # returned unchanged


def test_loader_accepts_raw_and_hex_key_formats(tmp_path):
    # The fleet's ~/.secrets keys come in both raw-32-byte and 64-hex-char forms.
    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes_raw()  # 32 bytes
    expected_pub = key.public_key().public_bytes_raw()

    raw_path = tmp_path / "raw.key"
    raw_path.write_bytes(raw)
    hex_path = tmp_path / "hex.key"
    hex_path.write_text(raw.hex())

    loaded_raw = load_cert_signing_key(raw_path)
    loaded_hex = load_cert_signing_key(hex_path)

    assert loaded_raw is not None and loaded_hex is not None
    assert loaded_raw.public_key().public_bytes_raw() == expected_pub
    assert loaded_hex.public_key().public_bytes_raw() == expected_pub


def test_malformed_key_file_returns_none(tmp_path):
    bad = tmp_path / "bad.key"
    bad.write_bytes(b"not-a-valid-ed25519-key")
    assert load_cert_signing_key(bad) is None


def test_verify_round_trips_with_matching_pubkey():
    key = Ed25519PrivateKey.generate()
    signed, _ = sign_certificate_local(_cert(), private_key=key)
    assert verify_certificate_local(signed, public_key=key.public_key()) is True


def test_verify_rejects_wrong_key():
    signer = Ed25519PrivateKey.generate()
    other = Ed25519PrivateKey.generate()
    signed, _ = sign_certificate_local(_cert(), private_key=signer)
    assert verify_certificate_local(signed, public_key=other.public_key()) is False


def test_verify_rejects_tampered_cert():
    # A valid signature must not verify once the SIGNED content changes. The
    # signature covers `composite_signing_payload` (which itself encodes
    # bundle_hash|jcs|version), not the loose `bundle_hash_sha256` field — so
    # tamper the signed core to exercise rejection.
    key = Ed25519PrivateKey.generate()
    signed, _ = sign_certificate_local(_cert(), private_key=key)
    tampered = signed.model_copy(
        update={"composite_signing_payload": "tampered|payload|9.9.9"}
    )
    assert verify_certificate_local(tampered, public_key=key.public_key()) is False


def test_verify_false_when_signature_absent():
    # Presence of no signature → not verified (never trusted on absence either).
    assert verify_certificate_local(_cert(), public_key=Ed25519PrivateKey.generate().public_key()) is False


def test_verify_false_when_no_pubkey_configured(monkeypatch):
    # No embedded const and no env override → cannot verify → False, even with a
    # present signature. Guards "presence is not proof".
    monkeypatch.delenv("AURORA_LAUNCH_CERT_PUBLIC_KEY_HEX", raising=False)
    key = Ed25519PrivateKey.generate()
    signed, _ = sign_certificate_local(_cert(), private_key=key)
    assert verify_certificate_local(signed) is False  # no pubkey param, none embedded


def test_verify_uses_env_pubkey_override(monkeypatch):
    key = Ed25519PrivateKey.generate()
    pub_hex = key.public_key().public_bytes_raw().hex()
    monkeypatch.setenv("AURORA_LAUNCH_CERT_PUBLIC_KEY_HEX", pub_hex)
    signed, _ = sign_certificate_local(_cert(), private_key=key)
    assert verify_certificate_local(signed) is True  # resolves pubkey from env
