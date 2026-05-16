"""Phase 2.B — bounded concurrent task caps (H-1).

Verifies sidecar refuses additional tasks когда cap reached + raises
SidecarBusyError с empathetic message. Frontend UX-5 ловит и показывает
toast вместо resource exhaustion / crash.

Test strategy: monkeypatch thread dicts с fake long-running threads
(не запускаем настоящий forecast — нужны только thread.is_alive() == True
для cap accounting).
"""

from __future__ import annotations

import threading
import time

import pytest


@pytest.fixture(autouse=True)
def _reset_module_singletons():
    from aurora_launch.sidecar.services import reset_services_for_testing

    reset_services_for_testing()
    yield
    reset_services_for_testing()


@pytest.fixture
def long_running_thread():
    """Spawn dummy thread which sleeps long enough для cap measurement."""
    stop_event = threading.Event()

    def _spawn(name: str = "fake-task") -> threading.Thread:
        def _runner() -> None:
            stop_event.wait(timeout=5.0)

        t = threading.Thread(target=_runner, name=name, daemon=True)
        t.start()
        return t

    yield _spawn
    stop_event.set()


class TestSidecarBusyError:
    def test_message_is_russian_with_counts(self) -> None:
        from aurora_launch.sidecar.methods import SidecarBusyError

        err = SidecarBusyError("прогноз", 2, 2)
        msg = str(err)
        assert "прогноз" in msg
        assert "2/2" in msg
        assert "Подождите" in msg

    def test_carries_metadata(self) -> None:
        from aurora_launch.sidecar.methods import SidecarBusyError

        err = SidecarBusyError("оптимизация", 1, 1)
        assert err.kind == "оптимизация"
        assert err.current == 1
        assert err.cap == 1


class TestCheckCapacityHelper:
    def test_passes_when_under_cap(self, long_running_thread) -> None:
        from aurora_launch.sidecar.methods import _check_capacity

        threads = {"h1": long_running_thread("t1")}
        # cap=2 > 1 alive — pass
        _check_capacity("test", threads, 2)

    def test_raises_when_at_cap(self, long_running_thread) -> None:
        from aurora_launch.sidecar.methods import SidecarBusyError, _check_capacity

        threads = {"h1": long_running_thread("t1"), "h2": long_running_thread("t2")}
        with pytest.raises(SidecarBusyError) as exc_info:
            _check_capacity("test", threads, 2)
        assert exc_info.value.current == 2
        assert exc_info.value.cap == 2

    def test_ignores_dead_threads(self, long_running_thread) -> None:
        """Completed threads не считаются — predictable cap accounting."""
        from aurora_launch.sidecar.methods import _check_capacity

        t1 = long_running_thread("alive")
        t2 = threading.Thread(target=lambda: None, name="dead", daemon=True)
        t2.start()
        t2.join()  # завершён
        assert not t2.is_alive()

        threads = {"h1": t1, "h2": t2}
        # cap=2 alive=1 — pass
        _check_capacity("test", threads, 2)


class TestForecastCapEnforced:
    def test_start_forecast_raises_busy_at_cap(
        self, long_running_thread, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Заполняем _forecast_threads и пытаемся start_forecast — busy."""
        from aurora_launch.sidecar import methods as _m
        from aurora_launch.sidecar.methods import SidecarBusyError, dispatch

        # Fill cap с fake live threads
        for i in range(_m.MAX_CONCURRENT_FORECASTS):
            _m._forecast_threads[f"fake-{i}"] = long_running_thread(f"fake-{i}")

        with pytest.raises(SidecarBusyError, match="прогноз"):
            dispatch("start_forecast", {"project_id": "", "horizon_weeks": 26, "seed": 42})

    def test_start_forecast_passes_under_cap(
        self, long_running_thread, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cap-1 fake threads → 1 slot свободен → можно start."""
        from aurora_launch.sidecar import methods as _m
        from aurora_launch.sidecar.methods import dispatch

        # Fill cap-1 — 1 свободный slot
        for i in range(_m.MAX_CONCURRENT_FORECASTS - 1):
            _m._forecast_threads[f"fake-{i}"] = long_running_thread(f"fake-{i}")

        # Должно пройти — не SidecarBusyError. Реальный forecast может
        # завершиться error'ом (legacy path, no proxy data) но не busy.
        try:
            result = dispatch(
                "start_forecast",
                {"project_id": "", "horizon_weeks": 26, "seed": 42},
            )
            assert "forecast_handle" in result
        except Exception as e:
            # Acceptable: legacy path failure — НЕ SidecarBusyError
            assert "busy" not in str(e).lower()
            assert "прогноз" not in str(e) or "активны" not in str(e)


class TestIntegrityCapEnforced:
    def test_start_integrity_check_raises_busy_at_cap(
        self, long_running_thread
    ) -> None:
        from aurora_launch.sidecar import methods as _m
        from aurora_launch.sidecar.methods import SidecarBusyError, dispatch

        for i in range(_m.MAX_CONCURRENT_INTEGRITY):
            _m._integrity_threads[f"fake-int-{i}"] = long_running_thread(f"fake-int-{i}")

        with pytest.raises(SidecarBusyError, match="целостност"):
            dispatch("start_integrity_check", {})


class TestCapacityConstants:
    def test_documented_caps(self) -> None:
        """Verify constants sane — pilot expectation: 1-2 concurrent."""
        from aurora_launch.sidecar import methods as _m

        assert _m.MAX_CONCURRENT_FORECASTS >= 1
        assert _m.MAX_CONCURRENT_OPTIMIZE >= 1
        assert _m.MAX_CONCURRENT_INTEGRITY >= 1
        # Должны быть в reasonable bounds (single-machine desktop)
        assert _m.MAX_CONCURRENT_FORECASTS <= 8
