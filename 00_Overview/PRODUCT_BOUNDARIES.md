# Aurora Launch - Product Boundaries

**Status:** v1.0 (2026-05-04)
**Authority:** P8 в `PRINCIPLES.md`

## Что Aurora Launch покрывает

### KPI scope: Sales only

- ✅ **Sales forecast** - объёмы продаж (рубли + единицы) с CI
- ✅ **Sales decomposition** - вклад каждого медиаканала + baseline + сезонность
- ✅ **Budget optimization** - оптимальная аллокация planned launch budget
- ✅ **Sensitivity analysis** - как forecast меняется при ±20% допущениях

### Use cases scope

- ✅ **Use case 1: Новый бренд** - zero history sales, zero history media
  - Recipient собирает: market_size, planned_share, distribution_target, SoV plan, media plan, pricing
  - Прокси: близкий competitor с full DSM + Mediascope history (24+ months)

- ✅ **Use case 2: Бренд с длительной паузой** - есть organic baseline продаж, нет рекламы давно (12+ months)
  - Recipient собирает: организический baseline (DSM history), planned media, anchors
  - Прокси: similar в категории с recent media activity

### Forecast horizon scope

- ✅ **12 weeks** (immediate launch, tight CI)
- ✅ **26 weeks** (6-month ramp, medium CI)
- ✅ **52 weeks** (year planning, wider CI)
- ❌ **>52 weeks** - не покрываем (uncertainty слишком большая, разумного value уже нет)

### Output formats scope

- ✅ **PPTX** - 8-section premium report (через aurora_pptx)
- ✅ **HTML** - interactive report (через aurora_html)
- ✅ **XLSX** - data drill-down (через Rust XLSX writer)
- ✅ **PDF Methodology Certificate** - signed audit document (через WeasyPrint)
- ❌ **Live API** - не покрываем (offline desktop product)

### Platform scope (Phase B)

- ✅ **Windows 10/11 64-bit** - primary target
- ❌ **macOS / Linux** - Phase D consideration (после Suite Bundle stabilization Phase C)
- WebView2 runtime обязателен на client machine

---

## Что Aurora Launch НЕ покрывает (находится в других продуктах)

### Awareness modeling -> Aurora Brand

- Awareness ramp-up forecast
- Brand-to-Sales bridge (joint two-stage Bayesian)
- Long-term brand effects decomposition (Binet-Field 60/40)
- Weibull adstock для long-horizon awareness
- Dual-posterior pickle schema

**Why separated:**
- Awareness = primary KPI первые 6-12 нед launch'а, но требует **отдельной math** (Weibull, dual-posterior)
- CFO/CMO conversation = разный sales motion (Brand =premium "защита бренда перед finance")
- Если клиент хочет и launch sales и awareness -> покупает Suite bundle (Launch + Brand)

**Cross-product flow:**
- Если в Aurora Launch клиент replyает "нужно показать как реклама строит знание для CFO" -> UI suggest "это Aurora Brand, открыть?"

### Portfolio launches (NEW SKU в существующем портфеле) -> Aurora Optimize

- Новый flavor / variant в established линейке
- Cannibalization analysis между SKU
- Halo effects от лидера на остальную линейку
- Multi-output Bayesian (SUR / VAR / multi-output GP) - в Aurora Portfolio Phase D

**Why separated:**
- Portfolio launches **есть данные** (по другим SKU) - это standard MMM use case с New SKU extension
- Aurora Optimize "New SKU workflow" использует transfer от sister-SKU, не от внешнего прокси
- Multi-output mathematics - другая ветвь, не для Launch

**Cross-product flow:**
- Discovery questionnaire в onboarding: "Это полностью новый бренд или новый SKU в портфеле?"
- Если NEW SKU -> redirect к Aurora Optimize

### Established brand optimization -> Aurora Optimize

- Бренд с собственной MMM-историей (12+ months media + sales)
- Re-allocation existing budget
- Scenario / what-if standard

**Why separated:**
- У Optimize клиента **есть данные** для standard MMM - не нужен прокси transfer
- Optimize workflow: Import -> Validate -> Model -> Decompose -> Optimize -> Report (без Proxy/Adapt steps)
- Дешевле в pricing (200-500k vs 1.5-3M Launch) - правильно для агентств с большим volume

### Pricing optimization -> Aurora Pricing (Phase C)

- Price elasticity per SKU
- Cross-price elasticity vs конкуренты
- Profit Optimum (margin × volume)

### Promo effectiveness -> Aurora Promo (Phase C)

- Net incremental decomposition
- Forward-buy adjustment
- Calendar Optimization

### Multi-tenant agency workspace -> Phase D

- Не в Launch до Phase D
- В Phase D Multi-tenant Data Studio для агентского workflow

---

## Decision Tree для Sales

Антон (или Customer expert) задаёт клиенту 3 вопроса:

