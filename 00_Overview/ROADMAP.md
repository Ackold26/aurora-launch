# Aurora Launch - Roadmap

**Status:** v1.1 (post-audit, 2026-05-04)
**Supersedes:** v1.0 plan from concept session 001

## Контекст

Aurora Launch - продукт Phase B Aurora Analytics Suite (см. `project_econometrica_roadmap_v3.md`). №1 priority в Phase B. Срок: **~7-8 недель** dev'а после Phase A platform foundation готова (revised post-audit 2026-05-04 - sequential dependencies + parallel B1.5 не сокращает critical path).

Этот roadmap описывает Phase B детально + связь с Phase A зависимостями + Phase C+ ecosystem.

---

## Зависимости от Aurora Platform (Phase A)

Aurora Launch не стартует до завершения Phase A:

| Компонент | Phase A deliverable | Аналог в Econometrica | Critical для Launch |
|---|---|---|---|
| Inference Core | extracted MMM engine с моделями registry | `engines/modeler.py` | YES - shared math |
| Data Studio | DSM/Mediascope importers + format adapters | sidecar import endpoints | YES - data ingestion |
| Workflow Engine | config-driven pipeline | hardcoded pipeline | YES - launch.workflow.yaml |
| Tauri shell template | boilerplate для fast spawn | `Aurora_Econometrica/` | YES - shell |
| Trust 3 Hierarchical | hierarchical Bayesian priors | `engines/modeler.py` v1.0.16 | YES (shipped) |
| Common Services | Auth + License + Updates shared | per-app duplication | YES |
| **cross_app_license** (added audit) | License key open multiple Suite apps | Econometrica own license | YES (subscription) |
| **schema_registry** (added audit) | Centralized pickle version migrations | ad-hoc per engine | YES (BC compat) |

**Принцип:** Aurora Launch не стартует до Phase A complete. Иначе - merge ад при параллельной разработке.

---

## Phase B Sprints (август-сентябрь 2026)

**Total:** **~7-8 недель** dev'а (revised post-audit 2026-05-04: sequential dependencies B0.5 → B1 → B2 → B3 → B4 → B5 → B6 plus B1.5 parallel с B1).

### Sprint B0: Concept Finalization ✅ DONE 2026-05-04

**Длительность:** 1 day
**Deliverables:**
- 10 принципов в `00_Overview/PRINCIPLES.md`
- Roadmap (этот файл)
- Product boundaries
- Data Requirements Spec (4 файла + JSON Schema)
- Architecture docs (5 файлов: Reuse, Test Strategy, UX, Data Privacy, Performance Budgets)
- Session 001 log + next questions
- Memory entry

**Status:** COMPLETE.

### Sprint B0.5: BC Test Corpus & Format Adapters (1 неделя) - ADDED AFTER AUDIT

**Goal:** ensure backwards compatibility + multi-version data ingestion before schema changes.

**Deliverables:**
- 10+ старых .aurora projects corpus (Кагоцел, Венарус, synthetic) с описаниями каждого case
- Parametrized pytest на каждый corpus item
- Format adapters: `DsmFormatAdapterV2023`, `V2024`, `V2025` + auto-detection logic
- Plug-in architecture skeleton: abstract `ProxyDataSource` interface
- CI gate: schema changes без BC test pass = blocked

**Why:** обнаружено в audit (A2, A3) - формат меняется год от года, BC tests insufficient в исходном плане.

### Sprint B1: Pickle Schema Extension + Schema Registry (1 неделя)

**Goal:** schema готова к Launch features + migration path safe.

**Deliverables:**
- `engines/schema_registry.py` - centralized version migrations
- Pickle schema v3.0 с additive полями:
  - `proxy_brand_metadata` (similarity scores, dimensions, source)
  - `transfer_provenance` (что переносится, какие versions)
  - `recipient_anchors` (validated через Pydantic)
  - `forecast_horizons` (12/26/52 weeks с CI per horizon)
- Pydantic v2 models для всех schemas (auto JSON Schema export)
- KPI registry дополнение для launch use case (sales-only)
- BC tests against B0.5 corpus PASS

