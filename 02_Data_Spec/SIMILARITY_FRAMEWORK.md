# Aurora Launch - Similarity Framework

**Status:** Accepted (S003 closed 2026-05-04)
**Authority:** P2 в `00_Overview/PRINCIPLES.md` + Section 6 `MATH_REFERENCE.md`
**Sprint context:** Sprint B2 implementation reference
**Owner:** Маша (math design) + Антон (domain validation)

## Контекст

P2 декларирует similarity по 6+ measurements. Этот документ финализирует:
1. Точные categorical structures для каждой dimension (tier definitions)
2. Per-dimension scoring rules (how to compute s_d ∈ [0, 1])
3. Default + category-specific weight profiles (asymmetric)
4. Aggregate similarity formula
5. Verdict thresholds (High/Medium/Low/Insufficient)
6. Multi-proxy aggregation logic
7. Calibration approach (synthetic transfers + iterative pilot refinement)

Sprint B2 implements `engines/similarity_calculator.py` (Python backend) + Rust → WASM module (UI real-time) per этот документ.

---

## 1. Six Dimensions (Definitions)

### 1.1 D1: Category & Sub-category

**Three-level taxonomic structure:**

- **L1 (Major category)** - макрокатегория продукта
- **L2 (Sub-category)** - функциональная sub-категория
- **L3 (Granular sub)** - product type / форма / variant

**Examples:**

| L1 | L2 | L3 |
|---|---|---|
| FMCG_food | snacks_savoury | chips |
| FMCG_food | snacks_savoury | crackers |
| FMCG_food | snacks_sweet | chocolate_bars |
| FMCG_food | dairy_yogurt | yogurt_drinking |
| FMCG_food | dairy_milk | milk_uht |
| FMCG_beverage | beverage_carbonated | cola_regular |
| FMCG_beverage | beverage_juice | juice_100pct |
| FMCG_beverage | beverage_energy | energy_caffeine |
| OTC_pharma | OTC_cold_flu | OTC_antiviral |
| OTC_pharma | OTC_pain | OTC_analgesic |
| Rx_pharma | Rx_cardio | Rx_antihypertensive |
| Cosmetics | cosmetics_skincare | skincare_premium_face |
| Cosmetics | cosmetics_haircare | haircare_premium_shampoo |
| Telecom | telecom_mobile | telecom_b2c_mobile |
| Banking | banking_retail | banking_credit_cards |
| B2B | B2B_software | B2B_saas |

**Maintenance:** taxonomy maintained в `engines/category_taxonomy.yaml`. Updates - quarterly review. New categories added when first project в категории launches.

### 1.2 D2: Pricing Tier

**Four tiers (ordered):**

1. **ECONOMY** - private label + value brands (price index 0.5-0.85 vs category mean)
2. **MAINSTREAM** - middle market national brands (price index 0.85-1.20)
3. **PREMIUM** - premium positioning (price index 1.20-2.00)
4. **LUXURY** - super-premium / luxury (price index >2.00)

**How to determine tier:**
- DSM Group `price_shelf_avg` ÷ category median price
- Index из range:
  - <0.85 → ECONOMY
  - 0.85-1.20 → MAINSTREAM
  - 1.20-2.00 → PREMIUM
  - >2.00 → LUXURY

### 1.3 D3: Brand Size

**Three tiers:**

1. **LEADER** - top 3 в категории по market share (или top 1 для small categories)
2. **CHALLENGER** - rank 4-10 по share, gaining or stable
3. **NICHE** - rank 11+, specialty positioning или small share

**How to determine:**
- DSM Group share rank в L2 sub-category за last 12 months average

### 1.4 D4: Distribution

**Three tiers:**

1. **NATIONAL** - распространён в большинстве регионов (weighted distribution >=70% за last 6 mo average)
2. **REGIONAL** - концентрация в нескольких регионах (40-70%)
3. **NICHE** - специализированные каналы или малая распространённость (<40%)

**How to determine:**
- DSM Group `distribution_weighted_pct` last 6-month average

### 1.5 D5: Media Maturity

**Four tiers (media activity pattern):**

1. **ALWAYS-ON** - continuous TV/digital presence year-round (>=80% weeks have media activity)
2. **PULSING** - regular bursts (4-12 campaigns per year, gaps между активностью)
3. **PROMO-DRIVEN** - media tied к promo cycles (preorder + sale events)
4. **DORMANT** - minimal или no media activity last 6+ months

**How to determine:**
- Mediascope TV + Digital data: % weeks с budget>0 за last 24 months
  - >=80% → ALWAYS-ON
  - 40-80% → PULSING
  - <40% и promo-correlated → PROMO-DRIVEN
  - <20% или paused → DORMANT

### 1.6 D6: Lifecycle Stage

**Four tiers:**

