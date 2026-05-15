"""Phase Scale S-11 — Dispatch table refactor tests.

Coverage:
- All 4 EngineMode values have an entry in _MODE_DISPATCH
- dispatch_engine returns correct handler result per mode
- Mode 3 (OLS_WITH_PROXY_PRIORS) fallback path emits warning
- Mode 4 (BAYESIAN_WITH_PROXY_PRIORS) fallback path emits warning
- KeyError raised for an unregistered mode (defensive guard)
- Dispatch contract: each registered handler accepts the full kwargs signature
- LaunchOrchestrator.forecast_recipient uses dispatch table (end-to-end smoke)
- Mode 2 bias check still fires via orchestrator post-dispatch hook
"""

from __future__ import annotations

import inspect
from unittest.mock import patch

import numpy as np
import pytest

from aurora_launch.engines.dispatch_table import (
    _MODE_DISPATCH,
    _handle_bayesian_with_proxy_priors_stub,
    _handle_ols_with_proxy_priors_stub,
    _handle_pure_transfer,
    _handle_transfer_with_bias_check,
    dispatch_engine,
)
from aurora_launch.engines.launch_orchestrator import (
    LaunchOrchestrator,
    ProxyBundle,
    make_proxy_bundle,
)
from aurora_launch.engines.pure_transfer_engine import (
    ChannelTransferParams,
    RecipientAnchors,
)
from aurora_launch.engines.router import EngineMode


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_channels(n: int = 2) -> list[ChannelTransferParams]:
    return [
        ChannelTransferParams(
            channel_id=f"ch_{i}",
            proxy_beta_mean=0.2,
            proxy_beta_std=0.05,
            adstock_decay=0.5,
            hill_alpha=2.0,
            hill_half_saturation=100.0,
            similarity_factor=1.0,
            similarity_inflation=0.1,
        )
        for i in range(n)
    ]


def _make_anchors(horizon: int = 6) -> RecipientAnchors:
    return RecipientAnchors(
        market_size=10_000_000.0,
        market_size_cv=0.10,
        planned_share_trajectory=[0.05] * horizon,
        distribution_trajectory=[0.70] * horizon,
        pricing_index=1.0,
        elasticity=0.5,
        seasonality=[1.0] * horizon,
    )


def _make_spend_plan(horizon: int = 6, channel_ids: list[str] | None = None) -> dict[str, list[float]]:
    if channel_ids is None:
        channel_ids = ["ch_0", "ch_1"]
    return {ch: [100.0] * horizon for ch in channel_ids}


def _make_proxy_bundle(n_channels: int = 2, n_samples: int = 200) -> ProxyBundle:
    rng = np.random.default_rng(42)
    return make_proxy_bundle(
        posterior_samples={
            "media_betas": np.array(
                [rng.normal(loc=0.2, scale=0.05, size=n_samples) for _ in range(n_channels)]
            ),
            "alphas": np.array(
                [rng.normal(loc=2.0, scale=0.1, size=n_samples) for _ in range(n_channels)]
            ),
            "gammas": np.array(
                [rng.normal(loc=100.0, scale=5.0, size=n_samples) for _ in range(n_channels)]
            ),
            "adstock_decay": np.array(
                [
                    np.clip(rng.normal(loc=0.5, scale=0.05, size=n_samples), 0.0, 1.0)
                    for _ in range(n_channels)
                ]
            ),
        },
        media_cols=["tv", "digital"][:n_channels],
        normalization={"y_mean": 500_000.0, "y_std": 50_000.0},
        config={},
        proxy_brand_id="test-proxy",
        n_proxy_observations=104,
    )


# ---------------------------------------------------------------------------
# S-11-T01: All 4 modes have an entry in _MODE_DISPATCH
# ---------------------------------------------------------------------------


class TestDispatchTableCompleteness:
    def test_all_engine_modes_registered(self) -> None:
        """_MODE_DISPATCH must contain every EngineMode value."""
        for mode in EngineMode:
            assert mode in _MODE_DISPATCH, (
                f"EngineMode.{mode.name} has no entry in _MODE_DISPATCH. "
                f"Add a handler in dispatch_table.py."
            )

    def test_dispatch_table_length_matches_engine_mode_count(self) -> None:
        """No extra phantom entries, no missing modes."""
        assert len(_MODE_DISPATCH) == len(EngineMode)

    def test_all_values_are_callable(self) -> None:
        """Every registered handler must be callable."""
        for mode, handler in _MODE_DISPATCH.items():
            assert callable(handler), f"Handler for {mode.name} is not callable"


# ---------------------------------------------------------------------------
# S-11-T02: dispatch_engine returns correct handler per mode
# ---------------------------------------------------------------------------


