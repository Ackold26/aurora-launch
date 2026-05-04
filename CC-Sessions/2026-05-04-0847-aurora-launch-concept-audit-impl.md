---
tags: [session, compressed, aurora-launch, concept, audit, phase-b]
type: session
updated: 2026-05-04
---

# Quick Reference

**Aurora Launch Phase B концепт + Data Requirements Spec + post-implementation audit + автономная коррекция 55+ findings + git init + memory update.** Создано **24 файла документации** (~10K строк) + 1 ADR + memory entries + plan file. Local git initialized (HEAD `a6dfbfd`, no remote yet - OQ003 pending). Phase B duration revised 5-6 → **7-8 нед** (sequential dependencies). S005 split: a (storage до B1) + b (posterior math до B5).

**Topic:** Aurora Launch concept finalization + Variant 2 Data Spec + post-implementation audit + fix application
**Key files:**
- `D:\Docs\Aurora_Ai\Aurora Launch\` (24 docs, git HEAD `a6dfbfd`)
- `~/.claude/plans/zippy-wobbling-waffle.md` (plan + Часть 4 audit findings 55+)
- `~/Desktop/zippy-wobbling-waffle-track.md` (live track)
- `~/.claude/projects/D--Docs-Aurora-Ai/memory/project_aurora_launch_principles.md` (memory)
- `~/.claude/projects/D--Docs-Aurora-Ai/memory/MEMORY.md` (index updated)

**Status:**
- ✅ DONE: concept (10 принципов), Data Requirements Spec, all architecture docs, 9 enhancement docs, audit + fixes, git commit, memory
- ⏳ PENDING (Антон decisions): OQ003 (git remote location), S003 (Similarity Framework), S005a (Storage Layer Decision - blocker для B1), S005b (Posterior math), S006 (Report sections), S007 (Multi-proxy UX), S008 (Pilot client), S009 (Pricing tiers), S010 (Sales playbook)

---

## Learnings

### About the product (Aurora Launch)

- **No donor library philosophy** - индивидуальный proxy подбор каждый раз через category expertise + DSM/Mediascope industrial data. Library bias-by-curation + categorical heterogeneity не работает для РФ-рынка.
- **Subscription model:** unlimited launches + 20-40h consulting hours/year, premium pricing 1.5-3M (Starter / Pro / Enterprise tiers).
- **Use cases scope strict:** только (1) новый бренд + (2) бренд с длительной паузой. NEW SKU portfolio launches → Aurora Optimize "New SKU" workflow (другая math).
- **Awareness НЕ в Launch** - вынесено в Aurora Brand. Launch = sales-only forecast. Это упрощает math (no Weibull adstock, no dual-posterior schema).
- **Local-first архитектура critical** - клиенты могут быть competitors (Wavemaker и Mindshare), их данные не должны mix через Aurora cloud.
- **Single-proxy default + multi-proxy expert toggle** - технически TWO разных engine (single_proxy_transfer + multi_proxy_hierarchical). Hierarchical с N=1 mathematically degenerates - hyperpriors lose identifiability.

### About the audit process

- **Self-audit на own work работает** - 55+ findings нашла без эхо-камеры через систематический read of created files и cross-checks.
- **Geopolitical accuracy** часто упускается в product docs - Disney запрещён в РФ 2022, Mail.ru/myTarget sunset 2024, WPP/Omnicom suspended РФ ops. Memory references к agency landscape могут drift'ить.
- **Performance budgets** требуют tier framework (cold/warm/premium HW), single budget unrealistic для Bayesian MMM с NumPyro.
- **Pydantic v2 patterns** - частая ошибка: `field_validator(values=...)` deprecated → `model_validator(mode="after")`. `parse_date()` undefined - Pydantic v2 уже coerces.
- **Conformal Prediction violation в transfer scenario** - exchangeability assumption broken. Tibshirani 2019 adaptive conformal нужен.
- **Test coverage 90% для math layer нереалистичен** - MCMC stochastic outputs. Property-based testing (Hypothesis) + reference comparison важнее coverage метрики.

### About workflow

- **Plan mode → audit → fix-apply → commit** - чистая sequence для quality work.
- **Track file (Desktop)** - позволяет resume work после compression / context loss. NEXT field critical.
- **Memory index entry** - под 200 chars compact но информативно (commit hash + file count + status).
- **Auto-commit local разрешён**, push - need approval (per user directive).

---

## Decisions

### Concept decisions (D001-D014)

| ID | Decision | Rationale |
|---|---|---|
| D001 | Aurora Launch цель: помощь новым / paused брендам через прокси | Gap в РФ market между Excel и Nielsen BASES |
| D002 | Отказ от donor library - индивидуальный proxy каждый раз | Categorical heterogeneity, bias-by-curation, library не покрывает РФ |
| D003 | Subscription model: unlimited launches + 20-40h consulting/year | Premium positioning, recurring revenue, hour tracking от старта |
| D004 | DSM Group + Mediascope как primary data sources | Legal-clean industrial syndicated data (vs scraping / illegal) |
| D005 | Подбор прокси и сбор данных = клиент / агентство | Aurora даёт spec, не data acquisition tool |
| D006 | Single-proxy default + multi-proxy expert toggle, two engines | Avoids hierarchical N=1 math degeneracy |
| D007 | Awareness не в Launch (отдан в Brand) | Clean product boundaries, separate sales motions |
| D008 | Use cases: только new brand + paused brand (не NEW SKU) | NEW SKU есть data → Optimize workflow |
| D009 | Forecast horizon до 52 нед (12/26/52 views с expanding cone) | >52w uncertainty слишком велика |
| D010 | 80%+ reuse from Aurora Econometrica | Engineering velocity + Suite consistency |
| D011 | Pydantic v2 + JSON Schema как SSoT | Auto-gen Python + TypeScript, single source |
| D012 | Quality stamp transparent (Tier badges Olympic-style) | Block forecast при Insufficient + override option |
| D013 | Premium Feel as P10 (after audit) | UX premium первоклассный, не post-fact polish |
| D014 | Local-first architecture explicit | Multi-tenant конкуренты, privacy critical |

### Audit-driven decisions

| ID | Decision | Source |
|---|---|---|
| A1 | Pydantic v2 model_validator (вместо deprecated field_validator) | F1 |
| A2 | Two engines (single_proxy_transfer + multi_proxy_hierarchical) | F4 - mathematical degeneracy |
| A3 | Conformal Prediction adaptation (Tibshirani 2019) | F17 - exchangeability violation в transfer |
| A4 | Phase B 7-8 нед (было 5-6) - sequential dependencies | F16 - arithmetic correction |
| A5 | S005 split → S005a (storage до B1) + S005b (posterior math до B5) | F18 - storage decision blocks schema design |
| A6 | SQLite hybrid recommended (vs pure pickle / pure SQLite) | F18 / SCHEMA_DESIGN.md |
| A7 | WeasyPrint для PDF Methodology Certificate | F22 - reuse aurora_html templates |
| A8 | A11y per-Sprint discipline (не B6 only) | F31 - design-time, не retrofit |
| A9 | Performance budgets cold/warm/premium HW tiers | F10 - reality vs plan optimism |

### Open architecture decisions (require Антон input)

| OQ | Decision | Blocker |
|---|---|---|
| OQ003 | Aurora Launch git remote location | After init - до push |
| OQ004 | (resolved через A6 - SQLite hybrid recommended) | - |
| OQ005 | WASM module commitment | Sprint B2 prereq |
| OQ006 | Streaming MCMC commitment | Sprint B1 prereq |
| OQ010 | Mediascope/DSM подписка кто платит | S010 |

---

## Pending

### Q&A Sessions roadmap (unblockers по sprints)

- **S005a** - Storage Layer Decision (SQLite hybrid vs pickle) → BLOCKER для **Sprint B1**. Recommended: hybrid (см. SCHEMA_DESIGN.md). Estimate: 1h dialogue + 1h ADR-002 written.
- **S003** - Proxy Similarity Framework (calibrate weights + thresholds) → BLOCKER для Sprint B2.
- **S007** - Multi-proxy UX (когда expert включает) → BLOCKER для Sprint B2.
- **S004** - Adaptation Rules detail → BLOCKER для Sprint B3.
- **S006** - Report Sections + PDF tool → BLOCKER для Sprint B4.
- **S009** - Pricing tier finalization (Starter/Pro/Enterprise) → moved up до Sprint B4.
- **S005b** - Posterior Update math (weight schedule formula) → BLOCKER для Sprint B5.
- **S008** - Pilot client identification → BLOCKER для Sprint B6.
- **S010** - Sales playbook → BLOCKER для Sprint B6.

### Architecture decisions

- **OQ003 git remote** - separate repo `aurora-launch` / sub-folder в `aurora-business` / monorepo. После decision: `git remote add origin <url> && git push -u origin main`.

### Phase A platform foundation prerequisites

Aurora Launch Sprint B0.5 не стартует до:
- `aurora-platform-core` package extracted + published
- Data Studio MVP (DSM + Mediascope importers) готова
- Tauri shell template available
- Workflow Engine API documented
- `cross_app_license` framework supports cross-app keys
- `schema_registry` pattern tested на Aurora Optimize backwards compat

### Future enhancement docs (не critical)

- AURORA_LAUNCH_VS_COMPETITORS.xlsx (E7 - sales sheet)
- i18n framework prep (E8 - keys structure для Phase D Eng support)
- PUBLIC_METHODOLOGY_SCAFFOLD.md (E10 - public website prep Phase C)

---

## Files Modified / Created

### Project files (24 docs, all committed в `a6dfbfd`):

**`D:\Docs\Aurora_Ai\Aurora Launch\`**:
- `.gitignore` (created)
- **00_Overview/** (3):
  - `PRINCIPLES.md` - 10 принципов (P1-P10) + Platform scope (Windows-only Phase B) + P10 testable criteria
  - `ROADMAP.md` - all phases A-D + sprints B0-B6 (7-8 нед)
  - `PRODUCT_BOUNDARIES.md` - что входит / не входит, decision tree для sales
- **02_Data_Spec/** (5):
  - `DATA_REQUIREMENTS.md` - master spec, Pydantic v2 models (model_validator), SemanticValidator с category-specific ratios
  - `DSM_FIELDS.md` - DSM Group fields detail + format adapters V2023/V2024
  - `MEDIASCOPE_FIELDS.md` - Mediascope TV/Digital + AdIndex (актуальный РФ landscape 2026)
  - `RECIPIENT_ANCHORS.md` - anchor form spec + Svelte 5 runes skeleton с error handling
  - `recipient_anchors_v1.schema.json` - JSON Schema SSoT (auroraai.pro $id)
- **03_Architecture/** (10 + 1 ADR):
  - `REUSE_FROM_ECONOMETRICA.md` - 80% reuse map + schema migration BFS topological + Pydantic schemas (TransferProvenance, ForecastHorizon, etc.) + LaunchConformalCalibrator + WeasyPrint PDF decision
  - `TEST_STRATEGY.md` - test pyramid 80/15/5 + property-based + 70-80% math coverage realistic + Tauri WebDriver limitations note
  - `UX_PRINCIPLES.md` - premium UX (P10) + Ctrl+K Windows + WCAG AA contrast verification table + a11y per-Sprint deliverables
  - `DATA_PRIVACY.md` - local-first + DPA + Ed25519 signing (corrected from "encryption") + termination policy GDPR-aligned
  - `PERFORMANCE_BUDGETS.md` - cold/warm/premium HW tiers + WASM bundle ≤200KB + realistic sample data sizes
  - `MATH_REFERENCE.md` (NEW E1) - canonical formulas: adstock, Hill, hierarchical Bayesian, posterior update, conformal adaptation, similarity, uncertainty decomposition, magnitude calibration, diagnostics + academic references (DOIs)
  - `SCHEMA_DESIGN.md` (NEW E2) - SQLite hybrid prep для S005a + recommended schema layout
  - `THREAT_MODEL.md` (NEW E5) - STRIDE + 10 risks ranked + compliance mapping
  - `OBSERVABILITY.md` (NEW E9) - 4 telemetry tiers + opt-in privacy
  - `ADR_TEMPLATE.md` - ADR creation template
- **03_Architecture/decisions/** (1):
  - `ADR-001-consulting-hours-persistence.md` (Accepted) - SQLite local-first per-license scoped
- **05_Sessions/** (2):
  - `SESSION_001_concept_2026-05-04.md` - session 001 log с 14 decisions + audit summary
  - `SESSION_NEXT_QUESTIONS.md` - Q&A roadmap S003-S010 + S005a/b split
- **06_References/** (3 NEW):
  - `INSTALL.md` (E3) - dev setup guide (Python + Node + Rust + JAX gotchas)
  - `CONTRIBUTING.md` (E4) - code style (Pydantic v2 + Svelte 5 runes) + PR + ADR process
  - `MIGRATION_GUIDE.md` (E6) - Aurora Launch → Aurora Optimize transition (после 12+ months)

### Memory files:

**`C:\Users\ackol\.claude\projects\D--Docs-Aurora-Ai\memory\`**:
- `project_aurora_launch_principles.md` (created → updated 2x): final state с git hash + audit summary + 24 files breakdown
- `MEMORY.md` (updated index entry в 🔴 System-wide Priority section)

### Plan/Track files:

**`C:\Users\ackol\.claude\plans\`**:
- `zippy-wobbling-waffle.md` - Initial plan (Часть 1+2) + audit Часть 3 + post-impl audit Часть 4 (55+ findings)

**`C:\Users\ackol\Desktop\`**:
- `zippy-wobbling-waffle-track.md` - live track с current task / done / next first step / decisions log + audit summary + git commit details

---

## Setup & Config Changes

### Git initialization (2026-05-04):

```
cd D:\Docs\Aurora_Ai\Aurora Launch
git init -b main
git config user.email "ackold@yandex.ru"
git config user.name "Антон Сипович"
```

`.gitignore` includes:
- OS: Thumbs.db, .DS_Store, desktop.ini
- Editor: .idea/, .vscode/, *.swp, *~
- Backup: *.bak, *.tmp, ~$*
- Office locks: .~lock.*
- Future build: __pycache__/, *.pyc, node_modules/, target/, dist/, build/, .venv/
- Future secrets: .env, .env.local, *.key, *.pem, license.json, aurora-secrets.env
- Privacy: TestData/, fixtures/private/, *.aurora

### Initial commit:

```
Commit: a6dfbfd
Branch: main
Files: 25 (24 docs + .gitignore)
Subject: chore: initial Aurora Launch project documentation
Co-author: Claude Opus 4.7 (1M context)
```

### Remote NOT configured

Pending OQ003 - где будет git remote:
- Option 1: separate repo `github.com/Ackold26/aurora-launch` (private)
- Option 2: sub-folder в `aurora-business` repo
- Option 3: monorepo с Aurora Suite (Phase A coordination)

---

## Errors & Workarounds (audit findings → fixes)

### BLOCKER fixes applied (15)

| ID | Problem | Fix |
|---|---|---|
| F1 | Pydantic v2 `field_validator(values=)` - deprecated v1 pattern | → `model_validator(mode="after")` с `Self` return |
| F2 | `parse_date()`, `now()` undefined imports | → `from datetime import date` + `date.today()` (Pydantic уже coerces) |
| F3 | `ValidationIssue` class undefined | → BaseModel с severity Literal, field, message |
| F4 | Heuristic `market_size * 0.05` = false positives 60%+ cases | → Category-specific ratios dict с info-level (не блок) |
| F5 | JSON Schema `$id` non-resolvable URL `https://aurora-launch/...` | → `https://auroraai.pro/schemas/launch/recipient_anchors_v1.json` |
| F6 | `additionalProperties: false` блокирует forward compat | → schema_version routing вместо relaxing strictness |
| F7 | `distribution_ramp_weeks` mandatory inconsistency между docs | → added в DATA_REQUIREMENTS Section 3.1 |
| F8 | `TransferProvenance, ForecastHorizon, PosteriorUpdateEvent, ConsultingEvent` undefined | → Pydantic schemas defined в REUSE_FROM_ECONOMETRICA.md |
| F9 | SchemaRegistry `_next_version()` undefined | → BFS topological migration path resolution |
| F10 | Performance budgets unrealistic для NumPyro Bayesian MMM | → cold/warm/premium tier framework |
| F11 | "License key encrypted (Ed25519)" - Ed25519 = signing, не encryption | → "signed (Ed25519)" + AES-256 cached |
| F12 | Channel mapping geopolitical errors (Disney, Mail.ru/myTarget) | → актуальный РФ 2026 landscape |
| F13 | "Adstock decay - категорийная характеристика" oversimplified | → per-channel с категорийным prior + uncertainty |
| F14 | Svelte `validateAnchors()` undefined import | → import + try/catch graceful degradation |
| F15 | Cmd+K на Windows-only product | → Ctrl+K / Ctrl+Shift+P (VSCode-style) |

