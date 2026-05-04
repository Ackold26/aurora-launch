# Aurora Launch - Data Requirements (Master Spec)

**Status:** v1.0 (2026-05-04)
**Authority:** определяет какие данные нужны для запуска Aurora Launch project. Используется в onboarding wizard, validation logic, sales playbook.
**Owner:** Маша + Антон (Aurora team). Updates - explicit в Q&A session.

## Контекст

Aurora Launch требует **3 источника данных**:
1. **Proxy data** - DSM Group + Mediascope по выбранному прокси-бренду (24+ месяцев)
2. **Recipient anchors** - данные от клиента (market context + media plan)
3. **Recipient history** (опционально) - DSM Group по recipient'у если бренд был на паузе

Этот документ - **master spec**. Детали - в companion files:
- `DSM_FIELDS.md` - точные поля DSM Group
- `MEDIASCOPE_FIELDS.md` - точные поля Mediascope TV + Digital
- `RECIPIENT_ANCHORS.md` - форма для клиента
- `recipient_anchors_v1.schema.json` - JSON Schema (machine-readable)

---

## Section 1: Overview - что нужно от кого

### От клиента / агентства (responsibility):

- **Подбор прокси-бренда** - совместно с Aurora expert (Антон) или собственным экспертом клиента / агентства
- **Сбор Proxy data** - выгрузки DSM + Mediascope (через подписки клиента / агентства)
- **Recipient anchors** - заполнение формы (market context, media plan, pricing)
- **Recipient history** (если paused brand case) - выгрузка DSM по recipient'у

### От Aurora (responsibility):

- **Format adapters** - Aurora Launch ingests DSM/MS форматы автоматически (multi-version support)
- **Validation** - проверка completeness + quality перед моделированием
- **Modeling** - transfer + forecasting + posterior update
- **Reporting** - PPTX/HTML/XLSX/PDF outputs
- **Consulting** - 20-40h в год support (proxy review, methodology questions, posterior updates)

---

## Section 2: Proxy Data Requirements

### 2.1 DSM Group (продажи + рынок) - MUST HAVE

**Source:** DSM Group monthly Excel выгрузки (по подписке клиента / агентства)
**Period:** 24+ месяцев непрерывных (для адекватной calibration adstock + hill shape)
**Grain:** monthly, Россия + key cities (Москва, СПб + 5-10 городов миллионников)

**Mandatory fields:**
- `brand_id` / `brand_name` - identifier прокси-бренда
- `period` - YYYY-MM
- `geo` - "RF_total" + city codes
- `sales_rub` - продажи в рублях
- `sales_packs` - продажи в упаковках
- `distribution_numeric_pct` - численная дистрибуция, %
- `distribution_weighted_pct` - взвешенная дистрибуция, %
- `penetration_pct` - пенетрация, % (опционально для some categories)
- `price_shelf_avg` - средняя цена на полке, ₽
- `price_wholesale_avg` - средняя оптовая цена, ₽

**Recommended fields** (если доступны):
- `sku_breakdown` - разбивка по SKU (для multi-SKU брендов)
- `manufacturer` - corporation name
- `atc_class` - ATC класс (для pharma)
- `category_total_rub` - объём всей категории (для category trend)

**Validator rules** (см. `DSM_FIELDS.md`):
- Coverage: 24+ непрерывных months
- No gaps > 1 month
- Currency consistency (нет mixed RUB/USD)
- Sales > 0 (no negative entries)
- Distribution 0..100 range

### 2.2 Mediascope TV (рекламная активность TV) - MUST HAVE

**Source:** Mediascope monthly или weekly XLSX выгрузки
**Period:** 18+ месяцев overlapping с DSM period
**Grain:** weekly (preferred) или monthly

