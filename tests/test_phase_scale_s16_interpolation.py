"""Phase Scale S-16 — SensitivityGrid interpolation tests.

Coverage:
- Linear: midpoint between 0% and 20% → 10% returns correct interpolated values
- Edge: request at exact grid point returns exact stored value (no drift)
- Out-of-range: request below min OR above max → ValueError (no silent extrapolation)
- Nearest-neighbour fallback: interpolate=False returns closest precomputed point
- Monotonic ordering robustness: grid loaded in non-sorted order still interpolates
- relative_impact_pct uses interpolation path correctly
- 2D bilinear: documents future intent, raises NotImplementedError if called on
  1D-only grid (placeholder test records intent)
"""

from __future__ import annotations

import pytest

from aurora_launch.engines.sensitivity_grid import (
    SensitivityGrid,
    SensitivityGridPoint,
    compute_sensitivity_grid,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_grid_two_points(
    dim: str = "proxy_similarity",
    level_lo: float = 0.0,
    level_hi: float = 0.20,
    forecast_lo: float = 1_000_000.0,
    forecast_hi: float = 1_200_000.0,
    ci_lo: float = 100_000.0,
    ci_hi: float = 120_000.0,
    baseline_total: float = 1_000_000.0,
    baseline_ci: float = 100_000.0,
) -> SensitivityGrid:
    """Minimal two-point grid for interpolation tests."""
    points = [
        SensitivityGridPoint(
            dimension=dim,
            level=level_lo,
            point_forecast_total=forecast_lo,
            ci_width_total=ci_lo,
        ),
        SensitivityGridPoint(
            dimension=dim,
            level=level_hi,
            point_forecast_total=forecast_hi,
            ci_width_total=ci_hi,
        ),
    ]
    return SensitivityGrid(
        baseline_total=baseline_total,
        baseline_ci_width=baseline_ci,
        points=points,
        dimensions=[dim],
    )


def _make_five_point_grid() -> SensitivityGrid:
    """Five-point grid matching default proxy_similarity levels."""
    levels = [-0.20, -0.10, 0.0, 0.05, 0.10]
    base = 1_000_000.0
    points = [
        SensitivityGridPoint(
            dimension="proxy_similarity",
            level=lv,
            point_forecast_total=base * (1.0 + lv),
            ci_width_total=base * (1.0 + lv) * 0.30,
        )
        for lv in levels
    ]
    return SensitivityGrid(
        baseline_total=base,
        baseline_ci_width=base * 0.30,
        points=points,
        dimensions=["proxy_similarity"],
    )


# ---------------------------------------------------------------------------
# S-16-T01: Linear midpoint interpolation
# ---------------------------------------------------------------------------


class TestLinearInterpolation:
    def test_midpoint_forecast(self) -> None:
        """Midpoint between 0% and 20% should interpolate to mean of both forecasts."""
        grid = _make_grid_two_points(
            level_lo=0.0,
            level_hi=0.20,
            forecast_lo=1_000_000.0,
            forecast_hi=1_200_000.0,
        )
        point = grid.lookup("proxy_similarity", 0.10)
        expected_forecast = (1_000_000.0 + 1_200_000.0) / 2.0
        assert abs(point.point_forecast_total - expected_forecast) < 1.0

    def test_midpoint_ci_width(self) -> None:
        """CI width interpolates linearly as well."""
        grid = _make_grid_two_points(
            level_lo=0.0,
            level_hi=0.20,
            ci_lo=100_000.0,
            ci_hi=120_000.0,
        )
        point = grid.lookup("proxy_similarity", 0.10)
        expected_ci = (100_000.0 + 120_000.0) / 2.0
        assert abs(point.ci_width_total - expected_ci) < 1.0

    def test_midpoint_level_stored_as_requested(self) -> None:
        """Returned point.level should equal the requested value, not a grid anchor."""
        grid = _make_grid_two_points()
        point = grid.lookup("proxy_similarity", 0.10)
        assert abs(point.level - 0.10) < 1e-12

    def test_quarter_point_interpolation(self) -> None:
        """t=0.25 → forecast = lo + 0.25 * (hi - lo)."""
        grid = _make_grid_two_points(
            level_lo=0.0,
            level_hi=0.20,
            forecast_lo=1_000_000.0,
            forecast_hi=1_200_000.0,
        )
        point = grid.lookup("proxy_similarity", 0.05)  # t = 0.05/0.20 = 0.25
        expected = 1_000_000.0 + 0.25 * 200_000.0
        assert abs(point.point_forecast_total - expected) < 1.0

    def test_five_point_interpolation_inner(self) -> None:
        """Interpolate between −10% and 0% in a five-point grid."""
        grid = _make_five_point_grid()
        # Midpoint between -0.10 and 0.0 → level = -0.05
        point = grid.lookup("proxy_similarity", -0.05)
        # forecast_lo = 1M*(1-0.10)=900k, forecast_hi = 1M*(1-0)=1M → 950k
        expected = 950_000.0
        assert abs(point.point_forecast_total - expected) < 1.0


# ---------------------------------------------------------------------------
# S-16-T02: Exact grid point returns stored value
# ---------------------------------------------------------------------------


class TestExactGridPointLookup:
    def test_exact_lower_boundary(self) -> None:
        grid = _make_grid_two_points(
            level_lo=0.0,
            level_hi=0.20,
            forecast_lo=1_000_000.0,
        )
        point = grid.lookup("proxy_similarity", 0.0)
        assert abs(point.point_forecast_total - 1_000_000.0) < 1.0

    def test_exact_upper_boundary(self) -> None:
        grid = _make_grid_two_points(
            level_lo=0.0,
            level_hi=0.20,
            forecast_hi=1_200_000.0,
        )
        point = grid.lookup("proxy_similarity", 0.20)
        assert abs(point.point_forecast_total - 1_200_000.0) < 1.0

    def test_exact_inner_point_five_grid(self) -> None:
        """Requesting an anchor level returns exact stored value (no drift)."""
        grid = _make_five_point_grid()
        for lv in [-0.20, -0.10, 0.0, 0.05, 0.10]:
            point = grid.lookup("proxy_similarity", lv)
            expected = 1_000_000.0 * (1.0 + lv)
            assert abs(point.point_forecast_total - expected) < 0.1, (
                f"level={lv}: got {point.point_forecast_total}, expected {expected}"
            )


# ---------------------------------------------------------------------------
# S-16-T03: Out-of-range raises ValueError (no silent extrapolation)
# ---------------------------------------------------------------------------


class TestOutOfRangeRaisesError:
    def test_below_min_raises(self) -> None:
        grid = _make_grid_two_points(level_lo=0.0, level_hi=0.20)
        with pytest.raises(ValueError, match="out of range"):
            grid.lookup("proxy_similarity", -0.01)

    def test_above_max_raises(self) -> None:
        grid = _make_grid_two_points(level_lo=0.0, level_hi=0.20)
        with pytest.raises(ValueError, match="out of range"):
            grid.lookup("proxy_similarity", 0.21)

    def test_above_max_raises_also_for_non_interpolate(self) -> None:
        """Out-of-range check applies regardless of interpolate flag."""
        grid = _make_grid_two_points(level_lo=0.0, level_hi=0.20)
        with pytest.raises(ValueError, match="out of range"):
            grid.lookup("proxy_similarity", 0.50, interpolate=False)

    def test_unknown_dimension_raises(self) -> None:
        grid = _make_grid_two_points()
        with pytest.raises(ValueError, match="not в grid"):
            grid.lookup("nonexistent_dim", 0.05)

    def test_error_message_contains_range(self) -> None:
        grid = _make_grid_two_points(level_lo=0.0, level_hi=0.20)
        with pytest.raises(ValueError) as exc_info:
            grid.lookup("proxy_similarity", 0.99)
        msg = str(exc_info.value)
        assert "0.0" in msg or "0.2" in msg  # range bounds mentioned


# ---------------------------------------------------------------------------
# S-16-T04: interpolate=False returns nearest neighbour (legacy behaviour)
# ---------------------------------------------------------------------------


class TestNearestNeighbourFallback:
    def test_nearest_left(self) -> None:
        """When interpolate=False, 0.07 snaps to 0.05 (closer than 0.10)."""
        grid = _make_five_point_grid()
        point = grid.lookup("proxy_similarity", 0.07, interpolate=False)
        assert abs(point.level - 0.05) < 1e-9

    def test_nearest_right(self) -> None:
        """When interpolate=False, 0.09 snaps to 0.10 (closer than 0.05)."""
        grid = _make_five_point_grid()
        point = grid.lookup("proxy_similarity", 0.09, interpolate=False)
        assert abs(point.level - 0.10) < 1e-9

    def test_exact_hit_nearest_returns_same_as_interp(self) -> None:
        """At exact anchor, nearest and interp should return same forecast."""
        grid = _make_five_point_grid()
        for lv in [-0.20, -0.10, 0.0, 0.05, 0.10]:
            p_interp = grid.lookup("proxy_similarity", lv, interpolate=True)
            p_nearest = grid.lookup("proxy_similarity", lv, interpolate=False)
            assert abs(p_interp.point_forecast_total - p_nearest.point_forecast_total) < 1.0


# ---------------------------------------------------------------------------
# S-16-T05: relative_impact_pct uses interpolation path
# ---------------------------------------------------------------------------


class TestRelativeImpactPctWithInterpolation:
    def test_midpoint_relative_impact(self) -> None:
        """relative_impact_pct at midpoint should match interpolated forecast vs baseline."""
        grid = _make_grid_two_points(
            level_lo=0.0,
            level_hi=0.20,
            forecast_lo=1_000_000.0,
            forecast_hi=1_200_000.0,
            baseline_total=1_000_000.0,
        )
        pct = grid.relative_impact_pct("proxy_similarity", 0.10)
        # Interpolated = 1.1M → impact = +10%
        assert abs(pct - 10.0) < 0.01

    def test_relative_impact_zero_baseline(self) -> None:
        """Zero baseline → returns 0.0 without division error."""
        grid = SensitivityGrid(
            baseline_total=0.0,
            baseline_ci_width=0.0,
            points=[
                SensitivityGridPoint(
                    dimension="proxy_similarity",
                    level=0.0,
                    point_forecast_total=0.0,
                    ci_width_total=0.0,
                ),
                SensitivityGridPoint(
                    dimension="proxy_similarity",
                    level=0.20,
                    point_forecast_total=200_000.0,
                    ci_width_total=20_000.0,
                ),
            ],
            dimensions=["proxy_similarity"],
        )
        assert grid.relative_impact_pct("proxy_similarity", 0.10) == 0.0


# ---------------------------------------------------------------------------
# S-16-T06: compute_sensitivity_grid integration → lookup works on result
# ---------------------------------------------------------------------------


class TestComputeGridWithInterpolation:
    def _linear_fn(self, params: dict[str, float]) -> tuple[float, float]:
        base = 1_000_000.0
        delta = params.get("proxy_similarity", 0.0)
        f = base * (1.0 + delta)
        return f, f * 0.3

    def test_interpolate_between_precomputed_levels(self) -> None:
        grid = compute_sensitivity_grid(
            self._linear_fn,
            dimensions=["proxy_similarity"],
        )
        # Levels: -0.20, -0.10, 0.0, 0.05, 0.10
        # Midpoint between 0.0 and 0.05 → 0.025
        point = grid.lookup("proxy_similarity", 0.025)
        # Linear fn → expected = 1M * 1.025
        expected = 1_000_000.0 * 1.025
        assert abs(point.point_forecast_total - expected) < 1.0

    def test_out_of_range_raises_after_compute(self) -> None:
        grid = compute_sensitivity_grid(
            self._linear_fn,
            dimensions=["proxy_similarity"],
        )
        with pytest.raises(ValueError, match="out of range"):
            grid.lookup("proxy_similarity", 0.50)  # above max 0.10


# ---------------------------------------------------------------------------
# S-16-T07: 2D bilinear — documents future intent
# ---------------------------------------------------------------------------


class Test2DBilinearFutureIntent:
    def test_1d_grid_has_no_lookup_2d(self) -> None:
        """Current SensitivityGrid is 1D per dimension.
        2D bilinear requires cross-dimension grid points not yet computed.
        This test verifies that the attribute does NOT exist on the current
        class — acting as a forward-contract reminder for Phase Magic.
        When 2D is implemented, this test should be replaced by a real
        bilinear test.
        """
        grid = _make_five_point_grid()
        # Should not have lookup_2d yet — it's documented as future work.
        assert not hasattr(grid, "lookup_2d"), (
            "lookup_2d appeared — update this test with real bilinear coverage."
        )
