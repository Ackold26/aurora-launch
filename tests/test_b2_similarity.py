"""B2 similarity calculator tests per SIMILARITY_FRAMEWORK.md."""

from __future__ import annotations

import asyncio

import pytest
from hypothesis import given, settings, strategies as st

from aurora_launch.engines.similarity_calculator import (
    CATEGORY_WEIGHT_PROFILES,
    DEFAULT_WEIGHTS,
    INFLATION_BY_VERDICT,
    PRICING_TIERS,
    VERDICT_THRESHOLDS,
    _get_weight_profile_id,
    _get_weights,
    _score_category_match,
    _score_tier_distance,
    aggregate_multi_proxy,
    compute,
    compute_aggregate_score,
    compute_dimension_scores,
    detect_anti_patterns,
    determine_verdict,
)
from aurora_launch.schemas.proxy import ProxyEntry


def _make_entry(**overrides) -> ProxyEntry:
    defaults = dict(
        proxy_brand_name="Test",
        proxy_brand_code="TST-2026",
        category_l1="FMCG_food",
        category_l2="snacks_savoury",
        category_l3="chips",
        pricing_tier="MAINSTREAM",
        brand_size="CHALLENGER",
        distribution="NATIONAL",
        media_maturity="ALWAYS_ON",
        lifecycle="MATURE",
    )
    defaults.update(overrides)
    return ProxyEntry(**defaults)


class TestCategoryMatching:
    def test_l3_exact_match(self) -> None:
        score = _score_category_match("a", "b", "c", "a", "b", "c")
        assert score == 1.0

    def test_l2_match(self) -> None:
        score = _score_category_match("a", "b", "c", "a", "b", "different")
        assert score == 0.7

    def test_l1_match(self) -> None:
        score = _score_category_match("a", "b", "c", "a", "different", "different")
        assert score == 0.5

    def test_adjacent_l1(self) -> None:
        # L2 and L3 must differ to drop к L1 match (else 0.7 returned)
        score = _score_category_match(
            "FMCG_food", "snacks", "chips",
            "FMCG_beverage", "carbonated", "cola",
        )
        assert score == 0.2

    def test_cross_l1_blocked(self) -> None:
        score = _score_category_match(
            "FMCG_food", "snacks", "chips",
            "OTC_pharma", "OTC_cold_flu", "antiviral",
        )
        assert score == 0.0


class TestTierDistance:
    def test_same_tier(self) -> None:
        score = _score_tier_distance("PREMIUM", "PREMIUM", PRICING_TIERS)
        assert score == 1.0

    def test_one_tier_apart(self) -> None:
        score = _score_tier_distance("PREMIUM", "MAINSTREAM", PRICING_TIERS)
        assert score == 0.5

    def test_two_tiers_apart(self) -> None:
        score = _score_tier_distance("LUXURY", "MAINSTREAM", PRICING_TIERS)
        assert score == 0.2

    def test_three_tiers_apart(self) -> None:
        score = _score_tier_distance("LUXURY", "ECONOMY", PRICING_TIERS)
        assert score == 0.0


class TestWeightProfiles:
    def test_otc_pharma_weights(self) -> None:
        weights = _get_weights("OTC_pharma", "OTC_cold_flu")
        assert weights["category"] == 0.40

    def test_fmcg_impulse_weights(self) -> None:
        weights = _get_weights("FMCG_food", "snacks_savoury")
        assert weights["pricing_tier"] == 0.25

    def test_default_weights_for_unknown(self) -> None:
        weights = _get_weights("Unknown", "x")
        assert weights == DEFAULT_WEIGHTS


class TestAggregateScore:
    def test_perfect_match_score_one(self) -> None:
        recipient = _make_entry()
        proxy = _make_entry()  # same as recipient
        dim_scores = compute_dimension_scores(recipient, proxy)
        weights = _get_weights(recipient.category_l1, recipient.category_l2)
        score = compute_aggregate_score(dim_scores, weights)
        assert score == 1.0

    def test_total_mismatch_score_low(self) -> None:
        recipient = _make_entry(category_l1="FMCG_food", category_l3="chips")
        proxy = _make_entry(
            category_l1="OTC_pharma",  # cross-L1
            category_l2="OTC_cold_flu",
            category_l3="OTC_antiviral",
            pricing_tier="LUXURY",  # 3 tiers apart
            brand_size="LEADER",  # 1 tier apart
            distribution="NICHE",  # 2 tiers apart
            media_maturity="DORMANT",  # 3 tiers apart
            lifecycle="DECLINING",  # 3 tiers apart
        )
        dim_scores = compute_dimension_scores(recipient, proxy)
        weights = _get_weights(recipient.category_l1, recipient.category_l2)
        score = compute_aggregate_score(dim_scores, weights)
        assert score < 0.50  # Insufficient territory


