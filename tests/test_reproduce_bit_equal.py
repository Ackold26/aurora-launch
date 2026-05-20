"""D2.1 Sprint 2 — generate_reproduce_script bit-equal acceptance test.

Spec contract (ReproductionInstructions.expected_rtol_deterministic = 1e-4):
    Running the generated reproduce script against the saved .aurora bundle
    must produce forecast points bit-equal to the original forecast
    within rtol < 1e-4 for deterministic engines (PURE_TRANSFER).

Two complementary test strategies:
    1. API-level: call forecast_recipient twice with the same proxy + inputs,
       compare results. This is the canonical bit-equal proof regardless of
       the script execution mechanism.
    2. Subprocess: write the generated script to a temp .py file, execute it
       via sys.executable, parse stdout, compare to original. Mirrors the
       customer "python reproduce.py" flow exactly.

Pre-existing template bugs in tools/reproduce_script.py surfaced and fixed
in the same Sprint 2 D2.1 commit:
    - bundle.get_bytes(entry) → bundle.files[entry] (no get_bytes method exists
      on LoadedBundle / LazyLoadedBundle — was AttributeError at runtime).
    - json.dumps(anchors) → pprint.pformat(anchors) (json emits "null"/"true"/
      "false" which raises NameError when re-evaluated as Python source).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import numpy.testing as npt
import pytest

from aurora_launch import __version__
from aurora_launch.engines.bundle_container import BundleZipWriter
from aurora_launch.engines.launch_orchestrator import (
    LaunchOrchestrator,
    make_proxy_bundle,
)
from aurora_launch.engines.pure_transfer_engine import RecipientAnchors
from aurora_launch.persistence.safe_serializer import serialize
from aurora_launch.tools.reproduce_script import generate_reproduce_script

# ---------------------------------------------------------------------------
# Deterministic tolerance (from ReproductionInstructions schema)
# ---------------------------------------------------------------------------

RTOL_DETERMINISTIC = 1e-4  # ReproductionInstructions.expected_rtol_deterministic


# ---------------------------------------------------------------------------
# Shared fixture: minimal deterministic proxy + inputs
# ---------------------------------------------------------------------------

_ANCHORS_DICT: dict[str, Any] = {
    "market_size": 1_000_000.0,
    "market_size_cv": 0.10,
    "planned_share_trajectory": [0.05] * 12,
    "distribution_trajectory": [0.80] * 12,
    "pricing_index": 1.0,
    "elasticity": 0.0,
    "seasonality": None,
}

_SPEND_PLAN = {"tv": [100_000.0] * 12}

_HORIZON = 12
_GRANULARITY = "monthly"
_SEED = 42


def _make_deterministic_posterior(n_samples: int = 200, seed: int = 42) -> dict[str, np.ndarray]:
    """Minimal synthetic posterior — deterministic, no EconometricaDataset needed.

    Produces the same schema as bayesian_engine / derive_synthetic_posterior:
        media_betas, alphas, gammas, adstock_decay, intercept, control_betas
    All samples drawn from a fixed RNG seed so results are bit-reproducible.
    """
    rng = np.random.default_rng(seed)
    n_channels = 1  # single "tv" channel

    media_betas = rng.uniform(0.01, 0.5, size=(n_channels, n_samples))
    alphas = rng.uniform(1.5, 2.5, size=(n_channels, n_samples))
    gammas = rng.uniform(1.5, 2.5, size=(n_channels, n_samples))
    adstock_decay = rng.uniform(0.3, 0.7, size=(n_channels, n_samples))
    intercept = rng.normal(0.0, 0.1, size=n_samples).astype(np.float32)
    control_betas = np.zeros((0, n_samples), dtype=np.float32)

    return {
        "media_betas": media_betas,
        "alphas": alphas,
        "gammas": gammas,
        "adstock_decay": adstock_decay,
        "intercept": intercept,
        "control_betas": control_betas,
    }


def _make_normalization() -> dict[str, Any]:
    return {
        "y_mean": 500_000.0,
        "y_std": 50_000.0,
        "media_means": {"tv": 100_000.0},
        "control_means": {},
        "control_stds": {},
        "intercept_mean": 0.0,
        "control_betas_mean": [],
        "untrained_channels": [],
        "control_kinds": {},
        "holiday_cols_injected": [],
        "control_prior_mus": {},
        "untrained_controls": [],
    }


@pytest.fixture(scope="module")
def deterministic_proxy():
    """Build a ProxyBundle with fixed posterior — module-scoped for speed."""
    posterior = _make_deterministic_posterior()
    normalization = _make_normalization()
    return make_proxy_bundle(
        posterior_samples=posterior,
        media_cols=["tv"],
        normalization=normalization,
        config={"media_columns": ["tv"], "mode": "sales", "granularity": "monthly"},
        n_proxy_observations=48,  # > proxy_min=24 for monthly
    )


@pytest.fixture(scope="module")
def original_forecast(deterministic_proxy):
    """Run forecast_recipient once — module-scoped reference result."""
    anchors = RecipientAnchors(**_ANCHORS_DICT)
    orchestrator = LaunchOrchestrator()
    result = orchestrator.forecast_recipient(
        proxy=deterministic_proxy,
        anchors=anchors,
        spend_plan=_SPEND_PLAN,
        horizon_periods=_HORIZON,
        granularity=_GRANULARITY,
        n_recipient=0,
    )
    assert result.forecast is not None, "Reference forecast returned None"
    return result


@pytest.fixture(scope="module")
def aurora_bundle_path(tmp_path_factory, deterministic_proxy):
    """Write a minimal ZIP .aurora bundle containing the proxy posterior.

    The bundle structure mirrors what the generated reproduce script expects:
        entry name containing 'proxy' or 'posterior'
        → bytes from safe_serializer.serialize(posterior_data_dict)

    Returns path to the written .aurora ZIP file.
    """
    tmp = tmp_path_factory.mktemp("bundles")
    bundle_path = tmp / "test_project.aurora"

    # Compose posterior_data dict matching the generated script's deserialize contract
    posterior_data = {
        "posterior_samples": deterministic_proxy.posterior.posterior_samples,
        "media_cols": deterministic_proxy.posterior.media_cols,
        "normalization": dict(deterministic_proxy.posterior.normalization),
        "config": dict(deterministic_proxy.config_obj.config),
        "n_proxy_observations": deterministic_proxy.metadata.n_proxy_observations,
    }
    posterior_bytes = serialize(posterior_data)

    writer = BundleZipWriter(aurora_app_version=__version__)
    writer.add_file("proxy_posterior.msgpack", posterior_bytes, schema_version="1.0")
    writer.write(bundle_path)

    return bundle_path


# ---------------------------------------------------------------------------
# Test 1: API-level bit-equal — PURE_TRANSFER determinism
# ---------------------------------------------------------------------------


class TestPureTransferBitEqual:
    """Canonical bit-equal proof via API (no subprocess dependency)."""

    def test_pure_transfer_reproduces_bit_equal(
        self, deterministic_proxy, original_forecast
    ) -> None:
        """Running forecast_recipient twice with same inputs → identical points.

        This is the core spec acceptance criterion:
        ReproductionInstructions.expected_rtol_deterministic = 1e-4.
        PURE_TRANSFER (n_recipient=0) is deterministic — no MCMC sampling.
        """
        anchors = RecipientAnchors(**_ANCHORS_DICT)
        orchestrator = LaunchOrchestrator()
        result2 = orchestrator.forecast_recipient(
            proxy=deterministic_proxy,
            anchors=anchors,
            spend_plan=_SPEND_PLAN,
            horizon_periods=_HORIZON,
            granularity=_GRANULARITY,
            n_recipient=0,
        )
        assert result2.forecast is not None

        orig_pts = original_forecast.forecast.points
        repr_pts = result2.forecast.points

        assert len(repr_pts) == len(orig_pts), (
            f"Forecast length mismatch: original {len(orig_pts)}, reproduced {len(repr_pts)}"
        )

        orig_point = np.array([p.point_forecast for p in orig_pts])
        repr_point = np.array([p.point_forecast for p in repr_pts])
        orig_lower = np.array([p.ci_lower for p in orig_pts])
        repr_lower = np.array([p.ci_lower for p in repr_pts])
        orig_upper = np.array([p.ci_upper for p in orig_pts])
        repr_upper = np.array([p.ci_upper for p in repr_pts])

        npt.assert_allclose(
            repr_point, orig_point, rtol=RTOL_DETERMINISTIC,
            err_msg="point_forecast differs beyond rtol=1e-4",
        )
        npt.assert_allclose(
            repr_lower, orig_lower, rtol=RTOL_DETERMINISTIC,
            err_msg="ci_lower differs beyond rtol=1e-4",
        )
        npt.assert_allclose(
            repr_upper, orig_upper, rtol=RTOL_DETERMINISTIC,
            err_msg="ci_upper differs beyond rtol=1e-4",
        )

    def test_observed_rtol_is_well_under_spec_limit(
        self, deterministic_proxy, original_forecast
    ) -> None:
        """PURE_TRANSFER is fully deterministic — observed rtol must be 0.0 (exact).

        This verifies the implementation is not relying on floating-point
        tolerance to hide non-determinism: same inputs → exactly identical floats.
        """
        anchors = RecipientAnchors(**_ANCHORS_DICT)
        orchestrator = LaunchOrchestrator()
        result2 = orchestrator.forecast_recipient(
            proxy=deterministic_proxy,
            anchors=anchors,
            spend_plan=_SPEND_PLAN,
            horizon_periods=_HORIZON,
            granularity=_GRANULARITY,
            n_recipient=0,
        )
        assert result2.forecast is not None

        orig_pts = original_forecast.forecast.points
        repr_pts = result2.forecast.points

        for i, (o, r) in enumerate(zip(orig_pts, repr_pts)):
            assert o.point_forecast == r.point_forecast, (
                f"Period {i}: point_forecast not bit-exact: "
                f"original={o.point_forecast}, reproduced={r.point_forecast}"
            )
            assert o.ci_lower == r.ci_lower, (
                f"Period {i}: ci_lower not bit-exact"
            )
            assert o.ci_upper == r.ci_upper, (
                f"Period {i}: ci_upper not bit-exact"
            )


# ---------------------------------------------------------------------------
# Test 2: generate_reproduce_script — script generation is well-formed
# ---------------------------------------------------------------------------


class TestGenerateReproduceScriptContent:
    """Verify the generated script contains correct inputs for reproduction."""

    def test_script_embeds_anchors_and_spend_plan(self, aurora_bundle_path) -> None:
        """Generated script must embed the anchor values and spend channels."""
        script = generate_reproduce_script(
            bundle_path=str(aurora_bundle_path),
            anchors=_ANCHORS_DICT,
            spend_plan=_SPEND_PLAN,
            horizon_periods=_HORIZON,
            granularity=_GRANULARITY,
            seed=_SEED,
        )
        assert "market_size" in script
        assert "tv" in script
        # bundle_path is JSON-encoded in the script (backslashes escaped on Windows);
        # check the bundle filename (no path separators) appears somewhere in script.
        assert "test_project.aurora" in script

    def test_script_embeds_horizon_and_granularity(self, aurora_bundle_path) -> None:
        """Horizon and granularity must appear in the generated script's orchestrator call."""
        script = generate_reproduce_script(
            bundle_path=str(aurora_bundle_path),
            anchors=_ANCHORS_DICT,
            spend_plan=_SPEND_PLAN,
            horizon_periods=_HORIZON,
            granularity=_GRANULARITY,
            seed=_SEED,
        )
        # horizon_periods and granularity are embedded in the orchestrator call
        assert f"horizon_periods={_HORIZON}" in script
        assert f'granularity="{_GRANULARITY}"' in script


