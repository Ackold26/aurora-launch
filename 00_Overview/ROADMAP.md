# Aurora Launch - Roadmap

**Status:** v1.3 — execution plan to v0.1.0 GA, post-audit (2026-05-08)
**Supersedes:** v1.2 plan (имел 4 BLOCKER + 9 HIGH findings, см. `04_Sprints/AUDIT_ROADMAP_v1.2.md`)
**Next planning revision:** после Block 1 audit gate

## Контекст

Aurora Launch - продукт Phase B Aurora Analytics Suite. Backend Phase B завершён (B0.5/B1/B1.5/B2-backend/B3/B4/B5 shipped + 4 audit waves). Остаётся: foundation hardening (ZIP container, concurrency) → frontend с premium UX → audit → pilot integration с Антоном.

Этот roadmap описывает execution plan к v0.1.0 GA + детальные Phase B sprint specs + Phase C+ ecosystem.

---

## Execution Roadmap to v0.1.0 GA (v1.3 revised — 2026-05-08)

**Цель:** v0.1.0 GA с 1 paying pilot client за **~7-9 недель calendar** (revised от v1.2 6-8 — учтены code signing setup, observability, premium UX, реалистичные оценки solo dev'а).

**Источник изменений:** см. `04_Sprints/AUDIT_ROADMAP_v1.2.md` — 4 BLOCKER + 9 HIGH + 7 MEDIUM + 12 PREMIUM UX + 5 TRUST findings приложены к плану.

### Текущее состояние (snapshot 2026-05-08)

| Слой | Готовность | Комментарий |
|---|---|---|
| Backend / engine | ~95% | shipped, 344 tests passing, 9/9 handlers real |
| C3 Workflow Engine | ~100% | v0.2.0 (StepType 8→13) |
| C7 Methodology Cert verifier | ~50% | code shipped; deployment pending |
| Frontend (B2 UI) | ~5% | scaffolding only |
| `.aurora` ZIP container | ~30% | transitional `.json` works; real ZIP per spec pending |
| Phase A C2 integration | ~20% | stubs вместо real DSM/Mediascope adapters |
| B6 Pilot validation | 0% | требует real customers |
| Документация / ADR / spec | ~90% | Phase B Plan v1.1 + 4 audit waves закрыты |

**HEAD:** `aurora-launch` `46b52d6` / `aurora-platform-core` `6d0866d`. Общая готовность ~60-65%.

### Стратегия revised

**3 автономных блока + 1 параллельный + финал с Антоном**, с premium UX встроенным в core scope (не отложенным в B6).

**Ключевые изменения от v1.2:**
- **Block 0 NEW** — CI/CD + cert procurement стартуют параллельно с Block 1 (снимаем hidden work с финала)
- **WASM убран из desktop** — native Rust IPC verification в Tauri (architectural fix). Web verifier WASM defer в v0.1.1.
- **Phase A C2 adapters** перенесены в Block 4 параллельно с Final F1 (не блокируют frontend)
- **Premium UX** (onboarding, observability, motion, themes, crypto UI, audit log) встроены в Block 2, не отложены в B6
- **Calendar 7-9 weeks realistic** (было оптимистичные 6-8) с буфером на slip

**Принцип очерёдности:** foundation (data layer) → frontend (с premium UX upfront) → audit → integration adapters параллельно с pilot prep.

---

### Block 0 — CI/CD foundation (~3h Маша) ✅ DONE 2026-05-08

**Цель:** CI/CD foundation на main до начала разработки.

**Маша (~3h) — выполнено (HEAD `28e05d3`):**
- `.github/workflows/ci.yml` — lint + test matrix (Ubuntu/Windows/macOS × Python 3.11/3.12) + corpus-check jobs, cancel-in-progress
- `.github/workflows/release.yml` — на tag `v*`: version/tag parity check + full test suite + GitHub Release + CHANGELOG extract. Tauri binary matrix — `TODO(block-2)`.
- `.pre-commit-config.yaml` — ruff format+check, check-yaml/toml/json, no-commit-to-branch main, mypy. Rust hooks — `TODO(block-2)`.
- `.github/dependabot.yml` — weekly pip + github-actions updates.

**Cert procurement — отложено в Final Block (F2):**
Регистрация юрлица ещё не завершена. До F2 поставка идёт без OS code signing:
- **Windows:** NSIS-инсталлятор без Authenticode → SmartScreen «Unknown publisher», пользователь подтверждает в 2 клика. Прикладывается Installation Guide PDF.
- **macOS:** ad-hoc подпись (`codesign --sign -`, без Apple ID) → убирает ошибку «повреждён», остаётся «неизвестный разработчик» → правой кнопкой → Открыть.
- **Tauri update signing:** ed25519 key pair (`tauri signer generate`) — без юрлица, реализуется в Block 2E.
- **После регистрации юрлица (F2 revised):** Authenticode EV + Apple Developer ID + перекладываем подпись через auto-updater. Пилотный клиент получает update одним кликом.

**DoD:** ✅ CI green на main, 344 tests passing.

---

### Block 1 — Foundation Hardening (~20-22h автономно, 2 сессии)

**Цель:** data layer готов к frontend dependency, без архитектурного долга.

#### 1A. Real `.aurora` ZIP container + concurrency + migration tool (~12h)
- Replace `.aurora.json` transitional → real ZIP per spec
- `manifest.json` + parquet (binary efficiency) + pickle (model artifacts) внутри ZIP
- Phase A C6 SchemaRegistry integration
- BFS migration `v.json` → ZIP с backwards-compat reader (Phase B читает оба формата)
- Hash chain через ZIP entries (BLAKE3)
- **Concurrency strategy** (BLOCKER fix B4):
  - Read-only mmap при загрузке + advisory lock (POSIX `flock` / Windows `LockFileEx`)
  - Atomic write: temp file + atomic rename (one-volume guarantee)
  - Optimistic concurrency: bundle-level revision counter в manifest
- **Migration tool**: dry-run mode + automatic backup (.aurora.backup last 3 versions, rotated) — критично для пилота, proxy training стоит 2-3h

**DoD:** 35+ новых тестов pass, все 344 existing tests pass, BundleReader handles обоих форматов, migration tool тестирован на 10+ existing bundles.

#### 1B. License integration с aurora-platform-core JWT (~2h)

Reuse existing flow (НЕ изобретать):
- Import `acquire_seat_atomic` plpgsql function (уже в platform-core migrations/0007)
- ADR-002 jwt-based-offline-grace flow integration
- Tauri command `validate_license` → JWT verify локально + grace period check

**DoD:** Aurora Launch использует platform-core license flow, no duplication.

#### 1C. Memory streaming reader (~3h, HIGH fix H9)

Bundle с real-data может быть 50-200MB. Загружать всё в RAM = fail на 8GB машинах.
- Streaming reader: read manifest first (~few KB)
- Lazy-load parquet pages on-demand
- LRU cache для recently accessed pages (configurable cap, default 512MB)

**DoD:** Bundle 200MB загружается peak <600MB RAM, time-to-first-interactive <500ms.

#### 1D. Audit gate (~3h)
Fresh-eyes pass над 1A+1B+1C. Attack scenarios: zip slip (CVE-2018-1002200 pattern), concurrent write race, malicious manifest. По паттерну прошлых сессий — ожидать 5-10 findings, apply BLOCKER+HIGH сразу.

**Block 1 deliverable:** tag `v0.1.0-alpha1`.

---

### Block 2 — B2 Frontend Ship (~32-35h автономно, 3-4 сессии)

**Цель:** customer-facing UI с premium feel + observability + onboarding встроены, не отложены.

#### 2A. Tauri shell + Svelte 5 + Design System integration (~6h)
- Tauri v2 shell config (Windows/macOS/Linux)
- Svelte 5 + Vite project structure
- **Design System integration** (HIGH fix H1):
  - Import `06_Aurora_Design_system/01_Tokens/tokens.json` → CSS custom properties
  - Адаптация 4 TSX компонентов из `03_Hybrid_Design_System/` в Svelte
  - Storybook (или histoire) для component gallery
- IPC commands: `load_bundle` / `compute_similarity` / `generate_forecast` / `sign_methodology` / `validate_license`
- Window customization + system tray + menu

#### 2B. Wizard + Inspector + Compare + Onboarding (~14h)
- **Wizard flow** (5-7 steps): import → mapping → similarity → forecast → adaptation → cert
- **Inspector tabs** (lazy-load): bundle metadata / similarity matrix / forecast chart / methodology cert
- **Compare flow** для multi-proxy mode
- **Verdict panel** (High / Medium / Low / Insufficient) с explainability tooltip'ами
- **Onboarding** (MEDIUM fix M4, было в B6 — premium upfront):
  - Welcome screen с 3 entry points: Sample / Import existing / New project
  - Pre-loaded sample bundle (anonymized cosmetics или synthetic FMCG) — first-run wow за 60 секунд
  - Guided tour первого forecast'а (interactive overlays, dismissable)
  - Glossary в Help menu (proxy, similarity, posterior, methodology cert)
- **Source citations** (PREMIUM P9): tooltip'ы с academic references

#### 2C. Native Rust verification IPC commands (~3h, BLOCKER fix B1)

**WASM убран из desktop scope.** В Tauri используем native Rust:
- IPC command `verify_bundle_signature(path) → VerificationResult`
- Native `ed25519-dalek` crate, BLAKE3, ZIP reader (no WASM bridge overhead)
- **Verification UI** (PREMIUM P8): «Methodology Cert verified ✓ Aurora AI on 2026-05-15 14:32 MSK using key 0x4F3E…» с expandable chain of trust
- **Tamper detection**: если bundle modified → красный banner, нельзя dismiss

**Web verifier WASM** (для `auroraai.pro/verify`) — отдельный проект, defer в v0.1.1.

#### 2D. i18n + custom radar + theme system + motion (~6h)
- **i18n** (MEDIUM fix M3):
  - ru-RU first-class (проверен носителем), en-US best-effort secondary
  - ICU MessageFormat для plurals (1 неделя / 2 недели / 5 недель)
  - ru-locale numbers (1 234,56 ₽), dates (8 мая 2026 г.)
- **Visualization** (HIGH fix H6):
  - Custom SVG radar component (~2-3h, premium fit-for-purpose) — quality stamp
  - Chart.js tree-shaken (~100KB) для forecast time series
  - ECharts отброшена (1MB слишком большой)
- **Theme system** (PREMIUM P2):
  - Light + dark themes (CSS custom properties с tokens)
  - Auto-switch по системной теме default, manual override
  - Smooth transitions
- **Motion design** (PREMIUM P1):
  - Page transitions: spring-based (`svelte/motion`), 200-300ms
  - Skeleton screens вместо spinner'ов
  - Real progress events из C3 Workflow Engine (НЕ fake setTimeout — `feedback_no_lying_progress_ui.md`)
  - Live MCMC chains visualization для sampling >10s
  - Cancelable forecast (ESC key + UI button → graceful cleanup)
- A11y pass: WCAG AA + ГОСТ Р 52872-2019 (MEDIUM M7)
- Playwright E2E (≥30 tests, не 10 — premium quality coverage M6)

#### 2E. Auto-updater + release infrastructure (~4h, HIGH fix H4)
- `tauri-plugin-updater` config
- Vercel-hosted update manifest endpoint (`updates.auroraai.pro/launch/{version}`)
- Differential updates если bundle large
- Rollback strategy + version semantics (background update + explicit confirm)

#### 2F. Crash reporting + opt-in telemetry + audit log UI (~3h, HIGH fix H5)
- Local SQLite log (extends Customer Success Lite B1.5 schema)
- Crash dump на panic + workflow errors → local-first, opt-in upload через signed Vercel endpoint
- **Settings UI**: «Send anonymous diagnostics» toggle (default OFF, premium = privacy first)
- **Audit log UI** (PREMIUM P6): History panel — все operations visible (timestamp + operation + outcome)
- **Performance metrics visible** (PREMIUM P7): footer показывает «Forecast 23s (target ≤30s ✓)»
- **In-app feedback channel** (PREMIUM P10): `Cmd+Shift+F` → quick form с auto-attached screenshot/log/version → Vercel function → GitHub Issue

**DoD:** Tauri app launches на Win/Mac/Linux, Design System integrated, theme system работает, ≥30 E2E tests pass, onboarding + audit log + feedback channel functional, no fake progress UI.

**Block 2 deliverable:** tag `v0.1.0-alpha2`.

---

### Block 3 — Integration Audit + Bug-Bash (~10h автономно, 1 сессия)

**Цель:** beta-quality, ноль BLOCKER findings open.

#### 3A. Fresh-eyes red-team pass (~5h)
- Critical review всех Block 0+1+2 commits
- Attack scenarios: signing scope, ZIP malicious entries (zip slip), Tauri IPC abuse, frontend XSS, license bypass attempts
- Performance budgets validation (cold start <2s, wizard step <200ms, forecast <30s/<90s)
- Pattern: past audit waves поймали BLOCKERs во всех 4 sessions — ожидать 8-12 findings

#### 3B. Apply audit fixes + final smoke (~5h)
- BLOCKER fixes immediately
- HIGH fixes если ≤2h каждый
- Defer MEDIUM/LOW в `04_Sprints/POST_PILOT_BACKLOG.md`
- Final test run + tag `v0.1.0-beta`

**DoD:** 0 BLOCKER findings open, all HIGH addressed или explicitly deferred, beta tag pushed, CHANGELOG + ADR updated.

---

### Block 4 — Phase A C2 real adapters integration (~12h автономно, parallel с Final F1)

**Цель:** real adapters готовы к пилоту. Параллельно с Антоном на C7 deployment — снимает critical path.

- Replace DSM stub adapter → real Phase A C2 adapter
- Replace Mediascope stub adapter → real C2 adapter
- Phi-3.5 LLM parser Tier 3 hookup
- Custom Client XLSX adapter integration
- AI parser pipeline: heuristic → A/B/C/D detector → Phi-3.5 → Haiku → PII redaction

**DoD:** 9 source kinds supported (vs 2 stub), end-to-end real .xlsx → bundle → forecast, 20+ adapter tests, no regression.

---

### Final Block — Антон involvement (~15-20h actual + 2-3 weeks calendar pilot)

**Цель:** v0.1.0 GA с 1 paying pilot client.

#### F1. C7 deployment infrastructure (~6h Антон + ~3h Маша)
- **Антон:** Yandex.Cloud KMS key creation, Vercel project setup, DNS `cdn.auroraai.pro` (model downloads + signing endpoint)
- **Маша:** Vercel Edge Function deploy (signing service code shipped в Phase A), E2E test verifier ↔ Vercel ↔ KMS

#### F2. Beta installer build + (опционально) OS code signing (~2h Маша + ~1h Антон)

Разделён на две части:

**F2a. Beta installer (без OS code signing) — делается всегда:**
- **Маша:** NSIS installer build (Windows, unsigned) + macOS DMG с ad-hoc подписью (`codesign --sign -`) + Installation Guide PDF (скриншоты обхода SmartScreen / Gatekeeper)
- **Маша:** Tauri update signing уже настроен в Block 2E (ed25519, без юрлица)
- **Антон:** Smoke test installer на Windows + Mac (~1h)

**F2b. OS code signing — откладывается до регистрации юрлица:**
- Apple Developer Program enrollment (5-10 рабочих дней верификация)
- Microsoft Authenticode EV certificate purchase (3-5 дней, EV — не OV, иначе SmartScreen не уберётся)
- После получения: перекладываем подпись, пушим через auto-updater → пилотный клиент получает update одним кликом, без повторной ручной установки
- Блокирует только **GA публичный релиз**, не пилот

#### F3. B6 Pilot kickoff (~2-3 weeks calendar)
- **Антон:** Materia Medica contact, kickoff call, proxy intake (Кагоцел/Венарус ad-hoc per `PROXY_INTAKE_PROTOCOL.md`)
- **Маша:** Customer Success Lite hookup, posterior update первые 2-3 недели telemetry, hot-fix bugs (24-48h SLA через in-app feedback channel)
- **Совместно:** weekly check-in calls, methodology cert generation, pilot success report

#### F4. v0.1.0 GA release (~2-4h)
**Триггер (Pilot Success Metrics, MEDIUM fix M2):**
- ≥1 forecast end-to-end сгенерирован
- ≥1 posterior update с real recipient data
- ≥1 Methodology Certificate подписан + verified
- NPS ≥7 от pilot champion
- Customer **commits** к 1.5M+ contract на v0.1.x
- Zero data loss / corruption инцидентов
- ≤2 critical bugs requiring patch release

**Совместно:** final tag `v0.1.0`, README + DOCS update, public announcement, pricing page activation, RELEASE.md, CHANGELOG finalize, ADR-XXX «v0.1.0 GA».

---

### Total estimate revised

| Block | Owner | Effort | Calendar |
|---|---|---|---|
| Block 0 (CI/CD + cert order) | Маша + Антон фон | ~3h Маша + Антон async | day 1 |
| Block 1 (foundation hardening) | Маша | ~20-22h | week 1-2 |
| Block 2 (frontend + premium UX) | Маша | ~32-35h | week 2-4 |
| Block 3 (audit + bug-bash) | Маша | ~10h | week 4 |
| Block 4 (C2 adapters parallel) | Маша | ~12h | week 5 (parallel с F1-F2) |
| Final (F1-F4) | Антон + Маша | ~15-20h actual | week 5-8 |
| **Total to v0.1.0 GA** | — | **~92-102h dev + 2-3 wk pilot** | **~7-9 weeks realistic** |

---

### Risk register revised

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `.aurora` ZIP migration breaks existing tests | Medium | High | Backwards-compat reader Phase B; explicit audit gate в 1D + dry-run migration |
| Concurrent ZIP write race conditions | Low | High | Advisory lock + atomic rename + revision counter (Block 1A) |
| Bundle 200MB+ exhausts RAM | Medium | Medium | Streaming reader + LRU cache (Block 1C) |
| Apple Developer enrollment delayed (5-10 days) | High | Medium | Block 0 parallel start, не на critical path |
| Microsoft Authenticode EV cert delayed (3-5 days) | Medium | Low | Block 0 parallel start |
| C7 KMS setup blocks Антон >1 week | Medium | Medium | Mock signing для beta tag; defer real KMS на post-beta |
| Materia Medica pilot delayed | Medium | High | Backup ICP candidates: Adwatch / Media Direction / Proximity |
| Audit Block 3 finds late BLOCKER | High | Medium | 5h time buffer, can extend |
| Pilot finds critical regression | Medium | High | In-app feedback channel + 24-48h hot-fix SLA + auto-updater |
| WASM web verifier scope creep в v0.1.0 | Low | Low | Defer полностью в v0.1.1 backlog |
| ECharts/Chart.js bundle bloat | Low | Medium | Custom SVG для radar + Chart.js tree-shaken (Block 2D) |

---

### Success criteria для v0.1.0 GA

- [ ] 1 paying pilot customer с successful forecast cycle (Materia Medica или backup)
- [ ] ≥400 tests passing (344 existing + ~60 новых из Block 1+2+3+4)
- [ ] ≥30 Playwright E2E tests
- [ ] Zero BLOCKER findings open
- [ ] Performance budgets met: cold start <2s, wizard step <200ms, forecast <30s/<90s
- [ ] Code-signed installer Windows + macOS (notarized)
- [ ] C7 Methodology Cert signing live (Vercel + KMS)
- [ ] Auto-updater functional
- [ ] Crash reporting + telemetry opt-in working
- [ ] Light/dark theme support
- [ ] ru-RU i18n full + en-US scaffolding
- [ ] WCAG AA + ГОСТ Р 52872-2019 partial compliance
- [ ] In-app feedback channel + audit log UI functional
- [ ] CHANGELOG + ADRs current
- [ ] README + Methodology paper publicly accessible (`auroraai.pro/methodology`)
- [ ] Pricing page активна (Tauri licence flow с platform-core JWT)
- [ ] NPS ≥7 от pilot champion
- [ ] Customer commits к 1.5M+ contract

---

### Premium UX commitments (v0.1.0 baseline)

Чтобы пользователь работал с уверенностью в premium-продукте:

**Visual & motion:**
- Design System tokens.json как SSOT (light/dark themes)
- Custom SVG radar (premium fit-for-purpose)
- Spring-based page transitions, skeleton loading screens
- Generous whitespace, scientific publication aesthetic для PDF Cert

**Trust & transparency:**
- Cryptographic signature visible с full chain of trust
- Audit log UI (все operations history)
- Performance metrics visible в footer
- Source citations с academic references в tooltip'ах
- App/model/methodology versioning visible везде
- Tamper detection visible (red banner, не dismissable)

**Productivity & frictionless:**
- 60-second first-run wow (sample bundle pre-loaded)
- Real progress events (C3 Workflow Engine), не fake
- Live MCMC chains visualization для long-running operations
- Cancelable operations (ESC key + UI)
- In-app feedback channel (`Cmd+Shift+F` → screenshot + logs auto-attach)
- Auto-backup .aurora bundles (3 versions rotated)

**Privacy & security:**
- Local-first (no telemetry by default, opt-in only)
- Backup/restore tool с dry-run
- License flow через platform-core JWT (offline grace)
- Memory streaming reader (200MB+ bundles)

---

### Когда начинать какой блок

**Now (immediately):** Block 0 (CI/CD setup ~3h + Антон стартует cert enrollment async). Без CI Block 1+2 идут «вслепую».

**После Block 0:** Block 1 (foundation hardening). 

**После Block 1:** Block 2 (frontend с premium UX upfront).

**После Block 2:** Block 3 audit (last quality gate перед pilot).

**Параллельно с Block 3 → Final F1:** Block 4 (C2 adapters) — Маша автономно пока Антон на cert validation + KMS.

**После Block 3 + Block 4 + F1+F2 ready:** F3 pilot kickoff.

---

### Альтернативы / fast-path сценарии

**Fast-path A (если pilot задерживается >2 weeks):** ship `v0.1.0-rc1` без real Code Signing для internal testing (unsigned warning), signing постепенно в первые 1-2 недели pilot. Trade-off: Mac пользователи увидят Gatekeeper warning, ослабляет premium-фил.

**Fast-path B (если certs задерживаются >3 weeks):** swap Block 4 ↔ Final F2 — adapters раньше, signing позже. Pilot стартует на signed dev build.

**Slow-path (если premium UX недостаточен на пилоте):** insert Block 2.5 «UX-доработка по pilot feedback» — 1 week, после первых 2 недель пилота. Buffer уже учтён в 7-9 weeks calendar.

**Default:** Block 0 → 1 → 2 → 3 → (4 ‖ F1+F2) → F3 → F4. Tested через 4 audit waves backend + applied audit findings v1.2 → структурно устойчиво.

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

**Goal:** ensure backwards compatibility + multi-version data ingestion before schema changes. **Corpus = ad-hoc proxy intake validation harness, не предзаготовленная donor library** (per restored D002 2026-05-06; см. `03_Architecture/PROXY_INTAKE_PROTOCOL.md`).

**Deliverables:**
- Ad-hoc proxy intake validation corpus: 8+ synthetic .aurora projects (категории FMCG / OTC / cosmetics / telecom / awareness — coverage диверсификация для testing pipeline, **НЕ предзаготовленная library учителей**) + опционально 1-2 anonymized real cases когда первый клиент придёт
- Parametrized pytest на каждый corpus item — verifies workflow приёма proxy ad-hoc от 7-step protocol works
- Format adapters: `DsmFormatAdapterV2023`, `V2024`, `V2025` + auto-detection logic (применяются к **любому** proxy от клиента, не только pre-built)
- Plug-in architecture skeleton: abstract `ProxyDataSource` interface (per-deal proxy ingestion при customer engagement)
- CI gate: schema changes без BC test pass = blocked

**Why:** обнаружено в audit (A2, A3) - формат меняется год от года, BC tests insufficient в исходном плане. **Per D002 restored 2026-05-06** — corpus тестирует workflow приёма proxy ad-hoc, не валидирует предзаготовленную library.

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
  - Single-proxy mode (default): один прокси-бренд + 6 similarity dimensions
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
- **Эконометрика → Launch migration flow** (primary demo path - см. ADR launch-demo-strategy-real-client-data-first): импорт `.aurora` от Эконометрика-клиента в Launch как proxy candidate, демо на real-данных клиента (с его согласия) или анонимизированной копии
- Property-based tests (monotonic CI growth с horizon, consistent transfers)

**Note:** обязательный синтетический demo-кейс УБРАН из B5 scope. Synthetic кейс - secondary, делается lightweight (2-3 дня) только когда нужен для конкретной активности (cold outreach, конференция, контент). Primary demo = real client data Эконометрика.

### Sprint B6: Pilot Live-Test + Polish (1 неделя)

**Goal:** один pilot client отвалидировал end-to-end flow.

**Prerequisites (DONE 2026-05-04):**
- ✅ S008 Pilot Client Identification - `04_Sprints/PILOT_CLIENT_PLAN.md` (3 candidates × 3 categories + qualification + 12-week engagement plan)
- ✅ S010 Sales Playbook - `06_References/SALES_PLAYBOOK.md` (outreach + discovery + demo + conversion + onboarding + ops)

**Deliverables:**
- Pilot session с 3 parallel клиентами (Pharma OTC + FMCG + Cosmetics, Tier 1 prioritized = existing Эконометрика clients). **Каждый pilot — first pilot case для своей категории, не permanent stage.** Customer называет свой proxy ad-hoc per `03_Architecture/PROXY_INTAKE_PROTOCOL.md`, не выбирает из предзаготовленной library.
- **Эконометрика → Launch project migration integration** (UI-кнопка в Эконометрике "Использовать как proxy в Aurora Launch", lossless transfer recipient_brand_metadata + recent posterior как proxy_priors). **Customer-nominated proxy** (existing Эконометрика project клиента), не library-based.
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
| **D002 RESTORE** | **Антон restored D002 «отказ от donor library» — `04_Sprints/DONOR_LIBRARY_SHORTLIST.md` удалён, заменён `03_Architecture/PROXY_INTAKE_PROTOCOL.md`. Aurora Launch — продукт прогноза для любых отраслей с ad-hoc proxy intake от клиента.** | 2026-05-06 | ✅ DONE (commit `152a0ad`) | B0.5 + B6 sprint descriptions clarified |
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
