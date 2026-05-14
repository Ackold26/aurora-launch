"""Trust score engine — compute_trust_score() for forecast confidence (P-03).

Per Plan v3.0 §A.5 formula:

    score = round(weighted_average(
        proxy_similarity_score * 0.30,   # 0..100 — Phase B similarity output
        methodology_certified * 20,      # 0/1 — Ed25519 chain valid?
        model_convergence_passed * 20,   # 0/1 — R̂ < 1.05 + ESS > 400 + 0 divergent
        data_sufficiency * 20,           # 0..1 — months_of_data / required_months, clamped
        uncertainty_pct_inverse * 10     # 0..1 — 1 - (median_ci_width / point_mean), clamped
    ))

Tier mapping (Manager-mode label, INV-25):
    90-100 → "Очень высокий"
    75-89  → "Высокий"
    60-74  → "Средний"
    40-59  → "Низкий"
    0-39   → "Не подтверждён"

Per INV-11: explicit narrow except clauses, no bare pass.
Per INV-25: output supports both Manager (tier label) and Expert (diagnostics).
No new dependencies — stdlib + math only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal


# ─── Types ────────────────────────────────────────────────────────────────────

DiagnosticStatus = Literal["good", "warn", "bad", "info"]


@dataclass(frozen=True)
class Diagnostic:
    """Single per-component diagnostic record for Expert mode (INV-25)."""

    label: str
    value: str
    status: DiagnosticStatus
    weight: float  # fractional weight applied (0..1) — informs Expert drilldown


@dataclass(frozen=True)
class TrustScoreInputs:
    """Inputs to compute_trust_score().

    Fields
    ------
    proxy_similarity_score : float
        Phase B proxy similarity index.  0..100 scale.
        Negative values are clamped to 0; values > 100 clamped to 100.
    methodology_certified : float
        1.0 if Ed25519 certificate chain is valid + unrevoked, 0.0 otherwise.
        Intermediate values allowed for partial cert states (e.g. 0.5 = signed
        but revocation check skipped). Clamped 0..1.
    model_convergence_passed : float
        1.0 when R̂ < 1.05 AND ESS > 400 AND 0 divergent transitions.
        Partial credit: 0.5 when R̂ < 1.1 (marginal convergence).
        Clamped 0..1.
    data_sufficiency : float
        Ratio months_of_data / required_months_minimum (typically 12..24).
        Clamped 0..1 before weighting — caller should not pre-clamp.
    uncertainty_pct_inverse : float
        1 - (median_ci_width / point_mean_forecast).  Already 0..1 scale.
        If point_mean_forecast == 0 caller should pass 0.0 (worst-case).
        Clamped 0..1.
    """

    proxy_similarity_score: float
    methodology_certified: float
    model_convergence_passed: float
    data_sufficiency: float
    uncertainty_pct_inverse: float


@dataclass
class TrustScoreResult:
    """Output of compute_trust_score().

    Fields
    ------
    score : int
        0..100 integer trust score (rounded weighted average).
    tier : str
        Manager-mode label — human-readable verdict in Russian.
    diagnostics : list[Diagnostic]
        Per-component breakdown for Expert mode (INV-25 dual-mode UX).
    """

    score: int
    tier: str
    diagnostics: list[Diagnostic] = field(default_factory=list)


# ─── Weights ──────────────────────────────────────────────────────────────────

_W_SIMILARITY = 0.30
_W_CERT = 0.20
_W_CONVERGENCE = 0.20
_W_DATA = 0.20
_W_UNCERTAINTY = 0.10

# Sum must equal 1.0 — verified by assertion in compute_trust_score for safety.
_WEIGHT_SUM = _W_SIMILARITY + _W_CERT + _W_CONVERGENCE + _W_DATA + _W_UNCERTAINTY


# ─── Tier mapping ─────────────────────────────────────────────────────────────


def _score_to_tier(score: int) -> str:
    """Map integer score (0-100) to Manager-mode Russian label."""
    if score >= 90:
        return "Очень высокий"
    if score >= 75:
        return "Высокий"
    if score >= 60:
        return "Средний"
    if score >= 40:
        return "Низкий"
    return "Не подтверждён"


# ─── Diagnostic helpers ───────────────────────────────────────────────────────


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp value to [lo, hi]. NaN → lo (safe fallback)."""
    if math.isnan(value) or math.isinf(value):
        return lo
    return max(lo, min(hi, value))


def _similarity_diagnostic(raw: float, clamped: float, contribution: float) -> Diagnostic:
    """Build diagnostic record for proxy_similarity_score component."""
    pct = round(clamped, 1)
    if clamped >= 70.0:
        status: DiagnosticStatus = "good"
    elif clamped >= 50.0:
        status = "warn"
    else:
        status = "bad"
    return Diagnostic(
        label="Схожесть с прокси-данными",
        value=f"{pct:.1f} / 100  →  {contribution:.1f} pt",
        status=status,
        weight=_W_SIMILARITY,
    )


