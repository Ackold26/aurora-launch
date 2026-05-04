# Aurora Launch - Adaptation Rules

**Status:** Accepted (S004 closed 2026-05-04)
**Authority:** P3 в `00_Overview/PRINCIPLES.md` + Section 1, 2, 3, 8 `MATH_REFERENCE.md`
**Sprint context:** Sprint B3 implementation reference
**Owner:** Маша (math design) + Антон (domain validation, autonomous mandate)
**Related ADR:** `decisions/ADR-003-pretrain-vs-joint-training.md` - locks pre-train + transfer approach

## Контекст

P3 declares: переносим **shape**, не **magnitude**. Этот документ финализирует:

1. **Transfer parameter list** - какие параметры именно переносятся from proxy posterior, какие нет
2. **Magnitude calibration formulas** - как из anchors восстанавливается β-magnitude + baseline
3. **Anchor quality rules** - sensitivity к incomplete anchors, uncertainty propagation
4. **Cross-category transfer matrix** - allowed transfers (L3/L2/L1 match), penalties (adjacent L1), blocked (non-adjacent)
5. **Workflow:** pre-train + transfer (locked в ADR-003), не joint training (Phase D consideration)
6. **Paused brand integration** - organic baseline DSM history → recipient calibration enhancement

Sprint B3 implements `engines/launch_adapt.py` (`extract_proxy_priors` + `apply_recipient_magnitudes`) per этот документ.

---

## 1. Transfer Parameter List

### 1.1 Five Shape Parameters Transferred (per channel + global)

| Parameter | Symbol | Per-channel? | Source | Inflation by similarity |
|---|---|---|---|---|
| **Adstock decay** | λ_c | YES | proxy posterior (mean + std) | proxy std × similarity_inflation |
| **Hill saturation shape** | γ_c | YES | proxy posterior (mean + std) | proxy std × similarity_inflation |
| **Hill half-saturation** | k_c | YES | proxy posterior (mean + std) | proxy std × similarity_inflation |
| **Category seasonality** | season_t (52-vector) | NO (global) | proxy posterior (residual after detrend) | scale_var × similarity_inflation |
| **Long-term trend slope** | β_trend | NO (global) | proxy posterior (linear approximation) | proxy std × similarity_inflation |

**Inflation factors** (см. `SIMILARITY_FRAMEWORK.md` Section 5):
- High verdict (S>=0.85): 1.2× std
- Medium (0.65-0.85): 1.5× std
- Low (0.50-0.65): 2.0× std

### 1.2 Optional Sixth Parameter

| Parameter | When transferred | Status |
|---|---|---|
| **Reach-frequency curve shape** | Если proxy model fitted reach-frequency layer (Phase B optional, не required для basic transfer) | OPTIONAL (skip если no fit) |

Aurora Launch Phase B uses standard MMM (TRP/GRP/spend → response) без separate reach-frequency layer. Phase C+ если customers просят explicit reach analysis - проверим transfer.

### 1.3 NOT Transferred (Recipient-Specific)

| Parameter | Why not transferred |
|---|---|
| **β coefficients per channel** | Magnitude зависит от размера recipient'а (5% share brand vs 20%) |
| **Baseline / intercept** | Зависит от distribution + price + organic demand recipient'а |
| **Residual variance σ** | Зависит от noise level recipient market |
| **Cross-category competitive controls** | Зависит от competitive set recipient'a |
| **Promo coefficients** | Recipient promo strategy independent от proxy |

These are calibrated through **anchors-based magnitude calibration** (Section 2) или fitted as recipient priors with weak informative defaults.

### 1.4 Why these specific parameters (rationale)

**Adstock decay (λ_c):** carryover effect category-specific. TV ad для chips на week t влияет на purchases весь импульсный покупочный cycle (4-6 weeks). Recipient в same category inherits same decay pattern. Per-channel because TV-decay ≠ digital-decay.

**Hill γ_c (saturation shape):** S-curve steepness reflects audience saturation behavior. Same category audience saturates similarly. Per-channel because digital saturates faster than TV (different reach mechanics).

**Hill k_c (half-saturation):** absolute spend level где effect = α/2. Reflects category competitive landscape. Slight scale-dependence на recipient size handled через subsequent calibration (β scaling).

**Category seasonality:** 52-week deviation pattern (e.g., snacks +20% summer, -15% February). Category-driven, не brand-driven.

**Long-term trend slope:** category growth/decline characteristic. Separate из anchor `category_trend` field (validation cross-check: if anchor says "growing" но trend negative - warning).

---

## 2. Magnitude Calibration Formulas

Magnitudes восстанавливаются из anchors. Two key calibrations: baseline + β coefficients.

### 2.1 Baseline Calibration

**Formula:**

```
baseline_recipient_t = market_size_year × seasonality_t × planned_share(t) × distribution(t) × pricing_factor
```

где:
- `market_size_year` = anchor.market_size_rub (yearly category size)
- `seasonality_t` = transferred from proxy (52-week vector deviation от yearly mean) for week t
- `planned_share(t)` = ramp from 0 к anchor.planned_share_pct/100 over distribution_ramp_weeks
- `distribution(t)` = ramp from 0 к anchor.distribution_target_pct/100 over distribution_ramp_weeks
- `pricing_factor` = function of anchor.pricing_index_vs_proxy (Section 2.3)

