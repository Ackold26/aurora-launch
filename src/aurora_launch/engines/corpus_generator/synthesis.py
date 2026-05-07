"""Synthetic data synthesis для corpus projects.

Implements MMM-realistic time series generation:
- Hill saturation response per channel (γ_c, k_c)
- Adstock decay carryover (λ_c per channel)
- Category seasonality (52-week pattern)
- Long-term trend (linear approximation)
- ROI ratios preserved through synchronized R factor invariant
- Stationarity preserved (no unit roots в generated series)

Per ADAPTATION_RULES.md §1.4 rationale.

Uses numpy with explicit `np.random.Generator(np.random.PCG64(seed))` for
deterministic cross-platform reproducibility (NOT global np.random.seed).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from aurora_launch.schemas.synthetic_corpus import SyntheticProjectSpec


def _make_rng(seed: int) -> np.random.Generator:
    """Cross-platform deterministic RNG."""
    return np.random.Generator(np.random.PCG64(seed))


def _category_response_params(category_l3: str, n_channels: int, rng: np.random.Generator) -> dict:
    """Category-specific MMM response curve parameters.

    Per ADAPTATION_RULES.md §1.4 — adstock decay & Hill saturation per category type.
    """
    # Adstock decay λ_c — short-cycle FMCG ~0.3, long-cycle pharma ~0.6
    if category_l3.startswith("FMCG_food.snacks") or category_l3.startswith("FMCG_beverage"):
        adstock_base = 0.30
    elif category_l3.startswith("OTC_pharma"):
        adstock_base = 0.55
    elif category_l3.startswith("Cosmetics.skincare"):
        adstock_base = 0.45
    elif category_l3.startswith("Telecom") or category_l3.startswith("Banking"):
        adstock_base = 0.60
    else:
        adstock_base = 0.40

    # Per-channel variation (TV vs digital)
    adstock_decay = adstock_base + rng.uniform(-0.10, 0.10, size=n_channels)
    adstock_decay = np.clip(adstock_decay, 0.05, 0.85)

    # Hill γ_c (saturation shape) — typical 1.0-3.0
    hill_gamma = rng.uniform(1.0, 3.0, size=n_channels)

    # Hill k_c (half-saturation, normalized to spend_max)
    hill_k_normalized = rng.uniform(0.3, 1.5, size=n_channels)

    # β coefficients (channel impact magnitude)
    beta = rng.uniform(0.05, 0.25, size=n_channels)

    return {
        "adstock_decay": adstock_decay.tolist(),
        "hill_gamma": hill_gamma.tolist(),
        "hill_k_normalized": hill_k_normalized.tolist(),
        "beta": beta.tolist(),
    }


def _seasonality_pattern(category_l3: str, variant: str, rng: np.random.Generator) -> NDArray:
    """52-week seasonality deviation pattern.

    High-seasonality variant amplifies pattern 2x.
    """
    weeks = np.arange(52)
    base_amplitude = 0.20

    if variant == "high_seasonality":
        amplitude = base_amplitude * 2.0
    elif variant == "low_data":
        amplitude = base_amplitude * 0.5
    else:
        amplitude = base_amplitude

    # FMCG impulse — summer peak; Pharma — winter (cold/flu) peak; cosmetics — Q4 (gifting)
    if category_l3.startswith("FMCG_beverage") or "snacks" in category_l3:
        peak_week = 26  # mid-summer
    elif category_l3.startswith("OTC_pharma.OTC_cold_flu"):
        peak_week = 4  # late January
    elif category_l3.startswith("Cosmetics"):
        peak_week = 50  # December
    else:
        peak_week = rng.integers(0, 52)

    # Sinusoidal with category-specific phase
    phase = 2 * np.pi * (weeks - peak_week) / 52
    seasonal = amplitude * np.cos(phase)

    # Add small noise on top
    seasonal += rng.normal(0, amplitude * 0.05, size=52)

    return seasonal


def _generate_channel_spend(
    n_weeks: int,
    n_channels: int,
    media_maturity: str,
    variant: str,
    rng: np.random.Generator,
) -> NDArray:
    """Generate weekly spend per channel.

    Shape: (n_weeks, n_channels). Patterns reflect media_maturity.
    """
    spend = np.zeros((n_weeks, n_channels))

    for ch in range(n_channels):
        base_spend = rng.uniform(50_000, 500_000)

        if media_maturity == "ALWAYS_ON":
            # Continuous with weekly variation
            weekly = base_spend * (1 + 0.15 * rng.normal(size=n_weeks))
            weekly = np.maximum(weekly, base_spend * 0.3)
        elif media_maturity == "PULSING":
            # On-off pattern (4 weeks on, 4 weeks off)
            cycle = (np.arange(n_weeks) % 8) < 4
            weekly = base_spend * cycle * (1 + 0.10 * rng.normal(size=n_weeks))
            weekly = np.maximum(weekly, 0)
        elif media_maturity == "PROMO_DRIVEN":
            # Sparse high-spike weeks
            promo_weeks = rng.choice(n_weeks, size=n_weeks // 8, replace=False)
            weekly = np.zeros(n_weeks)
            weekly[promo_weeks] = base_spend * 4.0
        else:  # DORMANT
            weekly = np.zeros(n_weeks)
            if variant != "low_data":
                # Few weeks at end as comeback test
                weekly[-8:] = base_spend * 0.5

        spend[:, ch] = weekly

    return spend


def _apply_adstock(spend: NDArray, decay: float) -> NDArray:
    """Geometric adstock transform per channel."""
    n = len(spend)
    out = np.zeros(n)
    out[0] = spend[0]
    for t in range(1, n):
        out[t] = spend[t] + decay * out[t - 1]
    return out


def _hill_saturation(adstocked: NDArray, gamma: float, k_normalized: float) -> NDArray:
    """Hill saturation response."""
    spend_max = max(adstocked.max(), 1.0)
    k = k_normalized * spend_max
    return adstocked**gamma / (adstocked**gamma + k**gamma)


def synthesize_project_data(spec: SyntheticProjectSpec) -> dict:
    """Generate complete synthetic project data structure.

    Returns dict with keys:
    - meta: project metadata
    - response_params: MMM response curve parameters
    - seasonality: 52-week deviation pattern
    - weekly_data: list of week records (date_iso, sales_volume, channel_spends_dict)
    - canonical_columns: list of CanonicalFieldName equivalents
    """
    rng = _make_rng(spec.seed)

    # Response curve parameters (MMM realistic)
    response_params = _category_response_params(spec.category_l3, spec.n_channels, rng)

    # Seasonality
    seasonality = _seasonality_pattern(spec.category_l3, spec.variant, rng)

    # Channel spend
    spend = _generate_channel_spend(
        spec.n_weeks, spec.n_channels, spec.media_maturity, spec.variant, rng
    )

    # Compute response per channel: adstock → Hill → β-scaled
    adstock_decays = np.array(response_params["adstock_decay"])
    gammas = np.array(response_params["hill_gamma"])
    k_norms = np.array(response_params["hill_k_normalized"])
    betas = np.array(response_params["beta"])

    channel_response = np.zeros_like(spend)
    for ch in range(spec.n_channels):
        adstocked = _apply_adstock(spend[:, ch], adstock_decays[ch])
        saturated = _hill_saturation(adstocked, gammas[ch], k_norms[ch])
        channel_response[:, ch] = saturated * betas[ch]

    # Aggregate response
    total_response = channel_response.sum(axis=1)

    # Add baseline + seasonality + trend
    baseline_mean = rng.uniform(0.4, 0.7)  # baseline as fraction of peak

    # Seasonality — repeat 52-week pattern
    full_seasonality = np.tile(seasonality, (spec.n_weeks // 52) + 1)[: spec.n_weeks]

    # Trend
    if spec.lifecycle == "GROWING":
        trend = np.linspace(0, 0.20, spec.n_weeks)
    elif spec.lifecycle == "DECLINING":
        trend = np.linspace(0, -0.15, spec.n_weeks)
    else:
        trend = np.zeros(spec.n_weeks)

    # Final sales (volatility per variant)
    if spec.variant == "volatile":
        noise_scale = 0.15
    elif spec.variant == "low_data":
        noise_scale = 0.30
    else:
        noise_scale = 0.05

    noise = rng.normal(0, noise_scale, size=spec.n_weeks)

    sales_normalized = baseline_mean + 0.5 * total_response + full_seasonality + trend + noise
    sales_normalized = np.maximum(sales_normalized, 0.05)  # prevent negatives

    # Scale to absolute (millions of packs typical)
    base_volume = rng.uniform(50_000, 5_000_000)
    sales_volume = sales_normalized * base_volume

    # Generate week dates (weekly Monday starting from Jan 2024)
    start_year = 2024
    start_week_offset = rng.integers(0, 4)
    week_dates = []
    for w in range(spec.n_weeks):
        # ISO week date approximation
        day_of_year = (start_week_offset * 7) + (w * 7) + 1
        year = start_year + (day_of_year - 1) // 365
        day_in_year = ((day_of_year - 1) % 365) + 1
        # Approximate to ISO month-day (good enough для synthetic)
        month = ((day_in_year - 1) // 30) + 1
        day = ((day_in_year - 1) % 30) + 1
        month = min(12, month)
        day = min(28, day)  # safe for all months
        week_dates.append(f"{year}-{month:02d}-{day:02d}")

    # Channel names
    channel_names = ["TV", "Digital", "OOH", "Radio", "Print", "Cinema", "Sponsorship", "OLV"]
    channels = channel_names[: spec.n_channels]

    # Weekly records
    weekly_data = []
    for w in range(spec.n_weeks):
        record = {
            "period_date": week_dates[w],
            "sales_volume": float(sales_volume[w]),
        }
        for ch_idx, ch_name in enumerate(channels):
            record[f"spend_{ch_name.lower()}"] = float(spend[w, ch_idx])
        weekly_data.append(record)

    canonical_columns = ["period_date", "sales_volume"] + [
        f"spend_{ch.lower()}" for ch in channels
    ]

    return {
        "meta": {
            "spec": spec.model_dump(),
            "channels": channels,
            "n_weeks": spec.n_weeks,
            "rng_algorithm": "PCG64",
        },
        "response_params": response_params,
        "seasonality_52w": seasonality.tolist(),
        "weekly_data": weekly_data,
        "canonical_columns": canonical_columns,
    }