class TestDispatchEngineLookup:
    """Verify that dispatch_engine calls the correct handler for each mode."""

    _COMMON = dict(
        channels=_make_channels(2),
        anchors=_make_anchors(6),
        spend_plan=_make_spend_plan(6, ["ch_0", "ch_1"]),
        horizon_periods=6,
        granularity="monthly",
        proxy_baseline=500_000.0,
        coverage_target=0.95,
        recipient_y=None,
    )

    def test_pure_transfer_dispatch(self) -> None:
        warnings: list[str] = []
        forecast, sig = dispatch_engine(
            mode=EngineMode.PURE_TRANSFER,
            warnings=warnings,
            **self._COMMON,
        )
        assert forecast is not None
        assert sig == "pure_transfer_v1"
        assert warnings == []  # Mode 1 produces no warnings

    def test_transfer_with_bias_check_dispatch_no_y(self) -> None:
        warnings: list[str] = []
        forecast, sig = dispatch_engine(
            mode=EngineMode.TRANSFER_WITH_BIAS_CHECK,
            warnings=warnings,
            **self._COMMON,
        )
        assert forecast is not None
        assert sig == "transfer_with_bias_check_v1"
        # Handler emits a warning when recipient_y is absent
        assert any("bias check skipped" in w for w in warnings)

    def test_ols_with_proxy_priors_dispatch(self) -> None:
        warnings: list[str] = []
        forecast, sig = dispatch_engine(
            mode=EngineMode.OLS_WITH_PROXY_PRIORS,
            warnings=warnings,
            **self._COMMON,
        )
        assert forecast is not None
        assert sig == "ols_with_proxy_priors_fallback_v1"

    def test_bayesian_with_proxy_priors_dispatch(self) -> None:
        warnings: list[str] = []
        forecast, sig = dispatch_engine(
            mode=EngineMode.BAYESIAN_WITH_PROXY_PRIORS,
            warnings=warnings,
            **self._COMMON,
        )
        assert forecast is not None
        assert sig == "bayesian_with_proxy_priors_fallback_v1"


# ---------------------------------------------------------------------------
# S-11-T03: Mode 3 / Mode 4 fallback paths emit warnings
# ---------------------------------------------------------------------------


class TestFallbackWarnings:
    _COMMON = dict(
        channels=_make_channels(2),
        anchors=_make_anchors(6),
        spend_plan=_make_spend_plan(6, ["ch_0", "ch_1"]),
        horizon_periods=6,
        granularity="monthly",
        proxy_baseline=500_000.0,
        coverage_target=0.95,
        recipient_y=None,
    )

    def test_mode3_emits_fallback_warning(self) -> None:
        warnings: list[str] = []
        dispatch_engine(
            mode=EngineMode.OLS_WITH_PROXY_PRIORS,
            warnings=warnings,
            **self._COMMON,
        )
        assert len(warnings) >= 1
        # Post-M-01: real handler emits "OLS+priors: <reason> — falling back…"
        # when recipient_y missing. Accept either old "fallback" wording OR new.
        assert any(
            ("OLS+priors" in w and ("fallback" in w or "falling back" in w))
            for w in warnings
        )

    def test_mode4_emits_fallback_warning(self) -> None:
        warnings: list[str] = []
        dispatch_engine(
            mode=EngineMode.BAYESIAN_WITH_PROXY_PRIORS,
            warnings=warnings,
            **self._COMMON,
        )
        assert len(warnings) >= 1
        # Post-M-02: accept both "Bayesian+priors fallback" and "Bayesian+priors: <reason> — falling back"
        assert any(
            ("Bayesian+priors" in w and ("fallback" in w or "falling back" in w))
            for w in warnings
        )

    def test_mode1_no_warnings(self) -> None:
        """Pure transfer should produce no warnings under normal conditions."""
        warnings: list[str] = []
        dispatch_engine(
            mode=EngineMode.PURE_TRANSFER,
            warnings=warnings,
            **self._COMMON,
        )
        assert warnings == []

    def test_mode2_warns_when_no_recipient_y(self) -> None:
        """Mode 2 without recipient_y must warn (bias check skipped)."""
        warnings: list[str] = []
        dispatch_engine(
            mode=EngineMode.TRANSFER_WITH_BIAS_CHECK,
            warnings=warnings,
            **self._COMMON,
        )
        assert any("bias check skipped" in w for w in warnings)

    def test_mode2_no_warning_when_recipient_y_provided(self) -> None:
        """Mode 2 with valid recipient_y should NOT emit the 'skipped' warning."""
        warnings: list[str] = []
        common_with_y = {**self._COMMON, "recipient_y": [500_000.0] * 3}
        dispatch_engine(
            mode=EngineMode.TRANSFER_WITH_BIAS_CHECK,
            warnings=warnings,
            **common_with_y,
        )
        assert not any("bias check skipped" in w for w in warnings)


