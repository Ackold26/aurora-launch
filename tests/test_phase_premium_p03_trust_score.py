"""Phase Premium P-03 — compute_trust_score() unit tests.

Coverage:
1.  Perfect inputs → score 100, tier "Очень высокий"
2.  Zero inputs → score 0, tier "Не подтверждён"
3.  Similarity contribution weight correctness (30 pts max)
4.  Certification contribution weight correctness (20 pts max)
5.  Convergence contribution weight correctness (20 pts max)
6.  Data sufficiency contribution weight correctness (20 pts max)
7.  Uncertainty inverse contribution weight correctness (10 pts max)
8.  Tier boundary: score 89 → "Высокий" (not "Очень высокий")
9.  Tier boundary: score 90 → "Очень высокий"
10. Tier boundary: score 59 → "Низкий", score 60 → "Средний"
11. Tier boundary: score 39 → "Не подтверждён", score 40 → "Низкий"
12. Negative input clamping: similarity -50 → contributes 0, not negative
13. Over-100 similarity clamped: similarity 200 → same as 100 (30 pts)
14. Diagnostic count matches component count (5 diagnostics always)
15. Diagnostic status good/warn/bad classification correctness
16. IPC handler dispatch: compute_trust_score method registered + returns dict
17. IPC handler schema validation: missing field raises ValueError

Per INV-11: explicit exception testing.
Per INV-25: dual-mode output verified (tier + diagnostics).
"""

from __future__ import annotations

import math
import pytest

from aurora_launch.engines.trust_score import (
    TrustScoreInputs,
    TrustScoreResult,
    compute_trust_score,
)


# ─── Helper ───────────────────────────────────────────────────────────────────


def _inputs(
    sim: float = 100.0,
    cert: float = 1.0,
    conv: float = 1.0,
    data: float = 1.0,
    unc: float = 1.0,
) -> TrustScoreInputs:
    return TrustScoreInputs(
        proxy_similarity_score=sim,
        methodology_certified=cert,
        model_convergence_passed=conv,
        data_sufficiency=data,
        uncertainty_pct_inverse=unc,
    )


# ─── Test 1: Perfect inputs ────────────────────────────────────────────────────


def test_perfect_inputs_score_100() -> None:
    """All components at maximum → score == 100, tier correct."""
    result = compute_trust_score(_inputs())
    assert isinstance(result, TrustScoreResult)
    assert result.score == 100
    assert result.tier == "Очень высокий"


# ─── Test 2: Zero inputs ──────────────────────────────────────────────────────


def test_zero_inputs_score_0() -> None:
    """All components zero → score == 0, tier 'Не подтверждён'."""
    result = compute_trust_score(_inputs(sim=0.0, cert=0.0, conv=0.0, data=0.0, unc=0.0))
    assert result.score == 0
    assert result.tier == "Не подтверждён"


# ─── Test 3: Similarity component weight ─────────────────────────────────────


def test_similarity_contribution_weight() -> None:
    """Similarity 100 with all others zero → score == 30 (weight 0.30)."""
    result = compute_trust_score(_inputs(sim=100.0, cert=0.0, conv=0.0, data=0.0, unc=0.0))
    assert result.score == 30


# ─── Test 4: Certification component weight ───────────────────────────────────


def test_certification_contribution_weight() -> None:
    """Certification 1.0 with all others zero → score == 20 (weight 0.20)."""
    result = compute_trust_score(_inputs(sim=0.0, cert=1.0, conv=0.0, data=0.0, unc=0.0))
    assert result.score == 20


# ─── Test 5: Convergence component weight ─────────────────────────────────────


def test_convergence_contribution_weight() -> None:
    """Convergence 1.0 with all others zero → score == 20 (weight 0.20)."""
    result = compute_trust_score(_inputs(sim=0.0, cert=0.0, conv=1.0, data=0.0, unc=0.0))
    assert result.score == 20


# ─── Test 6: Data sufficiency component weight ────────────────────────────────


