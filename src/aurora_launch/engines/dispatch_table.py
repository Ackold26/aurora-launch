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
        **kwargs: Any,
    ) -> tuple[TransferForecast, str]:
        ...

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
      priors. Currently propagated via **kwargs. Make it explicit once
      bayesian_engine.train_model signature is updated.

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
from typing import TYPE_CHECKING, Any

from aurora_launch.engines.pure_transfer_engine import (
    ChannelTransferParams,
    RecipientAnchors,
    TransferForecast,
    TransferInputs,
    forecast_pure_transfer,
)
from aurora_launch.engines.router import EngineMode, Granularity

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
        Any,                          # **kwargs
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
    **kwargs: Any,
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
    **kwargs: Any,
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


def _handle_ols_with_proxy_priors_stub(
    channels: list[ChannelTransferParams],
    anchors: RecipientAnchors,
    spend_plan: dict[str, list[float]],
    horizon_periods: int,
    granularity: Granularity,
    proxy_baseline: float,
    coverage_target: float,
    recipient_y: list[float] | None,
    warnings: list[str],
    **kwargs: Any,
) -> tuple[TransferForecast, str]:
    """Mode 3 — OLS_WITH_PROXY_PRIORS (Phase Magic M-01 stub).

    Full implementation pending Phase Magic M-01 (ols_engine.train_ols_with_priors).
    Current fallback: pure_transfer с tighter similarity_inflation (×0.7)
    because observed y is available to anchor variance.

    Replace this function with the real OLS implementation in Phase Magic M-01.
    See module OQ-1, OQ-3 for interface questions to resolve first.
    """
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


def _handle_bayesian_with_proxy_priors_stub(
    channels: list[ChannelTransferParams],
    anchors: RecipientAnchors,
    spend_plan: dict[str, list[float]],
    horizon_periods: int,
    granularity: Granularity,
    proxy_baseline: float,
    coverage_target: float,
    recipient_y: list[float] | None,
    warnings: list[str],
    **kwargs: Any,
) -> tuple[TransferForecast, str]:
    """Mode 4 — BAYESIAN_WITH_PROXY_PRIORS (Phase Magic M-02 stub).

    Full implementation pending Phase Magic M-02 (bayesian_engine informative
    β priors injection refactor).  Current fallback: pure_transfer.

    Replace this function with the real Bayesian implementation in Phase Magic
    M-02.  See module OQ-2, OQ-3 for interface questions to resolve first.
    INV-04: when M-02 is wired, import PyMC lazily inside the handler.
    """
    warnings.append(
        "Bayesian+priors fallback к pure_transfer (Phase Π.2.6 will "
        "fully wire informative-prior Bayesian path)."
    )
    forecast = _run_pure_transfer(
        channels=channels,
        anchors=anchors,
        spend_plan=spend_plan,
        horizon_periods=horizon_periods,
        granularity=granularity,
        proxy_baseline=proxy_baseline,
        coverage_target=coverage_target,
    )
    return forecast, "bayesian_with_proxy_priors_fallback_v1"


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
    EngineMode.OLS_WITH_PROXY_PRIORS: _handle_ols_with_proxy_priors_stub,
    EngineMode.BAYESIAN_WITH_PROXY_PRIORS: _handle_bayesian_with_proxy_priors_stub,
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
    **kwargs: Any,
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
        **kwargs: forwarded to handler (shrinkage_factor etc. for future modes).

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
        **kwargs,
    )
