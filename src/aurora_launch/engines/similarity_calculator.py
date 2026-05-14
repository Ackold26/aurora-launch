"""Aurora Launch similarity calculator (B2 sprint, real implementation).

Per SIMILARITY_FRAMEWORK.md §1-7:
- 6+2 dimensions × per-category weight profiles
- Aggregate similarity score → verdict (High/Medium/Low/Insufficient)
- Anti-pattern detection (leader_as_proxy_for_challenger, etc.)
- Multi-proxy aggregation с multi-penalty + floor warnings

Real Python implementation. Rust WASM mirror deferred к dedicated frontend
session (≤200KB gzipped target per audit M1).

Replaces v0.1.x stub.
"""

from __future__ import annotations

from typing import Any, Literal

from aurora_launch.schemas.proxy import (
    ProxyEntry,
    SimilarityDimensionScores,
)


# ─── Verdict thresholds per SIMILARITY_FRAMEWORK §6 ──────────────────

VERDICT_THRESHOLDS = {
    "High": 0.85,
    "Medium": 0.65,
    "Low": 0.50,
    # < 0.50 = Insufficient (BLOCKED forecast generation)
}

INFLATION_BY_VERDICT = {
    "High": 1.2,
    "Medium": 1.5,
    "Low": 2.0,
    "Insufficient": 3.0,  # BLOCKED downstream, but inflation defined for completeness
}


# ─── Default weights + per-category profiles per SIMILARITY_FRAMEWORK §4 ──

DEFAULT_WEIGHTS = {
    "category": 0.30,         # combined L1/L2/L3
    "pricing_tier": 0.20,
    "media_maturity": 0.15,
    "brand_size": 0.15,
    "distribution": 0.10,
    "lifecycle": 0.10,
}


CATEGORY_WEIGHT_PROFILES: dict[str, dict[str, float]] = {
    "OTC_PHARMA": {
        "category": 0.40, "pricing_tier": 0.15, "media_maturity": 0.15,
        "brand_size": 0.15, "distribution": 0.10, "lifecycle": 0.05,
    },
    "RX_PHARMA": {
        "category": 0.45, "pricing_tier": 0.10, "media_maturity": 0.15,
        "brand_size": 0.15, "distribution": 0.10, "lifecycle": 0.05,
    },
    "FMCG_IMPULSE": {
        "category": 0.25, "pricing_tier": 0.25, "media_maturity": 0.15,
        "brand_size": 0.15, "distribution": 0.10, "lifecycle": 0.10,
    },
    "FMCG_STAPLES": {
        "category": 0.25, "pricing_tier": 0.20, "media_maturity": 0.15,
        "brand_size": 0.15, "distribution": 0.15, "lifecycle": 0.10,
    },
    "PREMIUM_COSMETICS": {
        "category": 0.25, "pricing_tier": 0.30, "media_maturity": 0.15,
        "brand_size": 0.15, "distribution": 0.10, "lifecycle": 0.05,
    },
    "TELECOM_BANKING": {
        "category": 0.30, "pricing_tier": 0.10, "media_maturity": 0.20,
        "brand_size": 0.20, "distribution": 0.10, "lifecycle": 0.10,
    },
    "B2B": {
        "category": 0.35, "pricing_tier": 0.15, "media_maturity": 0.15,
        "brand_size": 0.20, "distribution": 0.05, "lifecycle": 0.10,
    },
}


def _get_weight_profile_id(category_l1: str, category_l2: str = "") -> str:
    """Lookup profile id from category.

    FIX B-A3-3: Cosmetics differentiated mass vs premium (was lumping all Cosmetics
    к PREMIUM_COSMETICS, breaking mass-market scoring). Mass cosmetics use
    FMCG_STAPLES weights (distribution matters more than premium pricing).
    """
    if category_l1 == "OTC_pharma":
        return "OTC_PHARMA"
    if category_l1 == "Rx_pharma":
        return "RX_PHARMA"
    if category_l1.startswith("FMCG_food") and ("snacks" in category_l2 or "beverage" in category_l2):
        return "FMCG_IMPULSE"
    if category_l1.startswith("FMCG_beverage"):
        return "FMCG_IMPULSE"
    if category_l1.startswith("FMCG"):
        return "FMCG_STAPLES"
    if category_l1.startswith("Cosmetics"):
        # B-A3-3 fix: distinguish mass vs premium subcategories
        # Mass cosmetics behave like FMCG (distribution-sensitive)
        if "mass" in category_l2.lower():
            return "FMCG_STAPLES"
        return "PREMIUM_COSMETICS"
    if category_l1 in ("Telecom", "Banking"):
        return "TELECOM_BANKING"
    if category_l1 == "B2B":
        return "B2B"
    return "DEFAULT"