1. **NEW** - <2 years на рынке, fast-growing
2. **GROWING** - 2-5 years, stable growth, gaining share
3. **MATURE** - >5 years, stable share, established
4. **DECLINING** - losing share, end-of-life signals

**How to determine:**
- DSM Group rolling 12-month sales trend slope:
  - Positive >5% YoY и age <2y → NEW
  - Positive 2-5% YoY и age 2-5y → GROWING
  - Stable ±2% YoY → MATURE
  - Negative >2% YoY → DECLINING

---

## 2. Per-Dimension Scoring Rules

Each dimension produces s_d ∈ [0, 1]. Tier-distance-based scoring.

### 2.1 D1: Category Scoring

```python
def score_category(proxy: CategorySpec, recipient: CategorySpec) -> float:
    """Score category similarity на 3-level taxonomy."""
    # L3 exact match
    if proxy.l3 == recipient.l3:
        return 1.0
    # L2 match, different L3
    if proxy.l2 == recipient.l2:
        return 0.7
    # L1 match, different L2
    if proxy.l1 == recipient.l1:
        return 0.5
    # Adjacent L1 (e.g., FMCG_food vs FMCG_beverage)
    if are_adjacent_l1(proxy.l1, recipient.l1):
        return 0.2
    # Cross L1
    return 0.0


# Adjacency для L1 categories - SOURCE OF TRUTH: engines/category_taxonomy.yaml
# Loaded at runtime, NOT duplicated в коде. Quarterly review by Антон + Маша.

def load_adjacent_l1_pairs() -> set[tuple[str, str]]:
    """Load adjacent L1 pairs from category_taxonomy.yaml (SSoT)."""
    import yaml
    from pathlib import Path
    taxonomy_path = Path(__file__).parent.parent / "engines" / "category_taxonomy.yaml"
    with open(taxonomy_path, encoding="utf-8") as f:
        taxonomy = yaml.safe_load(f)
    return {tuple(sorted(pair)) for pair in taxonomy.get("adjacent_l1_pairs", [])}


def are_adjacent_l1(l1_a: str, l1_b: str) -> bool:
    pairs = load_adjacent_l1_pairs()  # cached в production через @lru_cache
    return tuple(sorted([l1_a, l1_b])) in pairs


# Reference content of category_taxonomy.yaml `adjacent_l1_pairs` (for documentation):
# - [FMCG_food, FMCG_beverage]
# - [FMCG_food, FMCG_household]
# - [OTC_pharma, OTC_supplements]
# - [Cosmetics, Personal_care]
# - [Cosmetics, FMCG_personal_care]
# - [Telecom, Banking_retail]
# (Maintained в taxonomy.yaml, не в этом документе - prevents drift)
```

**Edge case:** new sub-category not in taxonomy - default L2/L3 to "unknown_<name>", score against parent L1 only.

### 2.2 D2: Pricing Tier Scoring

```python
PRICING_TIER_ORDER = ["ECONOMY", "MAINSTREAM", "PREMIUM", "LUXURY"]

def score_pricing_tier(proxy_tier: str, recipient_tier: str) -> float:
    distance = abs(
        PRICING_TIER_ORDER.index(proxy_tier) - PRICING_TIER_ORDER.index(recipient_tier)
    )
    return {0: 1.0, 1: 0.5, 2: 0.2, 3: 0.0}[distance]
```

### 2.3 D3: Brand Size Scoring

```python
SIZE_TIER_ORDER = ["LEADER", "CHALLENGER", "NICHE"]

def score_brand_size(proxy_size: str, recipient_size: str) -> float:
    distance = abs(
        SIZE_TIER_ORDER.index(proxy_size) - SIZE_TIER_ORDER.index(recipient_size)
    )
    return {0: 1.0, 1: 0.6, 2: 0.3}[distance]
```

### 2.4 D4: Distribution Scoring

```python
DIST_TIER_ORDER = ["NATIONAL", "REGIONAL", "NICHE"]

def score_distribution(proxy_dist: str, recipient_dist: str) -> float:
    distance = abs(
        DIST_TIER_ORDER.index(proxy_dist) - DIST_TIER_ORDER.index(recipient_dist)
    )
    return {0: 1.0, 1: 0.5, 2: 0.2}[distance]
```

### 2.5 D5: Media Maturity Scoring

```python
MATURITY_TIER_ORDER = ["ALWAYS-ON", "PULSING", "PROMO-DRIVEN", "DORMANT"]

def score_media_maturity(proxy_mat: str, recipient_mat: str) -> float:
    distance = abs(
        MATURITY_TIER_ORDER.index(proxy_mat) - MATURITY_TIER_ORDER.index(recipient_mat)
    )
    return {0: 1.0, 1: 0.5, 2: 0.2, 3: 0.0}[distance]
```

**Special case:** recipient = NEW BRAND (no media history) → use planned media maturity from anchors `media_plan` instead.