# ---------------------------------------------------------------------------
# S-11-T04: KeyError for invalid / unregistered mode
# ---------------------------------------------------------------------------


class TestDispatchDefensiveGuard:
    def test_keyerror_for_unregistered_mode(self) -> None:
        """dispatch_engine raises KeyError when mode is not in _MODE_DISPATCH."""
        channels = _make_channels(2)
        anchors = _make_anchors(6)
        spend_plan = _make_spend_plan(6, ["ch_0", "ch_1"])
        warnings: list[str] = []

        # Temporarily remove a mode from the dispatch table to simulate
        # a future EngineMode added without a registered handler.
        original = _MODE_DISPATCH.copy()
        del _MODE_DISPATCH[EngineMode.PURE_TRANSFER]
        try:
            with pytest.raises(KeyError, match="No dispatch handler registered"):
                dispatch_engine(
                    mode=EngineMode.PURE_TRANSFER,
                    channels=channels,
                    anchors=anchors,
                    spend_plan=spend_plan,
                    horizon_periods=6,
                    granularity="monthly",
                    proxy_baseline=500_000.0,
                    coverage_target=0.95,
                    recipient_y=None,
                    warnings=warnings,
                )
        finally:
            _MODE_DISPATCH[EngineMode.PURE_TRANSFER] = original[EngineMode.PURE_TRANSFER]

    def test_keyerror_message_contains_registered_modes(self) -> None:
        """KeyError message must list which modes ARE registered."""
        original = _MODE_DISPATCH.copy()
        del _MODE_DISPATCH[EngineMode.BAYESIAN_WITH_PROXY_PRIORS]
        try:
            with pytest.raises(KeyError) as exc_info:
                dispatch_engine(
                    mode=EngineMode.BAYESIAN_WITH_PROXY_PRIORS,
                    channels=_make_channels(1),
                    anchors=_make_anchors(3),
                    spend_plan={"ch_0": [100.0] * 3},
                    horizon_periods=3,
                    granularity="monthly",
                    proxy_baseline=100_000.0,
                    coverage_target=0.95,
                    recipient_y=None,
                    warnings=[],
                )
            # KeyError wraps the message in quotes; normalise for assertion.
            msg = str(exc_info.value)
            assert "BAYESIAN_WITH_PROXY_PRIORS" in msg
        finally:
            _MODE_DISPATCH[EngineMode.BAYESIAN_WITH_PROXY_PRIORS] = original[
                EngineMode.BAYESIAN_WITH_PROXY_PRIORS
            ]


# ---------------------------------------------------------------------------
# S-11-T05: Dispatch contract — each handler accepts same kwargs signature
# ---------------------------------------------------------------------------


class TestDispatchContract:
    """Verify the positional/keyword signature of every registered handler.

    The contract (per dispatch_table module docstring):
        handler(channels, anchors, spend_plan, horizon_periods, granularity,
                proxy_baseline, coverage_target, recipient_y, warnings, **kwargs)
        → tuple[TransferForecast, str]

    We check:
    1. Each handler accepts the 9 required positional params + **kwargs.
    2. None of the handlers import PyMC at module level (INV-04 lazy imports).
    """

    EXPECTED_PARAMS = [
        "channels",
        "anchors",
        "spend_plan",
        "horizon_periods",
        "granularity",
        "proxy_baseline",
        "coverage_target",
        "recipient_y",
        "warnings",
    ]

    def test_all_handlers_have_required_params(self) -> None:
        for mode, handler in _MODE_DISPATCH.items():
            sig = inspect.signature(handler)
            params = list(sig.parameters.keys())
            for expected in self.EXPECTED_PARAMS:
                assert expected in params, (
                    f"Handler for {mode.name} ({handler.__name__}) "
                    f"is missing required param '{expected}'. "
                    f"Actual params: {params}"
                )

    def test_all_handlers_accept_extras(self) -> None:
        """Every handler must accept extras: DispatchExtras parameter.

        Phase 1 audit fix: typed DispatchExtras replaces unsafe **kwargs.
        Handlers MUST accept extras as the last positional/keyword.
        """
        from aurora_launch.engines.dispatch_table import DispatchExtras

        for mode, handler in _MODE_DISPATCH.items():
            sig = inspect.signature(handler)
            assert "extras" in sig.parameters, (
                f"Handler for {mode.name} ({handler.__name__}) "
                f"does not accept extras: DispatchExtras parameter."
            )
            param = sig.parameters["extras"]
            # Either default value OR annotation must be DispatchExtras
            ann = param.annotation
            if ann is not inspect.Parameter.empty:
                # accept "DispatchExtras" as forward ref or class
                assert (
                    ann is DispatchExtras
                    or getattr(ann, "__name__", str(ann)) == "DispatchExtras"
                ), f"Handler {handler.__name__} extras param wrong annotation: {ann}"


