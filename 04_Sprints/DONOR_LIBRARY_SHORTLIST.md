# Donor Library Shortlist (Sprint B6)

**Status:** Draft v0.1 (2026-05-05) — Маша маленькая.
**Decision context:** Маша небесная strategic correction 2026-05-05 — incremental donor library 5 моделей в Sprint B6. Это **revises D002** ("Отказ от donor library") из SESSION_001 — donor library теперь принимается, но **incremental** (накопительный, не curated upfront), и **только из реальных клиентов Эконометрики** с технической anonymization.

**Цель shortlist:** список 5 моделей-доноров для B6 с максимальным покрытием фарма-категорий. Кандидаты — реальные клиенты Aurora Эконометрики, обработанные anonymization protocol (Section 3).

**Pre-conditions для inclusion:**
- Existing Aurora Эконометрика project (.aurora/.pickle) с trained model (Trust 3 hierarchical Bayesian preferable).
- Полная история данных >= 2 года (для seasonality + trend extraction).
- Антон's approval после shortlist review.
- ATC class документирован (для category match).

---

## 1. Подтверждённые кандидаты (existing Эконометрика clients)

### Candidate 1 — KAG-anonymized (Materia Medica Кагоцел)

| Field | Value |
|---|---|
| Original brand | Кагоцел |
| Manufacturer | Materia Medica Holding |
| Anonymization code | `KAG-2024` |
| Category L1/L2/L3 | OTC / cold_flu / antiviral |
| ATC class | J05AX (other antivirals) |
| Pricing tier | MAINSTREAM |
| Brand size | LEADER |
| Distribution | NATIONAL |
| Media maturity | PULSING (sezonal спайки осень-зима) |
| Lifecycle | MATURE |
| Data history | 3+ года weekly (DSM + Mediascope TV + Digital) |
| Aurora model status | Trust 3 hierarchical Bayesian validated v1.0.16 (commit `2cf603f`) |
| Reason for inclusion | Самая отвалидированная модель в портфолио Эконометрики. Polished post v1.2.0 audit (838 pytest pass). Lift formula canonical fix applied. |
| Transferable parameters | adstock decay (per-channel posterior), hill saturation gamma + half-saturation, category seasonality (52-week pattern, осень-зима peak), long-term trend |
| Excluded parameters | β coefficients, baseline, residual variance |

### Candidate 2 — VEN-anonymized (Венарус)

| Field | Value |
|---|---|
| Original brand | Венарус |
| Manufacturer | (Servier? — `?` уточнить у Антона; в memory упомянут Materia Medica? как preliminary) |
| Anonymization code | `VEN-2024` |
| Category L1/L2/L3 | OTC / venotonic / chronic_venous_insufficiency |
| ATC class | C05CA (bioflavonoids) |
| Pricing tier | PREMIUM |
| Brand size | CHALLENGER |
| Distribution | NATIONAL |
| Media maturity | ALWAYS-ON |
| Lifecycle | MATURE |
| Data history | Live-test проводился (см. memory `project_econometrica_v1_1_0_live_test_polish.md`) — exact horizon уточнить |
| Aurora model status | Trust 3 v1.1.0 live-test ready, post-polish 14 fixes applied |
| Reason for inclusion | Categorical diversity vs Кагоцел (venotonic ≠ antiviral). PREMIUM pricing tier coverage. ALWAYS-ON media pattern (контраст к PULSING Кагоцела). |
| Open question | Manufacturer confirmation (для anonymization context) |

---

## 2. Открытые вопросы Антону (для INBOX_TO_MN)

### 2.1 ROSST — что это?

В моей памяти **ROSST упоминается только в контексте release infrastructure** (`rosst-updates` repo для `latest.json` auto-update endpoint). В Aurora Launch repo также — только release pipeline (CONTRIBUTING.md, THREAT_MODEL.md).

**Гипотезы:**
1. ROSST = клиентский бренд / компания, которого я не знаю (Антон передавал shortlist устно).
2. ROSST = аббревиатура — Российский [...?]. Возможно фарма-компания.
3. Confusion с другим именем — возможно ROSSI / ROST / ROSST AG.

