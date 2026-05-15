"""Phase Σ.0.4 — Sample bundles tests.

Coverage:
- XLSX adapter parsing (Russian month, currency strings, channel detection)
- Synthetic posterior derivation (shape correctness, schema compat с bayesian_engine)
- End-to-end: XLSX → synthetic posterior → orchestrator forecast smoke
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from aurora_launch.sample_bundles.econometrica_xlsx_adapter import (
    EconometricaDataset,
    EconometricaXLSXError,
    _coerce_numeric,
    _normalise_header,
    _parse_russian_month,
    load_econometrica_xlsx,
)
from aurora_launch.sample_bundles.synthetic_posterior import (
    SyntheticPosteriorError,
    derive_synthetic_posterior,
)


# Existing pilot test data (provided by Антон 2026-05-14)
KAGOTSEL_XLSX = Path(
    "C:/Users/ackol/Desktop/Аврора - материалы для обучения и тестирования"
    "/Эконометрика - тестовые файлы/XLSX"
    "/Кагоцел РФ+_данные для эконометрики + наши данные 29.08.xlsx"
)
VENARUS_XLSX = Path(
    "C:/Users/ackol/Desktop/Аврора - материалы для обучения и тестирования"
    "/Эконометрика - тестовые файлы/XLSX"
    "/Венарус_данные для эконометрики для модели + наши данные.xlsx"
)
MMX_XLSX = Path(
    "C:/Users/ackol/Desktop/Аврора - материалы для обучения и тестирования"
    "/Эконометрика - тестовые файлы/XLSX/MMX 2021-2025 исходник.xlsx"
)


# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------


class TestParseRussianMonth:
    def test_basic_january(self) -> None:
        assert _parse_russian_month("январь 2023") == "2023-01-01"

    def test_december(self) -> None:
        assert _parse_russian_month("декабрь 2024") == "2024-12-01"

    def test_lowercase_irregular_spaces(self) -> None:
        assert _parse_russian_month("  Март 2025  ") == "2025-03-01"

    def test_invalid_returns_none(self) -> None:
        assert _parse_russian_month("not a date") is None
        assert _parse_russian_month("13 января 2023") is None
        assert _parse_russian_month("") is None


class TestCoerceNumeric:
    def test_simple_int(self) -> None:
        assert _coerce_numeric(42) == 42.0

    def test_float(self) -> None:
        assert _coerce_numeric(5.19) == 5.19

    def test_currency_string(self) -> None:
        assert _coerce_numeric(" 3,836,962 ₽ ") == 3836962.0

    def test_separator_only(self) -> None:
        assert _coerce_numeric("-") is None
        assert _coerce_numeric("") is None

    def test_none(self) -> None:
        assert _coerce_numeric(None) is None

    def test_nan(self) -> None:
        assert _coerce_numeric(float("nan")) is None


class TestNormaliseHeader:
    def test_strip_newlines(self) -> None:
        assert _normalise_header("OLV Бюджет\nдо НДС") == "olv бюджет до ндс"


# ---------------------------------------------------------------------------
# Real XLSX integration (skip если файлы отсутствуют на CI)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not KAGOTSEL_XLSX.exists(), reason="Pilot test data not present (dev only)"
)
class TestKagotselDataset:
    def test_loads_dataset(self) -> None:
        ds = load_econometrica_xlsx(KAGOTSEL_XLSX)
        assert isinstance(ds, EconometricaDataset)
        assert ds.brand_id == "Кагоцел РФ+Герпес"
        assert ds.granularity == "monthly"
        assert ds.n_periods >= 24, f"Expected ≥24 monthly observations, got {ds.n_periods}"

    def test_channels_detected(self) -> None:
        ds = load_econometrica_xlsx(KAGOTSEL_XLSX)
        # Per actual data file: OLV, Banners, Social, Performance, Статьи (Retail Media + Спецпроекты пустые)
        assert "olv" in ds.channel_ids
        assert "banners" in ds.channel_ids
        assert "social" in ds.channel_ids
        assert "performance" in ds.channel_ids
        # Statьи channel также должен быть detected
        assert "articles" in ds.channel_ids or "specials" in ds.channel_ids

    def test_dates_iso_format(self) -> None:
        ds = load_econometrica_xlsx(KAGOTSEL_XLSX)
        # Каждая дата соответствует pattern YYYY-MM-01
        for d in ds.dates_iso:
            assert len(d) == 10
            assert d[4] == "-" and d[7] == "-"
            assert d.endswith("-01")

    def test_dates_monotonic(self) -> None:
        ds = load_econometrica_xlsx(KAGOTSEL_XLSX)
        # ISO format support lexicographic comparison
        for i in range(1, len(ds.dates_iso)):
            assert ds.dates_iso[i] >= ds.dates_iso[i - 1]

    def test_sales_positive(self) -> None:
        ds = load_econometrica_xlsx(KAGOTSEL_XLSX)
        # All-zero sales is a corruption — должно быть mostly positive
        positives = sum(1 for s in ds.sales_brand if s > 0)
        assert positives >= len(ds.sales_brand) * 0.8


@pytest.mark.skipif(
    not VENARUS_XLSX.exists(), reason="Pilot test data not present (dev only)"
)
class TestVenarusDataset:
    def test_loads_dataset(self) -> None:
        ds = load_econometrica_xlsx(VENARUS_XLSX)
        assert ds.brand_id == "Венарус (таб.)+Венапрокт (комп)"
        assert ds.n_periods >= 24


@pytest.mark.skipif(
    not MMX_XLSX.exists(), reason="Pilot test data not present (dev only)"
)
class TestMMXDataset:
    def test_afalaza_loads(self) -> None:
        ds = load_econometrica_xlsx(MMX_XLSX, sheet_name="Афалаза")
        assert ds.brand_id == "Афалаза"
        # MMX coverage до 43 месяцев per Антон's data inventory
        assert ds.n_periods >= 36


# ---------------------------------------------------------------------------
# XLSX adapter error paths
# ---------------------------------------------------------------------------


class TestXLSXErrors:
    def test_missing_file(self) -> None:
        with pytest.raises(EconometricaXLSXError, match="not found"):
            load_econometrica_xlsx(Path("/nonexistent/file.xlsx"))


# ---------------------------------------------------------------------------
# Synthetic posterior derivation
# ---------------------------------------------------------------------------


def _make_dataset_synthetic(
    n_periods: int = 36, n_channels: int = 3, seed: int = 0
) -> EconometricaDataset:
    """Synthetic dataset для unit tests (no XLSX dependency)."""
    rng = np.random.default_rng(seed)
    channel_ids = ["tv", "digital", "search"][:n_channels]
    spend_by_channel: dict[str, list[float]] = {}
    for i, ch in enumerate(channel_ids):
        base_spend = (i + 1) * 1_000_000.0
        spend_by_channel[ch] = list(
            rng.normal(loc=base_spend, scale=base_spend * 0.2, size=n_periods).clip(
                min=0
            )
        )
    # Build sales as linear combo
    sales_brand = []
    for t in range(n_periods):
        s = 100_000_000.0
        for i, ch in enumerate(channel_ids):
            s += 0.1 * (i + 1) * spend_by_channel[ch][t]
        sales_brand.append(s + rng.normal(scale=5_000_000.0))
    return EconometricaDataset(
        brand_id="synthetic",
        granularity="monthly",
        n_periods=n_periods,
        dates_iso=[f"2023-{(m % 12) + 1:02d}-01" for m in range(n_periods)],
        channel_ids=channel_ids,
        spend_by_channel=spend_by_channel,
        sales_brand=sales_brand,
        sales_competitors=[s * 5 for s in sales_brand],
        raw_headers=[],
    )


class TestSyntheticPosterior:
    def test_basic_derivation(self) -> None:
        ds = _make_dataset_synthetic(n_periods=36, n_channels=3)
        result = derive_synthetic_posterior(ds, n_samples=500)
        assert "media_betas" in result.posterior_samples
        assert "alphas" in result.posterior_samples
        assert "gammas" in result.posterior_samples
        assert "adstock_decay" in result.posterior_samples

    def test_posterior_shape(self) -> None:
        ds = _make_dataset_synthetic(n_periods=36, n_channels=3)
        result = derive_synthetic_posterior(ds, n_samples=500)
        for key in ["media_betas", "alphas", "gammas", "adstock_decay"]:
            assert result.posterior_samples[key].shape == (3, 500), (
                f"Wrong shape for {key}: {result.posterior_samples[key].shape}"
            )

    def test_too_short_dataset_rejected(self) -> None:
        ds = _make_dataset_synthetic(n_periods=4, n_channels=2)
        with pytest.raises(SyntheticPosteriorError, match="≥6"):
            derive_synthetic_posterior(ds)

    def test_normalization_y_mean_present(self) -> None:
        ds = _make_dataset_synthetic()
        result = derive_synthetic_posterior(ds, n_samples=200)
        assert result.normalization["y_mean"] > 0
        assert result.normalization["y_std"] > 0

    def test_config_contains_media_columns(self) -> None:
        ds = _make_dataset_synthetic(n_channels=2)
        result = derive_synthetic_posterior(ds, n_samples=200)
        assert result.config["media_columns"] == ["tv", "digital"]
        assert result.config["granularity"] == "monthly"

    def test_media_cols_match_channels(self) -> None:
        ds = _make_dataset_synthetic(n_channels=3)
        result = derive_synthetic_posterior(ds, n_samples=200)
        assert result.media_cols == ["tv", "digital", "search"]
        assert result.n_proxy_observations == 36

    def test_betas_non_negative(self) -> None:
        ds = _make_dataset_synthetic()
        result = derive_synthetic_posterior(ds, n_samples=500)
        assert (result.posterior_samples["media_betas"] >= 0).all()

    def test_adstock_in_zero_one(self) -> None:
        ds = _make_dataset_synthetic()
        result = derive_synthetic_posterior(ds, n_samples=500)
        decays = result.posterior_samples["adstock_decay"]
        assert (decays >= 0).all()
        assert (decays <= 1).all()


# ---------------------------------------------------------------------------
# End-to-end integration
# ---------------------------------------------------------------------------


class TestEndToEndIntegration:
    def test_synthetic_dataset_feeds_orchestrator(self) -> None:
        """Synthetic dataset → posterior → ProxyBundle → orchestrator forecast."""
        from aurora_launch.engines.launch_orchestrator import (
            LaunchOrchestrator,
            ProxyBundle,
    make_proxy_bundle,
        )
        from aurora_launch.engines.pure_transfer_engine import RecipientAnchors

        ds = _make_dataset_synthetic(n_periods=36, n_channels=2)
        synth = derive_synthetic_posterior(ds, n_samples=1000)

        bundle = make_proxy_bundle(
            posterior_samples=synth.posterior_samples,
            media_cols=synth.media_cols,
            normalization=synth.normalization,
            config=synth.config,
            proxy_brand_id=ds.brand_id,
            n_proxy_observations=ds.n_periods,
        )

        anchors = RecipientAnchors(
            market_size=10_000_000.0,
            market_size_cv=0.10,
            planned_share_trajectory=[0.05] * 6,
            distribution_trajectory=[0.70] * 6,
            pricing_index=1.0,
            elasticity=0.5,
            seasonality=[1.0] * 6,
        )

        orch = LaunchOrchestrator()
        # Spend plan is "normalised" 2.0 to match synthetic posterior gamma anchor
        result = orch.forecast_recipient(
            proxy=bundle,
            anchors=anchors,
            spend_plan={
                ch: [synth.normalization["media_means"][ch]] * 6
                for ch in synth.media_cols
            },
            horizon_periods=6,
            granularity="monthly",
            n_recipient=0,
        )
        # End-to-end smoke: forecast generated, CI ordering preserved
        assert result.forecast is not None
        assert len(result.forecast.points) == 6
        for p in result.forecast.points:
            assert p.ci_lower <= p.point_forecast <= p.ci_upper