### 2.2 Ramp Functions (planned_share, distribution)

Linear ramp by default:

```python
def linear_ramp(t: int, target: float, ramp_weeks: int) -> float:
    """Ramp from 0 to target over ramp_weeks, then constant."""
    if t < 0:
        return 0.0
    if t >= ramp_weeks:
        return target
    return target * (t / ramp_weeks)
```

**S-curve alternative (Phase C+):** sigmoid ramp better reflects real distribution growth (slow start, fast middle, plateau). Phase B keeps linear (simpler + adequate для Sprint B6 pilot).

### 2.3 Pricing Factor

Pricing affects volume через elasticity. Cheaper price → more volume (within reason). Default category-elasticities:

```python
PRICING_ELASTICITIES = {
    # category L1 → elasticity (volume response к pricing change)
    "FMCG_food.snacks_savoury": 0.7,    # impulse - more elastic
    "FMCG_food.snacks_sweet": 0.7,
    "FMCG_food.dairy_yogurt": 0.5,      # mid-elastic
    "FMCG_food.dairy_milk": 0.4,        # less elastic - staple
    "FMCG_beverage.beverage_carbonated": 0.6,
    "FMCG_beverage.beverage_energy": 0.5,
    "FMCG_beverage.beverage_juice": 0.5,
    "OTC_pharma.*": 0.2,                 # therapeutic need - low elastic
    "Rx_pharma.*": 0.1,                  # very low (insurance, need)
    "Cosmetics.cosmetics_premium_*": 0.3, # prestige effect, low elastic
    "Cosmetics.cosmetics_mass_*": 0.6,
    "Telecom.*": 0.4,                    # subscription churn elastic
    "Banking.*": 0.3,
    "B2B.*": 0.5,                        # bounded by procurement cycles
}

DEFAULT_PRICING_ELASTICITY = 0.5  # fallback


def pricing_factor(pricing_index: float, elasticity: float) -> float:
    """
    Volume response к pricing change.
    pricing_index = recipient_price / proxy_price.
    pricing_factor < 1.0 if recipient more expensive.
    pricing_factor > 1.0 if recipient cheaper.
    """
    return (1.0 / pricing_index) ** elasticity
```

**Examples:**

| pricing_index | elasticity | pricing_factor | Comment |
|---|---|---|---|
| 0.7 (cheaper 30%) | 0.5 | 1.20 | 20% volume boost |
| 0.7 | 0.7 (FMCG impulse) | 1.30 | 30% boost (more elastic) |
| 1.0 | 0.5 | 1.00 | Same price, no change |
| 1.5 | 0.5 | 0.82 | Premium - 18% volume reduction |
| 1.5 | 0.3 (premium cosmetics) | 0.89 | Prestige effect mitigates |
| 2.0 | 0.5 | 0.71 | 29% volume reduction |
| 2.0 | 0.2 (OTC) | 0.87 | Low elasticity - therapeutic need |

### 2.4 β Coefficient Priors

Per channel scaling формула:

```
β_c_prior_mean = (proxy_β_c_post_mean / proxy_baseline_avg) × recipient_baseline_avg × similarity_factor

similarity_factor = {
    "High": 1.0,    # no shrinkage
    "Medium": 0.85, # 15% shrinkage toward 0
    "Low": 0.70,    # 30% shrinkage
}

σ_β_prior = β_c_prior_mean × (CV_proxy + similarity_inflation_addon)

CV_proxy = proxy_β_c_post_std / proxy_β_c_post_mean

similarity_inflation_addon = {
    "High": 0.0,
    "Medium": 0.15,
    "Low": 0.30,
}
```

**Why scaling through baseline ratio:**
- Captures relative channel effectiveness (proxy_β / proxy_baseline) - normalized к brand size
- Recipient β scales к his market context: relative effectiveness × recipient size
- Similarity factor shrinks magnitude toward 0 для weaker matches (proxy effectiveness не fully transferable)

### 2.5 Variance Decomposition

При forecast generation, total variance = sum of independent sources (MATH_REFERENCE Section 7):

```
σ²_total = σ²_proxy + σ²_transfer + σ²_anchor + σ²_sampling

σ²_proxy: from proxy model posterior (inherent uncertainty в proxy fit)
σ²_transfer: shape transfer uncertainty (similarity-dependent inflation)
σ²_anchor: anchor uncertainty (Section 3.4)
σ²_sampling: MCMC sampling noise (target ESS >= 4000 → small)
```

Each source separately reported в Methodology Certificate.

---

## 3. Anchor Quality Rules

### 3.1 Mandatory Anchors (block if missing)

Per `RECIPIENT_ANCHORS.md` Section 1.1-1.5:

- `market_size_rub` - required, no default
- `planned_share_pct` - required
- `distribution_target_pct` + `distribution_ramp_weeks` - both required
- `sov_planned_pct` - required
- `pricing_index_vs_proxy` - required
- `launch_date` - required
- `media_plan` (>=1 item) - required
- `category_trend` - required

If any missing → `ProxyDataValidator` blocks forecast generation, prompts user to complete.

