"""Proxy + similarity schemas (B1 §4.2.4).

Per PHASE_B_REQUIREMENTS.md B1 schema section.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class SimilarityDimensionScores(BaseModel):
    """6+2 dimension similarity scores (per SIMILARITY_FRAMEWORK §1)."""

    category_l1_match: float = Field(ge=0.0, le=1.0)
    category_l2_match: float = Field(ge=0.0, le=1.0)
    category_l3_match: float = Field(ge=0.0, le=1.0)
    pricing_tier_match: float = Field(ge=0.0, le=1.0)
    brand_size_match: float = Field(ge=0.0, le=1.0)
    distribution_match: float = Field(ge=0.0, le=1.0)
    media_maturity_match: float = Field(ge=0.0, le=1.0)
    lifecycle_match: float = Field(ge=0.0, le=1.0)
    weights_used: dict[str, float] = Field(default_factory=dict)


class AnonymizationDetails(BaseModel):
    """Per PROXY_INTAKE_PROTOCOL.md Шаг 3 — anonymization invariants."""

    synchronized_random_factor: float = Field(gt=0)
    period_shift_months: int = Field(ge=-24, le=24)
    brand_name_replaced: bool = True
    manufacturer_removed: bool = True


class ProxyEntry(BaseModel):
    """Single proxy brand entry (B2 §4.4.4)."""

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
