"""Tests for ROADMAP §3.4 — cross-product calibration (Launch ↔ Optimizer).

Coverage:
1. Schema validation (OptimizerProjectRef, OptimizerHistoryQuery,
   OptimizerHistoryResponse, CrossProductValidation).
2. MockOptimizerClient behaviour (list_projects, get_history, unknown brand).
3. validate_against_optimizer sidecar method:
   - happy path (low deviation)
   - high deviation case
   - client not configured (None in ServiceContainer) → available=False
   - proxy brand not found in Optimizer → available=False + warning
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest

from aurora_launch.schemas.cross_product import (
    CrossProductValidation,
    OptimizerHistoryQuery,
    OptimizerHistoryResponse,
    OptimizerProjectRef,
    WeeklyActual,
)
from aurora_launch.services.optimizer_client import (
    MockOptimizerClient,
    OptimizerNotConfigured,
)
from aurora_launch.sidecar.methods import dispatch
from aurora_launch.sidecar.services import (
    ServiceContainer,
    reset_services_for_testing,
    set_services_for_testing,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _restore_services():
    """Reset DI container after every test (test isolation)."""
    yield
    reset_services_for_testing()


@pytest.fixture()
def mock_client() -> MockOptimizerClient:
    """Default MockOptimizerClient with all built-in brands, 52 weeks."""
    return MockOptimizerClient()


@pytest.fixture()
def container_with_mock(mock_client: MockOptimizerClient) -> ServiceContainer:
    """ServiceContainer with MockOptimizerClient installed."""
    svc = ServiceContainer(optimizer_client=mock_client)
    set_services_for_testing(svc)
    return svc


# ===========================================================================
# 1. Schema validation tests
# ===========================================================================


class TestOptimizerProjectRef:
    def test_valid_weekly(self):
        ref = OptimizerProjectRef(
            project_uuid=UUID("00000000-0000-0000-0000-000000000001"),
            brand_code="kagotsel",
            granularity="weekly",
            last_modified=date(2025, 3, 1),
        )
        assert ref.brand_code == "kagotsel"
        assert ref.granularity == "weekly"

    def test_valid_monthly(self):
        ref = OptimizerProjectRef(
            project_uuid=UUID("00000000-0000-0000-0000-000000000002"),
            brand_code="venarus",
            granularity="monthly",
            last_modified=date(2025, 6, 1),
        )
        assert ref.granularity == "monthly"

    def test_rejects_unknown_granularity(self):
        with pytest.raises(Exception):
            OptimizerProjectRef(
                project_uuid=UUID("00000000-0000-0000-0000-000000000003"),
                brand_code="x",
                granularity="daily",  # type: ignore[arg-type]
                last_modified=date(2025, 1, 1),
            )

    def test_rejects_empty_brand_code(self):
        with pytest.raises(Exception):
            OptimizerProjectRef(
                project_uuid=UUID("00000000-0000-0000-0000-000000000004"),
                brand_code="",
                granularity="weekly",
                last_modified=date(2025, 1, 1),
            )


class TestOptimizerHistoryQuery:
    def test_valid_query_no_channels(self):
        q = OptimizerHistoryQuery(
            brand_code="kagotsel",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31),
        )
        assert q.channels is None

    def test_valid_query_with_channels(self):
        q = OptimizerHistoryQuery(
            brand_code="venarus",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 6, 30),
            channels=["tv", "digital"],
        )
        assert q.channels == ["tv", "digital"]

    def test_rejects_reversed_period(self):
        with pytest.raises(Exception, match="period_start"):
            OptimizerHistoryQuery(
                brand_code="x",
                period_start=date(2024, 12, 31),
                period_end=date(2024, 1, 1),
            )

    def test_same_day_period_ok(self):
        """period_start == period_end is allowed (single-day snapshot)."""
        q = OptimizerHistoryQuery(
            brand_code="x",
            period_start=date(2024, 6, 1),
            period_end=date(2024, 6, 1),
        )
        assert q.period_start == q.period_end


class TestOptimizerHistoryResponse:
    def test_valid_response(self):
        actuals = [WeeklyActual(week_index=i, sales=1000.0 + i) for i in range(4)]
        resp = OptimizerHistoryResponse(
            brand_code="kagotsel",
            weekly_actuals=actuals,
            n_observations=4,
            granularity="weekly",
        )
        assert resp.n_observations == 4

    def test_rejects_mismatched_n_observations(self):
        actuals = [WeeklyActual(week_index=0, sales=1000.0)]
        with pytest.raises(Exception, match="n_observations"):
            OptimizerHistoryResponse(
                brand_code="x",
                weekly_actuals=actuals,
                n_observations=5,  # wrong — only 1 actual
                granularity="weekly",
            )


class TestCrossProductValidation:
    def test_low_deviation(self):
        v = CrossProductValidation(
            proxy_brand="kagotsel",
            launch_forecast_value=50_000.0,
            optimizer_actual_value=48_000.0,
            deviation_pct=4.167,  # (50k-48k)/48k*100
            deviation_severity="low",
            confidence=1.0,
        )
        assert v.deviation_severity == "low"

    def test_high_deviation(self):
        v = CrossProductValidation(
            proxy_brand="venarus",
            launch_forecast_value=80_000.0,
            optimizer_actual_value=48_000.0,
            deviation_pct=66.667,
            deviation_severity="high",
            confidence=0.8,
        )
        assert v.deviation_severity == "high"

    def test_severity_validator_catches_mismatch(self):
        """deviation_pct=5% but severity='high' should fail."""
        with pytest.raises(Exception, match="deviation_severity"):
            CrossProductValidation(
                proxy_brand="x",
                launch_forecast_value=50_000.0,
                optimizer_actual_value=48_000.0,
                deviation_pct=4.167,
                deviation_severity="high",  # wrong — 4.167% is "low"
                confidence=0.9,
            )

    def test_confidence_bounds(self):
        with pytest.raises(Exception):
            CrossProductValidation(
                proxy_brand="x",
                launch_forecast_value=50_000.0,
                optimizer_actual_value=48_000.0,
                deviation_pct=4.167,
                deviation_severity="low",
                confidence=1.5,  # > 1.0 — invalid
            )


# ===========================================================================
# 2. MockOptimizerClient tests
# ===========================================================================


class TestMockOptimizerClient:
    def test_list_projects_returns_all_builtin_brands(self, mock_client: MockOptimizerClient):
        projects = mock_client.list_projects()
        brand_codes = {p.brand_code for p in projects}
        assert "kagotsel" in brand_codes
        assert "venarus" in brand_codes
        assert "mmx_afala" in brand_codes

    def test_list_projects_custom_brands(self):
        client = MockOptimizerClient(brand_codes=["brand_a", "brand_b"])
        projects = client.list_projects()
        assert len(projects) == 2
        assert {p.brand_code for p in projects} == {"brand_a", "brand_b"}

    def test_get_history_known_brand_returns_weekly_actuals(self, mock_client: MockOptimizerClient):
        query = OptimizerHistoryQuery(
            brand_code="kagotsel",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31),
        )
        resp = mock_client.get_history(query)
        assert resp is not None
        assert resp.brand_code == "kagotsel"
        assert resp.n_observations == 52  # default n_weeks
        assert len(resp.weekly_actuals) == 52
        # All sales should be positive
        assert all(w.sales > 0 for w in resp.weekly_actuals)

    def test_get_history_unknown_brand_returns_none(self, mock_client: MockOptimizerClient):
        query = OptimizerHistoryQuery(
            brand_code="unknown_brand_xyz",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31),
        )
        result = mock_client.get_history(query)
        assert result is None

    def test_get_history_with_channels_populates_spend(self, mock_client: MockOptimizerClient):
        query = OptimizerHistoryQuery(
            brand_code="venarus",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31),
            channels=["tv", "digital"],
        )
        resp = mock_client.get_history(query)
        assert resp is not None
        # Every week should have per-channel spend
        for w in resp.weekly_actuals:
            assert "tv" in w.spend_per_channel
            assert "digital" in w.spend_per_channel

    def test_n_weeks_parameter_controls_output_length(self):
        client = MockOptimizerClient(brand_codes=["kagotsel"], n_weeks=12)
        query = OptimizerHistoryQuery(
            brand_code="kagotsel",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31),
        )
        resp = client.get_history(query)
        assert resp is not None
        assert resp.n_observations == 12


# ===========================================================================
# 3. validate_against_optimizer sidecar method tests
# ===========================================================================


class TestValidateAgainstOptimizerMethod:
    """Tests for the `validate_against_optimizer` JSON-RPC method handler."""

    # ── Happy path: low deviation ────────────────────────────────────────

    def test_happy_path_low_deviation(self, container_with_mock):
        """kagotsel mock mean sales ≈ 48000; forecast near that → low deviation."""
        # MockOptimizerClient for kagotsel returns ~48k/week with mild seasonality.
        # Mean over 52 weeks is approximately 48000.
        result = dispatch(
            "validate_against_optimizer",
            {
                "launch_forecast_value": 48_000.0,
                "proxy_brand_code": "kagotsel",
                "horizon_weeks": 12,
            },
        )
        assert result is not None
        assert result["available"] is True
        assert result["proxy_brand"] == "kagotsel"
        assert result["deviation_severity"] == "low"
        assert 0.0 <= result["confidence"] <= 1.0
        # With 52 observations and horizon=12, confidence should be 1.0
        assert result["confidence"] == 1.0

    # ── High deviation case ──────────────────────────────────────────────

    def test_high_deviation_case(self, container_with_mock):
        """Forecast 2× the actual → deviation ~100% → severity=high."""
        result = dispatch(
            "validate_against_optimizer",
            {
                "launch_forecast_value": 96_000.0,  # ~2× kagotsel mean
                "proxy_brand_code": "kagotsel",
                "horizon_weeks": 12,
            },
        )
        assert result is not None
        assert result["available"] is True
        assert result["deviation_severity"] == "high"
        assert result["deviation_pct"] > 35.0

    # ── Medium deviation ─────────────────────────────────────────────────

    def test_medium_deviation_case(self, container_with_mock):
        """Forecast 20% above mean → medium severity."""
        # kagotsel mean ≈ 48000; 20% above ≈ 57600
        result = dispatch(
            "validate_against_optimizer",
            {
                "launch_forecast_value": 57_600.0,
                "proxy_brand_code": "kagotsel",
                "horizon_weeks": 12,
            },
        )
        assert result is not None
        assert result["available"] is True
        assert result["deviation_severity"] == "medium"

    # ── Client not configured → graceful null ────────────────────────────

    def test_no_optimizer_client_returns_not_available(self):
        """When optimizer_client slot is None, method returns available=False."""
        # No set_services_for_testing → optimizer_client is None (default)
        result = dispatch(
            "validate_against_optimizer",
            {
                "launch_forecast_value": 50_000.0,
                "proxy_brand_code": "kagotsel",
            },
        )
        assert result is not None
        assert result["available"] is False
        assert result["reason"] == "optimizer_not_configured"

    # ── Brand not found in Optimizer ─────────────────────────────────────

    def test_brand_not_found_returns_not_available(self, container_with_mock):
        """Unknown brand_code → method returns available=False + brand_not_found."""
        result = dispatch(
            "validate_against_optimizer",
            {
                "launch_forecast_value": 50_000.0,
                "proxy_brand_code": "nonexistent_brand_xyz",
            },
        )
        assert result is not None
        assert result["available"] is False
        assert result["reason"] == "brand_not_found"
        assert result["brand_code"] == "nonexistent_brand_xyz"

    # ── Low n_observations → lower confidence ────────────────────────────

    def test_low_n_observations_reduces_confidence(self):
        """With only 2 weeks of actuals (< 4), confidence should be 0.3."""
        tiny_client = MockOptimizerClient(brand_codes=["kagotsel"], n_weeks=2)
        svc = ServiceContainer(optimizer_client=tiny_client)
        set_services_for_testing(svc)

        result = dispatch(
            "validate_against_optimizer",
            {
                "launch_forecast_value": 48_000.0,
                "proxy_brand_code": "kagotsel",
                "horizon_weeks": 12,
            },
        )
        assert result is not None
        assert result["available"] is True
        assert result["confidence"] == 0.3

    # ── Missing required params raises ───────────────────────────────────

    def test_missing_launch_forecast_value_raises(self, container_with_mock):
        with pytest.raises((KeyError, ValueError)):
            dispatch(
                "validate_against_optimizer",
                {"proxy_brand_code": "kagotsel"},  # missing launch_forecast_value
            )
