"""Generate real PyMC InferenceData fixture для R-10 audit verification (one-time).

Closes audit R-10: проверяет что proxy_posterior_extractor работает против
real PyMC output schema, не только synthetic dict.

Usage:
    python tools/generate_pymc_fixture.py
    → writes tests/fixtures/real_pymc_posterior.msgpack

Runtime: ~3-5 minutes (small PyMC model, 500 draws × 2 chains).

The fixture stores the dict that bayesian_engine.train_model produces в
'posterior_samples' field, NOT a full arviz.InferenceData (which would
contain prior groups etc и unnecessary size).

CI runs `tests/test_real_pymc_fixture.py::test_extractor_handles_real_posterior`
once per release to verify schema contract.

Note: this script imports pymc which takes ~5s — runs on demand only.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

# Ensure repo src is on path для standalone script invocation.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))


def generate_fixture(output_path: Path, *, seed: int = 42) -> None:
    """Generate small real-PyMC posterior dict в bayesian_engine output schema.

    Synthesizes Кагоцел-like data (12 months × 4 channels) and runs a
    minimal PyMC model с HalfNormal priors на media betas + Gamma на
    hill alphas + Beta on hill gammas + Logit-Normal on adstock decay.

    Final samples_dict shape per key: (n_channels, n_samples)
        where n_samples = n_chains × n_draws.
    """
    import pymc as pm  # noqa: PLC0415 — heavy import deferred
    import arviz as az  # noqa: PLC0415 — heavy import deferred

    print(f"Generating fixture к {output_path}...", flush=True)

    rng = np.random.default_rng(seed)
    n_periods = 12
    media_cols = ["olv", "banners", "social", "performance"]
    n_channels = len(media_cols)

    # Synthetic spend + sales (Кагоцел-like values)
    spend = rng.normal(loc=2_000_000.0, scale=500_000.0, size=(n_periods, n_channels))
    spend = np.clip(spend, 100_000.0, None)
    spend_normalised = spend / spend.mean(axis=0)
    true_betas = np.array([0.15, 0.10, 0.05, 0.20])
    y = 100_000_000.0 + (spend_normalised @ true_betas) * 50_000_000.0
    y += rng.normal(0.0, 5_000_000.0, size=n_periods)
    y_mean, y_std = float(np.mean(y)), float(np.std(y))
    y_norm = (y - y_mean) / y_std

    print(f"Synthesised data: y range {y.min():.2e} - {y.max():.2e}")
    print("Building PyMC model...")

    with pm.Model():
        media_betas = pm.HalfNormal("media_betas", sigma=0.3, shape=n_channels)
        alphas = pm.Gamma("alphas", alpha=5.0, beta=3.0, shape=n_channels)
        gammas = pm.Beta("gammas", alpha=3.0, beta=3.0, shape=n_channels)
        adstock_decay = pm.Beta("adstock_decay", alpha=2.0, beta=2.0, shape=n_channels)
        # Simple linear (no actual adstock+hill чтобы fit fast)
        mu = pm.math.dot(spend_normalised, media_betas)
        sigma = pm.HalfNormal("sigma", sigma=0.3)
        pm.Normal("y", mu=mu, sigma=sigma, observed=y_norm)

        print("Running NUTS sampling (~30-60s)...")
        trace = pm.sample(
            draws=500,
            tune=200,
            chains=2,
            cores=1,
            return_inferencedata=True,
            random_seed=seed,
            progressbar=False,
        )

    print(f"Sampling complete. R̂ max: {float(az.rhat(trace).max().to_array().max()):.4f}")

    # Extract в bayesian_engine output schema dict.
    # PI-RESCUE-06 audit fix: removed dead if/else branch — both paths assigned identically.
    samples_dict: dict[str, np.ndarray] = {}
    for key in ["media_betas", "alphas", "gammas", "adstock_decay"]:
        # shape: (chain, draw, channel) → (channel, chain*draw) after stack
        stacked = trace.posterior[key].stack(sample=("chain", "draw"))
        samples_dict[key] = np.asarray(stacked.values, dtype=np.float32)
        print(f"  {key}: shape {samples_dict[key].shape}")

    # Add intercept + control_betas keys per R-12 (real PyMC also produces these)
    # In this minimal model intercept ≈ 0 (normalised), control_betas empty.
    n_samples = samples_dict["media_betas"].shape[1]
    samples_dict["intercept"] = np.zeros(n_samples, dtype=np.float32)
    samples_dict["control_betas"] = np.zeros((0, n_samples), dtype=np.float32)

    fixture = {
        "posterior_samples": samples_dict,
        "media_cols": media_cols,
        "y_mean": y_mean,
        "y_std": y_std,
        "n_periods": n_periods,
        "schema_version": "1.0-real-pymc",
        "model_description": "Minimal HalfNormal+Gamma+Beta model — fixture для R-10 verification",
        "convergence_rhat_max": float(az.rhat(trace).max().to_array().max()),
    }

    # Use safe_serializer to write msgpack (consistent with blob_store format)
    from aurora_launch.persistence.safe_serializer import serialize  # noqa: PLC0415

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(serialize(fixture))
    print(f"\nFixture written к {output_path} ({output_path.stat().st_size} bytes)")


if __name__ == "__main__":
    target = REPO_ROOT / "tests" / "fixtures" / "real_pymc_posterior.msgpack"
    generate_fixture(target)
