"""Tests for Pydantic schemas (B0.5/B1/B2 schema validation)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aurora_launch.schemas.proxy import (
    AnonymizationDetails,
    ProxyBrandMetadata,
    ProxyEntry,
    SimilarityDimensionScores,
)
from aurora_launch.schemas.synthetic_corpus import (
    FormatAdapterContract,
    SyntheticProjectSpec,
)


class TestSyntheticProjectSpec:
    def test_minimum_valid(self) -> None:
        spec = SyntheticProjectSpec(
            seed=42,
            category_l3="FMCG_food.snacks_savoury",
            variant="baseline",
        )
        assert spec.seed == 42
        assert spec.n_weeks == 104  # default
        assert spec.n_channels == 6  # default

    def test_seed_must_be_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            SyntheticProjectSpec(
                seed=-1,
                category_l3="FMCG_food.snacks_savoury",
                variant="baseline",
            )

    def test_n_weeks_lower_bound(self) -> None:
        with pytest.raises(ValidationError):
            SyntheticProjectSpec(
                seed=42,
                category_l3="FMCG_food.snacks_savoury",
                variant="baseline",
                n_weeks=50,
            )

    def test_invalid_category_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SyntheticProjectSpec(
                seed=42,
                category_l3="invalid.category",  # type: ignore[arg-type]
                variant="baseline",
            )


class TestSimilarityDimensionScores:
    def test_all_scores_in_range(self) -> None:
        scores = SimilarityDimensionScores(
            category_l1_match=1.0,
            category_l2_match=1.0,
            category_l3_match=1.0,
            pricing_tier_match=0.5,
            brand_size_match=0.7,
            distribution_match=1.0,
            media_maturity_match=0.8,
            lifecycle_match=0.6,
        )
        assert scores.category_l1_match == 1.0

    def test_score_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SimilarityDimensionScores(
                category_l1_match=1.5,
                category_l2_match=1.0,
                category_l3_match=1.0,
                pricing_tier_match=0.5,
                brand_size_match=0.7,
                distribution_match=1.0,
                media_maturity_match=0.8,
                lifecycle_match=0.6,
            )


class TestProxyBrandMetadata:
    def _valid_dims(self) -> SimilarityDimensionScores:
        return SimilarityDimensionScores(
            category_l1_match=1.0,
            category_l2_match=1.0,
            category_l3_match=1.0,
            pricing_tier_match=0.8,
            brand_size_match=0.7,
            distribution_match=1.0,
            media_maturity_match=0.8,
            lifecycle_match=0.6,
        )

    def _valid_anon(self) -> AnonymizationDetails:
        return AnonymizationDetails(
            synchronized_random_factor=1.5,
            period_shift_months=-12,
        )

    def test_verdict_consistent_with_score_high(self) -> None:
        meta = ProxyBrandMetadata(
            proxy_code="ABC-2026-Q1",
            similarity_dimensions=self._valid_dims(),
            similarity_score=0.92,
            verdict="High",
            inflation_factor=1.2,
            anonymization_applied=self._valid_anon(),
        )
        assert meta.verdict == "High"

    def test_verdict_inconsistent_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ProxyBrandMetadata(
                proxy_code="ABC-2026-Q1",
                similarity_dimensions=self._valid_dims(),
                similarity_score=0.92,
                verdict="Insufficient",  # inconsistent — should be High
                inflation_factor=1.2,
                anonymization_applied=self._valid_anon(),
            )

    def test_proxy_code_pattern_uppercase_only(self) -> None:
        with pytest.raises(ValidationError):
            ProxyBrandMetadata(
                proxy_code="abc-2026",  # lowercase, fails pattern
                similarity_dimensions=self._valid_dims(),
                similarity_score=0.92,
                verdict="High",
                inflation_factor=1.2,
                anonymization_applied=self._valid_anon(),
            )

    def test_anonymization_synchronized_factor_positive(self) -> None:
        with pytest.raises(ValidationError):
            AnonymizationDetails(
                synchronized_random_factor=0.0,  # must be > 0
                period_shift_months=0,
            )


class TestProxyEntry:
    def test_minimum_valid(self) -> None:
        entry = ProxyEntry(
            proxy_brand_name="Lipton Iced Tea",
            proxy_brand_code="LIPTON-2026-Q1",
            category_l1="FMCG_beverage",
            category_l2="beverage_tea",
            category_l3="beverage_tea_cold",
            pricing_tier="PREMIUM",
            brand_size="LEADER",
            distribution="NATIONAL",
            media_maturity="ALWAYS_ON",
            lifecycle="MATURE",
        )
        assert entry.proxy_brand_name == "Lipton Iced Tea"


class TestFormatAdapterContract:
    def test_adapter_id_pattern(self) -> None:
        with pytest.raises(ValidationError):
            FormatAdapterContract(
                adapter_id="DSM-V2024",  # uppercase + dash, fails pattern
                adapter_version="0.1.0",
                schema_version="2024",
                sample_files_glob=["*.dsm.xlsx"],
                canonical_record_mapping={},
            )

    def test_valid_adapter_id(self) -> None:
        contract = FormatAdapterContract(
            adapter_id="dsm_v2024",
            adapter_version="0.1.0",
            schema_version="2024",
            sample_files_glob=["*.dsm.xlsx"],
            canonical_record_mapping={"col": "canonical_col"},
        )
        assert contract.adapter_id == "dsm_v2024"