# ---------------------------------------------------------------------------
# Test 3: Subprocess execution — xfail due to get_bytes API bug
# ---------------------------------------------------------------------------


class TestSubprocessExecution:
    """Subprocess-level tests for the generated script.

    These exercise the full customer flow: write generated .py к file,
    run it via `python reproduce.py`, parse forecast table from stdout,
    compare to original. Closes spec acceptance criterion
    "python reproduce.py reproduces forecast bit-equal".
    """

    def test_reproduce_script_runs_without_error(
        self, aurora_bundle_path, tmp_path
    ) -> None:
        """Generated script subprocess exits with returncode=0 + writes forecast."""
        script = generate_reproduce_script(
            bundle_path=str(aurora_bundle_path),
            anchors=_ANCHORS_DICT,
            spend_plan=_SPEND_PLAN,
            horizon_periods=_HORIZON,
            granularity=_GRANULARITY,
            seed=_SEED,
        )
        script_path = tmp_path / "reproduce.py"
        script_path.write_text(script, encoding="utf-8")

        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        assert proc.returncode == 0, (
            f"Reproduce script exited with code {proc.returncode}.\n"
            f"STDOUT: {proc.stdout[:2000]}\n"
            f"STDERR: {proc.stderr[:2000]}"
        )
        # Script prints forecast table — must mention period index
        assert "Period" in proc.stdout or "period" in proc.stdout.lower(), (
            f"Forecast table header not found in stdout: {proc.stdout[:500]}"
        )

    def test_pure_transfer_subprocess_bit_equal(
        self, aurora_bundle_path, original_forecast, tmp_path
    ) -> None:
        """Subprocess forecast matches original within rtol=1e-4.

        Runs the generated script as a subprocess, parses its stdout for
        per-period forecast values, and compares to the API reference result.
        Closes the customer-facing reproduce validation contract.
        """
        script = generate_reproduce_script(
            bundle_path=str(aurora_bundle_path),
            anchors=_ANCHORS_DICT,
            spend_plan=_SPEND_PLAN,
            horizon_periods=_HORIZON,
            granularity=_GRANULARITY,
            seed=_SEED,
        )
        script_path = tmp_path / "reproduce.py"
        script_path.write_text(script, encoding="utf-8")

        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        assert proc.returncode == 0, (
            f"Script exited {proc.returncode}\nSTDOUT: {proc.stdout[:1000]}\nSTDERR: {proc.stderr[:1000]}"
        )

        # Parse the forecast table from stdout.
        # Generated script prints lines: "<period_idx>  <point>  <lower>  <upper>"
        # after the header separator line "---..."
        reproduced_points = []
        in_table = False
        for line in proc.stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("---"):
                in_table = True
                continue
            if in_table and stripped and not stripped.startswith("Warning"):
                parts = stripped.split()
                if len(parts) >= 4:
                    try:
                        reproduced_points.append({
                            "period_index": int(parts[0]),
                            "point_forecast": float(parts[1]),
                            "ci_lower": float(parts[2]),
                            "ci_upper": float(parts[3]),
                        })
                    except (ValueError, IndexError):
                        continue

        assert len(reproduced_points) == _HORIZON, (
            f"Expected {_HORIZON} periods from subprocess, got {len(reproduced_points)}.\n"
            f"STDOUT: {proc.stdout[:1000]}"
        )

        orig_pts = original_forecast.forecast.points
        orig_point = np.array([p.point_forecast for p in orig_pts])
        orig_lower = np.array([p.ci_lower for p in orig_pts])
        orig_upper = np.array([p.ci_upper for p in orig_pts])

        repr_point = np.array([p["point_forecast"] for p in reproduced_points])
        repr_lower = np.array([p["ci_lower"] for p in reproduced_points])
        repr_upper = np.array([p["ci_upper"] for p in reproduced_points])

        npt.assert_allclose(
            repr_point, orig_point, rtol=RTOL_DETERMINISTIC,
            err_msg="Subprocess point_forecast differs from API result beyond rtol=1e-4",
        )
        npt.assert_allclose(
            repr_lower, orig_lower, rtol=RTOL_DETERMINISTIC,
            err_msg="Subprocess ci_lower differs from API result beyond rtol=1e-4",
        )
        npt.assert_allclose(
            repr_upper, orig_upper, rtol=RTOL_DETERMINISTIC,
            err_msg="Subprocess ci_upper differs from API result beyond rtol=1e-4",
        )