### 2.6 D6: Lifecycle Scoring

```python
LIFECYCLE_TIER_ORDER = ["NEW", "GROWING", "MATURE", "DECLINING"]

def score_lifecycle(proxy_lc: str, recipient_lc: str) -> float:
    distance = abs(
        LIFECYCLE_TIER_ORDER.index(proxy_lc) - LIFECYCLE_TIER_ORDER.index(recipient_lc)
    )
    return {0: 1.0, 1: 0.6, 2: 0.3, 3: 0.0}[distance]
```

**Edge case:** recipient ALWAYS NEW (Aurora Launch is launch product). Best matching proxy lifecycle stage = NEW or GROWING. MATURE/DECLINING proxies get 0.6/0.3.

---

## 3. Weight Profiles (Default + Category-Specific)

### 3.1 Default Profile (general)

```python
DEFAULT_WEIGHTS = {
    "category_subcategory": 0.30,
    "pricing_tier": 0.20,
    "media_maturity": 0.15,
    "brand_size": 0.15,
    "distribution": 0.10,
    "lifecycle_stage": 0.10,
}
# Sum = 1.00
```

**Rationale:**
- **Category 0.30** - drives adstock decay class (impulse vs long-cycle), seasonality, hill saturation shape, channel mix relevance. Most critical для shape transfer.
- **Pricing 0.20** - drives volume/elasticity relationship, channel preference (premium → less TV more digital), audience demo. Important но не critical как category.
- **Media maturity 0.15** - drives adstock decay magnitude (always-on → lower decay because constant baseline; pulsing → higher response к bursts). Critical для adstock transfer.
- **Brand size 0.15** - drives saturation level (large brands ближе к hill plateau), reach efficiency. Affects mostly magnitude (which не переносится anyway), но влияет на shape для high-saturation проксей.
- **Distribution 0.10** - geographic mix, trade-channel media efficiency, local vs federal TV mix. Important для budget allocation, less для shape transfer.
- **Lifecycle 0.10** - hill saturation point + baseline trend. Affects baseline (которая не переносится) больше чем shape.

### 3.2 Category-Specific Profiles (asymmetric)

Categories show different sensitivity к dimensions. Profiles auto-loaded based on recipient L1+L2.

#### OTC Pharma Profile

```python
OTC_PHARMA_WEIGHTS = {
    "category_subcategory": 0.40,  # ATC class match critical
    "pricing_tier": 0.10,           # pharma less price-elastic
    "media_maturity": 0.15,
    "brand_size": 0.15,
    "distribution": 0.10,
    "lifecycle_stage": 0.10,
}
```

**Rationale:** ATC class strongly determines therapeutic effect class, который drives consumer search behavior + channel preference. Pricing menos critical в OTC где insurance не covers - но clearly matters less than therapeutic match.

#### Rx Pharma Profile

```python
RX_PHARMA_WEIGHTS = {
    "category_subcategory": 0.45,  # ATC + Rx restriction critical
    "pricing_tier": 0.05,
    "media_maturity": 0.10,         # Rx media regulated
    "brand_size": 0.15,
    "distribution": 0.10,
    "lifecycle_stage": 0.15,
}
```

**Special note:** Rx restrictions on advertising РФ - media maturity tier almost always PROMO-DRIVEN или DORMANT для Rx. Pricing largely irrelevant в bookkeeping retail.

#### FMCG Impulse (snacks, beverages, candy)

```python
FMCG_IMPULSE_WEIGHTS = {
    "category_subcategory": 0.30,
    "pricing_tier": 0.25,           # tier critical для impulse purchase behavior
    "media_maturity": 0.10,
    "brand_size": 0.15,
    "distribution": 0.10,
    "lifecycle_stage": 0.10,
}
```

**Rationale:** impulse purchases highly price-sensitive. Premium chips vs economy chips имеют different launch dynamics (gross margin permits different media intensity).

#### FMCG Staples (dairy, household, hygiene)

```python
FMCG_STAPLES_WEIGHTS = {
    "category_subcategory": 0.30,
    "pricing_tier": 0.20,
    "media_maturity": 0.15,
    "brand_size": 0.15,
    "distribution": 0.15,           # distribution критично - trip frequency, shopper habit
    "lifecycle_stage": 0.05,
}
```

#### Premium Cosmetics

```python
PREMIUM_COSMETICS_WEIGHTS = {
    "category_subcategory": 0.25,
    "pricing_tier": 0.30,           # luxury tier match very important
    "media_maturity": 0.15,
    "brand_size": 0.10,
    "distribution": 0.10,
    "lifecycle_stage": 0.10,
}
```

**Rationale:** premium positioning drives entire marketing playbook. Luxury vs premium-mass have wildly different ATL/digital mix, creative tone, media timing.

#### Telecom / Banking Retail

