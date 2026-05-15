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


class ProxyBundle:
    __slots__ = (
        "metadata", "posterior", "config_obj",
        "_legacy_posterior_samples", "_legacy_media_cols",
        "_legacy_normalization", "_legacy_config",
        "_legacy_proxy_brand_id", "_legacy_n_proxy_observations",
    )

    def __init__(
        self,
        *,
        metadata: Optional[ProxyMetadata] = None,
        posterior: Optional[ProxyPosteriorPayload] = None,
        config_obj: Optional[ProxyConfig] = None,
        posterior_samples: Optional[Mapping[str, Any]] = None,
        media_cols: Optional[list] = None,
        normalization: Optional[Mapping[str, Any]] = None,
        config: Optional[Mapping[str, Any]] = None,
        proxy_brand_id: Optional[str] = None,
        n_proxy_observations: int = 0,
    ) -> None:
        import warnings as _w

        if posterior_samples is not None or media_cols is not None or normalization is not None:
            _w.warn(
                "ProxyBundle flat-field constructor is deprecated. "
                "Use ProxyBundle(metadata=ProxyMetadata(...), "
                "posterior=ProxyPosteriorPayload(...), config_obj=ProxyConfig(...)) "
                "instead. Flat fields will be removed in v0.2.0.",
                DeprecationWarning,
                stacklevel=2,
            )
            object.__setattr__(self, "metadata", None)
            object.__setattr__(self, "posterior", None)
            object.__setattr__(self, "config_obj", None)
            object.__setattr__(self, "_legacy_posterior_samples", posterior_samples)
            object.__setattr__(self, "_legacy_media_cols",
                               media_cols if media_cols is not None else [])
            object.__setattr__(self, "_legacy_normalization",
                               normalization if normalization is not None else {})
            object.__setattr__(self, "_legacy_config",
                               config if config is not None else {})
            object.__setattr__(self, "_legacy_proxy_brand_id", proxy_brand_id)
            object.__setattr__(self, "_legacy_n_proxy_observations", n_proxy_observations)
        else:
            object.__setattr__(self, "metadata", metadata)
            object.__setattr__(self, "posterior", posterior)
            object.__setattr__(self, "config_obj", config_obj)
            object.__setattr__(self, "_legacy_posterior_samples", None)
            object.__setattr__(self, "_legacy_media_cols", None)
            object.__setattr__(self, "_legacy_normalization", None)
            object.__setattr__(self, "_legacy_config", None)
            object.__setattr__(self, "_legacy_proxy_brand_id", None)
            object.__setattr__(self, "_legacy_n_proxy_observations", None)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError(
            "ProxyBundle is immutable (frozen). Use a new ProxyBundle instance."
        )

    def __getattr__(self, name: str) -> Any:
        import warnings as _w

        _LEGACY_MAP: dict = {
            "posterior_samples":    ("posterior",  "posterior_samples", {}),
            "media_cols":           ("posterior",  "media_cols",        []),
            "normalization":        ("posterior",  "normalization",     {}),
            "config":               ("config_obj", "config",            {}),
            "proxy_brand_id":       ("metadata",   "origin_brand_id",   None),
            "n_proxy_observations": ("metadata",   "n_proxy_observations", 0),
        }

        if name not in _LEGACY_MAP:
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'"
            )

        sub_obj_name, sub_field, default_val = _LEGACY_MAP[name]

        _w.warn(
            f"ProxyBundle.{name} is deprecated. "
            f"Use bundle.{sub_obj_name}.{sub_field} instead. "
            f"Direct field access will be removed in v0.2.0.",
            DeprecationWarning,
            stacklevel=2,
        )

        legacy_slot = f"_legacy_{name}"
        try:
            val = object.__getattribute__(self, legacy_slot)
        except AttributeError:
            val = None
        if val is not None:
            return val

        try:
            sub_obj = object.__getattribute__(self, sub_obj_name)
        except AttributeError:
            return default_val
        if sub_obj is not None:
            return getattr(sub_obj, sub_field)

        return default_val

    def __repr__(self) -> str:
        meta = object.__getattribute__(self, "metadata")
        post = object.__getattribute__(self, "posterior")
        if meta is not None or post is not None:
            cfg = object.__getattribute__(self, "config_obj")
            return (
                f"ProxyBundle(metadata={meta!r}, posterior={post!r}, config_obj={cfg!r})"
            )
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            return (
                f"ProxyBundle(media_cols={self.media_cols!r}, "
                f"n_proxy_observations={self.n_proxy_observations!r})"
            )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ProxyBundle):
            return NotImplemented
        for slot in self.__slots__:
            try:
                a = object.__getattribute__(self, slot)
                b = object.__getattribute__(other, slot)
            except AttributeError:
                return False
            try:
                if a != b:
                    return False
            except (ValueError, TypeError):
                return False
        return True

    def __hash__(self) -> int:
        return id(self)


# End S-12
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