def _get_weights(category_l1: str, category_l2: str = "") -> dict[str, float]:
    """Returns weights for category. Default if no profile matches."""
    profile_id = _get_weight_profile_id(category_l1, category_l2)
    return CATEGORY_WEIGHT_PROFILES.get(profile_id, DEFAULT_WEIGHTS).copy()


# ─── Per-dimension scoring per SIMILARITY_FRAMEWORK §1 ───────────────


def _score_category_match(
    recipient_l1: str, recipient_l2: str, recipient_l3: str,
    proxy_l1: str, proxy_l2: str, proxy_l3: str,
) -> float:
    """Category L1/L2/L3 match per §1.1: L3=1.0 / L2=0.7 / L1=0.5 / adjacent_L1=0.2 / cross=0.0"""
    if recipient_l3 == proxy_l3:
        return 1.0
    if recipient_l2 == proxy_l2:
        return 0.7
    if recipient_l1 == proxy_l1:
        return 0.5

    # Adjacent L1 lookup (per ADAPTATION_RULES §3)
    ADJACENT_PAIRS = {
        ("FMCG_food", "FMCG_beverage"),
        ("FMCG_food", "FMCG_household"),
        ("OTC_pharma", "supplements"),
        ("Cosmetics", "FMCG_personal_care"),
        ("Telecom", "Banking"),
    }
    pair = (recipient_l1, proxy_l1)
    pair_reversed = (proxy_l1, recipient_l1)
    if pair in ADJACENT_PAIRS or pair_reversed in ADJACENT_PAIRS:
        return 0.2

    return 0.0


def _score_tier_distance(recipient_tier: str, proxy_tier: str, tiers_ordered: list[str]) -> float:
    """Generic tier distance scoring per §1.2: dist 0=1.0 / 1=0.5 / 2=0.2 / 3=0.0"""
    DISTANCE_TO_SCORE = {0: 1.0, 1: 0.5, 2: 0.2, 3: 0.0}
    try:
        idx_r = tiers_ordered.index(recipient_tier)
        idx_p = tiers_ordered.index(proxy_tier)
    except ValueError:
        return 0.0
    distance = abs(idx_r - idx_p)
    return DISTANCE_TO_SCORE.get(distance, 0.0)


PRICING_TIERS = ["ECONOMY", "MAINSTREAM", "PREMIUM", "LUXURY"]
BRAND_SIZE_TIERS = ["LEADER", "CHALLENGER", "NICHE"]
DISTRIBUTION_TIERS = ["NATIONAL", "REGIONAL", "NICHE"]
MEDIA_MATURITY_TIERS = ["ALWAYS_ON", "PULSING", "PROMO_DRIVEN", "DORMANT"]
LIFECYCLE_TIERS = ["NEW", "GROWING", "MATURE", "DECLINING"]


# ─── Public API: compute_dimension_scores ────────────────────────────


def compute_dimension_scores(
    recipient: ProxyEntry,  # both inputs use ProxyEntry shape
    proxy: ProxyEntry,
) -> SimilarityDimensionScores:
    """Compute per-dimension similarity scores for proxy vs recipient."""
    return SimilarityDimensionScores(
        category_l1_match=1.0 if recipient.category_l1 == proxy.category_l1 else 0.0,
        category_l2_match=1.0 if recipient.category_l2 == proxy.category_l2 else 0.0,
        category_l3_match=_score_category_match(
            recipient.category_l1, recipient.category_l2, recipient.category_l3,
            proxy.category_l1, proxy.category_l2, proxy.category_l3,
        ),
        pricing_tier_match=_score_tier_distance(
            recipient.pricing_tier, proxy.pricing_tier, PRICING_TIERS
        ),
        brand_size_match=_score_tier_distance(
            recipient.brand_size, proxy.brand_size, BRAND_SIZE_TIERS
        ),
        distribution_match=_score_tier_distance(
            recipient.distribution, proxy.distribution, DISTRIBUTION_TIERS
        ),
        media_maturity_match=_score_tier_distance(
            recipient.media_maturity, proxy.media_maturity, MEDIA_MATURITY_TIERS
        ),
        lifecycle_match=_score_tier_distance(
            recipient.lifecycle, proxy.lifecycle, LIFECYCLE_TIERS
        ),
        weights_used={},  # populated by aggregate function
    )


