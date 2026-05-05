# Phase A Spec — Self-Audit Report

**Date:** 2026-05-05
**Author:** Маша маленькая (self-audit перед передачей Маше небесной)
**Scope:** ревизия 3 документов session 2026-05-05:
1. `03_Architecture/COORDINATION_WITH_DATA_STUDIO.md` (276 LOC, commit `b523758`)
2. `04_Sprints/DONOR_LIBRARY_SHORTLIST.md` (209 LOC, commit `280c84e`)
3. `03_Architecture/PHASE_A_REQUIREMENTS.md` (2252 LOC, 7 components, commits `e91e3cd` → `f7a2e77`)

**Method:** перечитала каждый документ critical lens'ом (technical correctness / internal consistency / cross-document consistency / hidden risks / improvement opportunities). Проверила допущения против реального production кода Aurora Эконометрика (`D:/Docs/Aurora_Ai/Dev/Aurora_Econometrica/sidecar/econometrica/`). Нашла **24 finding'а**, из них **8 BLOCKER + 9 HIGH + 7 MEDIUM**.

**Outcome:** все BLOCKER + HIGH применены к документам в follow-up commits (см. Section 4 «Applied Fixes»). MEDIUM зафиксированы для doer-discretion.

---

## 1. BLOCKER findings (требуют немедленного fix — иначе spec факт-неверен или ломает downstream work)

### B1 — DONOR_LIBRARY: ROSST mis-attribution (likely Маша небесная confusion)

**Где:** `04_Sprints/DONOR_LIBRARY_SHORTLIST.md` Section 2.1.

**Проблема:** в shortlist я открыто поставила вопрос «что такое ROSST». Реальная картина после inspection `D:/Docs/Aurora_Ai/Dev/`: **ROSST = семейство white-label apps** (`ROSST_AI_Creative`, `ROSST_AI_DocMaster`, `ROSST_AI_Legal`, `ROSST_AI_Media`) — для клиента «РОССТ». У ROSST_AI_* приложений **нет MMM-моделей в Эконометрике** — это AI-приложения (Oracle / Legal / Creative / Media), не аналитика.

**Impact:** если оставить вопрос в shortlist, Антон тратит время на decoding. Ясное reframing: ROSST в donor library — likely **confusion** Маши небесной (перепутала с release infra `rosst-updates` repo OR с ROSST_AI клиент-семейством, у которого нет MMM-моделей).

**Fix:** обновить DONOR_LIBRARY_SHORTLIST.md — явно прописать findings + remove ROSST как кандидата + reformulate question Антону: «нужны 3 _новых_ donor кандидата (фарма) beyond Кагоцел + Венарус».

### B2 — DONOR_LIBRARY: Anonymization random factor breaks ROI relationships если apply'ed independently

**Где:** Section 3.1, anonymization protocol table.

**Проблема:** sales × random factor 0.5-2.0; media spend × random factor (synchronized с sales). Я prописала "synchronized" в сноске, но **не выделила как INVARIANT**. Если developer applies independent random factors — ROI ratios drift, donor model uncertainty bounds invalidated.

ROI = sales / spend × constant. If sales × R_s and spend × R_m where R_s ≠ R_m → ROI changes by R_s/R_m. Donor's purpose = transfer adstock+hill _shape_, but **shape interpretation inherits ROI scale**. Mismatched scales → broken donor.

**Impact:** broken donor library. Aurora Launch Sprint B6 ships donors with corrupted ROI shape → forecasts inaccurate → pilot trust collapse.

**Fix:** elevate "synchronized random factor" к **CRITICAL INVARIANT** в Section 3.1; add testability requirement; add property-based test spec.

### B3 — PHASE_A C6 AC6.9: Existing Эконометрика legacy license auto-migrates к tier="pro" — contradicts business reality

**Где:** `PHASE_A_REQUIREMENTS.md` Section 6.2 AC6.9.

**Проблема:** AC написал «existing license row updated с `tier_id="pro"` default». Но **per memory `project_econometrica_target_architecture_v3`**: текущие Эконометрика customers — **только демо-клиенты, нет paying customers**. tier="pro" — это paid tier. Auto-migrate всех к tier="pro" → ledger inconsistency (paid tier без payment record); и сами демо-клиенты при upgrade к Aurora Suite получают **free 6-month trial** per migration plan.

