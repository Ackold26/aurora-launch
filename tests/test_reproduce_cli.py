"""Tests for aurora-launch-reproduce CLI (BLOCKER B1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from aurora_launch.engines.corpus_generator import generate_synthetic_project
from aurora_launch.schemas.synthetic_corpus import SyntheticProjectSpec
from aurora_launch.tools.reproduce import main as reproduce_main


@pytest.fixture
def synthetic_bundle(tmp_path: Path) -> tuple[Path, str, str]:
    """Generate a bundle and return (path, manifest_hash, repro_token)."""
    spec = SyntheticProjectSpec(
        seed=42,
        category_l3="FMCG_food.snacks_savoury",
        variant="baseline",
    )
    bundle_path = generate_synthetic_project(spec, tmp_path)
    with bundle_path.open() as f:
        bundle = json.load(f)
    return bundle_path, bundle["manifest_sha256"], bundle["reproducibility_token"]


class TestReproduceCli:
    def test_match_exit_zero(self, synthetic_bundle: tuple[Path, str, str]) -> None:
        path, expected_hash, _ = synthetic_bundle
        runner = CliRunner()
        result = runner.invoke(reproduce_main, [str(path), expected_hash])
        assert result.exit_code == 0
        assert "verified" in result.output.lower()

    def test_mismatch_exit_one(self, synthetic_bundle: tuple[Path, str, str]) -> None:
        path, _, _ = synthetic_bundle
        wrong_hash = "0" * 64
        runner = CliRunner()
        result = runner.invoke(reproduce_main, [str(path), wrong_hash])
        assert result.exit_code == 1
        assert "mismatch" in result.output.lower()

    def test_file_not_found_exit_two(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "nonexistent.json"
        runner = CliRunner()
        result = runner.invoke(reproduce_main, [str(nonexistent), "abc123"])
        # Click handles file existence check (UsageError exit 2)
        assert result.exit_code == 2

    def test_json_output_match(self, synthetic_bundle: tuple[Path, str, str]) -> None:
        path, expected_hash, _ = synthetic_bundle
        runner = CliRunner()
        result = runner.invoke(reproduce_main, [str(path), expected_hash, "--json-output"])
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["status"] == "match"
        assert output["computed_hash"] == expected_hash

    def test_json_output_mismatch(self, synthetic_bundle: tuple[Path, str, str]) -> None:
        path, _, _ = synthetic_bundle
        runner = CliRunner()
        result = runner.invoke(
            reproduce_main, [str(path), "0" * 64, "--json-output"]
        )
        assert result.exit_code == 1
        output = json.loads(result.output)
        assert output["status"] == "mismatch"
        assert "expected_hash" in output

    def test_check_mode_reproducibility_token(
        self, synthetic_bundle: tuple[Path, str, str]
    ) -> None:
        path, _, repro_token = synthetic_bundle
        runner = CliRunner()
        result = runner.invoke(
            reproduce_main,
            [str(path), repro_token, "--check-mode", "reproducibility_token"],
        )
        assert result.exit_code == 0

    def test_tampered_bundle_error(self, synthetic_bundle: tuple[Path, str, str]) -> None:
        """If bundle internal manifest hash mismatch — exit 2 (error)."""
        path, expected_hash, _ = synthetic_bundle
        # Tamper: modify weekly data
        with path.open() as f:
            bundle = json.load(f)
        bundle["data"]["weekly_data"][0]["sales_volume"] = 9999999.0
        with path.open("w") as f:
            json.dump(bundle, f)

        runner = CliRunner()
        result = runner.invoke(reproduce_main, [str(path), expected_hash])
        # Internal manifest hash recompute fails → exit 2 (error)
        assert result.exit_code == 2
        assert "mismatch" in result.output.lower() or "manifest" in result.output.lower()