**Decision DONE S005a (2026-05-04):** ADR-002 - `.aurora` = ZIP archive container (Option D), не SQLite hybrid. См. `03_Architecture/decisions/ADR-002-storage-layer.md` + finalized `03_Architecture/SCHEMA_DESIGN.md`.

### Sprint B1.5: Customer Success Lite (3 дня, parallel с B1) - ADDED AFTER AUDIT

**Goal:** consulting hours tracker от старта Phase B.

**Deliverables:**
- SQLite local table `consulting_log`
- Auto-log session events (proxy review, posterior update, methodology question)
- Hours tracker UI (sidebar widget)
- CSV export для billing

**Why:** subscription pricing требует hour tracking сразу, не в Phase C (audit A14).

### Sprint B2: Proxy Selection Cabinet UI (1.5 недели)

**Goal:** клиент может выбрать прокси и заполнить similarity scores.

**Prerequisites (all DONE 2026-05-04):**
- ✅ S003 Similarity Framework - `02_Data_Spec/SIMILARITY_FRAMEWORK.md`
- ✅ S007 Multi-proxy UX - `01_Concept/MULTI_PROXY_UX_DECISION_RULES.md`

**Deliverables:**
- Svelte cabinet `ProxySelectionStep.svelte`:
  - Single-proxy mode (default): один проктси-бренд + 6 similarity dimensions
  - Multi-proxy mode (expert toggle): 2-3 прокси с partial pooling weights
- Live similarity radar chart (С3 в UX_PRINCIPLES)
- Quality stamp panel (similarity score, verdict, warnings)
- WASM module для real-time similarity calculation (audit B4)
- Confidence verdict: High / Medium / Low / Insufficient
- Block forecast generation если Insufficient
- Pydantic backend validation
- Vitest + Pytest integration tests

### Sprint B3: Adaptation Layer + Transfer Validation (2 недели)

**Goal:** recipient anchors собраны, transfer validated.

**Prerequisites (DONE 2026-05-04):**
- ✅ S004 Adaptation Rules - `03_Architecture/ADAPTATION_RULES.md` + ADR-003 (pre-train + transfer locked)

**Deliverables:**
- Cabinet `RecipientAnchorsStep.svelte` (form по anchors spec)
  - Pydantic validation client-side + server-side
  - SemanticValidator (cross-field rules: Excess SoV, distribution velocity, pricing extreme)
  - Real-time feedback (Svelte 5 runes derived stores)
- Adaptation engine `engines/launch_adapt.py`:
  - `extract_proxy_priors(model)` - извлечение adstock/hill shapes + uncertainty
  - `apply_recipient_magnitudes(priors, anchors)` - β/baseline rescale
- Transfer Validation step `TransferValidateStep.svelte`:
  - Prior predictive checks (visualize что forecast выглядит разумно)
  - Sensitivity analysis (как forecast меняется при ±20% similarity)
- Backend endpoints: `/launch/adapt`, `/launch/validate_transfer`
- Two engines: `single_proxy_transfer.py` + `multi_proxy_hierarchical.py` (audit A4)

### Sprint B4: Launch Forecast Report Template (1 неделя)

**Goal:** PPTX/HTML/XLSX отчёт launch-specific.

**Prerequisites (DONE 2026-05-04):**
- ✅ S006 Report Sections - `02_Data_Spec/REPORT_SECTIONS_SPEC.md` (8 sections + per-format + Methodology Certificate)
- ✅ S009 Pricing tier - `06_References/PRICING_TIERS.md` (Starter 1.5M / Pro 2.5M / Enterprise 3.5M + trials + discounts)

**Deliverables:**
- `aurora_pptx/launch_forecast/` - 8-section template:
  1. Cover (Aurora seal, project name, date, version)
  2. Executive Summary (key metrics, tier badge, CFO-friendly framing)
  3. Proxy Quality (similarity radar, dimensions table, confidence verdict)
  4. Transfer Caveats (что переносится / не переносится, uncertainty decomposition)
  5. Forecast 12 weeks (immediate launch, tight CI)
  6. Forecast 26 weeks (6-month ramp, medium CI)
  7. Forecast 52 weeks (year planning, wider CI)
  8. Methodology + References (academic citations, model card, hash signature)
- HTML version (через aurora_html shared adapter)
- XLSX version (через Rust XLSX writer)
- Methodology Certificate PDF generator (audit C10)