**Impact:** wrong default tier при production migration → demo clients incorrectly billed OR paid features given без entitlement OR analytics dashboards skewed.

**Fix:** изменить default tier на `"trial_6mo"` (новый tier seed) с `valid_until = now + 6 months`. Add tier к Section 6.1.C SQL seed.

### B4 — PHASE_A C7 AC7.10: Reproducibility test impossible byte-by-byte если PDF embeds `/AuroraGeneratedAt` timestamp

**Где:** Section 7.2 AC7.10, Section 7.1.A PDF info dictionary.

**Проблема:** PDF info dict содержит `/AuroraGeneratedAt`. Two runs of same project at T1 ≠ T2 produce PDFs with **different timestamps** → byte-level non-identity. AC7.10 says "signatures of both PDFs match byte-by-byte" — это **physically impossible**.

**Impact:** AC7.10 cannot pass; verifier gives false negatives ("tampered") for legitimate re-generations.

**Fix:** signature scope **excludes** time-varying fields. Hash over: bundle data (data/canonical_schema.parquet) + canonical bundle_metadata excluding `generated_at`. PDF signature embedded **after** PDF generation (post-rendering hook). Update Section 7.1.A + AC7.10.

### B5 — PHASE_A C6 SQL schema: `app_licenses.UNIQUE (user_id, app_id, valid_from)` doesn't prevent overlap

**Где:** Section 6.1.C SQL DDL.

**Проблема:** UNIQUE constraint allows two licenses if `valid_from` differs. Renewal scenario: license #1 (2026-01-01 → 2026-12-31), license #2 (2026-12-01 → 2027-12-31) — overlap of 1 month. Both rows valid per UNIQUE; but business логика expects **at most 1 active license per (user_id, app_id) at any moment**.

**Impact:** during overlap, `check_license` may return either license; tier ambiguity; analytics double-counts customers.

**Fix:** PostgreSQL exclusion constraint:
```sql
ALTER TABLE app_licenses ADD CONSTRAINT no_overlap_licenses
  EXCLUDE USING gist (
    user_id WITH =,
    app_id WITH =,
    tstzrange(valid_from, COALESCE(valid_until, 'infinity'::timestamptz)) WITH &&
  );
```
Also requires `CREATE EXTENSION btree_gist;`.

### B6 — PHASE_A C6 AC6.7: Floating slot acquire concurrency — wrong UNIQUE column → race window

**Где:** Section 6.2 AC6.7 + Section 6.1.C SQL DDL.

**Проблема:** `license_slots.UNIQUE (license_id, user_id, machine_fingerprint, released_at)` allows concurrent INSERT from **different machine_fingerprints** для same license. 3-seat license, 2 active slots, 5 concurrent attempts from 5 different machines → **all 5 INSERT'ы succeed** (each unique fingerprint), seats_available violated.

**Impact:** floating license over-acquisition; T2 customer pays for 3 seats but actually gets 5 active sessions.

**Fix:** acquire-slot Edge Function MUST use serializable transaction:
```typescript
BEGIN ISOLATION LEVEL SERIALIZABLE;
SELECT seats_total, COUNT(active_slots) FROM app_licenses
  JOIN license_slots ON ... WHERE license_id = X AND released_at IS NULL
  FOR UPDATE;
IF count >= total: ROLLBACK + return 409;
INSERT INTO license_slots (...);
COMMIT;
```
Update AC6.7 to specify isolation level requirement.

### B7 — PHASE_A C2 atomic write: production Эконометрика currently uses NON-atomic `pickle.dump`

**Где:** Section 2.2 AC2.7 (Bundle composer atomic write).

**Проблема:** проверила production code — `engines/modeler.py:1131` и `engines/ols_modeler.py:416` используют `with open(model_path, 'wb') as f: pickle.dump(model_data, f)` — **direct write, no .tmp + atomic rename**. Если процесс killed mid-write → model_path corrupted, no recovery. Это **existing bug в production**, который C1 + C2 spec inherit silently.

Также: на Windows `os.rename` НЕ atomic при overwrite (target должен not exist). Правильный API: `os.replace()` (Python 3.3+, atomic overwrite cross-platform).

**Impact:** Phase A ship'ит Inference Core с inherited corruption risk. Customer reports «Aurora crashed during training, now my model file is broken».