class TestVerdict:
    def test_high(self) -> None:
        assert determine_verdict(0.92) == "High"
        assert determine_verdict(0.85) == "High"

    def test_medium(self) -> None:
        assert determine_verdict(0.70) == "Medium"
        assert determine_verdict(0.65) == "Medium"

    def test_low(self) -> None:
        assert determine_verdict(0.55) == "Low"
        assert determine_verdict(0.50) == "Low"

    def test_insufficient(self) -> None:
        assert determine_verdict(0.42) == "Insufficient"
        assert determine_verdict(0.0) == "Insufficient"

    def test_inflation_factors_match_spec(self) -> None:
        assert INFLATION_BY_VERDICT["High"] == 1.2
        assert INFLATION_BY_VERDICT["Medium"] == 1.5
        assert INFLATION_BY_VERDICT["Low"] == 2.0


class TestAntiPatterns:
    def test_leader_for_challenger_flagged(self) -> None:
        recipient = _make_entry(brand_size="CHALLENGER")
        proxy = _make_entry(brand_size="LEADER")
        flags = detect_anti_patterns(recipient, proxy)
        assert any(f["pattern_id"] == "leader_as_proxy_for_challenger" for f in flags)

    def test_premium_for_economy_flagged(self) -> None:
        recipient = _make_entry(pricing_tier="ECONOMY")
        proxy = _make_entry(pricing_tier="PREMIUM")
        flags = detect_anti_patterns(recipient, proxy)
        assert any(f["pattern_id"] == "premium_as_proxy_for_economy" for f in flags)

    def test_no_flags_when_aligned(self) -> None:
        recipient = _make_entry()
        proxy = _make_entry()  # identical
        flags = detect_anti_patterns(recipient, proxy)
        assert flags == []


class TestMultiProxyAggregation:
    def test_weighted_average(self) -> None:
        result = aggregate_multi_proxy(
            individual_scores=[0.85, 0.75],
            pooling_weights=[0.6, 0.4],
        )
        # Weighted: 0.85 × 0.6 + 0.75 × 0.4 = 0.51 + 0.3 = 0.81
        assert abs(result["combined_score"] - 0.81) < 1e-6

    def test_multi_penalty_n_2(self) -> None:
        result = aggregate_multi_proxy([0.8, 0.8], [0.5, 0.5])
        # 1 + 0.05 × (2-1) = 1.05
        assert result["multi_penalty"] == 1.05

    def test_multi_penalty_n_3(self) -> None:
        result = aggregate_multi_proxy([0.8, 0.8, 0.8], [0.4, 0.3, 0.3])
        # 1 + 0.05 × (3-1) = 1.10
        assert result["multi_penalty"] == 1.10

    def test_floor_warning_individual_below_0_5(self) -> None:
        result = aggregate_multi_proxy([0.85, 0.40], [0.5, 0.5])
        assert any(
            w["warning_type"] == "individual_below_0_5"
            for w in result["floor_warnings"]
        )

    def test_floor_warning_spread_above_0_3(self) -> None:
        result = aggregate_multi_proxy([0.85, 0.50], [0.5, 0.5])
        assert any(
            w["warning_type"] == "spread_above_0_3"
            for w in result["floor_warnings"]
        )

    def test_weights_must_sum_unity(self) -> None:
        with pytest.raises(ValueError, match="must sum to 1.0"):
            aggregate_multi_proxy([0.85, 0.75], [0.6, 0.5])  # sums to 1.1


class TestComputeHandler:
    def test_handler_full_response(self) -> None:
        result = asyncio.run(compute(ctx=None))
        assert result["step_type"] == "proxy_select"
        assert result["stub"] is False
        assert "similarity_score" in result
        assert result["verdict"] in ("High", "Medium", "Low", "Insufficient")
        assert "anti_patterns_detected" in result
        assert "dimension_scores" in result

    def test_insufficient_blocks_forecast(self) -> None:
        # Cross-L1 mismatch → low score → Insufficient
        result = asyncio.run(compute(
            ctx=None,
            recipient={
                "proxy_brand_name": "R", "proxy_brand_code": "REC-1",
                "category_l1": "FMCG_food", "category_l2": "x", "category_l3": "y",
                "pricing_tier": "ECONOMY", "brand_size": "NICHE",
                "distribution": "NICHE", "media_maturity": "DORMANT",
                "lifecycle": "DECLINING",
            },
            proxy={
                "proxy_brand_name": "P", "proxy_brand_code": "PRX-1",
                "category_l1": "Banking", "category_l2": "x", "category_l3": "y",
                "pricing_tier": "LUXURY", "brand_size": "LEADER",
                "distribution": "NATIONAL", "media_maturity": "ALWAYS_ON",
                "lifecycle": "MATURE",
            },
        ))
        assert result["verdict"] == "Insufficient"
        assert result["block_forecast"] is True


class TestPropertyBased:
    @given(
        s=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    )
    def test_verdict_threshold_consistency(self, s: float) -> None:
        verdict = determine_verdict(s)
        if s >= 0.85:
            assert verdict == "High"
        elif s >= 0.65:
            assert verdict == "Medium"
        elif s >= 0.50:
            assert verdict == "Low"
        else:
            assert verdict == "Insufficient"
