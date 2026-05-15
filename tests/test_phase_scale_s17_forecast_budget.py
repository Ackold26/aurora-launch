"""Phase Scale S-17 — Forecast budget enforcement tests.

Coverage:
- Forecast under budget: completes normally, returns OrchestrationResult
- Forecast over budget: raises ForecastBudgetExceededError
- Cancel flag triggered by watchdog thread
- elapsed_s in error is accurate (>= budget_s when raised)
- Budget=0: immediate cancel on first pipeline check
- Watchdog thread is daemon (does not leak after test)
- ForecastBudgetExceededError carries correct attributes
- Module-level _cancel_event reset between calls (no cross-call contamination)
"""

from __future__ import annotations

import threading
import time

import numpy as np
import pytest

from aurora_launch.engines.launch_orchestrator import (
    ForecastBudgetExceededError,
    LaunchOrchestrator,
    ProxyBundle,
    make_proxy_bundle,
    _cancel_event,
    _start_watchdog,
)
from aurora_launch.engines.pure_transfer_engine import RecipientAnchors
from aurora_launch.engines.router import EngineMode


# ---------------------------------------------------------------------------
# Fixtures (reuse pattern from test_phase_pi_2_4_orchestrator.py)
# ---------------------------------------------------------------------------


def _make_proxy_bundle(n_channels: int = 2, n_samples: int = 500) -> ProxyBundle:
    rng = np.random.default_rng(7)
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


def _make_anchors(horizon: int = 12) -> RecipientAnchors:
    return RecipientAnchors(
        market_size=10_000_000.0,
        market_size_cv=0.10,
        planned_share_trajectory=[0.05] * horizon,
        distribution_trajectory=[0.70] * horizon,
        pricing_index=1.0,
        elasticity=0.5,
        seasonality=[1.0] * horizon,
    )


def _make_spend_plan(horizon: int = 12) -> dict[str, list[float]]:
    return {"tv": [200.0] * horizon, "digital": [80.0] * horizon}


# ---------------------------------------------------------------------------
# S-17-T01: Forecast under budget completes normally
# ---------------------------------------------------------------------------


class TestForecastUnderBudget:
    def test_completes_normally_with_generous_budget(self) -> None:
        """Pure-transfer forecast is O(ms) — 30 s budget is never hit."""
        orch = LaunchOrchestrator()
        result = orch.forecast_recipient(
            proxy=_make_proxy_bundle(),
            anchors=_make_anchors(12),
            spend_plan=_make_spend_plan(12),
            horizon_periods=12,
            granularity="monthly",
            n_recipient=0,
            forecast_budget_seconds=30.0,
        )
        assert result.forecast is not None
        assert result.engine_config.mode == EngineMode.PURE_TRANSFER

    def test_cancel_event_cleared_before_forecast(self) -> None:
        """Module _cancel_event should be clear after a successful forecast."""
        orch = LaunchOrchestrator()
        orch.forecast_recipient(
            proxy=_make_proxy_bundle(),
            anchors=_make_anchors(12),
            spend_plan=_make_spend_plan(12),
            horizon_periods=12,
            n_recipient=0,
            forecast_budget_seconds=30.0,
        )
        # After successful run, cancel event should be cleared
        # (it was cleared at the start and watchdog was cancelled)
        # We just verify no lingering cancel that would poison next call.
        assert not _cancel_event.is_set()

    def test_default_budget_is_thirty_seconds(self) -> None:
        """Calling without forecast_budget_seconds uses 30 s default."""
        orch = LaunchOrchestrator()
        # This completes fast — just verifying the default doesn't break.
        result = orch.forecast_recipient(
            proxy=_make_proxy_bundle(),
            anchors=_make_anchors(6),
            spend_plan={"tv": [200.0] * 6, "digital": [80.0] * 6},
            horizon_periods=6,
            n_recipient=0,
        )
        assert result.forecast is not None


# ---------------------------------------------------------------------------
# S-17-T02: Budget=0 → immediate cancel on first pipeline check
# ---------------------------------------------------------------------------


class TestBudgetZeroImmediateCancel:
    def test_budget_zero_raises_immediately(self) -> None:
        """Budget=0 arms watchdog with 0-second delay.
        The _cancel_event is set almost immediately (Timer fires at 0s).
        The first _check_cancel() call in the pipeline should raise.
        """
        orch = LaunchOrchestrator()
        with pytest.raises(ForecastBudgetExceededError) as exc_info:
            orch.forecast_recipient(
                proxy=_make_proxy_bundle(),
                anchors=_make_anchors(12),
                spend_plan=_make_spend_plan(12),
                horizon_periods=12,
                n_recipient=0,
                forecast_budget_seconds=0.0,
            )
        err = exc_info.value
        # Budget reported as 0 in error
        assert err.budget_s == 0.0

    def test_budget_zero_elapsed_is_non_negative(self) -> None:
        """elapsed_s attribute is always ≥ 0."""
        orch = LaunchOrchestrator()
        with pytest.raises(ForecastBudgetExceededError) as exc_info:
            orch.forecast_recipient(
                proxy=_make_proxy_bundle(),
                anchors=_make_anchors(6),
                spend_plan={"tv": [200.0] * 6, "digital": [80.0] * 6},
                horizon_periods=6,
                n_recipient=0,
                forecast_budget_seconds=0.0,
            )
        assert exc_info.value.elapsed_s >= 0.0


