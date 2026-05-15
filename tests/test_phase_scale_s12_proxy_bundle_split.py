"""Phase Scale S-12 — ProxyBundle god-dataclass decomposition tests.

Coverage:
- New structured constructor (metadata + posterior + config_obj) works
- Backward-compat flat constructor issues DeprecationWarning
- Backward-compat __getattr__ field access issues DeprecationWarning per field
- Frozen immutability: cannot mutate any sub-object or ProxyBundle
- ProxyMetadata exact fields: origin_brand_id, proxy_app_version, recorded_at,
  n_proxy_observations, brand_category
- ProxyPosteriorPayload exact fields: posterior_samples, normalization, media_cols
- ProxyConfig exact fields: config
- Composition: bundle.metadata.brand_category accessible
- Orchestrator works with new-API bundle (end-to-end smoke)
- Orchestrator works with legacy-API bundle (backward compat smoke)
"""

from __future__ import annotations

import warnings
from dataclasses import fields

import numpy as np
import pytest

from aurora_launch.engines.launch_orchestrator import (
    LaunchOrchestrator,
    ProxyBundle,
    ProxyConfig,
    ProxyMetadata,
    ProxyPosteriorPayload,
)
from aurora_launch.engines.pure_transfer_engine import RecipientAnchors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_posterior_samples(n_channels: int = 2, n_samples: int = 200) -> dict:
    rng = np.random.default_rng(42)
    return {
        "media_betas": np.array(
            [rng.normal(loc=0.2, scale=0.05, size=n_samples) for _ in range(n_channels)]
        ),
        "alphas": np.array(
            [rng.normal(loc=2.0, scale=0.1, size=n_samples) for _ in range(n_channels)]
        ),
        "gammas": np.array(
            [rng.normal(loc=100.0, scale=5.0, size=n_samples) for _ in range(n_channels)]
        ),
        "adstock_decay": np.array(
            [np.clip(rng.normal(loc=0.5, scale=0.05, size=n_samples), 0.0, 1.0)
             for _ in range(n_channels)]
        ),
    }


def _make_new_bundle(
    media_cols: list[str] | None = None,
    n_obs: int = 104,
) -> ProxyBundle:
    """Construct a ProxyBundle using the new structured S-12 API."""
    cols = media_cols or ["tv", "digital"]
    return ProxyBundle(
        metadata=ProxyMetadata(
            origin_brand_id="brand-42",
            proxy_app_version="0.1.0",
            recorded_at="2026-05-15T10:00:00Z",
            n_proxy_observations=n_obs,
            brand_category="pharma_otc",
        ),
        posterior=ProxyPosteriorPayload(
            posterior_samples=_make_posterior_samples(len(cols)),
            normalization={"y_mean": 500_000.0, "y_std": 50_000.0},
            media_cols=cols,
        ),
        config_obj=ProxyConfig(config={"mode": "sales", "granularity": "monthly"}),
    )


def _make_legacy_bundle(
    media_cols: list[str] | None = None,
    n_obs: int = 104,
) -> ProxyBundle:
    """Construct a ProxyBundle using the deprecated legacy flat API."""
    cols = media_cols or ["tv", "digital"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return ProxyBundle(
            posterior_samples=_make_posterior_samples(len(cols)),
            media_cols=cols,
            normalization={"y_mean": 500_000.0, "y_std": 50_000.0},
            config={"mode": "sales"},
            proxy_brand_id="brand-42",
            n_proxy_observations=n_obs,
        )


def _make_anchors(horizon: int = 12) -> RecipientAnchors:
    return RecipientAnchors(
        market_size=10_000_000.0,
        market_size_cv=0.10,
        planned_share_trajectory=[0.05] * horizon,
        distribution_trajectory=[0.8] * horizon,
        pricing_index=1.0,
        elasticity=0.0,
    )


# ---------------------------------------------------------------------------
# S-12-1: New constructor works with 3 sub-objects
# ---------------------------------------------------------------------------


class TestNewConstructor:
    def test_new_bundle_has_metadata_sub_object(self) -> None:
        bundle = _make_new_bundle()
        assert bundle.metadata is not None
        assert isinstance(bundle.metadata, ProxyMetadata)

    def test_new_bundle_has_posterior_sub_object(self) -> None:
        bundle = _make_new_bundle()
        assert bundle.posterior is not None
        assert isinstance(bundle.posterior, ProxyPosteriorPayload)

    def test_new_bundle_has_config_obj_sub_object(self) -> None:
        bundle = _make_new_bundle()
        assert bundle.config_obj is not None
        assert isinstance(bundle.config_obj, ProxyConfig)

    def test_new_bundle_no_deprecation_warning(self) -> None:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _make_new_bundle()
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) == 0, (
            f"Expected 0 DeprecationWarnings from new constructor, got: {deprecation_warnings}"
        )

    def test_new_bundle_field_values_via_sub_objects(self) -> None:
        bundle = _make_new_bundle()
        assert bundle.metadata.origin_brand_id == "brand-42"
        assert bundle.metadata.n_proxy_observations == 104
        assert bundle.metadata.brand_category == "pharma_otc"
        assert bundle.posterior.media_cols == ["tv", "digital"]
        assert "y_mean" in bundle.posterior.normalization
        assert bundle.config_obj.config["mode"] == "sales"


