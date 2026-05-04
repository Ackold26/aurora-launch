# Aurora Launch - Multi-Proxy UX Decision Rules

**Status:** Accepted (S007 closed 2026-05-04)
**Authority:** P7 в `00_Overview/PRINCIPLES.md` (Single-proxy default + multi-proxy expert toggle)
**Sprint context:** Sprint B2 implementation reference
**Owner:** Антон (domain expert) + Маша (UX design)

## Контекст

P7 declares: UI default = single-proxy, multi-proxy = power-user feature через explicit toggle. Этот документ финализирует:

1. Decision rules **когда** включать multi-proxy (decision tree)
2. Когда **не** включать (anti-patterns)
3. Weight assignment UX (default + manual sliders)
4. N bounds (min 2, max 3 proxies)
5. UI form layout (tabs + pooling sidebar + combined aggregate panel)
6. Integration с similarity framework (S003)
7. Inline hints + tooltip texts
8. Anti-patterns

Sprint B2 implements `ProxySelectionStep.svelte` per этот документ.

---

## 1. Decision Tree (когда включать multi-proxy)

Пять **trigger conditions**. Если ≥ 1 condition true → consider multi-proxy. Если ≥ 2 trigger conditions → strongly recommend.

### 1.1 Trigger 1: Volatile category leader

**Signal:** SoV (share of voice) у category leader varies > 50% месяц-к-месяцу за last 12 months. Or recent ownership / branding change (<12 месяцев).

**Why multi-proxy helps:** один volatile proxy дает unstable structural priors. Average across stable peer brands → robust transfer.

**Detection (Phase B Sprint B2):**
- Manual: эксперт знает категорию, видит volatility
- Phase C+: AI hint "category leader's SoV CV is high - consider multi-proxy"

### 1.2 Trigger 2: No clear single proxy

**Signal:** several plausible proxies have similar similarity scores (top-2 within 0.05 difference).

**Why multi-proxy helps:** instead of arbitrary choice between candidates, combine их structural signals weighted.

**Detection:** UI computes similarity для multiple candidate proxies (user adds 2-3 в sidebar list, similarity computed на каждом). If no clear winner - suggest multi-proxy mode.

### 1.3 Trigger 3: Categorical heterogeneity

**Signal:** sub-category includes meaningfully different brands. Examples:
- FMCG snacks: chips vs nuts vs popcorn vs crackers - very different adstock patterns
- OTC pharma: cold-flu category mixes Rx-like (Кагоцел) и nutraceutical (Vitamin D) - different consumer behavior
- Premium cosmetics: luxury vs masstige vs aspirational - different media playbook

**Why multi-proxy helps:** select 2-3 proxies covering different "modes" of category, partial pooling lets recipient inherit averaged shape.

### 1.4 Trigger 4: High-stakes launch

**Signal:** launch media plan total budget >= 5M ₽ or strategic significance (CFO presentation expected).

**Why multi-proxy helps:** robustness против outlier dependency. If one proxy turns out to be misleading - others provide ballast. Reduces "single proxy risk".

**Cost trade-off:** multi-proxy training is 2-3× slower (audit performance budget). Acceptable для high-stakes if extra confidence justified.

### 1.5 Trigger 5: Sensitivity analysis demand

**Signal:** client / эксперт wants explicit sensitivity ("what if proxy A vs proxy B is right?"). Multi-proxy with weighted averaging naturally provides это.

**Why multi-proxy helps:** quantify how forecast moves under different proxy assumptions без переобучения per scenario.

### 1.6 Decision tree visual (UI tooltip)

```
Recipient ready, similarity computed для 1+ candidates.

╔══════════════════════════════════════════════════════════╗
║ Use SINGLE PROXY (default) когда:                        ║
║   - Один proxy явно лидирует (S>=0.85, next best <0.7)   ║
║   - Стабильная категория, понятный peer set             ║
║   - Time-pressed launch (training time critical)         ║
╚══════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════╗
║ Use MULTI-PROXY (expert toggle) когда:                   ║
║   - Volatile category leader (SoV CV > 50%)              ║
║   - No clear single proxy (top-2 within 0.05)            ║
║   - Heterogeneous sub-category                           ║
║   - High-stakes launch (>= 5M budget)                    ║
║   - Sensitivity analysis demand                          ║
╚══════════════════════════════════════════════════════════╝
```

