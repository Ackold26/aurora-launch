"""Synthetic corpus generation schemas (B0.5 §4.1.4).

Per PHASE_B_REQUIREMENTS.md §4.1 Pydantic Schemas section.
"""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field

CategoryL3 = Literal[
    "FMCG_food.snacks_savoury",
    "FMCG_food.snacks_sweet",
    "FMCG_food.dairy_yogurt",
    "FMCG_beverage.beverage_carbonated",
    "FMCG_beverage.beverage_juice",
    "FMCG_beverage.beverage_energy",
    "OTC_pharma.OTC_cold_flu",
    "OTC_pharma.OTC_pain",
    "Cosmetics.skincare_premium",
    "Cosmetics.haircare_premium",
    "Telecom.telecom_b2c_mobile",
    "Banking.banking_retail",
    "awareness.brand_awareness_only",
    "cross_category.cross_l1_edge",
]

VariantId = Literal[
    "baseline",
    "high_seasonality",
    "volatile",
    "low_data",
    "cross_category_edge",
]


class SyntheticProjectSpec(BaseModel):
    """Specification for synthetic corpus project generation.

    Per PHASE_B_REQUIREMENTS.md §4.1 — `aurora corpus generate <category> <variant> --seed <N>`.
    """

    seed: int = Field(ge=0, lt=2**32)
    category_l3: CategoryL3
    variant: VariantId
    n_weeks: int = Field(default=104, ge=104, le=312)
    n_channels: int = Field(default=6, ge=4, le=12)
    pricing_tier: Literal["ECONOMY", "MAINSTREAM", "PREMIUM", "LUXURY"] = "MAINSTREAM"
    brand_size: Literal["LEADER", "CHALLENGER", "NICHE"] = "CHALLENGER"
    distribution: Literal["NATIONAL", "REGIONAL", "NICHE"] = "NATIONAL"
    media_maturity: Literal["ALWAYS_ON", "PULSING", "PROMO_DRIVEN", "DORMANT"] = "ALWAYS_ON"
    lifecycle: Literal["NEW", "GROWING", "MATURE", "DECLINING"] = "MATURE"


class FormatAdapterContract(BaseModel):
    """Abstract contract for plug-in ProxyDataSource.

    Per PHASE_B_REQUIREMENTS.md §4.1 — extensibility point.
    """

    adapter_id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    adapter_version: str
    schema_version: str
    sample_files_glob: list[str]
    canonical_record_mapping: dict[str, str]
    detected_signatures: list[str] = Field(default_factory=list)


class ProxyDataSource(Protocol):
    """Plug-in extensibility point for per-deal proxy data ingestion.

    Phase B+ extensibility. Phase B ships built-in DSM/Mediascope adapters.
    """

    def detect(self, file_path: str) -> bool: ...

    def parse(self, file_path: str) -> list[dict]: ...

    def get_metadata(self) -> FormatAdapterContract: ...
