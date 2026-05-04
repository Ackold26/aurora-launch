# Aurora Launch - Pilot Client Plan

**Status:** Accepted (S008 closed 2026-05-04)
**Sprint context:** Sprint B6 (Pilot Live-Test) prerequisite
**Owner:** Антон (sales)
**Coordinated с:** S010 SALES_PLAYBOOK + S009 PRICING_TIERS (Path B free pilot)

## Контекст

Sprint B6 требует pilot client для end-to-end validation Aurora Launch (proxy → anchors → forecast → report → posterior update). Этот документ финализирует:

1. **3 parallel pilot categories** (не single - safer для Sprint B6 risk diversification)
2. **Named candidate brands** + ranking criteria
3. **Qualification questions** для discovery call
4. **Pilot offer structure** (Path B free first launch с case-study consent per S009)
5. **12-week engagement plan** + check-ins
6. **Success criteria** (что значит "pilot passed")
7. **Post-pilot conversion strategy**

---

## 1. Three Parallel Pilot Categories

**Strategy:** 3 pilots in parallel вместо одного - diversification benefits:

- Если один pilot не успешный (organizational change, data delay) - другие продолжают
- Cross-category learning (FMCG vs Pharma vs Cosmetics issues differ)
- Faster v1.4.0 ship validation (3 successes parallel > 1 sequential)
- Case studies для 3 customer categories (broader marketing assets)

**Risks:** 3× consulting hours strain (Антон solo). Mitigation: phase pilot kickoffs 2-4 weeks apart, не all simultaneously.

### 1.1 Category A - OTC Pharma Launch

**Why this category first:**
- Existing relationship через Aurora Econometrica trust (Кагоцел case)
- Pharma OTC has clear data sources (DSM Pharma + Mediascope)
- ATC class structure makes proxy selection well-defined
- Regulated media (limits creative variability) - cleaner forecast
- Case study impact: pharma is highest-ticket Aurora segment (1.5-3M+ contracts)

### 1.2 Category B - FMCG Impulse Launch (snacks / beverages)

**Why this category:**
- High consumer volume + fast feedback loop (12-week pilot has meaningful data)
- DSM Retail panel coverage strong для FMCG categories
- Pricing tier matters (impulse purchase elasticity high)
- Case study impact: FMCG is largest Aurora addressable market by volume

### 1.3 Category C - Premium Cosmetics Launch

**Why this category:**
- Post-2022 import substitution wave - many Russian premium brands launching
- Premium positioning valuable case study (high-ticket per launch)
- Cosmetics have category-specific weight profile (PREMIUM_COSMETICS_WEIGHTS S003)
- Case study impact: differentiates Aurora vs FMCG-only positioning

---

## 2. Named Candidate Brands

**Note:** specific brand finalization happens at sales conversation. List below = Антон's prioritized prospect pipeline для pilot kickoff.

### 2.1 Category A - Pharma OTC (3 candidates)

**Tier 1 (existing Aurora Эконометрика clients - PRIMARY upsell, per ADR launch-as-econometrica-upsell):**

1. **Materia Medica Holding (Кагоцел team)** - existing Aurora Эконометрика client (Trust 3 hierarchical Bayesian validated на Кагоцел data v1.0.16). Highest priority: новый OTC-launch проходит как natural upsell + Кагоцел project можно использовать как proxy в Launch (lossless migration через Эконометрика → Launch flow Sprint B6). Decision-maker: marketing director / new product launch lead. Conversion expectation 60%+ (warm relationship).

2. **Венарус team / Materia Medica peer brands** - similar relationship logic. Если есть другие OTC-бренды в pipeline - same upsell story.

**Tier 2 (warm intros от Tier 1 + adjacent Эконометрика clients):**

3. **Stada CIS** - mid-tier OTC pharma manufacturer, multiple new launches per year. Warm intro candidate (industry peer of Materia Medica). Decision-maker: head of Russia marketing.

