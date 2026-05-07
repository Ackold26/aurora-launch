"""Proxy + similarity schemas (B1 §4.2.4).

Per PHASE_B_REQUIREMENTS.md B1 schema section.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


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

    @field_validator("verdict")
    @classmethod
    def verdict_matches_score(cls, v: str, info) -> str:
        score = info.data.get("similarity_score")
        if score is None:
            return v
        expected = (
            "High"
            if score >= 0.85
            else "Medium"
            if score >= 0.65
            else "Low"
            if score >= 0.50
            else "Insufficient"
        )
        if v != expected:
            raise ValueError(
                f"verdict {v!r} inconsistent with score {score} (expected {expected!r})"
            )
        return v