### Sprint B5: Posterior Update Workflow + Integration Testing (1 неделя)

**Goal:** клиент может re-fit модель с новыми recipient данными.

**Prerequisites (DONE 2026-05-04):**
- ✅ S005b Posterior Math design - `03_Architecture/POSTERIOR_UPDATE_DESIGN.md` + ADR-004 (ESS-based partial pooling + BMA fallback)
- ✅ S005a (storage architecture) - ADR-002 ZIP archive

**Deliverables:**
- `engines/launch_posterior_update.py` - partial pooling weight schedule
  - ESS-based weighting (Konstantinopoulos 2014)
  - BMA как промежуточный
  - Sensitivity testing на synthetic data
- UI flow: user uploads new recipient data -> sees pooling weight reduce
- Integration tests на synthetic data (proxy -> recipient transfer accuracy)
- Pilot dataset preparation
- Property-based tests (monotonic CI growth с horizon, consistent transfers)

### Sprint B6: Pilot Live-Test + Polish (1 неделя)

**Goal:** один pilot client отвалидировал end-to-end flow.

**Prerequisites (DONE 2026-05-04):**
- ✅ S008 Pilot Client Identification - `04_Sprints/PILOT_CLIENT_PLAN.md` (3 candidates × 3 categories + qualification + 12-week engagement plan)
- ✅ S010 Sales Playbook - `06_References/SALES_PLAYBOOK.md` (outreach + discovery + demo + conversion + onboarding + ops)

**Deliverables:**
- Pilot session с 1 фарма OTC или FMCG launch team
- Bug fixes по live-test findings
- Onboarding tour (Welcome experience, glossary, sample dataset)
- Templates library (FMCG Snacks, OTC Pharma, Premium Cosmetic, Energy Drink)
- Empty states + error states polish
- A11y audit (WCAG AA)
- Performance budget validation (audit A9: train ≤30s single, ≤90s multi-proxy N=3)
- Documentation для customer success
- v1.4.0 alpha-tag

---

## Q&A Sessions Roadmap (S002-S010)

Концептуальные сессии between sprints для finalize unresolved questions:

| Session ID | Тема | Когда | Status | Blocker для |
|---|---|---|---|---|
| S001 | Concept finalization (10 principles) | 2026-05-04 | DONE | - |
| S002 | Data Requirements Spec deep-dive (этой сессии Variant 2) | 2026-05-04 | DONE | - |
| S003 | Proxy Similarity Framework - 6 dimensions + scoring + weights + multi-aggregation | 2026-05-04 | ✅ DONE | ~~Sprint B2~~ resolved |
| S004 | Adaptation Rules detail - 5 shape params + magnitude calibration + cross-category matrix + ADR-003 pre-train | 2026-05-04 | ✅ DONE | ~~Sprint B3~~ resolved |
| **S005a** | **Storage Layer Decision: ZIP archive container (Option D)** | 2026-05-04 | ✅ DONE (ADR-002) | ~~Sprint B1~~ resolved |
| **S005b** | **Posterior Update math design** - ESS-based partial pooling + BMA fallback + drift adaptive | 2026-05-04 | ✅ DONE | ~~Sprint B5~~ resolved |
| S006 | Launch Forecast Report sections - 8 sections + per-format + Methodology Certificate WeasyPrint | 2026-05-04 | ✅ DONE | ~~Sprint B4~~ resolved |
| S007 | Multi-proxy UX - когда expert включает + decision rules + UI wireframe | 2026-05-04 | ✅ DONE | ~~Sprint B2~~ resolved |
| S008 | Pilot client identification - 3 parallel categories (Pharma/FMCG/Cosmetics), 3 candidates per category, Path B free pilot | 2026-05-04 | ✅ DONE | ~~Sprint B6~~ resolved |
| S009 | Pricing tier finalization - Starter 1.5M / Pro 2.5M / Enterprise 3.5M + trials + discounts | 2026-05-04 | ✅ DONE | ~~Sprint B4~~ resolved |
| S010 | Sales playbook - outreach + discovery + demo + conversion + onboarding + ops | 2026-05-04 | ✅ DONE | ~~Sprint B6~~ resolved |

