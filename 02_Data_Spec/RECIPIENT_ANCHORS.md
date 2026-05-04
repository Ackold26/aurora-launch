# Recipient Anchors - Form Spec

**Status:** v1.0 (2026-05-04)
**JSON Schema (machine-readable):** `recipient_anchors_v1.schema.json`

## Контекст

Recipient anchors - данные от клиента про recipient brand. Эти данные используются для **magnitude calibration**: shape parameters (adstock, hill) переносятся от proxy, а magnitude (β scale, baseline) - calibration через recipient anchors.

Без anchors transfer невозможен - модель не знает на какой scale действует recipient (это маленький бренд с 5% share или большой с 25%? премиум по 500₽ или mainstream по 200₽?).

---

## Section 1: Mandatory Fields

### 1.1 Market Context

| Field | Type | Description | Range / Constraint |
|---|---|---|---|
| `market_size_rub` | float | Размер категории в рублях, год (на момент launch) | > 0 |
| `planned_share_pct` | float | Планируемая доля рынка к концу 1 года, % | 0 < x ≤ 100 |
| `category_trend` | enum | Категорийный тренд | growing / stable / declining |

### 1.2 Distribution

| Field | Type | Description | Range |
|---|---|---|---|
| `distribution_target_pct` | float | Целевая численная дистрибуция к запуску, % | 0 < x ≤ 100 |
| `distribution_ramp_weeks` | int | За сколько недель достигается целевая дистрибуция | 1-52 |

### 1.3 Share of Voice & Pricing

| Field | Type | Description | Range |
|---|---|---|---|
| `sov_planned_pct` | float | Планируемая доля голоса в категории за launch period, % | 0 < x ≤ 100 |
| `pricing_index_vs_proxy` | float | Цена recipient'а / Цена прокси | 0.3 ≤ x ≤ 3.0 (warning при extreme) |

### 1.4 Launch Schedule

| Field | Type | Description |
|---|---|---|
| `launch_date` | date | ISO date старта рекламы |
| `media_plan` | array | Список media plan items (см. ниже) |

### 1.5 Media Plan Item

```json
{
  "channel": "perviy",
  "period_start": "2026-08-15",
  "period_end": "2026-08-21",
  "budget_rub": 4500000,
  "units": 145.3,
  "placement_type": "spot"
}
```

| Field | Type | Description | Required |
|---|---|---|---|
| `channel` | string | Canonical channel name (см. MEDIASCOPE_FIELDS) | YES |
| `period_start` | date | Start ISO | YES |
| `period_end` | date | End ISO | YES |
| `budget_rub` | float | Budget, ₽ | YES |
| `units` | float | TRP / impressions | RECOMMENDED |
| `placement_type` | enum | spot / sponsorship / display / video / native / context | RECOMMENDED |

---

## Section 2: Recommended Fields

### 2.1 Creative Quality (boost forecast accuracy if available)

| Field | Type | Description | Range |
|---|---|---|---|
| `creative_quality_benchmark` | float | Pre-test score (Kantar Link / Ipsos copytest / similar) | 0..1 |
| `creative_test_methodology` | string | Methodology name | "Kantar_Link" / "Ipsos_Copytest" / "Internal" |

### 2.2 Business Targets

| Field | Type | Description |
|---|---|---|
| `target_kpi_sales` | float | Бизнес-цель по продажам, ₽ (для reality check) |
| `target_kpi_packs` | int | Бизнес-цель по упаковкам |
| `target_period` | enum | "first_year" / "first_half" / "first_quarter" |

### 2.3 Competitive Context

| Field | Type | Description | Values |
|---|---|---|---|
| `competitive_response_assumption` | enum | Ожидаемая реакция конкурентов | passive / moderate_increase / aggressive_response |
| `top3_competitors` | array | List of top 3 competitor brand names | ["Бренд A", "Бренд B", "Бренд C"] |
| `category_consolidation` | enum | Концентрация рынка | top1_dominant / top3_dominant / fragmented |

### 2.4 Special Cases

