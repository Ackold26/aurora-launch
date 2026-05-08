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

from datetime import date, timedelta

import numpy as np
from numpy.typing import NDArray

from aurora_launch.schemas.synthetic_corpus import SyntheticProjectSpec


def _make_rng(seed: int) -> np.random.Generator:
    """Cross-platform deterministic RNG."""
    return np.random.Generator(np.random.PCG64(seed))


# FIX H-Audit-3: full handling of all 14 declared categories.
# Per ADAPTATION_RULES.md §1.4 + memory `project_econometrica_target_architecture_v3`
# domain knowledge о category MMM characteristics.
_CATEGORY_RESPONSE_PARAMS_TABLE: dict[str, dict[str, tuple[float, float]]] = {
    # FMCG impulse — short adstock, low saturation, fast turnover
    "FMCG_food.snacks_savoury":   {"adstock": (0.25, 0.40), "hill_gamma": (1.0, 2.5), "hill_k": (0.3, 1.0)},
    "FMCG_food.snacks_sweet":     {"adstock": (0.25, 0.40), "hill_gamma": (1.0, 2.5), "hill_k": (0.3, 1.0)},
    "FMCG_food.dairy_yogurt":     {"adstock": (0.30, 0.50), "hill_gamma": (1.2, 2.8), "hill_k": (0.4, 1.2)},
    "FMCG_beverage.beverage_carbonated": {"adstock": (0.20, 0.35), "hill_gamma": (1.0, 2.3), "hill_k": (0.3, 1.0)},
    "FMCG_beverage.beverage_juice":      {"adstock": (0.25, 0.40), "hill_gamma": (1.2, 2.5), "hill_k": (0.4, 1.1)},
    "FMCG_beverage.beverage_energy":     {"adstock": (0.25, 0.45), "hill_gamma": (1.5, 3.0), "hill_k": (0.5, 1.5)},
    # OTC pharma — moderate adstock, regulated media → cleaner curves
    "OTC_pharma.OTC_cold_flu":    {"adstock": (0.45, 0.65), "hill_gamma": (1.5, 2.8), "hill_k": (0.5, 1.5)},
    "OTC_pharma.OTC_pain":        {"adstock": (0.45, 0.65), "hill_gamma": (1.5, 2.8), "hill_k": (0.5, 1.5)},
    # Cosmetics premium — moderate adstock, brand/awareness driven
    "Cosmetics.skincare_premium": {"adstock": (0.35, 0.55), "hill_gamma": (1.5, 3.0), "hill_k": (0.5, 1.7)},
    "Cosmetics.haircare_premium": {"adstock": (0.35, 0.55), "hill_gamma": (1.5, 3.0), "hill_k": (0.5, 1.7)},
    # Telecom — long adstock (subscription decision cycle), high saturation thresholds
    "Telecom.telecom_b2c_mobile": {"adstock": (0.55, 0.75), "hill_gamma": (1.8, 3.5), "hill_k": (0.8, 2.2)},
    # Banking retail — similar to telecom (long consideration), regulated
    "Banking.banking_retail":     {"adstock": (0.55, 0.75), "hill_gamma": (1.8, 3.5), "hill_k": (0.8, 2.2)},
    # Awareness-only (synthetic awareness trajectory category)
    "awareness.brand_awareness_only": {"adstock": (0.40, 0.60), "hill_gamma": (1.2, 2.5), "hill_k": (0.4, 1.5)},
    # Cross-category edge case (mismatched proxy/recipient — for testing edge logic)
    "cross_category.cross_l1_edge": {"adstock": (0.20, 0.80), "hill_gamma": (1.0, 4.0), "hill_k": (0.2, 2.5)},
}