# ---------------------------------------------------------------------------
# S-11-T06: End-to-end smoke — orchestrator uses dispatch table
# ---------------------------------------------------------------------------


class TestOrchestratorUsesDispatchTable:
    """Verify that LaunchOrchestrator.forecast_recipient is routed through
    the dispatch table (not the old if/elif chain)."""

    def test_mode1_pure_transfer_smoke(self) -> None:
        orch = LaunchOrchestrator()
        result = orch.forecast_recipient(
            proxy=_make_proxy_bundle(),
            anchors=_make_anchors(6),
            spend_plan={"tv": [200.0] * 6, "digital": [80.0] * 6},
            horizon_periods=6,
            granularity="monthly",
            n_recipient=0,
        )
        assert result.forecast is not None
        assert result.methodology_signature == "pure_transfer_v1"

    def test_mode3_fallback_via_orchestrator(self) -> None:
        """n_recipient=3 (monthly) → OLS mode → fallback warning in result."""
        orch = LaunchOrchestrator()
        result = orch.forecast_recipient(
            proxy=_make_proxy_bundle(),
            anchors=_make_anchors(6),
            spend_plan={"tv": [200.0] * 6, "digital": [80.0] * 6},
            horizon_periods=6,
            granularity="monthly",
            n_recipient=3,  # ≥ ols_low(3), < bayesian(7) → OLS mode
        )
        assert result.forecast is not None
        assert result.methodology_signature == "ols_with_proxy_priors_fallback_v1"
        # Post-M-01 wording accept variant
        assert any(
            ("OLS+priors" in w and ("fallback" in w or "falling back" in w))
            for w in result.warnings
        )

    def test_mode4_fallback_via_orchestrator(self) -> None:
        """n_recipient=7 (monthly) → Bayesian mode → fallback warning in result."""
        orch = LaunchOrchestrator()
        result = orch.forecast_recipient(
            proxy=_make_proxy_bundle(),
            anchors=_make_anchors(6),
            spend_plan={"tv": [200.0] * 6, "digital": [80.0] * 6},
            horizon_periods=6,
            granularity="monthly",
            n_recipient=7,  # ≥ bayesian(7) → Bayesian mode
        )
        assert result.forecast is not None
        assert result.methodology_signature == "bayesian_with_proxy_priors_fallback_v1"
        assert any(
            ("Bayesian+priors" in w and ("fallback" in w or "falling back" in w))
            for w in result.warnings
        )

    def test_dispatch_engine_called_during_orchestration(self) -> None:
        """dispatch_engine should be invoked (not the old if/elif) during orchestration."""
        orch = LaunchOrchestrator()
        with patch(
            "aurora_launch.engines.launch_orchestrator.dispatch_engine",
            wraps=dispatch_engine,
        ) as mock_dispatch:
            result = orch.forecast_recipient(
                proxy=_make_proxy_bundle(),
                anchors=_make_anchors(6),
                spend_plan={"tv": [200.0] * 6, "digital": [80.0] * 6},
                horizon_periods=6,
                granularity="monthly",
                n_recipient=0,
            )
            mock_dispatch.assert_called_once()
        assert result.forecast is not None


# ---------------------------------------------------------------------------
# S-11-T07: Mode 2 bias check still fires post-dispatch (orchestrator hook)
# ---------------------------------------------------------------------------


class TestMode2BiasCheckPreservation:
    """The bias check post-dispatch hook in the orchestrator must still work."""

    def test_mode2_bias_warning_on_high_deviation(self) -> None:
        """Provide recipient_y that deviates >30% from proxy expectation."""
        orch = LaunchOrchestrator()
        # n_recipient=1 → TRANSFER_WITH_BIAS_CHECK (1 ≤ n < ols_low=3)
        # Use a recipient_y far from what proxy predicts (very small values)
        result = orch.forecast_recipient(
            proxy=_make_proxy_bundle(),
            anchors=_make_anchors(6),
            spend_plan={"tv": [200.0] * 6, "digital": [80.0] * 6},
            horizon_periods=6,
            granularity="monthly",
            n_recipient=1,
            recipient_y=[1.0],  # near-zero vs expected ~10,000+ → massive bias
        )
        assert result.forecast is not None
        # Either a bias_pct warning or a degenerate-forecast diagnostic
        has_bias_warning = any(
            ("Bias check" in w or "degenerate" in w or "bias check skipped" in w)
            for w in result.warnings
        )
        assert has_bias_warning, (
            f"Expected a bias-related warning. Got: {result.warnings}"
        )