**Mandatory fields per channel per period:**
- `period_start` / `period_end` - ISO dates
- `channel` - имя канала (Первый, Россия 1, НТВ, СТС, ТНТ, ...)
- `target_demo` - демо-группа (W 25-54, M 18-44, All 18+, ...)
- `trp` - Target Rating Points
- `grp` - Gross Rating Points
- `budget_rub` - стоимость размещения, ₽
- `format_type` - sponsorship / spot / product placement

**Recommended fields:**
- `daypart` - время суток (prime / off-prime)
- `program_genre` - жанр программы
- `creative_id` - идентификатор ролика (для creative analysis)

**Validator rules** (см. `MEDIASCOPE_FIELDS.md`):
- Coverage: непрерывные periods (нет skipping weeks)
- TRP > 0, budget > 0 (no zero entries unless brand was off-air)
- Demo группы consistent (один target throughout history)
- Cross-validation TRP vs Budget (sanity на CPP в reasonable range)

### 2.3 Mediascope Digital (рекламная активность Digital) - MUST HAVE если есть digital в media mix

**Source:** Mediascope Digital + Digital Budget (от AdIndex / профильный подписчик)
**Period:** 18+ месяцев
**Grain:** weekly или monthly

**Mandatory fields per platform per period:**
- `period_start` / `period_end`
- `platform` - Yandex, VK, Mail.ru Group, Telegram Ads, programmatic networks
- `placement_type` - context / display / video / native
- `impressions` - показы
- `budget_rub` - бюджет, ₽

**Recommended:**
- `clicks`, `ctr` - если доступны
- `views` (для video), `vtr` - completion rate
- `target_demo` - если доступны на digital

### 2.4 Digital Budget (alternative source) - if Mediascope Digital недоступен

**Source:** AdIndex Digital Budget tracker
**Note:** разные форматы выгрузок чем Mediascope - см. `MEDIASCOPE_FIELDS.md` Section 4

---

## Section 3: Recipient Data Requirements

### 3.1 Recipient Anchors (форма) - MUST HAVE

См. `RECIPIENT_ANCHORS.md` для полной спецификации + `recipient_anchors_v1.schema.json` для JSON Schema.

**Mandatory fields:**
- `market_size_rub` - размер категории в рублях, год (на момент launch)
- `planned_share_pct` - планируемая доля рынка к концу 1 года (%)
- `distribution_target_pct` - целевая численная дистрибуция к запуску (%)
- `sov_planned_pct` - планируемая доля голоса в категории (%)
- `pricing_index_vs_proxy` - цена recipient'а как % от прокси (range 0.3..3.0, soft warning при extreme)
- `launch_date` - ISO date старта рекламы
- `media_plan` - список каналов × periods × budgets

**Recommended fields:**
- `creative_quality_benchmark` - если есть pre-test данные (Kantar Link, Ipsos copytest)
- `target_kpi_sales` - бизнес-цель по продажам (для reality check)
- `competitive_response_assumption` - ожидаемая реакция конкурентов
- `category_trend` - категория растёт / стабильна / падает (если recipient знает)

### 3.2 Recipient History (опционально, для paused brand case)

Если бренд был на паузе в рекламе но имеет sales history - **рекомендовано** добавить:
- DSM Group выгрузка по recipient'у (12+ месяцев organic sales)
- Используется для baseline calibration (organic baseline + competitive context)
- Optional: short Mediascope history если была рекламная активность давно

**Если recipient history отсутствует** (true new brand) - magnitude calibration через anchors only.

---

## Section 4: Quality Validators (правила что значит "пригодные данные")

### 4.1 Proxy data validation

**ProxyDataValidator** в `engines/launch_validators.py`:

```python
from typing import List, Tuple, Optional
import pandas as pd
from pydantic import BaseModel

class ProxyDataValidationResult(BaseModel):
    is_sufficient: bool
    severity: Literal["error", "warning", "info"]
    issues: List[str]
    recommendations: List[str]

class ProxyDataValidator:
    """Validates DSM + Mediascope data sufficiency for proxy modeling."""

    MIN_DSM_MONTHS = 24
    MIN_MEDIASCOPE_MONTHS = 18
    MAX_GAP_MONTHS = 1

    def validate(
        self,
        dsm_df: pd.DataFrame,
        ms_tv_df: pd.DataFrame,
        ms_digital_df: Optional[pd.DataFrame] = None,
    ) -> ProxyDataValidationResult:
        issues = []
        warnings = []
        recommendations = []

        # DSM coverage
        dsm_months = self._count_unique_months(dsm_df, "period")
        if dsm_months < self.MIN_DSM_MONTHS:
            issues.append(
                f"DSM data insufficient: {dsm_months} months "
                f"(need {self.MIN_DSM_MONTHS}+)"
            )
            recommendations.append(
                "Запросите выгрузку DSM за дополнительные периоды"
            )

        # DSM gaps
        gaps = self._detect_gaps(dsm_df, "period")
        if any(g > self.MAX_GAP_MONTHS for g in gaps):
            issues.append(f"DSM gaps detected: {gaps}")

        # Mediascope TV coverage
        ms_months = self._count_unique_months(ms_tv_df, "period_start")
        if ms_months < self.MIN_MEDIASCOPE_MONTHS:
            issues.append(
                f"Mediascope TV insufficient: {ms_months} months"
            )

        # Cross-validation: DSM and MS overlap
        overlap = self._compute_overlap(dsm_df, ms_tv_df)
        if overlap < 12:
            issues.append(f"DSM/Mediascope overlap < 12 months ({overlap})")

        # ... more checks

        return ProxyDataValidationResult(
            is_sufficient=len(issues) == 0,
            severity="error" if issues else ("warning" if warnings else "info"),
            issues=issues + warnings,
            recommendations=recommendations,
        )
```

### 4.2 Recipient anchors validation

**ValidationIssue model:**

```python
from pydantic import BaseModel
from typing import Literal, Optional

class ValidationIssue(BaseModel):
    severity: Literal["error", "warning", "info"]
    field: str
    message: str
```

**Category media-to-revenue ratios (для Budget vs SoV consistency check):**

```python
# Category-specific ratios (low / high bounds). Source: Russian Advertising Communications
# Industry research, 2024-2025. Usage: соотношение медиа-бюджета к выручке отрасли.
CATEGORY_MEDIA_TO_REV_RATIO = {
    "FMCG_snacks": (0.06, 0.10),
    "FMCG_beverages": (0.05, 0.09),
    "FMCG_dairy": (0.04, 0.07),
    "FMCG_household": (0.05, 0.08),
    "OTC_pharma": (0.08, 0.15),
    "Rx_pharma": (0.03, 0.06),  # ограничения на рекламу Rx
    "telecom": (0.04, 0.08),
    "banking_premium": (0.03, 0.05),
    "B2B": (0.01, 0.03),
    "cosmetics_premium": (0.10, 0.18),
    "energy_drinks": (0.06, 0.12),
}
```

**SemanticValidator - cross-field consistency rules:**