def test_data_sufficiency_contribution_weight() -> None:
    """Data sufficiency 1.0 with all others zero → score == 20 (weight 0.20)."""
    result = compute_trust_score(_inputs(sim=0.0, cert=0.0, conv=0.0, data=1.0, unc=0.0))
    assert result.score == 20


# ─── Test 7: Uncertainty inverse component weight ─────────────────────────────


def test_uncertainty_contribution_weight() -> None:
    """Uncertainty inverse 1.0 with all others zero → score == 10 (weight 0.10)."""
    result = compute_trust_score(_inputs(sim=0.0, cert=0.0, conv=0.0, data=0.0, unc=1.0))
    assert result.score == 10


# ─── Test 8: Tier boundary 89 → "Высокий" ────────────────────────────────────


def test_tier_boundary_89_is_high() -> None:
    """Score 89 maps to 'Высокий', not 'Очень высокий'."""
    # sim=100→30, cert=1→20, conv=1→20, data=1→20 = 90; drop unc so score < 90.
    # sim=65→19.5, cert=1→20, conv=1→20, data=1→20, unc=0→0 ≈ 79.5 (Высокий).
    # For exact 89: we need 89 pts.
    # sim=63.33→19.0, cert=20, conv=20, data=20, unc=0 = 79. Try other combos.
    # Easiest: use direct score search: sim=96.67*0.30=29, cert=20,conv=20,data=20=89.
    result = compute_trust_score(_inputs(sim=96.67, cert=1.0, conv=1.0, data=1.0, unc=0.0))
    # 96.67 * 0.30 = 29.0, + 20 + 20 + 20 + 0 = 89.0 → round → 89
    assert result.score == 89
    assert result.tier == "Высокий"


# ─── Test 9: Tier boundary 90 → "Очень высокий" ──────────────────────────────


def test_tier_boundary_90_is_very_high() -> None:
    """Score 90 maps to 'Очень высокий'."""
    # sim=100→30, cert=1→20, conv=1→20, data=1→20, unc=0→0 = 90.
    result = compute_trust_score(_inputs(sim=100.0, cert=1.0, conv=1.0, data=1.0, unc=0.0))
    assert result.score == 90
    assert result.tier == "Очень высокий"


# ─── Test 10: Tier boundaries 59/60 ──────────────────────────────────────────


def test_tier_boundary_59_60() -> None:
    """Score 59 → 'Низкий'; score 60 → 'Средний'."""
    # 59: sim=63.33→19, cert=20, conv=20, data=0, unc=0 = 59
    r59 = compute_trust_score(_inputs(sim=63.33, cert=1.0, conv=1.0, data=0.0, unc=0.0))
    assert r59.score == 59
    assert r59.tier == "Низкий"

    # 60: sim=66.67→20, cert=20, conv=20, data=0, unc=0 = 60
    r60 = compute_trust_score(_inputs(sim=66.67, cert=1.0, conv=1.0, data=0.0, unc=0.0))
    assert r60.score == 60
    assert r60.tier == "Средний"


# ─── Test 11: Tier boundaries 39/40 ──────────────────────────────────────────


def test_tier_boundary_39_40() -> None:
    """Score 39 → 'Не подтверждён'; score 40 → 'Низкий'."""
    # 39: sim=63.33→19, cert=20, conv=0, data=0, unc=0 = 39
    r39 = compute_trust_score(_inputs(sim=63.33, cert=1.0, conv=0.0, data=0.0, unc=0.0))
    assert r39.score == 39
    assert r39.tier == "Не подтверждён"

    # 40: sim=66.67→20, cert=20, conv=0, data=0, unc=0 = 40
    r40 = compute_trust_score(_inputs(sim=66.67, cert=1.0, conv=0.0, data=0.0, unc=0.0))
    assert r40.score == 40
    assert r40.tier == "Низкий"


# ─── Test 12: Negative similarity clamped to 0 ───────────────────────────────