```python
TELECOM_BANKING_WEIGHTS = {
    "category_subcategory": 0.30,
    "pricing_tier": 0.10,           # tier less granular в subscription services
    "media_maturity": 0.20,         # always-on critical
    "brand_size": 0.20,             # national vs regional matters
    "distribution": 0.05,           # digital sales dominant, distribution irrelevant
    "lifecycle_stage": 0.15,
}
```

#### B2B Software / SaaS

```python
B2B_WEIGHTS = {
    "category_subcategory": 0.35,
    "pricing_tier": 0.05,           # tier пусть, B2B pricing custom
    "media_maturity": 0.20,
    "brand_size": 0.20,
    "distribution": 0.05,
    "lifecycle_stage": 0.15,
}
```

**Rationale:** B2B media plays largely в LinkedIn, podcasts, conferences - very different mix. Brand size critical (enterprise vs SMB). Lifecycle stage matters because growth-stage SaaS has different unit economics.

### 3.3 Profile Selection Logic

```python
import fnmatch

# Profiles list-of-tuples (NOT dict) для proper wildcard matching через fnmatch.
# Order matters: most specific entries first, wildcards last per L1.
# Dict-based lookup with literal "cosmetics_premium_*" key would NOT match "cosmetics_premium_face"
# (string equality ≠ glob match). Iteration с fnmatch correctly handles patterns.

PROFILE_BY_L1_L2: list[tuple[str, str, dict]] = [
    # OTC pharma - all L2 patterns covered by wildcard
    ("OTC_pharma", "*", OTC_PHARMA_WEIGHTS),
    ("Rx_pharma", "*", RX_PHARMA_WEIGHTS),
    # FMCG impulse (specific L2 - must come before any wildcards под FMCG_food)
    ("FMCG_food", "snacks_savoury", FMCG_IMPULSE_WEIGHTS),
    ("FMCG_food", "snacks_sweet", FMCG_IMPULSE_WEIGHTS),
    ("FMCG_beverage", "beverage_carbonated", FMCG_IMPULSE_WEIGHTS),
    ("FMCG_beverage", "beverage_energy", FMCG_IMPULSE_WEIGHTS),
    # FMCG staples
    ("FMCG_food", "dairy_yogurt", FMCG_STAPLES_WEIGHTS),
    ("FMCG_food", "dairy_milk", FMCG_STAPLES_WEIGHTS),
    ("FMCG_food", "household", FMCG_STAPLES_WEIGHTS),
    ("FMCG_beverage", "beverage_juice", FMCG_STAPLES_WEIGHTS),
    # Cosmetics - prefix glob (premium L2 detected through pattern)
    ("Cosmetics", "cosmetics_premium_*", PREMIUM_COSMETICS_WEIGHTS),
    # Telecom / Banking
    ("Telecom", "*", TELECOM_BANKING_WEIGHTS),
    ("Banking", "banking_retail", TELECOM_BANKING_WEIGHTS),
    ("B2B", "*", B2B_WEIGHTS),
]


def select_weight_profile(recipient_l1: str, recipient_l2: str) -> dict[str, float]:
    """Select weight profile based on recipient category. First match wins (order = priority)."""
    for l1_pattern, l2_pattern, profile in PROFILE_BY_L1_L2:
        if l1_pattern != recipient_l1:
            continue
        if l2_pattern == "*" or fnmatch.fnmatchcase(recipient_l2, l2_pattern):
            return profile
    return DEFAULT_WEIGHTS
```

### 3.4 Manual Override

User может explicitly override weights в Advanced settings (per-project):
- UI panel: 6 sliders summing to 1.00 (auto-rebalance)
- Override flag stored в project metadata
- Audit trail: who changed weights когда + reason text

**Use case:** edge category или эксперт знает specific transfer concern (например premium positioning hijacks weight 0.50 для проектов где это критично).

---

## 4. Aggregate Similarity Formula

```python
def compute_aggregate_similarity(
    dimensions: dict[str, float],  # 6 dimensions с scores
    weights: dict[str, float],     # weight profile selected
) -> float:
    """Weighted average. Weights must sum to 1.0."""
    assert abs(sum(weights.values()) - 1.0) < 1e-6, "Weights must sum to 1.0"
    return sum(weights[d] * dimensions[d] for d in weights)
```

**Properties:**
- Monotonic в каждой dimension
- Bounded [0, 1]
- Weighted = sensitivity к important dimensions amplified

---

## 5. Verdict Thresholds

```python
def determine_confidence_verdict(s_aggregate: float) -> Literal["High", "Medium", "Low", "Insufficient"]:
    if s_aggregate >= 0.85:
        return "High"
    elif s_aggregate >= 0.65:
        return "Medium"
    elif s_aggregate >= 0.50:
        return "Low"
    else:
        return "Insufficient"
```

**Thresholds aligned с CI inflation factor (`MATH_REFERENCE.md` Section 3.1, 5.1):**