**Tier 3 (cold - secondary, после стабилизации Tier 1):**

4. **Биннофарм Group** - Russian pharma, expanding OTC portfolio post-2022. Cold contact, requires LinkedIn intro or industry event meeting. Активировать после ≥1 case study от Tier 1.

### 2.2 Category B - FMCG Impulse (3 candidates)

**Tier 1:**

1. **KDV Group** - leader Russian snacks (chocolate, confectionery), launching new products regularly. Cold but well-known target. Decision-maker: brand manager / new product team.

2. **PepsiCo Russia** - launching new flavors / sub-brands continuously. Has sophisticated marketing team that values methodology rigor. Cold but typical Aurora fit (premium brand engagement).

**Tier 2:**

3. **Сладко** (United Confectioners) - mid-tier challenger в snacks_sweet category. Less sophisticated marketing organization but launches new products. May benefit most from Aurora's structured approach.

### 2.3 Category C - Premium Cosmetics (3 candidates)

**Tier 1:**

1. **Натура Сиберика** - premium Russian skincare/haircare. Active launch pipeline (post-2022 expansion). Decision-maker: marketing director / new product team.

2. **ARTKOSMETIK** - premium Russian decorative cosmetics, growing rapidly. Cold but fast-growth signal valuable for Aurora messaging.

**Tier 2:**

3. **Лэтуаль private brands** - retailer launching own brands. Different sales motion (multi-stakeholder), less Aurora-fit но potential premium tier client.

---

## 3. Ranking Criteria (which to chase first within tier)

Антон prioritizes pilot prospects по этим signals:

1. **Existing Aurora Эконометрика client** (already trusts methodology, easiest upsell): **+5 priority points (PRIMARY)**
2. **Warm intro available** (existing relationship, mutual connection): +3 priority points
3. **New brand launch in pipeline within 4-8 weeks** (Aurora can validate forecast before launch): +2 points
4. **Category data infrastructure exists** (DSM Pharma / DSM Retail / Mediascope subscription у клиента): +2 points (can move fast)
5. **Decision-maker accessible** (LinkedIn / email / phone known): +2 points
6. **Marketing team sophistication** (uses MMM, knows similarity concept, values methodology): +1 point
7. **Budget signals** (>=2.5M ₽ Pro tier feasible): +1 point
8. **Case study consent flexibility** (PR-friendly organization): +1 point

**Pilot kickoff target:** top 3 candidates (one per category) by total score. Existing Aurora Эконометрика clients автоматически получают +5 - они должны быть Tier 1 prospects если новый запуск в pipeline.

---

## 4. Pilot Qualification Questions (Discovery Call)

30-minute discovery call (per S010 SALES_PLAYBOOK). Before offering Aurora Launch demo, Антон qualifies:

### 4.1 Use Case Fit

1. "У вас есть бренд / SKU, запуск которого планируется в ближайшие 2-6 месяцев?"
2. "Это полностью новый бренд или новый SKU в существующем портфеле?"
   - Новый бренд → fits Aurora Launch
   - SKU в портфеле → handoff к Aurora Optimize "New SKU workflow" (out of pilot scope)
3. "Бренд имеет историю продаж до 12+ месяцев?"
   - Yes → handoff к Aurora Optimize standard
   - No → fits Aurora Launch

### 4.2 Data Availability

4. "Есть ли подписка DSM Group или Mediascope в вашей организации?"
   - Yes → can supply proxy data quickly
   - No → can ARM agency partner (если applicable). Если no path к DSM/MS - pilot blocked.
5. "В вашей категории есть established competitor brand с 24+ months DSM history?"
   - Yes → proxy candidate exists
   - No → may need cross-category proxy (warning: Insufficient verdict possible)

### 4.3 Timeline + Capacity