```python
from datetime import date

class RecipientAnchorsSemanticValidator:
    """Cross-field domain rules for recipient anchors."""

    def __init__(self, category_ratios: Optional[dict] = None):
        self.category_ratios = category_ratios or CATEGORY_MEDIA_TO_REV_RATIO

    def validate(
        self,
        anchors: RecipientAnchorsV1,
        category: Optional[str] = None,
    ) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []

        # 1. Excess Share of Voice principle
        # SoV должна быть 1-3 п.п. больше market share для growing brand
        sov_excess = anchors.sov_planned_pct - anchors.planned_share_pct
        if sov_excess < 0:
            issues.append(ValidationIssue(
                severity="warning",
                field="sov_planned_pct",
                message=(
                    f"SoV ({anchors.sov_planned_pct}%) ниже planned share "
                    f"({anchors.planned_share_pct}%). Excess SoV theory: "
                    f"для growth нужно SoV > share на 1-3 п.п."
                ),
            ))
        elif sov_excess > 10:
            issues.append(ValidationIssue(
                severity="info",
                field="sov_planned_pct",
                message=(
                    f"SoV excess {sov_excess:.1f} п.п. - aggressive launch. "
                    f"Aurora forecasts (от proxy) могут underestimate effect."
                ),
            ))

        # 2. Pricing extreme
        if anchors.pricing_index_vs_proxy < 0.5:
            issues.append(ValidationIssue(
                severity="warning",
                field="pricing_index_vs_proxy",
                message=(
                    "Recipient в 2× дешевле прокси. "
                    "Magnitude calibration может быть unreliable."
                ),
            ))
        elif anchors.pricing_index_vs_proxy > 2.0:
            issues.append(ValidationIssue(
                severity="warning",
                field="pricing_index_vs_proxy",
                message=(
                    "Recipient в 2× дороже прокси. "
                    "Premium positioning - learnt elasticities могут differ."
                ),
            ))

        # 3. Distribution velocity (Pydantic v2 already coerces launch_date to date)
        # Bug-fix: было `< 180`, что соответствовало и отрицательным дням (already launched)
        days_to_launch = (anchors.launch_date - date.today()).days
        if 0 < days_to_launch < 180 and anchors.distribution_target_pct > 80:
            issues.append(ValidationIssue(
                severity="warning",
                field="distribution_target_pct",
                message=(
                    f"Distribution target {anchors.distribution_target_pct}% "
                    f"за {days_to_launch} дней может быть unrealistic для нового бренда"
                ),
            ))

        # 4. Budget vs SoV consistency (category-specific, не блокирующий)
        # Проверка только если знаем категорию - иначе skip (no false positive)
        if category and category in self.category_ratios:
            ratio_low, ratio_high = self.category_ratios[category]
            total_budget = sum(item.budget_rub for item in anchors.media_plan)
            market_media_low = anchors.market_size_rub * ratio_low
            market_media_high = anchors.market_size_rub * ratio_high

            # implied SoV range
            implied_sov_low = (total_budget / market_media_high) * 100
            implied_sov_high = (total_budget / market_media_low) * 100

            if not (implied_sov_low <= anchors.sov_planned_pct <= implied_sov_high):
                issues.append(ValidationIssue(
                    severity="info",
                    field="media_plan",
                    message=(
                        f"Implied SoV by budget ({implied_sov_low:.1f}-{implied_sov_high:.1f}%) "
                        f"вне range заявленной ({anchors.sov_planned_pct}%). "
                        f"Проверьте бюджет и SoV plan."
                    ),
                ))
        elif not category:
            # Skip check - no false positives without category context
            pass

        return issues
```

### 4.3 Workflow integration

**В UI (Sprint B2-B3):**

1. **ProxySelectionStep**: ProxyDataValidator runs on data upload
   - Issues отображаются в UI panel
   - Severity-based icons (red error / yellow warning / blue info)
   - Block "Generate Forecast" при errors

2. **RecipientAnchorsStep**: SemanticValidator runs real-time на form changes
   - Live tooltip warnings под полями
   - Aggregate quality verdict в sidebar

3. **TransferValidateStep**: combined check
   - Proxy quality verdict
   - Anchors completeness verdict
   - Combined transfer confidence (Tier-1 / Tier-2 / Tier-3 / Insufficient)

---

## Section 5: Code Snippets для реализации

### 5.1 Pydantic models (Sprint B1) - Pydantic v2 patterns