| Field | Type | Description |
|---|---|---|
| `is_paused_brand` | bool | true если paused brand case (есть organic baseline) |
| `pause_duration_months` | int | Если paused - сколько месяцев без рекламы |
| `seasonal_pattern` | enum | "summer_peak" / "winter_peak" / "holiday_peak" / "uniform" |

---

## Section 3: Validation Rules (Pydantic + SemanticValidator)

### 3.1 Pydantic field-level validation

```python
class RecipientAnchorsV1(BaseModel):
    schema_version: Literal["1.0"] = "1.0"

    market_size_rub: float = Field(gt=0)
    planned_share_pct: float = Field(gt=0, le=100)

    distribution_target_pct: float = Field(gt=0, le=100)
    distribution_ramp_weeks: int = Field(ge=1, le=52)

    sov_planned_pct: float = Field(gt=0, le=100)
    pricing_index_vs_proxy: float = Field(ge=0.3, le=3.0)

    launch_date: date
    media_plan: List[MediaPlanItem] = Field(min_length=1)

    category_trend: Literal["growing", "stable", "declining"]
    is_paused_brand: bool = False
    pause_duration_months: Optional[int] = Field(default=None, ge=6)  # audit fix F48

    # ... optional fields

    @model_validator(mode="after")
    def check_paused_brand_consistency(self) -> Self:
        if self.is_paused_brand and self.pause_duration_months is None:
            raise ValueError("pause_duration_months required when is_paused_brand=true")
        if not self.is_paused_brand and self.pause_duration_months is not None:
            raise ValueError("pause_duration_months only valid for paused brands")
        return self
```

### 3.2 Semantic validation (cross-field rules)

См. `DATA_REQUIREMENTS.md` Section 4.2 для full SemanticValidator implementation.

Key rules:
- **Excess Share of Voice**: SoV должна быть 1-3 п.п. выше market share для growing brand
- **Distribution velocity**: 100% дистрибуция за 6 мес для нового FMCG = unrealistic
- **Pricing extreme**: pricing_index < 0.5 или > 2.0 - warning
- **Budget vs SoV consistency**: implied SoV by budget vs declared
- **Launch date sanity**: не в прошлом (если новый launch), reasonable future window

---

## Section 4: UI Form Spec (Sprint B3)

### 4.1 Form layout

**Step 1 of recipient anchors form** - Market Context:
- Market size input (with thousand separators)
- Planned share % slider with input
- Category trend radio buttons (3 options + tooltip "что выбрать?")

**Step 2** - Distribution:
- Distribution target % slider
- Distribution ramp weeks input ("за сколько недель")

**Step 3** - Share of Voice & Pricing:
- SoV planned % slider with cross-validation against budget
- Pricing index vs proxy input with extreme warning

**Step 4** - Launch Schedule:
- Launch date picker
- Media plan table editor (channel × period × budget × units)

**Step 5** - Optional Fields (collapsible):
- Creative quality benchmark
- Business targets
- Competitive context

### 4.2 Real-time feedback

При заполнении - **live validation**:
- Tooltip warnings под полями
- Aggregate quality verdict в sidebar (Mandatory complete? Optional filled?)
- "Generate Forecast" button enabled только после mandatory complete

### 4.3 Templates library

Pre-filled templates для common scenarios:
- "FMCG Snacks Launch (mid-tier)" - market_size 5B, share 3%, distribution 60% за 12 нед, SoV 5%
- "OTC Pharma Launch (specialty)" - market_size 800M, share 5%, distribution 40% за 24 нед, SoV 8%
- "Premium Cosmetic Launch (niche)" - market_size 2B, share 1%, distribution 25% за 16 нед, SoV 3%
- "Energy Drink Launch (mass)" - market_size 8B, share 2%, distribution 70% за 8 нед, SoV 6%
- "Telecom Service Launch (national)" - market_size 50B, share 0.5%, distribution N/A, SoV 4%

User clones template → fills with own data → reduces blank-page anxiety.

### 4.4 Save/load anchors

- Сохранение anchors как named template (для repeated launches same client)
- Reuse в follow-up launches с slight modifications
- Export anchors as JSON (для backup / sharing с команды)