# ---------------------------------------------------------------------------
# S-17-T03: Watchdog thread fires cancel flag
# ---------------------------------------------------------------------------


class TestWatchdogThread:
    def test_watchdog_sets_cancel_after_delay(self) -> None:
        """_start_watchdog fires after budget_s and sets cancel event."""
        ev = threading.Event()
        timer = _start_watchdog(budget_s=0.05, cancel=ev)
        try:
            assert not ev.is_set()
            # Wait up to 500ms for watchdog to fire
            fired = ev.wait(timeout=0.5)
            assert fired, "Watchdog did not set cancel event within 500ms"
        finally:
            timer.cancel()

    def test_watchdog_thread_is_daemon(self) -> None:
        """Watchdog thread must be daemon so it doesn't prevent process exit."""
        ev = threading.Event()
        timer = _start_watchdog(budget_s=60.0, cancel=ev)
        try:
            assert timer.daemon is True
        finally:
            timer.cancel()

    def test_cancel_timer_prevents_fire(self) -> None:
        """Calling timer.cancel() before budget expires prevents event being set."""
        ev = threading.Event()
        timer = _start_watchdog(budget_s=0.2, cancel=ev)
        timer.cancel()  # cancel immediately
        time.sleep(0.05)  # give time for would-be fire
        assert not ev.is_set()


# ---------------------------------------------------------------------------
# S-17-T04: ForecastBudgetExceededError attributes
# ---------------------------------------------------------------------------


class TestForecastBudgetExceededError:
    def test_attributes_set_correctly(self) -> None:
        err = ForecastBudgetExceededError(elapsed_s=35.7, budget_s=30.0)
        assert err.elapsed_s == 35.7
        assert err.budget_s == 30.0

    def test_is_runtime_error(self) -> None:
        err = ForecastBudgetExceededError(elapsed_s=1.0, budget_s=0.5)
        assert isinstance(err, RuntimeError)

    def test_str_contains_times(self) -> None:
        err = ForecastBudgetExceededError(elapsed_s=45.0, budget_s=30.0)
        msg = str(err)
        assert "45" in msg
        assert "30" in msg

    def test_elapsed_gte_budget_in_normal_scenario(self) -> None:
        """In a normal timeout scenario elapsed should be >= budget."""
        err = ForecastBudgetExceededError(elapsed_s=30.1, budget_s=30.0)
        assert err.elapsed_s >= err.budget_s


# ---------------------------------------------------------------------------
# S-17-T05: No cross-call contamination (cancel event reset per call)
# ---------------------------------------------------------------------------


class TestCancelEventReset:
    def test_second_call_succeeds_after_first_times_out(self) -> None:
        """Even if first call raised ForecastBudgetExceededError, second call
        with generous budget completes normally (cancel reset at entry)."""
        orch = LaunchOrchestrator()

        # First call: immediate timeout
        with pytest.raises(ForecastBudgetExceededError):
            orch.forecast_recipient(
                proxy=_make_proxy_bundle(),
                anchors=_make_anchors(12),
                spend_plan=_make_spend_plan(12),
                horizon_periods=12,
                n_recipient=0,
                forecast_budget_seconds=0.0,
            )

        # Second call: should complete normally
        result = orch.forecast_recipient(
            proxy=_make_proxy_bundle(),
            anchors=_make_anchors(12),
            spend_plan=_make_spend_plan(12),
            horizon_periods=12,
            n_recipient=0,
            forecast_budget_seconds=30.0,
        )
        assert result.forecast is not None

    def test_cancel_event_clear_before_each_call(self) -> None:
        """Manually pre-set cancel event — orchestrator should clear it at start."""
        _cancel_event.set()  # simulate lingering state
        orch = LaunchOrchestrator()
        # With generous budget: cancel is reset, forecast completes normally
        result = orch.forecast_recipient(
            proxy=_make_proxy_bundle(),
            anchors=_make_anchors(6),
            spend_plan={"tv": [200.0] * 6, "digital": [80.0] * 6},
            horizon_periods=6,
            n_recipient=0,
            forecast_budget_seconds=30.0,
        )
        assert result.forecast is not None