### HIGH RISK fixes applied (9)

- F16: Phase B 5-6 нед → 7-8 нед (sequential dependencies)
- F17: Conformal Prediction в transfer violates exchangeability → adapted с similarity inflation factor (Tibshirani 2019)
- F18: S005 split → S005a storage (до B1) + S005b posterior math (до B5)
- F19: Test coverage math 90% → 70-80% + property-based + reference comparison
- F20: Tauri WebDriver limitations note + manual smoke fallback
- F21: WASM bundle ≤ 200KB gzipped budget added
- F22-F23: PDF generator decision (WeasyPrint - reuses aurora_html)
- F24: ADR template + ADR-001 process created

### MEDIUM/LOW fixes applied (26)

- distribution_velocity bug `< 180` matched negative days → `0 < days < 180`
- DSM/MS V2025 placeholder removed (formats не released)
- Sample data sizes 50KB → 1-2MB realistic
- pause_duration_months minimum 12 → 6
- Sound files WAV 256KB → OGG ~30KB
- A11y per-Sprint deliverables (не B6 only)
- ConsultingHoursWidget design + ADR-001
- AdIndex format adapter detection
- OpenAPI 3.1 explicit configuration
- Test python_wasm_consistency within tolerance (1e-6)
- Forward compat helper (`check_forward_compatibility`)
- ... etc

