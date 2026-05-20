"""Tests for ``aurora_launch.utils.mcmc_budget_check`` (Sprint 2 D5)."""

from __future__ import annotations

import threading
import time
from collections import namedtuple
from typing import Any, Callable
from unittest.mock import patch

import pytest

from aurora_launch.utils import mcmc_budget_check as mbc
from aurora_launch.utils.mcmc_budget_check import (
    ABORT_RAM_THRESHOLD_PCT,
    MIN_RAM_AVAILABLE_BYTES,
    BudgetCheckResult,
    MemoryMonitor,
    check_mcmc_budget,
    format_bytes_human,
)


# ─── Test helpers ─────────────────────────────────────────────────────────────


_VMem = namedtuple("VMem", ["total", "available", "percent", "used", "free"])


def _make_vmem(
    *,
    available: int = 8_000_000_000,
    total: int = 16_000_000_000,
    percent: float = 50.0,
) -> _VMem:
    """Build a psutil.svmem-shaped tuple для monkeypatch."""
    used = total - available
    return _VMem(total=total, available=available, percent=percent, used=used, free=available)


# ─── check_mcmc_budget — boundary + status mapping ────────────────────────────


class TestCheckMcmcBudgetStatusMapping:
    """Verify status mapping against ``min_required_bytes`` thresholds."""

    def test_status_ok_when_available_above_minimum(self) -> None:
        with patch.object(mbc.psutil, "virtual_memory", return_value=_make_vmem(available=8_000_000_000)):
            result = check_mcmc_budget()
        assert result.status == "ok"
        assert result.suggested_fallback is None
        assert "достаточно" in result.recommendation.lower()
        assert result.available_bytes == 8_000_000_000

    def test_status_ok_at_exact_minimum_boundary(self) -> None:
        with patch.object(mbc.psutil, "virtual_memory", return_value=_make_vmem(available=MIN_RAM_AVAILABLE_BYTES)):
            result = check_mcmc_budget()
        assert result.status == "ok", "available == min_required should be inclusive"

    def test_status_low_ram_between_half_and_full(self) -> None:
        # 3 GB available, min 4 GB — between half (2 GB) and full (4 GB)
        with patch.object(mbc.psutil, "virtual_memory", return_value=_make_vmem(available=3_000_000_000)):
            result = check_mcmc_budget()
        assert result.status == "low_ram"
        assert result.suggested_fallback == "ols"
        assert "OLS" in result.recommendation

    def test_status_low_ram_at_half_threshold(self) -> None:
        half = MIN_RAM_AVAILABLE_BYTES // 2
        with patch.object(mbc.psutil, "virtual_memory", return_value=_make_vmem(available=half)):
            result = check_mcmc_budget()
        assert result.status == "low_ram", "available == half should be inclusive of low_ram"

    def test_status_critical_below_half(self) -> None:
        # 1 GB available — below 2 GB half threshold
        with patch.object(mbc.psutil, "virtual_memory", return_value=_make_vmem(available=1_000_000_000)):
            result = check_mcmc_budget()
        assert result.status == "critical"
        assert result.suggested_fallback == "ols"
        assert "почти наверняка упадёт" in result.recommendation

    def test_custom_min_required_bytes(self) -> None:
        # With min=8 GB, 5 GB available → low_ram (between half 4 GB and full 8 GB)
        with patch.object(mbc.psutil, "virtual_memory", return_value=_make_vmem(available=5_000_000_000)):
            result = check_mcmc_budget(min_required_bytes=8_000_000_000)
        assert result.status == "low_ram"

    def test_raises_on_zero_min_required(self) -> None:
        with pytest.raises(ValueError, match="must be positive"):
            check_mcmc_budget(min_required_bytes=0)

    def test_raises_on_negative_min_required(self) -> None:
        with pytest.raises(ValueError, match="must be positive"):
            check_mcmc_budget(min_required_bytes=-100)

    def test_result_includes_diagnostic_snapshot(self) -> None:
        with patch.object(
            mbc.psutil,
            "virtual_memory",
            return_value=_make_vmem(available=10_000_000_000, total=16_000_000_000, percent=37.5),
        ):
            result = check_mcmc_budget()
        assert result.available_bytes == 10_000_000_000
        assert result.total_bytes == 16_000_000_000
        assert result.used_pct == 37.5

    def test_result_is_frozen_dataclass(self) -> None:
        with patch.object(mbc.psutil, "virtual_memory", return_value=_make_vmem()):
            result = check_mcmc_budget()
        with pytest.raises(Exception):
            result.status = "tampered"  # type: ignore[misc]


# ─── MemoryMonitor — abort behaviour ──────────────────────────────────────────