| Verdict | S_aggregate | Inflation factor | UX behavior |
|---|---|---|---|
| **High** | ≥ 0.85 | 1.2× | Forecast generation enabled, badge "Gold" |
| **Medium** | 0.65-0.85 | 1.5× | Forecast enabled, badge "Silver", warning suggested action |
| **Low** | 0.50-0.65 | 2.0× | Forecast enabled с prominent CI warning, badge "Bronze", suggestions для improving |
| **Insufficient** | < 0.50 | N/A | Forecast generation **blocked**. Recommendations: better proxy or category prior fallback |

### 5.1 Floor logic (per-dimension warnings)

Even при high aggregate, single-dimension failure raises warning:

```python
def check_dimension_floors(dimensions: dict[str, float]) -> List[Warning]:
    warnings = []
    if dimensions["category_subcategory"] < 0.5:
        warnings.append(Warning(
            severity="high",
            field="category_subcategory",
            message="Category mismatch (different L1 or distant L2). "
                    "Adstock + seasonality transfer may be unreliable."
        ))
    if dimensions["media_maturity"] < 0.3:
        warnings.append(Warning(
            severity="medium",
            field="media_maturity",
            message="Media maturity gap большой (e.g., always-on proxy → dormant recipient). "
                    "Adstock decay rates likely differ."
        ))
    # ... etc
    return warnings
```

---

## 6. Multi-Proxy Aggregation

When N≥2 proxies (S007 Multi-proxy mode):

```python
def compute_multi_proxy_aggregate(
    proxy_similarities: List[float],   # individual S per proxy
    pooling_weights: List[float],      # user-assigned partial pooling weights
) -> tuple[float, List[Warning]]:
    """Compute combined aggregate similarity для multi-proxy."""
    assert len(proxy_similarities) == len(pooling_weights)
    assert abs(sum(pooling_weights) - 1.0) < 1e-6, "Pooling weights must sum to 1.0"

    s_aggregate_multi = sum(
        w * s for w, s in zip(pooling_weights, proxy_similarities)
    )

    warnings = []
    # Floor: any individual proxy below 0.5 - warn
    for i, s in enumerate(proxy_similarities):
        if s < 0.5:
            warnings.append(Warning(
                severity="high",
                field=f"proxy_{i+1}",
                message=f"Прокси #{i+1} имеет similarity {s:.2f} < 0.5. "
                        f"Рекомендуется убрать его или найти лучший candidate."
            ))

    # Floor: spread > 0.3 between best и worst - warn (heterogeneous proxies)
    if max(proxy_similarities) - min(proxy_similarities) > 0.3:
        warnings.append(Warning(
            severity="medium",
            field="multi_proxy",
            message="Прокси имеют сильно разный similarity scores "
                    f"(spread {max(proxy_similarities) - min(proxy_similarities):.2f}). "
                    f"Combined uncertainty будет выше чем у любого отдельного прокси."
        ))

    return s_aggregate_multi, warnings
```

**Verdict для multi-proxy:** use `s_aggregate_multi` для tier (same thresholds). Inflation factor adjusts:

```python
def multi_proxy_inflation_factor(s_aggregate_multi: float, proxy_count: int) -> float:
    """Multi-proxy inflation чуть выше single (model averaging adds variance)."""
    base = single_proxy_inflation_factor(s_aggregate_multi)  # 1.2 / 1.5 / 2.0
    multi_penalty = 1.0 + 0.05 * (proxy_count - 1)  # +5% per extra proxy
    return base * multi_penalty
```

**Rationale:** model averaging across proxies introduces additional variance source. Inflation должна reflect это.

---

## 7. Calibration Approach

### 7.1 Phase B (initial release) - default + synthetic validation

**Default weights** locked в этом документе (Section 3). Used as-is для Phase B Sprint B6 pilot.

**Synthetic validation:**
- Generate synthetic recipient evolved from known proxy с varying similarity (controlled noise injection)
- Train Aurora Launch на synthetic recipient using each proxy
- Compare forecast accuracy across similarity buckets
- Validate что High verdict transfers indeed produce <15% MAPE, Medium 15-25%, Low >25%

Tests в `tests/integration/test_similarity_calibration.py` (Sprint B5):
```python
def test_high_similarity_yields_low_mape():
    synthetic_proxy = generate_synthetic_proxy(category="FMCG_food.snacks_savoury.chips")
    synthetic_recipient = derive_recipient(synthetic_proxy, similarity_target=0.90)
    forecast = aurora_launch.forecast(synthetic_recipient, proxy=synthetic_proxy)
    mape = compute_mape(forecast, synthetic_recipient.true_values)
    assert mape < 0.15, f"High similarity (0.90) gave MAPE {mape:.2%}, expected <15%"


def test_low_similarity_yields_higher_mape_with_wider_ci():
    # ... similar but similarity_target=0.55, expect MAPE 20-30%, CI captures truth
```