### 3.2 Recommended Anchors (defaults if missing + warn)

| Field | Default if missing | Warning |
|---|---|---|
| `creative_quality_benchmark` | 1.0 (assume average creative) | "Без pre-test данных Aurora использует average creative quality. Если ваш креатив выше/ниже average - forecast accuracy уменьшается." |
| `target_kpi_sales` | None (no reality check) | (no warning - просто skip reality check) |
| `competitive_response_assumption` | "moderate_increase" | "Aurora assumes moderate competitive response. Если ваши конкуренты passive или aggressive - укажите в anchors для refinement." |
| `top3_competitors` | None | (no warning) |
| `category_consolidation` | None (auto-infer from proxy) | (no warning) |
| `seasonal_pattern` | None (auto-detect from proxy seasonality) | (no warning) |

### 3.3 Anchor Uncertainty Propagation

Каждый anchor имеет inherent uncertainty (point estimate сам неточен):

```python
ANCHOR_UNCERTAINTY = {
    "market_size_rub": 0.10,         # ±10% (typical syndicated data error)
    "planned_share_pct": 0.25,        # ±25% (это план, не certainty)
    "distribution_target_pct": 0.15,  # ±15%
    "distribution_ramp_weeks": 0.20,  # ±20% (timing variance)
    "pricing_index_vs_proxy": 0.05,   # ±5%
    "creative_quality_benchmark": 0.20,  # ±20% (если есть pre-test)
}
```

Эти uncertainties propagate в σ²_anchor через variance formula:

```
σ²_anchor = (∂baseline/∂market_size)² × var(market_size) +
            (∂baseline/∂share)² × var(share) +
            (∂baseline/∂distribution)² × var(distribution) +
            (∂baseline/∂pricing)² × var(pricing)
```

Computed numerically через automatic differentiation (JAX) or finite differences during posterior generation.

### 3.4 Anchor Completeness Score

```python
def anchor_completeness_score(anchors: RecipientAnchorsV1) -> float:
    """0-1 score, higher = more recommended fields filled."""
    recommended_fields = [
        "creative_quality_benchmark",
        "target_kpi_sales",
        "competitive_response_assumption",
        "top3_competitors",
        "category_consolidation",
        "seasonal_pattern",
    ]
    filled = sum(1 for f in recommended_fields if getattr(anchors, f, None) is not None)
    return filled / len(recommended_fields)
```

Used in:
- Tier badge calculation (combined с similarity verdict + anchor score)
- Methodology Certificate (transparency: "anchor completeness 67%")

### 3.5 Sanity Cross-Checks

Before transfer, validate anchors против proxy data:

1. **Market size sanity:** anchor.market_size_rub vs proxy DSM total category sales × 12. If anchor > 3× или < 0.3× proxy implied → warning "anchor market size диссонирует с proxy data".

2. **Pricing sanity:** anchor.pricing_index_vs_proxy vs computed (recipient pricing inferred / proxy pricing). If anchor self-reported но contradicts price ratio → warning.

3. **Trend consistency:** anchor.category_trend vs proxy long-term slope. Mismatch → log warning, не block.

---

## 4. Cross-Category Transfer Matrix

Per SIMILARITY_FRAMEWORK Section 1.1 + 2.1.

### 4.1 Transfer Permission Matrix

| Match level | Similarity contribution (D1) | Transfer behavior |
|---|---|---|
| **L3 exact** (chips → chips) | 1.0 | Full transfer all 5 shape parameters |
| **L2 match** (chips → crackers, both snacks_savoury) | 0.7 | Full transfer all 5 shape parameters |
| **L1 match** (snacks → dairy, both FMCG_food) | 0.5 | Full transfer adstock + hill (per channel structurally similar). Seasonality + trend skipped (use category-specific defaults). |
| **Adjacent L1** (FMCG_food → FMCG_beverage) | 0.2 | Limited transfer: только adstock decay (per channel). Hill shape, seasonality, trend - NOT transferred (category prior fallback). +50% extra inflation на transferred parameters. |
| **Cross L1** (FMCG → pharma) | 0.0 | Forecast BLOCKED at similarity verdict layer (Insufficient). |

### 4.2 Adjacent L1 Pairs (curated)

```python
ADJACENT_L1_PAIRS = {
    ("FMCG_food", "FMCG_beverage"),       # similar consumer behavior + retail channels
    ("OTC_pharma", "OTC_supplements"),     # similar regulation + pharmacy channel
    ("Cosmetics", "Personal_care"),         # overlapping channels + audiences
    ("Telecom", "Banking_retail"),          # subscription consumer services
    ("FMCG_food", "FMCG_household"),        # FMCG retail dynamics
    ("Cosmetics", "FMCG_personal_care"),    # cross-overs (skincare ↔ shower gels)
}
```

Maintained в `engines/category_taxonomy.yaml`. Quarterly review.

### 4.3 Cross-Category Penalty Multipliers

Para Adjacent L1 transfers, transfer-side inflation factor multiplied by **1.5×**:

```python
def transfer_inflation_factor(verdict: str, is_cross_category: bool) -> float:
    base = {
        "High": 1.2,
        "Medium": 1.5,
        "Low": 2.0,
    }[verdict]
    if is_cross_category:
        return base * 1.5  # extra inflation для cross-category
    return base
```

