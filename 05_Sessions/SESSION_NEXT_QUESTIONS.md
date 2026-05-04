# Aurora Launch - Q&A Sessions Roadmap

**Status:** v1.0 (2026-05-04)
**Owner:** Антон + Маша
**Update cadence:** после каждой session

## Контекст

Каждый Sprint Phase B имеет blocker Q&A sessions которые финализируют design decisions до начала dev. Этот документ - roadmap всех S002-S010 с темами + кто решает + когда.

---

## S002: Data Requirements Spec deep-dive

**Status:** ✅ DONE (этой сессии Variant 2)
**Owner:** Маша + Антон
**Output:** 5 файлов в `02_Data_Spec/` + JSON Schema SSoT

---

## S003: Proxy Similarity Framework

**Status:** PENDING
**Blocker для:** Sprint B2 (Proxy Selection cabinet)
**Target completion:** до старта Sprint B2

**Open questions:**

1. **Точные веса 6 dimensions** в aggregate similarity score
   - Default proposal: category 30%, pricing 20%, brand size 15%, distribution 10%, media maturity 15%, lifecycle 10%
   - Calibration: synthetic transfers с known truth → adjust weights

2. **Threshold values** для verdict tiers
   - High >= 0.85 / Medium 0.65-0.85 / Low 0.50-0.65 / Insufficient < 0.50
   - Validated на synthetic transfers?

3. **Per-dimension scoring rules** (как именно превращать "категория совпадает" в score)
   - Exact = 1.0, soeдний tier = X, через tier = Y - конкретные numbers
   - Cross-category - всегда 0 или partial credit для adjacent (FMCG snacks vs sweets)?

4. **Asymmetric weights** возможны для разных recipient типов?
   - Pharma OTC: ATC class match критично (weight 40%)
   - FMCG: ценовой tier важнее (weight 30%)
   - Default vs category-specific weights

5. **Multi-proxy aggregation logic**
   - Как комбинировать 2-3 similarity scores в aggregate?
   - Average / max / weighted by partial pooling weight?

**Owner of decision:** Антон (domain expert) + Маша (math design)

**Deliverable:** SIMILARITY_FRAMEWORK.md в `02_Data_Spec/` с calibrated weights + thresholds + scoring rules.

---

## S004: Adaptation Rules Detail

**Status:** PENDING
**Blocker для:** Sprint B3 (Adaptation Layer)
**Target completion:** до старта Sprint B3

**Open questions:**

1. **Точный список параметров для transfer**
   - Что именно из proxy model переносится?
     - Adstock decay rate (single value vs per-channel?)
     - Hill saturation shape (alpha + gamma vs sqrt-form?)
     - Reach-frequency response curve shape
     - Категорийная сезонность как deviation pattern
     - Long-term trend (linear vs other)
   - **Что НЕ переносится:**
     - β coefficients (точно)
     - Baseline magnitude
     - ROI levels
     - CPP / CPM levels (ROBYN-style normalization)

2. **Magnitude calibration logic**
   - Как из anchors восстанавливаются β magnitudes?
   - Формула baseline calibration: baseline = (market_size × planned_share × pricing_index)?
   - Уверенность в calibrated magnitude (variance из anchor uncertainty)

3. **Sensitivity to anchor quality**
   - Что если recipient anchor incomplete?
   - Hard requirement vs soft warnings
   - Default values для missing optional fields

4. **Cross-category transfer rules**
   - Можно ли transfer FMCG snacks proxy для FMCG sweets recipient (соседняя sub-categория)?
   - Adjustments при cross-category transfer?
   - Tier discount?

5. **Pre-train vs post-train transfer**
   - Сейчас design предполагает: train proxy model отдельно → extract priors → train recipient с priors
   - Alternative: joint training с partial pooling из start
   - Trade-offs

**Owner of decision:** Маша (math) + Антон (domain validation)

**Deliverable:** ADAPTATION_RULES.md в `01_Concept/` или `03_Architecture/`.

---

## S005a: Storage Layer Decision (Architectural blocker)

**Status:** PENDING (post-audit 2026-05-04 split из S005)
**Blocker для:** **Sprint B1** (schema design)
**Target completion:** **до старта Sprint B1** (early decision - storage choice fundamentally меняет schema layout)

**Decision options:**
- A) Pure pickle (как Aurora Econometrica) - simpler, breaking change при migrations
- B) Pure SQLite - human-readable, query-able, harder migration
- C) Hybrid: SQLite для metadata + pickle BLOBs для math artifacts (RECOMMENDED)

**Owner:** Маша (technical) + Антон (operational impact).

**Deliverable:** ADR-002 "Storage Layer Choice" + initial SCHEMA_DESIGN.md.

---

## S005b: Posterior Update Math Design