### 7.2 Phase C+ - iterative refinement from pilot data

После Sprint B6 pilot (Materia Medica / FMCG launch team) - empirical similarity vs forecast accuracy regressed:

```python
def empirical_calibration_from_pilots(pilot_records: List[PilotRecord]) -> dict:
    """Refine weights based on empirical pilot data.

    PilotRecord = (proxy, recipient, similarity_dimensions, S_aggregate, true_outcome, predicted_outcome)
    """
    # Inverse problem: find weights that minimize transfer error
    # subject to constraints (weights sum to 1, weights >= 0)
    from scipy.optimize import minimize

    def loss(weights, records):
        s_agg = [sum(w * r.dimensions[d] for w, d in zip(weights, DIMS)) for r in records]
        # Loss = correlation between (1 - s_agg) and (mape) - we want s_agg correlated с accuracy
        ...

    # Refine + report
    return new_weights
```

**Cadence:** quarterly review post-pilot expansion (>10 launches).

### 7.3 Override audit trail

Manual weight overrides (Section 3.4) tracked в audit log:
```
project_id: ...
timestamp: 2026-09-15T...
user: <expert_name>
old_weights: {...}
new_weights: {...}
reason: "Premium cosmetics launch - elevated pricing weight to 0.40 because target tier is luxury and proxy tier ambiguous"
```

---

## 8. Code Snippets для реализации

### 8.1 Python backend (Sprint B2)

```python
# engines/similarity_calculator.py

from typing import List, Literal
from pydantic import BaseModel, Field

class CategorySpec(BaseModel):
    l1: str
    l2: str
    l3: str

class BrandProfile(BaseModel):
    brand_name: str
    category: CategorySpec
    pricing_tier: Literal["ECONOMY", "MAINSTREAM", "PREMIUM", "LUXURY"]
    brand_size: Literal["LEADER", "CHALLENGER", "NICHE"]
    distribution: Literal["NATIONAL", "REGIONAL", "NICHE"]
    media_maturity: Literal["ALWAYS-ON", "PULSING", "PROMO-DRIVEN", "DORMANT"]
    lifecycle_stage: Literal["NEW", "GROWING", "MATURE", "DECLINING"]

class SimilarityResult(BaseModel):
    s_aggregate: float = Field(ge=0, le=1)
    dimensions: dict[str, float]
    verdict: Literal["High", "Medium", "Low", "Insufficient"]
    inflation_factor: float
    weight_profile_used: str  # "default" or category profile name
    warnings: List[str]


class SimilarityCalculator:
    def compute(
        self,
        proxy: BrandProfile,
        recipient: BrandProfile,
        weight_override: dict[str, float] | None = None,
    ) -> SimilarityResult:
        # Per-dimension scoring
        dims = {
            "category_subcategory": score_category(proxy.category, recipient.category),
            "pricing_tier": score_pricing_tier(proxy.pricing_tier, recipient.pricing_tier),
            "brand_size": score_brand_size(proxy.brand_size, recipient.brand_size),
            "distribution": score_distribution(proxy.distribution, recipient.distribution),
            "media_maturity": score_media_maturity(proxy.media_maturity, recipient.media_maturity),
            "lifecycle_stage": score_lifecycle(proxy.lifecycle_stage, recipient.lifecycle_stage),
        }

        # Weight profile
        weights = weight_override or select_weight_profile(
            recipient.category.l1, recipient.category.l2
        )
        profile_name = self._weight_profile_name(weights)

        # Aggregate
        s_agg = compute_aggregate_similarity(dims, weights)

        # Verdict + inflation
        verdict = determine_confidence_verdict(s_agg)
        inflation = INFLATION_BY_VERDICT[verdict]

        # Floor warnings
        warnings = check_dimension_floors(dims)

        return SimilarityResult(
            s_aggregate=s_agg,
            dimensions=dims,
            verdict=verdict,
            inflation_factor=inflation,
            weight_profile_used=profile_name,
            warnings=[w.message for w in warnings],
        )


INFLATION_BY_VERDICT = {
    "High": 1.2,
    "Medium": 1.5,
    "Low": 2.0,
    "Insufficient": float("nan"),  # forecast blocked
}
```

### 8.2 Rust → WASM module (Sprint B2)

Same logic ported к Rust для UI real-time computation. Bundle ≤200 KB (audit constraint).

