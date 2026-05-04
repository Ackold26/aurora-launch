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

**Status:** ✅ DONE (closed 2026-05-04, autonomous session, mandate Антон)
**Blocker для:** Sprint B2 - resolved

**Decisions (Accepted):**

1. **Default weights** locked: category 0.30, pricing 0.20, media_maturity 0.15, brand_size 0.15, distribution 0.10, lifecycle 0.10 (sum 1.00). Rationale в SIMILARITY_FRAMEWORK Section 3.1.

2. **Threshold values** locked: High >= 0.85 (inflation 1.2×), Medium 0.65-0.85 (1.5×), Low 0.50-0.65 (2.0×), Insufficient < 0.50 (forecast blocked).

3. **Per-dimension scoring rules** finalized с three-level taxonomic structure (L1/L2/L3 categories), 4-tier pricing (ECONOMY/MAINSTREAM/PREMIUM/LUXURY), 3-tier brand size (LEADER/CHALLENGER/NICHE), 3-tier distribution (NATIONAL/REGIONAL/NICHE), 4-tier media maturity (ALWAYS-ON/PULSING/PROMO-DRIVEN/DORMANT), 4-tier lifecycle (NEW/GROWING/MATURE/DECLINING). Tier-distance scoring per dimension.

4. **Category-specific weight profiles** (asymmetric): OTC_PHARMA (category 0.40), RX_PHARMA (category 0.45 + lifecycle 0.15), FMCG_IMPULSE (pricing 0.25), FMCG_STAPLES (distribution 0.15), PREMIUM_COSMETICS (pricing 0.30), TELECOM_BANKING (media maturity + brand size 0.20 each), B2B (category 0.35 + brand size 0.20). Auto-loaded по recipient L1+L2.

5. **Multi-proxy aggregation:** weighted average S × pooling_weight + multi penalty 1 + 0.05×(N-1) на inflation factor. Floor warnings: any individual S<0.5 → warn, spread max-min > 0.3 → warn heterogeneous.

**Output:**
- ✅ `02_Data_Spec/SIMILARITY_FRAMEWORK.md` (master spec, ~870 строк)
- Synthetic validation плановый в Sprint B5 tests
- Iterative refinement Phase C+ (>10 pilot launches)

---

## S004: Adaptation Rules Detail

**Status:** ✅ DONE (closed 2026-05-04, autonomous session, mandate Антон)
**Blocker для:** Sprint B3 (Adaptation Layer) - resolved

**Decisions (Accepted):**

1. **Transfer parameter list:** 5 shape parameters transferred (adstock_decay_per_channel + hill_shape_gamma_per_channel + hill_half_saturation_per_channel + category_seasonality 52-vector + long_term_trend_slope) + 1 optional (reach_frequency_curve_shape если fitted, skip otherwise). NOT transferred: β coefficients, baseline, residual variance, cross-category controls, promo coefficients.

2. **Magnitude calibration formulas locked:**
   - Baseline = market_size × seasonality_t × planned_share(t) × distribution(t) × pricing_factor
   - Pricing factor = (1/pricing_index)^elasticity, с category-specific elasticities (FMCG_impulse 0.7, OTC 0.2, premium cosmetics 0.3, default 0.5)
   - β prior = (proxy_β / proxy_baseline) × recipient_baseline × similarity_factor (1.0/0.85/0.70 for High/Medium/Low)
   - σ_β = β_mean × (CV_proxy + similarity_inflation_addon 0.0/0.15/0.30)

3. **Anchor quality rules:** mandatory missing → block, recommended missing → defaults + warn (creative_quality_benchmark=1.0, competitive_response="moderate_increase", etc.). Anchor uncertainty propagation: ±10% market_size, ±25% planned_share, ±15% distribution, ±5% pricing.

4. **Cross-category matrix:**
   - L3 exact: full transfer all 5 parameters
   - L2 match: full transfer all 5
   - L1 match: only adstock + hill (seasonality + trend → category prior fallback)
   - Adjacent L1 (FMCG_food↔FMCG_beverage, OTC_pharma↔OTC_supplements, etc.): only adstock decay, +50% extra inflation
   - Cross L1 non-adjacent: BLOCKED at similarity verdict layer (Insufficient)

5. **Workflow:** **pre-train + transfer locked в ADR-003** (joint Bayesian = Phase D consideration). Three-step workflow: train proxy standalone → extract structural priors → train recipient с priors + anchor magnitudes. Reuses Aurora Econometrica modeler.py (P9 80%+ reuse).

**Paused brand integration:** organic baseline DSM history weighted с formula trajectory (organic weight 0.7/0.4/0.2 для pause 0-12mo / 12-24mo / 24+mo). σ_anchor reduced до 40% при quality organic data.

**Output:**
- ✅ `03_Architecture/ADAPTATION_RULES.md` (master spec ~1100 строк, code snippets, sensitivity tests Sprint B5 plan, 3 worked examples)
- ✅ `03_Architecture/decisions/ADR-003-pretrain-vs-joint-training.md` (Accepted, locks workflow choice + Phase D revisit triggers)

---

## S005a: Storage Layer Decision (Architectural blocker)

**Status:** ✅ DONE (closed 2026-05-04, autonomous session, mandate Антон)
**Blocker для:** Sprint B1 (schema design) - resolved

**Decision (Accepted):** **Option D - ZIP archive container** (overrides initial draft Option C SQLite hybrid).

