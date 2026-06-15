"""Customer-facing report copy — RU phrases + forbidden-phrase guard.

Codifies the reusable phrases from `02_Data_Spec/REPORT_SECTIONS_SPEC.md` §4.2 and
enforces the forbidden anti-patterns from §4.3. This is Launch-local (product
voice); the Core `aurora_reporting` primitives render it but do not own it.

Tier is exposed as a TEXT label + a similarity→tier mapping only — NOT emoji
(badges render unreliably in embedded PPTX/PNG; the Core styled-table renders a
vector tier chip from this label — Core correction П.7).

Acceptance (spec §7): customer phrases must match the §4.2 reusable list, and no
forbidden phrase may appear in any client-facing string.
"""

from __future__ import annotations

# Non-breaking space, EXPLICIT escape — RU number/unit typography ("165,9 млн ₽"
# must not wrap). An invisible literal U+00A0 is a known editing hazard, so the
# escape form (pure ASCII source) is used deliberately.
_NBSP = chr(0xA0)

# ── Tier (similarity verdict) ────────────────────────────────────────────────

# similarity aggregate score → tier key (spec §3.2 colour thresholds + §4.2 verdicts).
_TIER_THRESHOLDS = (
    (0.85, "gold"),
    (0.65, "silver"),
    (0.50, "bronze"),
)

_TIER_LABEL_RU = {
    "gold": "Высокая уверенность",
    "silver": "Средняя уверенность",
    "bronze": "Низкая уверенность",
}

_TIER_VERDICT_RU = {
    "gold": "Высокая уверенность — близкий прокси-бренд + полные anchors",
    "silver": "Средняя уверенность — подходящий прокси, требует verification posterior update",
    "bronze": "Низкая уверенность — прокси не идеален, рекомендуется поиск лучшего candidate",
}


def tier_from_similarity(aggregate: float) -> str:
    """Map a 0..1 aggregate similarity score to a tier key (gold/silver/bronze)."""
    for threshold, tier in _TIER_THRESHOLDS:
        if aggregate >= threshold:
            return tier
    return "bronze"


def tier_label(tier: str) -> str:
    """Short tier label for the vector chip (NOT emoji)."""
    return _TIER_LABEL_RU.get(tier, _TIER_LABEL_RU["bronze"])


def tier_verdict(tier: str) -> str:
    """Full tier verdict sentence (spec §4.2)."""
    return _TIER_VERDICT_RU.get(tier, _TIER_VERDICT_RU["bronze"])


# ── Number formatting ────────────────────────────────────────────────────────


def format_rub_millions(rub: float) -> str:
    """Format rubles as ``X млн ₽`` with non-breaking spaces (RU typography)."""
    millions = rub / 1_000_000.0
    # RU convention: NBSP thousands separator, comma decimal.
    whole = f"{millions:,.1f}".replace(",", _NBSP).replace(".", ",")
    return f"{whole}{_NBSP}млн{_NBSP}₽"


# ── Reusable phrases (spec §4.2) ─────────────────────────────────────────────


def headline_forecast(period_weeks: int, total_rub: float, ci_pct: float) -> str:
    """Headline forecast line (spec §4.2 / §2.1 headline)."""
    return (
        f"Прогноз продаж за первые {period_weeks} недель: "
        f"{format_rub_millions(total_rub)} ± {ci_pct:g}% (95% доверительный интервал)"
    )


def similarity_one_liner(proxy_name: str, aggregate: float) -> str:
    """Plain-language proxy one-liner (spec §2.1 slide 2.1)."""
    return f"Запуск базируется на прокси-бренде {proxy_name} с similarity {aggregate:g}"


def transfer_caveat(proxy_name: str) -> str:
    """Transfer caveat boilerplate (spec §4.2)."""
    return (
        f"Прогноз основан на трансфере структурных параметров от прокси-бренда "
        f"{proxy_name}. Magnitude калибруется от ваших recipient anchors. Real-world "
        f"результаты могут отличаться — неопределённость явно показана в 95% CI."
    )


def posterior_update_reminder() -> str:
    """Posterior update reminder (spec §4.2)."""
    return (
        "После 12–16 недель реальных recipient данных Aurora обновит прогноз. "
        "Предполагаемое сужение CI: –25–40% при стабильном recipient response."
    )


def methodology_cross_reference() -> str:
    """Methodology cross-reference (spec §4.2)."""
    return (
        "Полная методология + список академических источников — в разделе 8 этого "
        "отчёта и в Methodology Certificate PDF."
    )


# ── Forbidden phrases (spec §4.3 anti-patterns) ──────────────────────────────

FORBIDDEN_PHRASES: tuple[str, ...] = (
    "гарантированный результат",
    "гарантиру",  # "гарантируем", "гарантирует" — Aurora never guarantees
    "точный прогноз",
    "превзойдёт конкурентов",
    "превзойдет конкурентов",
    "полностью автоматизированный",
)


def find_forbidden_phrases(text: str) -> list[str]:
    """Return any forbidden phrases (case-insensitive) present in `text`."""
    lowered = text.lower()
    return [p for p in FORBIDDEN_PHRASES if p in lowered]


def assert_client_safe(*texts: str) -> None:
    """Raise ValueError if any text contains a forbidden phrase (spec §4.3).

    A preventive client-surface hygiene gate — call on every client-facing string
    the report composes before it ships.
    """
    violations: dict[str, list[str]] = {}
    for text in texts:
        hits = find_forbidden_phrases(text)
        if hits:
            violations[text] = hits
    if violations:
        detail = "; ".join(f"{hits!r} в {text!r}" for text, hits in violations.items())
        raise ValueError(f"Запрещённые формулировки (spec §4.3): {detail}")
