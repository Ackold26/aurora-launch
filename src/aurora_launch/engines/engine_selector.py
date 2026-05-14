"""Aurora Launch deterministic engine selection (B3 sprint, real implementation).

Per audit M4 — testable function shape. Replaces v0.1.x stub.

Selection logic per PHASE_B_REQUIREMENTS §5.1.3:

    n_proxies == 1 → "single"
    n_proxies >= 2 and all S_i >= 0.65 → "multi"
    n_proxies >= 2 and any S_i < 0.65 → "single_with_pooling" (use only S_max)
    max(S) - min(S) > 0.4 → "blocked" (heterogeneity too high)

Plus edge cases:
    n_proxies == 0 → "blocked" (no proxy provided)
    cross_category=True (cross-L1 non-adjacent) → "blocked"
    recipient_weeks_available == 0 for new brand — OK (single proxy needed,
    но multi requires anchor accumulation)
"""

from __future__ import annotations

from typing import Any

from aurora_launch.schemas.adaptation import EngineSelectionResult


# Defaults per spec; overridable via workflow YAML config
DEFAULT_SPREAD_THRESHOLD_FOR_BLOCKED: float = 0.4
DEFAULT_SINGLE_WITH_POOLING_THRESHOLD: float = 0.65


def select_engine(
    n_proxies: int,
    individual_scores: list[float],
    cross_category: bool = False,
    recipient_weeks_available: int = 0,
    spread_threshold_for_blocked: float = DEFAULT_SPREAD_THRESHOLD_FOR_BLOCKED,
    single_with_pooling_threshold: float = DEFAULT_SINGLE_WITH_POOLING_THRESHOLD,
) -> EngineSelectionResult:
    """Deterministic engine selector. Returns EngineSelectionResult dataclass.

    Tests this function directly (audit M4 — testable function shape).
    """
    # Edge case: no proxy provided
    if n_proxies <= 0:
        return EngineSelectionResult(
            selected_engine="blocked",
            rationale="No proxy provided (n_proxies=0). Insufficient для transfer.",
            n_proxies_used=0,
            blocking_reason="n_proxies must be ≥ 1",
        )

    # Edge case: cross-category non-adjacent — verdict layer should already block,
    # но defense-in-depth here too
    if cross_category:
        return EngineSelectionResult(
            selected_engine="blocked",
            rationale="Cross-category non-adjacent transfer blocked at verdict layer",
            n_proxies_used=n_proxies,
            blocking_reason="cross_category L1 non-adjacent transfers not supported per ADAPTATION_RULES §3",
        )

    # Edge case: scores list mismatch
    if len(individual_scores) != n_proxies:
        return EngineSelectionResult(
            selected_engine="blocked",
            rationale=f"individual_scores length {len(individual_scores)} != n_proxies {n_proxies}",
            n_proxies_used=n_proxies,
            blocking_reason="Scores list length mismatch",
        )

    # Single proxy case
    if n_proxies == 1:
        score = individual_scores[0]
        if score < 0.50:
            return EngineSelectionResult(
                selected_engine="blocked",
                rationale=f"Single proxy similarity {score:.2f} < 0.50 (Insufficient verdict)",
                n_proxies_used=1,
                blocking_reason="Insufficient similarity (S < 0.50) — refuse to deceive (CP-6)",
            )
        return EngineSelectionResult(
            selected_engine="single",
            rationale=f"Single proxy with similarity {score:.2f}",
            n_proxies_used=1,
            blocking_reason=None,
        )

    # Multi-proxy case
    max_s = max(individual_scores)
    min_s = min(individual_scores)
    spread = max_s - min_s

    # Heterogeneity check
    if spread > spread_threshold_for_blocked:
        return EngineSelectionResult(
            selected_engine="blocked",
            rationale=(
                f"Multi-proxy heterogeneity too high: "
                f"max(S)={max_s:.2f} - min(S)={min_s:.2f} = {spread:.2f} > {spread_threshold_for_blocked}. "
                f"Aggregating heterogeneous proxies risks misleading combined verdict."
            ),
            n_proxies_used=n_proxies,
            blocking_reason="Spread too high — escalate to expert proxy review",
        )

    # Some proxies below threshold — fall back to single with pooling weight reduction
    if any(s < single_with_pooling_threshold for s in individual_scores):
        return EngineSelectionResult(
            selected_engine="single_with_pooling",
            rationale=(
                f"Multi-proxy mode but some scores < {single_with_pooling_threshold}: "
                f"{[round(s, 2) for s in individual_scores]}. Falling back к single-proxy с reduced pooling weight."
            ),
            n_proxies_used=1,  # uses S_max only
            blocking_reason=None,
        )

    # Full multi-proxy hierarchical
    return EngineSelectionResult(
        selected_engine="multi",
        rationale=(
            f"Multi-proxy hierarchical engine: {n_proxies} proxies, "
            f"all S ≥ {single_with_pooling_threshold}, "
            f"spread {spread:.2f} ≤ {spread_threshold_for_blocked}"
        ),
        n_proxies_used=n_proxies,
        blocking_reason=None,
    )


# ─── Workflow handler entry point ────────────────────────────────────

async def select_engine_handler(ctx: Any, **kwargs: Any) -> dict[str, Any]:
    """Workflow step entry point — real implementation, not stub.

    Reads upstream similarity_score / n_proxies / cross_category from bundle
    context (placeholder — full integration when bundle reading shipped в B+).
    """
    # Phase B B3: handler reads from kwargs (passed by workflow engine).
    # Bundle context integration → когда workflow engine bundle-aware Phase B+.
    n_proxies = kwargs.get("n_proxies", 1)
    individual_scores = kwargs.get("individual_scores", [0.85])
    cross_category = kwargs.get("cross_category", False)
    recipient_weeks_available = kwargs.get("recipient_weeks_available", 0)
    spread_threshold = kwargs.get("spread_threshold_for_blocked", DEFAULT_SPREAD_THRESHOLD_FOR_BLOCKED)
    pooling_threshold = kwargs.get("single_with_pooling_threshold", DEFAULT_SINGLE_WITH_POOLING_THRESHOLD)

    result = select_engine(
        n_proxies=n_proxies,
        individual_scores=individual_scores,
        cross_category=cross_category,
        recipient_weeks_available=recipient_weeks_available,
        spread_threshold_for_blocked=spread_threshold,
        single_with_pooling_threshold=pooling_threshold,
    )

    return {
        "step_type": "engine_select",
        "stub": False,
        "selected_engine": result.selected_engine,
        "rationale": result.rationale,
        "n_proxies_used": result.n_proxies_used,
        "blocking_reason": result.blocking_reason,
        "thresholds_applied": {
            "spread_threshold_for_blocked": spread_threshold,
            "single_with_pooling_threshold": pooling_threshold,
        },
    }
