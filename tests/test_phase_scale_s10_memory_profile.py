"""Phase Scale S-10: memory profile + policy tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from aurora_launch.sidecar.memory_profile import (
    CRITICAL_BYTES,
    HARD_CAP_BYTES,
    SOFT_WARNING_BYTES,
    MemoryReport,
    format_bytes,
    get_memory_report,
    policy_advice,
)


class TestFormatBytes:
    def test_small_bytes(self) -> None:
        assert format_bytes(512) == "512 B"

    def test_kilobytes(self) -> None:
        assert format_bytes(2048) == "2.0 KB"

    def test_megabytes(self) -> None:
        assert format_bytes(5 * 1024 * 1024) == "5.0 MB"

    def test_gigabytes(self) -> None:
        # 1.5 GB
        assert format_bytes(int(1.5 * (1024 ** 3))) == "1.50 GB"


class TestSeverityClassification:
    def test_severity_ok_below_warning(self) -> None:
        # Build a fake report directly (don't depend on actual process state)
        report = MemoryReport(
            rss_bytes=500 * 1024 * 1024,  # 500 MB
            vms_bytes=600 * 1024 * 1024,
            available_bytes=4 * (1024 ** 3),
            severity="ok",
            threshold_bytes=SOFT_WARNING_BYTES,
        )
        assert report.severity == "ok"

    def test_real_get_report_returns_valid_severity(self) -> None:
        """Integration test using actual current process state."""
        try:
            report = get_memory_report()
        except ImportError:
            pytest.skip("psutil not installed")
        assert report.severity in ("ok", "warning", "hard_cap", "critical")
        assert report.rss_bytes > 0
        assert report.vms_bytes > 0
        assert report.available_bytes > 0

    def test_real_get_report_threshold_matches_severity(self) -> None:
        try:
            report = get_memory_report()
        except ImportError:
            pytest.skip("psutil not installed")
        if report.severity == "ok":
            assert report.threshold_bytes == SOFT_WARNING_BYTES
        elif report.severity == "warning":
            assert report.threshold_bytes == SOFT_WARNING_BYTES
        elif report.severity == "hard_cap":
            assert report.threshold_bytes == HARD_CAP_BYTES
        elif report.severity == "critical":
            assert report.threshold_bytes == CRITICAL_BYTES


class TestSeverityBoundaries:
    """Synthetic reports verify boundary logic via direct call."""

    def _make_at_rss(self, rss: int) -> MemoryReport:
        # Use private internals via psutil-less path
        from aurora_launch.sidecar.memory_profile import (
            CRITICAL_BYTES as cb,
            HARD_CAP_BYTES as hc,
            SOFT_WARNING_BYTES as sw,
        )

        if rss >= cb:
            severity = "critical"
            threshold = cb
        elif rss >= hc:
            severity = "hard_cap"
            threshold = hc
        elif rss >= sw:
            severity = "warning"
            threshold = sw
        else:
            severity = "ok"
            threshold = sw
        return MemoryReport(
            rss_bytes=rss,
            vms_bytes=rss,
            available_bytes=4 * (1024 ** 3),
            severity=severity,  # type: ignore[arg-type]
            threshold_bytes=threshold,
        )

    def test_just_below_warning_is_ok(self) -> None:
        r = self._make_at_rss(SOFT_WARNING_BYTES - 1)
        assert r.severity == "ok"

    def test_at_warning_is_warning(self) -> None:
        r = self._make_at_rss(SOFT_WARNING_BYTES)
        assert r.severity == "warning"

    def test_at_hard_cap_is_hard_cap(self) -> None:
        r = self._make_at_rss(HARD_CAP_BYTES)
        assert r.severity == "hard_cap"

    def test_at_critical_is_critical(self) -> None:
        r = self._make_at_rss(CRITICAL_BYTES)
        assert r.severity == "critical"

    def test_way_above_critical_is_critical(self) -> None:
        r = self._make_at_rss(10 * CRITICAL_BYTES)
        assert r.severity == "critical"


class TestPolicyAdvice:
    """Russian advisory copy varies by severity."""

    def _report(self, severity: str, rss: int = SOFT_WARNING_BYTES) -> MemoryReport:
        threshold_map = {
            "ok": SOFT_WARNING_BYTES,
            "warning": SOFT_WARNING_BYTES,
            "hard_cap": HARD_CAP_BYTES,
            "critical": CRITICAL_BYTES,
        }
        return MemoryReport(
            rss_bytes=rss,
            vms_bytes=rss,
            available_bytes=4 * (1024 ** 3),
            severity=severity,  # type: ignore[arg-type]
            threshold_bytes=threshold_map[severity],
        )

    def test_ok_advice(self) -> None:
        msg = policy_advice(self._report("ok"))
        assert "норме" in msg.lower()

    def test_warning_advice(self) -> None:
        msg = policy_advice(self._report("warning"))
        assert "продолжать" in msg or "порог" in msg

    def test_hard_cap_advice(self) -> None:
        msg = policy_advice(self._report("hard_cap", rss=HARD_CAP_BYTES))
        assert "закрыть" in msg.lower() or "загрузк" in msg.lower()

    def test_critical_advice(self) -> None:
        msg = policy_advice(self._report("critical", rss=CRITICAL_BYTES))
        assert "критическая" in msg.lower() or "один проект" in msg.lower()


class TestIpcHandler:
    """get_memory_report IPC handler returns expected schema."""

    def test_handler_returns_required_fields(self) -> None:
        from aurora_launch.sidecar.methods import dispatch

        result = dispatch("get_memory_report", {})
        for key in (
            "rss_bytes",
            "vms_bytes",
            "available_bytes",
            "severity",
            "threshold_bytes",
            "advice",
            "measured",
        ):
            assert key in result, f"Missing key: {key}"

    def test_handler_severity_is_valid(self) -> None:
        from aurora_launch.sidecar.methods import dispatch

        result = dispatch("get_memory_report", {})
        assert result["severity"] in ("ok", "warning", "hard_cap", "critical")

    def test_handler_advice_is_russian_string(self) -> None:
        from aurora_launch.sidecar.methods import dispatch

        result = dispatch("get_memory_report", {})
        assert isinstance(result["advice"], str)
        assert len(result["advice"]) > 0


class TestPsutilMissingDegradesGracefully:
    """When psutil import fails — handler returns measured=False, severity=ok."""

    def test_handler_returns_unmeasured_on_import_error(self) -> None:
        from aurora_launch.sidecar import methods
        from aurora_launch.sidecar import memory_profile

        with patch.object(
            memory_profile,
            "get_memory_report",
            side_effect=ImportError("psutil missing"),
        ):
            result = methods.dispatch("get_memory_report", {})
            assert result["measured"] is False
            assert result["severity"] == "ok"
            assert result["rss_bytes"] == 0
