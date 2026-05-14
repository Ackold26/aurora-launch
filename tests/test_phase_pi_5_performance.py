"""Phase Π.5 — Performance optimization tests.

Coverage:
- Sensitivity grid: compute, lookup, relative impact, error paths
- Scenario card params (pessimistic / base / optimistic)
- Lazy PyMC import: deferred until first call (cold-start audit fix)
"""

from __future__ import annotations

import pytest

from aurora_launch.engines.lazy_pymc import (
    pymc_loaded,
    reset_for_testing,
)
from aurora_launch.engines.sensitivity_grid import (
    DEFAULT_PERTURBATION_LEVELS,
    SCENARIO_BASE,
    SCENARIO_OPTIMISTIC,
    SCENARIO_PESSIMISTIC,
    SensitivityGrid,
    SensitivityGridPoint,
    compute_sensitivity_grid,
    get_scenario_params,
)


# ---------------------------------------------------------------------------
# Sensitivity grid
# ---------------------------------------------------------------------------


def _mock_forecast_fn(params: dict[str, float]) -> tuple[float, float]:
    """Simple mock: forecast scales linearly with proxy_similarity perturbation."""
    base_forecast = 1_000_000.0
    similarity_delta = params.get("proxy_similarity", 0.0)
    pricing = params.get("pricing_index_relative", 1.0)
    forecast = base_forecast * (1.0 + similarity_delta) / pricing
    ci_width = forecast * 0.3
    return forecast, ci_width


class TestSensitivityGrid:
    def test_basic_compute(self) -> None:
        grid = compute_sensitivity_grid(_mock_forecast_fn)
        assert grid.baseline_total == 1_000_000.0
        assert grid.baseline_ci_width == 300_000.0
        # 6 dimensions × 5 levels = 30 points
        assert len(grid.points) == 30

    def test_lookup_exact_level(self) -> None:
        grid = compute_sensitivity_grid(_mock_forecast_fn)
        point = grid.lookup("proxy_similarity", 0.10)
        # forecast = 1M × 1.10 = 1.1M
        assert abs(point.point_forecast_total - 1_100_000.0) < 1.0

    def test_lookup_closest_level(self) -> None:
        grid = compute_sensitivity_grid(_mock_forecast_fn)
        # 0.07 closest к 0.05 (proxy_similarity levels: -0.20 -0.10 0 0.05 0.10)
        point = grid.lookup("proxy_similarity", 0.07)
        assert abs(point.level - 0.05) < 1e-9

    def test_lookup_unknown_dimension_raises(self) -> None:
        grid = compute_sensitivity_grid(_mock_forecast_fn)
        with pytest.raises(ValueError, match="not в grid"):
            grid.lookup("invalid_dimension", 0.5)

    def test_relative_impact_pct_increases_with_similarity(self) -> None:
        grid = compute_sensitivity_grid(_mock_forecast_fn)
        # Higher similarity → higher forecast (positive impact)
        pct_low = grid.relative_impact_pct("proxy_similarity", -0.10)
        pct_high = grid.relative_impact_pct("proxy_similarity", 0.10)
        assert pct_low < 0
        assert pct_high > 0
        assert pct_high > pct_low

    def test_compute_skips_dimensions_without_levels(self) -> None:
        grid = compute_sensitivity_grid(
            _mock_forecast_fn,
            dimensions=["proxy_similarity", "unknown_dim"],
        )
        # Only one dimension covered
        dims_in_points = {p.dimension for p in grid.points}
        assert "proxy_similarity" in dims_in_points
        assert "unknown_dim" not in dims_in_points

    def test_forecast_failure_logged_not_raised(self) -> None:
        """Caller exceptions per-level не abort entire grid build."""
        call_count = {"n": 0}

        def flaky_fn(params: dict[str, float]) -> tuple[float, float]:
            call_count["n"] += 1
            if call_count["n"] == 5:  # fail на 5-й вызов
                raise RuntimeError("simulated failure")
            return 1.0, 0.3

        grid = compute_sensitivity_grid(
            flaky_fn,
            dimensions=["proxy_similarity"],  # 5 levels
        )
        # 5 levels - 1 failed = 4 grid points
        assert len(grid.points) <= 4
        assert grid.baseline_total == 1.0


class TestScenarioParams:
    def test_pessimistic(self) -> None:
        params = get_scenario_params("pessimistic")
        assert params == SCENARIO_PESSIMISTIC
        assert params["proxy_similarity"] < 0  # negative similarity perturbation

    def test_base(self) -> None:
        params = get_scenario_params("base")
        assert params == SCENARIO_BASE
        assert params["proxy_similarity"] == 0.0

    def test_optimistic(self) -> None:
        params = get_scenario_params("optimistic")
        assert params == SCENARIO_OPTIMISTIC
        assert params["proxy_similarity"] > 0

    def test_case_insensitive(self) -> None:
        assert get_scenario_params("Pessimistic") == SCENARIO_PESSIMISTIC
        assert get_scenario_params("BASE") == SCENARIO_BASE

    def test_unknown_scenario(self) -> None:
        with pytest.raises(ValueError, match="Unknown scenario"):
            get_scenario_params("custom")


class TestPerturbationLevels:
    def test_all_dimensions_present(self) -> None:
        expected = {
            "proxy_similarity",
            "market_size_cv",
            "pricing_index_relative",
            "distribution_relative",
            "adstock_decay",
            "hill_alpha",
        }
        assert set(DEFAULT_PERTURBATION_LEVELS.keys()) == expected

    def test_each_dimension_has_5_levels(self) -> None:
        for dim, levels in DEFAULT_PERTURBATION_LEVELS.items():
            assert len(levels) == 5, f"{dim} has {len(levels)} levels"

    def test_levels_monotonic(self) -> None:
        for dim, levels in DEFAULT_PERTURBATION_LEVELS.items():
            for i in range(1, len(levels)):
                assert levels[i] >= levels[i - 1], (
                    f"{dim} levels not monotonic: {levels}"
                )


# ---------------------------------------------------------------------------
# Lazy PyMC
# ---------------------------------------------------------------------------


class TestLazyPyMC:
    def teardown_method(self) -> None:
        reset_for_testing()

    def test_not_loaded_initially(self) -> None:
        reset_for_testing()
        assert pymc_loaded() is False

    def test_lazy_load_via_call(self) -> None:
        """Smoke: calling lazy_pymc() loads и returns cached module."""
        from aurora_launch.engines.lazy_pymc import lazy_pymc
        pm = lazy_pymc()
        assert pm is not None
        assert pymc_loaded() is True
        # Second call returns same cached object
        assert lazy_pymc() is pm

    def test_reset_clears_cache(self) -> None:
        from aurora_launch.engines.lazy_pymc import lazy_pymc
        lazy_pymc()
        assert pymc_loaded() is True
        reset_for_testing()
        assert pymc_loaded() is False
