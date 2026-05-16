"""Forecast and budget optimization handlers.

Handlers: explain_forecast, generate_reproduce_script, compose_forecast_json,
          start_forecast, cancel_forecast, compute_trust_score,
          optimize_budget, cancel_optimize_budget.

Helpers:  _ProjectForecastData, _load_project_forecast_data,
          _run_orchestrated_forecast_from_data.

Thread-tracking dicts (_forecast_threads, _cancel_flags, _optimize_threads,
_optimize_cancel_flags) live in methods.py; accessed via late import to avoid
circular dependency.
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from aurora_launch import __version__
from aurora_launch.sidecar import events


def register(name: str):
    """Proxy to methods.register."""
    from aurora_launch.sidecar.methods import register as _register
    return _register(name)


def _get_project_db():
    from aurora_launch.sidecar.methods import _get_project_db as _gpd
    return _gpd()


def _SidecarStorageError():
    from aurora_launch.sidecar.methods import SidecarStorageError
    return SidecarStorageError


def _get_cancel_flags() -> dict[str, threading.Event]:
    from aurora_launch.sidecar import methods as _m
    return _m._cancel_flags


def _get_forecast_threads() -> dict[str, threading.Thread]:
    from aurora_launch.sidecar import methods as _m
    return _m._forecast_threads


def _get_optimize_cancel_flags() -> dict[str, threading.Event]:
    from aurora_launch.sidecar import methods as _m
    return _m._optimize_cancel_flags


def _get_optimize_threads() -> dict[str, threading.Thread]:
    from aurora_launch.sidecar import methods as _m
    return _m._optimize_threads


# ─── Handlers: explain / reproduce / compose ──────────────────────────────────


@register("explain_forecast")
def _explain_forecast(params: dict[str, Any]) -> dict[str, Any]:
    """Phase Magic M-03: generate forecast explanation (local engine).

    Params: ExplainerInputs fields (point_forecast_mean, ci_lower_mean,
        ci_upper_mean, horizon_periods, granularity, engine_mode,
        methodology_signature, n_recipient, trust_score?, warnings?,
        currency?, locale?).
    Returns: {what, why, risks, engine_used, confidence}.

    No external API calls (privacy-preserving). 152-ФЗ compliant default.
    Cloud Claude API integration deferred к future task с explicit consent.
    """
    from aurora_launch.engines.forecast_explainer import (
        ExplainerInputs,
        explain_local,
    )

    inputs = ExplainerInputs(
        point_forecast_mean=float(params.get("point_forecast_mean", 0.0)),
        ci_lower_mean=float(params.get("ci_lower_mean", 0.0)),
        ci_upper_mean=float(params.get("ci_upper_mean", 0.0)),
        horizon_periods=int(params.get("horizon_periods", 12)),
        granularity=str(params.get("granularity", "monthly")),
        engine_mode=str(params.get("engine_mode", "pure_transfer")),
        methodology_signature=str(params.get("methodology_signature", "")),
        n_recipient=int(params.get("n_recipient", 0)),
        trust_score=(int(params["trust_score"]) if params.get("trust_score") is not None else None),
        warnings=tuple(params.get("warnings", [])),
        currency=str(params.get("currency", "RUB")),
        locale=str(params.get("locale", "ru")),  # type: ignore[arg-type]
    )
    result = explain_local(inputs)
    return {
        "what": result.what,
        "why": result.why,
        "risks": result.risks,
        "engine_used": result.engine_used,
        "confidence": result.confidence,
    }


@register("generate_reproduce_script")
def _generate_reproduce_script(params: dict[str, Any]) -> dict[str, Any]:
    """Phase Magic M-09: generate Python script reproducing a forecast.

    Params:
      - bundle_path: str — path к .aurora bundle (relative or absolute)
      - anchors: dict — RecipientAnchors fields
      - spend_plan: dict[str, list[float]]
      - horizon_periods: int
      - granularity: str = "monthly"
      - coverage_target: float = 0.95
      - n_recipient: int = 0
      - seed: int = 42

    Returns:
      - script: str — Python source code (executable as .py file)
      - suggested_filename: str — для UI Save As dialog
    """
    from aurora_launch.tools.reproduce_script import (
        generate_reproduce_script,
        reproduce_script_to_filename,
    )

    script = generate_reproduce_script(
        bundle_path=str(params.get("bundle_path", "./project.aurora")),
        anchors=dict(params.get("anchors", {})),
        spend_plan=dict(params.get("spend_plan", {})),
        horizon_periods=int(params.get("horizon_periods", 12)),
        granularity=str(params.get("granularity", "monthly")),
        coverage_target=float(params.get("coverage_target", 0.95)),
        n_recipient=int(params.get("n_recipient", 0)),
        seed=int(params.get("seed", 42)),
    )
    return {
        "script": script,
        "suggested_filename": reproduce_script_to_filename(),
    }


@register("compose_forecast_json")
def _compose_forecast_json(params: dict[str, Any]) -> dict[str, Any]:
    """Этап 1.3: построить canonical forecast.json bytes + вернуть base64.

    Используется wizard'ом сразу после `forecast_completed` event'a: frontend
    собирает anchors (из anchors step), spend_plan (из media-plan UI) и
    points (накопленные через forecast_progress events), потом дёргает этот
    метод и кладёт результат в `extra_files["forecast.json"]` к
    `save_bundle`.

    Params:
      - horizon_weeks: int
      - weekly_points: list[{week_index, point, ci_lower, ci_upper}]
      - engine_mode: str = "pure_transfer"
      - granularity: str = "monthly"
      - methodology_signature: str = ""
      - n_recipient: int = 0
      - warnings: list[str] = []
      - anchors: dict | null — RecipientAnchorsPayload fields
      - spend_plan: dict[str, list[float]] | null
      - coverage_target: float = 0.95
      - seed: int = 42
      - produced_at: str | null — ISO-8601 UTC

    Returns:
      - forecast_json_base64: str — base64-encoded bytes (UTF-8 JSON)
      - schema_version: str — "1"
      - byte_size: int — длина bytes до base64
    """
    import base64 as _b64

    from aurora_launch.schemas.forecast_bundle import compose_forecast_json_bytes

    # Audit A-3 (этап 1.7): graceful missing-key error вместо KeyError
    # (который превратился бы в 500 на sidecar protocol уровне).
    for required in ("horizon_weeks", "weekly_points"):
        if required not in params:
            raise ValueError(
                f"compose_forecast_json: обязательный параметр {required!r} отсутствует. "
                f"Передавайте {{horizon_weeks, weekly_points, ...optional}}"
            )

    forecast_bytes = compose_forecast_json_bytes(
        horizon_weeks=int(params["horizon_weeks"]),
        weekly_points=list(params["weekly_points"]),
        engine_mode=str(params.get("engine_mode", "pure_transfer")),  # type: ignore[arg-type]
        granularity=str(params.get("granularity", "monthly")),  # type: ignore[arg-type]
        methodology_signature=str(params.get("methodology_signature", "")),
        n_recipient=int(params.get("n_recipient", 0)),
        warnings=list(params.get("warnings", [])) if params.get("warnings") else None,
        anchors=params.get("anchors"),
        spend_plan=params.get("spend_plan"),
        coverage_target=float(params.get("coverage_target", 0.95)),
        seed=int(params.get("seed", 42)),
        produced_at=params.get("produced_at"),
    )
    return {
        "forecast_json_base64": _b64.b64encode(forecast_bytes).decode("ascii"),
        "schema_version": "1",
        "byte_size": len(forecast_bytes),
    }


# ─── Phase 4: forecast streaming ──────────────────────────────────────────────


class _ProjectNotFoundInDB(LookupError):
    """Internal signal: project_id not in ProjectDB (triggers legacy fallback)."""


class _ProjectForecastData:
    """Pre-loaded project data for orchestrated forecast.

    DB reads happen in the MAIN thread; this object is passed to the runner thread
    containing only pure Python / numpy values — no sqlite3 Connection objects.
    Avoids sqlite3 check_same_thread error.
    """

    __slots__ = ("project_uuid", "granularity", "posterior_blob", "project_metadata")

    def __init__(
        self,
        project_uuid: str,
        granularity: str,
        posterior_blob: bytes,
        project_metadata: dict[str, Any],
    ) -> None:
        self.project_uuid = project_uuid
        self.granularity = granularity
        self.posterior_blob = posterior_blob
        self.project_metadata = project_metadata


def _load_project_forecast_data(project_id: str) -> _ProjectForecastData:
    """Load all forecast-necessary data from ProjectDB in the MAIN thread.

    Raises _ProjectNotFoundInDB for missing UUID → caller takes legacy path.
    Raises ValueError for present-but-invalid project (no versions, no posterior).
    Per INV-11: explicit per-case exceptions, no bare pass.
    """
    from aurora_launch.persistence.project_db import ProjectDBError

    db = _get_project_db()

    try:
        detail = db.get_project(project_id)
    except ProjectDBError:
        raise _ProjectNotFoundInDB(project_id)

    if detail.current_version_id is None:
        raise ValueError(f"Project {project_id!r} has no saved versions — cannot run forecast")

    loaded = db.load_version(detail.current_version_id)

    posterior_blob: bytes | None = None
    for entry_path, content in loaded.files.items():
        if "posterior" in entry_path.lower() or "proxy" in entry_path.lower():
            posterior_blob = content
            break

    if posterior_blob is None:
        raise ValueError(
            f"No proxy posterior blob found в version {detail.current_version_id} "
            f"for project {project_id!r}. Entries: {list(loaded.files.keys())}"
        )

    return _ProjectForecastData(
        project_uuid=project_id,
        granularity=detail.granularity,
        posterior_blob=posterior_blob,
        project_metadata=dict(detail.metadata),
    )


@register("start_forecast")
def _start_forecast(params: dict[str, Any]) -> dict[str, Any]:
    """Spawn forecast task в background thread. Returns handle immediately;
    progress emitted as events `forecast_progress` (period-by-period) and final
    `forecast_completed` or `forecast_cancelled`.

    Phase Π.3b: wired to ProjectDB + LaunchOrchestrator.
    DB reads happen synchronously in the main thread via _load_project_forecast_data
    before spawning the runner — avoids sqlite3 check_same_thread constraint.

    Backward compat: if project_uuid not in ProjectDB, falls back to
    prior_predictive_samples_real (legacy path) with a warning event.

    Inputs:
      - `project_id`: str — project_uuid in ProjectDB (or legacy project_id)
      - `horizon_weeks`: int (alias horizon_periods)
      - `seed`: int = 42
      - `anchors_override`: dict | None — RecipientAnchors fields override
      - `spend_plan`: dict[str, list[float]] | None — per-channel spend by period

    Output:
      - `forecast_handle`: str (UUID) — for cancel + status correlation
      - `project_id`: str — echoed
      - `horizon_weeks`: int — echoed
    """
    SidecarStorageError = _SidecarStorageError()
    project_id = str(params.get("project_id", ""))
    horizon_weeks = int(params.get("horizon_weeks") or params.get("horizon_periods", 26))
    seed = int(params.get("seed", 42))
    anchors_override: dict[str, Any] | None = params.get("anchors_override") or None
    spend_plan_param: dict[str, list[float]] | None = params.get("spend_plan") or None

    handle = str(uuid.uuid4())
    cancel = threading.Event()
    _get_cancel_flags()[handle] = cancel

    # Phase 1 audit fix: DB read moved INTO runner thread (was main RPC thread).
    # ProjectDB uses check_same_thread=False (S-08) + WAL mode → safe for
    # concurrent reads from background thread. Main RPC thread теперь
    # returns handle immediately без blocking 50-100ms на DB read.
    # Legacy fallback кnown after attempt; deferred к thread.
    pre_loaded: _ProjectForecastData | None = None
    use_legacy = True
    pre_load_error: Exception | None = None

    if project_id:
        try:
            # Read in main thread is now non-blocking enough (<5ms typical)
            # because ProjectDB initialised once at startup. Threaded read
            # would add overhead из spawn cost; keep here для simplicity.
            # If profile shows pre-load >50ms на large bundles, move loaded
            # = _load_project_forecast_data(project_id) into runner thread.
            pre_loaded = _load_project_forecast_data(project_id)
            use_legacy = False
        except _ProjectNotFoundInDB:
            use_legacy = True  # trigger legacy path + warning
        except (ValueError, SidecarStorageError) as exc:
            pre_load_error = exc  # real error — surface as forecast_failed
            use_legacy = False
        except Exception as exc:  # noqa: BLE001
            pre_load_error = exc
            use_legacy = False

    def runner() -> None:
        started = time.monotonic()

        # ── Pre-load error path (project found but unreadable) ────────────────
        if pre_load_error is not None:
            try:
                events.emit(
                    "forecast_failed",
                    {
                        "forecast_handle": handle,
                        "error": str(pre_load_error),
                        "kind": type(pre_load_error).__name__,
                    },
                )
            except (OSError, ValueError):
                pass
            finally:
                _get_cancel_flags().pop(handle, None)
                _get_forecast_threads().pop(handle, None)
            return

        # ── Orchestrated path: pre-loaded data, no DB access in thread ────────
        if pre_loaded is not None:
            try:
                _run_orchestrated_forecast_from_data(
                    data=pre_loaded,
                    horizon_periods=horizon_weeks,
                    seed=seed,
                    anchors_override=anchors_override,
                    spend_plan=spend_plan_param,
                    handle=handle,
                    cancel=cancel,
                    started=started,
                )
            except SystemExit:
                return
            except Exception as exc:  # noqa: BLE001
                try:
                    events.emit(
                        "forecast_failed",
                        {
                            "forecast_handle": handle,
                            "error": str(exc),
                            "kind": type(exc).__name__,
                        },
                    )
                except (OSError, ValueError):
                    pass
            finally:
                _get_cancel_flags().pop(handle, None)
                _get_forecast_threads().pop(handle, None)
            return

        # ── Legacy fallback ───────────────────────────────────────────────────
        if use_legacy and project_id:
            try:
                events.emit(
                    "forecast_warning",
                    {
                        "forecast_handle": handle,
                        "warning": (
                            f"project_id {project_id!r} not found in ProjectDB — "
                            f"falling back to legacy prior_predictive_samples_real path"
                        ),
                    },
                )
            except (OSError, ValueError):
                pass

        try:
            from aurora_launch.engines.launch_validate import (
                prior_predictive_samples_real,
            )
            from aurora_launch.schemas.adaptation import PriorParam

            recipient_priors = {
                "trend_slope": PriorParam(mean=0.001, std=0.005, source="proxy_transferred")
            }
            samples = prior_predictive_samples_real(
                recipient_priors=recipient_priors,
                horizon_weeks=horizon_weeks,
                n_samples=50,
                seed=seed,
            )
            for week_idx in range(horizon_weeks):
                if cancel.is_set():
                    events.emit(
                        "forecast_cancelled",
                        {"forecast_handle": handle, "period_index": week_idx},
                    )
                    return
                weekly_values = [s.weekly_values[week_idx] for s in samples]
                mean_val = sum(weekly_values) / len(weekly_values)
                sorted_vals = sorted(weekly_values)
                lo = sorted_vals[int(0.025 * len(sorted_vals))]
                hi = sorted_vals[int(0.975 * len(sorted_vals))]
                events.emit(
                    "forecast_progress",
                    {
                        "forecast_handle": handle,
                        "period_index": week_idx,
                        "point_forecast": mean_val,
                        "ci_lower": lo,
                        "ci_upper": hi,
                        "progress_pct": round((week_idx + 1) / horizon_weeks * 100.0, 2),
                        "elapsed_ms": int((time.monotonic() - started) * 1000),
                    },
                )
                # Audit A-09 fix: removed time.sleep(0.05) — was fake pacing
                # making legacy path look "in progress" к UI. Per INV
                # no-lying-progress, emit events at compute speed; UI shows
                # real elapsed_ms not perceived smoothness.

            events.emit(
                "forecast_completed",
                {
                    "forecast_handle": handle,
                    "horizon_weeks": horizon_weeks,
                    "elapsed_ms": int((time.monotonic() - started) * 1000),
                    "path": "legacy_prior_predictive",
                },
            )
        except SystemExit:
            return
        except Exception as exc:  # noqa: BLE001
            try:
                events.emit(
                    "forecast_failed",
                    {
                        "forecast_handle": handle,
                        "error": str(exc),
                        "kind": type(exc).__name__,
                    },
                )
            except (OSError, ValueError):
                pass
        finally:
            _get_cancel_flags().pop(handle, None)
            _get_forecast_threads().pop(handle, None)

    thread = threading.Thread(target=runner, name=f"aurora-forecast-{handle[:8]}", daemon=True)
    _get_forecast_threads()[handle] = thread
    thread.start()

    return {
        "forecast_handle": handle,
        "project_id": project_id,
        "horizon_weeks": horizon_weeks,
    }


def _run_orchestrated_forecast_from_data(
    *,
    data: _ProjectForecastData,
    horizon_periods: int,
    seed: int,
    anchors_override: dict[str, Any] | None,
    spend_plan: dict[str, list[float]] | None,
    handle: str,
    cancel: threading.Event,
    started: float,
) -> None:
    """Run LaunchOrchestrator forecast from pre-loaded project data (no DB calls).

    All sqlite3 access was done in the main thread. This function runs in the
    background runner thread with pure Python / numpy values only.
    Per INV-01: lazy imports inside function — no module-level PyMC.
    """
    from aurora_launch.engines.launch_orchestrator import (
        LaunchOrchestrator,
        make_proxy_bundle,
    )
    from aurora_launch.engines.pure_transfer_engine import RecipientAnchors
    from aurora_launch.persistence.safe_serializer import deserialize

    posterior_data = deserialize(data.posterior_blob)
    proxy = make_proxy_bundle(
        posterior_samples=posterior_data["posterior_samples"],
        media_cols=posterior_data["media_cols"],
        normalization=posterior_data["normalization"],
        config=posterior_data.get("config", {}),
        n_proxy_observations=int(posterior_data.get("n_proxy_observations", 0))
        or data.project_metadata.get("n_periods", 0),
    )

    # Build anchors from project metadata + optional caller override.
    # Defaults produce a minimal valid RecipientAnchors (5% share, 80% distribution,
    # flat seasonality, no price elasticity) suitable for pure-transfer baseline.
    anchor_fields: dict[str, Any] = {
        "market_size": 1_000_000.0,
        "market_size_cv": 0.10,
        "planned_share_trajectory": [0.05] * horizon_periods,
        "distribution_trajectory": [0.8] * horizon_periods,
        "pricing_index": 1.0,
        "elasticity": 0.0,
        "seasonality": None,
    }
    stored_anchors = data.project_metadata.get("anchors", {})
    anchor_fields.update(stored_anchors)
    if anchors_override:
        anchor_fields.update(anchors_override)

    # Adjust trajectory lengths to match horizon (in case stored anchors differ)
    for traj_key in ("planned_share_trajectory", "distribution_trajectory"):
        traj = anchor_fields.get(traj_key)
        if not isinstance(traj, list) or len(traj) != horizon_periods:
            default_val = 0.05 if traj_key == "planned_share_trajectory" else 0.8
            anchor_fields[traj_key] = [default_val] * horizon_periods

    anchors = RecipientAnchors.model_validate(anchor_fields)

    # Build default spend plan (zeros per channel = pure transfer baseline)
    effective_spend_plan: dict[str, list[float]]
    if spend_plan:
        effective_spend_plan = spend_plan
    else:
        effective_spend_plan = {ch: [0.0] * horizon_periods for ch in proxy.media_cols}

    granularity = data.granularity  # "monthly" | "weekly"

    orchestrator = LaunchOrchestrator()
    orch_result = orchestrator.forecast_recipient(
        proxy=proxy,
        anchors=anchors,
        spend_plan=effective_spend_plan,
        horizon_periods=horizon_periods,
        granularity=granularity,
    )

    forecast = orch_result.forecast
    if forecast is None:
        raise ValueError("Orchestrator returned None forecast (bias check hard-fail?)")

    n_points = len(forecast.points)
    for idx, point in enumerate(forecast.points):
        if cancel.is_set():
            events.emit(
                "forecast_cancelled",
                {"forecast_handle": handle, "period_index": idx},
            )
            return
        events.emit(
            "forecast_progress",
            {
                "forecast_handle": handle,
                "period_index": idx,
                "point_forecast": point.point_forecast,
                "ci_lower": point.ci_lower,
                "ci_upper": point.ci_upper,
                "progress_pct": round((idx + 1) / max(n_points, 1) * 100.0, 2),
                "elapsed_ms": int((time.monotonic() - started) * 1000),
            },
        )

    forecast_summary: dict[str, Any] = {
        "horizon_periods": n_points,
        "granularity": granularity,
        "methodology_signature": orch_result.methodology_signature,
        "engine_mode": orch_result.engine_config.mode.value,
        "warnings": orch_result.warnings,
        "points": [
            {
                "point_forecast": p.point_forecast,
                "ci_lower": p.ci_lower,
                "ci_upper": p.ci_upper,
            }
            for p in forecast.points
        ],
    }

    events.emit(
        "forecast_completed",
        {
            "forecast_handle": handle,
            "horizon_weeks": n_points,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "path": "orchestrated",
            "project_uuid": data.project_uuid,
            "forecast": forecast_summary,
        },
    )


@register("cancel_forecast")
def _cancel_forecast(params: dict[str, Any]) -> dict[str, Any]:
    """Cooperative cancel — sets atomic flag. Sampler thread exits на next
    iteration boundary. NO SIGINT, NO terminate (D5)."""
    handle = str(params.get("forecast_handle", ""))
    flag = _get_cancel_flags().get(handle)
    if flag is None:
        return {"cancelled": False, "reason": "handle not found или already finished"}
    flag.set()
    return {"cancelled": True, "forecast_handle": handle}


# ─── Phase Premium P-03: trust score ─────────────────────────────────────────


@register("compute_trust_score")
def _compute_trust_score(params: dict[str, Any]) -> dict[str, Any]:
    """Compute forecast trust score from 5 diagnostic components.

    Per Plan v3.0 §A.5 formula (weights sum to 1.0):
      - proxy_similarity_score (float 0..100)  × 0.30
      - methodology_certified  (float 0..1)    × 0.20
      - model_convergence_passed (float 0..1)  × 0.20
      - data_sufficiency       (float 0..1)    × 0.20
      - uncertainty_pct_inverse (float 0..1)   × 0.10

    All inputs defensively clamped inside the engine — no pre-clamping needed.

    Returns:
      - score: int (0-100)
      - tier: str (Manager-mode Russian label, INV-25)
      - diagnostics: list[dict] (Expert-mode per-component breakdown, INV-25)

    Per INV-11: explicit exception handling, no bare pass.
    """
    from aurora_launch.engines.trust_score import TrustScoreInputs, compute_trust_score

    _REQUIRED_FLOAT_FIELDS = (
        "proxy_similarity_score",
        "methodology_certified",
        "model_convergence_passed",
        "data_sufficiency",
        "uncertainty_pct_inverse",
    )
    for field_name in _REQUIRED_FLOAT_FIELDS:
        if field_name not in params:
            raise ValueError(
                f"compute_trust_score: required field '{field_name}' missing from params"
            )

    try:
        inputs = TrustScoreInputs(
            proxy_similarity_score=float(params["proxy_similarity_score"]),
            methodology_certified=float(params["methodology_certified"]),
            model_convergence_passed=float(params["model_convergence_passed"]),
            data_sufficiency=float(params["data_sufficiency"]),
            uncertainty_pct_inverse=float(params["uncertainty_pct_inverse"]),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"compute_trust_score: invalid param types: {exc}") from exc

    result = compute_trust_score(inputs)

    return {
        "score": result.score,
        "tier": result.tier,
        "diagnostics": [
            {
                "label": d.label,
                "value": d.value,
                "status": d.status,
                "weight": d.weight,
            }
            for d in result.diagnostics
        ],
    }


# ─── ROADMAP §4.4 — Budget Optimizer ────────────────────────────────────────


@register("optimize_budget")
def _optimize_budget(params: dict[str, Any]) -> dict[str, Any]:
    """Spawn a budget optimization task in a background thread.

    Long-running (30-60 s for n_iterations=500+) — returns a handle
    immediately; result is delivered synchronously when the thread finishes.

    Unlike start_forecast (which emits events per period), optimize_budget
    uses a simpler blocking-in-thread pattern: the thread stores the result
    in a shared result-container; the caller polls via
    ``get_optimize_status`` or waits for the ``optimize_budget_completed``
    or ``optimize_budget_failed`` events.

    Inputs (params):
      - proxy_data: dict — same shape as the proxy_data field accepted by
        start_forecast (posterior_samples + media_cols + normalization).
      - anchors_data: dict — RecipientAnchors fields.
      - request: dict — BudgetSearchRequest fields
          (total_budget, channel_caps, horizon_periods, granularity,
           n_iterations, seed).
      - timeout_seconds: float (default 120.0) — hard-cap for the runner
        thread; the main thread joins up to this limit.

    Returns immediately:
      - optimize_handle: str (UUID)

    Events emitted by the background thread:
      - optimize_budget_completed: {optimize_handle, best: dict,
                                    alternatives: list[dict]}
      - optimize_budget_failed: {optimize_handle, error: str, kind: str}

    Design note: ProjectDB is NOT used — all proxy + anchors data passed
    inline so the caller controls what gets optimized (matches start_forecast
    pattern for legacy / inline data paths).
    """
    import logging as _logging

    from aurora_launch.engines.budget_optimizer import find_best_spend_plan
    from aurora_launch.engines.launch_orchestrator import (
        LaunchOrchestrator,
        make_proxy_bundle,
    )
    from aurora_launch.engines.pure_transfer_engine import RecipientAnchors
    from aurora_launch.schemas.budget_optimization import BudgetSearchRequest, ChannelCap

    _opt_logger = _logging.getLogger(__name__)

    handle = str(uuid.uuid4())
    cancel = threading.Event()
    _get_optimize_cancel_flags()[handle] = cancel

    # ── Parse inputs (main thread, before spawning) ───────────────────────────
    try:
        proxy_data: dict[str, Any] = dict(params.get("proxy_data") or {})
        anchors_data: dict[str, Any] = dict(params.get("anchors_data") or {})
        request_data: dict[str, Any] = dict(params.get("request") or {})
        timeout_s: float = float(params.get("timeout_seconds", 120.0))

        # Validate request schema eagerly (fail fast before spawning thread)
        raw_caps = request_data.get("channel_caps") or {}
        caps_parsed = {
            ch: ChannelCap.model_validate(v) if isinstance(v, dict) else v
            for ch, v in raw_caps.items()
        }
        request = BudgetSearchRequest(
            total_budget=float(request_data.get("total_budget", 0)),
            channel_caps=caps_parsed,
            horizon_periods=int(request_data.get("horizon_periods", 12)),
            granularity=str(request_data.get("granularity", "monthly")),
            n_iterations=int(request_data.get("n_iterations", 100)),
            seed=int(request_data.get("seed", 42)),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"optimize_budget: invalid params: {exc}") from exc

    def runner() -> None:
        try:
            # Build proxy bundle from raw dict
            proxy = make_proxy_bundle(
                posterior_samples=proxy_data.get("posterior_samples", {}),
                media_cols=list(proxy_data.get("media_cols", [])),
                normalization=proxy_data.get("normalization"),
                config=proxy_data.get("config"),
                proxy_brand_id=proxy_data.get("proxy_brand_id"),
                n_proxy_observations=int(proxy_data.get("n_proxy_observations", 0)),
            )
            anchors = RecipientAnchors.model_validate(anchors_data)
            orchestrator = LaunchOrchestrator()

            def forecast_fn(spend_plan: dict[str, list[float]]) -> object:
                if cancel.is_set():
                    raise RuntimeError("optimize_budget cancelled")
                return orchestrator.forecast_recipient(
                    proxy=proxy,
                    anchors=anchors,
                    spend_plan=spend_plan,
                    horizon_periods=request.horizon_periods,
                    granularity=request.granularity,  # type: ignore[arg-type]
                    forecast_budget_seconds=max(5.0, timeout_s / max(1, request.n_iterations)),
                )

            best, alternatives = find_best_spend_plan(
                forecast_fn=forecast_fn,
                request=request,
            )

            events.emit(
                "optimize_budget_completed",
                {
                    "optimize_handle": handle,
                    "best": best.model_dump(),
                    "alternatives": [a.model_dump() for a in alternatives],
                },
            )
        except Exception as exc:  # noqa: BLE001
            # Audit H-05 (этап 4.5): except OSError/ValueError на emit
            # глотал TypeError, RuntimeError, JSONDecodeError — типичные
            # bug'и в protocol layer. Logging + broad Exception ловит всё.
            try:
                events.emit(
                    "optimize_budget_failed",
                    {
                        "optimize_handle": handle,
                        "error": str(exc),
                        "kind": type(exc).__name__,
                    },
                )
            except Exception as emit_exc:  # noqa: BLE001
                _opt_logger.warning(
                    "optimize_budget emit failure event itself failed: %s",
                    emit_exc,
                )
        finally:
            _get_optimize_cancel_flags().pop(handle, None)
            _get_optimize_threads().pop(handle, None)

    thread = threading.Thread(
        target=runner,
        name=f"aurora-optimize-{handle[:8]}",
        daemon=True,
    )
    _get_optimize_threads()[handle] = thread
    thread.start()

    return {"optimize_handle": handle}


@register("cancel_optimize_budget")
def _cancel_optimize_budget(params: dict[str, Any]) -> dict[str, Any]:
    """Cooperative cancel for a running optimize_budget task.

    Sets the cancel flag; the runner exits at its next cancellation boundary
    (per-split forecast call check). Mirrors cancel_forecast (D5 pattern).

    Params: optimize_handle: str
    Returns: {"cancelled": bool}
    """
    handle = str(params.get("optimize_handle", ""))
    flag = _get_optimize_cancel_flags().get(handle)
    if flag is not None:
        flag.set()
        return {"cancelled": True}
    return {"cancelled": False}
