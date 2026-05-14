"""Aurora Launch Pydantic v2 schemas — SSoT for data contracts."""

from aurora_launch.schemas.bundle import AuroraLaunchBundleMetadata
from aurora_launch.schemas.proxy import (
    AnonymizationDetails,
    ProxyBrandMetadata,
    ProxyEntry,
    SimilarityDimensionScores,
)
from aurora_launch.schemas.synthetic_corpus import (
    FormatAdapterContract,
    SyntheticProjectSpec,
)

__all__ = [
    "AnonymizationDetails",
    "AuroraLaunchBundleMetadata",
    "FormatAdapterContract",
    "ProxyBrandMetadata",
    "ProxyEntry",
    "SimilarityDimensionScores",
    "SyntheticProjectSpec",
]
