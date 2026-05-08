"""Aurora Launch similarity calculator (B2 sprint deliverable).

STUB IMPLEMENTATION v0.1.2-b05 (M-A2-7 closure): provides handler entry-point
referenced by `aurora_launch_proxy_intake.v2.yaml` workflow. Returns
realistic-shape ProxyVerdict result для integration testing.

# TODO Phase B B2 sprint full implementation:
# - 6+2 dimension computation (per SIMILARITY_FRAMEWORK.md §1)
# - Per-category weight profile (SIMILARITY_FRAMEWORK §4)
# - Anti-pattern detection (leader_as_proxy_for_challenger etc.)
# - Multi-proxy aggregation с floor warnings
# - WASM Rust mirror для real-time UI updates
"""

from __future__ import annotations

from typing import Any


async def compute(ctx: Any, **kwargs: Any) -> dict[str, Any]:
    """Workflow handler entry point referenced by YAML as `compute`.

    Workflow handler signature: `(ctx, **params) -> dict | StepResult`.
    Stub returns medium-verdict to allow downstream pipeline progression.
    """
    multi_proxy_mode = kwargs.get("multi_proxy_mode", False)
    weights_profile = kwargs.get("weights_profile", "auto_per_category")

    # Stub returns realistic Medium verdict (S=0.72 typical mid-similarity)
    # для allow downstream steps to proceed in integration tests.
    # Real implementation (B2 sprint) computes from actual proxy + recipient data.
    return {
        "step_type": "proxy_select",
        "stub": True,
        "similarity_score": 0.72,
        "verdict": "Medium",
        "inflation_factor": 1.5,
        "multi_proxy_mode": multi_proxy_mode,
        "weights_profile_used": weights_profile,
        "anti_patterns_detected": [],
        "block_forecast": False,
        "todo": "Phase B B2 sprint — 6+2 dimensions + per-category weights + anti-pattern detector + WASM mirror",
    }