```rust
// src-rust/similarity_wasm/src/lib.rs

use wasm_bindgen::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize)]
pub struct CategorySpec {
    pub l1: String,
    pub l2: String,
    pub l3: String,
}

#[derive(Serialize, Deserialize)]
pub struct BrandProfile {
    pub category: CategorySpec,
    pub pricing_tier: String,
    pub brand_size: String,
    pub distribution: String,
    pub media_maturity: String,
    pub lifecycle_stage: String,
}

#[derive(Serialize, Deserialize)]
pub struct SimilarityResult {
    pub s_aggregate: f64,
    pub dimensions: std::collections::HashMap<String, f64>,
    pub verdict: String,
    pub inflation_factor: f64,
}

#[wasm_bindgen]
pub fn compute_similarity_wasm(
    proxy_json: &str,
    recipient_json: &str,
) -> Result<JsValue, JsValue> {
    let proxy: BrandProfile = serde_json::from_str(proxy_json).map_err(|e| e.to_string())?;
    let recipient: BrandProfile = serde_json::from_str(recipient_json).map_err(|e| e.to_string())?;

    let dims = compute_dimensions(&proxy, &recipient);
    let weights = select_weight_profile(&recipient.category.l1, &recipient.category.l2);
    let s_agg = compute_aggregate(&dims, &weights);
    let verdict = determine_verdict(s_agg);
    let inflation = inflation_factor(&verdict);

    let result = SimilarityResult {
        s_aggregate: s_agg,
        dimensions: dims,
        verdict: verdict.to_string(),
        inflation_factor: inflation,
    };
    Ok(serde_wasm_bindgen::to_value(&result)?)
}
```

**Parity testing (Sprint B2):** synthetic test corpus с 100 proxy/recipient pairs - both Python и Rust WASM compute, results bit-equal (within float epsilon).

### 8.3 Svelte UI integration (Sprint B2)

```typescript
// src/lib/similarityWasm.ts
import init, { compute_similarity_wasm } from "./pkg/similarity_wasm";

let initialized = false;

export async function ensureInit() {
    if (!initialized) {
        await init();
        initialized = true;
    }
}

export async function computeSimilarity(
    proxy: BrandProfile,
    recipient: BrandProfile
): Promise<SimilarityResult> {
    await ensureInit();
    const result = compute_similarity_wasm(
        JSON.stringify(proxy),
        JSON.stringify(recipient)
    );
    return result as SimilarityResult;
}
```

```svelte
<!-- src/lib/components/SimilarityRadarChart.svelte -->
<script lang="ts">
    import { computeSimilarity } from "$lib/similarityWasm";

    let { proxy, recipient } = $props<{
        proxy: BrandProfile;
        recipient: BrandProfile;
    }>();

    let result = $derived(await computeSimilarity(proxy, recipient));
    // Real-time radar chart updates как user меняет dimensions
</script>
```

---

## 9. Worked Examples

### 9.1 Example: New OTC antiviral launch (Кагоцел-like proxy)

**Recipient:** new OTC antiviral, premium pricing, planned national distribution, planned always-on TV+digital, NEW lifecycle.

**Proxy:** Кагоцел (existing OTC antiviral, mainstream pricing, national distribution, pulsing media, MATURE).

| Dimension | Proxy | Recipient | Score |
|---|---|---|---|
| category | OTC.cold_flu.antiviral | OTC.cold_flu.antiviral | 1.0 (L3 match) |
| pricing_tier | MAINSTREAM | PREMIUM | 0.5 (1 step) |
| brand_size | LEADER | NICHE (predicted) | 0.3 (2 steps) |
| distribution | NATIONAL | NATIONAL | 1.0 |
| media_maturity | PULSING | ALWAYS-ON | 0.5 (1 step) |
| lifecycle | MATURE | NEW | 0.3 (2 steps) |

**Weights:** OTC_PHARMA_WEIGHTS (since L1=OTC_pharma):
- category 0.40, pricing 0.10, media_maturity 0.15, brand_size 0.15, distribution 0.10, lifecycle 0.10

**Aggregate:**
```
S = 0.40×1.0 + 0.10×0.5 + 0.15×0.5 + 0.15×0.3 + 0.10×1.0 + 0.10×0.3
  = 0.40 + 0.05 + 0.075 + 0.045 + 0.10 + 0.03
  = 0.70
```

**Verdict:** Medium (0.65 ≤ 0.70 < 0.85). Inflation factor 1.5×.

**Warnings:** none (all dimension floors passed).

### 9.2 Example: New premium snack (cross-tier mismatch)

**Recipient:** premium kale chips (NEW, niche, premium-luxury pricing).

**Proxy 1:** Lay's classic chips (LEADER, MAINSTREAM, MATURE, ALWAYS-ON, NATIONAL).

| Dimension | Score |
|---|---|
| category (L3 match: chips) | 1.0 |
| pricing_tier (MAINSTREAM vs PREMIUM, 1 step) | 0.5 |
| brand_size (LEADER vs NICHE, 2 steps) | 0.3 |
| distribution (NATIONAL vs NATIONAL planned) | 1.0 |
| media_maturity (ALWAYS-ON vs PULSING planned) | 0.5 |
| lifecycle (MATURE vs NEW, 2 steps) | 0.3 |