### Enhancement docs created (10)

- E1: MATH_REFERENCE.md - canonical formulas + DOIs
- E2: SCHEMA_DESIGN.md - storage prep
- E3: INSTALL.md - dev setup
- E4: CONTRIBUTING.md - style + ADR process
- E5: THREAT_MODEL.md - STRIDE
- E6: MIGRATION_GUIDE.md - Launch → Optimize
- E9: OBSERVABILITY.md - telemetry strategy
- (E7 XLSX, E8 i18n, E10 public methodology - deferred Phase C)

---

## Full Session Notes

### Session phases

**Phase 1: Concept dialogue (S001 - утро 2026-05-04)**

Антон представил видение:
- Помощь новым / paused брендам через прокси-modeling
- Индивидуальный proxy каждый раз (БЕЗ библиотеки доноров)
- Максимальный reuse Aurora Econometrica engines

Маша провела discovery через 5 ключевых вопросов:
1. Subscription tier modes - Антон выбрал unlimited launches + N consulting hours
2. Multi-proxy approach - default single, expert toggle multi
3. Awareness inclusion - вынести в Aurora Brand
4. Use cases scope - только new brand + paused brand
5. Forecast horizon - до 52 weeks с expanding cone

Финализированы 9 принципов работы продукта. Source decisions: D001-D013 (без P10 пока).

