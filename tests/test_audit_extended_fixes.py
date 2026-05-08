"""Tests для post-Block-1D extended audit fixes.

Coverage:
- HIGH-1: Pydantic schemas в proxy.py reject unknown fields (extra="forbid"),
  immutable (frozen), и weights_used sum validation
- HIGH-2: DSM V2024 detect rejects files с 2023/2025 year markers
- HIGH-3: format adapters refuse files >MAX_INPUT_FILE_BYTES
- HIGH-4: migrate_bundle refuses to overwrite existing target without --force
- MEDIUM: similarity_calculator.determine_verdict rejects NaN/Inf
"""

from __future__ import annotations

import io
import json
import math
import tempfile
import zipfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurora_launch.engines.format_adapters import (
    MAX_INPUT_FILE_BYTES,
    AdapterRegistry,
    FormatAdapterFileTooLarge,
    assert_file_size_ok,
)
from aurora_launch.engines.format_adapters.dsm_v2023 import DsmAdapterV2023
from aurora_launch.engines.format_adapters.dsm_v2024 import DsmAdapterV2024
from aurora_launch.engines.format_adapters.dsm_v2025 import DsmAdapterV2025
from aurora_launch.engines.format_adapters.registry import build_default_registry
from aurora_launch.engines.similarity_calculator import determine_verdict
from aurora_launch.schemas.proxy import (
    AnonymizationDetails,
    ProxyBrandMetadata,
    ProxyEntry,
    SimilarityDimensionScores,
)


# ============================================================================
# HIGH-1: Pydantic schemas immutability + extra="forbid"
# ============================================================================


class TestSchemasExtraForbid:
    def test_proxy_entry_rejects_unknown_fields(self):
        with pytest.raises(ValidationError, match="extra"):
            ProxyEntry(
                proxy_brand_name="Acme",
                proxy_brand_code="ACME01",
                category_l1="FMCG",
                category_l2="Food",
                category_l3="Snacks",
                pricing_tier="MAINSTREAM",
                brand_size="CHALLENGER",
                distribution="NATIONAL",
                media_maturity="ALWAYS_ON",
                lifecycle="MATURE",
                injected_field="MALICIOUS",  # type: ignore[call-arg]
            )

    def test_proxy_entry_is_frozen(self):
        e = ProxyEntry(
            proxy_brand_name="Acme",
            proxy_brand_code="ACME01",
            category_l1="FMCG",
            category_l2="Food",
            category_l3="Snacks",
            pricing_tier="MAINSTREAM",
            brand_size="CHALLENGER",
            distribution="NATIONAL",
            media_maturity="ALWAYS_ON",
            lifecycle="MATURE",
        )
        with pytest.raises(ValidationError):
            e.proxy_brand_name = "Tampered"  # type: ignore[misc]

    def test_similarity_dimension_scores_rejects_unknown(self):
        with pytest.raises(ValidationError, match="extra"):
            SimilarityDimensionScores(
                category_l1_match=0.9,
                category_l2_match=0.8,
                category_l3_match=0.7,
                pricing_tier_match=0.8,
                brand_size_match=0.7,
                distribution_match=0.6,
                media_maturity_match=0.7,
                lifecycle_match=0.6,
                hidden_backdoor=True,  # type: ignore[call-arg]
            )

    def test_anonymization_details_rejects_unknown(self):
        with pytest.raises(ValidationError, match="extra"):
            AnonymizationDetails(
                synchronized_random_factor=1.0,
                period_shift_months=3,
                arbitrary_extra_field=42,  # type: ignore[call-arg]
            )

    def test_weights_used_sum_validation_passes_when_correct(self):
        s = SimilarityDimensionScores(
            category_l1_match=0.9,
            category_l2_match=0.9,
            category_l3_match=0.9,
            pricing_tier_match=0.8,
            brand_size_match=0.7,
            distribution_match=0.6,
            media_maturity_match=0.7,
            lifecycle_match=0.6,
            weights_used={"a": 0.5, "b": 0.3, "c": 0.2},
        )
        assert sum(s.weights_used.values()) == 1.0

    def test_weights_used_sum_validation_rejects_off(self):
        with pytest.raises(ValidationError, match="sum to ~1.0"):
            SimilarityDimensionScores(
                category_l1_match=0.9,
                category_l2_match=0.9,
                category_l3_match=0.9,
                pricing_tier_match=0.8,
                brand_size_match=0.7,
                distribution_match=0.6,
                media_maturity_match=0.7,
                lifecycle_match=0.6,
                weights_used={"a": 0.5, "b": 0.3},  # sums to 0.8
            )

    def test_weights_used_empty_passes(self):
        """Empty weights_used (default) skips sum check."""
        s = SimilarityDimensionScores(
            category_l1_match=0.9,
            category_l2_match=0.9,
            category_l3_match=0.9,
            pricing_tier_match=0.8,
            brand_size_match=0.7,
            distribution_match=0.6,
            media_maturity_match=0.7,
            lifecycle_match=0.6,
        )
        assert s.weights_used == {}