**Status:** PENDING (post-audit 2026-05-04 split из S005)
**Blocker для:** Sprint B5 (Posterior Update workflow)
**Target completion:** до старта Sprint B5

**Open questions:**

### S005b.1: Weight schedule formula

1. **Weight schedule formula**
   - ESS-based: weight = proxy_ESS / (proxy_ESS + recipient_ESS)
   - Bayesian Model Averaging: model weights from posterior log-likelihood
   - Linear / exponential decay
   - Threshold для "proxy released" - когда weight < 0.05 → standalone model

2. **Validation на synthetic data**
   - Generate synthetic recipient evolved from proxy
   - Test что model converges к recipient truth
   - Sensitivity to weight schedule choice

3. **Identifiability при partial pooling**
   - Если recipient data short - модель может застрять в proxy local minimum
   - Когда обнаружить и предупредить пользователя

**Owner of decision:** Маша (math) + Антон (domain validation).

**Deliverable:** POSTERIOR_UPDATE_DESIGN.md в `03_Architecture/` + ADR-003 для weight schedule.

---

## S006: Launch Forecast Report Sections

**Status:** PENDING
**Blocker для:** Sprint B4 (Report Template)
**Target completion:** до старта Sprint B4

**Open questions:**

1. **8 sections - что именно в каждой**
   - Section 1: Cover - что включаем (project name, date, version, hash, Aurora seal, recipient brand, proxy used)
   - Section 2: Executive Summary - tier badge, key metrics (forecast 1-year sales, CI), CFO framing language
   - Section 3: Proxy Quality - similarity radar, dimensions table, verdict, what doesn't transfer
   - Section 4: Transfer Caveats - что переносится / не переносится, uncertainty decomposition
   - Section 5: Forecast 12 weeks - tight CI, immediate launch period
   - Section 6: Forecast 26 weeks - 6-month ramp
   - Section 7: Forecast 52 weeks - year planning, expanding cone
   - Section 8: Methodology + References + Model Card + Hash signature

2. **Должны ли быть decomposition + optimization sections?**
   - Пока не в 8-section template
   - Add as optional appendix?

3. **Visualizations per section**
   - PPTX vs HTML vs XLSX format-specific?
   - Charts через ECharts (HTML) vs python-pptx (PPTX) vs Rust XLSX

4. **Methodology Certificate PDF (audit C10)**
   - Standalone document или часть report?
   - Какие fields обязательны (Aurora seal, version, hash, proxy used, methodology version)

5. **Customer-facing language tone**
   - CFO-friendly framing
   - Reusable phrases / templates
   - Plain-language vs technical balance

**Owner of decision:** Маша (design) + Антон (customer perspective).

**Deliverable:** REPORT_SECTIONS_SPEC.md в `02_Data_Spec/` + Methodology Certificate template.

---

## S007: Multi-Proxy UX

**Status:** PENDING
**Blocker для:** Sprint B2 (Proxy Selection cabinet UI)
**Target completion:** до старта Sprint B2 (вместе с S003)

**Open questions:**

1. **Когда expert включает multi-proxy?**
   - Decision rules:
     - Volatile lead brand (sharp swings в SoV)
     - Recent brand ownership change
     - Categorical merger / ownership consolidation
     - Multiple plausible proxies без чёткого "лучшего"
   - UX: tooltip / wizard / explicit decision

2. **Multi-proxy weight assignment**
   - Equal weights default?
   - Manual weights с slider?
   - Calculated from individual similarity scores?

3. **Number of proxies allowed**
   - Min 2, max 3? Or 4?
   - Computational cost growth с N

4. **UI form для multi-proxy**
   - Tabs (proxy 1, 2, 3) или vertical list?
   - Aggregate similarity radar (per proxy + combined)
   - Confidence verdict per proxy + combined

5. **Decision rules в documentation**
   - "Включай multi-proxy когда..."
   - Tooltip с links к knowledge base

**Owner of decision:** Антон (domain expert) + Маша (UX).

**Deliverable:** MULTI_PROXY_UX_DECISION_RULES.md в `01_Concept/` + UI wireframe.

---

## S008: Pilot Client Identification

**Status:** PENDING
**Blocker для:** Sprint B6 (Live-Test)
**Target completion:** до старта Sprint B6

**Open questions:**

1. **Кандидаты pilot client**
   - 1-2 фарма OTC launch teams (Materia Medica? Stada?)
   - 1-2 FMCG launch teams (snacks / напитки / молочка)
   - Параллельно или sequential?

2. **Pilot offer structure**
   - Free first launch с case-study consent
   - Discounted (50%) первый launch
   - Free 90-day trial с proxy review

3. **Success criteria pilot**
   - Clean end-to-end flow (proxy → anchors → forecast → report)
   - Forecast confidence verdict generated
   - Methodology Certificate accepted by client
   - Posterior update workflow tested