**Phase 2: Plan + initial audit (середина дня)**

Маша создала plan файл с:
- Часть 1: общий план (все этапы Phase A-D)
- Часть 2: детальный Variant 2 (Data Requirements Spec, файлы для создания, code skeletons)

Плюс Часть 3: первый аудит плана с 60+ findings (BLOCKER/HIGH/MEDIUM/LOW + ENHANCEMENTS) что улучшил план перед implementation. P10 Premium Feel добавлен как 10-й принцип.

**Phase 3: Autonomous implementation (Антон директива "реализуй все")**

17 файлов создано в batches (4-5 параллельно):
1. Track file (Desktop)
2. Overview batch (3 files)
3. Data Spec batch (5 files)
4. Architecture batch (5 files)
5. Sessions + Memory batch (4 files)

Total ~5500 lines documentation initial.

**Phase 4: Post-implementation audit (вечер)**

Антон попросил critical audit + fix application. Маша:
- Прочитала critical files (DATA_REQUIREMENTS, JSON Schema, MEDIASCOPE, REUSE, TEST_STRATEGY, PERFORMANCE_BUDGETS)
- Выявила 55+ findings:
  - 15 BLOCKER (technical errors, factual inaccuracies)
  - 9 HIGH RISK (architectural correctness)
  - 12 MEDIUM RISK
  - 14 LOW RISK
  - 10 ENHANCEMENTS

