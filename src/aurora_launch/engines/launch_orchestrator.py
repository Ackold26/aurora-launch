from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from aurora_launch.engines.dispatch_table import dispatch_engine
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
)
from aurora_launch.engines.router import (
    EngineConfig,
    EngineMode,
    Granularity,
    select_engine,
)

_log = logging.getLogger(__name__)

_cancel_event: threading.Event = threading.Event()


class ForecastBudgetExceededError(RuntimeError):
    def __init__(self, elapsed_s: float, budget_s: float) -> None:
        self.elapsed_s = elapsed_s
        self.budget_s = budget_s
        super().__init__(
            f"Forecast budget exceeded: elapsed {elapsed_s:.2f}s > budget {budget_s:.2f}s. "
            f"Consider raising forecast_budget_seconds or simplifying the spend plan."
        )


def _start_watchdog(budget_s: float, cancel: threading.Event) -> threading.Timer:
    def _fire() -> None:
        _log.warning(
            "Forecast budget watchdog fired after %.2f s (budget=%.2f s). Setting cancel flag.",
            budget_s, budget_s,
        )
        cancel.set()

    timer = threading.Timer(interval=budget_s, function=_fire)
    timer.daemon = True
    timer.start()
    return timer


# ---------------------------------------------------------------------------
# S-12: ProxyBundle decomposed into 3 focused dataclasses + lightweight aggregator
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProxyMetadata:
    origin_brand_id: Optional[str] = None
    proxy_app_version: Optional[str] = None
    recorded_at: Optional[str] = None
    n_proxy_observations: int = 0
    brand_category: Optional[str] = None


@dataclass(frozen=True)
class ProxyPosteriorPayload:
    posterior_samples: Mapping[str, Any]
    normalization: Mapping[str, Any]
    media_cols: list


@dataclass(frozen=True)
class ProxyConfig:
    config: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProxyBundle:
    """Structured proxy bundle (Phase 1 hard cut — was S-12 shim).

    Three sub-objects:
      - metadata: provenance + brand identity
      - posterior: samples + normalization + media_cols
      - config_obj: model config dict
    """
    metadata: ProxyMetadata
    posterior: ProxyPosteriorPayload
    config_obj: ProxyConfig

    # Convenience properties для read-only forward access (no warnings).
    # Common dotted paths: bundle.posterior.posterior_samples → bundle.samples
    @property
    def samples(self) -> Mapping[str, Any]:
        return self.posterior.posterior_samples

    @property
    def media_cols(self) -> list:
        return self.posterior.media_cols

    @property
    def n_proxy_observations(self) -> int:
        return self.metadata.n_proxy_observations


def make_proxy_bundle(
    *,
    posterior_samples: Mapping[str, Any],
    media_cols: list,
    normalization: Mapping[str, Any] | None = None,
    config: Mapping[str, Any] | None = None,
    proxy_brand_id: str | None = None,
    proxy_app_version: str | None = None,
    recorded_at: str | None = None,
    n_proxy_observations: int = 0,
    brand_category: str | None = None,
) -> ProxyBundle:
    """Factory for ProxyBundle from flat keyword args.

    Was: ProxyBundle(posterior_samples=, media_cols=, ...) legacy constructor
    с DeprecationWarning. Now: explicit packaging helper. Same call shape,
    но clear что результат is structured + no warning.

    Use в test fixtures + adapters/loaders that produce flat data.
    """
    return ProxyBundle(
        metadata=ProxyMetadata(
            origin_brand_id=proxy_brand_id,
            proxy_app_version=proxy_app_version,
            recorded_at=recorded_at,
            n_proxy_observations=n_proxy_observations,
            brand_category=brand_category,
        ),
        posterior=ProxyPosteriorPayload(
            posterior_samples=posterior_samples,
            normalization=normalization or {},
            media_cols=media_cols,
        ),
        config_obj=ProxyConfig(config=config or {}),
    )


# End S-12 + Phase 1 hard cut
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OrchestrationResult:
    engine_config: EngineConfig
    forecast: TransferForecast | None
    proxy_priors_used: dict[str, ProxyChannelPrior]
    methodology_signature: str
    warnings: list[str] = field(default_factory=list)


class OrchestratorError(RuntimeError):
    pass