**Запрос Антону:** что такое ROSST в контексте donor base? Если это клиент Эконометрики — название бренда + категория ATC + manufacturer.

### 2.2 Дополнительные 2-3 кандидата (для покрытия категорий)

**Уже покрыто:** OTC.cold_flu.antiviral (Кагоцел) + OTC.venotonic (Венарус). Это 2 из 5+ нужных.

**Категорийные gaps в shortlist:**
- **OTC.analgesic** (НПВС, парацетамол, ибупрофен) — массовая фарма-категория, частые launches новых SKU
- **OTC.digestive** (probiotics, антациды, желчегонные)
- **OTC.dermatology** (cosmeceuticals OTC, акне-средства)
- **OTC.immune_support** (иммуномодуляторы, supplements)
- **Rx.cardiology** (если есть в pipeline Эконометрики)
- **OTC.respiratory_relief** (отличается от antiviral — мукоактивы, противокашлевые)

**Запрос Антону:**
1. Какие ещё бренды из existing Эконометрика clients готовы к anonymization? (фарма приоритет, не FMCG / cosmetics — per ICP correction 2026-05-05)
2. Если "ROSST" не клиент Эконометрики — заменить ли на другое существующее? Или ROSST = плейсхолдер для будущего пилота?
3. Допустимо ли использовать данные Эконометрика клиентов БЕЗ их прямого consent (anonymization достаточна) или нужен informational notice? (Per Section 3 protocol — техническая anonymization достаточна по Антону, но для critical clients double-check.)

---

## 3. Anonymization protocol (per Антон 2026-05-05)

**Принцип:** техническая anonymization достаточна. Согласия клиентов НЕ требуются (если данные не покидают anonymized form). Brand identity not derivable из donor entry.

### 3.1 Mandatory anonymization steps

| Field | Transformation | Rationale |
|---|---|---|
| Brand name | → код `<3-letter>-<year>` (e.g., `KAG-2024`, `VEN-2024`) | De-identification primary |
| Manufacturer | → удалить полностью | Brand → manufacturer mapping public knowledge |
| Sales numbers (units / revenue) | × random factor 0.5-2.0 (constant per donor для preserve shape) | Magnitude masking, shape preserved |
| Media spend numbers | × same random factor (synchronized с sales) | Preserve ROI ratios |
| Period dates | shift by -12 months (constant per donor) | Preserve seasonality, hide actual time window |
| Specific creative names / campaign names | → удалить (если присутствуют в metadata) | Identifying details |
| SKU names / pack sizes | → generic codes (`SKU_1`, `SKU_2`) | Brand identification vector |

### 3.2 Preserved fields (для category match + transfer accuracy)

| Field | Why preserved |
|---|---|
| ATC class | Category match для similarity framework (S003 SIMILARITY_FRAMEWORK) |
| Category L1/L2/L3 | Same |
| Pricing tier (relative) | Pricing dimension в similarity score |
| Brand size (LEADER/CHALLENGER/NICHE) | Similarity dimension |
| Distribution tier (NATIONAL/REGIONAL/NICHE) | Similarity dimension |
| Media maturity (ALWAYS-ON/PULSING/PROMO/DORMANT) | Similarity dimension |
| Lifecycle stage (NEW/GROWING/MATURE/DECLINING) | Similarity dimension |
| Adstock decay shape (per-channel posterior) | **Transferred parameter** |
| Hill saturation shape (gamma + half-sat) | **Transferred parameter** |
| Category seasonality (52-week deviation pattern) | **Transferred parameter** |
| Long-term trend slope | **Transferred parameter** |

**Note:** β coefficients, baseline, residual variance — **NOT transferred** (recipient-specific magnitudes), значит их anonymization бессмысленна — они пересчитываются на recipient anchor data (per ADAPTATION_RULES).

### 3.3 Anonymization automation

**Tool:** `tools/donor_anonymizer.py` (Sprint B6 deliverable).