Документировала в plan файл Часть 4.

Антон директива "исправляй сразу, без approval" → Маша applied всё:
- Batch A (Pydantic + schemas critical)
- Batch B (documentation correctness - geopolitics, math, platform)
- Batch C (UX + Test + Performance)
- Batch D (Privacy + DSM + Sessions)
- Batch E (Memory updates)
- Batch F (4 new architecture docs: ADR template, ADR-001, MATH_REFERENCE, SCHEMA_DESIGN, THREAT_MODEL, OBSERVABILITY)
- Batch G (3 new reference docs: INSTALL, CONTRIBUTING, MIGRATION_GUIDE)

Total добавлено: 7 новых docs + ~25 в-place edits = 24 файла финал.

**Phase 5: Save & memory update (Антон "сохрани все")**

- `git init` в Aurora Launch folder
- `.gitignore` standard patterns
- Commit `a6dfbfd` "chore: initial Aurora Launch project documentation"
- Memory file updated с финальным statement (24 docs + git hash + audit summary)
- MEMORY.md index entry updated (200+ chars compact)
- Track file updated с git commit details + next action

### Critical context for future sessions

**Aurora Launch is NOT yet a coding project.** Все 24 файла - documentation. Phase B implementation начнётся когда:
1. Phase A platform foundation готова (Inference Core extracted, Data Studio MVP)
2. S005a Storage Layer Decision сделан
3. Sprint B0.5 BC Test Corpus собран