# ---------------------------------------------------------------------------
# S-12-2: Backward-compat flat constructor issues DeprecationWarning
# ---------------------------------------------------------------------------


class TestLegacyConstructor:
    def test_legacy_constructor_issues_deprecation_warning(self) -> None:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            ProxyBundle(
                posterior_samples=_make_posterior_samples(),
                media_cols=["tv", "digital"],
                normalization={"y_mean": 500_000.0, "y_std": 50_000.0},
            )
            dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(dep_warnings) >= 1
        assert "deprecated" in str(dep_warnings[0].message).lower()
        assert "v0.2.0" in str(dep_warnings[0].message)

    def test_legacy_flat_fields_accessible_with_warning(self) -> None:
        bundle = _make_legacy_bundle()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            ps = bundle.posterior_samples
            mc = bundle.media_cols
            nm = bundle.normalization
            cfg = bundle.config
            bid = bundle.proxy_brand_id
            nobs = bundle.n_proxy_observations
            dep = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(dep) == 6, f"Expected 6 DeprecationWarnings (one per field), got {len(dep)}"
        assert ps is not None
        assert mc == ["tv", "digital"]
        assert "y_mean" in nm
        assert cfg["mode"] == "sales"
        assert bid == "brand-42"
        assert nobs == 104


# ---------------------------------------------------------------------------
# S-12-3: Frozen immutability
# ---------------------------------------------------------------------------


class TestFrozenImmutability:
    def test_proxy_bundle_cannot_be_mutated(self) -> None:
        bundle = _make_new_bundle()
        with pytest.raises(AttributeError):
            bundle.metadata = None  # type: ignore[misc]

    def test_proxy_metadata_frozen(self) -> None:
        meta = ProxyMetadata(origin_brand_id="x", n_proxy_observations=10)
        with pytest.raises((AttributeError, TypeError)):
            meta.origin_brand_id = "y"  # type: ignore[misc]

    def test_proxy_posterior_payload_frozen(self) -> None:
        payload = ProxyPosteriorPayload(
            posterior_samples={},
            normalization={},
            media_cols=[],
        )
        with pytest.raises((AttributeError, TypeError)):
            payload.media_cols = ["new"]  # type: ignore[misc]

    def test_proxy_config_frozen(self) -> None:
        cfg = ProxyConfig(config={"a": 1})
        with pytest.raises((AttributeError, TypeError)):
            cfg.config = {}  # type: ignore[misc]


# ---------------------------------------------------------------------------
# S-12-4: ProxyMetadata exact fields
# ---------------------------------------------------------------------------


