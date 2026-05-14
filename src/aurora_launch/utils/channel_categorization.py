"""Channel categorization for Trust Level 3 (Brand vs Performance Split).

Single source of truth for media-channel classification into brand / performance / mixed.

Ported from Aurora Econometrica (sidecar/econometrica/utils/channel_categorization.py).
Import paths updated; no other changes.

Used by:
- bayesian_engine.py: group-conditional priors (brand_sigma, perf_sigma, brand_mu_logit, perf_mu_logit)
- decompose.py: per-group ROI verdict thresholds
- loader.py: get_channel_categories fallback heuristic

Heuristic: substring match against BRAND_HINTS / PERF_HINTS after normalization.
Confidence score = 1.0 if single-category match, 0.5 if ambiguous, 0.0 if no match (→ mixed).
"""

from __future__ import annotations

from typing import Literal, TypedDict

ChannelCategory = Literal['brand', 'performance', 'mixed']

# Heuristic hints - single source of truth
BRAND_HINTS: tuple[str, ...] = (
    'TRP', 'GRP', 'OTS', 'ОХВАТ', 'РЕЙТИНГ',
    'TV', 'ТВ', 'OOH', 'НАРУЖК', 'РАДИО', 'RADIO',
    'БРЕНД', 'BRAND',
    # OLV (Online Video) - video advertising works on awareness (long-decay) similar to TV.
    'OLV',
)

PERF_HINTS: tuple[str, ...] = (
    'DIGITAL', 'SEARCH', 'ПОИСК', 'CONTEXT', 'КОНТЕКСТ',
    'SOCIAL', 'СОЦ', 'CTR', 'CPC', 'CPA', 'PERFORMANCE', 'ПЕРФ',
    'ЯНДЕКС', 'GOOGLE', 'VK', 'ВК', 'TELEGRAM', 'ТЕЛЕГРАМ',
    'МЕТА', 'META', 'КЛИК', 'ПРОСМОТР', 'ВИЗИТ',
    'PROGRAMMATIC', 'ПРОГРАММАТИК', 'DSP',
)

# Strong performance signals - auto-bidding / response-direct markers that
# override brand classification if both match.
STRONG_PERF_HINTS: tuple[str, ...] = (
    'PROGRAMMATIC', 'ПРОГРАММАТИК', 'DSP',
    'CPC', 'CPA', 'CTR',
    'PERFORMANCE', 'ПЕРФ',
)


class CategorySuggestion(TypedDict):
    category: ChannelCategory
    confidence: float
    reasoning: str


def normalize_channel_name(name: str) -> str:
    """Lowercase + strip punctuation/parens for hint matching."""
    if not name:
        return ''
    s = name.upper()
    cleaned = []
    for ch in s:
        if ch.isalnum() or ch in (' ', '-', '_'):
            cleaned.append(ch)
        else:
            cleaned.append(' ')
    return ' '.join(''.join(cleaned).split())


def auto_suggest_category(channel_name: str) -> CategorySuggestion:
    """Suggest category for a single channel name based on heuristic hints.

    Returns:
        {category, confidence, reasoning}
        - confidence 1.0: strong unambiguous match (only one category hits)
        - confidence 0.5: ambiguous - both brand AND performance hints match → mixed
        - confidence 0.0: no hint match → mixed (default)
    """
    if not channel_name:
        return {'category': 'mixed', 'confidence': 0.0, 'reasoning': 'empty name'}

    normalized = normalize_channel_name(channel_name)

    brand_matches = [h for h in BRAND_HINTS if h in normalized]
    perf_matches = [h for h in PERF_HINTS if h in normalized]

    is_brand = bool(brand_matches)
    is_perf = bool(perf_matches)

    if is_brand and not is_perf:
        conf = min(1.0, 0.7 + 0.15 * (len(brand_matches) - 1))
        return {
            'category': 'brand',
            'confidence': round(conf, 2),
            'reasoning': f"brand hints: {', '.join(brand_matches)}",
        }
    if is_perf and not is_brand:
        conf = min(1.0, 0.7 + 0.15 * (len(perf_matches) - 1))
        return {
            'category': 'performance',
            'confidence': round(conf, 2),
            'reasoning': f"performance hints: {', '.join(perf_matches)}",
        }
    if is_brand and is_perf:
        # Strong-perf override: programmatic / CPC / CPA / DSP / Performance
        strong_matches = [h for h in STRONG_PERF_HINTS if h in normalized]
        if strong_matches:
            return {
                'category': 'performance',
                'confidence': 0.8,
                'reasoning': f"strong-perf override: {', '.join(strong_matches)} (brand hints {brand_matches} ignored)",
            }
        return {
            'category': 'mixed',
            'confidence': 0.5,
            'reasoning': f"ambiguous: brand={brand_matches}, perf={perf_matches}",
        }
    return {
        'category': 'mixed',
        'confidence': 0.0,
        'reasoning': 'no hint match - default to mixed',
    }