class TestMemoryMonitor:
    """Verify polling, abort thresholds, callbacks, lifecycle."""

    def test_abort_triggers_when_threshold_crossed(self) -> None:
        # Memory at 85% > 80% threshold — should abort on first poll
        with patch.object(mbc.psutil, "virtual_memory", return_value=_make_vmem(percent=85.0)):
            monitor = MemoryMonitor(poll_interval_s=0.05)
            monitor.start()
            try:
                aborted = monitor.aborted.wait(timeout=1.0)
            finally:
                monitor.stop()
            assert aborted, "Monitor should have set aborted within 1s"
            assert monitor.last_reading_pct == 85.0

    def test_no_abort_below_threshold(self) -> None:
        with patch.object(mbc.psutil, "virtual_memory", return_value=_make_vmem(percent=50.0)):
            monitor = MemoryMonitor(poll_interval_s=0.05)
            monitor.start()
            try:
                time.sleep(0.3)  # 5-6 polls
            finally:
                monitor.stop()
            assert not monitor.aborted.is_set()
            assert monitor.last_reading_pct == 50.0

    def test_on_abort_callback_invoked_with_pct_and_message(self) -> None:
        captured: dict[str, Any] = {}

        def on_abort(used_pct: float, message: str) -> None:
            captured["used_pct"] = used_pct
            captured["message"] = message

        with patch.object(mbc.psutil, "virtual_memory", return_value=_make_vmem(percent=90.0)):
            monitor = MemoryMonitor(poll_interval_s=0.05, on_abort=on_abort)
            monitor.start()
            try:
                monitor.aborted.wait(timeout=1.0)
            finally:
                monitor.stop()
        assert captured.get("used_pct") == 90.0
        assert "90" in captured.get("message", "")
        assert "Прерываем MCMC" in captured.get("message", "")

    def test_callback_exception_swallowed_not_propagated(self) -> None:
        # If the user's on_abort raises, monitor should log + continue cleanup,
        # NOT propagate the exception to caller thread.
        def buggy_callback(_pct: float, _msg: str) -> None:
            raise RuntimeError("buggy hook")

        with patch.object(mbc.psutil, "virtual_memory", return_value=_make_vmem(percent=85.0)):
            monitor = MemoryMonitor(poll_interval_s=0.05, on_abort=buggy_callback)
            monitor.start()
            try:
                monitor.aborted.wait(timeout=1.0)
            finally:
                # stop() should not raise even though callback raised
                monitor.stop()
        # If we reach here without exception → swallow works
        assert monitor.aborted.is_set()

    def test_context_manager_starts_and_stops(self) -> None:
        with patch.object(mbc.psutil, "virtual_memory", return_value=_make_vmem(percent=50.0)):
            with MemoryMonitor(poll_interval_s=0.05) as monitor:
                time.sleep(0.15)
                assert monitor._thread is not None
                assert monitor._thread.is_alive()
            # After context exit thread should be stopped
            assert monitor._thread is None

    def test_double_start_raises_runtime_error(self) -> None:
        with patch.object(mbc.psutil, "virtual_memory", return_value=_make_vmem(percent=50.0)):
            monitor = MemoryMonitor(poll_interval_s=0.05)
            monitor.start()
            try:
                with pytest.raises(RuntimeError, match="already started"):
                    monitor.start()
            finally:
                monitor.stop()

    def test_psutil_transient_error_does_not_kill_loop(self) -> None:
        # First call raises, subsequent calls return normal value → loop survives
        call_count = {"n": 0}

        def flaky_vmem() -> _VMem:
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise OSError("transient psutil failure")
            return _make_vmem(percent=85.0)

        with patch.object(mbc.psutil, "virtual_memory", side_effect=flaky_vmem):
            monitor = MemoryMonitor(poll_interval_s=0.05)
            monitor.start()
            try:
                aborted = monitor.aborted.wait(timeout=1.0)
            finally:
                monitor.stop()
            assert aborted, "Monitor should recover from transient psutil error"

    def test_invalid_threshold_raises(self) -> None:
        with pytest.raises(ValueError, match="abort_threshold_pct"):
            MemoryMonitor(abort_threshold_pct=0.0)
        with pytest.raises(ValueError, match="abort_threshold_pct"):
            MemoryMonitor(abort_threshold_pct=150.0)

    def test_invalid_poll_interval_raises(self) -> None:
        with pytest.raises(ValueError, match="poll_interval_s"):
            MemoryMonitor(poll_interval_s=0.0)
        with pytest.raises(ValueError, match="poll_interval_s"):
            MemoryMonitor(poll_interval_s=-1.0)

    def test_default_threshold_matches_module_constant(self) -> None:
        monitor = MemoryMonitor()
        assert monitor._threshold == ABORT_RAM_THRESHOLD_PCT


# ─── format_bytes_human — locale + unit transitions ───────────────────────────