Cross-category trigger: D1 (category dimension) score <= 0.2.

### 4.4 Category Prior Fallback

When seasonality / trend NOT transferred (L1 match или adjacent L1) - используем categorical Aurora-curated priors:

```yaml
# engines/category_priors.yaml
FMCG_food:
  seasonality_prior:
    summer_lift: 0.10  # ±10% summer
    winter_lift: -0.05
    weekly_cv: 0.08
  trend_prior:
    growth_rate_yoy: 0.02   # +2% category growth typical
    growth_rate_std: 0.05

OTC_pharma:
  seasonality_prior:
    summer_lift: -0.10  # cold/flu - winter-driven
    winter_lift: 0.30
    weekly_cv: 0.15
  trend_prior:
    growth_rate_yoy: 0.04
    growth_rate_std: 0.06

# ... maintained per L1 category
```

Used as priors в Bayesian model when transfer-derived priors absent.

---

## 5. Workflow: Pre-Train + Transfer (Locked в ADR-003)

### 5.1 Three-Step Workflow

**Step 1: Train Proxy MMM (standalone)**

```python
# engines/single_proxy_transfer.py (Sprint B3)

def train_proxy_model(
    proxy_data: ProxyData,  # DSM + Mediascope
    category: str,
) -> TrainedProxyModel:
    """Train Bayesian MMM на proxy data."""
    # Reuse Aurora Econometrica modeler.py
    from aurora_platform_core.modeler import train_mmm

    # Apply category-specific defaults to free parameters
    config = build_mmm_config(category=category)

    model = train_mmm(
        sales=proxy_data.sales,
        media=proxy_data.media,
        controls=proxy_data.controls,
        config=config,
    )
    return model
```

**Step 2: Extract Structural Priors**

```python
# engines/launch_adapt.py

def extract_proxy_priors(model: TrainedProxyModel) -> ProxyPriors:
    """Extract 5 shape parameters + uncertainty bounds."""
    posterior = model.get_posterior()

    return ProxyPriors(
        adstock_decay_per_channel={
            channel: PriorSpec(
                mean=posterior[f"lambda_{channel}"].mean(),
                std=posterior[f"lambda_{channel}"].std(),
            )
            for channel in model.channels
        },
        hill_shape_per_channel={
            channel: PriorSpec(
                gamma_mean=posterior[f"gamma_{channel}"].mean(),
                gamma_std=posterior[f"gamma_{channel}"].std(),
                k_mean=posterior[f"k_{channel}"].mean(),
                k_std=posterior[f"k_{channel}"].std(),
            )
            for channel in model.channels
        },
        category_seasonality=SeasonalityPrior(
            weekly_pattern=posterior["seasonality"].mean(axis=0),
            weekly_std=posterior["seasonality"].std(axis=0),
        ),
        long_term_trend=TrendPrior(
            slope_mean=posterior["trend_slope"].mean(),
            slope_std=posterior["trend_slope"].std(),
        ),
        proxy_baseline_avg=posterior["baseline"].mean(),
        proxy_betas={
            channel: PriorSpec(
                mean=posterior[f"beta_{channel}"].mean(),
                std=posterior[f"beta_{channel}"].std(),
            )
            for channel in model.channels
        },
        proxy_metadata=ProxyBrandMetadata(
            brand_name=model.brand_name,
            category=model.category,
            similarity_aggregate=...,  # filled by similarity_calculator
            confidence_verdict=...,
        ),
    )
```

**Step 3: Apply Recipient Magnitudes + Train Recipient Model**