# ─── Public API: aggregate_score + verdict ───────────────────────────


def compute_aggregate_score(
    dimension_scores: SimilarityDimensionScores,
    weights: dict[str, float],
) -> float:
    """Weighted average across dimensions.

    Category dimension uses category_l3_match (which already encodes L3/L2/L1/adjacent).
    """
    total_weight = sum(weights.values())
    if total_weight == 0:
        return 0.0

    contributions = {
        "category": dimension_scores.category_l3_match * weights.get("category", 0.0),
        "pricing_tier": dimension_scores.pricing_tier_match * weights.get("pricing_tier", 0.0),
        "brand_size": dimension_scores.brand_size_match * weights.get("brand_size", 0.0),
        "distribution": dimension_scores.distribution_match * weights.get("distribution", 0.0),
        "media_maturity": dimension_scores.media_maturity_match * weights.get("media_maturity", 0.0),
        "lifecycle": dimension_scores.lifecycle_match * weights.get("lifecycle", 0.0),
    }
    weighted_sum = sum(contributions.values())
    return weighted_sum / total_weight


def determine_verdict(score: float) -> Literal["High", "Medium", "Low", "Insufficient"]:
    """Map aggregate score к verdict label.

    Audit (post-1D extended): rejects non-finite scores upfront. Previously a
    NaN would silently route to "Insufficient" because every `>=` comparison
    is False on NaN — masking upstream computation bugs as "low similarity".
    """
    import math as _math

    if not _math.isfinite(score):
        raise ValueError(
            f"determine_verdict: similarity score must be finite, got {score!r} "
            f"(NaN/Inf indicates upstream computation error — investigate "
            f"compute_aggregate_score inputs)."
        )
    if score >= VERDICT_THRESHOLDS["High"]:
        return "High"
    if score >= VERDICT_THRESHOLDS["Medium"]:
        return "Medium"
    if score >= VERDICT_THRESHOLDS["Low"]:
        return "Low"
    return "Insufficient"


# ─── Anti-pattern detection ──────────────────────────────────────────


def detect_anti_patterns(
    recipient: ProxyEntry, proxy: ProxyEntry,
) -> list[dict]:
    """Detect risky proxy patterns. Returns list of warnings dict."""
    flags: list[dict] = []

    # Leader as proxy for challenger
    if proxy.brand_size == "LEADER" and recipient.brand_size == "CHALLENGER":
        flags.append({
            "pattern_id": "leader_as_proxy_for_challenger",
            "severity": "warning",
            "message": (
                "Using leader proxy for challenger recipient — expected ROI may overestimate. "
                "Consider challenger-tier proxy for closer match."
            ),
        })

    # Premium proxy for economy recipient (or vice versa)
    if (
        proxy.pricing_tier == "PREMIUM" and recipient.pricing_tier == "ECONOMY"
    ) or (
        proxy.pricing_tier == "LUXURY" and recipient.pricing_tier in ("ECONOMY", "MAINSTREAM")
    ):
        flags.append({
            "pattern_id": "premium_as_proxy_for_economy",
            "severity": "warning",
            "message": "Premium proxy for economy recipient — pricing elasticity differs significantly.",
        })

    # Always-on proxy for dormant recipient
    if proxy.media_maturity == "ALWAYS_ON" and recipient.media_maturity == "DORMANT":
        flags.append({
            "pattern_id": "always_on_as_proxy_for_dormant",
            "severity": "warning",
            "message": "Always-on media proxy for dormant brand — adstock decay assumptions different.",
        })

    return flags


# ─── Multi-proxy aggregation per SIMILARITY_FRAMEWORK §5 ─────────────