6. "Когда планируете launch? Aurora Launch требует ~2 недели на data preparation + forecast generation."
7. "Кто в команде будет работать с Aurora? Один человек / маркетинг + аналитики?"
8. "Есть ли у вас pre-test данные креатива (Kantar Link / Ipsos copytest)?" (boost forecast accuracy если есть)

### 4.4 Pilot Compatibility

9. "Готовы ли согласиться на case-study consent (anonymized)? Aurora использует pilot results для marketing materials. Brand name remains confidential если не пожелаете."
10. "Можете предоставить feedback после 12 weeks пилотирования?"

**Disqualification signals:**
- No DSM/MS data path → блок (Aurora cannot operate)
- Launch >12 months out → too far for pilot
- No willingness for case study consent → still possible но lower priority
- Recipient brand has существующая history → wrong product (handoff)

---

## 5. Pilot Offer Structure

**Path B - Free first launch с case-study consent** (per S009 PRICING_TIERS Section 2.2).

### 5.1 What Aurora Provides FREE

- Aurora Launch software access (12-week pilot duration)
- Антон's consulting hours (~10-20h budgeted across pilot - covers proxy review session, anchors workshop, posterior update session, final review)
- Methodology Certificate PDF (full Pro+ tier 2-page format - showcase quality)
- Pilot kickoff session (1.5h)
- 4-weekly check-ins (30 min each)
- Final post-pilot review meeting (1h)
- All deliverables (PPTX/HTML/XLSX/PDF) - белый-label если Enterprise feel needed

### 5.2 What Customer Provides

- DSM/Mediascope data extraction (от their subscription)
- Recipient anchors form completion (~2h customer time)
- Marketing team availability for sessions (~5-8h total customer time)
- Case study consent (NDA signed, anonymized publication permission)
- Post-launch results sharing (после 12+ weeks - feedback into Aurora calibration)

### 5.3 Conversion Offer (post-pilot)

End of 12-week pilot, formal offer:
- **Pilot conversion discount -10%** on first year (per S009)
- **Stack с multi-year:** -10% pilot + -5% 2-year = -14.5% effective on 2-year deal
- Tier choice based on customer launch frequency:
  - 1-3 launches/year expected → Starter @ 1.35M (с -10% pilot)
  - 4-8 launches/year → Pro @ 2.25M (с -10%)
  - Strategic partnership → Enterprise @ 3.15M (с -10%)

---

## 6. 12-Week Engagement Plan

### 6.1 Pre-Pilot (Week -2 to 0)

**Week -2:** Discovery call → qualification → pilot offer
**Week -1:** NDA + pilot agreement signed → data collection guidance shared (DSM/MS export instructions)
**Week 0:** Pilot kickoff session

### 6.2 Pilot Kickoff Session (1.5 hours)

**Agenda:**
1. Aurora Launch overview (15 min) - principles, methodology, what to expect
2. Recipient brand briefing (15 min) - customer presents their launch context
3. Proxy discovery (30 min) - Антон + customer expert collaboratively select 1-3 proxy candidates
4. Anchors collection plan (15 min) - customer team assigned to fill recipient_anchors form
5. Timeline confirmation (15 min) - milestones, check-ins, deliverables

**Deliverable:** Pilot Engagement Plan signed (1-page)

### 6.3 Pilot Phase 1 - Forecast Generation (Week 1-3)

