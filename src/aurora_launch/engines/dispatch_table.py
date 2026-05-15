"""4-mode engine dispatch table for Aurora Launch Planner (S-11).

Replaces the if/elif chain in LaunchOrchestrator._forecast_recipient_impl
with a registry-based dispatch pattern that makes adding new mode
implementations (Phase Magic M-01 / M-02) a one-line registration.

Dispatch contract
-----------------
Every handler in _MODE_DISPATCH must have the following signature:

    def handler(
        channels: list[ChannelTransferParams],
        anchors: RecipientAnchors,
        spend_plan: dict[str, list[float]],
        horizon_periods: int,
        granularity: Granularity,
        proxy_baseline: float,
        coverage_target: float,
        recipient_y: list[float] | None,
        warnings: list[str],
        extras: DispatchExtras,
    ) -> tuple[TransferForecast, str]:
        ...

Where DispatchExtras — frozen dataclass с typed optional fields
(historical_spend, shrinkage, n_samples) вместо raw `**kwargs: Any`.
Typo `historical_spnd` теперь TypeError при construction, не silent
ignore (Phase 1 audit closure 1.2).

Return value: (forecast, methodology_signature_str).

The handler MUST:
  - return a valid TransferForecast (never None — caller handles None semantics
    on top, e.g., Mode 2 hard-fail).
  - append any user-visible warnings to the *warnings* list (passed by ref).
  - NOT raise for recoverable fallback situations — use warnings instead.
  - NOT import heavy dependencies (PyMC, scipy) at module level — INV-04
    requires lazy imports inside the handler body.

Phase Magic upgrade path
------------------------
When M-01 (OLS+priors full) or M-02 (Bayesian+priors full) is implemented,
replace the corresponding stub handler with the real implementation and
update the handler's docstring. No changes needed in LaunchOrchestrator.

    # Phase Magic M-01: uncomment when ols_engine.train_ols_with_priors exists
    # _MODE_DISPATCH[EngineMode.OLS_WITH_PROXY_PRIORS] = _handle_ols_with_priors

Open questions for Phase Magic-Math
-------------------------------------
OQ-1: Should Mode 3 handler accept recipient_y directly or a pre-built
      numpy array? Currently recipient_y is list[float] | None — the OLS
      engine will likely want np.ndarray[float64]. Decide conversion point
      (here vs inside ols_engine).

OQ-2: Mode 4 Bayesian handler needs shrinkage_factor to build informative
      priors. Propagated via DispatchExtras.shrinkage field. When
      bayesian_engine.train_model accepts informative priors directly,
      this можно убрать из extras.

OQ-3: Both real implementations need the proxy posterior priors directly
      (not just the already-tightened ChannelTransferParams). Consider
      adding `proxy_priors: dict[str, ProxyChannelPrior]` as explicit param
      once M-01/M-02 are wired.

OQ-4: Mode 3 fallback inflation factor (0.7×) was chosen conservatively.
      Revisit during M-01 real implementation — may become irrelevant once
      OLS is wired.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

from aurora_launch.engines.pure_transfer_engine import (
    ChannelTransferParams,
    RecipientAnchors,
    TransferForecast,
    TransferInputs,
    forecast_pure_transfer,
)
from aurora_launch.engines.router import EngineMode, Granularity


# ---------------------------------------------------------------------------
# Phase 1 audit 1.2 closure: typed DispatchExtras replaces unsafe **kwargs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DispatchExtras:
    """Typed extras для dispatch handlers (Phase 1 audit fix).

    Previously **kwargs surface allowed silent typos: `historicl_spend`
    would simply be missing from kwargs.get() и handler would silently
    fallback к pure_transfer. Now: typo на field name raises TypeError
    при construction.

    Phase Magic-Math handlers (M-01, M-02) use historical_spend +
    shrinkage. Future modes can extend this dataclass с new optional
    fields без breaking handler signatures.
    """
    historical_spend: dict[str, list[float]] | None = None
    """Per-channel historical spend для OLS+priors / Bayesian+priors fits."""

    shrinkage: float = 0.3
    """Proxy prior weight ∈ [0, 1]. 0 = pure OLS, 1 = pure proxy."""

    n_samples: int = 500
    """Number of posterior samples для Mode 4 Bayesian+priors output."""

    @classmethod
    def empty(cls) -> "DispatchExtras":
        """Default extras (no historical data, default shrinkage)."""
        return cls()

if TYPE_CHECKING:
    pass  # future: ProxyChannelPrior for M-01/M-02 real impls

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Type alias — makes _MODE_DISPATCH annotation readable
# ---------------------------------------------------------------------------

# Handler signature (see module docstring for contract).
# Spelled out explicitly so IDEs can check callers.
from typing import Callable  # noqa: E402 — after stdlib/third-party

DispatchHandler = Callable[
    [
        list[ChannelTransferParams],  # channels
        RecipientAnchors,             # anchors
        dict[str, list[float]],       # spend_plan
        int,                          # horizon_periods
        Granularity,                  # granularity
        float,                        # proxy_baseline
        float,                        # coverage_target
        "list[float] | None",         # recipient_y
        list[str],                    # warnings (mutated in place)
        "DispatchExtras",             # extras (typed dataclass)
    ],
    "tuple[TransferForecast, str]",
]


# ---------------------------------------------------------------------------
# Handler implementations
# ---------------------------------------------------------------------------


def _handle_pure_transfer(
    channels: list[ChannelTransferParams],
    anchors: RecipientAnchors,
    spend_plan: dict[str, list[float]],
    horizon_periods: int,
    granularity: Granularity,
    proxy_baseline: float,
    coverage_target: float,
    recipient_y: list[float] | None,
    warnings: list[str],
    extras: DispatchExtras = DispatchExtras(),
) -> tuple[TransferForecast, str]:
    """Mode 1 — PURE_TRANSFER.

    No fitting. Scaled proxy posterior × recipient anchors.
    """
    forecast = _run_pure_transfer(
        channels=channels,
        anchors=anchors,
        spend_plan=spend_plan,
        horizon_periods=horizon_periods,
        granularity=granularity,
        proxy_baseline=proxy_baseline,
        coverage_target=coverage_target,
    )
    return forecast, "pure_transfer_v1"


def _handle_transfer_with_bias_check(
    channels: list[ChannelTransferParams],
    anchors: RecipientAnchors,
    spend_plan: dict[str, list[float]],
    horizon_periods: int,
    granularity: Granularity,
    proxy_baseline: float,
    coverage_target: float,
    recipient_y: list[float] | None,
    warnings: list[str],
    extras: DispatchExtras = DispatchExtras(),
) -> tuple[TransferForecast, str]:
    """Mode 2 — TRANSFER_WITH_BIAS_CHECK.

    Pure transfer + optional bias check against observed recipient y.
    Bias check is performed by the caller (LaunchOrchestrator) because it
    requires access to the forecast result post-computation; the handler
    returns the forecast and the caller appends bias warnings to the same
    warnings list.

    The recipient_y parameter is accepted here so future callers can embed
    bias-check logic directly in the handler if preferred.
    """
    forecast = _run_pure_transfer(
        channels=channels,
        anchors=anchors,
        spend_plan=spend_plan,
        horizon_periods=horizon_periods,
        granularity=granularity,
        proxy_baseline=proxy_baseline,
        coverage_target=coverage_target,
    )
    if recipient_y is None or len(recipient_y) == 0:
        warnings.append(
            "Mode 2 (TRANSFER_WITH_BIAS_CHECK) selected but recipient_y "
            "not provided — bias check skipped, falling back к pure transfer."
        )
    # Note: bias magnitude check is performed by LaunchOrchestrator after
    # this handler returns, because it needs _compute_bias_check helper.
    return forecast, "transfer_with_bias_check_v1"


def _handle_ols_with_proxy_priors(
    channels: list[ChannelTransferParams],
    anchors: RecipientAnchors,
    spend_plan: dict[str, list[float]],
    horizon_periods: int,
    granularity: Granularity,
    proxy_baseline: float,
    coverage_target: float,
    recipient_y: list[float] | None,
    warnings: list[str],
    extras: DispatchExtras = DispatchExtras(),
) -> tuple[TransferForecast, str]:
    """Mode 3 — OLS_WITH_PROXY_PRIORS (Phase Magic M-01 real implementation).

    Math: ridge regression combining observed recipient_y с proxy β priors.
    β̂ = (XᵀX + λΩ⁻¹)⁻¹ (Xᵀy + λΩ⁻¹ μ_proxy)

    Falls back к pure_transfer (с warning) if:
      - recipient_y missing / shorter than MIN_OBSERVATIONS (5)
      - historical_spend missing в extras OR misaligned

    Required в extras (DispatchExtras):
      - historical_spend: dict[str, list[float]] — per-channel spend для
        same period as recipient_y. Same channel_ids as in `channels` arg.
      - shrinkage: float = 0.3 (optional override). High → trust proxy more.
    """
    from aurora_launch.engines.ols_with_priors import (
        MIN_OBSERVATIONS,
        DEFAULT_SHRINKAGE,
        fit_ols_with_priors,
    )

    # Phase 1 audit fix: typed extras instead of kwargs.get (typo-unsafe)
    historical_spend = extras.historical_spend
    shrinkage = float(extras.shrinkage) if extras.shrinkage != DEFAULT_SHRINKAGE else DEFAULT_SHRINKAGE

    # Fallback path: insufficient input
    if (
        recipient_y is None
        or len(recipient_y) < MIN_OBSERVATIONS
        or historical_spend is None
    ):
        reason = (
            "missing recipient_y" if recipient_y is None
            else f"recipient_y too short ({len(recipient_y)} < {MIN_OBSERVATIONS})"
            if len(recipient_y) < MIN_OBSERVATIONS
            else "missing historical_spend"
        )
        warnings.append(
            f"OLS+priors: {reason} — falling back к pure_transfer с tighter "
            f"inflation (×0.7) as proxy-only baseline."
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
        forecast = _run_pure_transfer(
            channels=tightened_channels,
            anchors=anchors,
            spend_plan=spend_plan,
            horizon_periods=horizon_periods,
            granularity=granularity,
            proxy_baseline=proxy_baseline,
            coverage_target=coverage_target,
        )
        return forecast, "ols_with_proxy_priors_fallback_v1"

    # Real OLS+priors path
    channel_ids = [c.channel_id for c in channels]

    # Scale proxy β к recipient baseline (same logic as pure_transfer)
    recipient_baseline_mean = float(
        np.mean(_compute_baseline_for_ols(anchors, horizon_periods))
    )
    if proxy_baseline <= 0:
        warnings.append(
            "OLS+priors: proxy_baseline <= 0 — falling back к pure_transfer."
        )
        return _handle_ols_with_proxy_priors(
            channels=channels, anchors=anchors, spend_plan=spend_plan,
            horizon_periods=horizon_periods, granularity=granularity,
            proxy_baseline=1.0, coverage_target=coverage_target,
            recipient_y=None, warnings=warnings,  # forces fallback path
        )
    scale_ratio = recipient_baseline_mean / proxy_baseline

    proxy_beta_means_scaled = {
        c.channel_id: c.proxy_beta_mean * scale_ratio * c.similarity_factor
        for c in channels
    }
    proxy_beta_stds_scaled = {
        c.channel_id: c.proxy_beta_std * scale_ratio + c.similarity_inflation
        for c in channels
    }
    adstock_decays = {c.channel_id: c.adstock_decay for c in channels}
    hill_params = {c.channel_id: (c.hill_alpha, c.hill_half_saturation) for c in channels}

    try:
        result = fit_ols_with_priors(
            recipient_y=recipient_y,
            historical_spend=historical_spend,
            channel_ids=channel_ids,
            adstock_decays=adstock_decays,
            hill_params=hill_params,
            proxy_beta_means=proxy_beta_means_scaled,
            proxy_beta_stds=proxy_beta_stds_scaled,
            shrinkage=shrinkage,
        )
    except (ValueError, np.linalg.LinAlgError) as exc:
        warnings.append(
            f"OLS+priors fit failed ({exc}) — falling back к pure_transfer."
        )
        forecast = _run_pure_transfer(
            channels=channels, anchors=anchors, spend_plan=spend_plan,
            horizon_periods=horizon_periods, granularity=granularity,
            proxy_baseline=proxy_baseline, coverage_target=coverage_target,
        )
        return forecast, "ols_with_proxy_priors_fallback_v1"

    # Build forecast using combined β + σ. Same pipeline as pure_transfer
    # but channels now have updated β_mean / β_std from fit.
    updated_channels = []
    for i, c in enumerate(channels):
        # β_combined is в recipient units already (we scaled priors before fit).
        # Reverse-engineer proxy-side params for pure_transfer entry: divide
        # back by scale_ratio so the engine's own scale_ratio multiplication
        # restores the combined β.
        new_proxy_mean = float(result.beta_combined[i]) / (
            scale_ratio * c.similarity_factor if (scale_ratio * c.similarity_factor) != 0 else 1.0
        )
        # Inflation captures the OLS+priors combined σ minus the scale-back proxy σ.
        # Conservative: zero inflation (rely on combined σ for variance).
        new_proxy_std = float(result.sigma_beta_combined[i]) / (
            scale_ratio if scale_ratio != 0 else 1.0
        )
        updated_channels.append(
            ChannelTransferParams(
                channel_id=c.channel_id,
                proxy_beta_mean=new_proxy_mean,
                proxy_beta_std=new_proxy_std,
                adstock_decay=c.adstock_decay,
                hill_alpha=c.hill_alpha,
                hill_half_saturation=c.hill_half_saturation,
                similarity_factor=c.similarity_factor,
                similarity_inflation=0.0,  # already в combined σ
            )
        )

    forecast = _run_pure_transfer(
        channels=updated_channels, anchors=anchors, spend_plan=spend_plan,
        horizon_periods=horizon_periods, granularity=granularity,
        proxy_baseline=proxy_baseline, coverage_target=coverage_target,
    )

    warnings.append(
        f"OLS+priors fit converged (N={result.n_observations}, "
        f"shrinkage={result.shrinkage_used:.2f}, σ_residual="
        f"{result.sigma_residual:.2f})."
    )
    return forecast, "ols_with_proxy_priors_v1"


def _compute_baseline_for_ols(anchors: RecipientAnchors, horizon: int) -> np.ndarray:
    """Helper — mirrors pure_transfer_engine.compute_recipient_baseline."""
    from aurora_launch.engines.pure_transfer_engine import compute_recipient_baseline
    return compute_recipient_baseline(anchors, horizon)


# Backward-compat alias (test imports the stub name)
_handle_ols_with_proxy_priors_stub = _handle_ols_with_proxy_priors


def _handle_bayesian_with_proxy_priors(
    channels: list[ChannelTransferParams],
    anchors: RecipientAnchors,
    spend_plan: dict[str, list[float]],
    horizon_periods: int,
    granularity: Granularity,
    proxy_baseline: float,
    coverage_target: float,
    recipient_y: list[float] | None,
    warnings: list[str],
    extras: DispatchExtras = DispatchExtras(),
) -> tuple[TransferForecast, str]:
    """Mode 4 — BAYESIAN_WITH_PROXY_PRIORS (Phase Magic M-02 real impl).

    Closed-form Bayesian linear regression с Gaussian priors + likelihood.
    Returns posterior samples drawn from analytical Gaussian Σ̂.

    Falls back к pure_transfer (с warning) if:
      - recipient_y missing / shorter than MIN_OBSERVATIONS (5)
      - historical_spend not provided в extras

    Required в extras (DispatchExtras):
      - historical_spend: dict[str, list[float]] — per-channel spend для
        same period as recipient_y
      - shrinkage: float (optional, default 0.3) — proxy weight ∈ [0,1]
      - n_samples: int (optional, default 500) — posterior sample count

    INV-04: lazy imports inside.
    """
    from aurora_launch.engines.bayesian_with_priors import (
        DEFAULT_POSTERIOR_SAMPLES,
        fit_bayesian_with_priors,
    )
    from aurora_launch.engines.ols_with_priors import (
        DEFAULT_SHRINKAGE,
        MIN_OBSERVATIONS,
    )

    # Phase 1 audit fix: typed extras instead of kwargs.get (typo-unsafe)
    historical_spend = extras.historical_spend
    shrinkage = float(extras.shrinkage)
    n_samples = int(extras.n_samples) if extras.n_samples != DEFAULT_POSTERIOR_SAMPLES else DEFAULT_POSTERIOR_SAMPLES

    # Fallback path: insufficient input
    if (
        recipient_y is None
        or len(recipient_y) < MIN_OBSERVATIONS
        or historical_spend is None
    ):
        reason = (
            "missing recipient_y" if recipient_y is None
            else f"recipient_y too short ({len(recipient_y)} < {MIN_OBSERVATIONS})"
            if len(recipient_y) < MIN_OBSERVATIONS
            else "missing historical_spend"
        )
        warnings.append(
            f"Bayesian+priors: {reason} — falling back к pure_transfer."
        )
        forecast = _run_pure_transfer(
            channels=channels, anchors=anchors, spend_plan=spend_plan,
            horizon_periods=horizon_periods, granularity=granularity,
            proxy_baseline=proxy_baseline, coverage_target=coverage_target,
        )
        return forecast, "bayesian_with_proxy_priors_fallback_v1"

    # Real Bayesian path
    channel_ids = [c.channel_id for c in channels]
    recipient_baseline_mean = float(
        np.mean(_compute_baseline_for_ols(anchors, horizon_periods))
    )
    if proxy_baseline <= 0:
        warnings.append(
            "Bayesian+priors: proxy_baseline <= 0 — falling back к pure_transfer."
        )
        forecast = _run_pure_transfer(
            channels=channels, anchors=anchors, spend_plan=spend_plan,
            horizon_periods=horizon_periods, granularity=granularity,
            proxy_baseline=1.0, coverage_target=coverage_target,
        )
        return forecast, "bayesian_with_proxy_priors_fallback_v1"
    scale_ratio = recipient_baseline_mean / proxy_baseline

    proxy_beta_means_scaled = {
        c.channel_id: c.proxy_beta_mean * scale_ratio * c.similarity_factor
        for c in channels
    }
    proxy_beta_stds_scaled = {
        c.channel_id: c.proxy_beta_std * scale_ratio + c.similarity_inflation
        for c in channels
    }
    adstock_decays = {c.channel_id: c.adstock_decay for c in channels}
    hill_params = {c.channel_id: (c.hill_alpha, c.hill_half_saturation) for c in channels}

    try:
        result = fit_bayesian_with_priors(
            recipient_y=recipient_y,
            historical_spend=historical_spend,
            channel_ids=channel_ids,
            adstock_decays=adstock_decays,
            hill_params=hill_params,
            proxy_beta_means=proxy_beta_means_scaled,
            proxy_beta_stds=proxy_beta_stds_scaled,
            shrinkage=shrinkage,
            n_samples=n_samples,
            seed=42,
        )
    except (ValueError, np.linalg.LinAlgError) as exc:
        warnings.append(
            f"Bayesian+priors fit failed ({exc}) — falling back к pure_transfer."
        )
        forecast = _run_pure_transfer(
            channels=channels, anchors=anchors, spend_plan=spend_plan,
            horizon_periods=horizon_periods, granularity=granularity,
            proxy_baseline=proxy_baseline, coverage_target=coverage_target,
        )
        return forecast, "bayesian_with_proxy_priors_fallback_v1"

    # Build forecast using posterior mean (same approach as M-01).
    # CI bands come из engine's variance computation; posterior_samples
    # available downstream через result для decomposer / sensitivity.
    updated_channels = []
    for i, c in enumerate(channels):
        new_proxy_mean = float(result.beta_mean[i]) / (
            scale_ratio * c.similarity_factor if (scale_ratio * c.similarity_factor) != 0 else 1.0
        )
        # σ from diagonal of posterior covariance
        sigma_i = float(np.sqrt(result.beta_cov[i, i]))
        new_proxy_std = sigma_i / (scale_ratio if scale_ratio != 0 else 1.0)
        updated_channels.append(
            ChannelTransferParams(
                channel_id=c.channel_id,
                proxy_beta_mean=new_proxy_mean,
                proxy_beta_std=new_proxy_std,
                adstock_decay=c.adstock_decay,
                hill_alpha=c.hill_alpha,
                hill_half_saturation=c.hill_half_saturation,
                similarity_factor=c.similarity_factor,
                similarity_inflation=0.0,
            )
        )

    forecast = _run_pure_transfer(
        channels=updated_channels, anchors=anchors, spend_plan=spend_plan,
        horizon_periods=horizon_periods, granularity=granularity,
        proxy_baseline=proxy_baseline, coverage_target=coverage_target,
    )

    warnings.append(
        f"Bayesian+priors fit converged (N={result.n_observations}, "
        f"samples={result.n_samples}, R̂={result.r_hat:.3f}, "
        f"shrinkage={result.shrinkage_used:.2f})."
    )
    return forecast, "bayesian_with_proxy_priors_v1"


# Backward-compat alias (test imports the stub name)
_handle_bayesian_with_proxy_priors_stub = _handle_bayesian_with_proxy_priors


# ---------------------------------------------------------------------------
# Internal helper — shared by all handlers that call pure_transfer
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Dispatch table — single registry; one entry per EngineMode
# ---------------------------------------------------------------------------

_MODE_DISPATCH: dict[EngineMode, DispatchHandler] = {
    EngineMode.PURE_TRANSFER: _handle_pure_transfer,
    EngineMode.TRANSFER_WITH_BIAS_CHECK: _handle_transfer_with_bias_check,
    EngineMode.OLS_WITH_PROXY_PRIORS: _handle_ols_with_proxy_priors,
    EngineMode.BAYESIAN_WITH_PROXY_PRIORS: _handle_bayesian_with_proxy_priors,
}


# ---------------------------------------------------------------------------
# Public dispatch entrypoint
# ---------------------------------------------------------------------------


def dispatch_engine(
    mode: EngineMode,
    channels: list[ChannelTransferParams],
    anchors: RecipientAnchors,
    spend_plan: dict[str, list[float]],
    horizon_periods: int,
    granularity: Granularity,
    proxy_baseline: float,
    coverage_target: float,
    recipient_y: list[float] | None,
    warnings: list[str],
    extras: DispatchExtras = DispatchExtras(),
) -> tuple[TransferForecast, str]:
    """Dispatch forecast execution to the registered handler for *mode*.

    Args:
        mode: EngineMode selected by router.
        channels: per-channel transfer parameters (already shrunk + similarity-adjusted).
        anchors: recipient brand anchors validated by caller.
        spend_plan: per-channel spend by period.
        horizon_periods: number of forecast periods.
        granularity: 'monthly' or 'weekly'.
        proxy_baseline: y_mean from proxy normalization (for scale ratio).
        coverage_target: CI coverage probability (0.80/0.90/0.95/0.99).
        recipient_y: observed recipient y (for modes 2-4, may be None).
        warnings: mutable list; handlers append user-visible warnings here.
        extras: typed DispatchExtras dataclass (historical_spend / shrinkage /
            n_samples). Заменяет raw **kwargs (Phase 1 audit closure 1.2):
            typo на field теперь TypeError, не silent fallback.

    Returns:
        Tuple of (TransferForecast, methodology_signature_str).

    Raises:
        KeyError: if *mode* has no registered handler (defensive guard).
            This should never happen in production — it would indicate
            a new EngineMode value was added without registering a handler.
    """
    try:
        handler = _MODE_DISPATCH[mode]
    except KeyError:
        registered = [m.value for m in _MODE_DISPATCH]
        raise KeyError(
            f"No dispatch handler registered for EngineMode.{mode.name}. "
            f"Registered modes: {registered}. "
            f"Add an entry to _MODE_DISPATCH in dispatch_table.py."
        ) from None

    _log.debug("Dispatching to %s handler for mode=%s", handler.__name__, mode.value)
    return handler(
        channels,
        anchors,
        spend_plan,
        horizon_periods,
        granularity,
        proxy_baseline,
        coverage_target,
        recipient_y,
        warnings,
        extras,
    )
