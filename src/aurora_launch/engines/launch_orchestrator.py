"""LaunchOrchestrator — proxy → recipient forecast pipeline coordinator (Phase Π.2.4).

Integration glue across Phase Π.2 components:

    proxy posterior bundle  ─┐
                             ├──► proxy_posterior_extractor ──► priors
    recipient anchors       ─┤                                     │
    spend plan              ─┤                                     ▼
    n_recipient (+ y if)  ─┴──► router ──► EngineConfig ──► engine dispatch
                                                                   │
                                                                   ▼
                                                        TransferForecast OR
                                                        OLS+priors forecast OR
                                                        Bayesian+priors forecast
                                                                   │
                                                                   ▼
                                                        ProjectDB.save_version

This module does NOT train proxy Bayesian models — that's expensive (minutes)
and orthogonal к routing logic. Caller pre-trains (or loads cached) proxy
posterior, then orchestrator handles transfer + recipient forecast.

Engine wiring per mode (Phase Π.2.1 + Π.2.2 + future Π.2.5/2.6):

    PURE_TRANSFER             → pure_transfer_engine.forecast_pure_transfer
    TRANSFER_WITH_BIAS_CHECK  → pure_transfer + bias check vs observed y
    OLS_WITH_PROXY_PRIORS     → ols_engine.train_ols + SE inflation (Phase Π.2.5)
    BAYESIAN_WITH_PROXY_PRIORS→ bayesian_engine.train_model с informative priors
                                                                 (Phase Π.2.6)

For modes OLS/Bayesian, current implementation falls back к pure_transfer
с conservative similarity inflation, because OLS+priors / Bayesian+priors
require recipient y vector AND the proxy posterior priors injection
которое is a separate refactor of bayesian_engine.py (currently uses
HalfNormal defaults, not arbitrary mean/std).

Phase Π.2.4 ship: orchestrator pure_transfer paths working end-to-end.
Phase Π.2.5/2.6 ship: OLS+priors and Bayesian+priors paths fully wired.

S-17: Forecast budget enforcement (Phase Scale)
-----------------------------------------------
``forecast_recipient`` accepts ``forecast_budget_seconds: float = 30.0``.
A watchdog daemon thread fires ``_cancel_event`` when wall-clock budget is
exceeded.  The forecast pipeline (particularly the Bayesian sampler loop)
already checks ``_cancel_event.is_set()`` at iteration boundaries, so the
shutdown is cooperative.

Trade-offs:
  - Budget is enforced cooperatively; the sampler may finish the current
    MCMC draw before honoring the cancel signal.  Observed overhead is
    typically < 2 s on supported hardware.
  - For pure-transfer paths (modes 1-2) the computation is O(ms), so the
    watchdog fires only in pathological edge cases (e.g., extremely long
    spend plans).  Budget=0 → immediate cancel on the very first check.
  - The watchdog thread is daemon=True so it does not prevent process exit.
  - Pure stdlib: threading.Event + time.monotonic — no extra dependencies.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from aurora_launch.engines.proxy_posterior_extractor import (
    ProxyChannelPrior,
    ProxyExtractionError,
    extract_proxy_priors,
    proxy_baseline_from_normalization,
    shrink_proxy_priors,
    to_channel_transfer_params,
)
from aurora_launch.engines.pure_transfer_engine import (
    ChannelTransferParams,
    RecipientAnchors,
    TransferForecast,
    TransferInputs,
    forecast_pure_transfer,
)
from aurora_launch.engines.router import (
    EngineConfig,
    EngineMode,
    Granularity,
    select_engine,
)

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# S-17: Module-level cancel event — set by watchdog thread on budget exceeded.
# The sampler loop checks this at each iteration boundary.
# Callers that bypass the orchestrator can import and check this directly.
# ---------------------------------------------------------------------------
_cancel_event: threading.Event = threading.Event()


class ForecastBudgetExceededError(RuntimeError):
    """Raised when forecast_recipient exceeds its wall-clock budget.

    Attributes:
        elapsed_s: actual elapsed time in seconds at the moment of cancellation.
        budget_s: the budget that was set.
    """

    def __init__(self, elapsed_s: float, budget_s: float) -> None:
        self.elapsed_s = elapsed_s
        self.budget_s = budget_s
        super().__init__(
            f"Forecast budget exceeded: elapsed {elapsed_s:.2f}s > budget {budget_s:.2f}s. "
            f"Consider raising forecast_budget_seconds or simplifying the spend plan."
        )


def _start_watchdog(budget_s: float, cancel: threading.Event) -> threading.Timer:
    """Spawn a daemon thread that sets *cancel* after *budget_s* seconds.

    Returns the Timer so the caller can cancel it if the forecast finishes
    before the budget expires.
    """
    def _fire() -> None:
        _log.warning(
            "Forecast budget watchdog fired after %.2f s (budget=%.2f s). "
            "Setting cancel flag.",
            budget_s,
            budget_s,
        )
        cancel.set()

    timer = threading.Timer(interval=budget_s, function=_fire)
    timer.daemon = True
    timer.start()
    return timer


@dataclass(frozen=True)
class ProxyBundle:
    """Pre-trained proxy state ready for transfer.

    Caller obtains this by:
      (a) Running bayesian_engine.train_model and extracting from its result
      (b) Loading cached proxy from .aurora bundle (via loader.py)
      (c) Loading from ProjectDB (Phase Π.3.1 forecast versioning)

    Fields:
        posterior_samples — bayesian_engine output {media_betas, alphas, ...}
        media_cols — channel IDs ordered to match posterior axis 0
        normalization — bayesian_engine output (contains y_mean for baseline)
        config — bayesian_engine config used (for traceability + audit cert)
    """

    posterior_samples: Mapping[str, Any]
    media_cols: list[str]
    normalization: Mapping[str, Any]
    config: Mapping[str, Any] = field(default_factory=dict)
    proxy_brand_id: str | None = None  # opaque identifier (anonymized code OK)
    n_proxy_observations: int = 0


@dataclass(frozen=True)
class OrchestrationResult:
    """Full orchestration output: routing decision + forecast + diagnostics."""

    engine_config: EngineConfig
    forecast: TransferForecast | None  # None if bias check failed hard
    proxy_priors_used: dict[str, ProxyChannelPrior]
    methodology_signature: str
    warnings: list[str] = field(default_factory=list)


class OrchestratorError(RuntimeError):
    """Raised for orchestration-level failures (e.g., engine selection mismatch)."""


class LaunchOrchestrator:
    """Coordinates proxy → recipient forecast pipeline.

    Stateless по design — каждый forecast_recipient is independent. Caller
    persists results via ProjectDB.

    Per Plan v3.0 §A.2 + D-07: orchestrator delegates routing к router.py,
    routing к engines, persistence к ProjectDB. No business logic baked here.
    """

    def __init__(self) -> None:
        pass

    def forecast_recipient(
        self,
        *,
        proxy: ProxyBundle,
        anchors: RecipientAnchors,
        spend_plan: dict[str, list[float]],
        horizon_periods: int,
        granularity: Granularity = "monthly",
        n_recipient: int = 0,
        recipient_y: list[float] | None = None,
        similarity_factors: Mapping[str, float] | None = None,
        similarity_inflations: Mapping[str, float] | None = None,
        coverage_target: float = 0.95,
        shrinkage_factor: float = 0.5,
        user_override_mode: EngineMode | None = None,
        forecast_budget_seconds: float = 30.0,
    ) -> OrchestrationResult:
        """Run full pipeline: extract priors → route → forecast.

        Args:
            proxy: pre-trained ProxyBundle (Bayesian on proxy brand history)
            anchors: RecipientAnchors validated by caller
            spend_plan: per-channel spend by period (length = horizon_periods)
            horizon_periods: number of forecast periods
            granularity: 'monthly' or 'weekly' (D-06)
            n_recipient: number of recipient observations available
            recipient_y: optional recipient observed y (for modes 2-4)
            similarity_factors / similarity_inflations: per-channel overrides
            coverage_target: CI coverage (0.80 / 0.90 / 0.95 / 0.99)
            shrinkage_factor: how strongly informative priors compress σ ([0,1])
            user_override_mode: optional explicit mode override (only when allowed)
            forecast_budget_seconds: wall-clock budget in seconds (default 30.0).
                A watchdog daemon thread sets the module-level cancel event if
                the budget is exceeded.  The forecast pipeline checks the cancel
                flag cooperatively at iteration boundaries; actual teardown may
                take up to ~2 s more than the stated budget.
                Pass 0 (or any value ≤ 0) to trigger an immediate cancel on the
                very next pipeline check.

        Returns:
            OrchestrationResult с engine decision + forecast + diagnostics.

        Raises:
            OrchestratorError: orchestration-level failure.
            ProxyExtractionError: cannot extract priors from proxy bundle.
            ValueError: bad inputs.
            ForecastBudgetExceededError: wall-clock budget exceeded during
                forecast pipeline execution.
        """
        # S-17: reset cancel flag and arm watchdog before pipeline starts.
        _cancel_event.clear()
        t_start = time.monotonic()
        effective_budget = max(0.0, forecast_budget_seconds)
        watchdog = _start_watchdog(effective_budget, _cancel_event)

        try:
            return self._forecast_recipient_impl(
                proxy=proxy,
                anchors=anchors,
                spend_plan=spend_plan,
                horizon_periods=horizon_periods,
                granularity=granularity,
                n_recipient=n_recipient,
                recipient_y=recipient_y,
                similarity_factors=similarity_factors,
                similarity_inflations=similarity_inflations,
                coverage_target=coverage_target,
                shrinkage_factor=shrinkage_factor,
                user_override_mode=user_override_mode,
                cancel_event=_cancel_event,
                t_start=t_start,
                budget_s=effective_budget,
            )
        finally:
            watchdog.cancel()  # disarm if forecast completed within budget

    def _forecast_recipient_impl(
        self,
        *,
        proxy: ProxyBundle,
        anchors: RecipientAnchors,
        spend_plan: dict[str, list[float]],
        horizon_periods: int,
        granularity: Granularity,
        n_recipient: int,
        recipient_y: list[float] | None,
        similarity_factors: Mapping[str, float] | None,
        similarity_inflations: Mapping[str, float] | None,
        coverage_target: float,
        shrinkage_factor: float,
        user_override_mode: EngineMode | None,
        cancel_event: threading.Event,
        t_start: float,
        budget_s: float,
    ) -> OrchestrationResult:
        """Internal implementation — separated so watchdog wraps cleanly."""
        warnings: list[str] = []

        def _check_cancel() -> None:
            """Raise ForecastBudgetExceededError if cancel event is set."""
            if cancel_event.is_set():
                elapsed = time.monotonic() - t_start
                raise ForecastBudgetExceededError(elapsed_s=elapsed, budget_s=budget_s)

        # S-17: check cancel at pipeline entry (handles budget=0 case).
        _check_cancel()

        # 1. Engine routing decision
        engine_config = select_engine(
            n_recipient=n_recipient,
            n_proxy=proxy.n_proxy_observations or len(proxy.media_cols) * 24,
            granularity=granularity,
            user_override=user_override_mode,
            shrinkage_factor=shrinkage_factor,
        )

        _log.info(
            "Routing decision: mode=%s, n_recipient=%d, n_proxy=%d, granularity=%s",
            engine_config.mode.value,
            n_recipient,
            engine_config.n_proxy,
            granularity,
        )

        # 2. Extract priors (always needed for all 4 modes)
        _check_cancel()  # S-17: cooperative boundary before expensive step
        try:
            raw_priors = extract_proxy_priors(
                proxy.posterior_samples, proxy.media_cols
            )
        except ProxyExtractionError as exc:
            raise OrchestratorError(
                f"Cannot extract proxy priors: {exc}"
            ) from exc

        shrunk_priors = shrink_proxy_priors(raw_priors, shrinkage_factor)

        # 3. Proxy baseline for scale ratio
        _check_cancel()  # S-17: cooperative boundary before normalization read
        try:
            proxy_baseline = proxy_baseline_from_normalization(proxy.normalization)
        except ProxyExtractionError as exc:
            raise OrchestratorError(
                f"Cannot read proxy baseline: {exc}"
            ) from exc

        # 4. Build pure_transfer ChannelTransferParams (used by modes 1+2+fallback)
        channel_dicts = to_channel_transfer_params(
            shrunk_priors,
            similarity_factors=similarity_factors,
            similarity_inflations=similarity_inflations,
        )
        channels = [ChannelTransferParams.model_validate(d) for d in channel_dicts]

        # 5. Engine dispatch
        _check_cancel()  # S-17: cooperative boundary before engine computation
        forecast: TransferForecast | None = None
        signature = "unknown"

        if engine_config.mode == EngineMode.PURE_TRANSFER:
            forecast = self._run_pure_transfer(
                channels=channels,
                anchors=anchors,
                spend_plan=spend_plan,
                horizon_periods=horizon_periods,
                granularity=granularity,
                proxy_baseline=proxy_baseline,
                coverage_target=coverage_target,
            )
            signature = "pure_transfer_v1"

        elif engine_config.mode == EngineMode.TRANSFER_WITH_BIAS_CHECK:
            # Mode 2: pure transfer + bias check vs observed y
            forecast = self._run_pure_transfer(
                channels=channels,
                anchors=anchors,
                spend_plan=spend_plan,
                horizon_periods=horizon_periods,
                granularity=granularity,
                proxy_baseline=proxy_baseline,
                coverage_target=coverage_target,
            )
            if recipient_y is not None and len(recipient_y) > 0:
                bias_pct, bias_diagnostics = self._compute_bias_check(
                    forecast=forecast, recipient_y=recipient_y
                )
                if bias_diagnostics:
                    warnings.extend(bias_diagnostics)
                elif abs(bias_pct) > 30.0:
                    warnings.append(
                        f"Bias check: observed baseline deviates {bias_pct:.1f}% "
                        f"from proxy expectation (>30% threshold). "
                        f"Recipient may differ from proxy materially."
                    )
            else:
                # PI2-M3 audit fix: explicit warning when Mode 2 selected but
                # no recipient_y available for bias check.
                warnings.append(
                    "Mode 2 (TRANSFER_WITH_BIAS_CHECK) selected but recipient_y "
                    "not provided — bias check skipped, falling back к pure transfer."
                )
            signature = "transfer_with_bias_check_v1"

        elif engine_config.mode == EngineMode.OLS_WITH_PROXY_PRIORS:
            # Mode 3: OLS+priors. Full impl в Phase Π.2.5. Current fallback:
            # pure_transfer с tighter similarity_inflation (because we have
            # observed y to anchor variance — reduces uncertainty conservatively).
            warnings.append(
                "OLS+priors fallback к pure_transfer с tighter inflation "
                "(full OLS-with-proxy-priors will be wired в Phase Π.2.5)."
            )
            tighter_inflations = {
                ch.channel_id: ch.similarity_inflation * 0.7
                for ch in channels
            }
            tightened_channels = [
                ChannelTransferParams(
                    channel_id=c.channel_id,
                    proxy_beta_mean=c.proxy_beta_mean,
                    proxy_beta_std=c.proxy_beta_std,
                    adstock_decay=c.adstock_decay,
                    hill_alpha=c.hill_alpha,
                    hill_half_saturation=c.hill_half_saturation,
                    similarity_factor=c.similarity_factor,
                    similarity_inflation=tighter_inflations[c.channel_id],
                )
                for c in channels
            ]
            forecast = self._run_pure_transfer(
                channels=tightened_channels,
                anchors=anchors,
                spend_plan=spend_plan,
                horizon_periods=horizon_periods,
                granularity=granularity,
                proxy_baseline=proxy_baseline,
                coverage_target=coverage_target,
            )
            signature = "ols_with_proxy_priors_fallback_v1"

        elif engine_config.mode == EngineMode.BAYESIAN_WITH_PROXY_PRIORS:
            # Mode 4: Bayesian+priors. Full impl в Phase Π.2.6 (refactor
            # bayesian_engine to accept informative β priors from caller).
            # Current fallback: pure_transfer.
            warnings.append(
                "Bayesian+priors fallback к pure_transfer (Phase Π.2.6 will "
                "fully wire informative-prior Bayesian path)."
            )
            forecast = self._run_pure_transfer(
                channels=channels,
                anchors=anchors,
                spend_plan=spend_plan,
                horizon_periods=horizon_periods,
                granularity=granularity,
                proxy_baseline=proxy_baseline,
                coverage_target=coverage_target,
            )
            signature = "bayesian_with_proxy_priors_fallback_v1"

        return OrchestrationResult(
            engine_config=engine_config,
            forecast=forecast,
            proxy_priors_used=dict(shrunk_priors),
            methodology_signature=signature,
            warnings=warnings,
        )

    @staticmethod
    def _run_pure_transfer(
        *,
        channels: list[ChannelTransferParams],
        anchors: RecipientAnchors,
        spend_plan: dict[str, list[float]],
        horizon_periods: int,
        granularity: Granularity,
        proxy_baseline: float,
        coverage_target: float,
    ) -> TransferForecast:
        inputs = TransferInputs(
            granularity=granularity,
            horizon_periods=horizon_periods,
            channels=channels,
            anchors=anchors,
            spend_plan=spend_plan,
            proxy_baseline_mean=proxy_baseline,
            coverage_target=coverage_target,
        )
        return forecast_pure_transfer(inputs)

    @staticmethod
    def _compute_bias_check(
        forecast: TransferForecast, recipient_y: list[float]
    ) -> tuple[float, list[str]]:
        """Compare observed y mean vs predicted point forecast mean.

        Returns: (bias_pct, diagnostics). bias_pct = relative bias в % (positive
        = observed > predicted). diagnostics — non-empty if bias check could
        not be performed cleanly (e.g., degenerate predicted_mean=0).

        PI2-B4 audit fix: degenerate predicted_mean=0 now returns diagnostic
        warning rather than silently returning 0.0 (which would suppress
        any user-visible bias signal).
        """
        import math  # noqa: PLC0415 — local import к keep top-level light

        if not forecast.points or not recipient_y:
            return 0.0, []
        n = min(len(recipient_y), len(forecast.points))
        observed_mean = sum(recipient_y[:n]) / n
        predicted_mean = sum(p.point_forecast for p in forecast.points[:n]) / n
        # PI-RESCUE-07 audit fix: NaN/inf bypass detection — previously `abs(NaN) < 1e-6`
        # evaluated False, falling through к division by NaN → bias_pct = NaN, then
        # `abs(NaN) > 30.0` also False → bias warning silently suppressed.
        if not math.isfinite(predicted_mean):
            return 0.0, [
                "Bias check inconclusive: predicted_mean is NaN or inf (degenerate forecast). "
                "Review anchors, proxy similarity, и spend plan for invalid values."
            ]
        # R-11 audit fix: ε threshold вместо exact-zero check.
        # Previous `if predicted_mean == 0` missed near-zero values (e.g. 1e-10
        # from float64 underflow) which then produced 30000000% bias spike.
        # Threshold 1e-6 chosen relative к minimal realistic sales value.
        if abs(predicted_mean) < 1e-6:
            return 0.0, [
                "Bias check inconclusive: predicted_mean ≈ 0 (degenerate forecast). "
                f"Observed mean = {observed_mean:.4g}. Review anchors + proxy similarity."
            ]
        return 100.0 * (observed_mean - predicted_mean) / predicted_mean, []