# ============================================================================
# HIGH-2: DSM V2024 detect rejects foreign year markers
# ============================================================================


class TestDsmV2024NoCollision:
    def test_v2024_rejects_2023_marker_in_xlsx(self):
        adapter = DsmAdapterV2024()
        # Previously: matched on `.dsm` substring + `.xlsx` suffix
        assert not adapter.detect("data.dsm.2023.xlsx")
        assert not adapter.detect("annual_dsm_2023.xlsx")

    def test_v2024_rejects_2025_marker_in_xlsx(self):
        adapter = DsmAdapterV2024()
        assert not adapter.detect("annual_dsm_2025.xlsx")

    def test_v2024_still_matches_canonical_v2024_files(self):
        adapter = DsmAdapterV2024()
        assert adapter.detect("data.dsm.xlsx")  # no year marker → V2024
        assert adapter.detect("dsm_2024_export.csv")

    def test_registry_dispatches_v2023_xlsx_to_v2023(self, tmp_path: Path):
        registry = build_default_registry()
        # Create file with V2023 year marker
        f = tmp_path / "annual_dsm_2023.xlsx"
        f.write_bytes(b"")  # empty placeholder, name-based detection
        adapter = registry.detect(f)
        assert adapter is not None
        assert adapter.get_metadata().adapter_id == "dsm_v2023"

    def test_v2024_csv_header_sniff_rejects_v2023_column(self, tmp_path: Path):
        adapter = DsmAdapterV2024()
        f = tmp_path / "ambig.csv"
        # Header has ; AND Дата_продажи (V2023 marker) — must reject
        f.write_text(
            "Бренд;Дата_продажи;Продажи\nA;01.01.2023;100\n",
            encoding="utf-8-sig",
        )
        assert not adapter.detect(str(f))


# ============================================================================
# HIGH-3: Format adapters refuse oversized files
# ============================================================================


class TestAdapterFileSizeCap:
    def test_assert_file_size_ok_passes_under_cap(self, tmp_path: Path):
        f = tmp_path / "small.csv"
        f.write_bytes(b"X" * 1000)
        assert_file_size_ok(f)  # no raise

    def test_assert_file_size_ok_rejects_over_cap(self, tmp_path: Path):
        f = tmp_path / "big.csv"
        # Use sparse/quick approach — write minimal content but report large size
        # is impossible without actually writing. Use monkeypatched cap для скорости.
        f.write_bytes(b"X" * 1000)
        with pytest.raises(FormatAdapterFileTooLarge, match="too large"):
            assert_file_size_ok(f, cap=500)

    def test_assert_file_size_ok_nonexistent_path_passes(self, tmp_path: Path):
        # Helper deliberately delegates non-existence to caller's FileNotFoundError
        assert_file_size_ok(tmp_path / "nope.csv")

    def test_dsm_v2024_parse_refuses_oversized(self, tmp_path: Path, monkeypatch):
        """Replace assert_file_size_ok с tiny-cap version to avoid writing 256 MB."""
        from aurora_launch.engines import format_adapters as fa_mod

        def tiny_cap_assert(path, *, cap=100):
            return fa_mod.assert_file_size_ok.__wrapped__(path, cap=100) if hasattr(
                fa_mod.assert_file_size_ok, "__wrapped__"
            ) else _tiny_check(path)

        def _tiny_check(path):
            from pathlib import Path as _Path
            p = _Path(path)
            if not p.exists():
                return
            if p.stat().st_size > 100:
                raise FormatAdapterFileTooLarge(
                    f"Input file {p} too large: {p.stat().st_size} > 100"
                )

        monkeypatch.setattr(fa_mod, "assert_file_size_ok", _tiny_check)

        f = tmp_path / "dsm_2024_big.csv"
        f.write_text(
            "Бренд;Дата;Продажи_упаковки\n" + "A;2024-01-01;100\n" * 50,
            encoding="utf-8-sig",
        )
        adapter = DsmAdapterV2024()
        with pytest.raises(FormatAdapterFileTooLarge):
            adapter.parse(str(f))

    def test_default_cap_is_reasonable(self):
        # 256 MB default is documented; sanity check: not zero, not absurd
        assert MAX_INPUT_FILE_BYTES >= 64 * 1024 * 1024
        assert MAX_INPUT_FILE_BYTES <= 1024 * 1024 * 1024


