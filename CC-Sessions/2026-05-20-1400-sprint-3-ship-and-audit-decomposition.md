---
tags: [session, compressed]
type: session
updated: 2026-05-20
---

# Quick Reference

Aurora Launch Sprint 3 (Transparency + Drill-down + Methodology Cert + AV Submission) — 8 deliverables shipped в 7 commits + tag v0.1.4, PR #11 merged rebase. Post-merge multi-axis critical audit нашёл 21 findings (5 security + 8 a11y + 8 code quality); first reco Variant A (hotfix v0.1.5) был overengineered, revised к Variant D (Sprint 4 расширенный) после декомпозиции на 7 под-вопросов. Created `aurora-meta/SPRINT_BUFFER.md` v0.1 SSOT registry (items #21-#34) + INV-48 codified (Cross-product port security parity) в `aurora-meta/ENGINEERING_INVARIANTS.md` v2.3 (push `f74a72a`).

**Topic:** sprint-3-ship-and-audit-decomposition
**Key files:**
- Aurora Launch: PR #11 (7 commits), tag v0.1.4
- aurora-meta: `ENGINEERING_INVARIANTS.md` v2.3 (INV-48), `SPRINT_BUFFER.md` v0.1
- Memory: `feedback_audit_severity_requires_threat_model_pilot_check.md`, `feedback_sprint_buffer_ssot_registry_pattern.md`
- Next session: `Desktop/Aurora_Dev/Aurora-platform-core/NEXT_SESSION_PROMPT.md` (Sprint 4 расширенный)

**Status:**
- ✅ Sprint 3 closed, v0.1.4 tag, 17/17 CI green (1 flake re-run)
- ✅ Audit complete, 21 findings classified P0/P1/P2
- ✅ Sprint Buffer SSOT created, INV-48 codified, both pushed origin
- ⏭️ Sprint 4 ready to start (Pilot Scenarios + i18n RU + A11y + Sprint 3 hardening)

---

## Learnings

### 1. Audit severity grading требует threat model + pilot user profile check
**Self-correction lesson.** First reco после multi-axis audit dump'нула все P0 finding'ов как "CRITICAL" / "HIGH" без проверки реального threat model или pilot user profile. Антон попросил «подумай глубже», после декомпозиции на 7 под-вопросов severity grading изменилась:
- S1 (token gap): real, но pilot threat model sparse (friendly customers 4-6 weeks)
- A1 (touch 16px): WCAG fail, но pilot desktop primary (~5-10% touch usage)
- A3/A4 (screen reader): WCAG fail, но ~0% pilot screen reader users
- Hotfix 5 fixes одновременно = exponential регрессии risk
- Variant D (Sprint 4 расширенный) dominates по cost-benefit

Codified в `feedback_audit_severity_requires_threat_model_pilot_check.md`.

### 2. INV-48 — Cross-product port security parity: attack scenario test первым
**Sprint 3 D6 incident.** Port'нула `aurora-launch-reproduce` Python CLI в Rust IPC `verify_reproducibility`. Python имеет cross-binding защиту через `reproducibility_token = SHA-256(manifest_sha256 || data_artifacts_hash || version)` (Sprint 2 B-Audit-2/3 hardening). Rust port re-hashed только per-file `sha256` — anti-tamper защита **silently broken**. Атакующий с пересчитанными per-file hashes проходит Rust verification.

**Pattern:** при cross-product port security-critical логики — (1) grep source на security tokens, (2) написать attack scenario tests первым (INV-02 enforcement), (3) implementation passes только когда attack tests fail предсказуемо до implementation. Cross-language binary compatibility verified explicitly (Python `hashlib` output bytes-equal Rust `sha2` output).

Codified в `ENGINEERING_INVARIANTS.md` v2.3, INV-48.

### 3. Sprint Buffer SSOT registry pattern
Sprint Buffer items до 2026-05-20 жили в session-specific Sprint closure logs (`CC-Sessions/YYYY-MM-DD-sprint-X-closure.md`). Sprint 3 commits ссылались на items #21-#24 но **central registry не существовало**. Risk: items forgotten между sessions.

**Resolution:** central SSOT `aurora-meta/SPRINT_BUFFER.md` v0.1 created. Item template: severity + file:line + recommendation + estimate. Sequential numbering cross-product. Sister pattern to `aurora-meta/PORTFOLIO.md` (portfolio SSOT) + `NAMING_GLOSSARY.md` (aliases SSOT).