**Maintain integrity of audit fixes** - не reverse Pydantic v2 patterns, не reuse outdated channel mapping, не plan на 5-6 нед Phase B (8 недель realistic).

**Memory hierarchy:**
- `MEMORY.md` index entry: 200-char compact с status + commit hash
- `project_aurora_launch_principles.md`: full project memory (~6.5KB)
- `CC-Sessions/2026-05-04-0847-aurora-launch-concept-audit-impl.md` (this file): detailed session log

**Git state:**
- HEAD: `a6dfbfd` (initial commit)
- Branch: `main`
- Remote: not configured (OQ003 pending)
- Если Антон решит push - `git remote add origin <url> && git push -u origin main`

### Tech stack decisions (already made)

- **Backend:** Python 3.11+ with Pydantic v2 (model_validator), NumPyro JAX, FastAPI с OpenAPI 3.1
- **Frontend:** Svelte 5 runes ($state, $derived, $effect), TypeScript, ECharts 5
- **Shell:** Tauri 2 (Windows-only Phase B)
- **Math:** Bayesian MMM (existing v1.0.16) + Trust 3 hierarchical priors + adapted Conformal
- **WASM:** Rust → WASM для real-time similarity calculation в UI (≤200KB budget)
- **Storage:** SQLite hybrid recommended (S005a finalize) с pickle BLOBs для math artifacts
- **PDF:** WeasyPrint для Methodology Certificate (reuses aurora_html templates)
- **Schema:** JSON Schema 2020-12 как SSoT, auto-gen Python TypedDict + TypeScript interfaces