# ---------------------------------------------------------------------------
# Test 4: Sanity — different seeds → different results (non-vacuous check)
# ---------------------------------------------------------------------------


class TestDeterminismSanity:
    """Verify that bit-equality is not vacuous (different inputs → different outputs)."""

    def test_different_spend_plan_gives_different_forecast(
        self, deterministic_proxy
    ) -> None:
        """Changed spend_plan must produce different forecast.

        Guards against a degenerate implementation where spend has no effect
        (which would make the bit-equal test trivially true for wrong reasons).
        """
        anchors = RecipientAnchors(**_ANCHORS_DICT)
        orchestrator = LaunchOrchestrator()

        result_low = orchestrator.forecast_recipient(
            proxy=deterministic_proxy,
            anchors=anchors,
            spend_plan={"tv": [10_000.0] * 12},  # 10× lower spend
            horizon_periods=_HORIZON,
            granularity=_GRANULARITY,
            n_recipient=0,
        )
        result_high = orchestrator.forecast_recipient(
            proxy=deterministic_proxy,
            anchors=anchors,
            spend_plan={"tv": [500_000.0] * 12},  # 5× higher spend
            horizon_periods=_HORIZON,
            granularity=_GRANULARITY,
            n_recipient=0,
        )

        assert result_low.forecast is not None
        assert result_high.forecast is not None

        low_pts = np.array([p.point_forecast for p in result_low.forecast.points])
        high_pts = np.array([p.point_forecast for p in result_high.forecast.points])

        # Higher spend → higher forecast (channel contributes positively)
        assert np.mean(high_pts) > np.mean(low_pts), (
            "Higher spend did not produce higher forecast — sanity failure. "
            f"low_mean={np.mean(low_pts):.2f}, high_mean={np.mean(high_pts):.2f}"
        )

    def test_same_inputs_different_posterior_magnitude_diverges(self) -> None:
        """Different proxy posterior magnitude → different forecast.

        PURE_TRANSFER uses the *mean* of posterior samples. The baseline
        (market_size × share × distribution) can dominate media contribution
        when betas are small. This test forces a detectable difference by
        using media spend much larger than the normalization mean so that
        the hill-transformed contribution amplifies the beta difference.

        Uses y_std=1.0 (rather than 50K) in normalization so the beta
        scaling (which operates in normalised space) has a large absolute
        effect on the final forecast.
        """
        # Normalization with small y_mean (1.0) and y_std=1.0 means beta is
        # numerically large relative to the baseline ratio, amplifying differences.
        norm_unit_std = {
            "y_mean": 1.0,  # must be > 0 per proxy_baseline_from_normalization contract
            "y_std": 1.0,
            "media_means": {"tv": 1.0},
            "control_means": {},
            "control_stds": {},
            "intercept_mean": 0.0,
            "control_betas_mean": [],
            "untrained_channels": [],
            "control_kinds": {},
            "holiday_cols_injected": [],
            "control_prior_mus": {},
            "untrained_controls": [],
        }
        anchors = RecipientAnchors(**_ANCHORS_DICT)
        orchestrator = LaunchOrchestrator()

        def _run_with_beta_value(beta_value: float) -> np.ndarray:
            """Posterior with all media_betas = beta_value (deterministic mean)."""
            n_samples = 50
            posterior = {
                # All samples identical → mean = beta_value (maximally explicit)
                "media_betas": np.full((1, n_samples), beta_value),
                "alphas": np.full((1, n_samples), 2.0),
                "gammas": np.full((1, n_samples), 2.0),
                "adstock_decay": np.full((1, n_samples), 0.5),
                "intercept": np.zeros(n_samples, dtype=np.float32),
                "control_betas": np.zeros((0, n_samples), dtype=np.float32),
            }
            proxy = make_proxy_bundle(
                posterior_samples=posterior,
                media_cols=["tv"],
                normalization=norm_unit_std,
                config={"media_columns": ["tv"], "mode": "sales"},
                n_proxy_observations=48,
            )
            result = orchestrator.forecast_recipient(
                proxy=proxy,
                anchors=anchors,
                spend_plan=_SPEND_PLAN,
                horizon_periods=_HORIZON,
                granularity=_GRANULARITY,
                n_recipient=0,
            )
            assert result.forecast is not None
            return np.array([p.point_forecast for p in result.forecast.points])

        # 0.0 media effect (no contribution from spend) vs 100.0 (large)
        pts_zero = _run_with_beta_value(0.0)
        pts_large = _run_with_beta_value(100.0)

        # Large beta must produce meaningfully larger forecast
        assert np.mean(pts_large) != np.mean(pts_zero), (
            "Forecast is identical for beta=0.0 and beta=100.0 — "
            "sanity failure suggesting media betas have no effect on forecast. "
            f"zero_mean={np.mean(pts_zero):.4f}, large_mean={np.mean(pts_large):.4f}"
        )