def _cert_diagnostic(raw: float, clamped: float, contribution: float) -> Diagnostic:
    """Build diagnostic record for methodology_certified component."""
    if clamped >= 1.0:
        status: DiagnosticStatus = "good"
        label_val = "Подтверждён (Ed25519 OK)"
    elif clamped > 0.0:
        status = "warn"
        label_val = f"Частично ({clamped:.2f})"
    else:
        status = "bad"
        label_val = "Не подтверждён"
    return Diagnostic(
        label="Сертификат методологии",
        value=f"{label_val}  →  {contribution:.1f} pt",
        status=status,
        weight=_W_CERT,
    )


def _convergence_diagnostic(raw: float, clamped: float, contribution: float) -> Diagnostic:
    """Build diagnostic record for model_convergence_passed component."""
    if clamped >= 1.0:
        status: DiagnosticStatus = "good"
        label_val = "Сошлось (R̂ < 1.05, ESS > 400)"
    elif clamped >= 0.5:
        status = "warn"
        label_val = "Частично (R̂ < 1.10)"
    else:
        status = "bad"
        label_val = "Не сошлось"
    return Diagnostic(
        label="Сходимость модели",
        value=f"{label_val}  →  {contribution:.1f} pt",
        status=status,
        weight=_W_CONVERGENCE,
    )


def _data_diagnostic(raw: float, clamped: float, contribution: float) -> Diagnostic:
    """Build diagnostic record for data_sufficiency component."""
    pct = round(clamped * 100.0, 1)
    if clamped >= 1.0:
        status: DiagnosticStatus = "good"
    elif clamped >= 0.67:
        status = "warn"
    else:
        status = "bad"
    return Diagnostic(
        label="Достаточность данных",
        value=f"{pct:.1f}% от минимума  →  {contribution:.1f} pt",
        status=status,
        weight=_W_DATA,
    )


def _uncertainty_diagnostic(raw: float, clamped: float, contribution: float) -> Diagnostic:
    """Build diagnostic record for uncertainty_pct_inverse component."""
    pct = round(clamped * 100.0, 1)
    if clamped >= 0.75:
        status: DiagnosticStatus = "good"
    elif clamped >= 0.50:
        status = "warn"
    else:
        status = "bad"
    return Diagnostic(
        label="Точность прогноза (ширина ДИ)",
        value=f"Инверсия {pct:.1f}%  →  {contribution:.1f} pt",
        status=status,
        weight=_W_UNCERTAINTY,
    )


# ─── Public API ───────────────────────────────────────────────────────────────


def compute_trust_score(inputs: TrustScoreInputs) -> TrustScoreResult:
    """Compute trust score from structured inputs.

    Applies defensive clamping before weighting — callers need not pre-clamp.
    Returns score 0-100 + tier label (Manager) + diagnostics list (Expert).

    Raises
    ------
    TypeError
        If inputs is not a TrustScoreInputs instance.
    """
    if not isinstance(inputs, TrustScoreInputs):
        raise TypeError(
            f"inputs must be TrustScoreInputs, got {type(inputs).__name__}"
        )

    # Safety invariant — weight sum must equal 1.0 (catches future edits).
    assert math.isclose(_WEIGHT_SUM, 1.0, abs_tol=1e-9), (
        f"Trust score weights do not sum to 1.0: {_WEIGHT_SUM}"
    )

    # ── Defensive clamping ────────────────────────────────────────────────────
    # proxy_similarity_score is 0..100 scale; others are 0..1.
    sim_clamped = _clamp(inputs.proxy_similarity_score, 0.0, 100.0)
    cert_clamped = _clamp(inputs.methodology_certified)
    conv_clamped = _clamp(inputs.model_convergence_passed)
    data_clamped = _clamp(inputs.data_sufficiency)
    unc_clamped = _clamp(inputs.uncertainty_pct_inverse)

    # ── Weighted contributions ─────────────────────────────────────────────────
    # similarity is 0..100 * 0.30 → up to 30 pts directly
    # others are 0..1 * weight * 100 → scale to point space
    c_sim = sim_clamped * _W_SIMILARITY           # max 30.0
    c_cert = cert_clamped * _W_CERT * 100.0       # max 20.0
    c_conv = conv_clamped * _W_CONVERGENCE * 100.0  # max 20.0
    c_data = data_clamped * _W_DATA * 100.0        # max 20.0
    c_unc = unc_clamped * _W_UNCERTAINTY * 100.0   # max 10.0

    raw_score = c_sim + c_cert + c_conv + c_data + c_unc
    score = int(round(raw_score))
    # Final clamp guards against float rounding at boundaries (99.999... → 100)
    score = max(0, min(100, score))

    tier = _score_to_tier(score)

    diagnostics: list[Diagnostic] = [
        _similarity_diagnostic(inputs.proxy_similarity_score, sim_clamped, c_sim),
        _cert_diagnostic(inputs.methodology_certified, cert_clamped, c_cert),
        _convergence_diagnostic(inputs.model_convergence_passed, conv_clamped, c_conv),
        _data_diagnostic(inputs.data_sufficiency, data_clamped, c_data),
        _uncertainty_diagnostic(inputs.uncertainty_pct_inverse, unc_clamped, c_unc),
    ]

    return TrustScoreResult(score=score, tier=tier, diagnostics=diagnostics)
