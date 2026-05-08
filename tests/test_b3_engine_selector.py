"""B3 engine selector tests — deterministic logic per audit M4."""

from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from aurora_launch.engines.engine_selector import (
    DEFAULT_SINGLE_WITH_POOLING_THRESHOLD,
    DEFAULT_SPREAD_THRESHOLD_FOR_BLOCKED,
    select_engine,
)


class TestSingleProxy:
    def test_single_proxy_high_sim(self) -> None:
        result = select_engine(n_proxies=1, individual_scores=[0.92])
        assert result.selected_engine == "single"
        assert result.n_proxies_used == 1
        assert result.blocking_reason is None

    def test_single_proxy_medium_sim(self) -> None:
        result = select_engine(n_proxies=1, individual_scores=[0.72])
        assert result.selected_engine == "single"

    def test_single_proxy_low_sim_still_proceeds(self) -> None:
        result = select_engine(n_proxies=1, individual_scores=[0.55])
        # Low (S 0.50-0.65) — single proceeds, не blocked
        assert result.selected_engine == "single"

    def test_single_proxy_insufficient_blocked(self) -> None:
        result = select_engine(n_proxies=1, individual_scores=[0.42])
        assert result.selected_engine == "blocked"
        assert "Insufficient" in result.rationale or "0.50" in result.rationale


class TestMultiProxy:
    def test_multi_high_uniform(self) -> None:
        result = select_engine(n_proxies=2, individual_scores=[0.85, 0.87])
        assert result.selected_engine == "multi"
        assert result.n_proxies_used == 2

    def test_multi_three_proxies(self) -> None:
        result = select_engine(n_proxies=3, individual_scores=[0.80, 0.82, 0.85])
        assert result.selected_engine == "multi"
        assert result.n_proxies_used == 3

    def test_multi_some_below_threshold_falls_back_to_single_with_pooling(self) -> None:
        # max=0.85 (above), min=0.55 (below 0.65 threshold)
        # spread = 0.30 (below 0.4 blocked threshold)
        result = select_engine(n_proxies=2, individual_scores=[0.85, 0.55])
        assert result.selected_engine == "single_with_pooling"
        assert result.n_proxies_used == 1  # uses S_max only

    def test_multi_high_spread_blocked(self) -> None:
        # spread = 0.95 - 0.40 = 0.55 > 0.4 default
        result = select_engine(n_proxies=2, individual_scores=[0.95, 0.40])
        assert result.selected_engine == "blocked"
        assert "spread" in result.rationale.lower() or "heterogeneity" in result.rationale.lower()


class TestEdgeCases:
    def test_zero_proxies_blocked(self) -> None:
        result = select_engine(n_proxies=0, individual_scores=[])
        assert result.selected_engine == "blocked"
        assert "n_proxies" in result.blocking_reason

    def test_cross_category_blocked(self) -> None:
        result = select_engine(
            n_proxies=1, individual_scores=[0.85], cross_category=True
        )
        assert result.selected_engine == "blocked"
        assert "cross" in result.rationale.lower() or "L1" in result.rationale

    def test_scores_length_mismatch(self) -> None:
        result = select_engine(n_proxies=2, individual_scores=[0.85])
        assert result.selected_engine == "blocked"
        assert "length" in result.blocking_reason.lower()


class TestDeterminism:
    @given(
        n_proxies=st.integers(min_value=1, max_value=3),
        scores=st.lists(
            st.floats(min_value=0.45, max_value=0.99, allow_nan=False),
            min_size=1, max_size=3,
        ),
    )
    def test_same_inputs_same_outputs(self, n_proxies: int, scores: list[float]) -> None:
        # Match list length to n_proxies
        if len(scores) != n_proxies:
            scores = scores[:n_proxies] + [0.7] * (n_proxies - len(scores))
        scores = scores[:n_proxies]

        r1 = select_engine(n_proxies=n_proxies, individual_scores=scores)
        r2 = select_engine(n_proxies=n_proxies, individual_scores=scores)
        assert r1.selected_engine == r2.selected_engine
        assert r1.n_proxies_used == r2.n_proxies_used


class TestThresholdInvariants:
    def test_default_thresholds_match_spec(self) -> None:
        assert DEFAULT_SPREAD_THRESHOLD_FOR_BLOCKED == 0.4
        assert DEFAULT_SINGLE_WITH_POOLING_THRESHOLD == 0.65

    def test_spread_at_threshold_not_blocked(self) -> None:
        # spread = 0.40 (exactly at threshold) — should still proceed
        result = select_engine(
            n_proxies=2,
            individual_scores=[0.90, 0.50],
            spread_threshold_for_blocked=0.40,
        )
        # 0.50 < 0.65 single_with_pooling threshold → fallback
        # spread 0.40 == 0.40 strictly не >, not blocked
        assert result.selected_engine == "single_with_pooling"

    def test_custom_threshold_override(self) -> None:
        # Tighter spread threshold — block sooner
        result = select_engine(
            n_proxies=2,
            individual_scores=[0.85, 0.65],
            spread_threshold_for_blocked=0.15,  # very strict
        )
        assert result.selected_engine == "blocked"