---

## 2. Когда НЕ включать multi-proxy (Anti-Patterns)

### 2.1 Anti-pattern: "Multi-proxy fixes bad data"

❌ Recipient is mismatched к category, single best proxy is только S=0.4 → switching на multi-proxy с 2 weak candidates won't help. Each candidate имеет low S, weighted average не magic.

✅ Correct action: search для better proxy. If none exists - block forecast (Insufficient verdict) или используй category-level prior fallback (Phase D feature).

### 2.2 Anti-pattern: "More proxies = better"

❌ User adds 3 proxies все с S=0.85 same category. Multi-proxy training adds 5% inflation penalty (см. SIMILARITY_FRAMEWORK Section 6). Marginal benefit minimal.

✅ Correct action: single proxy (best of 3) + sensitivity analysis (re-run с alternative proxies, compare).

### 2.3 Anti-pattern: "Multi-proxy для time pressure"

❌ Launch in 2 weeks, training time matters → multi-proxy doubles training time (~30s → ~90s).

✅ Correct action: single proxy + simpler workflow.

### 2.4 Anti-pattern: "Multi-proxy без understanding"

❌ Client просит "use multi-proxy because more is better" не understanding it.

✅ Correct action: эксперт объясняет trade-off + decision rules. Client может accept single-proxy с full transparency.

---

## 3. Weight Assignment UX

### 3.1 Default: Equal Weights

При включении multi-proxy mode, weights auto-set к equal (1/N each):
- N=2: 50% / 50%
- N=3: 33.3% / 33.3% / 33.3%

**Rationale:** absent strong reason to favor one, equal weights = most agnostic.

### 3.2 Manual Override

UI: 6 sliders (one per proxy slot used) с auto-rebalance constraint sum=100%.

**Interaction model:**
- User drags Proxy 1 slider от 50% к 70%
- Proxy 2 (and 3 if N=3) auto-rebalance proportionally к sum 30% (e.g., 50% → 30% если N=2)
- "Reset to equal" button restores defaults

**Visual:**
```
Pooling Weights:
  Proxy 1: ▓▓▓▓▓▓▓▓░░ 70%
  Proxy 2: ▓▓▓░░░░░░░ 30%
  [Reset to equal]
```

### 3.3 Weight Suggestions (Phase C+)

**Phase B:** equal default + manual.

**Phase C+ AI suggestion:** based on individual S_proxy values:
```python
suggested_weight_p = S_proxy_p / sum(S_proxy_i for i in proxies)
```

Higher individual similarity → larger pooling weight. UI shows "Suggested" вместо "Reset to equal" если AI suggestion enabled.

---

## 4. N Bounds (Number of Proxies)

### 4.1 Minimum: N = 2

Если user wants single = use single-proxy mode (different engine - `single_proxy_transfer.py`). N=1 в multi-proxy mode = mathematical degeneracy (hierarchical with single group).

### 4.2 Maximum: N = 3

**Cost:**
- Training time scales linearly + hierarchical sampler overhead. N=2 ~2× single, N=3 ~2.5×.
- UI complexity (3 tabs + sidebar) - manageable. 4 tabs - cluttered.
- Marginal benefit beyond N=3 minimal (covariance matrix gains shrink quickly).

### 4.3 N=2 Recommended Default для multi-proxy

Когда user toggles multi-proxy mode, default N=2 (Tab "Proxy 1" + "Proxy 2" + "Add Proxy" button).

User clicks "+ Add Proxy" → N=3, "Add Proxy" button replaced with "Cannot add more (max 3)".

---

## 5. UI Form Layout

### 5.1 Multi-Proxy Mode Toggle Position

В верху ProxySelectionStep, выше form:
```
[Single Proxy] [● Multi-Proxy (expert)]   ⓘ
```

**Tooltip on toggle:**
> Multi-proxy полезно для volatile categories или когда несколько equally-good кандидатов.
> [Когда использовать multi-proxy →]  (ссылка к decision tree в help)

### 5.2 Single-Proxy Layout (default)