```python
# engines/launch_adapt.py

def apply_recipient_magnitudes(
    priors: ProxyPriors,
    anchors: RecipientAnchorsV1,
    category_match_level: Literal["L3", "L2", "L1", "adjacent_L1"],
    similarity_verdict: Literal["High", "Medium", "Low"],
) -> RecipientPriors:
    """Calibrate magnitudes from anchors. Apply category-aware transfer rules."""

    # 1. Compute recipient baseline trajectory
    seasonality = (
        priors.category_seasonality
        if category_match_level in ("L3", "L2")
        else load_category_prior(anchors.category).seasonality
    )

    pricing_factor_value = pricing_factor(
        anchors.pricing_index_vs_proxy,
        elasticity_for_category(anchors.category),
    )

    recipient_baseline_trajectory = compute_baseline_trajectory(
        market_size=anchors.market_size_rub,
        planned_share_pct=anchors.planned_share_pct,
        distribution_target_pct=anchors.distribution_target_pct,
        ramp_weeks=anchors.distribution_ramp_weeks,
        seasonality=seasonality,
        pricing_factor=pricing_factor_value,
    )

    recipient_baseline_avg = recipient_baseline_trajectory.mean()

    # 2. Scale β coefficients
    similarity_factor = {"High": 1.0, "Medium": 0.85, "Low": 0.70}[similarity_verdict]
    inflation_addon = {"High": 0.0, "Medium": 0.15, "Low": 0.30}[similarity_verdict]
    cross_cat_multi = 1.5 if category_match_level == "adjacent_L1" else 1.0

    recipient_betas = {}
    for channel, proxy_beta in priors.proxy_betas.items():
        scale_factor = recipient_baseline_avg / priors.proxy_baseline_avg
        beta_mean = proxy_beta.mean * scale_factor * similarity_factor
        cv_proxy = proxy_beta.std / abs(proxy_beta.mean) if proxy_beta.mean != 0 else 1.0
        beta_std = abs(beta_mean) * (cv_proxy + inflation_addon) * cross_cat_multi
        recipient_betas[channel] = PriorSpec(mean=beta_mean, std=beta_std)

    # 3. Adstock + Hill priors с inflation
    inflation = transfer_inflation_factor(similarity_verdict, category_match_level == "adjacent_L1")
    recipient_adstock = {
        c: PriorSpec(mean=p.mean, std=p.std * inflation)
        for c, p in priors.adstock_decay_per_channel.items()
    }
    recipient_hill_gamma = {
        c: PriorSpec(mean=p.gamma_mean, std=p.gamma_std * inflation)
        for c, p in priors.hill_shape_per_channel.items()
    }
    recipient_hill_k = {
        c: PriorSpec(mean=p.k_mean, std=p.k_std * inflation)
        for c, p in priors.hill_shape_per_channel.items()
    }

    # 4. L1 match → seasonality / trend not transferred
    if category_match_level == "L1":
        recipient_seasonality = load_category_prior(anchors.category).seasonality
        recipient_trend = load_category_prior(anchors.category).trend
    elif category_match_level == "adjacent_L1":
        recipient_seasonality = load_category_prior(anchors.category).seasonality  # not transferred
        recipient_trend = load_category_prior(anchors.category).trend
    else:  # L2 or L3
        recipient_seasonality = SeasonalityPrior(
            weekly_pattern=priors.category_seasonality.weekly_pattern,
            weekly_std=priors.category_seasonality.weekly_std * inflation,
        )
        recipient_trend = TrendPrior(
            slope_mean=priors.long_term_trend.slope_mean,
            slope_std=priors.long_term_trend.slope_std * inflation,
        )

    return RecipientPriors(
        baseline_trajectory=recipient_baseline_trajectory,
        betas=recipient_betas,
        adstock_decay=recipient_adstock,
        hill_gamma=recipient_hill_gamma,
        hill_k=recipient_hill_k,
        seasonality=recipient_seasonality,
        trend=recipient_trend,
        provenance=TransferProvenance(
            proxy_engine_version="single_proxy_transfer/0.1.0",
            transferred_parameters=_list_transferred_params(category_match_level),
            excluded_parameters=_list_excluded_params(category_match_level),
            similarity_aggregate=priors.proxy_metadata.similarity_aggregate,
            transfer_timestamp=datetime.now(),
        ),
    )
```

```python
def _list_transferred_params(level: str) -> list:
    if level in ("L3", "L2"):
        return ["adstock_decay", "hill_shape", "category_seasonality", "long_term_trend"]
    if level == "L1":
        return ["adstock_decay", "hill_shape"]
    if level == "adjacent_L1":
        return ["adstock_decay"]
    return []


def _list_excluded_params(level: str) -> list:
    all_params = {"adstock_decay", "hill_shape", "category_seasonality", "long_term_trend"}
    transferred = set(_list_transferred_params(level))
    return sorted(all_params - transferred) + ["beta_magnitude", "baseline"]
```

### 5.2 Train Recipient Model

```python
def train_recipient_model(
    recipient_priors: RecipientPriors,
    recipient_data: Optional[RecipientData],  # None для pre-launch
    anchors: RecipientAnchorsV1,
) -> TrainedRecipientModel:
    """Train recipient MMM с transferred priors. Pre-launch = priors-only forecast."""
    if recipient_data is None or len(recipient_data.weeks) < 4:
        # Pre-launch: priors-only sampling (posterior == prior до first observation)
        return generate_priors_only_forecast(recipient_priors, anchors)

    # Post-launch: re-fit с recipient data + posterior update workflow
    # (Sprint B5 - launch_posterior_update.py)
    from aurora_platform_core.modeler import train_mmm_with_priors

    return train_mmm_with_priors(
        sales=recipient_data.sales,
        media=recipient_data.media,
        priors=recipient_priors,
        proxy_weight=compute_proxy_weight(len(recipient_data.weeks)),  # ESS-based
    )
```

### 5.3 No Joint Training (Phase D Consideration)

См. ADR-003 "Pre-train + Transfer vs Joint Training" - locked **pre-train + transfer** для Phase B. Joint Bayesian:
- Phase D consideration if customer demand
- Reasoning: Phase B simplicity + 100% reuse Econometrica engines (P9) + zero recipient data случай (joint = просто proxy fit) + posterior update (Sprint B5) - hands-on partial pooling вместо full joint.

---

## 6. Paused Brand Integration

Для use case 2 (paused brand с organic baseline DSM history):

### 6.1 Paused Brand Detection

`anchors.is_paused_brand=true` + `pause_duration_months >= 6` (audit fix F48: minimum 6 months).

### 6.2 Organic Baseline Integration

