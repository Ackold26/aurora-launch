"""B4 Forecast Report + Methodology Cert schemas (PHASE_B_REQUIREMENTS §5.2).

Per REPORT_SECTIONS_SPEC.md (8 sections + Methodology Certificate WeasyPrint).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


_FROZEN = ConfigDict(frozen=True, extra="forbid", validate_assignment=True)


# ─── Forecast schemas ────────────────────────────────────────────────


class ConformalInterval(BaseModel):
    """Single weekly Conformal Prediction interval (per Tibshirani 2019 adapted)."""

    model_config = _FROZEN

    week_index: int = Field(ge=0)
    point_forecast: float
    lower_bound: float
    upper_bound: float
    coverage_target: float = Field(ge=0.0, le=1.0, default=0.95)

    @model_validator(mode="after")
    def bounds_ordering(self) -> "ConformalInterval":
        if not (self.lower_bound <= self.point_forecast <= self.upper_bound):
            raise ValueError(
                f"Conformal interval ordering broken: "
                f"lower={self.lower_bound} ≤ point={self.point_forecast} ≤ upper={self.upper_bound}"
            )
        return self


class ForecastResult(BaseModel):
    """Single horizon forecast results."""

    model_config = _FROZEN

    horizon_weeks: Literal[12, 26, 52]
    weekly_intervals: list[ConformalInterval]
    coverage_target: float = Field(ge=0.0, le=1.0, default=0.95)
    conformal_method: Literal["split", "weighted_jackknife"] = "split"
    n_calibration: int = Field(ge=1)


class ForecastSummary(BaseModel):
    """Aggregate forecast across horizons (for Cert / report headers)."""

    model_config = _FROZEN

    total_forecast_12w: float
    total_forecast_26w: float
    total_forecast_52w: float
    ci_pct_12w: float
    ci_pct_26w: float
    ci_pct_52w: float


# ─── Methodology Certificate schemas ─────────────────────────────────


class AcademicReference(BaseModel):
    """Academic reference with DOI."""

    model_config = _FROZEN

    citation: str
    doi: str
    relevance: str


class ReproductionInstructions(BaseModel):
    """Per BLOCKER B1 — recipe runnable via aurora-launch-reproduce CLI."""

    model_config = _FROZEN

    cli_command: str
    expected_rtol_deterministic: float = Field(default=1e-4, gt=0.0, lt=1.0)
    expected_rtol_stochastic: float = Field(default=1e-2, gt=0.0, lt=1.0)
    aurora_launch_required_version: str
    expected_install_command: str
    estimated_reproduction_time_minutes: int = Field(ge=0)


class VerifierEndpoints(BaseModel):
    """3 verifier formats per HIGH H3 fix."""

    model_config = _FROZEN

    web_verifier_url: str = "https://verify.auroraai.pro/"
    standalone_html_download_url: str = "https://auroraai.pro/verifier/standalone.html"
    cli_tool_download_url: str = "https://auroraai.pro/verifier/cli/"
    cli_tool_command_example: str = "aurora-verify <bundle.aurora> <cert.pdf>"


class ProxyMetadataSummary(BaseModel):
    """Proxy metadata snapshot for Cert."""

    model_config = _FROZEN

    proxy_code: str
    similarity_score: float = Field(ge=0.0, le=1.0)
    verdict: Literal["High", "Medium", "Low", "Insufficient"]
    inflation_factor_applied: float = Field(ge=1.0)


class TransferSummary(BaseModel):
    """Transfer provenance snapshot for Cert."""

    model_config = _FROZEN

    transferred_params: list[str]
    not_transferred: list[str]
    cross_category_distance: int = Field(ge=0, le=4)
    adaptation_rules_version: str = "1.0"


class MethodologyCertificateData(BaseModel):
    """Per BLOCKER B2 — single canonical format universal across tiers."""

    model_config = _FROZEN

    cert_id: UUID = Field(default_factory=uuid4)
    cert_version: str = "1.0"
    aurora_launch_version: str
    bundle_hash_sha256: str = Field(min_length=64, max_length=64)
    bundle_hash_jcs_canonical: str = Field(min_length=64, max_length=64)
    composite_signing_payload: str

    proxy_metadata_summary: ProxyMetadataSummary
    transfer_summary: TransferSummary
    forecast_summary: ForecastSummary

    methodology_references: list[AcademicReference]
    reproducibility_recipe: ReproductionInstructions

    # Dual signature (HIGH H2 fix)
    signature_local_ed25519: Optional[bytes] = None
    signature_local_pubkey_id: Optional[str] = None
    signature_aurora_ed25519: Optional[bytes] = None
    signature_aurora_pubkey_id: Optional[str] = None
    signature_aurora_pending: bool = False

    verifier_urls: VerifierEndpoints = Field(default_factory=VerifierEndpoints)
    generated_at: Optional[datetime] = None  # excluded from signing scope (audit B4)


# ─── Report schemas ──────────────────────────────────────────────────


class ReportSection(BaseModel):
    """One section of Launch Forecast Report (per REPORT_SECTIONS_SPEC §3)."""

    model_config = _FROZEN

    section_id: Literal[
        "cover", "executive_summary", "proxy_quality", "transfer_caveats",
        "forecast_12w", "forecast_26w", "forecast_52w", "methodology_references",
    ]
    visibility_per_framing: dict[str, Literal["expanded", "visible", "collapsed", "hidden"]] = Field(
        default_factory=dict
    )
    content_payload: dict = Field(default_factory=dict)  # section-specific data


class LaunchForecastReport(BaseModel):
    """Aggregate report data — composed of 8 sections + appendices."""

    model_config = _FROZEN

    sections: list[ReportSection] = Field(min_length=1)
    framing_preset: Literal["cfo", "cmo", "balanced"] = "balanced"
    forecast_horizons: list[ForecastResult]
    methodology_cert_id: UUID