# ============================================================================
# HIGH-4: migrate_bundle refuses overwrite without --force
# ============================================================================


class TestMigrateBundleOverwriteGuard:
    def _make_legacy(self, path: Path) -> None:
        """Create a minimal legacy `.aurora.json` для migration test."""
        legacy = {
            "aurora_launch_version": "0.0.5",
            "manifest_sha256": "a" * 64,
            "schema_version": "3.0",
            "created_at": "2025-01-01T00:00:00Z",
            "last_modified": "2025-01-01T00:00:00Z",
        }
        path.write_text(json.dumps(legacy), encoding="utf-8")

    def test_migrate_refuses_to_overwrite_existing_target(self, tmp_path: Path):
        from aurora_launch.tools.migrate_bundle import _migrate_one, _plan

        legacy = tmp_path / "bundle.aurora.json"
        self._make_legacy(legacy)

        target = tmp_path / "bundle.aurora"
        target.write_bytes(b"PRIOR_MIGRATION_OUTPUT")  # simulate prior run

        plan = _plan(legacy)
        assert plan.target == target

        # Without force — refused, target untouched
        result = _migrate_one(plan, dry_run=False, force=False)
        assert result is False
        assert target.read_bytes() == b"PRIOR_MIGRATION_OUTPUT"

    def test_migrate_with_force_overwrites_target(self, tmp_path: Path):
        from aurora_launch.tools.migrate_bundle import _migrate_one, _plan

        legacy = tmp_path / "bundle.aurora.json"
        self._make_legacy(legacy)

        target = tmp_path / "bundle.aurora"
        target.write_bytes(b"PRIOR_MIGRATION_OUTPUT")

        plan = _plan(legacy)
        result = _migrate_one(plan, dry_run=False, force=True)
        assert result is True
        # Target now is real ZIP, not the prior placeholder
        assert target.read_bytes() != b"PRIOR_MIGRATION_OUTPUT"
        with zipfile.ZipFile(target, "r") as zf:
            assert "manifest.json" in zf.namelist()

    def test_migrate_no_target_collision_unaffected(self, tmp_path: Path):
        """Когда target doesn't exist, migration proceeds normally без --force."""
        from aurora_launch.tools.migrate_bundle import _migrate_one, _plan

        legacy = tmp_path / "fresh.aurora.json"
        self._make_legacy(legacy)

        plan = _plan(legacy)
        # target does NOT exist
        result = _migrate_one(plan, dry_run=False, force=False)
        assert result is True


# ============================================================================
# MEDIUM: NaN guard в determine_verdict
# ============================================================================


class TestDetermineVerdictNaNGuard:
    def test_nan_score_raises(self):
        with pytest.raises(ValueError, match="finite"):
            determine_verdict(float("nan"))

    def test_inf_score_raises(self):
        with pytest.raises(ValueError, match="finite"):
            determine_verdict(float("inf"))

    def test_neg_inf_score_raises(self):
        with pytest.raises(ValueError, match="finite"):
            determine_verdict(float("-inf"))

    def test_normal_scores_unaffected(self):
        assert determine_verdict(0.95) == "High"
        assert determine_verdict(0.75) == "Medium"
        assert determine_verdict(0.55) == "Low"
        assert determine_verdict(0.30) == "Insufficient"

    def test_boundary_scores(self):
        assert determine_verdict(0.85) == "High"
        assert determine_verdict(0.65) == "Medium"
        assert determine_verdict(0.50) == "Low"
        assert determine_verdict(0.0) == "Insufficient"