```python
def compute_paused_brand_baseline(
    anchors: RecipientAnchorsV1,
    recipient_history: PausedBrandHistory,  # DSM organic sales pre-launch
    formula_baseline_trajectory: np.ndarray,  # from Section 2.1 formula
) -> np.ndarray:
    """Combine formula-derived + organic-observed baseline для paused brand."""
    organic_yearly = recipient_history.average_yearly_sales

    # Decay applied для long pauses
    pause_months = anchors.pause_duration_months
    if pause_months <= 12:
        organic_weight = 0.7  # recent organic is reliable
    elif pause_months <= 24:
        organic_weight = 0.4
    else:
        organic_weight = 0.2  # very old organic data

    organic_baseline_per_week = (organic_yearly / 52)

    formula_weight = 1.0 - organic_weight

    combined_baseline = (
        organic_weight * organic_baseline_per_week +
        formula_weight * formula_baseline_trajectory
    )

    return combined_baseline
```

### 6.3 Paused Brand σ_anchor Adjustment

Organic data adds anchor uncertainty reduction:

```python
def paused_brand_sigma_anchor(
    base_sigma_anchor: float,
    has_organic: bool,
    organic_quality_index: float,  # data completeness 0-1
) -> float:
    if not has_organic:
        return base_sigma_anchor
    reduction_factor = 1.0 - 0.4 * organic_quality_index  # up to 40% reduction
    return base_sigma_anchor * reduction_factor
```

---

## 7. Sensitivity Tests (Sprint B5)

`tests/integration/test_adaptation_sensitivity.py`:

### 7.1 Synthetic Data Tests

```python
def test_high_similarity_yields_low_mape():
    """High verdict → MAPE < 15% on synthetic recipient."""
    proxy = generate_synthetic_proxy(category="FMCG_food.snacks_savoury.chips")
    recipient = derive_synthetic_recipient(proxy, similarity_target=0.90)

    proxy_model = train_proxy_model(proxy.data, proxy.category)
    proxy_priors = extract_proxy_priors(proxy_model)
    recipient_priors = apply_recipient_magnitudes(
        proxy_priors, recipient.anchors,
        category_match_level="L3", similarity_verdict="High"
    )
    forecast = generate_priors_only_forecast(recipient_priors, recipient.anchors)
    mape = compute_mape(forecast.mean, recipient.true_values)
    assert mape < 0.15


def test_anchor_uncertainty_propagated():
    """σ²_anchor non-zero, scales с anchor missing-fields."""
    proxy_priors = mock_proxy_priors()
    high_quality_anchors = mock_complete_anchors()
    low_quality_anchors = mock_minimum_anchors()  # only mandatory fields

    high_priors = apply_recipient_magnitudes(proxy_priors, high_quality_anchors, ...)
    low_priors = apply_recipient_magnitudes(proxy_priors, low_quality_anchors, ...)

    high_forecast = generate_forecast(high_priors)
    low_forecast = generate_forecast(low_priors)

    assert low_forecast.sigma_anchor > high_forecast.sigma_anchor


def test_pricing_factor_categories():
    """Different category elasticities yield different pricing factors."""
    pf_fmcg = pricing_factor(0.7, PRICING_ELASTICITIES["FMCG_food.snacks_savoury"])
    pf_pharma = pricing_factor(0.7, PRICING_ELASTICITIES["OTC_pharma.*"])
    # FMCG more elastic - bigger volume boost
    assert pf_fmcg > pf_pharma
    assert 1.15 < pf_fmcg < 1.40  # ~30% boost для impulse FMCG
    assert 1.0 < pf_pharma < 1.10  # <10% boost для OTC


def test_cross_category_blocks():
    """Cross L1 (FMCG → pharma) yields Insufficient verdict."""
    fmcg_proxy = generate_synthetic_proxy(category="FMCG_food.snacks_savoury.chips")
    pharma_recipient_anchors = mock_anchors(category="OTC_pharma.cold_flu.antiviral")
    similarity = compute_similarity(fmcg_proxy.profile, pharma_recipient_anchors_to_profile(pharma_recipient_anchors))
    assert similarity.verdict == "Insufficient"
    # Forecast generation blocked at this layer
```

### 7.2 Property-Based Tests

```python
from hypothesis import given, strategies as st

@given(
    pricing_index=st.floats(min_value=0.3, max_value=3.0),
    elasticity=st.floats(min_value=0.0, max_value=1.0),
)
def test_pricing_factor_monotonic(pricing_index, elasticity):
    """Lower price → larger pricing factor (more volume)."""
    pf_lower = pricing_factor(pricing_index * 0.9, elasticity)  # 10% cheaper
    pf_base = pricing_factor(pricing_index, elasticity)
    if elasticity > 0.01:
        assert pf_lower >= pf_base  # cheaper = more volume


@given(
    similarity=st.floats(min_value=0.5, max_value=1.0),
)
def test_inflation_decreases_with_similarity(similarity):
    """Higher similarity = lower inflation."""
    verdict = "High" if similarity >= 0.85 else "Medium" if similarity >= 0.65 else "Low"
    inflation = transfer_inflation_factor(verdict, is_cross_category=False)
    if verdict == "High":
        assert inflation == 1.2
    elif verdict == "Medium":
        assert inflation == 1.5
    elif verdict == "Low":
        assert inflation == 2.0
```