`.aurora` файл = ZIP archive с layout:
- `manifest.json` (SSoT schema versions + integrity hashes)
- `metadata.json`, `proxy_brand_metadata.json`, `recipient_anchors.json`, `transfer_provenance.json`, `posterior_update_log.json`, `consulting_hours_log.json` (structured Pydantic models в JSON для human inspectability)
- `models/*.pickle`, `forecasts/horizon_NNw.pickle`, `cache/*.pickle` (math artifacts pickle preserved для 100% reuse Econometrica engines)
- Atomic save через `.aurora.tmp` + rename + rolling 4 backups
- Industry pattern (.docx/.xlsx/.pptx)
- Zero new dependencies (Python stdlib zipfile)
- Migration path Econometrica v2 pickle → v3 zip (transparent, через SchemaRegistry BFS)

**Rejected alternatives:**
- A (pure pickle): no human inspectability, BC fragile
- B (pure SQLite): math BLOB columns = pickle anyway, no real benefit, +10 MB deps
- C (SQLite hybrid - initial recommendation): 2 paradigms complexity, deps overhead, breaking pattern с Econometrica, real driver analysis показал что D delivers same benefits cleaner

**Output:**
- ✅ `03_Architecture/decisions/ADR-002-storage-layer.md` (Accepted)
- ✅ `03_Architecture/SCHEMA_DESIGN.md` (status Draft → Accepted, full layout)

---

## S005b: Posterior Update Math Design

**Status:** ✅ DONE (closed 2026-05-04, autonomous session, mandate Антон)
**Blocker для:** Sprint B5 - resolved

**Decisions (Accepted):**

1. **ESS-based weight schedule formula locked** (ADR-004):
   ```
   w_proxy(t) = ESS_proxy_adj / (ESS_proxy_adj + ESS_recipient(t))
   ESS_PROXY_BASE = 50 × similarity_factor (1.0/0.7/0.5 для High/Medium/Low)
   ESS_recipient(t) = t × recipient_obs_value (categorical: FMCG impulse 4.0, FMCG staples 3.0-3.5, OTC 2.5, Telecom/Banking 2.0, B2B 1.5, Rx 1.5, default 3.5)
   ```
   Worked schedule (FMCG High): t=12 w=0.51, t=26 w=0.32, t=52 w=0.19, t=104 w=0.11.

2. **Architecture: partial pooling primary** (single Bayesian model, prior strength controlled by w_proxy через std multiplier 1/w_proxy). **BMA fallback** только при severe drift (coverage <0.60).

3. **Drift detection adaptive policy:**
   - Coverage 0.90-0.95: normal schedule
   - 0.80-0.90: mild (recipient_obs_value × 1.5)
   - 0.60-0.80: moderate (× 3.0)
   - <0.60: severe → switch к BMA mode (two-model averaging)

4. **Identifiability mitigations:**
   - Min 4 weeks recipient data перед refit
   - Max shrinkage cap: weeks <12 → w_proxy >=0.40, weeks <24 → w_proxy >=0.20
   - Diagnostic checks (Gelman-Rubin <1.05, ESS >=400, divergent_transitions=0, posterior predictive p-value 0.05-0.95)

5. **Proxy release threshold:** 0.10 (audit-revised from 0.05 - calibrated к ~2.2y FMCG handoff window vs 4.6y at 0.05 - too long). Cross-app handoff trigger: w_proxy <0.10 + 52+ weeks → suggest Aurora Optimize transition.

6. **Audit trail:** `PosteriorUpdateEvent` per refit captures full state (weights, coverage, drift severity, ESS values, diagnostics, triggering data hash, user note). Methodology Certificate PDF includes full posterior update history table.

**Multi-proxy edge case:** each proxy own ESS reduction schedule, hierarchical model re-fit с new individual weights, pooling weights между proxies preserved.

**Output:**
- ✅ `03_Architecture/POSTERIOR_UPDATE_DESIGN.md` (master spec ~1100 строк, calibrated formulas + worked schedules + UI flow + sensitivity tests Sprint B5 plan)
- ✅ `03_Architecture/decisions/ADR-004-ess-based-weight-schedule.md` (Accepted, locks formula + alternatives rejected + Phase D revisit triggers)

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

**Status:** ✅ DONE (closed 2026-05-04, autonomous session, mandate Антон)
**Blocker для:** Sprint B2 - resolved

**Decisions (Accepted):**

1. **5 trigger conditions** для включения multi-proxy: (1) volatile category leader (SoV CV > 50%), (2) no clear single proxy (top-2 within 0.05 difference), (3) categorical heterogeneity, (4) high-stakes launch (>=5M ₽ budget), (5) sensitivity analysis demand. ≥1 → consider, ≥2 → strongly recommend. Decision tree в UI tooltip + help system.

2. **Anti-patterns explicit:** не использовать multi-proxy для (a) "fix bad data" (weak candidates не help), (b) "more proxies = better" с already-similar proxies, (c) time-pressed launches (training 2-3× slower), (d) без эксперт review.

3. **Weight assignment:** equal default (1/N), manual sliders с auto-rebalance (sum=100%), Phase C+ AI-suggested weights based on individual S scores.

4. **N bounds:** min 2 (single = different engine), max 3 (computational cost + UI complexity beyond 3 не justifies).

5. **UI form layout:** tabs (Proxy 1 / Proxy 2 / + Add Proxy) для each proxy form, sticky sidebar с pooling weights sliders + combined aggregate panel (S_combined, verdict, inflation, warnings, estimated training time). ASCII wireframes в deliverable Section 5.

6. **Inline hints + tooltips:** suggestion sidebar в heterogeneous categories (Phase C+), warning if user toggles multi с too-similar proxies (>0.9 between them), tooltips on pooling weights + combined aggregate explaining math.

**Output:**
- ✅ `01_Concept/MULTI_PROXY_UX_DECISION_RULES.md` (full decision rules + ASCII wireframes + 3 worked examples + implementation notes Sprint B2, ~620 строк)

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
