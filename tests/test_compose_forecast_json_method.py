"""Тесты sidecar метода `compose_forecast_json` (этап 1.3).

Метод регистрируется в src/aurora_launch/sidecar/methods.py и вызывается
из frontend wizard'a после forecast_completed event'a.
"""

from __future__ import annotations

import base64
import json

import pytest

from aurora_launch.schemas.forecast_bundle import load_forecast_json


def _points(n: int):
    return [
        {"week_index": i, "point": 100.0, "ci_lower": 80.0, "ci_upper": 120.0} for i in range(n)
    ]


class TestComposeForecastJsonMethod:
    def test_minimal_call_returns_base64(self) -> None:
        from aurora_launch.sidecar.methods import dispatch

        result = dispatch(
            "compose_forecast_json",
            {
                "horizon_weeks": 3,
                "weekly_points": _points(3),
            },
        )
        assert "forecast_json_base64" in result
        assert result["schema_version"] == "1"
        assert result["byte_size"] > 0

    def test_round_trip_via_loader(self) -> None:
        from aurora_launch.sidecar.methods import dispatch

        result = dispatch(
            "compose_forecast_json",
            {
                "horizon_weeks": 2,
                "weekly_points": _points(2),
                "engine_mode": "pure_transfer",
                "granularity": "monthly",
                "methodology_signature": "pure_transfer@v1.0",
                "n_recipient": 0,
                "anchors": {
                    "market_size": 500_000.0,
                    "market_size_cv": 0.15,
                    "planned_share_trajectory": [0.05, 0.05],
                    "distribution_trajectory": [0.7, 0.75],
                    "pricing_index": 1.1,
                    "elasticity": 0.3,
                    "seasonality": None,
                },
                "spend_plan": {"digital": [10_000.0, 12_000.0]},
                "coverage_target": 0.95,
                "produced_at": "2026-05-16T16:00:00Z",
            },
        )
        blob = base64.b64decode(result["forecast_json_base64"])
        loaded = load_forecast_json(blob)
        assert loaded.engine_mode == "pure_transfer"
        assert loaded.methodology_signature == "pure_transfer@v1.0"
        assert loaded.anchors is not None
        assert loaded.anchors.market_size == 500_000.0
        assert loaded.spend_plan == {"digital": [10_000.0, 12_000.0]}
        assert loaded.produced_at == "2026-05-16T16:00:00Z"

    def test_validation_horizon_mismatch_raises(self) -> None:
        from pydantic import ValidationError

        from aurora_launch.sidecar.methods import dispatch

        with pytest.raises(ValidationError):
            dispatch(
                "compose_forecast_json",
                {
                    "horizon_weeks": 4,
                    "weekly_points": _points(2),  # mismatch
                },
            )

    def test_validation_bad_anchors_raises(self) -> None:
        from pydantic import ValidationError

        from aurora_launch.sidecar.methods import dispatch

        with pytest.raises(ValidationError):
            dispatch(
                "compose_forecast_json",
                {
                    "horizon_weeks": 1,
                    "weekly_points": _points(1),
                    "anchors": {
                        "market_size": -1.0,  # invalid
                        "planned_share_trajectory": [0.05],
                        "distribution_trajectory": [0.7],
                        "pricing_index": 1.0,
                        "elasticity": 0.5,
                    },
                },
            )

    def test_method_registered(self) -> None:
        from aurora_launch.sidecar.methods import list_methods

        assert "compose_forecast_json" in list_methods()

    def test_produced_at_does_not_change_canonical_hash(self) -> None:
        from aurora_launch.sidecar.methods import dispatch

        kw = {
            "horizon_weeks": 2,
            "weekly_points": _points(2),
        }
        a = dispatch("compose_forecast_json", {**kw, "produced_at": "2026-05-16T00:00:00Z"})
        b = dispatch("compose_forecast_json", {**kw, "produced_at": "2027-12-31T23:59:59Z"})
        # Bundle bytes сами по себе различаются (produced_at в pretty JSON),
        # но canonical bytes должны совпадать.
        blob_a = base64.b64decode(a["forecast_json_base64"])
        blob_b = base64.b64decode(b["forecast_json_base64"])
        loaded_a = load_forecast_json(blob_a)
        loaded_b = load_forecast_json(blob_b)
        assert loaded_a.to_canonical_bytes() == loaded_b.to_canonical_bytes()

    def test_audit_a3_missing_horizon_weeks_raises_value_error(self) -> None:
        """Audit A-3: missing required key → ValueError с понятным сообщением,
        не KeyError (последний даёт generic 500 на sidecar protocol уровне)."""
        from aurora_launch.sidecar.methods import dispatch

        with pytest.raises(ValueError) as exc:
            dispatch(
                "compose_forecast_json",
                {"weekly_points": _points(1)},  # нет horizon_weeks
            )
        assert "horizon_weeks" in str(exc.value)

    def test_audit_a3_missing_weekly_points_raises_value_error(self) -> None:
        from aurora_launch.sidecar.methods import dispatch

        with pytest.raises(ValueError) as exc:
            dispatch(
                "compose_forecast_json",
                {"horizon_weeks": 1},  # нет weekly_points
            )
        assert "weekly_points" in str(exc.value)

    def test_b64_decodes_to_valid_json(self) -> None:
        from aurora_launch.sidecar.methods import dispatch

        result = dispatch(
            "compose_forecast_json",
            {"horizon_weeks": 1, "weekly_points": _points(1)},
        )
        blob = base64.b64decode(result["forecast_json_base64"])
        parsed = json.loads(blob.decode("utf-8"))
        assert parsed["version"] == "1"
        assert parsed["horizon_weeks"] == 1