### Q1: Есть ли у вас собственная MMM-история по этому бренду (12+ месяцев media + sales)?

- **Yes** -> Q2 (Optimize / Brand path)
- **No** -> Q3 (Launch / Optimize-NewSKU path)

### Q2: Какой основной интерес?

- "Оптимизировать существующий бюджет" -> **Aurora Optimize**
- "Защитить ATL/brand investments перед CFO" -> **Aurora Brand**
- "Оптимизировать промо vs ATL" -> **Aurora Promo** (Phase C)
- "Найти оптимальную цену" -> **Aurora Pricing** (Phase C)
- "Все из перечисленного" -> **Aurora Suite Bundle**

### Q3: Это новый бренд / категория или новый SKU в существующем портфеле?

- "Полностью новый бренд (или бренд с длинной паузой)" -> **Aurora Launch**
- "Новый SKU в существующем портфеле (есть данные по другим SKU)" -> **Aurora Optimize** + New SKU workflow
- "Не уверен" -> Discovery call с Антоном для детального discovery

---

## Cross-Product Handoff Scenarios

### Scenario 1: Launch -> Optimize transition (~12 месяцев post-launch)

После 12+ месяцев accumulated recipient data:
- Aurora Launch posterior weight schedule достигает >=90% recipient / <=10% proxy (proxy release threshold per ADR-004)
- Proxy в priors only, model fully recipient-driven
- **Transition opportunity**: client может switch на Aurora Optimize standard
- Aurora Launch project file (.aurora) opens в Optimize seamlessly (shared schema)
- Pricing: client остаётся на Suite bundle или downgrade на Optimize-only

**UX:** в Aurora Launch UI после T=40+ нед: banner "Ваш бренд готов к standard MMM. Перейти на Aurora Optimize?"

### Scenario 2: Launch + Brand bundle (parallel use)

Клиент запускает новый продукт:
- Aurora Launch - sales forecast
- Aurora Brand - awareness ramp + Brand-to-Sales bridge
- **Shared dataset** через Suite bundle Data Studio
- Cross-app reports: combined Launch + Brand отчёт (одна story)

### Scenario 3: Launch -> Pricing (Phase C+)

После launch'а established данные позволяют:
- Aurora Launch продолжает posterior updates
- Aurora Pricing анализирует price elasticity using accumulated data
- Combined recommendation: optimal price + optimal media mix

---

## Anti-patterns (что НЕ делать)

### Anti-pattern 1: "Только Launch достаточно"

Если клиент launchает новый бренд **с big awareness ambition** ("должны узнать все") - **Launch alone insufficient**. Нужен Brand для awareness modeling. Honest sales: предложить Launch + Brand (Suite bundle).

### Anti-pattern 2: "Launch для existing brand"

Если у клиента **есть данные** (даже короткие, 6-9 месяцев) - не Launch, а **Optimize с small-data tools** (OLS fallback + horseshoe priors из Sprint 2 v1.0.16). Launch для **zero/long-pause** только.

### Anti-pattern 3: "Launch для multi-SKU portfolio"

Multi-SKU = Aurora Optimize + New SKU workflow или Aurora Portfolio (Phase D). Launch single-SKU.

### Anti-pattern 4: "Launch без consulting hours"

Aurora Launch = assisted product (P6). Если клиент категорически отказывается от proxy review session с экспертом - **decline sale**. Self-serve Launch = guaranteed bad outcome (wrong proxy, wrong anchors, broken trust).

---

## Pricing Boundaries

| Tier | Price (rangeable) | Includes |
|---|---|---|
| **Starter** | 1.5M / год | Unlimited launches + 20h consulting |
| **Pro** | 2.5M / год | Unlimited launches + 30h consulting + priority support |
| **Enterprise** | 3M+ / год | Unlimited + 40h + custom training + on-site session |

Финал pricing tier - в S009 (до Sprint B4).

**Free trial:** 30/60/90 дней (S009 finalize). Pilot first launch может быть free с case study consent.

---

## Конкурентный landscape (recap)

| Сегмент | Aurora Launch положение |
|---|---|
| **Excel + Python** (free, manual) | Aurora replaces для NEW launches без data |
| **Nielsen BASES** (5-15M / launch) | Aurora 1.5-3M / год = 5-10× cheaper |
| **Kantar / Ipsos консалтинг** (1-3M per project) | Aurora subscription = better unit economics |
| **In-house эконометрист** (1.5M / project) | Aurora = continuous tooling vs one-shot work |

**Unique:** в РФ нет аналогов в Aurora Launch ценовом сегменте для launch use case.

---

## Связанные документы

- `PRINCIPLES.md` (P8) - boundaries как принцип
- `ROADMAP.md` - sprints implement boundaries
- `02_Data_Spec/DATA_REQUIREMENTS.md` - что нужно для каждого use case
- `05_Sessions/SESSION_NEXT_QUESTIONS.md` - S009 (Pricing) + S010 (Sales playbook)
