"""Tests for synthetic corpus generator (B0.5)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aurora_launch.engines.corpus_generator import (
    generate_synthetic_project,
    list_corpus_categories,
)
from aurora_launch.engines.corpus_generator.generator import compute_bundle_hash
from aurora_launch.schemas.synthetic_corpus import SyntheticProjectSpec


@pytest.fixture
def baseline_spec() -> SyntheticProjectSpec:
    return SyntheticProjectSpec(
        seed=42,
        category_l3="FMCG_food.snacks_savoury",
        variant="baseline",
    )


def test_list_categories_non_empty() -> None:
    cats = list_corpus_categories()
    assert len(cats) > 0
    assert "FMCG_food.snacks_savoury" in cats
    assert "OTC_pharma.OTC_cold_flu" in cats


class TestSyntheticGeneration:
    def test_generates_file(self, tmp_path: Path, baseline_spec: SyntheticProjectSpec) -> None:
        output = generate_synthetic_project(baseline_spec, tmp_path)
        assert output.exists()
        assert output.suffix == ".json"
        assert "FMCG_food_snacks_savoury" in output.name

    def test_bundle_has_required_keys(
        self, tmp_path: Path, baseline_spec: SyntheticProjectSpec
    ) -> None:
        output = generate_synthetic_project(baseline_spec, tmp_path)
        with output.open() as f:
            bundle = json.load(f)
        assert bundle["schema_version"] == "3.0"
        assert "manifest_sha256" in bundle
        assert "reproducibility_token" in bundle
        assert "spec" in bundle
        assert "data" in bundle
        assert "weekly_data" in bundle["data"]
        assert len(bundle["data"]["weekly_data"]) == baseline_spec.n_weeks

    def test_seed_determinism_same_machine(
        self, tmp_path: Path, baseline_spec: SyntheticProjectSpec
    ) -> None:
        """Critical AC0.5.1 — seed produces deterministic bundle hash."""
        out1 = generate_synthetic_project(baseline_spec, tmp_path / "run1")
        out2 = generate_synthetic_project(baseline_spec, tmp_path / "run2")

        with out1.open() as f:
            b1 = json.load(f)
        with out2.open() as f:
            b2 = json.load(f)

        assert b1["manifest_sha256"] == b2["manifest_sha256"]
        assert b1["reproducibility_token"] == b2["reproducibility_token"]

    def test_different_seeds_different_hashes(self, tmp_path: Path) -> None:
        spec1 = SyntheticProjectSpec(
            seed=42,
            category_l3="FMCG_food.snacks_savoury",
            variant="baseline",
        )
        spec2 = SyntheticProjectSpec(
            seed=43,
            category_l3="FMCG_food.snacks_savoury",
            variant="baseline",
        )
        out1 = generate_synthetic_project(spec1, tmp_path / "s1")
        out2 = generate_synthetic_project(spec2, tmp_path / "s2")

        with out1.open() as f:
            b1 = json.load(f)
        with out2.open() as f:
            b2 = json.load(f)

        assert b1["manifest_sha256"] != b2["manifest_sha256"]

    def test_compute_bundle_hash_returns_consistent(
        self, tmp_path: Path, baseline_spec: SyntheticProjectSpec
    ) -> None:
        output = generate_synthetic_project(baseline_spec, tmp_path)
        manifest_hash, repro_token = compute_bundle_hash(output)

        with output.open() as f:
            bundle = json.load(f)

        assert manifest_hash == bundle["manifest_sha256"]
        assert repro_token == bundle["reproducibility_token"]

    def test_compute_bundle_hash_detects_tampering(
        self, tmp_path: Path, baseline_spec: SyntheticProjectSpec
    ) -> None:
        output = generate_synthetic_project(baseline_spec, tmp_path)

        # Tamper: modify one weekly data point
        with output.open() as f:
            bundle = json.load(f)
        bundle["data"]["weekly_data"][0]["sales_volume"] = 9999999.0

        with output.open("w") as f:
            json.dump(bundle, f, indent=2, ensure_ascii=False)

        # Recompute should fail (manifest hash mismatch)
        with pytest.raises(ValueError, match="Manifest hash mismatch"):
            compute_bundle_hash(output)

    @pytest.mark.parametrize(
        "category,variant",
        [
            ("FMCG_food.snacks_savoury", "baseline"),
            ("FMCG_beverage.beverage_energy", "high_seasonality"),
            ("OTC_pharma.OTC_cold_flu", "baseline"),
            ("Cosmetics.skincare_premium", "volatile"),
            ("awareness.brand_awareness_only", "low_data"),
        ],
    )
    def test_generates_for_all_5_corpus_categories(
        self, tmp_path: Path, category: str, variant: str
    ) -> None:
        spec = SyntheticProjectSpec(
            seed=42,
            category_l3=category,  # type: ignore[arg-type]
            variant=variant,  # type: ignore[arg-type]
        )
        output = generate_synthetic_project(spec, tmp_path)
        assert output.exists()
        with output.open() as f:
            bundle = json.load(f)
        assert "manifest_sha256" in bundle


class TestGeneratedDataValidity:
    def test_weekly_data_has_required_fields(
        self, tmp_path: Path, baseline_spec: SyntheticProjectSpec
    ) -> None:
        output = generate_synthetic_project(baseline_spec, tmp_path)
        with output.open() as f:
            bundle = json.load(f)

        records = bundle["data"]["weekly_data"]
        first = records[0]
        assert "period_date" in first
        assert "sales_volume" in first
        # Has at least one channel spend
        assert any(k.startswith("spend_") for k in first.keys())

    def test_sales_volume_non_negative(
        self, tmp_path: Path, baseline_spec: SyntheticProjectSpec
    ) -> None:
        output = generate_synthetic_project(baseline_spec, tmp_path)
        with output.open() as f:
            bundle = json.load(f)

        for record in bundle["data"]["weekly_data"]:
            assert record["sales_volume"] >= 0, "sales must be non-negative"

    def test_response_params_per_channel(
        self, tmp_path: Path, baseline_spec: SyntheticProjectSpec
    ) -> None:
        output = generate_synthetic_project(baseline_spec, tmp_path)
        with output.open() as f:
            bundle = json.load(f)

        params = bundle["data"]["response_params"]
        n_channels = baseline_spec.n_channels
        assert len(params["adstock_decay"]) == n_channels
        assert len(params["hill_gamma"]) == n_channels
        assert len(params["hill_k_normalized"]) == n_channels
        assert len(params["beta"]) == n_channels

    def test_seasonality_52_weeks(
        self, tmp_path: Path, baseline_spec: SyntheticProjectSpec
    ) -> None:
        output = generate_synthetic_project(baseline_spec, tmp_path)
        with output.open() as f:
            bundle = json.load(f)

        seasonality = bundle["data"]["seasonality_52w"]
        assert len(seasonality) == 52

    def test_adstock_decays_in_valid_range(
        self, tmp_path: Path, baseline_spec: SyntheticProjectSpec
    ) -> None:
        output = generate_synthetic_project(baseline_spec, tmp_path)
        with output.open() as f:
            bundle = json.load(f)

        decays = bundle["data"]["response_params"]["adstock_decay"]
        for d in decays:
            assert 0.05 <= d <= 0.85, f"adstock decay {d} out of physical range"