```python
# engines/launch_schema.py

from pydantic import BaseModel, Field, model_validator
from typing import List, Literal, Optional
from typing_extensions import Self
from datetime import date

class MediaPlanItem(BaseModel):
    channel: str = Field(min_length=1, description="TV channel или digital platform")
    period_start: date
    period_end: date
    budget_rub: float = Field(gt=0)
    units: Optional[float] = Field(default=None, ge=0, description="TRP / impressions")

    @model_validator(mode="after")
    def end_after_start(self) -> Self:
        # Pydantic v2 cross-field validation pattern (model_validator, не field_validator)
        if self.period_end < self.period_start:
            raise ValueError(
                f"period_end ({self.period_end}) must be >= period_start ({self.period_start})"
            )
        return self

class RecipientAnchorsV1(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    market_size_rub: float = Field(
        gt=0, description="Размер категории в рублях, год (на момент launch)"
    )
    planned_share_pct: float = Field(gt=0, le=100)
    distribution_target_pct: float = Field(gt=0, le=100)
    distribution_ramp_weeks: int = Field(ge=1, le=52)
    sov_planned_pct: float = Field(gt=0, le=100)
    pricing_index_vs_proxy: float = Field(
        ge=0.3, le=3.0,
        description="Recipient price as fraction of proxy price (0.3-3.0)",
    )
    launch_date: date
    media_plan: List[MediaPlanItem] = Field(min_length=1)
    category_trend: Literal["growing", "stable", "declining"]

    is_paused_brand: bool = False
    pause_duration_months: Optional[int] = Field(default=None, ge=6)

    creative_quality_benchmark: Optional[float] = Field(default=None, ge=0, le=1)
    target_kpi_sales: Optional[float] = Field(default=None, gt=0)
    competitive_response_assumption: Optional[Literal[
        "passive", "moderate_increase", "aggressive_response"
    ]] = None

    @model_validator(mode="after")
    def check_paused_brand_consistency(self) -> Self:
        if self.is_paused_brand and self.pause_duration_months is None:
            raise ValueError(
                "pause_duration_months required when is_paused_brand=true"
            )
        if not self.is_paused_brand and self.pause_duration_months is not None:
            raise ValueError(
                "pause_duration_months only valid for paused brands (is_paused_brand=true)"
            )
        return self

class ProxyBrandMetadata(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    brand_id: str
    brand_name: str
    category: str
    sub_category: str
    similarity_dimensions: dict[str, float]  # 6 dimensions с scores
    similarity_aggregate: float = Field(ge=0, le=1)
    confidence_verdict: Literal["High", "Medium", "Low", "Insufficient"]
    data_period_start: date
    data_period_end: date
    data_sources: List[Literal["DSM_Group", "Mediascope_TV", "Mediascope_Digital", "Digital_Budget"]]
```

### 5.2 JSON Schema (auto-export from Pydantic)

См. `recipient_anchors_v1.schema.json` - generated через:
```python
import json
from launch_schema import RecipientAnchorsV1

with open("recipient_anchors_v1.schema.json", "w", encoding="utf-8") as f:
    json.dump(RecipientAnchorsV1.model_json_schema(), f, indent=2, ensure_ascii=False)
```

### 5.3 TypeScript interfaces (auto-gen из JSON Schema)

В Aurora Launch frontend:
```bash
npx json-schema-to-typescript recipient_anchors_v1.schema.json > src/lib/types/recipientAnchors.ts
```

Reproducible single source of truth.

---

## Section 6: Quality stamp computation (предварительно, S003 finalize)

Aggregate similarity score (0-1) из 6 dimensions:

```python
def compute_aggregate_similarity(dimensions: dict[str, float]) -> float:
    """
    Computes weighted average similarity score.
    Weights determined через S003 session.
    """
    weights = {
        "category_subcategory": 0.30,
        "pricing_tier": 0.20,
        "brand_size": 0.15,
        "distribution": 0.10,
        "media_maturity": 0.15,
        "lifecycle_stage": 0.10,
    }
    return sum(weights[k] * dimensions[k] for k in weights)

def determine_confidence_verdict(score: float) -> str:
    if score >= 0.85:
        return "High"
    elif score >= 0.65:
        return "Medium"
    elif score >= 0.50:
        return "Low"
    else:
        return "Insufficient"
```