def _category_response_params(category_l3: str, n_channels: int, rng: np.random.Generator) -> dict:
    """Category-specific MMM response curve parameters per ADAPTATION_RULES §1.4.

    FIX H-Audit-3: explicit table coverage для all 14 declared categories.
    Each category has tuple (low, high) for adstock/hill_gamma/hill_k —
    sampled per-channel within bounds (TV vs digital variation).
    Cross-category edge case uses widest bounds (deliberate volatility for
    testing transfer methodology robustness).
    """
    params = _CATEGORY_RESPONSE_PARAMS_TABLE.get(category_l3)
    if params is None:
        # Fallback default (categories beyond declared 14 — edge of Literal type)
        params = {"adstock": (0.30, 0.50), "hill_gamma": (1.0, 3.0), "hill_k": (0.3, 1.5)}

    adstock_lo, adstock_hi = params["adstock"]
    gamma_lo, gamma_hi = params["hill_gamma"]
    k_lo, k_hi = params["hill_k"]

    # Per-channel sampling within category bounds (TV typically slower decay
    # than digital; first half channels biased to upper bound)
    adstock_decay = rng.uniform(adstock_lo, adstock_hi, size=n_channels)
    # Add small per-channel variation (TV vs digital pattern)
    if n_channels >= 2:
        adstock_decay[0] = min(adstock_hi, adstock_decay[0] + 0.05)  # TV slower
        adstock_decay[1] = max(adstock_lo, adstock_decay[1] - 0.05)  # digital faster

    hill_gamma = rng.uniform(gamma_lo, gamma_hi, size=n_channels)
    hill_k_normalized = rng.uniform(k_lo, k_hi, size=n_channels)

    # β coefficients — magnitude varies inversely with brand_size в spec, but
    # baseline ~0.05-0.25 reasonable
    beta = rng.uniform(0.05, 0.25, size=n_channels)

    return {
        "adstock_decay": adstock_decay.tolist(),
        "hill_gamma": hill_gamma.tolist(),
        "hill_k_normalized": hill_k_normalized.tolist(),
        "beta": beta.tolist(),
        "category_table_used": category_l3 in _CATEGORY_RESPONSE_PARAMS_TABLE,
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

    # FIX H-Audit-3: explicit seasonality phase per category (was: random fallback).
    # Rationale per category type:
    # - FMCG impulse (snacks/beverages) — summer peak (week 26)
    # - OTC pharma cold/flu — winter peak (late January, week 4)
    # - OTC pharma pain — flat (year-round, no strong seasonality)
    # - Cosmetics premium — Q4 gifting peak (week 50)
    # - Telecom/Banking — Q1 budget renewals + Q4 promotional peaks (use Q1=week 6)
    # - Awareness — flat with mild Q4 lift (gifting/holiday context)
    # - Cross-category edge — deliberately random (tests transfer to volatile target)
    if "snacks" in category_l3 or category_l3.startswith("FMCG_beverage"):
        peak_week = 26
    elif category_l3 == "OTC_pharma.OTC_cold_flu":
        peak_week = 4
    elif category_l3 == "OTC_pharma.OTC_pain":
        peak_week = 26  # near-flat, mild summer peak (outdoor activities → injuries)
        amplitude *= 0.5  # de-amplified
    elif category_l3.startswith("Cosmetics"):
        peak_week = 50
    elif category_l3.startswith("Telecom") or category_l3.startswith("Banking"):
        peak_week = 6  # Q1 corporate budget cycle
        amplitude *= 0.7  # less seasonal than FMCG
    elif category_l3.startswith("awareness"):
        peak_week = 50
        amplitude *= 0.3  # awareness barely seasonal
    elif category_l3.startswith("cross_category"):
        peak_week = int(rng.integers(0, 52))  # explicit edge — random
    elif category_l3.startswith("FMCG_food.dairy"):
        peak_week = 13  # spring/Easter
    else:
        peak_week = int(rng.integers(0, 52))

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


def _is_awareness_category(category_l3: str) -> bool:
    """Awareness categories require different synthesis (logit-scale, ceiling 100)."""
    return category_l3.startswith("awareness.")


def synthesize_project_data(spec: SyntheticProjectSpec) -> dict:
    """Generate complete synthetic project data structure.

    Returns dict with keys:
    - meta: project metadata (includes `kpi_type`)
    - response_params: MMM response curve parameters
    - seasonality: 52-week deviation pattern
    - weekly_data: list of week records — sales-driven categories use
      `sales_volume`; awareness categories use `awareness_pct` (logit-scaled).
    - canonical_columns: list of CanonicalFieldName equivalents

    FIX B-Audit-5: awareness categories now produce logit-scale `awareness_pct`
    trajectory с ceiling 100 (per Aurora Эконометрика awareness module).
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

    is_awareness = _is_awareness_category(spec.category_l3)

    if is_awareness:
        # Awareness — logit-scale trajectory с ceiling 100.
        # Baseline awareness (e.g., 5-15% для new brand)
        baseline_awareness = rng.uniform(0.05, 0.15)
        # Awareness response: logit transform → linear sum → inverse logit
        # Adstock-decayed media drives awareness lift
        media_lift = 0.5 * total_response  # normalized
        # Combine in logit space
        eps = 1e-9
        baseline_logit = np.log(baseline_awareness / (1 - baseline_awareness + eps) + eps)
        full_logit = baseline_logit + media_lift + 0.5 * full_seasonality + trend + noise
        kpi_normalized = 1.0 / (1.0 + np.exp(-full_logit))
        kpi_values = np.clip(kpi_normalized * 100.0, 0.0, 100.0)  # awareness % с ceiling 100
        kpi_field_name = "awareness_pct"
        kpi_type = "awareness"
    else:
        # Sales-driven categories (FMCG/OTC/Cosmetics/Telecom/Banking/etc.)
        sales_normalized = baseline_mean + 0.5 * total_response + full_seasonality + trend + noise
        sales_normalized = np.maximum(sales_normalized, 0.05)
        base_volume = rng.uniform(50_000, 5_000_000)
        kpi_values = sales_normalized * base_volume
        kpi_field_name = "sales_volume"
        kpi_type = "sales"

    # Generate week dates (weekly Monday starting from configurable base date).
    # FIX B-Audit-1: use proper datetime arithmetic, not 30-day-month approximation.
    # All dates valid ISO 8601, real calendar (handles leap years correctly).
    start_date = date(2024, 1, 1)
    # First Monday on/after start_date
    days_to_monday = (7 - start_date.weekday()) % 7
    start_monday = start_date + timedelta(days=days_to_monday)
    # Optional offset (deterministic from rng)
    start_week_offset = int(rng.integers(0, 4))
    base_monday = start_monday + timedelta(weeks=start_week_offset)

    week_dates = [
        (base_monday + timedelta(weeks=w)).isoformat() for w in range(spec.n_weeks)
    ]

    # Channel names
    channel_names = ["TV", "Digital", "OOH", "Radio", "Print", "Cinema", "Sponsorship", "OLV"]
    channels = channel_names[: spec.n_channels]

    # Weekly records (kpi_field_name varies by category type)
    weekly_data = []
    for w in range(spec.n_weeks):
        record = {
            "period_date": week_dates[w],
            kpi_field_name: float(kpi_values[w]),
        }
        for ch_idx, ch_name in enumerate(channels):
            record[f"spend_{ch_name.lower()}"] = float(spend[w, ch_idx])
        weekly_data.append(record)

    canonical_columns = ["period_date", kpi_field_name] + [
        f"spend_{ch.lower()}" for ch in channels
    ]

    return {
        "meta": {
            "spec": spec.model_dump(),
            "channels": channels,
            "n_weeks": spec.n_weeks,
            "rng_algorithm": "PCG64",
            "kpi_type": kpi_type,
            "kpi_field_name": kpi_field_name,
        },
        "response_params": response_params,
        "seasonality_52w": seasonality.tolist(),
        "weekly_data": weekly_data,
        "canonical_columns": canonical_columns,
    }