**Input:** original `.aurora` или `.pickle` файл от Эконометрика project.
**Output:** anonymized `.aurora` bundle с metadata `donor_anonymized: true` + `random_factor_seed` (для reproducibility audit) + `period_shift_months: -12`.

**Audit trail:** anonymization log saved separately (НЕ в bundle) — Антон может aud check отображение брендов на коды для своих records.

---

## 4. Donor entry storage (Sprint B6 implementation hint)

**Location:** `aurora-platform-core/donor_library/<code>.aurora`

**Manifest extension:**
```json
{
  "donor_metadata": {
    "code": "KAG-2024",
    "category_l1_l2_l3": ["OTC", "cold_flu", "antiviral"],
    "atc_class": "J05AX",
    "pricing_tier": "MAINSTREAM",
    "brand_size": "LEADER",
    "distribution": "NATIONAL",
    "media_maturity": "PULSING",
    "lifecycle": "MATURE",
    "data_history_weeks": 156,
    "model_engine_version": "trust3_hierarchical_bayesian/1.0.16",
    "anonymized_at": "2026-05-XX",
    "anonymization_seed": "<sha256>",
    "approved_for_donor_library": true,
    "approved_by": "Антон Сипович",
    "approved_at": "2026-05-XX"
  }
}
```

**Donor library index:** `aurora-platform-core/donor_library/index.json` — searchable by category + similarity dimensions для proxy candidate suggestion (Phase C+ feature, AI-assisted proxy suggestion).

---

## 5. Acceptance criteria для B6 inclusion

Каждый донор passes:

- [ ] Anonymization automation script runs clean (no leftover identifying fields).
- [ ] Aurora Launch SimilarityCalculator able to score against test recipient.
- [ ] Transferred parameters (5 shape) extractable через `engines/launch_adapt.py`.
- [ ] Donor model uncertainty bounds preserved (posterior std не collapsed by anonymization).
- [ ] Антон's approval recorded в `donor_metadata.approved_by`.
- [ ] Property-based test passes: anonymized bundle → SchemaRegistry.migrate v3.0 → bundle reader open clean.

---

## 6. Recommended timeline (B6)

| Week | Activity |
|---|---|
| B6.1 | Антон confirms shortlist 5 final кандидатов (этот документ → ответ) |
| B6.2 | Anonymization script implementation + dry-run на Кагоцел + Венарус |
| B6.3 | Process 3 additional donors → anonymized `.aurora` bundles |
| B6.4 | Donor library index + similarity matching CLI prototype |
| B6.5 | Integration test: pilot recipient brand → similarity scoring → top-K donor selection → transfer + forecast |

---

## 7. Open coordination items

1. **Маша небесная adaptation:** Маша небесная может предложить дополнительных donor кандидатов из Tier 2/3 pilot pipeline (Stada CIS / Биннофарм) если clients consent — но эти не существующие Эконометрика clients, значит **scope creep** для B6. Default: оставить только Эконометрика-existing для B6, расширение после пилотов (per Маша небесная "расширение после пилотов").

2. **Donor library access tier:** included во все Suite tiers (Starter/Pro/Enterprise) или Pro+ feature? — Sprint B6 question, пока default included во все.

3. **Donor library size cap:** при росте библиотеки до 50+ donors, нужны fast similarity index (FAISS / hnswlib)? — Phase C+ consideration, для B6 N=5 linear scan adequate.

---

## 8. References

- Memory `project_aurora_launch_principles.md` § "Маша небесная Strategic Corrections 2026-05-05" item 3 (Donor library)
- Memory `project_econometrica_v1016_day1_optimize_cluster.md` (Кагоцел Trust 3 validated)
- Memory `project_econometrica_v1_1_0_live_test_polish.md` (Венарус live-test)
- Aurora Launch `02_Data_Spec/SIMILARITY_FRAMEWORK.md` (S003 — 6 similarity dimensions)
- Aurora Launch `03_Architecture/ADAPTATION_RULES.md` (S004 — 5 transferable shape params)
- Aurora Launch `05_Sessions/SESSION_001_concept_2026-05-04.md` D002 (revised by Маша небесная strategic correction)
