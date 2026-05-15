"""Тесты канонической схемы forecast.json (этап 1.3 ROADMAP_POST_V0_1_0).

Покрывают:
- Валидацию ForecastJsonV1 + RecipientAnchorsPayload + ForecastPoint
- Backwards-compat loader для legacy bundles без поля `version`
- Bit-stable canonical bytes (rfc8785) — produced_at exclude
- Round-trip через compose_forecast_json_bytes
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from aurora_launch.schemas.forecast_bundle import (
    ForecastJsonV1,
    ForecastPoint,
    RecipientAnchorsPayload,
    compose_forecast_json_bytes,
    load_forecast_json,
)


def _make_points(n: int, point_mean: float = 1_000_000.0, ci_width: float = 200_000.0):
    half = ci_width / 2
    return [
        {
            "week_index": i,
            "point": point_mean,
            "ci_lower": point_mean - half,
            "ci_upper": point_mean + half,
        }
        for i in range(n)
    ]


def _make_anchors(horizon: int) -> dict[str, object]:
    return {
        "market_size": 1_000_000.0,
        "market_size_cv": 0.1,
        "planned_share_trajectory": [0.05] * horizon,
        "distribution_trajectory": [0.8] * horizon,
        "pricing_index": 1.0,
        "elasticity": 0.2,
        "seasonality": None,
    }


class TestForecastPoint:
    def test_valid_point(self):
        p = ForecastPoint(week_index=0, point=100.0, ci_lower=80.0, ci_upper=120.0)
        assert p.point == 100.0

    def test_ci_ordering_violation_raises(self):
        with pytest.raises(ValidationError) as exc:
            ForecastPoint(week_index=0, point=100.0, ci_lower=120.0, ci_upper=80.0)
        assert "CI ordering" in str(exc.value)

    def test_negative_week_index_raises(self):
        with pytest.raises(ValidationError):
            ForecastPoint(week_index=-1, point=100.0, ci_lower=80.0, ci_upper=120.0)


class TestRecipientAnchorsPayload:
    def test_minimal_valid(self):
        a = RecipientAnchorsPayload(
            market_size=1000.0,
            planned_share_trajectory=[0.1],
            distribution_trajectory=[0.5],
            pricing_index=1.0,
            elasticity=0.5,
        )
        assert a.market_size_cv == 0.10
        assert a.seasonality is None

    def test_trajectory_length_mismatch_raises(self):
        with pytest.raises(ValidationError):
            RecipientAnchorsPayload(
                market_size=1000.0,
                planned_share_trajectory=[0.1, 0.1],
                distribution_trajectory=[0.5],
                pricing_index=1.0,
                elasticity=0.5,
            )

    def test_seasonality_length_mismatch_raises(self):
        with pytest.raises(ValidationError):
            RecipientAnchorsPayload(
                market_size=1000.0,
                planned_share_trajectory=[0.1, 0.1],
                distribution_trajectory=[0.5, 0.5],
                pricing_index=1.0,
                elasticity=0.5,
                seasonality=[1.0],
            )

    def test_share_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            RecipientAnchorsPayload(
                market_size=1000.0,
                planned_share_trajectory=[1.5],
                distribution_trajectory=[0.5],
                pricing_index=1.0,
                elasticity=0.5,
            )

    def test_market_size_must_be_positive(self):
        with pytest.raises(ValidationError):
            RecipientAnchorsPayload(
                market_size=0.0,
                planned_share_trajectory=[0.1],
                distribution_trajectory=[0.5],
                pricing_index=1.0,
                elasticity=0.5,
            )


class TestForecastJsonV1Validation:
    def test_minimal_valid_v1(self):
        f = ForecastJsonV1(horizon_weeks=2, weekly_points=_make_points(2))
        assert f.version == "1"
        assert f.granularity == "monthly"
        assert f.engine_mode == "pure_transfer"
        assert f.anchors is None
        assert f.spend_plan is None

    def test_horizon_mismatch_raises(self):
        with pytest.raises(ValidationError) as exc:
            ForecastJsonV1(horizon_weeks=3, weekly_points=_make_points(2))
        assert "horizon_weeks" in str(exc.value)

    def test_anchors_trajectory_length_mismatch_raises(self):
        bad_anchors = _make_anchors(2)
        with pytest.raises(ValidationError) as exc:
            ForecastJsonV1(
                horizon_weeks=3,
                weekly_points=_make_points(3),
                anchors=RecipientAnchorsPayload.model_validate(bad_anchors),
            )
        assert "planned_share_trajectory length" in str(exc.value)

    def test_spend_plan_length_mismatch_raises(self):
        with pytest.raises(ValidationError) as exc:
            ForecastJsonV1(
                horizon_weeks=3,
                weekly_points=_make_points(3),
                spend_plan={"tv": [100.0, 200.0]},
            )
        assert "spend_plan" in str(exc.value)

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError) as exc:
            ForecastJsonV1.model_validate(
                {
                    "horizon_weeks": 2,
                    "weekly_points": _make_points(2),
                    "made_up_field": "no good",
                }
            )
        # pydantic v2 error wording: "Extra inputs are not permitted"
        assert "extra" in str(exc.value).lower() or "not permitted" in str(exc.value).lower()

    def test_full_payload_with_anchors_and_spend(self):
        horizon = 12
        f = ForecastJsonV1(
            horizon_weeks=horizon,
            weekly_points=_make_points(horizon),
            engine_mode="ols_with_proxy_priors",
            granularity="weekly",
            methodology_signature="ols_with_proxy_priors@v1.2",
            n_recipient=24,
            warnings=["Low n_recipient — wide CI"],
            anchors=RecipientAnchorsPayload.model_validate(_make_anchors(horizon)),
            spend_plan={"tv": [50_000.0] * horizon, "digital": [30_000.0] * horizon},
        )
        assert f.anchors is not None
        assert f.spend_plan is not None
        assert len(f.spend_plan) == 2


class TestCanonicalBytes:
    def test_produced_at_excluded_from_canonical(self):
        a = ForecastJsonV1(
            horizon_weeks=2,
            weekly_points=_make_points(2),
            produced_at="2026-05-16T10:00:00Z",
        )
        b = ForecastJsonV1(
            horizon_weeks=2,
            weekly_points=_make_points(2),
            produced_at="2027-01-01T00:00:00Z",
        )
        assert a.to_canonical_bytes() == b.to_canonical_bytes()

    def test_canonical_stable_across_construction_order(self):
        # Pydantic instances built from differently-ordered dicts should
        # produce identical canonical bytes thanks to rfc8785 sort.
        d1 = {
            "horizon_weeks": 2,
            "weekly_points": _make_points(2),
            "granularity": "monthly",
            "engine_mode": "pure_transfer",
        }
        d2 = {
            "engine_mode": "pure_transfer",
            "granularity": "monthly",
            "weekly_points": _make_points(2),
            "horizon_weeks": 2,
        }
        a = ForecastJsonV1.model_validate(d1)
        b = ForecastJsonV1.model_validate(d2)
        assert a.to_canonical_bytes() == b.to_canonical_bytes()

    def test_bundle_bytes_is_pretty_json(self):
        f = ForecastJsonV1(horizon_weeks=2, weekly_points=_make_points(2))
        blob = f.to_bundle_bytes()
        text = blob.decode("utf-8")
        # Pretty-printed via json.dumps(indent=2) → newline present
        assert "\n" in text
        # Должно быть валидным JSON
        parsed = json.loads(text)
        assert parsed["horizon_weeks"] == 2


class TestBackwardsCompat:
    """Critical: legacy bundles до v0.1.1 не имеют поля version + новых полей."""

    def test_legacy_minimal_loads(self):
        """Аналог тестового фикстуры test_phase_2_smart_diff: только weekly_points + horizon_weeks + engine_mode."""
        legacy = {
            "weekly_points": _make_points(12),
            "horizon_weeks": 12,
            "engine_mode": "pure_transfer",
        }
        blob = json.dumps(legacy).encode("utf-8")
        f = load_forecast_json(blob)
        assert f.version == "1"
        assert f.anchors is None
        assert f.spend_plan is None
        assert f.n_recipient == 0
        assert f.granularity == "monthly"

    def test_legacy_without_horizon_derives_from_points(self):
        legacy = {
            "weekly_points": _make_points(5),
            "engine_mode": "transfer_with_bias_check",
        }
        blob = json.dumps(legacy).encode("utf-8")
        f = load_forecast_json(blob)
        assert f.horizon_weeks == 5

    def test_legacy_with_extra_keys_silently_drops(self):
        legacy = {
            "weekly_points": _make_points(3),
            "horizon_weeks": 3,
            "internal_debug_field": "ignored",
            "older_aurora_export_version": "0.0.9",
        }
        blob = json.dumps(legacy).encode("utf-8")
        f = load_forecast_json(blob)
        # Extra ключи отброшены normaliser'ом, не raise
        assert f.horizon_weeks == 3

    def test_v1_round_trip(self):
        original = ForecastJsonV1(
            horizon_weeks=4,
            weekly_points=_make_points(4),
            anchors=RecipientAnchorsPayload.model_validate(_make_anchors(4)),
            spend_plan={"tv": [1.0, 2.0, 3.0, 4.0]},
            warnings=["test"],
            produced_at="2026-05-16T12:00:00Z",
        )
        blob = original.to_bundle_bytes()
        loaded = load_forecast_json(blob)
        assert loaded.anchors is not None
        assert loaded.anchors.market_size == 1_000_000.0
        assert loaded.spend_plan == {"tv": [1.0, 2.0, 3.0, 4.0]}
        assert loaded.warnings == ["test"]
        # Канонические bytes без produced_at — должны совпасть
        assert loaded.to_canonical_bytes() == original.to_canonical_bytes()

    def test_not_a_dict_raises(self):
        with pytest.raises(ValueError):
            load_forecast_json(b"[1,2,3]")

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            load_forecast_json(b"not json at all")


class TestComposeHelper:
    def test_minimal_compose(self):
        blob = compose_forecast_json_bytes(
            horizon_weeks=3,
            weekly_points=_make_points(3),
        )
        loaded = load_forecast_json(blob)
        assert loaded.horizon_weeks == 3
        assert loaded.anchors is None

    def test_full_compose(self):
        horizon = 6
        blob = compose_forecast_json_bytes(
            horizon_weeks=horizon,
            weekly_points=_make_points(horizon),
            engine_mode="bayesian_with_proxy_priors",
            granularity="weekly",
            methodology_signature="bayesian@v2.0",
            n_recipient=10,
            warnings=["test warning"],
            anchors=_make_anchors(horizon),
            spend_plan={"tv": [100.0] * horizon},
            coverage_target=0.90,
            seed=7,
            produced_at="2026-05-16T15:30:00Z",
        )
        loaded = load_forecast_json(blob)
        assert loaded.engine_mode == "bayesian_with_proxy_priors"
        assert loaded.granularity == "weekly"
        assert loaded.coverage_target == 0.90
        assert loaded.seed == 7
        assert loaded.anchors is not None and loaded.anchors.elasticity == 0.2
        assert loaded.spend_plan == {"tv": [100.0] * horizon}

    def test_compose_validates_horizon(self):
        with pytest.raises(ValidationError):
            compose_forecast_json_bytes(
                horizon_weeks=5,
                weekly_points=_make_points(3),  # mismatch
            )
