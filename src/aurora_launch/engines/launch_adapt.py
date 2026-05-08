"""Aurora Launch adaptation layer (B3 sprint).

STUB IMPLEMENTATION v0.1.2-b05 (M-A2-7 closure): provides
`apply_recipient_magnitudes` entry-point referenced by workflow YAML.

# TODO Phase B B3 sprint full implementation per ADAPTATION_RULES.md:
# - extract_proxy_priors: 5 shape params per channel (adstock_decay, hill_gamma,
#   hill_k, seasonality, trend) from proxy posterior
# - apply_recipient_magnitudes: magnitude calibration via anchors,
#   Bayesian std × 1/√w_proxy invariant (audit BLOCKER fix preserved)
# - Cross-category transfer matrix enforcement
"""

from __future__ import annotations

from typing import Any


async def apply_recipient_magnitudes(ctx: Any, **kwargs: Any) -> dict[str, Any]:
    """Magnitude calibration handler — stub returns realistic-shape priors."""
    return {
        "step_type": "apply_recipient_magnitudes",
        "stub": True,
        "transferred_params": ["adstock_decay", "hill_gamma", "hill_k", "seasonality", "trend"],
        "not_transferred": ["beta_coefficients", "baseline", "residual_variance"],
        "inflation_factor_applied": 1.5,
        "cross_category_distance": 0,
        "warnings": [],
        "todo": "Phase B B3 sprint — full ADAPTATION_RULES §1-2 implementation",
    }


async def extract_proxy_priors(ctx: Any, **kwargs: Any) -> dict[str, Any]:
    """Proxy posterior extraction handler — stub."""
    return {
        "step_type": "extract_proxy_priors",
        "stub": True,
        "extraction_method": "posterior_mean_std",
        "todo": "Phase B B3 sprint — extract от trained model посредством ADR-003 pre-train+transfer",
    }