**Note:** weights и thresholds - предварительные. S003 (до Sprint B2) calibrates на synthetic transfers + expert review.

---

## Section 7: Workflow integration

### 7.1 Aurora Launch UI flow

**Step 1: Project Setup**
- New project / open existing / from template
- Project metadata: recipient brand name, category, expected launch date

**Step 2: Proxy Selection**
- Choose proxy brand (single or multi)
- Upload DSM data → auto-validate via ProxyDataValidator
- Upload Mediascope TV data → auto-validate
- Upload Mediascope Digital data (если применимо) → auto-validate
- Fill 6 similarity dimensions → live similarity radar chart
- View confidence verdict + warnings

**Step 3: Recipient Anchors**
- Form (Pydantic validated)
- Real-time SemanticValidator feedback
- Save / load anchors templates (для repeated launches same client)

**Step 4: Transfer Validation**
- Prior predictive checks (sample N forecasts с current setup, visualize)
- Sensitivity analysis
- Combined Tier badge (Gold / Silver / Bronze / Insufficient)
- Approve transfer → proceed к training

**Step 5: Training**
- Streaming MCMC visualization (audit B6)
- Diagnostic checks (Gelman-Rubin, ESS, divergences)
- Training time estimate в UI

**Step 6: Forecast & Decompose**
- Forecast cone animation (12 / 26 / 52 weeks)
- Decomposition stacked area
- What-if scenarios

**Step 7: Optimize**
- Budget reallocation suggestions
- Constrained optimization (per-channel limits)

**Step 8: Report**
- Generate PPTX/HTML/XLSX
- Methodology Certificate PDF
- Save to project archive

**Step 9 (recurring): Posterior Update**
- Upload new recipient data (DSM monthly или weekly Mediascope)
- Re-fit с reduced proxy weight
- Show weight reduction в UI

### 7.2 Backend API endpoints (decoupled REST)

```
POST /launch/v1/proxy/validate     # Validate proxy data
POST /launch/v1/anchors/validate   # Validate recipient anchors
POST /launch/v1/similarity/compute # Real-time similarity score
POST /launch/v1/adapt              # Run adaptation
POST /launch/v1/validate_transfer  # Prior predictive + sensitivity
POST /launch/v1/train              # Train model (streaming response)
POST /launch/v1/forecast           # Generate forecast
POST /launch/v1/decompose          # Decompose contribution
POST /launch/v1/optimize           # Budget optimization
POST /launch/v1/report/pptx        # Generate PPTX
POST /launch/v1/report/html        # Generate HTML
POST /launch/v1/report/certificate # Generate Methodology Certificate PDF
POST /launch/v1/posterior_update   # Re-fit с new recipient data
```

**OpenAPI version configuration:**

```python
# sidecar/main.py
from fastapi import FastAPI

app = FastAPI(
    title="Aurora Launch Backend",
    version="1.0.0",
    openapi_version="3.1.0",  # explicit (FastAPI 0.103+ supports 3.1)
)
```

Pydantic v2 → OpenAPI 3.1 переход: `anyOf [..., null]` вместо `nullable: true` (устаревший в OpenAPI 3.0).
TypeScript client generation - validate с openapi-typescript-codegen или zod-to-openapi.

---

## Связанные документы

- `DSM_FIELDS.md` - детали DSM Group fields + sample formats
- `MEDIASCOPE_FIELDS.md` - детали Mediascope TV/Digital + format adapters
- `RECIPIENT_ANCHORS.md` - детали anchor form + UI hints
- `recipient_anchors_v1.schema.json` - JSON Schema SSoT
- `../00_Overview/PRINCIPLES.md` - P3 (адаптация shape vs magnitude)
- `../03_Architecture/REUSE_FROM_ECONOMETRICA.md` - shared math layer
- `../03_Architecture/DATA_PRIVACY.md` - local-first архитектура