def auto_suggest_categories(channel_names: list[str]) -> dict[str, CategorySuggestion]:
    """Batch version. Returns {channel_name: suggestion}."""
    return {ch: auto_suggest_category(ch) for ch in channel_names}


def validate_categorization_for_hierarchical(
    categories: dict[str, ChannelCategory],
    media_cols: list[str],
) -> tuple[dict[str, ChannelCategory], list[str]]:
    """Validate categorization for hierarchical training.

    Identifiability constraint:
        - len(brand_idx) >= 2 OR demoted to mixed
        - len(perf_idx)  >= 2 OR demoted to mixed
        - Single-channel groups → degenerate posterior, r_hat > 1.1, fail.

    Works ONLY with explicit user entries - does NOT fill missing channels with 'mixed'
    automatically. Pre-Trust3 projects keep empty channel_categories in pickle,
    decompose applies heuristic fallback.

    Returns:
        (validated_categories, warnings)
    """
    warnings: list[str] = []

    media_set = set(media_cols)
    validated: dict[str, ChannelCategory] = {
        ch: cat for ch, cat in categories.items() if ch in media_set
    }
    orphans = [ch for ch in categories if ch not in media_set]
    if orphans:
        warnings.append(f"Удалены orphaned категории для каналов: {', '.join(orphans)}")

    brand_channels = [ch for ch, cat in validated.items() if cat == 'brand']
    perf_channels = [ch for ch, cat in validated.items() if cat == 'performance']

    if 0 < len(brand_channels) < 2:
        for ch in brand_channels:
            validated[ch] = 'mixed'
        warnings.append(
            f"Категория Brand имеет всего {len(brand_channels)} канал(ов) "
            f"({', '.join(brand_channels)}). Для надёжного hierarchical разделения нужно ≥2. "
            f"Канал(ы) переведены в Mixed (single prior)."
        )

    if 0 < len(perf_channels) < 2:
        for ch in perf_channels:
            validated[ch] = 'mixed'
        warnings.append(
            f"Категория Performance имеет всего {len(perf_channels)} канал(ов) "
            f"({', '.join(perf_channels)}). Для надёжного hierarchical разделения нужно ≥2. "
            f"Канал(ы) переведены в Mixed (single prior)."
        )

    return validated, warnings


def resolve_per_channel_categories(
    explicit: dict[str, ChannelCategory],
    media_cols: list[str],
    default: ChannelCategory = 'mixed',
) -> list[ChannelCategory]:
    """Resolve per-channel category vector for model (in-order list).

    Returns:
        list of categories aligned with media_cols order. Missing keys get `default`.
    """
    return [explicit.get(ch, default) for ch in media_cols]


def is_hierarchical_eligible(categories: dict[str, ChannelCategory]) -> bool:
    """Check if categorization warrants hierarchical priors.

    Returns True iff at least one group (brand or performance) has >= 2 channels
    AND there's at least one explicit non-mixed assignment.
    """
    if not categories:
        return False
    n_brand = sum(1 for c in categories.values() if c == 'brand')
    n_perf = sum(1 for c in categories.values() if c == 'performance')
    return n_brand >= 2 or n_perf >= 2


def infer_categories_heuristic(media_cols: list[str]) -> dict[str, ChannelCategory]:
    """Convenience helper: auto-suggest for all + apply confidence threshold.

    Confidence < 0.7 → mixed (uncertain auto-suggestion → defer to user override).
    Used as fallback for old pickles without explicit channel_categories.
    """
    suggestions = auto_suggest_categories(media_cols)
    result: dict[str, ChannelCategory] = {}
    for ch, sug in suggestions.items():
        if sug['confidence'] >= 0.7:
            result[ch] = sug['category']
        else:
            result[ch] = 'mixed'
    return result