class LaunchOrchestrator:
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
        recipient_y: Optional[list[float]] = None,
        similarity_factors: Optional[Mapping[str, float]] = None,
        similarity_inflations: Optional[Mapping[str, float]] = None,
        coverage_target: float = 0.95,
        shrinkage_factor: float = 0.5,
        user_override_mode: Optional[EngineMode] = None,
        forecast_budget_seconds: float = 30.0,
    ) -> OrchestrationResult:
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
            watchdog.cancel()

    def _forecast_recipient_impl(
        self,
        *,
        proxy: ProxyBundle,
        anchors: RecipientAnchors,
        spend_plan: dict[str, list[float]],
        horizon_periods: int,
        granularity: Granularity,
        n_recipient: int,
        recipient_y: Optional[list[float]],
        similarity_factors: Optional[Mapping[str, float]],
        similarity_inflations: Optional[Mapping[str, float]],
        coverage_target: float,
        shrinkage_factor: float,
        user_override_mode: Optional[EngineMode],
        cancel_event: threading.Event,
        t_start: float,
        budget_s: float,
    ) -> OrchestrationResult:
        warnings: list[str] = []

        def _check_cancel() -> None:
            if cancel_event.is_set():
                elapsed = time.monotonic() - t_start
                raise ForecastBudgetExceededError(elapsed_s=elapsed, budget_s=budget_s)

        _check_cancel()

        import warnings as _w

        _post = object.__getattribute__(proxy, "posterior")
        if _post is not None:
            _posterior_samples = _post.posterior_samples
            _media_cols = _post.media_cols
            _normalization = _post.normalization
        else:
            with _w.catch_warnings():
                _w.simplefilter("ignore", DeprecationWarning)
                _posterior_samples = proxy.posterior_samples
                _media_cols = proxy.media_cols
                _normalization = proxy.normalization

        _meta = object.__getattribute__(proxy, "metadata")
        if _meta is not None:
            _n_proxy_obs = _meta.n_proxy_observations
        else:
            with _w.catch_warnings():
                _w.simplefilter("ignore", DeprecationWarning)
                _n_proxy_obs = proxy.n_proxy_observations

        engine_config = select_engine(
            n_recipient=n_recipient,
            n_proxy=_n_proxy_obs or len(_media_cols) * 24,
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

        _check_cancel()
        try:
            raw_priors = extract_proxy_priors(_posterior_samples, _media_cols)
        except ProxyExtractionError as exc:
            raise OrchestratorError(
                f"Cannot extract proxy priors: {exc}"
            ) from exc

        shrunk_priors = shrink_proxy_priors(raw_priors, shrinkage_factor)

        _check_cancel()
        try:
            proxy_baseline = proxy_baseline_from_normalization(_normalization)
        except ProxyExtractionError as exc:
            raise OrchestratorError(
                f"Cannot read proxy baseline: {exc}"
            ) from exc

        channel_dicts = to_channel_transfer_params(
            shrunk_priors,
            similarity_factors=similarity_factors,
            similarity_inflations=similarity_inflations,
        )
        channels = [ChannelTransferParams.model_validate(d) for d in channel_dicts]

        _check_cancel()
        forecast, signature = dispatch_engine(
            mode=engine_config.mode,
            channels=channels,
            anchors=anchors,
            spend_plan=spend_plan,
            horizon_periods=horizon_periods,
            granularity=granularity,
            proxy_baseline=proxy_baseline,
            coverage_target=coverage_target,
            recipient_y=recipient_y,
            warnings=warnings,
            shrinkage_factor=shrinkage_factor,
        )

        if (
            engine_config.mode == EngineMode.TRANSFER_WITH_BIAS_CHECK
            and recipient_y is not None
            and len(recipient_y) > 0
        ):
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

        return OrchestrationResult(
            engine_config=engine_config,
            forecast=forecast,
            proxy_priors_used=dict(shrunk_priors),
            methodology_signature=signature,
            warnings=warnings,
        )

    @staticmethod
    def _compute_bias_check(
        forecast: TransferForecast, recipient_y: list[float]
    ) -> tuple[float, list[str]]:
        import math

        if not forecast.points or not recipient_y:
            return 0.0, []
        n = min(len(recipient_y), len(forecast.points))
        observed_mean = sum(recipient_y[:n]) / n
        predicted_mean = sum(p.point_forecast for p in forecast.points[:n]) / n
        if not math.isfinite(predicted_mean):
            return 0.0, [
                "Bias check inconclusive: predicted_mean is NaN or inf (degenerate forecast). "
                "Review anchors, proxy similarity, and spend plan for invalid values."
            ]
        if abs(predicted_mean) < 1e-6:
            return 0.0, [
                "Bias check inconclusive: predicted_mean approx 0 (degenerate forecast). "
                f"Observed mean = {observed_mean:.4g}. Review anchors + proxy similarity."
            ]
        return 100.0 * (observed_mean - predicted_mean) / predicted_mean, []