### 7.3 Pilot Validation (Sprint B6)

При pilot live-test (Materia Medica или FMCG launch team):
- Record actual results vs forecast после 12 нед launch
- Compare CI coverage (95% CI должен покрывать actuals в 95% случаев)
- Если consistent under-coverage - adaptation rules need recalibration (e.g., inflation factors too low)

---

## 8. Edge Cases

### 8.1 Pricing Index = 1.0 Exact

`pricing_factor = 1.0`, no adjustment needed. Default behavior trivially correct.

### 8.2 Pricing Index Extreme (< 0.5 или > 2.0)

SemanticValidator уже warns пользователя. Adaptation все equally applies, но additional inflation:

```python
if pricing_index < 0.5 or pricing_index > 2.0:
    inflation_addon += 0.15  # +15% extra inflation для extreme pricing
```

### 8.3 Recipient Category Not in Taxonomy

Fallback: similarity D1 = 0 (cross), forecast blocked at similarity layer. User prompted to suggest category addition.

### 8.4 Proxy with Single Channel

If proxy media model имеет только 1 channel (e.g., TV-only) - recipient transfer работает per-channel, recipient inherits prior для same channel. Other channels в recipient media plan get **category prior priors** (not from this proxy).

```python
def merge_priors_for_missing_channels(
    transferred_priors: dict[str, PriorSpec],
    recipient_channels: list[str],
    category_priors: dict[str, PriorSpec],
) -> dict[str, PriorSpec]:
    """For channels in recipient но не в proxy - use category prior."""
    result = {}
    for ch in recipient_channels:
        if ch in transferred_priors:
            result[ch] = transferred_priors[ch]
        else:
            result[ch] = category_priors.get(ch, default_channel_prior(ch))
    return result
```

### 8.5 Multi-Proxy Mode

При multi-proxy (S007) - extract priors из each proxy, hierarchical Bayesian model combines them с pooling weights (см. `multi_proxy_hierarchical.py` Sprint B3).

```python
def extract_multi_proxy_priors(
    proxy_models: List[TrainedProxyModel],
    pooling_weights: List[float],
) -> MultiProxyPriors:
    """Extract structural priors from N proxies for hierarchical training."""
    return MultiProxyPriors(
        per_proxy=[extract_proxy_priors(m) for m in proxy_models],
        pooling_weights=pooling_weights,
    )
```

Multi-proxy adaptation logic в `multi_proxy_hierarchical.py` - this document covers single-proxy transfer.

### 8.6 Posterior Update (Re-fit с recipient data)

Sprint B5 separate doc (POSTERIOR_UPDATE_DESIGN.md из S005b). Adaptation rules здесь применяются для **initial** transfer (pre-launch + first weeks). Posterior update modifies proxy weight через ESS-based schedule, не re-applies adaptation rules.

---

## 9. Worked Examples

### 9.1 Example: Launch новый OTC antiviral на основе Кагоцел

**Recipient anchors:**
```yaml
market_size_rub: 5_000_000_000  # 5B
planned_share_pct: 3.0
distribution_target_pct: 60.0
distribution_ramp_weeks: 12
sov_planned_pct: 5.0
pricing_index_vs_proxy: 1.4  # premium 40% over Кагоцел
launch_date: 2026-09-01
category: OTC_pharma.cold_flu.antiviral  # L3 match с Кагоцел
category_trend: stable
creative_quality_benchmark: 0.85  # above-average pre-test
competitive_response_assumption: moderate_increase
```

**Proxy:** Кагоцел trained model.
**Similarity:** verdict Medium (S=0.70).
**Category match level:** L3 exact.

**Step 1: Extract proxy priors:**
- adstock per channel: TV λ=0.55±0.08, digital λ=0.25±0.05
- hill γ_TV=2.1±0.3, k_TV=normalized 0.8±0.15
- seasonality 52-vector (winter peak +25%, summer -8%)
- trend slope -0.005/week (slight decline в Кагоцел category)
- proxy baseline avg 8.5M ₽/week
- proxy β_TV mean=2.3M, std=0.5M

**Step 2: Magnitude calibration:**
- pricing_factor = (1/1.4)^0.2 = 0.93 (OTC elasticity 0.2)
- recipient baseline avg trajectory peak = 5B × seasonality(week=peak) × ramp(planned_share) × ramp(distribution) × pricing_factor

  At week 26 (mid-launch, distribution ramped):
  - planned_share(26) = 0.03 × 26/12 = capped at 0.03
  - distribution(26) = 0.60 × capped at 0.60
  - seasonality(week 26) = ~1.05 (autumn slight lift)
  - baseline = 5B × 1.05 × 0.03 × 0.60 × 0.93 = 87.8M ₽/week

  recipient_baseline_avg ≈ 75M ₽/week (yearly average post-ramp)

- β_TV scaling: similarity_factor=0.85 (Medium), CV_proxy=0.5/2.3=0.22, inflation_addon=0.15
  - β_TV_mean = (2.3M / 8.5M) × 75M × 0.85 = 17.2M
  - β_TV_std = 17.2M × (0.22 + 0.15) × 1.0 = 6.4M (38% CV - reasonable для Medium)

