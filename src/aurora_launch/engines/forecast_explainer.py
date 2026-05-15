"""Phase Magic M-03: forecast explainer (local-first).

Generates 3-paragraph CFO-ready narrative explaining forecast result в
человеческом языке. Customer pain: "Aurora даёт прогноз 1 240 000 — но
ЧТО это значит? На чём основано? Какие риски?"

Architecture:
- **Local engine** (this module): template-based, always works, no network,
  no external API. Privacy: input never leaves machine. Suitable для
  152-ФЗ compliant pharma deployments.
- **Cloud engine** (future M-03 Phase 2.5): Claude API wrapper, opt-in
  с explicit consent flow. Higher quality narrative, brand-aware phrasing.
  External API call → 152-ФЗ assessment required per customer.

This module ships the local engine. Cloud engine deferred until Anthropic
API key acquisition decision + privacy consent UX (separate task).

Per audit SP-05: AI explanations send data к external API by default —
mitigated by opt-in privacy toggle. Local engine = privacy mode default.

Per master-plan §④ M-03:
    - 3-paragraph format: what / why / risks
    - Russian primary, English secondary
    - CFO-ready: business-vocabulary, no statistical jargon
    - Numbers from forecast (not invented)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

_log = logging.getLogger(__name__)

Engine = Literal["local", "cloud"]
Locale = Literal["ru", "en"]


@dataclass(frozen=True)
class ExplainerInputs:
    """Forecast data required к build explanation."""

    point_forecast_mean: float
    ci_lower_mean: float
    ci_upper_mean: float
    horizon_periods: int
    granularity: str  # "monthly" | "weekly"
    engine_mode: str  # "pure_transfer" | "transfer_with_bias_check" | ...
    methodology_signature: str
    n_recipient: int  # observed periods (0 для pre-launch)
    trust_score: int | None = None  # 0-100, optional
    warnings: tuple[str, ...] = ()
    currency: str = "RUB"
    locale: Locale = "ru"


@dataclass(frozen=True)
class Explanation:
    """3-paragraph CFO-ready forecast narrative."""

    what: str  # Para 1: what the forecast says
    why: str  # Para 2: what it's based on
    risks: str  # Para 3: what risks to watch
    engine_used: Engine
    confidence: Literal["high", "medium", "low"]


def _format_number(value: float, currency: str, locale: Locale) -> str:
    """Compact currency-aware formatting. RUB/USD/EUR/units."""
    if not isinstance(value, (int, float)) or value != value:  # NaN check
        return "—"
    sign = "" if value >= 0 else "−"
    v = abs(value)
    if v >= 1_000_000:
        formatted = f"{v / 1_000_000:.1f}".rstrip("0").rstrip(".") + (" млн" if locale == "ru" else "M")
    elif v >= 1_000:
        formatted = f"{v / 1_000:.0f}" + (" тыс" if locale == "ru" else "K")
    else:
        formatted = f"{v:.0f}"
    symbol_map = {"RUB": "₽", "USD": "$", "EUR": "€", "GBP": "£"}
    symbol = symbol_map.get(currency.upper(), "")
    if currency == "units" or not symbol:
        return f"{sign}{formatted}"
    if locale == "ru":
        return f"{sign}{formatted} {symbol}"
    return f"{symbol}{sign}{formatted}"


def _confidence_tier(
    ci_width_ratio: float, has_observed: bool, mode_is_fallback: bool
) -> Literal["high", "medium", "low"]:
    """Heuristic confidence rating from CI width + observed data + mode."""
    if mode_is_fallback or ci_width_ratio > 0.4:
        return "low"
    if has_observed and ci_width_ratio < 0.2:
        return "high"
    return "medium"


def _para_what(inputs: ExplainerInputs) -> str:
    """Para 1 — что прогноз говорит."""
    point = _format_number(inputs.point_forecast_mean, inputs.currency, inputs.locale)
    lower = _format_number(inputs.ci_lower_mean, inputs.currency, inputs.locale)
    upper = _format_number(inputs.ci_upper_mean, inputs.currency, inputs.locale)
    period_unit = (
        "месяц" if inputs.granularity == "monthly"
        else "неделя"
    ) if inputs.locale == "ru" else ("month" if inputs.granularity == "monthly" else "week")
    horizon_label = (
        f"{inputs.horizon_periods} {period_unit + ('а' if inputs.granularity == 'monthly' else 'ь')}"
        if inputs.locale == "ru"
        else f"{inputs.horizon_periods} {period_unit}s"
    )

    if inputs.locale == "ru":
        return (
            f"Прогноз продаж бренда: в среднем {point} за период (горизонт — {horizon_label}). "
            f"С учётом неопределённости — в диапазоне от {lower} до {upper}. "
            f"Это означает: 95 случаев из 100 показатель попадёт в этот интервал."
        )
    return (
        f"Forecast: average {point} per period (horizon: {horizon_label}). "
        f"Allowing for uncertainty, the range is {lower} to {upper}. "
        f"Reading: 95 cases out of 100, actual sales fall в this band."
    )


def _para_why(inputs: ExplainerInputs) -> str:
    """Para 2 — на чём основан."""
    mode_descriptions_ru = {
        "pure_transfer": (
            "Прогноз построен исключительно на данных похожего бренда (proxy). "
            "У вашего бренда пока нет своих исторических наблюдений — модель "
            "переносит закономерности proxy с учётом разницы рынков."
        ),
        "transfer_with_bias_check": (
            f"Прогноз использует proxy-бренд как основу, дополнительно сверяясь "
            f"с {inputs.n_recipient} наблюдениями вашего бренда — если расхождение "
            f"больше 30%, выдаётся предупреждение."
        ),
        "ols_with_proxy_priors": (
            f"Модель обучилась на {inputs.n_recipient} наблюдениях вашего бренда, "
            f"но также учла информацию proxy-бренда как «априорное знание». "
            f"Чем больше данных у бренда — тем меньше вес proxy."
        ),
        "bayesian_with_proxy_priors": (
            f"Полная Bayesian-модель: {inputs.n_recipient} наблюдений вашего бренда "
            f"+ proxy-распределения как informative priors. Возвращает не только "
            f"точечный прогноз, но и распределение возможных исходов."
        ),
    }
    mode_descriptions_en = {
        "pure_transfer": (
            "Forecast is built entirely on a similar brand's data (proxy). "
            "Your brand has no historical observations yet — the model transfers "
            "patterns from the proxy с adjustment for market differences."
        ),
        "transfer_with_bias_check": (
            f"Forecast uses the proxy brand as foundation, cross-checking against "
            f"{inputs.n_recipient} observations of your brand — flagged if "
            f"deviation exceeds 30%."
        ),
        "ols_with_proxy_priors": (
            f"Model was fit on {inputs.n_recipient} observations of your brand "
            f"и also incorporated proxy-brand information as 'prior knowledge'. "
            f"The more brand data, the less proxy weight."
        ),
        "bayesian_with_proxy_priors": (
            f"Full Bayesian model: {inputs.n_recipient} brand observations + proxy "
            f"distributions as informative priors. Returns not just point forecast "
            f"но distribution of possible outcomes."
        ),
    }
    base = (
        mode_descriptions_ru if inputs.locale == "ru" else mode_descriptions_en
    ).get(inputs.engine_mode, "")

    if inputs.trust_score is not None and base:
        trust_phrase = (
            f" Уровень доверия: {inputs.trust_score} из 100."
            if inputs.locale == "ru"
            else f" Trust score: {inputs.trust_score} of 100."
        )
        return base + trust_phrase
    return base or (
        "Прогноз сгенерирован моделью Aurora Launch Planner."
        if inputs.locale == "ru"
        else "Forecast generated by Aurora Launch Planner."
    )


def _para_risks(inputs: ExplainerInputs) -> str:
    """Para 3 — каким рискам подвержен."""
    ci_width_ratio = (
        (inputs.ci_upper_mean - inputs.ci_lower_mean)
        / max(abs(inputs.point_forecast_mean), 1.0)
    )
    is_fallback = "fallback" in inputs.methodology_signature

    risk_phrases_ru = []
    if ci_width_ratio > 0.4:
        risk_phrases_ru.append(
            f"Доверительный интервал широкий ({ci_width_ratio:.0%} от точечного значения) — "
            f"высокая неопределённость, желательно подождать ещё данных."
        )
    elif ci_width_ratio < 0.15:
        risk_phrases_ru.append(
            "Доверительный интервал узкий — модель уверена в прогнозе."
        )

    if is_fallback:
        risk_phrases_ru.append(
            "Использован упрощённый алгоритм (fallback) — полный Bayesian-режим "
            "появится в следующих версиях, когда у вашего бренда накопится "
            "достаточно данных."
        )

    if inputs.n_recipient == 0:
        risk_phrases_ru.append(
            "Поскольку у бренда ещё нет своих данных, прогноз нужно перепроверить "
            "через 4-6 недель после запуска и обновить через «Сравнить версии»."
        )

    for w in inputs.warnings[:2]:  # First 2 warnings only — avoid wall-of-text
        risk_phrases_ru.append(f"Внимание: {w}")

    if not risk_phrases_ru:
        return (
            "Прогноз стабилен — серьёзных рисков не выявлено."
            if inputs.locale == "ru"
            else "Forecast is stable — no major risks identified."
        )

    # Locale switch — RU only built so far; EN version mirrors
    if inputs.locale == "en":
        # Quick port — same ideas, English idiom
        risk_phrases_en = []
        if ci_width_ratio > 0.4:
            risk_phrases_en.append(
                f"Wide confidence interval ({ci_width_ratio:.0%} of point estimate) — "
                f"high uncertainty; wait для more data."
            )
        if is_fallback:
            risk_phrases_en.append(
                "Simplified (fallback) algorithm в use — full Bayesian mode "
                "available once brand has sufficient history."
            )
        if inputs.n_recipient == 0:
            risk_phrases_en.append(
                "No brand history yet — recheck forecast 4-6 weeks post-launch "
                "via 'Compare versions'."
            )
        for w in inputs.warnings[:2]:
            risk_phrases_en.append(f"Notice: {w}")
        return " ".join(risk_phrases_en) if risk_phrases_en else (
            "Forecast is stable — no major risks identified."
        )
    return " ".join(risk_phrases_ru)


def explain_local(inputs: ExplainerInputs) -> Explanation:
    """Generate 3-paragraph forecast explanation using local templates.

    Always works (no network). Output deterministic given same inputs.
    Numbers extracted from inputs, never invented. Phrasing varies by
    locale + engine mode + observed N + CI width + warnings.
    """
    ci_width_ratio = (
        (inputs.ci_upper_mean - inputs.ci_lower_mean)
        / max(abs(inputs.point_forecast_mean), 1.0)
    )
    is_fallback = "fallback" in inputs.methodology_signature
    confidence = _confidence_tier(
        ci_width_ratio=ci_width_ratio,
        has_observed=inputs.n_recipient > 0,
        mode_is_fallback=is_fallback,
    )

    return Explanation(
        what=_para_what(inputs),
        why=_para_why(inputs),
        risks=_para_risks(inputs),
        engine_used="local",
        confidence=confidence,
    )