4. **Client engagement plan**
   - Discovery call → pilot kickoff → 4-weekly check-ins
   - 12 weeks total pilot period
   - Final post-pilot review meeting

**Owner of decision:** Антон (sales).

**Deliverable:** PILOT_CLIENT_PLAN.md в `04_Sprints/`.

---

## S009: Pricing Tier Finalization

**Status:** PENDING
**Blocker для:** Sprint B4 (moved up - audit A15) + commercial ship
**Target completion:** до старта Sprint B4

**Open questions:**

1. **Tier numbers финал**
   - Starter: 1.5M / год + 20h consulting?
   - Pro: 2.5M / год + 30h + priority support?
   - Enterprise: 3M+ / год + 40h + custom training + on-site?

2. **What's in / what's out per tier**
   - All tiers: unlimited launches, all features
   - Pro+: priority support, methodology certificate volumes
   - Enterprise+: custom training, on-site sessions, multi-user license

3. **Free trial / pilot offer**
   - 30 / 60 / 90 дней?
   - Pilot first launch free с case-study consent?
   - Combined option

4. **Discount policy**
   - Multi-year discount (5% / 10% / 15%)?
   - Suite bundle discount (40% per Suite strategy)
   - Loyalty discount renewal

5. **Payment structure**
   - Annual upfront vs quarterly billing?
   - Currency (RUB primary, USD optional?)

6. **Renewal logic**
   - Auto-renewal default or opt-in?
   - 60-day notice for non-renewal
   - Grace period for late payment

**Owner of decision:** Антон (commercial).

**Deliverable:** PRICING_TIERS.md + контрактные templates.

---

## S010: Sales Playbook

**Status:** PENDING
**Blocker для:** Sprint B6 (Live-Test) + commercial ship
**Target completion:** до старта Sprint B6 (вместе с S008)

**Open questions:**

1. **Outreach template**
   - Cold email (LinkedIn DM)
   - Subject lines что resonate
   - Industry-specific angles (фарма vs FMCG)

2. **Discovery call flow (30 минут)**
   - Stated questions / conversation flow
   - Use case classification (Launch vs Optimize vs Brand)
   - Pain validation

3. **Demo flow (45-60 минут)**
   - Sample dataset / template
   - Live forecast generation
   - Confidence radar + tier badge
   - Methodology certificate sample
   - Q&A handling

4. **Pilot kickoff**
   - Onboarding checklist
   - Data collection guidance (DSM/MS)
   - Proxy discovery session
   - Anchors workshop
   - First forecast review

5. **Conversion / contract**
   - Pricing presentation
   - Contract negotiation framework
   - Custom terms common requests

6. **Post-conversion onboarding**
   - License activation
   - Initial training session (1-2h)
   - Quarterly check-ins schedule

**Owner of decision:** Антон (sales).

**Deliverable:** SALES_PLAYBOOK.md + email templates + contract templates.

---

## Q&A Sessions Cadence

**Recommended:** одна Q&A session per week starting 1-2 недели до Sprint kickoff.

**Critical path:**
- Week -3: S003 + S007 (parallel) → unblock B2
- Week -2: S004 → unblock B3
- Week -1: S006 + S009 (parallel) → unblock B4
- Week 0 (Sprint B2 start)
- Week +1: S005 → unblock B5 (during B3-B4)
- Week +5: S008 + S010 → unblock B6 (during B5)

Actual scheduling зависит от Phase A completion timing.

---

## Session Logs Storage

Все session outputs в `05_Sessions/`:
- `SESSION_001_concept_2026-05-04.md` ✓
- `SESSION_002_data_requirements_2026-05-04.md` (этой сессии Variant 2 - совмещено с S001)
- `SESSION_003_similarity_framework_TBD.md` (pending)
- ... etc.

Каждый session log содержит:
- Date + duration + participants
- Open questions (in)
- Discussion summary
- Decision log
- Action items (out)
- Next session topic

---

## Open Architecture Decisions (require Антон input)

(Эти НЕ в S002-S010 как formal sessions, а ad-hoc decisions для Маши)

| Decision | Owner | Target |
|---|---|---|
| Aurora Launch git repo (separate vs sub-folder) | Антон | до Sprint B0.5 |
| WASM module commitment (audit B4) | Маша | до Sprint B2 |
| Streaming MCMC commitment (audit B6) | Маша | до Sprint B1 |
| Phase A coordination protocol | Маша + Антон | до Phase A start |
| Aurora_Test_Corpus repo (audit B9) | Маша | до Sprint B0.5 |

---

## Связанные документы

- `SESSION_001_concept_2026-05-04.md` - предыдущая session
- `../00_Overview/ROADMAP.md` - sprint dependencies
- `../00_Overview/PRINCIPLES.md` - foundation
- Track file: `C:\Users\ackol\Desktop\zippy-wobbling-waffle-track.md`