class TestProxyMetadataFields:
    EXPECTED_FIELDS = {
        "origin_brand_id",
        "proxy_app_version",
        "recorded_at",
        "n_proxy_observations",
        "brand_category",
    }

    def test_proxy_metadata_has_exact_expected_fields(self) -> None:
        actual = {f.name for f in fields(ProxyMetadata)}
        assert actual == self.EXPECTED_FIELDS, (
            f"ProxyMetadata field mismatch.\n"
            f"Expected: {sorted(self.EXPECTED_FIELDS)}\n"
            f"Actual:   {sorted(actual)}"
        )

    def test_proxy_metadata_defaults(self) -> None:
        meta = ProxyMetadata()
        assert meta.origin_brand_id is None
        assert meta.proxy_app_version is None
        assert meta.recorded_at is None
        assert meta.n_proxy_observations == 0
        assert meta.brand_category is None

    def test_proxy_metadata_all_fields_populated(self) -> None:
        meta = ProxyMetadata(
            origin_brand_id="brand-99",
            proxy_app_version="0.1.5",
            recorded_at="2026-05-01T00:00:00Z",
            n_proxy_observations=52,
            brand_category="fmcg",
        )
        assert meta.origin_brand_id == "brand-99"
        assert meta.proxy_app_version == "0.1.5"
        assert meta.recorded_at == "2026-05-01T00:00:00Z"
        assert meta.n_proxy_observations == 52
        assert meta.brand_category == "fmcg"


# ---------------------------------------------------------------------------
# S-12-5: Composition: bundle.metadata.brand_category accessible
# ---------------------------------------------------------------------------


class TestComposition:
    def test_bundle_metadata_brand_category_accessible(self) -> None:
        bundle = _make_new_bundle()
        assert bundle.metadata is not None
        assert bundle.metadata.brand_category == "pharma_otc"

    def test_bundle_posterior_media_cols_accessible(self) -> None:
        bundle = _make_new_bundle(media_cols=["tv", "digital", "ooh"])
        assert bundle.posterior is not None
        assert bundle.posterior.media_cols == ["tv", "digital", "ooh"]

    def test_bundle_posterior_normalization_accessible(self) -> None:
        bundle = _make_new_bundle()
        assert bundle.posterior.normalization["y_mean"] == 500_000.0

    def test_bundle_config_obj_config_accessible(self) -> None:
        bundle = _make_new_bundle()
        assert bundle.config_obj is not None
        assert bundle.config_obj.config["granularity"] == "monthly"


# ---------------------------------------------------------------------------
# S-12-6: Orchestrator end-to-end smoke (new API)
# ---------------------------------------------------------------------------


class TestOrchestratorWithNewBundle:
    def test_forecast_with_new_api_bundle_completes(self) -> None:
        bundle = _make_new_bundle()
        anchors = _make_anchors(horizon=12)
        spend_plan = {col: [50_000.0] * 12 for col in bundle.posterior.media_cols}

        orchestrator = LaunchOrchestrator()
        result = orchestrator.forecast_recipient(
            proxy=bundle,
            anchors=anchors,
            spend_plan=spend_plan,
            horizon_periods=12,
        )
        assert result.forecast is not None
        assert len(result.forecast.points) == 12
        assert result.forecast.points[0].point_forecast > 0

    def test_forecast_no_deprecation_warnings_with_new_bundle(self) -> None:
        bundle = _make_new_bundle()
        anchors = _make_anchors(horizon=6)
        spend_plan = {col: [30_000.0] * 6 for col in bundle.posterior.media_cols}
        orchestrator = LaunchOrchestrator()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            orchestrator.forecast_recipient(
                proxy=bundle,
                anchors=anchors,
                spend_plan=spend_plan,
                horizon_periods=6,
            )
            dep = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(dep) == 0, (
            f"Orchestrator should not emit DeprecationWarnings with new-API bundle, "
            f"got: {[str(x.message) for x in dep]}"
        )


# ---------------------------------------------------------------------------
# S-12-7: Orchestrator end-to-end smoke (legacy API, backward compat)
# ---------------------------------------------------------------------------


class TestOrchestratorWithLegacyBundle:
    def test_forecast_with_legacy_bundle_completes(self) -> None:
        bundle = _make_legacy_bundle()
        anchors = _make_anchors(horizon=12)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            media_cols = bundle.media_cols

        spend_plan = {col: [50_000.0] * 12 for col in media_cols}

        orchestrator = LaunchOrchestrator()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = orchestrator.forecast_recipient(
                proxy=bundle,
                anchors=anchors,
                spend_plan=spend_plan,
                horizon_periods=12,
            )
        assert result.forecast is not None
        assert len(result.forecast.points) == 12