```
┌─────────────────────────────────────────────────┐
│  [Single ●] [Multi-Proxy] ⓘ                     │
├─────────────────────────────────────────────────┤
│  Proxy Brand: [Кагоцел ▼]                       │
│  ┌───────────────────────────────────────┐     │
│  │ Upload DSM Group data:                │     │
│  │ [📂 Drag .xlsx file here or click]   │     │
│  │                                       │     │
│  │ Upload Mediascope TV:                 │     │
│  │ [📂 Drag .xlsx file here or click]   │     │
│  │                                       │     │
│  │ Upload Mediascope Digital (optional): │     │
│  │ [📂 Drag .xlsx file here or click]   │     │
│  └───────────────────────────────────────┘     │
│                                                 │
│  Similarity Dimensions:                         │
│  Category:        [OTC.cold_flu.antiviral ▼]   │
│  Pricing tier:    [MAINSTREAM ▼]               │
│  Brand size:      [LEADER ▼]                   │
│  Distribution:    [NATIONAL ▼]                 │
│  Media maturity:  [PULSING ▼]                  │
│  Lifecycle:       [MATURE ▼]                   │
│                                                 │
│  ┌───────────────────────────────────────┐     │
│  │  📊 Similarity Radar (live update)    │     │
│  │     S = 0.70 (Medium)                 │     │
│  │     [radar chart hex]                 │     │
│  └───────────────────────────────────────┘     │
│                                                 │
│  Verdict: Medium (Inflation 1.5×) 🟡           │
│  [Continue to Anchors →]                       │
└─────────────────────────────────────────────────┘
```

### 5.3 Multi-Proxy Layout (expert toggle ON)

```
┌─────────────────────────────────────────────────┐
│  [Single] [● Multi-Proxy (expert)] ⓘ           │
├─────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────────┐    │
│  │ Proxy 1 ✓│ │ Proxy 2 ⚠│ │ + Add Proxy  │    │
│  └──────────┘ └──────────┘ └──────────────┘    │
│  ┌─────────────────────────────────────────┐    │
│  │ [Tab: Proxy 1 active]                   │    │
│  │ Brand: [Кагоцел ▼]                      │    │
│  │ Upload DSM ↓ ✓                          │    │
│  │ Upload Mediascope TV ↓ ✓                │    │
│  │ Similarity Dimensions [...] [↻ Live]    │    │
│  │ S = 0.78 (Medium)                       │    │
│  │ [small radar]                           │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│ ╔═══════════════════════════════════════════╗  │
│ ║ Pooling Weights:                          ║  │
│ ║   Proxy 1 [Кагоцел]:      ▓▓▓▓▓░ 50%     ║  │
│ ║   Proxy 2 [Арбидол]:      ▓▓▓▓▓░ 50%     ║  │
│ ║   [Reset to equal]                        ║  │
│ ║                                           ║  │
│ ║ Combined Aggregate:                       ║  │
│ ║   S_combined = 0.74 (Medium)              ║  │
│ ║   Inflation 1.575× (1.5 × 1.05 multi)    ║  │
│ ║   ⚠ Spread 0.10 between proxies          ║  │
│ ╚═══════════════════════════════════════════╝  │
│                                                 │
│  [Continue to Anchors →]                       │
└─────────────────────────────────────────────────┘
```

### 5.4 Tab Indicators

- **✓** (green check) - all data uploaded, similarity computed, S >= 0.65
- **⚠** (yellow warning) - data uploaded, S between 0.50-0.65 (Low verdict)
- **❌** (red error) - data missing or S < 0.50

### 5.5 Combined Aggregate Panel (sticky sidebar)

Always visible на правой стороне screen, even при scrolling per-proxy form:

```
╔════════════════════════════════╗
║ COMBINED AGGREGATE              ║
║                                 ║
║ S_multi = 0.74 (Medium) 🥈      ║
║ Inflation: 1.575× (1.5 + multi  ║
║   penalty 5%)                   ║
║                                 ║
║ Per-proxy:                      ║
║   #1 S=0.78 weight 50%          ║
║   #2 S=0.68 weight 50%          ║
║                                 ║
║ Warnings:                       ║
║   • Spread 0.10 - heterogeneous ║
║                                 ║
║ Estimated training time:        ║
║   ~85 seconds (multi-proxy)     ║
╚════════════════════════════════╝
```

---

## 6. Integration со Similarity Framework (S003)

### 6.1 Per-proxy similarity computation