---

## Section 5: Form Code Examples

### 5.1 TypeScript interface (auto-gen из JSON Schema)

```typescript
// src/lib/types/recipientAnchors.ts (auto-generated)

export type CategoryTrend = "growing" | "stable" | "declining";
export type CompetitiveResponse = "passive" | "moderate_increase" | "aggressive_response";
export type CategoryConsolidation = "top1_dominant" | "top3_dominant" | "fragmented";
export type SeasonalPattern = "summer_peak" | "winter_peak" | "holiday_peak" | "uniform";
export type PlacementType = "spot" | "sponsorship" | "display" | "video" | "native" | "context";

export interface MediaPlanItem {
  channel: string;
  period_start: string; // ISO date
  period_end: string;
  budget_rub: number;
  units?: number;
  placement_type?: PlacementType;
}

export interface RecipientAnchorsV1 {
  schema_version: "1.0";
  market_size_rub: number;
  planned_share_pct: number;
  distribution_target_pct: number;
  distribution_ramp_weeks: number;
  sov_planned_pct: number;
  pricing_index_vs_proxy: number;
  launch_date: string;
  media_plan: MediaPlanItem[];
  category_trend: CategoryTrend;
  is_paused_brand?: boolean;
  pause_duration_months?: number;
  creative_quality_benchmark?: number;
  creative_test_methodology?: string;
  target_kpi_sales?: number;
  target_kpi_packs?: number;
  target_period?: "first_year" | "first_half" | "first_quarter";
  competitive_response_assumption?: CompetitiveResponse;
  top3_competitors?: string[];
  category_consolidation?: CategoryConsolidation;
  seasonal_pattern?: SeasonalPattern;
}
```

### 5.2 Svelte form component skeleton (Svelte 5 runes)

```svelte
<!-- src/lib/components/RecipientAnchorsForm.svelte -->

<script lang="ts">
  import type { RecipientAnchorsV1 } from "$lib/types/recipientAnchors";
  import type { ValidationIssue } from "$lib/types/validation";
  import { validateAnchors } from "$lib/api/launch";

  let anchors = $state<Partial<RecipientAnchorsV1>>({
    schema_version: "1.0",
    media_plan: [],
  });

  // Live validation (debounced 300ms)
  let validationIssues = $state<ValidationIssue[]>([]);
  let validationTimer: ReturnType<typeof setTimeout> | null = null;

  $effect(() => {
    // Snapshot anchors для tracking changes
    const snapshot = JSON.stringify(anchors);
    if (validationTimer) clearTimeout(validationTimer);
    validationTimer = setTimeout(async () => {
      try {
        validationIssues = await validateAnchors(anchors);
      } catch (err) {
        console.error("[RecipientAnchorsForm] validation failed:", err);
        // graceful degradation - не блокируем работу из-за network error
        validationIssues = [];
      }
    }, 300);
  });

  // Aggregate verdict
  let mandatoryComplete = $derived(
    anchors.market_size_rub != null &&
    anchors.planned_share_pct != null &&
    anchors.distribution_target_pct != null &&
    anchors.sov_planned_pct != null &&
    anchors.pricing_index_vs_proxy != null &&
    anchors.launch_date != null &&
    (anchors.media_plan?.length ?? 0) > 0 &&
    anchors.category_trend != null
  );

  let canProceed = $derived(
    mandatoryComplete &&
    !validationIssues.some(i => i.severity === "error")
  );
</script>

<form class="anchors-form">
  <!-- Step 1: Market Context -->
  <fieldset>
    <legend>Контекст рынка</legend>

    <label>
      Размер категории, ₽/год
      <input type="number" bind:value={anchors.market_size_rub} min="0" />
      <span class="hint">Общий объём всей категории на момент запуска</span>
    </label>

    <label>
      Планируемая доля рынка к концу 1 года, %
      <input type="range" min="0.1" max="50" step="0.1"
             bind:value={anchors.planned_share_pct} />
      <output>{anchors.planned_share_pct}%</output>
    </label>

    <label>
      Категорийный тренд
      <select bind:value={anchors.category_trend}>
        <option value="growing">Растёт</option>
        <option value="stable">Стабилен</option>
        <option value="declining">Снижается</option>
      </select>
    </label>
  </fieldset>

  <!-- ... Other fieldsets ... -->

  {#if validationIssues.length > 0}
    <div class="validation-feedback" role="alert">
      {#each validationIssues as issue}
        <div class="issue {issue.severity}">{issue.message}</div>
      {/each}
    </div>
  {/if}

  <button type="submit" disabled={!canProceed}>
    Продолжить к Transfer Validation →
  </button>
</form>

<style>
  .anchors-form {
    display: grid;
    gap: 1.5rem;
    max-width: 720px;
  }

  fieldset {
    border: 1px solid var(--color-border);
    padding: 1rem;
    border-radius: 8px;
  }

  .validation-feedback {
    background: var(--color-warning-surface);
    padding: 1rem;
    border-radius: 6px;
  }

  .issue.error { color: var(--color-error); }
  .issue.warning { color: var(--color-warning); }
  .issue.info { color: var(--color-info); }
</style>
```