**Note:** S005 разделена post-audit (2026-05-04) на S005a (storage architecture - до Sprint B1) и S005b (posterior math - до Sprint B5). S005a blocks B1 потому что storage decision fundamentally меняет schema layout.

**Critical path:** ALL Q&A SESSIONS CLOSED 2026-05-04. ~~S003+S007 (B2)~~ + ~~S004 (B3)~~ + ~~S006+S009 (B4)~~ + ~~S005b (B5)~~ + ~~S008+S010 (B6)~~. **Phase B fully Q&A-unblocked для всех sprints (B0.5/B1/B1.5/B2/B3/B4/B5/B6).** Remaining: только Phase A platform foundation prerequisites.

---

## Phase C+ Ecosystem (октябрь 2026+)

После Phase B Aurora Launch ship:

### Phase C: Suite Bundle + Customer Success
- **Aurora Suite Bundle** - Launch + Optimize + Brand cross-sell (40% discount vs individual)
- **Customer Success portal** - hour tracking UI, posterior update reminders, ongoing methodology updates
- **AI-assisted proxy suggestion** - не library, а Claude reasoning над описанием recipient'а + open data candidates -> 2-3 предложения для эксперта (P6 maintained)
- **White-label tier для агентств** - Aurora Launch с rebrand-возможностью deliverables

### Phase D: Advanced Features
- **Cross-app Model Arbitrage** - сравнение forecast'а Launch vs Optimize vs Brand для same recipient (validity check)
- **Multi-proxy auto-discovery** - алгоритмическое предложение N proxies для volatile categories
- **Pre-registered prediction tracking** - запоминаем launch forecast, проверяем post-launch (public benchmark)

---

## Phase B success criteria

- [ ] 17 файлов Sprint B0 deliverables (этой сессии)
- [ ] BC test corpus 10+ projects (Sprint B0.5)
- [ ] Pydantic v2 + JSON Schema SSoT (Sprint B1)
- [ ] Schema registry pattern (Sprint B1)
- [ ] Customer Success Lite tracker (Sprint B1.5)
- [ ] Proxy Selection cabinet UI с WASM similarity (Sprint B2)
- [ ] Two engines (single + multi proxy) (Sprint B3)
- [ ] Launch Forecast Report template 8 sections (Sprint B4)
- [ ] Methodology Certificate PDF generator (Sprint B4)
- [ ] Posterior Update workflow (Sprint B5)
- [ ] Onboarding tour + templates library (Sprint B6)
- [ ] Pilot client validation PASS (Sprint B6)
- [ ] Performance budgets met (≤30s single, ≤90s multi-proxy) (Sprint B6)
- [ ] WCAG AA compliance (Sprint B6)
- [ ] Methodology document publicly accessible (Sprint B6)
- [ ] v1.4.0 alpha-tag

---

## Открытые вопросы для следующих сессий

1. **Aurora Launch git repo** - separate vs aurora-business sub-folder vs внутри Econometrica monorepo
2. **Proxy data acquisition** - Mediascope/DSM подписка purchase responsibility (Антон лично vs клиентом vs агентство)
3. **Free trial длительность** - 30 / 60 / 90 дней
4. **Aurora Launch installer** - отдельный exe или часть Aurora Suite installer
5. **License management UI** - где клиент видит "у меня unlimited launches + 22h из 30h"

Эти вопросы поднимаются в Q&A sessions S008-S010.

---

## Связанные документы

- `00_Overview/PRINCIPLES.md` - 10 принципов (foundation)
- `00_Overview/PRODUCT_BOUNDARIES.md` - детали P8
- `02_Data_Spec/DATA_REQUIREMENTS.md` - детали P3
- `03_Architecture/REUSE_FROM_ECONOMETRICA.md` - детали P9
- `03_Architecture/UX_PRINCIPLES.md` - детали P10
- `03_Architecture/TEST_STRATEGY.md` - test pyramid + coverage
- `03_Architecture/DATA_PRIVACY.md` - local-first + DPA
- `03_Architecture/PERFORMANCE_BUDGETS.md` - per-operation time limits
- Memory: `project_aurora_launch_principles.md`
- Aurora platform roadmap: `project_econometrica_roadmap_v3.md`
- Suite strategy: `project_aurora_analytics_suite_strategy.md`
