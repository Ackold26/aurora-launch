"""Phase Magic M-03: forecast explainer (local engine) tests."""

from __future__ import annotations

import pytest

from aurora_launch.engines.forecast_explainer import (
    Explanation,
    ExplainerInputs,
    _format_number,
    explain_local,
)


def _make_inputs(**overrides) -> ExplainerInputs:
    """Defaults для Pure Transfer happy path."""
    defaults = dict(
        point_forecast_mean=1_240_000.0,
        ci_lower_mean=1_100_000.0,
        ci_upper_mean=1_380_000.0,
        horizon_periods=12,
        granularity="monthly",
        engine_mode="pure_transfer",
        methodology_signature="pure_transfer_v1",
        n_recipient=0,
        currency="RUB",
        locale="ru",
    )
    defaults.update(overrides)
    return ExplainerInputs(**defaults)


class TestFormatNumber:
    def test_millions_with_currency(self) -> None:
        assert "1.2 млн" in _format_number(1_240_000.0, "RUB", "ru")
        assert "₽" in _format_number(1_240_000.0, "RUB", "ru")

    def test_thousands_no_decimal(self) -> None:
        result = _format_number(45_000.0, "RUB", "ru")
        assert "45" in result and "тыс" in result

    def test_units_no_currency_symbol(self) -> None:
        result = _format_number(1_240_000.0, "units", "ru")
        assert "₽" not in result and "$" not in result
        assert "1.2 млн" in result

    def test_nan_returns_dash(self) -> None:
        assert _format_number(float("nan"), "RUB", "ru") == "—"

    def test_negative_value(self) -> None:
        result = _format_number(-1_240_000.0, "RUB", "ru")
        assert result.startswith("−")  # Unicode minus

    def test_en_locale_format(self) -> None:
        result = _format_number(1_240_000.0, "USD", "en")
        assert "$" in result and "1.2M" in result


class TestExplainLocal:
    def test_returns_three_paragraphs(self) -> None:
        result = explain_local(_make_inputs())
        assert isinstance(result, Explanation)
        assert len(result.what) > 50
        assert len(result.why) > 50
        assert len(result.risks) > 20

    def test_local_engine_marker(self) -> None:
        result = explain_local(_make_inputs())
        assert result.engine_used == "local"

    def test_what_includes_forecast_value(self) -> None:
        result = explain_local(_make_inputs())
        # Point mean 1,240,000 → 1.2 млн in RU compact format
        assert "1.2" in result.what or "1240" in result.what

    def test_what_includes_ci_range(self) -> None:
        result = explain_local(_make_inputs())
        # Lower 1.1, Upper 1.38
        assert "1.1" in result.what
        assert "1.38" in result.what or "1.4" in result.what

    def test_why_pure_transfer_mentions_proxy(self) -> None:
        result = explain_local(_make_inputs(engine_mode="pure_transfer"))
        assert "proxy" in result.why.lower() or "прокси" in result.why.lower()

    def test_why_ols_mentions_observation_count(self) -> None:
        result = explain_local(
            _make_inputs(
                engine_mode="ols_with_proxy_priors",
                methodology_signature="ols_with_proxy_priors_v1",
                n_recipient=8,
            )
        )
        assert "8" in result.why

    def test_why_bayesian_mentions_distribution(self) -> None:
        result = explain_local(
            _make_inputs(
                engine_mode="bayesian_with_proxy_priors",
                methodology_signature="bayesian_with_proxy_priors_v1",
                n_recipient=10,
            )
        )
        assert "Bayesian" in result.why or "распределение" in result.why

    def test_risks_warns_when_ci_wide(self) -> None:
        result = explain_local(
            _make_inputs(
                point_forecast_mean=1_000_000.0,
                ci_lower_mean=300_000.0,
                ci_upper_mean=1_700_000.0,  # 140% ratio
            )
        )
        assert "интервал" in result.risks.lower() or "неопределённост" in result.risks.lower()

    def test_risks_mentions_fallback_when_signature_includes_it(self) -> None:
        result = explain_local(
            _make_inputs(
                engine_mode="ols_with_proxy_priors",
                methodology_signature="ols_with_proxy_priors_fallback_v1",
            )
        )
        assert "fallback" in result.risks.lower() or "упрощ" in result.risks.lower()

    def test_risks_recommends_recheck_when_no_observations(self) -> None:
        result = explain_local(_make_inputs(n_recipient=0))
        assert "4" in result.risks or "перепровер" in result.risks.lower()

    def test_risks_narrow_ci_emits_confidence_note(self) -> None:
        """Narrow CI (12% ratio) → "узкий" confidence note (not warning)."""
        result = explain_local(
            _make_inputs(
                point_forecast_mean=1_000_000.0,
                ci_lower_mean=940_000.0,  # 12% ratio
                ci_upper_mean=1_060_000.0,
                engine_mode="ols_with_proxy_priors",
                methodology_signature="ols_with_proxy_priors_v1",  # NO fallback
                n_recipient=12,
            )
        )
        assert "узкий" in result.risks.lower() or "уверен" in result.risks.lower()

    def test_risks_no_warnings_fallback_default(self) -> None:
        """Mid CI ratio + observed + no fallback → 'стабилен' default."""
        result = explain_local(
            _make_inputs(
                point_forecast_mean=1_000_000.0,
                ci_lower_mean=850_000.0,  # 30% ratio — между 15% и 40%
                ci_upper_mean=1_150_000.0,
                engine_mode="ols_with_proxy_priors",
                methodology_signature="ols_with_proxy_priors_v1",
                n_recipient=20,
            )
        )
        assert "стабилен" in result.risks.lower() or "не выявлено" in result.risks.lower()