### 5.3 Pydantic backend validation endpoint

```python
# sidecar/launch_routes.py

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError
from launch_schema import RecipientAnchorsV1
from launch_validators import RecipientAnchorsSemanticValidator

router = APIRouter(prefix="/launch/v1")

@router.post("/anchors/validate")
async def validate_anchors(anchors_payload: dict) -> dict:
    """Validates recipient anchors. Returns issues + verdict."""
    try:
        anchors = RecipientAnchorsV1.model_validate(anchors_payload)
    except ValidationError as e:
        return {
            "is_valid": False,
            "field_errors": e.errors(),
            "semantic_issues": [],
        }

    semantic_validator = RecipientAnchorsSemanticValidator()
    issues = semantic_validator.validate(anchors)

    return {
        "is_valid": len([i for i in issues if i.severity == "error"]) == 0,
        "field_errors": [],
        "semantic_issues": [i.model_dump() for i in issues],
        "verdict": determine_anchors_verdict(anchors, issues),
    }
```

---

## Section 6: UI Hints / Tooltips (per field)

| Field | Tooltip text |
|---|---|
| `market_size_rub` | "Общий объём всей категории в рублях за год. Если нет точных данных - оценка через DSM Group / Mediascope." |
| `planned_share_pct` | "Доля рынка к концу 1-го года после запуска. Не путать с долей голоса (SoV)." |
| `distribution_target_pct` | "Целевая численная дистрибуция (% торговых точек). Реалистичная для нового бренда: 30-60% за 12-24 нед." |
| `sov_planned_pct` | "Доля голоса = ваш медиа-бюджет / общий медиа-бюджет категории. Excess SoV theory: для роста SoV должна быть выше market share." |
| `pricing_index_vs_proxy` | "Цена вашего бренда / цена прокси. 1.0 = такая же цена. 0.7 = на 30% дешевле. 1.5 = на 50% дороже." |
| `category_trend` | "Растёт = +5% и более год к году. Стабилен = ±5%. Снижается = -5% и более." |
| `creative_quality_benchmark` | "Если есть pre-test (Kantar Link / Ipsos copytest) - значение 0..1. Если нет - оставьте пустым (Aurora примет нейтральное значение)." |
| `competitive_response_assumption` | "Passive = конкуренты не реагируют. Moderate = увеличивают бюджет на 10-30%. Aggressive = на 50%+ или контр-кампания." |

---

## Связанные документы

- `DATA_REQUIREMENTS.md` - master spec (Section 3.1)
- `recipient_anchors_v1.schema.json` - JSON Schema SSoT
- `DSM_FIELDS.md` - proxy data
- `MEDIASCOPE_FIELDS.md` - proxy media
- `../00_Overview/PRINCIPLES.md` - P3 (что переносим / что recipient anchors дают)
- `../03_Architecture/UX_PRINCIPLES.md` - real-time feedback design