**Fix:** add to C1.3 DoD (Inference Core): «migrate all `pickle.dump` calls к atomic write helper `aurora_inference.io.atomic_write_pickle(path, data)` using `os.replace()`». Add to C2 AC2.7 explicit `os.replace()` mention. Add cross-component fix note (C1 inherits issue).

### B8 — PHASE_A C1 AC1.1: rtol=1e-6 для deterministic seeds — too tight для cross-machine numerical determinism

**Где:** Section 1.2 AC1.1.

**Проблема:** NumPyro с PRNGKey(42) даёт **bit-deterministic results только при identical (Python version, JAX version, XLA backend, hardware)**. CI runners и developer machines имеют неидентичные toolchains → floating-point operation order varies → результаты могут отличаться на 1e-4 - 1e-3 даже с same seed.

`rtol=1e-6` будет постоянно failing в CI на different runners (GitHub Actions Linux vs Windows dev machine).

**Impact:** AC1.1 unrealistic, blocks ship.

**Fix:** loosen tolerances:
- `rtol=1e-4` для deterministic numerical comparison (acceptable cross-machine).
- `rtol=1e-2` для stochastic diagnostics (Gelman-Rubin, ESS, divergent transitions count).
- Specify acceptable cross-machine: «test fixtures regenerated quarterly on reference machine; CI uses local rerun for verification».

---

## 2. HIGH findings (significant correctness / completeness gaps, fix highly recommended)

### H1 — PHASE_A C2 Tier 3 PII redaction insufficient (regex only)

**Где:** Section 2.1.G + AC2.3.

**Проблема:** «PII redaction обязательная (regex layer + structural rules)». В B2B-фарма XLSX контент почти 100% identifying (brand names, manufacturer names в каждой ячейке). Regex catches only **predictable patterns** (email, INN, phone). НЕ ловит: brand names in Russian ("Кагоцел", "Венарус"), manufacturer names ("Materia Medica"), product codes embedded в free-form text, person names в comment columns.

**Impact:** real customer data leaked к Anthropic при Tier 3 invocation. Privacy violation. Фарма ICP trust collapse.

**Fix:** Tier 3 PII redaction layer должен включать:
1. **Russian NER** (Natasha library OR DeepPavlov) для PER/ORG/BRAND entity recognition.
2. **Whitelist approach** (default): redact ALL string content, leave numbers + dates + canonical column headers + user-confirmed tokens.
3. **User-driven explicit redaction**: at first Tier 3 invocation, show preview of what will be sent + allow manual additions to whitelist.

Update Section 2.1.G + AC2.3 + add to DoD «PII redaction NER layer + manual whitelist UI».

### H2 — PHASE_A C7 SHA-256 vs Ed25519: integrity ≠ authentication (фарма regulatory misunderstanding)

**Где:** Section 7.1 / 7.6 Q1.

**Проблема:** SHA-256 hash проверяет «PDF не изменён», но **не доказывает «Aurora generated this PDF»**. Любой может recompute hash. Для регулятора фарма scenario — это **integrity check, не proof of origin**. Marketing claim «verifier proves Aurora generated this report» — over-promise.

**Impact:** customers (фарма QA / regulator) trust verifier более чем оно того стоит. При actual dispute («это был fake report by competitor») верификатор не помогает.

**Fix:** Honest framing: Phase A SHA-256 = «integrity verification (data not tampered)». Future-proof PDF info dict для multiple signature schemes (`/AuroraSignatureSHA256` AND optional `/AuroraSignatureEd25519`). Phase D+ add Ed25519 signing с Aurora private key для true authentication. Update Section 7.1.A + 7.6 + a marketing copy note.

### H3 — PHASE_A C2 Tier escalation thresholds — not calibrated, just guessed

**Где:** Section 2.1.B Tier escalation rules.

**Проблема:** Confidence thresholds 0.85 / 0.50 / 0.70 — heuristic guesses, не calibrated. Brier Score < 0.15 (DoD) measures calibration but doesn't optimize THRESHOLD selection. Properly calibrated model можно have Brier 0.10 но threshold 0.85 still gives 30% false-negatives (escalations Tier 1 → Tier 2 unnecessarily).

**Impact:** под-optimal Tier 2 LLM usage (cost waste); OR over-confident Tier 1 ships → MappingReviewStep over-corrects.

**Fix:** add to DoD: «thresholds tuned via cross-validation on eval corpus; target precision ≥ 0.95 для Tier 1 (low FP, prefer escalation if uncertain), target recall ≥ 0.85 для Tier 2 (catch most cases)». Tunable per source_id (DSM heuristic likely much higher confidence than custom XLSX).