Codified в `feedback_sprint_buffer_ssot_registry_pattern.md`.

### 4. Composition pattern: DrillDownModal → NotificationBanner
Sprint 3 D1 DrillDownModal — thin wrapper над `<NotificationBanner level="prompt">` через `children` + `actions` snippets. Focus trap, ESC handler, ARIA dialog role, backdrop, INV-14 reduce-motion — все делегировано базовому компоненту. DrillDownModal owns только drill-down content layout (formula + explanation + inputs + output + provenance). Composition eliminates ~30 LOC duplication vs если бы DrillDownModal реализовал свой modal.

Reusable pattern: CertExportModal **could** also use NotificationBanner, но full-screen overlay UX requires custom layout — inline focus trap reimplemented (Sprint Buffer #34: focus trap utility extraction).

### 5. ADR-006 PDF strategy validation
D5 cert PDF — chose Tauri webview print (`@media print` + `window.print()`) over Rust printpdf/genpdf crates. Avoids font-bundling complexity (cyrillic Inter font already loaded в webview через @fontsource), no new Rust dependency, Edge print dialog produces ~100-500KB clean PDF (well under 1-3MB spec upper bound). ADR-006 chose webview print как primary — validated.

Trade-off: user manually picks "Save as PDF" в Edge dialog (не programmatic). Acceptable — user expects clicking Export → getting save dialog anyway.

### 6. Pragmatic scope reframe — D4 wrap 9 numbers vs spec 40
D4 spec target — wrap ~40 numbers. После inspection of frontend code, real useful numeric displays which benefit from methodology context = ~9. Wrapping less prominent numbers (labels, status badges, secondary stats) would add visual noise без context value.

Sprint Buffer rationale: "spec targets были ad-hoc estimates, реальные useful counts ниже. Pragmatic reframe per `feedback_pragmatic_scope_reframe_to_ship`."

### 7. Always Opus audit pass после Sonnet delegation
Per `feedback_audit_after_sonnet_delegation`. Sprint 3 D3 (NumberWithDrillDown + ChartWithDrillDown) — Sonnet написал dead code (`_instanceCounter` + `nextInstanceId()` + `instanceId` never referenced в template). Opus audit поймал, удалила в same session перед commit. Similar pattern Sprint 3 D5 — Sonnet missed redundant aria-label на close button + needed @ts-expect-error removed.

---

## Decisions

### D1: Use NotificationBanner composition в DrillDownModal
**Why:** Avoids ~30 LOC duplication of focus trap + ESC + ARIA. `simplify` audit gate finding (ReproduceModal still owns its own modal logic — Sprint Buffer #21 future refactor candidate).

### D2: TrustScore NOT wrapped с NumberWithDrillDown (Sprint Buffer #22 alternative)
**Trigger:** D4 Sonnet wrap TrustScore сломал 4 vitest tests (DOM structure change broke `getByRole('button')` / aria-label selectors). Revert. Sprint Buffer #22: add "Что значат эти 8 измерений?" link в expert mode toggle area as alternative transparency mechanism — doesn't duplicate existing expert mode affordance.

### D3: PDF export strategy — Tauri webview print (ADR-006 primary)
**Options considered:** (A) Tauri webview print, (B) Rust `printpdf`/`genpdf`, (C) Python ReportLab. Chose A.
**Why:** No font-bundling complexity, leverages existing `@fontsource/inter` для cyrillic, Edge print engine handles all rendering. Spec said WeasyPrint exists in backend — recon показал ADR-006 явно reject'нул WeasyPrint (GTK friction Windows). Python `methodology_cert.py` produces только cert data, не PDF. Tauri webview print path is correct ADR-006 strategy.

### D4: verify_reproducibility — Pure Rust verification (not sidecar spawn)
**Options:** (A) Add sidecar method `reproduce_bundle`, (B) Spawn `aurora-launch-reproduce.exe` external binary, (C) Pure Rust verification reusing `composite_bundle_hash_mirror`. Chose C.
**Why:** No sidecar overhead, no PyInstaller binary dependency requirement, reuses Sprint -1 audited cryptographic infrastructure. CLI semantics equivalent — bundle is reproducible iff all files match manifest claims.

**Gap identified post-ship:** D4 решение skip'нул cross-binding `reproducibility_token` check, который Python CLI имеет (B-Audit-2/3). Anti-tamper защита **silently broken**. INV-48 codified, Sprint 4 Batch 2 closes this.

### D5: Revised audit reco — Variant D (Sprint 4 расширенный) вместо Variant A (hotfix v0.1.5)
**Why:** После декомпозиции на 7 под-вопросов:
- Pilot threat model sparse (friendly customers, 4-6 weeks)
- Pilot user profile excludes touch primary + screen reader concerns
- Hotfix 5 simultaneous fixes = high регрессии risk
- Sprint 4 уже scope'нут как A11y sprint — natural fit для остальных fixes
- INV-02 требует attack scenario tests первым = 1 день работы, не 30-min hotfix

Variant D расширяет Sprint 4 scope с 0.9 weeks → 1.5 weeks, 1300 LOC → 2300 LOC. Test infrastructure первым (Batch 1) по INV-48 + INV-02 discipline.

### D6: Sprint Buffer SSOT в `aurora-meta/SPRINT_BUFFER.md`
**Why:** Aurora-wide SSOT pattern (sister к `PORTFOLIO.md`, `NAMING_GLOSSARY.md`, `ENGINEERING_INVARIANTS.md`). Cross-session continuity. Items #1-#20 jewель reference к session logs (carry-forward section). Items #21+ — explicit registry с template (severity + file + recommendation + estimate).

### D7: INV-48 codification (not skip / not predict number)
**Why:** Cross-product port security parity = institutional lesson worth permanent codification. Per `feedback_inv_number_verify_before_claim` — grep'нула aurora-meta SSOT перед claim, last INV-47 → INV-48 verified. Sister к INV-02 (cryptographic claims), INV-15 (adapter wiring), INV-34 (preventive split).

---

## Pending

### Sprint 4 ready to start (расширенный scope)

**Файл:** `C:/Users/ackol/Desktop/Aurora_Dev/Aurora-platform-core/NEXT_SESSION_PROMPT.md`
**Триггер:** «начинаем Sprint 4» / «продолжаем Aurora Launch» (cwd = `D:\Docs\Aurora_Ai`)

**8 batches, 1.5 weeks, ~2300 LOC:**

- **Batch 1 (Day 1)** — Test infrastructure первым:
  - Rust integration test `tests/test_verify_reproducibility.rs` — fresh/tampered/forgery rejection/zip bomb/malformed hash/path traversal (6 tests)
  - Vitest `DrillDownModal.test.ts`, `NumberWithDrillDown.test.ts`, `ChartWithDrillDown.test.ts`, `AuditTab.test.ts` (4 files)
  - INV-48 + INV-02 enforcement: attack scenario tests first
- **Batch 2 (Day 2-3)** — Sprint 3 security hardening:
  - S1: `reproducibility_token` cross-binding validation (mirror Python `generator.py:175-194`)
  - S2: Streaming SHA-256 вместо `read_to_end` (zip-bomb prevention + memory efficiency)
  - S4: Hex format validation на `expected_sha256` (uppercase / empty / malformed → "diverged" с reason)
- **Batch 3 (Day 3-5)** — Original Sprint 4:
  - 3 synthetic pharma bundles (otc_immune, rx_cardio, generic_painkiller)
  - i18n RU complete (A16 RU only, EN deferred)
  - MICROCOPY_AUDIT_2026_05_16 followups если есть
- **Batch 4 (Day 5-6)** — A11y core:
  - A1: Touch target 16px → 24×24+ (WCAG 2.5.8 AA)
  - A3: KaTeX MathML `aria-hidden` (prevent double-announce)
  - A4: Persistent aria-live container (render `.audit-result` вне `{#if}`)
  - A5: Focus restoration to opener (NotificationBanner + CertExportModal)
  - A6: `@media (hover: hover) and (pointer: fine)` для hover-dependent rules
  - A7: ESC `stopPropagation` в NotificationBanner
  - axe-core sweep all routes
- **Batch 5 (Day 6-7)** — Code quality (Q2-Q7):
  - `firstSentence` extract в `formulas.ts`
  - `hasFormula` / `getAllFormulaKeys` / `getAllFormulas` cleanup (delete dead code или document intent)
  - DrillDownModal API consistency (add `formulaKey?: string` prop)
  - `statusTone`/`statusLabel` defaults alignment
  - Focus trap utility `$lib/utils/focus-trap.ts` Svelte action
  - CertExportModal prop `verification` → `verificationResult`
- **Batch 6 (Day 7-8)** — Final audit gates:
  - `aurora-lawyer-advertising` skill на pharma microcopy (152-ФЗ)
  - `verification-loop` full pass
  - `security-review` final sweep
  - `click-path-audit` every modal flow
  - INV check: INV-38/40/41/42/48 compliance
- **Batch 7** — Optional Sprint Buffer pulls if time remains
- **PR + merge + tag v0.1.5**

### Sprint Buffer #21-#34 — Sprint 4 closes ТОЛЬКО P0 + Q2-Q7

Остальные carry-forward к Sprint 5:
- #21: Refactor ReproduceModal под NotificationBanner
- #22: TrustScore "Что значат эти 8 измерений?" expert mode link
- #23: CertExportModal forecast summary extension
- #24: Windows py3.11 timer flake `test_phase_scale_s17_forecast_budget`
- #25: TOCTOU race exists()/canonicalize() — `methodology_cert.rs:462`
- #26: CLI command injection через bundleFileName — `CertExportModal.svelte:228`
- #27: Focus restoration to opener (covered Sprint 4 A5)
- #28: ESC stopPropagation (covered Sprint 4 A7)
- #29: span[role=button] → native button — `NumberWithDrillDown.svelte:86`

### Pending external (Sprint 5 prep)
- 5 AV vendor submissions (актуальное submission Антоном через docs в `packaging/av_submission/`)
- EV-cert provisioning (Comodo/Sectigo, ~$300-500/year, ~7 business days express)
- Microsoft Partner Network application (free tier для accelerated WDSI review)
- `security@auroraai.pro` mailbox setup

---

## Full Session Notes

### Sprint 3 commit log (linear history)

```
167a576 chore(release): bump version 0.1.3 → 0.1.4
34b5172 feat(sprint-3/D8): AV vendor whitelist submission package — 7 docs for 5 vendors
2a55e53 feat(sprint-3/D7): i18n RU keys для Sprint 3 microcopy (A16 RU-only)
ff462fe feat(sprint-3/D6): verify_reproducibility — per-file SHA-256 integrity check
3d0b8d4 feat(sprint-3/D5): methodology cert PDF export via Tauri webview print
c1e3c2a feat(sprint-3/D4): per-chart wiring — ForecastCone + RadarChart + BudgetSplitChart wrapped
bf2dd56 feat(sprint-3/D1-D3): transparency core — DrillDownModal + formulas registry + wrappers
```

### Files modified — Sprint 3 (24 files, ~3893 LOC)

**Frontend new components (4):**
- `frontend/src/lib/components/transparency/DrillDownModal.svelte` (272 LOC)
- `frontend/src/lib/components/transparency/NumberWithDrillDown.svelte` (241 LOC)
- `frontend/src/lib/components/transparency/ChartWithDrillDown.svelte` (245 LOC)
- `frontend/src/lib/components/inspector/CertExportModal.svelte` (467 LOC)

**Frontend new utility (1):**
- `frontend/src/lib/utils/formulas.ts` (339 LOC, 12 FormulaEntry registry + helpers)

**Frontend modified components (3):**
- `frontend/src/lib/components/inspector/ForecastTab.svelte` (+97 LOC — 1 chart + 3 numbers wrapped)
- `frontend/src/lib/components/inspector/SimilarityTab.svelte` (+24 LOC — 1 chart + 1 number)
- `frontend/src/lib/components/inspector/AuditTab.svelte` (340 LOC, replaces 13 LOC placeholder)
- `frontend/src/lib/components/inspector/CertTab.svelte` (+51 LOC — Export button)

**Frontend modified routes (2):**
- `frontend/src/routes/inspector/+page.svelte` (+5 LOC — passes bundlePath + appVersion)
- `frontend/src/routes/optimize/+page.svelte` (+46 LOC — 2 charts + 5 numbers wrapped)

**Backend (Rust) modified (2):**
- `src-tauri/src/commands/methodology_cert.rs` (+143 LOC — new `verify_reproducibility` command)
- `src-tauri/src/lib.rs` (+2 LOC — command registration)
- `src-tauri/Cargo.toml` (1 LOC — version bump)
- `src-tauri/Cargo.lock` (1 LOC — version bump)
- `src-tauri/tauri.conf.json` (1 LOC — version bump)

**Frontend IPC types (1):**
- `frontend/src/lib/ipc/client.ts` (+12 LOC — ReproducibilityFileMismatch + ReproducibilityResult types + ipc wrapper)

**Frontend i18n (1):**
- `frontend/src/lib/i18n/locales/ru.json` (+43 LOC — 38 new keys)

**Frontend deps (2):**
- `frontend/package.json` (+2 lines — katex@^0.16.0 + @types/katex@^0.16.8)
- `frontend/package-lock.json` (large lock changes)
- `pyproject.toml` (1 LOC — version bump)

**Packaging docs new (7):**
- `packaging/av_submission/README.md` (104 LOC)
- `packaging/av_submission/BUSINESS_JUSTIFICATION.md` (180 LOC — EN + RU canonical)
- `packaging/av_submission/symantec.md` (249 LOC)
- `packaging/av_submission/mcafee.md` (243 LOC)
- `packaging/av_submission/avast.md` (189 LOC)
- `packaging/av_submission/kaspersky.md` (190 LOC)
- `packaging/av_submission/defender.md` (275 LOC — HIGHEST priority vendor)

### Files modified — Post-audit SSOT artefacts

**aurora-meta repo (commit `f74a72a` pushed origin):**
- `aurora-meta/SPRINT_BUFFER.md` (NEW, 180 LOC) — v0.1 SSOT registry, items #21-#34
- `aurora-meta/ENGINEERING_INVARIANTS.md` (+82 LOC) — v2.3, INV-48 codified

**Memory updates (project memory `D--Docs-Aurora-Ai`):**
- `memory/feedback_audit_severity_requires_threat_model_pilot_check.md` (NEW)
- `memory/feedback_sprint_buffer_ssot_registry_pattern.md` (NEW)
- `memory/MEMORY.md` (updated — Sprint 3 closure section added)

**Sprint 4 prep:**
- `C:/Users/ackol/Desktop/Aurora_Dev/Aurora-platform-core/NEXT_SESSION_PROMPT.md` (overwritten — Sprint 4 расширенный scope)

### Setup & config changes

**KaTeX dependency install:**
```bash
cd "D:/Docs/Aurora_Ai/Aurora Launch/frontend"
npm install katex@^0.16.0 --save --legacy-peer-deps
npm install -D @types/katex --legacy-peer-deps
```
Note: `--legacy-peer-deps` required из-за histoire/svelte 5 peer conflict (`@histoire/plugin-svelte@0.17.17` requires svelte ^3 || ^4, project на svelte ^5).

**Tauri command registration** (`src-tauri/src/lib.rs:103`):
```rust
// Sprint 3 D6: bundle reproducibility verification
commands::methodology_cert::verify_reproducibility,
```

**Branch + tag operations:**
- Branch created: `feat/sprint-3-transparency-and-cert` от main HEAD `31b98ac`
- 7 commits added sequentially
- Push: `git push origin feat/sprint-3-transparency-and-cert`
- PR #11 opened via `gh pr create`
- Merge: `gh pr merge 11 --rebase --delete-branch` (linear history)
- Tag: `git tag v0.1.4 -m "..."` + `git push origin v0.1.4`

**aurora-meta sync:**
- Pull first: `git pull --rebase --autostash` (Already up to date)
- Commit: `f74a72a`
- Push: `git push origin main`

### Errors & workarounds

#### Error 1: TrustScore wrap broke 4 vitest tests
**Where:** D4 wiring — Sonnet wrapped `<span class="trust-score-number">{scoreClamped}</span>` с NumberWithDrillDown.
**Symptom:** vitest 4 tests failed:
- `expertMode=false → toggle button hidden`: `queryByRole('button')` returns NumberWithDrillDown's info button даже без expertMode
- `expertMode=true → toggle button visible`: multiple buttons returned
- `toggle expanded → diagnostics visible`: same multiple buttons issue
- `ARIA label "Уровень доверия: 87 из 100"`: old aria-label removed, new aria-label "{value} — нажмите для деталей"

**Workaround:** **Pragmatic revert.** TrustScore already has expert mode transparency mechanism (R̂/ESS toggle). Adding NumberWithDrillDown поверх = duplicated affordance + test maintenance cost. Reverted TrustScore changes. Sprint Buffer #22 — alternative approach via expert mode link.

#### Error 2: Windows py3.11 CI timer flake
**Where:** PR #11 CI matrix.
**Symptom:** `test_phase_scale_s17_forecast_budget.py::TestBudgetZeroImmediateCancel::test_budget_zero_elapsed_is_non_negative` failed на Windows py3.11 (timer race condition). Windows py3.12 + Linux + macOS — passed.
**Workaround:** `gh run rerun --failed 26153497516` — re-run passed cleanly. Pattern matches existing TestTimerScheduling skip marks ("timer-driven race-prone на macOS + Windows GitHub Actions runners"). Sprint Buffer #24 — skip mark or rewrite с polling assertion.

#### Error 3: KaTeX install peer dependency conflict
**Where:** Initial `npm install katex@^0.16.0 --save`.
**Symptom:** `Could not resolve dependency: peer svelte@"^3.0.0 || ^4.0.0" from @histoire/plugin-svelte@0.17.17`.
**Workaround:** Re-run с `--legacy-peer-deps` flag. Pattern per `feedback_tauri_dev_first_run_chain` — Svelte 5 + histoire peer conflict known issue, `--legacy-peer-deps` standard mitigation.

#### Error 4: Sonnet D1 wrote `@ts-expect-error` для formulas.ts before file existed
**Where:** Sonnet built DrillDownModal сначала, formulas.ts писалась Opus параллельно. Sonnet added `// @ts-expect-error formulas.ts ships in same commit batch (Sprint 3 D2)` к type import.
**Symptom:** После formulas.ts создан — svelte-check would fail на "Unused @ts-expect-error directive."
**Workaround:** Opus audit pass removed comment manually before commit. Pattern: при parallel agent work над related files — check directive comments после dependencies resolve.

#### Error 5: NumberWithDrillDown dead code (`_instanceCounter` unused)
**Where:** Sonnet D3 — wrote module-level counter + `nextInstanceId()` function + `const instanceId = nextInstanceId()` but **never referenced** в template (no aria-labelledby или id refs).
**Symptom:** Dead code, not caught by tests или svelte-check (valid TypeScript).
**Workaround:** Opus audit pass deleted lines 22-26 (counter declaration) + line 59 (`const instanceId`). Pattern: после Sonnet delegation — explicit "dead code grep" во время Opus audit pass.

#### Error 6: Edit tool typo `old_str_iginal`
**Where:** ENGINEERING_INVARIANTS.md INV-48 insertion.
**Symptom:** `InputValidationError: The required parameter 'old_string' is missing. An unexpected parameter 'old_str_iginal' was provided.`
**Workaround:** Retry с correct `old_string` parameter name. Minor mechanical, не повторяющийся pattern. No memory needed.

#### Error 7: pytest 7 pre-existing failures
**Where:** Sprint 3 audit verification.
**Symptom:** `tests/test_phase_pi_1_engines.py` (5 tests ModuleNotFoundError) + `tests/test_reproduce_bit_equal.py::TestSubprocessExecution` (2 tests) + `tests/test_mcmc_budget_check.py` (collection error psutil).
**Workaround:** Verified pre-existing — не Sprint 3 regression. Sprint 3 не touched Python code (frontend Svelte + Rust IPC + i18n only). Acceptable for AUDIT GATE — documented в audit gate verdict.

### Audit findings — 21 items by Sonnet 3-agent parallel + Opus synthesis

**Security (5):** S1 token validation gap (HIGH), S2 zip-bomb OOM (HIGH), S3 TOCTOU exists/canonicalize (MEDIUM), S4 unvalidated hash format (MEDIUM), S5 CLI command injection через filename (MEDIUM)

**A11y (8):** A1 touch target 16px (CRITICAL WCAG 2.5.8), A2 focus ring flicker (HIGH WCAG 2.4.7), A3 KaTeX MathML double-announce (HIGH WCAG 1.3.1), A4 aria-live on conditional render (HIGH WCAG 4.1.3), A5 focus restoration missing (MEDIUM WCAG 2.4.3), A6 hover media query missing `hover: hover` (MEDIUM), A7 ESC propagation (MEDIUM), A8 span[role=button] vs native button (LOW)

**Code quality (8):** Q1 zero tests for Sprint 3 (HIGH), Q2 firstSentence duplication (MEDIUM), Q3 hasFormula dead code (MEDIUM), Q4 DrillDownModal API consistency (MEDIUM), Q5 statusTone/Label asymmetry (MEDIUM), Q6 focus trap duplication (LOW), Q7 verification prop naming (LOW), plus reproducibility_token gap (subset of Q1 manifesting в HIGH security)

### Decomposition into 7 sub-questions

After first reco "Variant A: hotfix v0.1.5" + Антона "подумай глубже":

1. **Threat model для D6:** sparse (friendly customers 4-6 weeks), real anti-tamper hole but не P0 timing
2. **Pilot user profile:** desktop primary, 0% screen reader, ~5-10% touch — A11y findings не block pilot
3. **Hotfix cost-benefit:** 6h + risk 5 simultaneous fixes vs Sprint 4 natural consolidation — Sprint 4 dominates
4. **Critical для pilot:** only Q1 (test coverage gap) — tests первым в Sprint 4 Batch 1
5. **S1 hotfix exception:** INV-02 требует attack scenario tests первым = 1 day work, не 30-min hotfix
6. **Sprint Buffer SSOT:** central registry needed (found gap)
7. **Long-term lessons:** INV-48 cross-product port security parity

### Final reco: Variant D — Sprint 4 расширенный

Sprint 4 scope: original 0.9 weeks → 1.5 weeks, 1300 LOC → 2300 LOC. Adds:
- Batch 1: Test infrastructure (INV-48 + INV-02 enforcement)
- Batch 2: Sprint 3 security hardening (S1, S2, S4)
- Batch 4: A11y findings (A1, A3, A4, A5, A6, A7)
- Batch 5: Code quality cleanup (Q2-Q7)

P1/P2 → Sprint Buffer #25-#34 carry-forward к Sprint 5+.

### Multi-axis audit Sonnet delegation pattern (validated)

3 parallel Sonnet agents (zero file overlap) + Opus synthesis:
1. Security audit (Sonnet) — `methodology_cert.rs` + `CertExportModal.svelte` + frontend AuditTab
2. A11y + click-path audit (Sonnet) — all Sprint 3 + NotificationBanner
3. Code quality audit (Sonnet) — full Sprint 3 + INV cross-check + test coverage gaps

Plus Opus сама — INV cross-check + threat model + Red Team scenarios + synthesis + reco.

Total: ~40 минут wall-clock vs ~2 часа serial. Validated pattern для critical post-ship audits.

### Memory references (auto-loaded via project MEMORY.md)

- `feedback_audit_severity_requires_threat_model_pilot_check.md` (NEW)
- `feedback_sprint_buffer_ssot_registry_pattern.md` (NEW)
- `feedback_audit_after_sonnet_delegation.md`
- `feedback_periodic_audit_gates_in_long_plans.md`
- `feedback_anton_universal_communication_style.md`
- `feedback_agent_delegation_opus_supervises.md`
- `feedback_pragmatic_scope_reframe_to_ship.md`
- `feedback_svelte5_state_derived_from_props.md`
- `feedback_audit_inline_before_commit.md`
- `feedback_inv_number_verify_before_claim.md`
- `feedback_commit_created_files_same_session.md`
- `feedback_tactical_reco_lead_with_definitive_not_menu.md`
- `feedback_cryptographic_claims_attack_test_first.md`

### Cross-product applicability

- **INV-48** applicable ко всем 12 Aurora продуктам с cross-product port activity (Aurora Launch / Econometrica / Data Studio / Agency mono-program sync)
- **SPRINT_BUFFER.md SSOT pattern** Aurora-wide — future imports от Econometrica / Agency / Data Studio через own numbering range или sequential
- **Audit severity grading discipline** (threat model + pilot user profile) — applicable ко всем pre-pilot products в Aurora линейке

### Session timeline (МСК)

- ~08:00-10:00 — Recon + planning (Sprint 3 scope verification, branch creation, katex install)
- ~10:00-12:00 — D1-D3 (transparency core, Sonnet делегация + Opus audit)
- ~12:00-12:39 — D4 + D5 + D6 + D7 + D8 (parallel Sonnet jobs для каждого batch)
- ~12:39 — Version bump + PR + CI wait
- ~13:00 — Windows py3.11 flake re-run + merge + tag v0.1.4
- ~13:00-13:30 — Sprint 3 closure + audit запуск (3 parallel Sonnet agents)
- ~13:30-13:45 — Audit synthesis + first reco Variant A
- ~13:45 — Антона feedback "подумай глубже"
- ~13:45-14:00 — Decomposition + Variant D revised reco + SSOT artefacts creation
- ~14:00 — Wrap-up + memory updates + NEXT_SESSION_PROMPT
- ~14:00 — /compress (this file)