**Weights:** FMCG_IMPULSE_WEIGHTS:
- category 0.30, pricing 0.25, media_maturity 0.10, brand_size 0.15, distribution 0.10, lifecycle 0.10

**Aggregate:**
```
S = 0.30×1.0 + 0.25×0.5 + 0.10×0.5 + 0.15×0.3 + 0.10×1.0 + 0.10×0.3
  = 0.30 + 0.125 + 0.05 + 0.045 + 0.10 + 0.03
  = 0.65
```

**Verdict:** Medium (boundary). Inflation 1.5×.

**Recommendation:** consider better proxy, e.g., Pringles Premium или premium artisan brand если в данных.

### 9.3 Example: Insufficient case (cross-category)

**Recipient:** new SaaS productivity tool.
**Proxy:** Yandex Plus (subscription-based but consumer entertainment service).

| Dimension | Score |
|---|---|
| category (B2B.B2B_software.B2B_saas vs Telecom.telecom_subscription, cross L1) | 0.0 (or 0.2 if adjacent) |
| pricing_tier (custom B2B vs MAINSTREAM consumer) | 0.5 |
| brand_size (LEADER vs LEADER) | 1.0 |
| distribution (digital-only vs digital-only) | 1.0 |
| media_maturity (PULSING vs ALWAYS-ON) | 0.5 |
| lifecycle (NEW vs GROWING) | 0.6 |

**Weights:** B2B_WEIGHTS:
- category 0.35, pricing 0.05, media_maturity 0.20, brand_size 0.20, distribution 0.05, lifecycle 0.15

**Aggregate (assuming category=0.0):**
```
S = 0.35×0.0 + 0.05×0.5 + 0.20×0.5 + 0.20×1.0 + 0.05×1.0 + 0.15×0.6
  = 0 + 0.025 + 0.10 + 0.20 + 0.05 + 0.09
  = 0.465
```

**Verdict:** Insufficient (< 0.50). Forecast generation **blocked**. UI suggests:
- Find a closer proxy in B2B_software.B2B_saas L2
- If no close proxy exists - категорийный prior fallback (Phase D feature)

---

## 10. Edge Cases

### 10.1 New L3/L2 categories not in taxonomy

Default fallback к L1 only matching. UI prompts user "Эта sub-category не в нашем catalog. Используем L1 match. Хотите propose addition?"

Quarterly: review proposed additions, update `engines/category_taxonomy.yaml`.

### 10.2 Recipient brand_size unknown (true new launch)

User provides expected size from anchor data (planned market share):
- planned_share_pct >= 10% → LEADER
- planned_share_pct 3-10% → CHALLENGER
- planned_share_pct < 3% → NICHE

### 10.3 Recipient media_maturity unknown (no plan yet)

Default к expected pattern from anchor `media_plan` profile:
- Continuous coverage all weeks → ALWAYS-ON
- 4-12 burst windows → PULSING
- Concentrated в promo periods → PROMO-DRIVEN
- Если media plan absent yet, prompt user to fill anchors first

### 10.4 Recipient pricing_index_vs_proxy extreme

If anchor.pricing_index_vs_proxy < 0.5 or > 2.0 - recipient + proxy span 2+ pricing tiers. Force-set recipient tier based on absolute pricing_index_vs_proxy interpretation:
- ratio < 0.5 → recipient one tier below proxy
- ratio 0.5-1.5 → same tier
- ratio 1.5-2.5 → one tier above
- ratio > 2.5 → two tiers above

### 10.5 Weights manual override conflict с auto-profile

User opts "Use category profile" - locked в auto. Or "Customize weights" - manual. Project metadata stores choice. На next session - auto-profile re-applied unless flag "manual" set.

---

## 11. Связанные документы

- `../00_Overview/PRINCIPLES.md` - P2 (similarity по 6+ measurements)
- `../03_Architecture/MATH_REFERENCE.md` Section 6 - similarity formula + Section 3 transfer (inflation by verdict)
- `../01_Concept/MULTI_PROXY_UX_DECISION_RULES.md` (S007) - когда multi-proxy + UI
- `DATA_REQUIREMENTS.md` Section 6 - aggregate similarity stub
- `DSM_FIELDS.md` - data для расчёта pricing tier, brand size, distribution, lifecycle
- `MEDIASCOPE_FIELDS.md` - data для расчёта media maturity
- `RECIPIENT_ANCHORS.md` - planned values для recipient unknowns
- `engines/category_taxonomy.yaml` (Phase A deliverable) - L1/L2/L3 hierarchy + adjacency map
- `engines/channel_canonical.yaml` (Phase A) - channel naming для media maturity calc
- `tests/integration/test_similarity_calibration.py` (Sprint B5) - synthetic validation
- `decisions/ADR-002-storage-layer.md` - similarity weight profile stored в `proxy_brand_metadata.json`