Each proxy slot uses S003 framework:
- 6 dimensions
- Category-specific weight profile (auto-loaded from recipient's L1/L2)
- Verdict tier per individual proxy

### 6.2 Combined aggregate computation

См. `02_Data_Spec/SIMILARITY_FRAMEWORK.md` Section 6 - `compute_multi_proxy_aggregate(proxy_similarities, pooling_weights)`.

### 6.3 Inflation factor

Multi-proxy inflation = base inflation (по combined S) × multi penalty (1 + 0.05 × (N-1)):
- N=2: base × 1.05
- N=3: base × 1.10

### 6.4 Floor warnings

Per-proxy floors apply individually:
- Если individual S < 0.5 → red badge на tab + warning в combined panel
- Если spread (max - min) > 0.3 → yellow warning "heterogeneous proxies, expect wider CI"

---

## 7. Inline Hints + Tooltip Texts

### 7.1 Hint когда expert NOT toggled multi yet

Если recipient enters category где multi-proxy commonly helpful (e.g., FMCG snacks, premium cosmetics) - sidebar suggestion:

```
💡 Suggestion: эта категория иногда лучше моделируется
   с multi-proxy (heterogeneous sub-category).
   [Toggle Multi-Proxy mode →]
   [Не показывать снова в этой категории]
```

(Phase C+ AI feature - Phase B static rules в category metadata.)

### 7.2 Warning if user toggles multi с very similar proxies

```
⚠ Прокси 1 (Кагоцел) и Прокси 2 (Арбидол)
   имеют между собой similarity 0.92 (very similar).
   
   Multi-proxy mode добавляет 5% inflation penalty.
   Single proxy + sensitivity analysis может быть
   достаточным.
   
   [Continue with multi]  [Switch to single]
```

### 7.3 Tooltip on Pooling Weights

```
Веса определяют как Aurora комбинирует structural priors из proxies:
- Каждый proxy contributes weighted average к recipient priors
- Proxy с весом 70% оказывает 70% влияния на adstock + hill shapes
- Magnitudes (β, baseline) восстанавливаются от recipient anchors
- Sum весов = 100%
```

### 7.4 Tooltip on Combined Aggregate

```
Combined similarity:
- Aggregate score = weighted average S × pooling_weight
- Verdict + inflation = same thresholds как single proxy
- Multi-proxy adds ~5% inflation per extra proxy (model averaging variance)
- Warnings if individual proxies weak или heterogeneous
```

---

## 8. Worked Examples

### 8.1 Example: 2-proxy OTC antiviral launch

**Recipient:** new premium OTC antiviral, NEW lifecycle, planned ALWAYS-ON TV+digital.

**Decision:** эксперт видит volatility в OTC antiviral leader's SoV (промо seasons). Triggers Trigger 1 (volatile category leader). Toggles multi-proxy.

**Proxy 1: Кагоцел** (mainstream, leader, pulsing).
- Similarity: 0.78 (Medium)

**Proxy 2: Арбидол** (mainstream, challenger, pulsing).
- Similarity: 0.68 (Medium)

**Pooling weights:** equal default 50/50.

**Combined:** S=0.73 (Medium). Inflation 1.575× (base 1.5 × multi penalty 1.05).

Combined aggregate panel shows:
- "Medium combined verdict"
- Both proxies validated, ready for transfer
- Estimated training: ~85s

User proceeds к Anchors step.

### 8.2 Example: Heterogeneous FMCG snacks (3-proxy)

**Recipient:** new premium kale chips, NEW, niche, premium pricing.

**Decision:** эксперт видит heterogeneity в snacks_savoury (chips vs crackers vs nuts). Triggers Trigger 3 (categorical heterogeneity). 3-proxy.

**Proxy 1: Lay's Premium chips** S=0.82
**Proxy 2: Lorenz Crunchips** (premium chips European) S=0.75
**Proxy 3: artisan kale brand** S=0.65

**Pooling weights:** 40 / 40 / 20 (manual: эксперт хочет larger weight на 1+2 как ближе к premium chips category).

**Combined:** S = 0.40×0.82 + 0.40×0.75 + 0.20×0.65 = 0.758 (Medium).
**Inflation:** 1.5 × (1 + 0.05 × 2) = 1.65×.

Warnings: spread 0.17 (within tolerance, no warning). All proxies above 0.5 floor.

**User proceeds.**

### 8.3 Example: User attempts multi с too-similar proxies (warning)

**Recipient:** new premium yogurt.
**Proxy 1:** Activia premium S=0.82.
**Proxy 2:** Danone Tema S=0.81.

**Detection:** между Proxy 1 и Proxy 2 similarity 0.94 (computed на лету).

**UI warning shown** (Section 7.2). User accepts trade-off, continues с multi-proxy. Fine.

Alternative: user clicks "Switch to single" → mode change, Proxy 2 data preserved as "candidate for sensitivity analysis" в side panel.

---

## 9. Anti-Patterns Summary

| ❌ Don't | ✅ Do instead |
|---|---|
| Multi-proxy с 2-3 weak (S<0.5) candidates | Find better single proxy. If none - block forecast |
| 3 nearly-identical proxies | Single best + sensitivity analysis в side panel |
| Multi-proxy для time-pressed launch | Single proxy + add multi later via posterior update |
| User-initiated multi without expert review | Consulting hours review session перед locking decision |
| Equal weights когда clearly один proxy лучше | Manual weights (e.g., 70/20/10) или single + sensitivity |

---

## 10. Implementation Notes (Sprint B2)

### 10.1 Files

**New components:**
- `src/lib/components/ProxySelectionStep.svelte` - main step (single + multi mode)
- `src/lib/components/ProxyTabs.svelte` - tabs для multi-proxy
- `src/lib/components/ProxyForm.svelte` - per-proxy form (used inside tab или standalone)
- `src/lib/components/PoolingWeightsSidebar.svelte` - sliders + reset
- `src/lib/components/CombinedAggregatePanel.svelte` - sticky sidebar
- `src/lib/components/SimilarityRadarChart.svelte` - per-proxy + combined views

**Backend endpoints:**
- `/launch/v1/similarity/compute` - per-proxy compute (already в DATA_REQUIREMENTS Section 7.2)
- `/launch/v1/similarity/compute_multi` - combined aggregate

**WASM:**
- `src-rust/similarity_wasm/` - same logic как single proxy, executes per-proxy в loop + multi aggregation

### 10.2 State management (Svelte 5 runes)

```typescript
// $state - mode toggle
let proxyMode = $state<"single" | "multi">("single");

// $state - per-proxy data
let proxies = $state<ProxyData[]>([
    { brandName: "", category: null, ..., similarity: null }
]);

// $state - pooling weights (auto-equal until manual)
let poolingWeights = $state<number[]>([1.0]);  // single
// При toggle multi: poolingWeights = [0.5, 0.5]

// $derived - combined aggregate
let combinedAggregate = $derived(() => {
    if (proxyMode === "single") return proxies[0]?.similarity?.s_aggregate;
    return computeMultiProxyAggregate(
        proxies.map(p => p.similarity.s_aggregate),
        poolingWeights
    );
});
```

### 10.3 Tests (Sprint B2)

**Unit:**
- `tests/unit/test_multi_proxy_aggregate.py` - 2-proxy, 3-proxy combinations + warnings
- `tests/unit/test_pooling_weights.py` - rebalance logic (auto-rebalance when slider moved)

**Component (Vitest + Svelte Testing Library):**
- `tests/component/proxy_selection_single.test.ts` - single mode flow
- `tests/component/proxy_selection_multi.test.ts` - multi mode toggle, tab navigation, sliders
- `tests/component/multi_proxy_warnings.test.ts` - too-similar warning, weak-proxy warning

**E2E (Playwright Sprint B6):**
- Toggle multi → fill 2 proxies → see combined aggregate update in real time → проceed к anchors

---

## 11. Связанные документы

- `../00_Overview/PRINCIPLES.md` - P7 (Single-proxy default + multi-proxy expert)
- `../02_Data_Spec/SIMILARITY_FRAMEWORK.md` (S003) - per-proxy + multi aggregation formula
- `../02_Data_Spec/DATA_REQUIREMENTS.md` Section 7.1 - UI flow
- `../03_Architecture/MATH_REFERENCE.md` Section 3.2 - hierarchical multi-proxy math
- `../03_Architecture/REUSE_FROM_ECONOMETRICA.md` Section 3.1 - two engines (single_proxy_transfer + multi_proxy_hierarchical)
- `../03_Architecture/UX_PRINCIPLES.md` (если existing - C3 similarity radar) - связь
- `../05_Sessions/SESSION_NEXT_QUESTIONS.md` - S007 + S003 closed
