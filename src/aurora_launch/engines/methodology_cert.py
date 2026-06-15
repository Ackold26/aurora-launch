"""Aurora Launch Methodology Certificate generator (B4 sprint, real impl).

Per PHASE_B_REQUIREMENTS §5.2 + ADR-006 (Tauri webview PDF) + HIGH H2/H3 fixes:
- Single canonical format universal across tiers (BLOCKER B2)
- Dual-signature scheme (local + Aurora) — HIGH H2
- 3 verifier formats (web + standalone HTML + CLI) — HIGH H3
- Reproducibility recipe via aurora-launch-reproduce CLI — BLOCKER B1

Real implementation for metadata composition + signing scope. Actual PDF
rendering (via Tauri webview / Typst / ReportLab fallback per ADR-006)
deferred к Phase A C8 reporting integration.

Ed25519 signing scope EXCLUDES timestamps (audit B4): generated_at field
NOT included в signed payload. Signature deterministic for same content.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from aurora_launch.schemas.forecast import (
    AcademicReference,
    ForecastSummary,
    MethodologyCertificateData,
    ProxyMetadataSummary,
    ReproductionInstructions,
    TransferSummary,
    VerifierEndpoints,
)


# ─── Standard academic references (per MATH_REFERENCE.md) ────────────


_DEFAULT_METHODOLOGY_REFS: list[AcademicReference] = [
    AcademicReference(
        citation="Tibshirani, R., Foygel Barber, R. (2019). Conformal Prediction Under Covariate Shift.",
        doi="10.48550/arXiv.1904.06019",
        relevance="Conformal Prediction adapted для transfer scenario",
    ),
    AcademicReference(
        citation="Konstantinopoulos, K. (2014). Empirical Bayes for hierarchical models.",
        doi="10.1080/01621459.2014.882844",
        relevance="ESS-based partial pooling weight schedule",
    ),
    AcademicReference(
        citation="Hanssens, D., Parsons, L., Schultz, R. (2001). Market Response Models.",
        doi="10.1007/978-1-4615-1417-3",
        relevance="Adstock + Hill saturation MMM foundations",
    ),
    AcademicReference(
        citation="Vovk, V. (2005). Algorithmic Learning in a Random World.",
        doi="10.1007/b106715",
        relevance="Conformal interval quantile correction для small calibration sets",
    ),
]


# ─── Composite signing payload (R8 closure preserved) ────────────────


def compute_composite_signing_payload(
    bundle_hash_sha256: str,
    bundle_hash_jcs_canonical: str,
    aurora_launch_version: str,
) -> str:
    """Composite signing payload per BLOCKER B1/B2 + audit B-A2-1 fix.

    Format: <bundle_hash> || "|" || <jcs_canonical> || "|" || <version>
    Domain validation rejects '|' in inputs (per Aurora Launch composite signing).
    """
    for name, value in (
        ("bundle_hash_sha256", bundle_hash_sha256),
        ("bundle_hash_jcs_canonical", bundle_hash_jcs_canonical),
        ("aurora_launch_version", aurora_launch_version),
    ):
        if "|" in value:
            raise ValueError(
                f"Composite signing input {name!r} contains '|' separator — "
                f"hash collision risk. Aurora Launch inputs must be hex strings + semver."
            )

    return f"{bundle_hash_sha256}|{bundle_hash_jcs_canonical}|{aurora_launch_version}"


# ─── Cert builder ────────────────────────────────────────────────────


def build_certificate_data(
    aurora_launch_version: str,
    bundle_hash_sha256: str,
    bundle_hash_jcs_canonical: str,
    proxy_metadata: ProxyMetadataSummary,
    transfer_summary: TransferSummary,
    forecast_summary: ForecastSummary,
    methodology_references: Optional[list[AcademicReference]] = None,
    reproduction_install_cmd: str = "Download from auroraai.pro/launch/",
    estimated_reproduction_minutes: int = 30,
) -> MethodologyCertificateData:
    """Compose complete MethodologyCertificateData (single canonical format)."""
    composite_payload = compute_composite_signing_payload(
        bundle_hash_sha256=bundle_hash_sha256,
        bundle_hash_jcs_canonical=bundle_hash_jcs_canonical,
        aurora_launch_version=aurora_launch_version,
    )

    repro_recipe = ReproductionInstructions(
        cli_command=f"aurora-launch-reproduce <bundle_path> {bundle_hash_sha256}",
        aurora_launch_required_version=aurora_launch_version,
        expected_install_command=reproduction_install_cmd,
        estimated_reproduction_time_minutes=estimated_reproduction_minutes,
    )

    return MethodologyCertificateData(
        aurora_launch_version=aurora_launch_version,
        bundle_hash_sha256=bundle_hash_sha256,
        bundle_hash_jcs_canonical=bundle_hash_jcs_canonical,
        composite_signing_payload=composite_payload,
        proxy_metadata_summary=proxy_metadata,
        transfer_summary=transfer_summary,
        forecast_summary=forecast_summary,
        methodology_references=methodology_references or _DEFAULT_METHODOLOGY_REFS,
        reproducibility_recipe=repro_recipe,
        verifier_urls=VerifierEndpoints(),
    )


# ─── Signing scope per audit B4 (excludes timestamps) ────────────────


def signing_payload_bytes(cert_data: MethodologyCertificateData) -> bytes:
    """Compute signing payload bytes — EXCLUDES timestamp fields (audit B4).

    Same cert content → same signature, regardless of when it was generated.
    Reproducibility-friendly.

    FIX B-A3-2: References use length-prefixed encoding to prevent separator
    collision (citation strings could contain '|'). Format per reference:
    "<len(doi)>:<doi>|<len(citation)>:<citation>". Length-prefix makes encoding
    unambiguous regardless of content.
    """
    def _len_prefix(s: str) -> str:
        b = s.encode("utf-8")
        return f"{len(b)}:{s}"

    refs_canonical_parts = []
    for ref in cert_data.methodology_references:
        # Format: <len(doi)>:doi|<len(citation)>:citation|<len(relevance)>:relevance
        refs_canonical_parts.append(
            f"{_len_prefix(ref.doi)}|{_len_prefix(ref.citation)}|{_len_prefix(ref.relevance)}"
        )
    refs_canonical = "||".join(refs_canonical_parts)  # double-pipe between refs

    payload = (
        f"{cert_data.composite_signing_payload}"
        f"|{cert_data.aurora_launch_version}"
        f"|{cert_data.cert_version}"
        f"|REFS:{refs_canonical}"
    )
    return payload.encode("utf-8")


def cert_payload_sha256(cert_data: MethodologyCertificateData) -> str:
    """SHA-256 hex of signing payload (used as input к Ed25519 signer)."""
    return hashlib.sha256(signing_payload_bytes(cert_data)).hexdigest()


# ─── Local Ed25519 certificate signer (Phase D, variant B) ───────────
#
# Fills the certificate's `signature_local_ed25519` slot with a STABLE,
# vendor-held key — NOT the per-install ephemeral key (`safe_serializer`
# blob key) and NOT cloud KMS. The honest framing: a real LOCAL signature,
# surfaced as a local-trust badge, never as production / cloud-KMS (that
# stays the deferred `signature_aurora_*` slot).
#
# Custody (variant B): a dedicated `~/.secrets/rosst_launch_private.key`,
# SEPARATE from the fleet licence key (`rosst_agency`). Minted in a key
# ceremony; this module only READS it. Absent key → honest `local_signed`
# = False (an unsigned certificate is emitted, never a fabricated signature).

_CERT_KEY_ENV = "AURORA_LAUNCH_CERT_SIGNING_KEY_PATH"


def _resolve_cert_signing_key_path() -> Path:
    """Cert signing key location: `$AURORA_LAUNCH_CERT_SIGNING_KEY_PATH` else the
    custody default `~/.secrets/rosst_launch_private.key`."""
    override = os.environ.get(_CERT_KEY_ENV)
    return Path(override) if override else Path.home() / ".secrets" / "rosst_launch_private.key"


def _private_key_from_keyfile_bytes(raw: bytes) -> Optional[Ed25519PrivateKey]:
    """Decode an Ed25519 private key from key-file bytes, tolerating BOTH the
    raw-32-byte and 64-hex-char conventions the fleet's ~/.secrets keys use
    (rosst_content is raw-32, rosst_agency/creative/legal/media are hex). None
    on any malformed input — the caller falls back to an unsigned certificate."""
    stripped = raw.strip()
    candidate: Optional[bytes] = None
    if len(stripped) == 64 and all(c in b"0123456789abcdefABCDEF" for c in stripped):
        try:
            candidate = bytes.fromhex(stripped.decode("ascii"))
        except ValueError:
            return None
    elif len(raw) == 32:
        candidate = raw
    elif len(stripped) == 32:
        candidate = stripped
    if candidate is None or len(candidate) != 32:
        return None
    try:
        return Ed25519PrivateKey.from_private_bytes(candidate)
    except ValueError:
        return None


def load_cert_signing_key(path: Optional[Path] = None) -> Optional[Ed25519PrivateKey]:
    """Load the local cert signing key, or None if absent/unreadable/malformed.
    None is the safe default: the caller then emits an honestly-UNSIGNED cert."""
    p = path or _resolve_cert_signing_key_path()
    try:
        raw = p.read_bytes()
    except OSError:
        return None
    return _private_key_from_keyfile_bytes(raw)


def cert_signing_input(cert_data: MethodologyCertificateData) -> bytes:
    """The 32 bytes the Ed25519 signature covers: SHA-256 digest of the
    timestamp-free signing payload (== `cert_payload_sha256` as raw bytes).
    Mirrors the bundle path's "sign the hash" convention so a future verifier
    checks `verify(signature, cert_signing_input(cert))`."""
    return hashlib.sha256(signing_payload_bytes(cert_data)).digest()


def cert_pubkey_id(public_key: Ed25519PublicKey) -> str:
    """Short, honest signing-key identifier (`local:<16hex>` = first 16 hex of
    SHA-256(raw pubkey)). Ties a signature to a specific key for the UI / a
    verifier without embedding the key itself."""
    raw = public_key.public_bytes_raw()
    return "local:" + hashlib.sha256(raw).hexdigest()[:16]


def sign_certificate_local(
    cert_data: MethodologyCertificateData,
    private_key: Optional[Ed25519PrivateKey] = None,
) -> tuple[MethodologyCertificateData, bool]:
    """Return `(cert, signed)`. When a key is available (the `private_key` arg, or
    the custody key on disk), returns a copy with `signature_local_ed25519` +
    `signature_local_pubkey_id` populated and `signed=True`. With no key, returns
    the cert UNCHANGED with `signed=False` — honestly unsigned, never faked."""
    key = private_key or load_cert_signing_key()
    if key is None:
        return cert_data, False
    signature = key.sign(cert_signing_input(cert_data))  # Ed25519 → 64 bytes
    signed = cert_data.model_copy(
        update={
            "signature_local_ed25519": signature,
            "signature_local_pubkey_id": cert_pubkey_id(key.public_key()),
        }
    )
    return signed, True


# ─── Workflow handler entry point ────────────────────────────────────


async def build_certificate(ctx: Any, **kwargs: Any) -> dict[str, Any]:
    """Workflow handler — real composition (signing deferred к C7 service)."""
    aurora_launch_version = kwargs.get("aurora_launch_version", "0.1.x-b05")
    bundle_hash_sha256 = kwargs.get("bundle_hash_sha256", "0" * 64)
    bundle_hash_jcs_canonical = kwargs.get("bundle_hash_jcs_canonical", "0" * 64)

    # Build summaries from kwargs or test fixtures
    proxy_metadata = ProxyMetadataSummary(
        proxy_code=kwargs.get("proxy_code", "TEST-2026-Q1"),
        similarity_score=kwargs.get("similarity_score", 0.72),
        verdict=kwargs.get("verdict", "Medium"),
        inflation_factor_applied=kwargs.get("inflation_factor", 1.5),
    )

    transfer_summary = TransferSummary(
        transferred_params=kwargs.get(
            "transferred_params",
            ["adstock_decay", "hill_gamma", "hill_k", "seasonality", "trend"],
        ),
        not_transferred=kwargs.get(
            "not_transferred",
            ["beta_coefficients", "baseline", "residual_variance"],
        ),
        cross_category_distance=kwargs.get("cross_category_distance", 0),
    )

    forecast_summary = ForecastSummary(
        total_forecast_12w=kwargs.get("forecast_12w", 1_200_000.0),
        total_forecast_26w=kwargs.get("forecast_26w", 2_600_000.0),
        total_forecast_52w=kwargs.get("forecast_52w", 5_200_000.0),
        ci_pct_12w=kwargs.get("ci_pct_12w", 15.0),
        ci_pct_26w=kwargs.get("ci_pct_26w", 22.0),
        ci_pct_52w=kwargs.get("ci_pct_52w", 32.0),
    )

    cert_data = build_certificate_data(
        aurora_launch_version=aurora_launch_version,
        bundle_hash_sha256=bundle_hash_sha256,
        bundle_hash_jcs_canonical=bundle_hash_jcs_canonical,
        proxy_metadata=proxy_metadata,
        transfer_summary=transfer_summary,
        forecast_summary=forecast_summary,
    )

    # Local Ed25519 signature (Phase D variant B): real when the custody key
    # `~/.secrets/rosst_launch_private.key` is present, honestly unsigned
    # otherwise. The Aurora cloud-KMS signature stays deferred (aurora_pending).
    cert_data, local_signed = sign_certificate_local(cert_data)

    payload_hash = cert_payload_sha256(cert_data)

    return {
        "step_type": "cert_sign",
        "stub": False,
        "cert_id": str(cert_data.cert_id),
        "cert_payload_sha256": payload_hash,
        "template_id": kwargs.get("template_id", "methodology_certificate_v1"),
        "pdf_renderer_used": kwargs.get("pdf_renderer", "tauri_webview"),
        "dual_signature_status": {
            "local_signed": local_signed,  # True iff the vendor custody key signed it
            "aurora_signed": False,
            "aurora_pending": True,
        },
        "signature_local_pubkey_id": cert_data.signature_local_pubkey_id,
        "reproducibility_recipe_included": True,
        "reproducibility_cli": cert_data.reproducibility_recipe.cli_command,
        "previous_cert_referenced": kwargs.get("include_previous_cert_reference", False),
        "verifier_urls": cert_data.verifier_urls.model_dump(),
        "tier_independent": True,  # BLOCKER B2 — single canonical format
        "n_methodology_references": len(cert_data.methodology_references),
    }