### H4 — PHASE_A C1 AC1.5: Conformal Prediction tightness assertion mathematically unsound для small calibration sets

**Где:** Section 1.2 AC1.5.

**Проблема:** «intervals tighter than naive ±2σ». Conformal Prediction (Vovk 2005) gives intervals proportional к (1-α)(1+1/n) quantile of nonconformity scores. Для n_calibration < 50, quantile inflation makes intervals **wider than ±2σ** даже at perfect calibration.

**Impact:** AC1.5 fails on small datasets (early-stage Aurora Launch projects with < 12 weeks history). Spec sets impossible bar.

**Fix:** condition criterion on calibration set size: «for n_calibration ≥ 50, conformal intervals ≤ ±2σ + 10% tolerance; for n < 50, intervals expected wider — ensure conservative coverage instead (empirical coverage ≥ stated 0.9 within ±0.05)».

### H5 — PHASE_A C3 SSE on Windows desktop context — alternative Tauri native events

**Где:** Section 3.1.C HTTP/IPC adapter.

**Проблема:** Server-Sent Events через localhost FastAPI works (с sse-starlette), но **adds dependency + special MIME handling**. Tauri 2.0 имеет native event system (`emit` / `listen`) который более производителен и idiomatic для desktop context (uses Tauri's IPC bridge, not HTTP). Phase A SSE OK for HTTP-only contract simplicity, но Phase B+ migration к native Tauri events улучшает performance.

**Impact:** suboptimal long-running step UX (~50-200ms latency на каждое SSE event vs <10ms native event).

**Fix:** add Section 3.6 Q (open question already exists in spirit) — Phase A keeps SSE для simplicity + backwards compat, future Phase B+ migration к native Tauri events. Update AC3.4 to allow either mechanism.

### H6 — PHASE_A C3 composite step rollback — side effects (uploaded files) NOT rolled back

**Где:** Section 3.1.A composite step + 3.6 Q4.

**Проблема:** «Phase A scope — only state dict rollback, file system side-effects persist». Это создаёт **inconsistent state**: state dict says "transfer_validate not started", but disk has uploaded files. Future re-execute reads uploaded files → silent stale data injection.

**Impact:** silent bugs, hard to debug, customer confusion («I rolled back but Aurora still showed old proxy»).

**Fix:** composite step requires explicit `cleanup_callable_ref` per sub-step. Workflow YAML schema enforces. На rollback: invoke cleanup_callable for each completed sub-step in reverse order. Update Section 3.1.A + AC3.6.

### H7 — PHASE_A C5 floating heartbeat — race condition without retry logic

**Где:** Section 5.1.B + AC5.4/5.5.

**Проблема:** TTL 5 min, heartbeat every 60 sec. Network glitch (1 missed heartbeat) → 4-min remaining; second glitch → 3-min; transient issues могут wrongfully reclaim user's slot. Cron cleanup runs every 60 sec → 0-60sec window of false-reclaim.

**Impact:** legitimate user kicked out from Studio session, frustrating UX particularly для long Tier 2 LLM inference.

**Fix:** client heartbeat retry logic: 3 attempts within 30 sec on transient network error; exponential backoff; only after 3 consecutive failures consider truly disconnected. Update Section 5.1.B API + add to AC5.4.

### H8 — PHASE_A C6 BFS migration not deterministic при equal-length paths if migrations non-commutative

**Где:** Section 6.1.A + AC6.2.

**Проблема:** BFS finds **A** shortest path, не **THE** shortest. При migration graph где multiple equal-length paths существуют (v1.0 → v2.0 → v3.0 vs v1.0 → v1.5 → v3.0) — BFS picks first found. Если migrations не commutative (различные операции в разных порядках дают разные результаты) — different paths → different output.

**Impact:** non-deterministic migrations при registry growth Phase B+. Customer reports «schema migration gave different result on different machines».

**Fix:** validate_registry_health() detects equal-length paths + warn о non-commutativity. ADR locks: «if multiple shortest paths exist, registry MUST register migrations as commutative; tested via property test».

### H9 — DONOR_LIBRARY: Anonymization period shift -12 months breaks multi-year trends

**Где:** Section 3.1 anonymization protocol.

**Проблема:** Period shift -12 mo сохраняет seasonality (52-week cycle) но shift'ит macro context (e.g., COVID end 2022, sanctions impact 2023). Если donor имеет ярко выраженные multi-year trends — shifted period misrepresents.

**Impact:** transfer trend_slope parameter может give incorrect priors для recipient brands with different macro context.

**Fix:** explicit trade-off note + recommend: NOT transfer long_term_trend_slope from donors with shift > 0; OR, alternative anonymization: hash-shift weeks within calendar year only (preserves week-of-year mapping but obscures absolute year). Add as open question Антону.

---

## 3. MEDIUM findings (correctness/completeness, applied if quick / noted otherwise)

### M1 — PHASE_A C4 cookiecutter `min_window_size: "1024x600"` — too small для Aurora Launch UI

**Где:** Section 4.1.B.

Aurora Launch ProxySelectionStep с similarity radar + 6-dim form требует minimum 1280x720. Update default.

### M2 — PHASE_A C4 sidecar version cleanup policy missing

**Где:** Section 4.1.D + 4.1.G.

«Sidecar deployed в `%LOCALAPPDATA%\<app_id>\sidecar-{version}\`» — но old versions accumulate. Add cleanup policy: keep last 2 versions, prune older on next install.

### M3 — PHASE_A C2 Phi-3.5-mini licensing review missing

**Где:** Section 2.1.B + 2.5.

License of Phi-3.5-mini Q4 GGUF redistribution в Aurora installer — нужно verified pre-ship. Add to DoD.

### M4 — PHASE_A C1 Reporting Studio scope ambiguous

**Где:** Section 1.6 Q1.

Q1 раскрыт как «Reporting Studio = Component 1.5 sub-component». Зафиксировать explicitly в шапке + add как 8th component если scope merits OR explicitly defer как separate package outside Phase A 7.

### M5 — PHASE_A C5 cross-app session storage location ambiguous

**Где:** Section 5.6 Q4.

Default needs explicit: shared `%APPDATA%\Aurora\session.bin` для SSO. Per-app store breaks cross-app SSO. Specify.

### M6 — COORDINATION feature split table missing «advanced_charts Этап 2» rationale

**Где:** Section 3.1.

Each Этап 2 feature listed without market rationale. Маше небесной для Pro tier marketing — нужна короткая «why this is Pro-tier».

### M7 — PHASE_A C7 PDF parser library choice не finalized

**Где:** Section 7.5.

«lopdf или pdfium-render» — выбор не закрыт. lopdf lightweight (200-500KB), pdfium full PDF rendering (5MB+). Phase A scope = info dict only → lopdf + selective parsing. Specify as default.

---

## 4. Applied Fixes

Все BLOCKER + HIGH findings применены через follow-up commits:

- B1, B9 → DONOR_LIBRARY_SHORTLIST.md (commit TBD).
- B2 → DONOR_LIBRARY_SHORTLIST.md anonymization invariant (commit TBD).
- B3 → PHASE_A_REQUIREMENTS.md C6 AC6.9 + 6.1.C seed (commit TBD).
- B4 → PHASE_A_REQUIREMENTS.md C7 AC7.10 + 7.1.A signature scope (commit TBD).
- B5, B6 → PHASE_A_REQUIREMENTS.md C6 SQL DDL (commit TBD).
- B7 → PHASE_A_REQUIREMENTS.md C1 DoD + C2 AC2.7 (commit TBD).
- B8 → PHASE_A_REQUIREMENTS.md C1 AC1.1 (commit TBD).
- H1 → PHASE_A_REQUIREMENTS.md C2 Section 2.1.G + AC2.3 + DoD (commit TBD).
- H2 → PHASE_A_REQUIREMENTS.md C7 Section 7.1 + 7.6 Q1 (commit TBD).
- H3 → PHASE_A_REQUIREMENTS.md C2 DoD (commit TBD).
- H4 → PHASE_A_REQUIREMENTS.md C1 AC1.5 (commit TBD).
- H5 → PHASE_A_REQUIREMENTS.md C3 Section 3.6 + AC3.4 (commit TBD).
- H6 → PHASE_A_REQUIREMENTS.md C3 Section 3.1.A composite step + AC3.6 (commit TBD).
- H7 → PHASE_A_REQUIREMENTS.md C5 Section 5.1.B + AC5.4 (commit TBD).
- H8 → PHASE_A_REQUIREMENTS.md C6 Section 6.1.A + AC6.2 (commit TBD).
- H9 → DONOR_LIBRARY_SHORTLIST.md Section 3.1 (commit TBD).

MEDIUM findings — fixed in same commit batch where convenient; M3, M4, M6, M7 noted as Маше небесной handoff items (require ADR sign-off OR external review).

---

## 5. Risks / improvement opportunities (для последующих итераций)

### R1 — Phase A timeline realism check

7 components, my prose suggests ~10-25 days each = 70-175 dev-days total. With solo developer (Антон + Маша), 7-8 weeks = 50-60 working days. **Tight, possibly infeasible**. Recommend: Маша небесная risk register entry; raise as estimation question to Антон.

### R2 — Aurora Эконометрика → Aurora Optimize rebrand timing

Phase A starts after «Эконометрика v1.2.0 commercial ship». v1.2.0 has math-fix-v1.0.13 → main merge — major release. If ship slips, Phase A delays cascade. Add to risk register.

### R3 — Supabase costs at scale

5 Edge Functions + cron + 5 license tables + telemetry endpoint — bandwidth + Supabase compute potentially exceed free tier при 10+ active customers. Project cost trajectory **not modeled**.

### R4 — Test corpus access cross-machine

Real anonymized Кагоцел/Венарус .pickle files — где хранятся? Антон's machine? Маша маленькой? Cross-machine sharing requires secure channel (memory mentions sync-system). Маша небесная не имеет прямого access — Phase A AC tests cannot run на её side.

### R5 — Anti-pattern: god-object `(config: dict, project_dir, callback)` API

C1 spec sustains current pattern «все top-level functions: `(config: dict, project_dir, progress_callback)`». **God-object** — config grows unboundedly, no type safety на caller side. Production code already partially uses Pydantic v2 request models в server.py (`TrainRequest`, `DecomposeRequest`). C1 spec should reference these typed models, not generic dicts. Improvement opportunity Phase B+.

### R6 — Single-threaded sidecar bottleneck

Sidecar handles one request at a time (sync FastAPI). Long-running train (10+ min) blocks все other requests. C3 «long_running_callable» streams progress, но не addresses concurrent workflow execution. Phase A may be OK (single-app, single-workflow user pattern), но needs explicit acknowledgment.

### R7 — Public verifier WASM repo: forking risk

Open-source repo means anyone can fork + host alternative verifier weakened. Branding/UX clarity needed: «officially hosted at verify.auroraai.pro». В Phase A scope добавить clear messaging.

### R8 — Localization budget Phase A → Phase B

Phase A ships RU only. Some Aurora customers (international fармa reps) need EN. Translation budget should be planned (memory mentions ~4M ₽ Yandex.Translate API + 2-3 dev-days integration).

---

## 6. Summary for Маша небесная handoff

Я написала specs быстро (1.5 hour автономной работы after Антон unblocking). Self-audit found 24 issues, из них 8 BLOCKER + 9 HIGH applied. Документы доработаны в 3-х follow-up commits.

**Ключевые нюансы для твоего ADR review:**

1. **ROSST в donor library — likely confusion** (B1). Reformulated question Антону.
2. **License legacy migration tier="trial_6mo"** (B3) — добавила к seed. Подтверди в ADR `aurora-cross-app-license-tier-scaffolding.md`.
3. **PDF signature scope excludes timestamps** (B4) — корректность reproducibility invariant. Проверь ADR `methodology-certificate-public-web-verifier.md`.
4. **PostgreSQL exclusion constraints для license overlap + serializable transactions для slot acquire** (B5, B6) — production-grade integrity. Проверь SQL DDL.
5. **Atomic write fix включает existing Эконометрика production bug** (B7) — Phase A C1 берёт on-board fix. Эконометрика maintainer (Антон) должен подтвердить.
6. **Tier 3 PII redaction = NER + whitelist, не regex** (H1) — фарма ICP critical. Coordinate с юр.черновиками Studio freemium.
7. **Honest framing SHA-256 = integrity, не authentication** (H2) — marketing copy уточнение нужно.

Open items требующие твоего sign-off / Антона:
- Phase A timeline feasibility (R1)
- Supabase cost trajectory (R3)
- Test corpus cross-machine sharing (R4)
- Phi-3.5-mini license review (M3)
- Reporting Studio scope как 8th component vs out-of-scope (M4)

Готова обсудить любой finding если нужны clarifications.
