"""Phase Π.2.3 — Proxy posterior extractor tests.

Coverage:
- Schema validation (missing keys, wrong shapes, inconsistent n_samples)
- Extraction correctness (mean / std per channel, n_samples preserved)
- Shrinkage formula (0=no shrink, 1=delta, 0.5 balanced)
- Conversion к ChannelTransferParams-compatible dicts
- Roundtrip integration с pure_transfer_engine
- Edge cases (single sample → std=0 floor, negative values clamp)
"""

from __future__ import annotations

import numpy as np
import pytest

from aurora_launch.engines.proxy_posterior_extractor import (
    ProxyChannelPrior,
    ProxyExtractionError,
    extract_proxy_priors,
    proxy_baseline_from_normalization,
    shrink_proxy_priors,
    to_channel_transfer_params,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_posterior(
    n_channels: int = 3, n_samples: int = 1000, seed: int = 42
) -> dict:
    """Synthetic posterior с known statistics для verification."""
    rng = np.random.default_rng(seed)
    # Channel-specific stats для verifiability
    beta_means = [0.2, 0.1, 0.15][:n_channels]
    beta_stds = [0.05, 0.02, 0.04][:n_channels]
    alpha_values = [2.0, 1.5, 1.8][:n_channels]
    gamma_values = [100.0, 50.0, 80.0][:n_channels]
    decay_values = [0.5, 0.2, 0.4][:n_channels]

    return {
        "media_betas": np.array(
            [
                rng.normal(loc=beta_means[i], scale=beta_stds[i], size=n_samples)
                for i in range(n_channels)
            ]
        ),
        "alphas": np.array(
            [
                rng.normal(loc=alpha_values[i], scale=0.1, size=n_samples)
                for i in range(n_channels)
            ]
        ),
        "gammas": np.array(
            [
                rng.normal(loc=gamma_values[i], scale=5.0, size=n_samples)
                for i in range(n_channels)
            ]
        ),
        "adstock_decay": np.array(
            [
                np.clip(
                    rng.normal(loc=decay_values[i], scale=0.05, size=n_samples),
                    0.0,
                    1.0,
                )
                for i in range(n_channels)
            ]
        ),
    }


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    def test_missing_required_key(self) -> None:
        posterior = _make_posterior()
        del posterior["adstock_decay"]
        with pytest.raises(ProxyExtractionError, match="missing required keys"):
            extract_proxy_priors(posterior, ["tv", "digital", "search"])

    def test_wrong_n_channels(self) -> None:
        posterior = _make_posterior(n_channels=3)
        with pytest.raises(ProxyExtractionError, match="≠ len"):
            extract_proxy_priors(posterior, ["tv", "digital"])  # 2, not 3

    def test_inconsistent_n_samples(self) -> None:
        posterior = _make_posterior()
        # Corrupt: different sample count в one key
        posterior["alphas"] = posterior["alphas"][:, :500]
        with pytest.raises(ProxyExtractionError, match="Inconsistent n_samples"):
            extract_proxy_priors(posterior, ["tv", "digital", "search"])

    def test_wrong_dimensions(self) -> None:
        posterior = _make_posterior()
        posterior["media_betas"] = posterior["media_betas"].flatten()
        with pytest.raises(ProxyExtractionError, match="must be 2-D"):
            extract_proxy_priors(posterior, ["tv", "digital", "search"])

    def test_empty_media_cols(self) -> None:
        with pytest.raises(ProxyExtractionError, match="non-empty"):
            extract_proxy_priors({}, [])

    def test_duplicate_media_cols(self) -> None:
        posterior = _make_posterior(n_channels=2)
        with pytest.raises(ProxyExtractionError, match="unique"):
            extract_proxy_priors(posterior, ["tv", "tv"])


# ---------------------------------------------------------------------------
# Extraction correctness
# ---------------------------------------------------------------------------


class TestExtraction:
    def test_mean_close_to_synthetic(self) -> None:
        posterior = _make_posterior(n_channels=3, n_samples=10000)
        priors = extract_proxy_priors(
            posterior, ["tv", "digital", "search"]
        )
        # Expected centers
        assert abs(priors["tv"].proxy_beta_mean - 0.2) < 0.01
        assert abs(priors["digital"].proxy_beta_mean - 0.1) < 0.01
        assert abs(priors["search"].proxy_beta_mean - 0.15) < 0.01

    def test_std_close_to_synthetic(self) -> None:
        posterior = _make_posterior(n_channels=3, n_samples=10000)
        priors = extract_proxy_priors(
            posterior, ["tv", "digital", "search"]
        )
        assert abs(priors["tv"].proxy_beta_std - 0.05) < 0.01
        assert abs(priors["digital"].proxy_beta_std - 0.02) < 0.01
        assert abs(priors["search"].proxy_beta_std - 0.04) < 0.01

    def test_decay_in_zero_one(self) -> None:
        posterior = _make_posterior()
        priors = extract_proxy_priors(
            posterior, ["tv", "digital", "search"]
        )
        for p in priors.values():
            assert 0.0 <= p.adstock_decay <= 1.0

    def test_hill_alpha_positive(self) -> None:
        posterior = _make_posterior()
        priors = extract_proxy_priors(
            posterior, ["tv", "digital", "search"]
        )
        for p in priors.values():
            assert p.hill_alpha > 0

    def test_n_samples_preserved(self) -> None:
        posterior = _make_posterior(n_samples=500)
        priors = extract_proxy_priors(
            posterior, ["tv", "digital", "search"]
        )
        for p in priors.values():
            assert p.n_samples == 500

    def test_sigma_floor_applied_for_single_sample(self) -> None:
        # Edge case: only 1 sample → std is 0 by default; floor kicks in
        rng = np.random.default_rng(0)
        posterior = {
            "media_betas": rng.normal(0.2, 0.0, size=(1, 1)),  # 1 ch, 1 sample
            "alphas": rng.normal(2.0, 0.0, size=(1, 1)),
            "gammas": rng.normal(100.0, 0.0, size=(1, 1)),
            "adstock_decay": rng.normal(0.5, 0.0, size=(1, 1)),
        }
        priors = extract_proxy_priors(posterior, ["tv"])
        assert priors["tv"].proxy_beta_std > 0  # floor kicks in

    def test_nan_in_media_betas_raises(self) -> None:
        """PI2-B2 audit fix: NaN в posterior detected early с explicit error."""
        posterior = _make_posterior(n_channels=2, n_samples=100)
        posterior["media_betas"][0, 50:] = float("nan")
        with pytest.raises(ProxyExtractionError, match="NaN found в media_betas"):
            extract_proxy_priors(posterior, ["tv", "digital"])

    def test_nan_in_alphas_raises(self) -> None:
        posterior = _make_posterior(n_channels=2, n_samples=100)
        posterior["alphas"][0, 50] = float("nan")
        with pytest.raises(ProxyExtractionError, match="NaN found в alphas"):
            extract_proxy_priors(posterior, ["tv", "digital"])

    def test_nan_in_decay_raises(self) -> None:
        posterior = _make_posterior(n_channels=2, n_samples=100)
        posterior["adstock_decay"][0, 99] = float("nan")
        with pytest.raises(ProxyExtractionError, match="NaN found в adstock_decay"):
            extract_proxy_priors(posterior, ["tv", "digital"])

    def test_hill_alpha_capped_at_20(self) -> None:
        """PI2-B1 propagated to extractor: alpha clamped к 20."""
        rng = np.random.default_rng(0)
        # Synthetic posterior с unrealistic alpha posterior (e.g., 100)
        posterior = {
            "media_betas": rng.normal(0.1, 0.01, size=(1, 100)),
            "alphas": np.full((1, 100), 100.0),  # extreme
            "gammas": rng.normal(50.0, 5.0, size=(1, 100)),
            "adstock_decay": np.clip(rng.normal(0.5, 0.05, size=(1, 100)), 0.0, 1.0),
        }
        priors = extract_proxy_priors(posterior, ["tv"])
        assert priors["tv"].hill_alpha <= 20.0

    def test_negative_beta_clamped_to_zero(self) -> None:
        rng = np.random.default_rng(0)
        # Synthetic posterior с slightly negative samples (numerical artefact)
        betas = rng.normal(0.1, 0.05, size=(1, 1000))
        # Force median negative
        betas[0] -= 0.2  # now mean ~ -0.1
        posterior = {
            "media_betas": betas,
            "alphas": rng.normal(2.0, 0.1, size=(1, 1000)),
            "gammas": rng.normal(100.0, 5.0, size=(1, 1000)),
            "adstock_decay": np.clip(
                rng.normal(0.5, 0.05, size=(1, 1000)), 0.0, 1.0
            ),
        }
        priors = extract_proxy_priors(posterior, ["tv"])
        assert priors["tv"].proxy_beta_mean >= 0.0  # clamped


# ---------------------------------------------------------------------------
# Shrinkage
# ---------------------------------------------------------------------------


class TestShrinkage:
    def test_shrinkage_zero_keeps_std(self) -> None:
        posterior = _make_posterior(n_samples=5000)
        priors = extract_proxy_priors(
            posterior, ["tv", "digital", "search"]
        )
        shrunk = shrink_proxy_priors(priors, shrinkage_factor=0.0)
        for ch in ["tv", "digital", "search"]:
            assert abs(shrunk[ch].proxy_beta_std - priors[ch].proxy_beta_std) < 1e-9

    def test_shrinkage_one_drives_to_floor(self) -> None:
        posterior = _make_posterior(n_samples=5000)
        priors = extract_proxy_priors(
            posterior, ["tv", "digital", "search"]
        )
        shrunk = shrink_proxy_priors(priors, shrinkage_factor=1.0)
        for ch in ["tv", "digital", "search"]:
            # Sigma collapsed к floor (1e-6)
            assert shrunk[ch].proxy_beta_std < 1e-3
            # But mean preserved
            assert shrunk[ch].proxy_beta_mean == priors[ch].proxy_beta_mean

    def test_shrinkage_half_halves_std(self) -> None:
        posterior = _make_posterior(n_samples=5000)
        priors = extract_proxy_priors(
            posterior, ["tv", "digital", "search"]
        )
        shrunk = shrink_proxy_priors(priors, shrinkage_factor=0.5)
        for ch in ["tv", "digital", "search"]:
            assert abs(shrunk[ch].proxy_beta_std - priors[ch].proxy_beta_std * 0.5) < 1e-9

    def test_invalid_shrinkage_rejected(self) -> None:
        posterior = _make_posterior()
        priors = extract_proxy_priors(
            posterior, ["tv", "digital", "search"]
        )
        with pytest.raises(ValueError, match="shrinkage_factor"):
            shrink_proxy_priors(priors, shrinkage_factor=1.5)
        with pytest.raises(ValueError, match="shrinkage_factor"):
            shrink_proxy_priors(priors, shrinkage_factor=-0.1)

    def test_shrinkage_immutable_input(self) -> None:
        """Frozen dataclass — shrinkage returns new dict, не mutates input."""
        posterior = _make_posterior()
        priors = extract_proxy_priors(
            posterior, ["tv", "digital", "search"]
        )
        original_stds = {k: v.proxy_beta_std for k, v in priors.items()}
        _shrunk = shrink_proxy_priors(priors, shrinkage_factor=0.8)
        # Originals unchanged
        for k, v in priors.items():
            assert v.proxy_beta_std == original_stds[k]


# ---------------------------------------------------------------------------
# Baseline extraction
# ---------------------------------------------------------------------------


class TestBaseline:
    def test_extract_baseline(self) -> None:
        normalization = {"y_mean": 12345.6, "y_std": 100.0}
        assert proxy_baseline_from_normalization(normalization) == 12345.6

    def test_missing_y_mean(self) -> None:
        with pytest.raises(ProxyExtractionError, match="y_mean"):
            proxy_baseline_from_normalization({"y_std": 100.0})

    def test_zero_y_mean_rejected(self) -> None:
        with pytest.raises(ProxyExtractionError, match="> 0"):
            proxy_baseline_from_normalization({"y_mean": 0.0})

    def test_negative_y_mean_rejected(self) -> None:
        with pytest.raises(ProxyExtractionError, match="> 0"):
            proxy_baseline_from_normalization({"y_mean": -5.0})


# ---------------------------------------------------------------------------
# Conversion to ChannelTransferParams
# ---------------------------------------------------------------------------


class TestConversion:
    def test_basic_conversion(self) -> None:
        posterior = _make_posterior()
        priors = extract_proxy_priors(
            posterior, ["tv", "digital", "search"]
        )
        dicts = to_channel_transfer_params(priors)
        assert len(dicts) == 3
        for d in dicts:
            assert "channel_id" in d
            assert "proxy_beta_mean" in d
            assert "proxy_beta_std" in d
            assert "adstock_decay" in d
            assert "hill_alpha" in d
            assert "hill_half_saturation" in d
            # Defaults applied
            assert d["similarity_factor"] == 0.85
            assert d["similarity_inflation"] == 0.15

    def test_custom_similarity_per_channel(self) -> None:
        posterior = _make_posterior()
        priors = extract_proxy_priors(
            posterior, ["tv", "digital", "search"]
        )
        dicts = to_channel_transfer_params(
            priors,
            similarity_factors={"tv": 0.9, "digital": 0.7},
            similarity_inflations={"tv": 0.10, "digital": 0.20},
        )
        tv = next(d for d in dicts if d["channel_id"] == "tv")
        digital = next(d for d in dicts if d["channel_id"] == "digital")
        search = next(d for d in dicts if d["channel_id"] == "search")
        assert tv["similarity_factor"] == 0.9
        assert tv["similarity_inflation"] == 0.10
        assert digital["similarity_factor"] == 0.7
        # No override for search → default
        assert search["similarity_factor"] == 0.85


# ---------------------------------------------------------------------------
# Integration с pure_transfer_engine
# ---------------------------------------------------------------------------


class TestIntegrationWithPureTransfer:
    def test_extracted_priors_usable_with_pure_transfer(self) -> None:
        """End-to-end: extract priors → convert → feed pure_transfer_engine."""
        from aurora_launch.engines.pure_transfer_engine import (
            ChannelTransferParams,
            RecipientAnchors,
            TransferInputs,
            forecast_pure_transfer,
        )

        posterior = _make_posterior(n_channels=2, n_samples=5000)
        priors = extract_proxy_priors(posterior, ["tv", "digital"])
        shrunk = shrink_proxy_priors(priors, shrinkage_factor=0.5)
        channel_dicts = to_channel_transfer_params(shrunk)
        channels = [ChannelTransferParams.model_validate(d) for d in channel_dicts]

        anchors = RecipientAnchors(
            market_size=10_000_000.0,
            market_size_cv=0.10,
            planned_share_trajectory=[0.05] * 6,
            distribution_trajectory=[0.7] * 6,
            pricing_index=1.0,
            elasticity=0.5,
            seasonality=[1.0] * 6,
        )

        inputs = TransferInputs(
            granularity="monthly",
            horizon_periods=6,
            channels=channels,
            anchors=anchors,
            spend_plan={"tv": [200.0] * 6, "digital": [80.0] * 6},
            proxy_baseline_mean=500_000.0,
            coverage_target=0.95,
        )
        result = forecast_pure_transfer(inputs)
        # Sanity: forecast generated, all bounds OK
        assert len(result.points) == 6
        for p in result.points:
            assert p.ci_lower <= p.point_forecast <= p.ci_upper
            assert p.point_forecast >= p.baseline