**Step 3: Adstock + Hill priors с inflation 1.5×:**
- TV λ prior: mean 0.55, std 0.08 × 1.5 = 0.12
- TV γ prior: mean 2.1, std 0.3 × 1.5 = 0.45

**Step 4: Seasonality + trend transferred (L3 match):**
- seasonality 52-vector with std × 1.5 inflation
- trend slope -0.005, std × 1.5

### 9.2 Example: Launch premium snack из FMCG_food L1 cousin

**Recipient anchors:**
```yaml
market_size_rub: 3_000_000_000
planned_share_pct: 2.0
distribution_target_pct: 35.0
distribution_ramp_weeks: 16
sov_planned_pct: 4.0
pricing_index_vs_proxy: 1.8  # premium snack
launch_date: 2026-10-01
category: FMCG_food.snacks_sweet.chocolate_bars  # L2 match с recipient (L3 differs)
category_trend: growing
```

**Proxy:** Lay's Premium chips trained model.
**Category match level:** L2 (snacks_sweet vs snacks_savoury - different L3, same L2 only if taxonomy considers them L2 siblings).

Wait, проверим: Lay's = snacks_savoury.chips, recipient = snacks_sweet.chocolate_bars. L2 differ (snacks_savoury vs snacks_sweet). L1 match (FMCG_food).

**Match level: L1.** Transfer adstock + hill (per channel similar in FMCG retail). Seasonality + trend NOT transferred (snacks_sweet has different seasonality - chocolate has Easter peak, summer lift; chips - more uniform).

**Adaptation:**
- adstock + hill from proxy с 1.5× inflation
- seasonality from category_priors.yaml для FMCG_food.snacks_sweet
- trend from category_priors.yaml
- pricing_factor = (1/1.8)^0.7 = 0.66 (FMCG impulse elasticity 0.7)

### 9.3 Example: Cross-category blocked (FMCG → B2B SaaS)

**Recipient anchors:** B2B SaaS productivity tool.
**Proxy:** Lay's chips.

**Similarity:** D1 score = 0.0 (cross L1 non-adjacent). Aggregate similarity ~0.20 → Insufficient verdict.

**Result:** forecast generation blocked at similarity layer. UI shows recommendation: "Find proxy в B2B.B2B_software." Adaptation rules не invoked.

---

## 10. Connection to Other Layers

### 10.1 Similarity Framework (S003)

`compute_similarity()` returns verdict + category_match_level. Adaptation rules используют это для determine inflation factors + transfer permissions.

### 10.2 Posterior Update (S005b)

Initial adaptation runs Sprint B3. Posterior update Sprint B5 modifies proxy weight по ESS schedule, не re-runs adaptation. Adaptation provides starting prior; posterior update adjusts how much weight это prior получает по мере recipient data accumulation.

### 10.3 Conformal Prediction (Sprint B5)

Adapted conformal CI (MATH_REFERENCE Section 5) использует similarity-based inflation factors из transfer scenario.

### 10.4 Storage (ADR-002)

Transfer provenance + recipient priors stored в `.aurora` bundle:
- `transfer_provenance.json` - что именно перенесено
- `models/recipient_model.pickle` - trained recipient model с priors used

---

## 11. Implementation Files (Sprint B3)

**Backend:**
- `engines/launch_adapt.py` - extract_proxy_priors + apply_recipient_magnitudes + linear_ramp + pricing_factor
- `engines/single_proxy_transfer.py` - workflow orchestrator (proxy training → priors → recipient training)
- `engines/category_priors.yaml` - category priors для seasonality/trend fallback
- `engines/category_taxonomy.yaml` - L1/L2/L3 hierarchy + adjacent L1 pairs (already needed для S003)

**Tests:**
- `tests/unit/test_launch_adapt.py` - extract_proxy_priors + apply_recipient_magnitudes unit tests
- `tests/integration/test_adaptation_sensitivity.py` - synthetic + property-based (Section 7)
- `tests/integration/test_paused_brand_integration.py` - organic baseline integration

**API:**
- `/launch/v1/adapt` - run adaptation (existing endpoint в DATA_REQUIREMENTS Section 7.2)
- `/launch/v1/validate_transfer` - prior predictive checks Sprint B3

---

## 12. Связанные документы

- `decisions/ADR-003-pretrain-vs-joint-training.md` - workflow choice authority
- `decisions/ADR-002-storage-layer.md` - где хранится transfer_provenance + recipient model
- `MATH_REFERENCE.md` Section 1, 2, 3, 8 - canonical formulas (adstock, hill, transfer, magnitude calibration)
- `../00_Overview/PRINCIPLES.md` P3 - адаптация переносит shape, не magnitude
- `../02_Data_Spec/SIMILARITY_FRAMEWORK.md` - similarity verdict, category match levels, weight profiles
- `../02_Data_Spec/RECIPIENT_ANCHORS.md` - anchor field reference
- `../02_Data_Spec/DATA_REQUIREMENTS.md` Section 4 - validators
- `REUSE_FROM_ECONOMETRICA.md` Section 1.1 - shared engines (modeler.py reuse)
- `../05_Sessions/SESSION_NEXT_QUESTIONS.md` S004 closed reference