def test_negative_similarity_clamped_to_zero() -> None:
    """Negative proxy_similarity_score must not reduce total score (clamped to 0)."""
    result_neg = compute_trust_score(_inputs(sim=-50.0, cert=0.0, conv=0.0, data=0.0, unc=0.0))
    result_zero = compute_trust_score(_inputs(sim=0.0, cert=0.0, conv=0.0, data=0.0, unc=0.0))
    assert result_neg.score == result_zero.score == 0


# ─── Test 13: Over-100 similarity clamped to 100 ─────────────────────────────


def test_similarity_over_100_clamped() -> None:
    """proxy_similarity_score > 100 must yield same result as exactly 100."""
    result_200 = compute_trust_score(_inputs(sim=200.0, cert=0.0, conv=0.0, data=0.0, unc=0.0))
    result_100 = compute_trust_score(_inputs(sim=100.0, cert=0.0, conv=0.0, data=0.0, unc=0.0))
    assert result_200.score == result_100.score == 30


# ─── Test 14: 5 diagnostics always present ───────────────────────────────────


def test_diagnostic_count_always_5() -> None:
    """Result must always contain exactly 5 diagnostics (one per component)."""
    for inputs in [
        _inputs(),
        _inputs(sim=0, cert=0, conv=0, data=0, unc=0),
        _inputs(sim=50, cert=0.5, conv=0.5, data=0.5, unc=0.5),
    ]:
        result = compute_trust_score(inputs)
        assert len(result.diagnostics) == 5


# ─── Test 15: Diagnostic status classification ────────────────────────────────


def test_diagnostic_status_classification() -> None:
    """High similarity → 'good'; low similarity → 'bad'; mid → 'warn'."""
    # High similarity: sim=80, all others irrelevant for sim status
    r_high = compute_trust_score(_inputs(sim=80.0, cert=0.0, conv=0.0, data=0.0, unc=0.0))
    sim_diag = r_high.diagnostics[0]  # first diagnostic is similarity
    assert sim_diag.status == "good"

    # Mid similarity (50-69 → warn)
    r_mid = compute_trust_score(_inputs(sim=55.0, cert=0.0, conv=0.0, data=0.0, unc=0.0))
    sim_diag_mid = r_mid.diagnostics[0]
    assert sim_diag_mid.status == "warn"

    # Low similarity (< 50 → bad)
    r_low = compute_trust_score(_inputs(sim=30.0, cert=0.0, conv=0.0, data=0.0, unc=0.0))
    sim_diag_low = r_low.diagnostics[0]
    assert sim_diag_low.status == "bad"


# ─── Test 16: IPC handler dispatch ───────────────────────────────────────────


def test_ipc_handler_dispatch() -> None:
    """compute_trust_score IPC method is registered and returns valid dict."""
    from aurora_launch.sidecar.methods import dispatch

    result = dispatch(
        "compute_trust_score",
        {
            "proxy_similarity_score": 80.0,
            "methodology_certified": 1.0,
            "model_convergence_passed": 1.0,
            "data_sufficiency": 1.0,
            "uncertainty_pct_inverse": 0.8,
        },
    )

    assert isinstance(result, dict)
    assert "score" in result
    assert "tier" in result
    assert "diagnostics" in result
    assert isinstance(result["score"], int)
    assert 0 <= result["score"] <= 100
    assert isinstance(result["tier"], str)
    assert isinstance(result["diagnostics"], list)
    assert len(result["diagnostics"]) == 5


# ─── Test 17: IPC handler schema validation ───────────────────────────────────


def test_ipc_handler_missing_field_raises() -> None:
    """compute_trust_score IPC handler raises ValueError on missing required field."""
    from aurora_launch.sidecar.methods import dispatch

    with pytest.raises(ValueError, match="proxy_similarity_score"):
        dispatch(
            "compute_trust_score",
            {
                # proxy_similarity_score intentionally missing
                "methodology_certified": 1.0,
                "model_convergence_passed": 1.0,
                "data_sufficiency": 1.0,
                "uncertainty_pct_inverse": 1.0,
            },
        )
