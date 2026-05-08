"""Proxy + similarity schemas (B1 §4.2.4).

Per PHASE_B_REQUIREMENTS.md B1 schema section.

Audit Block 1D-extended — finding "schemas without model_config":
all schemas в этом модуле теперь используют общий `_FROZEN_CONFIG` (frozen +
extra="forbid"). Previously they inherited Pydantic defaults (`extra="ignore"`),
silently dropping unknown fields — inconsistent с rest of codebase и
defence-in-depth concern для bundle ingestion.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


_FROZEN_CONFIG = ConfigDict(frozen=True, extra="forbid")


class SimilarityDimensionScores(BaseModel):
    """6+2 dimension similarity scores (per SIMILARITY_FRAMEWORK §1)."""

    model_config = _FROZEN_CONFIG

    category_l1_match: float = Field(ge=0.0, le=1.0)
    category_l2_match: float = Field(ge=0.0, le=1.0)
    category_l3_match: float = Field(ge=0.0, le=1.0)
    pricing_tier_match: float = Field(ge=0.0, le=1.0)
    brand_size_match: float = Field(ge=0.0, le=1.0)
    distribution_match: float = Field(ge=0.0, le=1.0)
    media_maturity_match: float = Field(ge=0.0, le=1.0)
    lifecycle_match: float = Field(ge=0.0, le=1.0)
    weights_used: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def weights_sum_to_unity_if_present(self) -> "SimilarityDimensionScores":
        """If `weights_used` is non-empty, weights must sum к ~1.0 (±0.05).

        Empty dict OK (caller did not specify weights); non-empty must be a
        valid weighting scheme.
        """
        if self.weights_used:
            total = sum(self.weights_used.values())
            if abs(total - 1.0) > 0.05:
                raise ValueError(
                    f"weights_used must sum to ~1.0 (±0.05), got {total:.4f}"
                )
        return self


class AnonymizationDetails(BaseModel):
    """Per PROXY_INTAKE_PROTOCOL.md Шаг 3 — anonymization invariants."""

    model_config = _FROZEN_CONFIG

    synchronized_random_factor: float = Field(gt=0)
    period_shift_months: int = Field(ge=-24, le=24)
    brand_name_replaced: bool = True
    manufacturer_removed: bool = True


class ProxyEntry(BaseModel):
    """Single proxy brand entry (B2 §4.4.4)."""

    model_config = _FROZEN_CONFIG

    proxy_brand_name: str = Field(min_length=1, max_length=200)
    proxy_brand_code: str = Field(pattern=r"^[A-Z][A-Z0-9_-]{2,32}$")
    category_l1: str
    category_l2: str
    category_l3: str
    pricing_tier: Literal["ECONOMY", "MAINSTREAM", "PREMIUM", "LUXURY"]
    brand_size: Literal["LEADER", "CHALLENGER", "NICHE"]
    distribution: Literal["NATIONAL", "REGIONAL", "NICHE"]
    media_maturity: Literal["ALWAYS_ON", "PULSING", "PROMO_DRIVEN", "DORMANT"]
    lifecycle: Literal["NEW", "GROWING", "MATURE", "DECLINING"]


class ProxyBrandMetadata(BaseModel):
    """Aurora Launch–specific proxy metadata (B1 ManifestV3Launch field)."""

    model_config = _FROZEN_CONFIG

    proxy_code: str = Field(pattern=r"^[A-Z][A-Z0-9_-]{2,32}$")
    similarity_dimensions: SimilarityDimensionScores
    similarity_score: float = Field(ge=0.0, le=1.0)
    verdict: Literal["High", "Medium", "Low", "Insufficient"]
    inflation_factor: float = Field(ge=1.0, le=3.0)
    intake_workflow_version: str = "1.0"
    anonymization_applied: AnonymizationDetails

    @model_validator(mode="after")
    def verdict_matches_score(self) -> "ProxyBrandMetadata":
        """FIX H-Audit-2: cross-field validation via model_validator (mode=after)
        — robust to field declaration order changes.

        Verdict thresholds per SIMILARITY_FRAMEWORK.md §6:
        - S ≥ 0.85 → High
        - 0.65 ≤ S < 0.85 → Medium
        - 0.50 ≤ S < 0.65 → Low
        - S < 0.50 → Insufficient (BLOCKS forecast generation per CP-6)
        """
        s = self.similarity_score
        expected = (
            "High"
            if s >= 0.85
            else "Medium"
            if s >= 0.65
            else "Low"
            if s >= 0.50
            else "Insufficient"
        )
        if self.verdict != expected:
            raise ValueError(
                f"verdict {self.verdict!r} inconsistent with score {s} "
                f"(expected {expected!r} per SIMILARITY_FRAMEWORK.md §6)"
            )
        return self