class TestFormatBytesHuman:
    """Locale-friendly byte rendering."""

    def test_renders_bytes_under_kilobyte(self) -> None:
        assert format_bytes_human(0) == "0 Б"
        assert format_bytes_human(512) == "512 Б"
        assert format_bytes_human(1023) == "1023 Б"

    def test_renders_kilobytes(self) -> None:
        assert format_bytes_human(1024) == "1.0 КБ"
        assert format_bytes_human(2048) == "2.0 КБ"

    def test_renders_megabytes(self) -> None:
        assert format_bytes_human(1024 ** 2) == "1.0 МБ"
        assert format_bytes_human(5 * 1024 ** 2) == "5.0 МБ"

    def test_renders_gigabytes(self) -> None:
        assert format_bytes_human(1024 ** 3) == "1.00 ГБ"
        assert format_bytes_human(int(2.5 * 1024 ** 3)) == "2.50 ГБ"

    def test_renders_4gb_threshold_near_min_required(self) -> None:
        # 4_000_000_000 = ~3.73 GiB — under-4-GB рендер
        out = format_bytes_human(MIN_RAM_AVAILABLE_BYTES)
        assert "ГБ" in out
        assert out.startswith("3.")

    def test_renders_negative_with_unicode_minus(self) -> None:
        assert format_bytes_human(-512) == "−512 Б"
        assert format_bytes_human(-1024 ** 3).startswith("−")


# ─── Cross-module: status returned and serializable ──────────────────────────


class TestBudgetCheckResultSerialization:
    """Ensure BudgetCheckResult fields are JSON-compatible for IPC return."""

    def test_all_fields_are_json_compatible(self) -> None:
        import json

        with patch.object(mbc.psutil, "virtual_memory", return_value=_make_vmem()):
            result = check_mcmc_budget()
        payload = {
            "status": result.status,
            "available_bytes": result.available_bytes,
            "total_bytes": result.total_bytes,
            "used_pct": result.used_pct,
            "recommendation": result.recommendation,
            "suggested_fallback": result.suggested_fallback,
        }
        encoded = json.dumps(payload, ensure_ascii=False)
        decoded = json.loads(encoded)
        assert decoded["status"] in ("ok", "low_ram", "critical")
        assert decoded["suggested_fallback"] in ("bayesian", "ols", None)


# ─── IPC handler regression — check_mcmc_budget JSON-RPC entrypoint ──────────


class TestCheckMcmcBudgetHandler:
    """Regression tests for the sidecar JSON-RPC handler wrapper."""

    def test_handler_returns_status_recommendation_and_fallback(self) -> None:
        from aurora_launch.sidecar.methods_forecast import _check_mcmc_budget

        with patch.object(mbc.psutil, "virtual_memory", return_value=_make_vmem(available=10_000_000_000)):
            result = _check_mcmc_budget({})
        assert result["status"] == "ok"
        assert result["suggested_fallback"] is None
        assert isinstance(result["recommendation"], str)
        assert result["available_bytes"] == 10_000_000_000

    def test_handler_accepts_custom_min_required_bytes(self) -> None:
        from aurora_launch.sidecar.methods_forecast import _check_mcmc_budget

        # 5 GB available, custom min 8 GB → low_ram (5 GB ≥ half=4 GB)
        with patch.object(mbc.psutil, "virtual_memory", return_value=_make_vmem(available=5_000_000_000)):
            result = _check_mcmc_budget({"min_required_bytes": 8_000_000_000})
        assert result["status"] == "low_ram"
        assert result["suggested_fallback"] == "ols"

    def test_handler_rejects_invalid_min_required_bytes_type(self) -> None:
        from aurora_launch.sidecar.methods_forecast import _check_mcmc_budget

        with pytest.raises(ValueError, match="invalid min_required_bytes"):
            _check_mcmc_budget({"min_required_bytes": "four gigabytes"})

    def test_handler_rejects_zero_min_required_bytes(self) -> None:
        from aurora_launch.sidecar.methods_forecast import _check_mcmc_budget

        with pytest.raises(ValueError, match="must be positive"):
            _check_mcmc_budget({"min_required_bytes": 0})

    def test_handler_payload_serializable_through_json(self) -> None:
        """End-to-end: handler return value → JSON encoded → decoded losslessly."""
        import json

        from aurora_launch.sidecar.methods_forecast import _check_mcmc_budget

        with patch.object(mbc.psutil, "virtual_memory", return_value=_make_vmem(available=1_000_000_000)):
            result = _check_mcmc_budget({})
        encoded = json.dumps(result, ensure_ascii=False)
        decoded = json.loads(encoded)
        assert decoded["status"] == "critical"
        assert decoded["suggested_fallback"] == "ols"
        assert "почти наверняка упадёт" in decoded["recommendation"]
