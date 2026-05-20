"""Project-based trust score wrapper (Sprint 2 D1').

Closes spec acceptance contract ``invoke("compute_trust_score", {projectId})``:
caller passes a project id, wrapper reads ProjectDB state and computes all
five trust dimensions internally instead of requiring the frontend to
pre-compute them client-side.

Existing client-side wrapper (ForecastTab.svelte ``computeTrustForBundle``)
hardcodes ``model_convergence_passed=1`` and ``data_sufficiency=1.0`` because
the frontend has no view of those backend invariants. This module reads them
from the actual saved project state (proxy posterior blob, project metadata,
forecast bundle, methodology cert) and keeps a per-dimension provenance map
so the wizard can show which inputs came from real data vs defaults.

Architecture:

- Pure extraction layer: ``extract_*`` functions each take a structured input
  (project_metadata dict OR file bytes) and return ``(value, source)`` so
  no extractor depends on ProjectDB directly. Testable with dict fixtures.
- Wrapper layer: ``compute_trust_score_for_project`` orchestrates extractors,
  applies caller overrides, calls the canonical ``compute_trust_score``, and
  builds a ``ProjectTrustScoreResult`` carrying score + tier + diagnostics +
  per-dimension sources.

INV cross-refs:
- INV-25 — dual-mode UX: tier label for Manager, source tracking for Expert
- INV-37 — single source: if metadata exists, trust it; defaults only on miss
- INV-41 — handler whitelist applied at IPC boundary (methods_forecast.py)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from aurora_launch.engines.trust_score import (
    Diagnostic,
    TrustScoreInputs,
    TrustScoreResult,
    compute_trust_score,
)

__all__ = [
    "DimensionSource",
    "ProjectTrustScoreResult",
    "compute_trust_score_for_project",
    "extract_similarity_score",
    "extract_methodology_certified",
    "extract_model_convergence",
    "extract_data_sufficiency",
    "extract_uncertainty_inverse",
]

_log = logging.getLogger(__name__)

DimensionSource = Literal["project_state", "default", "override"]

# Required-minimum monthly data points for "full" data_sufficiency = 1.0
_DEFAULT_MIN_PERIODS_MONTHLY = 12
_DEFAULT_MIN_PERIODS_WEEKLY = 26  # ≈ half a year of weekly observations

# r_hat → convergence credit (Aurora MMM A/B 2026-05-18 thresholds)
_RHAT_FULL_THRESHOLD = 1.05  # ≤ this → 1.0 credit
_RHAT_PARTIAL_THRESHOLD = 1.10  # ≤ this → 0.5 partial


# ─── Result type ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ProjectTrustScoreResult:
    """Trust score plus per-dimension provenance.

    Fields
    ------
    score : int
        Trust score 0..100 (от canonical compute_trust_score).
    tier : str
        Manager-mode Russian label.
    diagnostics : list[Diagnostic]
        Expert-mode per-component breakdown (from compute_trust_score).
    sources : dict[str, DimensionSource]
        Per-dimension source tag for transparency:
        - ``project_state`` — extracted from saved project data
        - ``default``       — extracted attempt failed, default used
        - ``override``      — caller supplied a direct value
    source_notes : dict[str, str]
        One-line human-readable note per dimension (Expert mode info chip).
    """

    score: int
    tier: str
    diagnostics: list[Diagnostic]
    sources: dict[str, DimensionSource]
    source_notes: dict[str, str] = field(default_factory=dict)


# ─── Extractors ───────────────────────────────────────────────────────────────


def extract_similarity_score(
    project_metadata: dict[str, Any],
) -> tuple[float, str]:
    """Pull proxy_similarity_score (0..100) from project metadata.

    Project metadata may store either ``similarity_score`` (0..1 ratio per
    proxy schema) or ``proxy_similarity_score`` (0..100 already scaled).
    The 0..1 form is up-scaled to 0..100 for trust_score formula.

    Default: 0 (no proxy similarity computed → bad signal).
    """
    raw = project_metadata.get("proxy_similarity_score")
    if raw is not None:
        try:
            value = float(raw)
            if 0.0 <= value <= 100.0:
                return value, "из метаданных проекта (0..100 шкала)"
        except (TypeError, ValueError):
            pass

    raw_ratio = project_metadata.get("similarity_score")
    if raw_ratio is not None:
        try:
            ratio = float(raw_ratio)
            if 0.0 <= ratio <= 1.0:
                return ratio * 100.0, "из метаданных проекта (0..1 ratio × 100)"
        except (TypeError, ValueError):
            pass

    return 0.0, "значение по умолчанию — similarity не сохранён в проекте"


def extract_methodology_certified(
    files: dict[str, bytes],
) -> tuple[float, str]:
    """Check methodology_cert presence + parsed validity.

    Looks for `methodology_cert.json` (preferred for parsing) or `.pdf`
    (presence signals certificate was generated). Returns 1.0 if both signed
    + cert_version matches, 0.5 if cert artifact present but signature absent
    (cert pending sign-off), 0.0 if no cert artifact.

    Default: 0.0 — no cert means not certified.
    """
    cert_json = files.get("methodology_cert.json")
    if cert_json is not None:
        try:
            cert_data = json.loads(cert_json.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return 0.0, "сертификат повреждён — невозможно прочитать JSON"
        sig_local = cert_data.get("signature_local_ed25519")
        sig_aurora = cert_data.get("signature_aurora_ed25519")
        pending = cert_data.get("signature_aurora_pending", False)
        if sig_local and sig_aurora and not pending:
            return 1.0, "сертификат подписан (local + aurora ed25519)"
        if sig_local:
            return 0.5, "сертификат подписан локально, ожидает aurora подпись"
        return 0.5, "сертификат сгенерирован, подписи отсутствуют"

    cert_pdf = files.get("methodology_cert.pdf")
    if cert_pdf is not None:
        return 0.5, "PDF сертификата присутствует, JSON для проверки подписи нет"

    return 0.0, "сертификат методологии не сгенерирован"


def extract_model_convergence(
    files: dict[str, bytes],
) -> tuple[float, str]:
    """Read posterior_diagnostics R-hat from saved bundle.

    Looks for `models/diagnostics.json` (canonical Bayesian engine output)
    or `models/proxy_posterior_diagnostics.json` (alternative path).
    Decision tree (Aurora MMM 2026-05-18 thresholds):
      - r_hat_max ≤ 1.05 → 1.0 (fully converged)
      - r_hat_max ≤ 1.10 → 0.5 (marginal)
      - else            → 0.0 (failed)

    Default: 1.0 (assume converged когда diagnostics not saved — many
    Aurora Launch projects use deterministic proxy transfer without MCMC,
    в которой нет r_hat. Conservative-toward-trust default матчит current
    frontend hardcode `model_convergence_passed=1`).
    """
    for candidate in ("models/diagnostics.json", "models/proxy_posterior_diagnostics.json"):
        blob = files.get(candidate)
        if blob is None:
            continue
        try:
            diag = json.loads(blob.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        r_hat_max = diag.get("r_hat_max") or diag.get("r_hat") or diag.get("rhat_max")
        if r_hat_max is None:
            continue
        try:
            r_hat = float(r_hat_max)
        except (TypeError, ValueError):
            continue
        if r_hat <= _RHAT_FULL_THRESHOLD:
            return 1.0, f"R̂ = {r_hat:.3f} ≤ 1.05 (полная сходимость)"
        if r_hat <= _RHAT_PARTIAL_THRESHOLD:
            return 0.5, f"R̂ = {r_hat:.3f} ≤ 1.10 (частичная сходимость)"
        return 0.0, f"R̂ = {r_hat:.3f} > 1.10 (модель не сошлась)"

    return 1.0, "диагностика не сохранена (детерминированный proxy-transfer без MCMC)"


def extract_data_sufficiency(
    project_metadata: dict[str, Any],
    *,
    granularity_hint: str | None = None,
) -> tuple[float, str]:
    """Compute available_periods / required_minimum, clamped 0..1.

    Required minimum:
      - monthly: 12 periods (one year baseline)
      - weekly: 26 periods (half year of weekly observations)

    ``granularity_hint`` overrides project_metadata.granularity if supplied
    (callers могут не иметь доступа к full project record).

    Default: 1.0 (assume sufficient когда n_periods unknown — matches current
    frontend hardcode и avoids over-penalising early-stage projects).
    """
    n_periods_raw = project_metadata.get("n_periods")
    if n_periods_raw is None:
        return 1.0, "n_periods не сохранён в проекте — допущена достаточность"

    try:
        n_periods = int(n_periods_raw)
    except (TypeError, ValueError):
        return 1.0, f"n_periods имеет невалидный тип {type(n_periods_raw).__name__}"

    granularity = granularity_hint or str(project_metadata.get("granularity", "monthly"))
    if granularity == "weekly":
        required = _DEFAULT_MIN_PERIODS_WEEKLY
    else:
        required = _DEFAULT_MIN_PERIODS_MONTHLY

    if n_periods <= 0:
        return 0.0, f"n_periods = {n_periods} — данных нет"

    ratio = min(1.0, n_periods / required)
    return ratio, (
        f"{n_periods} наблюдений из требуемых {required} ({granularity}) → "
        f"{ratio * 100:.0f}% достаточности"
    )


def extract_uncertainty_inverse(
    files: dict[str, bytes],
) -> tuple[float, str]:
    """Compute 1 - mean(ci_width / point) from saved forecast.json.

    Reads `forecast.json` (compose_forecast_json output). Each weekly point
    contributes a relative CI width; mean is taken across all points,
    inverted to a "tightness" score 0..1.

    Default: 0.5 (mid-band — no forecast saved, uncertainty unknown).
    """
    blob = files.get("forecast.json")
    if blob is None:
        return 0.5, "forecast.json отсутствует — точность прогноза неизвестна"

    try:
        forecast = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 0.5, "forecast.json повреждён — точность не извлечена"

    points = forecast.get("weekly_points") or forecast.get("points") or []
    widths: list[float] = []
    for point in points:
        if not isinstance(point, dict):
            continue
        center = point.get("point_forecast") or point.get("point")
        lower = point.get("ci_lower")
        upper = point.get("ci_upper")
        if not (
            isinstance(center, (int, float))
            and isinstance(lower, (int, float))
            and isinstance(upper, (int, float))
        ):
            continue
        denom = max(abs(float(center)), 1.0)
        widths.append((float(upper) - float(lower)) / denom)

    if not widths:
        return 0.5, "forecast.json не содержит валидных точек с CI"

    mean_width = sum(widths) / len(widths)
    inverse = max(0.0, min(1.0, 1.0 - mean_width))
    return inverse, (
        f"средняя ширина ДИ {mean_width * 100:.0f}% → "
        f"точность {inverse * 100:.0f}% (по {len(widths)} периодам)"
    )


# ─── Wrapper ──────────────────────────────────────────────────────────────────


_DIMENSION_KEYS = (
    "proxy_similarity_score",
    "methodology_certified",
    "model_convergence_passed",
    "data_sufficiency",
    "uncertainty_pct_inverse",
)


def compute_trust_score_for_project(
    project_metadata: dict[str, Any],
    files: dict[str, bytes],
    *,
    granularity_hint: str | None = None,
    overrides: dict[str, float] | None = None,
) -> ProjectTrustScoreResult:
    """Compute trust score from project state.

    Pure function over structured inputs — testable без real ProjectDB.

    Parameters
    ----------
    project_metadata : dict[str, Any]
        ``ProjectDetail.metadata`` payload (json-decoded once already).
    files : dict[str, bytes]
        ``LoadedVersion.files`` — entry_path → raw bytes mapping.
    granularity_hint : str | None
        Override project_metadata.granularity для data_sufficiency calculation.
    overrides : dict[str, float] | None
        Direct overrides per dimension key. Keys: ``proxy_similarity_score``,
        ``methodology_certified``, ``model_convergence_passed``,
        ``data_sufficiency``, ``uncertainty_pct_inverse``. Values clamped
        downstream by ``compute_trust_score``.

    Returns
    -------
    ProjectTrustScoreResult
        Score + tier + diagnostics + per-dimension sources + notes.
    """
    overrides = overrides or {}

    sources: dict[str, DimensionSource] = {}
    notes: dict[str, str] = {}

    sim_value, sim_note = extract_similarity_score(project_metadata)
    cert_value, cert_note = extract_methodology_certified(files)
    conv_value, conv_note = extract_model_convergence(files)
    data_value, data_note = extract_data_sufficiency(
        project_metadata, granularity_hint=granularity_hint
    )
    unc_value, unc_note = extract_uncertainty_inverse(files)

    extracted = {
        "proxy_similarity_score": (sim_value, sim_note),
        "methodology_certified": (cert_value, cert_note),
        "model_convergence_passed": (conv_value, conv_note),
        "data_sufficiency": (data_value, data_note),
        "uncertainty_pct_inverse": (unc_value, unc_note),
    }

    final: dict[str, float] = {}
    for key in _DIMENSION_KEYS:
        if key in overrides:
            try:
                final[key] = float(overrides[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"compute_trust_score_for_project: override {key}={overrides[key]!r} "
                    f"not float-coercible: {exc}"
                ) from exc
            sources[key] = "override"
            notes[key] = f"переопределено вызывающим = {final[key]}"
            continue

        value, note = extracted[key]
        final[key] = value
        notes[key] = note
        # Mark "default" when extractor returned default-path note
        if (
            "по умолчанию" in note
            or "не сохранён" in note
            or "не извлечена" in note
            or "не сгенерирован" in note
            or "детерминированный proxy-transfer без MCMC" in note
            or "точность прогноза неизвестна" in note
            or "не содержит валидных точек" in note
            or "не сошёл" in note  # tolerate без typo edge
        ):
            sources[key] = "default"
        else:
            sources[key] = "project_state"

    inputs = TrustScoreInputs(
        proxy_similarity_score=final["proxy_similarity_score"],
        methodology_certified=final["methodology_certified"],
        model_convergence_passed=final["model_convergence_passed"],
        data_sufficiency=final["data_sufficiency"],
        uncertainty_pct_inverse=final["uncertainty_pct_inverse"],
    )
    base: TrustScoreResult = compute_trust_score(inputs)

    return ProjectTrustScoreResult(
        score=base.score,
        tier=base.tier,
        diagnostics=base.diagnostics,
        sources=sources,
        source_notes=notes,
    )
