"""Verify real PyMC posterior schema matches proxy_posterior_extractor (R-10 audit fix).

Fixture generation (~3-5 min): run `python tools/generate_pymc_fixture.py` once.
Fixture file: `tests/fixtures/real_pymc_posterior.msgpack`.

Test verifies extractor handles real PyMC output dict without KeyError/shape
mismatch — closes R-10 finding that proxy_posterior_extractor was only ever
tested against synthetic 2D ndarrays.
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "real_pymc_posterior.msgpack"


@pytest.mark.skipif(
    not FIXTURE_PATH.exists(),
    reason="Real PyMC fixture not generated. Run: python tools/generate_pymc_fixture.py",
)
class TestRealPyMCFixture:
    def test_extractor_handles_real_posterior(self) -> None:
        """Real PyMC output dict → proxy_posterior_extractor.extract_proxy_priors works."""
        from aurora_launch.engines.proxy_posterior_extractor import (
            extract_proxy_priors,
        )
        from aurora_launch.persistence.safe_serializer import deserialize

        fixture = deserialize(FIXTURE_PATH.read_bytes())
        posterior_samples = fixture["posterior_samples"]
        media_cols = fixture["media_cols"]

        priors = extract_proxy_priors(posterior_samples, media_cols)

        # Verify all channels extracted
        assert len(priors) == len(media_cols)
        for channel_id in media_cols:
            assert channel_id in priors
            p = priors[channel_id]
            # β values must be non-negative (HalfNormal prior)
            assert p.proxy_beta_mean >= 0.0
            assert p.proxy_beta_std > 0.0
            # adstock decay в [0, 1]
            assert 0.0 <= p.adstock_decay <= 1.0
            # hill alpha clamped к [0.01, 20.0]
            assert 0.01 <= p.hill_alpha <= 20.0
            # half_saturation positive
            assert p.hill_half_saturation > 0.0

    def test_fixture_contains_required_keys(self) -> None:
        """Verify fixture schema."""
        from aurora_launch.persistence.safe_serializer import deserialize

        fixture = deserialize(FIXTURE_PATH.read_bytes())
        required = {
            "posterior_samples", "media_cols", "y_mean", "y_std",
            "n_periods", "schema_version", "convergence_rhat_max",
        }
        assert required <= set(fixture.keys())

        # Posterior dict has required keys (matches bayesian_engine schema)
        samples = fixture["posterior_samples"]
        required_keys = {
            "media_betas", "alphas", "gammas", "adstock_decay",
            "intercept", "control_betas",
        }
        assert required_keys <= set(samples.keys())

    def test_fixture_convergence_acceptable(self) -> None:
        """Sampled posterior must converge (R̂ < 1.1) для useful fixture."""
        from aurora_launch.persistence.safe_serializer import deserialize

        fixture = deserialize(FIXTURE_PATH.read_bytes())
        assert fixture["convergence_rhat_max"] < 1.10, (
            f"Fixture has poor convergence R̂={fixture['convergence_rhat_max']:.4f}"
        )