class TestConfidenceTier:
    def test_low_when_fallback(self) -> None:
        result = explain_local(
            _make_inputs(
                methodology_signature="ols_with_proxy_priors_fallback_v1",
            )
        )
        assert result.confidence == "low"

    def test_high_when_narrow_ci_with_observations(self) -> None:
        result = explain_local(
            _make_inputs(
                point_forecast_mean=1_000_000.0,
                ci_lower_mean=960_000.0,
                ci_upper_mean=1_040_000.0,  # 8% ratio
                methodology_signature="ols_with_proxy_priors_v1",
                n_recipient=20,
            )
        )
        assert result.confidence == "high"

    def test_low_when_wide_ci(self) -> None:
        result = explain_local(
            _make_inputs(
                point_forecast_mean=1_000_000.0,
                ci_lower_mean=200_000.0,
                ci_upper_mean=1_800_000.0,  # 160% ratio
            )
        )
        assert result.confidence == "low"


class TestEnglishLocale:
    def test_returns_english_paragraphs(self) -> None:
        result = explain_local(_make_inputs(locale="en"))
        # Some English keyword in what/why/risks
        assert "Forecast" in result.what
        assert any(kw in result.why for kw in ["model", "Forecast", "brand", "proxy"])

    def test_currency_symbol_prefix_in_en(self) -> None:
        result = explain_local(_make_inputs(locale="en", currency="USD"))
        assert "$" in result.what


class TestIpcHandler:
    def test_ipc_returns_explanation_shape(self) -> None:
        from aurora_launch.sidecar.methods import dispatch

        result = dispatch(
            "explain_forecast",
            {
                "point_forecast_mean": 1_240_000.0,
                "ci_lower_mean": 1_100_000.0,
                "ci_upper_mean": 1_380_000.0,
                "horizon_periods": 12,
                "granularity": "monthly",
                "engine_mode": "pure_transfer",
                "methodology_signature": "pure_transfer_v1",
                "n_recipient": 0,
                "currency": "RUB",
                "locale": "ru",
            },
        )
        for key in ("what", "why", "risks", "engine_used", "confidence"):
            assert key in result
        assert result["engine_used"] == "local"
        assert result["confidence"] in ("high", "medium", "low")