### Sprint plan (Phase B, 7-8 weeks total)

| Sprint | Duration | Status |
|---|---|---|
| B0 (Concept) | 1 day | ✅ DONE 2026-05-04 |
| B0.5 (BC corpus + format adapters) | 1 week | Pending Phase A complete |
| B1 (Schema extension + registry) | 1 week | Blocked by S005a |
| B1.5 (Customer Success Lite) | 3 days parallel | Sprint B1 dependency |
| B2 (Proxy Selection cabinet UI) | 1.5 weeks | Blocked by S003 + S007 |
| B3 (Adaptation + Transfer Validation) | 2 weeks | Blocked by S004 |
| B4 (Launch Forecast Report template) | 1 week | Blocked by S006 + S009 |
| B5 (Posterior Update workflow) | 1 week | Blocked by S005b |
| B6 (Pilot live-test + polish) | 1 week | Blocked by S008 + S010 |

### Premium UX deliverables (per Sprint)

- B2: Proxy Selection cabinet, similarity radar live, tier badges
- B3: Recipient Anchors form с real-time validation, Transfer Validate
- B4: Forecast cone animation, methodology certificate PDF
- B5: Posterior update visualization (weight schedule), audit trail timeline
- B6: Welcome experience, product tour, templates library, dashboard "My Aurora", Cmd-K command palette, full a11y audit

### Phase B success criteria

- 24 файла Sprint B0 deliverables ✅
- BC test corpus 10+ projects (B0.5)
- Pydantic v2 + JSON Schema SSoT (B1)
- Schema registry pattern (B1)
- Customer Success Lite tracker (B1.5)
- Proxy Selection cabinet UI с WASM similarity (B2)
- Two engines (single + multi proxy) (B3)
- Launch Forecast Report 8 sections (B4)
- Methodology Certificate PDF generator (B4)
- Posterior Update workflow (B5)
- Onboarding tour + templates (B6)
- Pilot client validation PASS (B6)
- Performance budgets met (B6)
- WCAG AA compliance (B6)
- v1.4.0 alpha-tag

### Reference index

Aurora platform memories (cross-product):
- `project_econometrica_roadmap_v3.md` - Phase A platform foundation context
- `project_aurora_analytics_suite_strategy.md` - Suite product positioning + ICPs
- `project_econometrica_target_architecture_v3.md` - shared platform layer
- `project_econometrica_trust3_brand_perf_split.md` - hierarchical priors basis
- `project_econometrica_v1_2_0_foundation_2026_04_28.md` - additive schema pattern
- `project_econometrica_premium_avatars.md` - 3 ICPs (avatars B+C apply)

Style/feedback memories:
- `feedback_no_em_dash.md` - hyphen-only style rule (применяется ко всем созданным docs)
- `feedback_econometrica_patterns.md` - 9 reusable UI patterns
- `feedback_online_only_license.md` - online-only license framework
- `feedback_sidecar_rebuild_required.md` - PyInstaller sidecar gotcha

External tools:
- WeasyPrint (PDF) - https://weasyprint.org/
- NumPyro (JAX Bayesian) - https://num.pyro.ai/
- Pydantic v2 - https://docs.pydantic.dev/2.x/
- Svelte 5 runes - https://svelte.dev/docs/svelte/what-are-runes
- Conformal Prediction adaptation - Tibshirani et al. 2019 NeurIPS