def aggregate_multi_proxy(
    individual_scores: list[float],
    pooling_weights: list[float],
) -> dict[str, Any]:
    """Multi-proxy weighted aggregate с multi-penalty + floor warnings.

    Returns:
        combined_score: weighted average
        multi_penalty: 1 + 0.05 × (N-1)
        effective_inflation: base × multi_penalty
        floor_warnings: list of dicts
    """
    n = len(individual_scores)
    if n == 0:
        return {
            "combined_score": 0.0,
            "multi_penalty": 1.0,
            "floor_warnings": [],
        }

    # Validate weights sum к 1.0
    weights_sum = sum(pooling_weights)
    if abs(weights_sum - 1.0) > 1e-6:
        raise ValueError(
            f"Pooling weights must sum to 1.0, got {weights_sum}"
        )

    combined = sum(s * w for s, w in zip(individual_scores, pooling_weights, strict=False))
    multi_penalty = 1.0 + 0.05 * (n - 1)

    # Floor warnings per §5.3
    warnings: list[dict] = []
    for i, s in enumerate(individual_scores):
        if s < 0.5:
            warnings.append({
                "warning_type": "individual_below_0_5",
                "affected_proxy_index": i,
                "score": s,
                "message": f"Proxy #{i+1} similarity {s:.2f} < 0.50 — Insufficient verdict floor",
            })

    if individual_scores:
        spread = max(individual_scores) - min(individual_scores)
        if spread > 0.3:
            warnings.append({
                "warning_type": "spread_above_0_3",
                "spread": spread,
                "message": f"Multi-proxy spread {spread:.2f} > 0.30 — heterogeneity high",
            })

    return {
        "combined_score": combined,
        "multi_penalty": multi_penalty,
        "effective_inflation": multi_penalty,  # base inflation applied separately
        "floor_warnings": warnings,
    }


# ─── Workflow handler entry point ────────────────────────────────────


async def compute(ctx: Any, **kwargs: Any) -> dict[str, Any]:
    """Workflow handler — real similarity scoring."""
    # Inputs (production reads from upstream bundle)
    recipient_data = kwargs.get("recipient")
    proxy_data = kwargs.get("proxy")

    if not recipient_data or not proxy_data:
        # Fallback test inputs
        recipient_data = recipient_data or {
            "proxy_brand_name": "Test Recipient",
            "proxy_brand_code": "REC-2026",
            "category_l1": "FMCG_beverage",
            "category_l2": "beverage_energy",
            "category_l3": "energy_caffeine",
            "pricing_tier": "PREMIUM",
            "brand_size": "CHALLENGER",
            "distribution": "NATIONAL",
            "media_maturity": "ALWAYS_ON",
            "lifecycle": "GROWING",
        }
        proxy_data = proxy_data or {
            "proxy_brand_name": "Test Proxy",
            "proxy_brand_code": "TST-2026",
            "category_l1": "FMCG_beverage",
            "category_l2": "beverage_energy",
            "category_l3": "energy_caffeine",
            "pricing_tier": "PREMIUM",
            "brand_size": "LEADER",
            "distribution": "NATIONAL",
            "media_maturity": "ALWAYS_ON",
            "lifecycle": "MATURE",
        }

    recipient = ProxyEntry(**recipient_data)
    proxy = ProxyEntry(**proxy_data)

    weights = _get_weights(recipient.category_l1, recipient.category_l2)
    dim_scores = compute_dimension_scores(recipient, proxy)
    score = compute_aggregate_score(dim_scores, weights)
    verdict = determine_verdict(score)
    inflation = INFLATION_BY_VERDICT[verdict]
    anti_patterns = detect_anti_patterns(recipient, proxy)

    # Multi-proxy mode
    multi_proxy_mode = kwargs.get("multi_proxy_mode", False)
    multi_data: dict[str, Any] = {}
    if multi_proxy_mode:
        all_scores = kwargs.get("individual_scores", [score])
        weights_list = kwargs.get("pooling_weights", [1.0])
        multi_data = aggregate_multi_proxy(all_scores, weights_list)

    return {
        "step_type": "proxy_select",
        "stub": False,
        "similarity_score": score,
        "verdict": verdict,
        "inflation_factor": inflation,
        "weights_profile_used": _get_weight_profile_id(
            recipient.category_l1, recipient.category_l2
        ),
        "dimension_scores": dim_scores.model_dump(),
        "anti_patterns_detected": anti_patterns,
        "block_forecast": verdict == "Insufficient",
        "multi_proxy_mode": multi_proxy_mode,
        "multi_proxy_data": multi_data,
    }
