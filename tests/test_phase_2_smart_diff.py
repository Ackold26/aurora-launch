"""Phase 2 smart diff: compare_forecast_versions IPC tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Each test gets isolated ProjectDB."""
    db_dir = tmp_path / "aurora_test_db"
    db_dir.mkdir()
    monkeypatch.setenv("AURORA_PROJECT_DB_PATH", str(db_dir))
    monkeypatch.setenv("AURORA_PROJECT_DB_KEY", "none")
    monkeypatch.setenv("AURORA_LAUNCH_TESTING", "1")
    # Reset singleton
    import aurora_launch.sidecar.methods as m
    with m._PROJECT_DB_LOCK:
        if m._PROJECT_DB is not None:
            try:
                m._PROJECT_DB.close()
            except Exception:
                pass
            m._PROJECT_DB = None
    yield db_dir
    with m._PROJECT_DB_LOCK:
        if m._PROJECT_DB is not None:
            try:
                m._PROJECT_DB.close()
            except Exception:
                pass
            m._PROJECT_DB = None


def _make_forecast_json(point_mean: float, ci_width: float, n: int, mode: str = "pure_transfer") -> bytes:
    """Build forecast.json blob с N weekly_points centered on point_mean."""
    half = ci_width / 2
    points = [
        {
            "week_index": i,
            "point": point_mean,
            "ci_lower": point_mean - half,
            "ci_upper": point_mean + half,
        }
        for i in range(n)
    ]
    data = {
        "weekly_points": points,
        "horizon_weeks": n,
        "engine_mode": mode,
    }
    return json.dumps(data).encode("utf-8")


class TestCompareForecastVersions:
    def _setup_project_with_two_forecasts(self, a_point: float, b_point: float, a_ci: float = 200_000.0, b_ci: float = 150_000.0) -> tuple[str, int, int]:
        """Create project + 2 versions, each с forecast.json blob."""
        from aurora_launch.sidecar.methods import dispatch

        proj = dispatch("create_project", {"name": "Diff Test"})
        project_uuid = proj["project_uuid"]
        db = dispatch.__globals__["_get_project_db"]()

        v_a = db.save_version(
            project_uuid=project_uuid,
            files={"forecast.json": _make_forecast_json(a_point, a_ci, 12)},
            label="version a",
        )
        v_b = db.save_version(
            project_uuid=project_uuid,
            files={"forecast.json": _make_forecast_json(b_point, b_ci, 12, mode="ols_with_proxy_priors")},
            label="version b",
        )
        return project_uuid, v_a, v_b

    def test_basic_diff_available(self) -> None:
        from aurora_launch.sidecar.methods import dispatch

        _, a, b = self._setup_project_with_two_forecasts(1_000_000.0, 1_200_000.0)
        result = dispatch("compare_forecast_versions", {
            "version_id_a": a, "version_id_b": b
        })
        assert result["available"] is True

    def test_point_delta_absolute_correct(self) -> None:
        from aurora_launch.sidecar.methods import dispatch

        _, a, b = self._setup_project_with_two_forecasts(1_000_000.0, 1_200_000.0)
        result = dispatch("compare_forecast_versions", {
            "version_id_a": a, "version_id_b": b
        })
        assert result["point_delta_abs"] == pytest.approx(200_000.0)

    def test_point_delta_percent_correct(self) -> None:
        from aurora_launch.sidecar.methods import dispatch

        _, a, b = self._setup_project_with_two_forecasts(1_000_000.0, 1_200_000.0)
        result = dispatch("compare_forecast_versions", {
            "version_id_a": a, "version_id_b": b
        })
        assert result["point_delta_pct"] == pytest.approx(20.0)

    def test_ci_width_delta_negative_when_tightening(self) -> None:
        """B has narrower CI than A → ci_width_delta_pct negative."""
        from aurora_launch.sidecar.methods import dispatch

        _, a, b = self._setup_project_with_two_forecasts(
            1_000_000.0, 1_000_000.0, a_ci=200_000.0, b_ci=100_000.0
        )
        result = dispatch("compare_forecast_versions", {
            "version_id_a": a, "version_id_b": b
        })
        assert result["ci_width_delta_pct"] < 0

    def test_engine_mode_change_detected(self) -> None:
        from aurora_launch.sidecar.methods import dispatch

        _, a, b = self._setup_project_with_two_forecasts(1_000_000.0, 1_100_000.0)
        result = dispatch("compare_forecast_versions", {
            "version_id_a": a, "version_id_b": b
        })
        assert result["engine_mode_a"] == "pure_transfer"
        assert result["engine_mode_b"] == "ols_with_proxy_priors"

    def test_horizon_extracted(self) -> None:
        from aurora_launch.sidecar.methods import dispatch

        _, a, b = self._setup_project_with_two_forecasts(1_000_000.0, 1_100_000.0)
        result = dispatch("compare_forecast_versions", {
            "version_id_a": a, "version_id_b": b
        })
        assert result["horizon_a"] == 12
        assert result["horizon_b"] == 12

    def test_unavailable_when_forecast_missing(self) -> None:
        """If version blob doesn't have forecast.json → available=False."""
        from aurora_launch.sidecar.methods import dispatch

        proj = dispatch("create_project", {"name": "Empty Test"})
        db = dispatch.__globals__["_get_project_db"]()
        v_a = db.save_version(
            project_uuid=proj["project_uuid"],
            files={"some_other.json": b"{}"},
            label="no forecast",
        )
        v_b = db.save_version(
            project_uuid=proj["project_uuid"],
            files={"another.txt": b"plain"},
            label="also no forecast",
        )
        result = dispatch("compare_forecast_versions", {
            "version_id_a": v_a, "version_id_b": v_b
        })
        assert result["available"] is False
        assert "reason" in result

    def test_invalid_version_id_raises_value_error(self) -> None:
        from aurora_launch.sidecar.methods import dispatch

        with pytest.raises(ValueError, match="integers"):
            dispatch("compare_forecast_versions", {
                "version_id_a": "abc", "version_id_b": 1
            })