**Week 1:**
- Customer uploads DSM + Mediascope data (proxy brand)
- Antón runs Aurora Launch validation → ProxyDataValidator results
- Customer fills recipient_anchors form (with Anton's coaching)
- SemanticValidator results reviewed

**Week 2:**
- Similarity computation (6 dimensions) → similarity radar shared
- Tier verdict (Gold/Silver/Bronze) discussed с customer
- If Insufficient → search for better proxy OR pivot to category prior fallback
- If Medium/Low → warnings discussed, customer accepts uncertainty

**Week 3:**
- Initial forecast generated (12/26/52 weeks)
- Aurora Launch Forecast Report (PPTX/HTML/XLSX) delivered
- Methodology Certificate PDF delivered
- Customer presents к internal stakeholders (CFO/CMO)

**Check-in Meeting #1 (Week 3, 30 min):** review forecast, discuss methodology, address questions.

### 6.4 Pilot Phase 2 - Launch Period (Week 4-12)

Customer executes their launch with media plan. Aurora не intervenes - customer measures actual results.

**Check-in Meeting #2 (Week 6, 30 min):**
- Early sales data review (DSM 1-2 month available)
- Any deviations from forecast?
- Customer feedback на Aurora deliverables UX

**Check-in Meeting #3 (Week 10, 30 min):**
- Mid-pilot data review (3 months DSM available)
- Posterior update session - upload new recipient data, re-run model
- Coverage check, drift detection results
- New forecast (refined CI) shared

### 6.5 Pilot Wrap-up (Week 12-13)

**Final post-pilot review (1h):**
- Compare initial forecast vs actuals (12-week period)
- Coverage accuracy: did 95% CI capture actual sales?
- Methodology learnings (what worked, what surprised)
- Customer satisfaction (NPS-style: "Would you continue использовать Aurora Launch?")
- Conversion offer presentation (per Section 5.3)

**Deliverables:**
- Final pilot report (anonymized version for Aurora marketing)
- Customer-facing pilot report (full named brand)
- Conversion contract option (signable)

---

## 7. Success Criteria (Pilot Passed)

Aurora marks pilot SUCCESSFUL если все следующие соблюдены:

### 7.1 Functional Success

- [ ] End-to-end flow completed: proxy selection → anchors → forecast → report
- [ ] Aurora Launch software completed без crashes / data loss
- [ ] All 4 deliverables generated (PPTX, HTML, XLSX, PDF Methodology Certificate)
- [ ] Posterior update workflow tested (Week 10 session)
- [ ] Hash signature reproducibility verified

### 7.2 Quality Success

- [ ] Forecast 95% CI captures actuals at 90%+ rate (some tolerance for Phase B initial)
- [ ] No critical methodology errors discovered
- [ ] Customer team understands methodology (плain language framing worked)
- [ ] Methodology Certificate accepted by customer's CFO/auditor (если applicable)

### 7.3 Customer Satisfaction Success

- [ ] Customer rates pilot 7+/10 NPS
- [ ] Customer would recommend Aurora Launch к peers
- [ ] At least 1 case study approved для Aurora marketing (anonymized или named)
- [ ] Conversion offer accepted OR principled non-conversion (e.g., "we'd buy if X feature added")

### 7.4 Sprint B6 Acceptance Criteria Linked

Pilot success enables Sprint B6 ship criteria:
- Pilot client validation PASS (per ROADMAP Sprint B6 deliverables list)
- Bug fixes по live-test findings applied
- Performance budget validation (train ≤30s single, ≤90s multi-proxy)
- v1.4.0 alpha-tag

---

## 8. Risk Mitigation

### 8.1 What if all 3 pilots fail?

**Failure modes:**
- Pilot 1 fails: customer organizational change, data delay, methodology rejected
- Pilot 2 fails: similar
- Pilot 3 fails: similar

**Mitigation:**
- 3 parallel pilots (instead of 1) - probability all 3 fail simultaneously is low
- Each pilot независим
- Backup plan: if all 3 fail by Week 8, Антон reaches out к 5+ Tier 2 candidates from list (Section 2)
- Worst case: Phase B B6 ship delayed by 4-6 weeks для secondary pilots

### 8.2 What if pilot succeeds but doesn't convert?

Common reasons:
- Budget constraints → multi-year discount + payment flexibility
- Pricing concerns → tier downgrade (Starter @ 1.35M still profitable)
- Internal champion lost (decision-maker leaves) → reach out к successor
- Not the right time → "warm" status, follow up в 6 months

**Aurora retains:** case study material, learnings, methodology validation (still v1.4.0 ship-able).

### 8.3 What if proxy selection blocks pilot?

If pilot client's category lacks suitable proxy (Insufficient verdict):
- Pivot к category prior fallback (Phase D feature - mention as "coming soon")
- Or pause pilot, find better proxy через Aurora's category research, restart
- Or escalate to "harder case study" - document that Aurora correctly blocked instead of generating bad forecast (trust signal)

---

## 9. Pilot Logistics

### 9.1 Antón's Time Investment

**Per pilot (12 weeks):**
- Pre-pilot: 4h (qualification + offer + agreement)
- Kickoff: 1.5h
- Phase 1 data review: 4h (proxy validation, anchors review, similarity discussion)
- Phase 2 check-ins: 3 × 30min = 1.5h
- Phase 2 ad-hoc questions: 4h budget
- Posterior update session: 1.5h
- Final review: 1h
- **Total: ~17.5h per pilot**

**3 parallel pilots:** ~52.5h total over 12-14 weeks. Manageable solo (Антон ~10h/week budget).

### 9.2 Pilot Scheduling

**Phased kickoffs (не all simultaneously):**
- Pilot A (pharma) kickoff: Week 0
- Pilot B (FMCG) kickoff: Week 2
- Pilot C (cosmetics) kickoff: Week 4

This balances Антон load + lets early-pilot learnings inform later kickoffs.

### 9.3 Tools

- **CRM:** Notion-based pipeline (Антон's existing setup)
- **Calendar:** Calendly anton-sipovich/aurora-launch-pilot (1.5h kickoff slots, 30min check-in slots)
- **Communication:** Email primary (ackold@yandex.ru), Telegram for quick questions, Zoom for sessions
- **Document delivery:** Aurora Launch generates locally, Антон encrypts + emails (pilot does не require Aurora cloud sync infrastructure - keep local)

---

## 10. Post-Pilot Marketing Assets

After pilot success, Aurora generates:

### 10.1 Case Study (anonymized или named)

**Format:** 4-6 page PDF
**Sections:**
1. Customer challenge (new brand launch без historical data)
2. Aurora approach (proxy selection + anchors + transfer)
3. Forecast generation (sample charts, similarity verdict)
4. Post-launch validation (actuals vs forecast)
5. Methodology certification
6. Customer testimonial (if named) или анонимный quote

**Distribution:** auroraai.pro/case-studies, sales playbook, LinkedIn posts.

### 10.2 Demo Dataset (sanitized)

Pilot data anonymized (brand renamed, numbers scrambled keeping ratios) → demo dataset for future sales calls.

**Pipeline impact:** future demos use real-world example instead of synthetic - much more compelling.

### 10.3 Methodology Validation Reference

Reference в Methodology Certificate того что methodology validated на pilot data. Builds trust для regulatory contexts (pharma).

---

## 11. Связанные документы

- `../05_Sessions/SESSION_NEXT_QUESTIONS.md` S008 closed reference + S010 sales playbook
- `../06_References/PRICING_TIERS.md` (S009) - Path B free pilot offer
- `../06_References/SALES_PLAYBOOK.md` (S010) - discovery call template + outreach
- `../00_Overview/ROADMAP.md` Sprint B6 deliverables
- `../00_Overview/PRODUCT_BOUNDARIES.md` - decision tree для qualification
- `../03_Architecture/POSTERIOR_UPDATE_DESIGN.md` - Week 10 posterior update session
- `../02_Data_Spec/REPORT_SECTIONS_SPEC.md` - deliverable formats
- Memory: `project_econometrica_premium_avatars.md` - Materia Medica Trust 3 baseline
- Memory: `project_econometrica_v1016_day1_optimize_cluster.md` - Кагоцел live-test learnings (relevant pharma pilot patterns)
