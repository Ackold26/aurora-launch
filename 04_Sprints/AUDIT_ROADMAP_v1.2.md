# Audit: ROADMAP v1.2 → v1.3 revisions

**Audit date:** 2026-05-08
**Auditor:** Маша Маленькая (Claude Opus 4.7), fresh-eyes red-team pass
**Subject:** `00_Overview/ROADMAP.md` v1.2 «Execution Roadmap to v0.1.0 GA»
**Status:** Findings applied → ROADMAP v1.3 (4 BLOCKER + 9 HIGH + 7 MEDIUM + 12 PREMIUM UX + 5 TRUST)
**Pattern:** аналогично 4 audit waves backend (S1-S2 Wave 1-4), но scope = planning document, не код

---

## Executive Summary

ROADMAP v1.2 описал три автономных блока (Foundation Hardening / B2 Frontend / Audit) + финальный с Антоном. План был структурно работоспособен, но содержал **4 архитектурные ошибки**, **9 HIGH технических недостатков** и не учитывал **premium UX components** как core scope (откладывал в B6).

После применения findings план revised в v1.3:
- **Block 0 NEW** — CI/CD foundation + cert procurement параллельный старт
- **WASM убран из desktop** — native Rust IPC (architectural fix B1)
- **Phase A C2 adapters** перенесены в Block 4 параллельно с Final F1 (B2)
- **Premium UX встроен в Block 2** (12 PREMIUM components — onboarding, observability, motion, themes, crypto UI, audit log)
- **Calendar** 6-8 weeks → 7-9 weeks realistic с буфером

Pages: ~10. Findings: 37. Apply rate: 100% (все findings applied в v1.3).

---

## Findings — BLOCKER (4)

### B1. WASM в Tauri-приложении — архитектурная путаница

**Проблема:** план Block 2C описал «Rust WASM crate ≤200KB gzipped … Bundle reader (verify signature client-side)» для Tauri desktop app. Это смешение двух разных компонентов:

| Component | Where | Tech | Bundle constraint |
|---|---|---|---|
| Aurora Launch desktop | Tauri (Win/Mac/Linux) | Native Rust IPC + ed25519-dalek | None — native binary |
| Aurora Web Verifier | Browser at `auroraai.pro/verify` | Rust → WASM | Yes, ≤200KB sensible |

В Tauri desktop у нас полноценный Rust в `src-tauri/` — native verification через IPC проще, быстрее, без bundle size ограничений.

**Impact:** ~8h на ненужную WASM crate работу + bundle размер 200KB hard target невозможен с realistic crypto deps.

**Fix:** Block 2C → переименован «Native Rust verification IPC commands (~3h)». WASM web verifier defer в v0.1.1 backlog.

**Saved effort:** ~5h directly + лучшая архитектура.

---

### B2. Block 1B (Phase A C2 adapters) на critical path не нужен

**Проблема:** план положил real DSM/Mediascope adapters в Block 1 как блокер frontend'а. Но frontend зависит от **bundle interface** (`.aurora` структура), не от того, как bundle создан. Stub'ы генерируют валидные bundle'ы — frontend читает их одинаково.

**Impact:** ~12h на critical path калибровки frontend'а, реально может идти параллельно с pilot prep.

**Fix:** Phase A C2 adapters → новый Block 4, parallel с Final F1 (Антон на C7 deployment, Маша на adapters). Calendar critical path сокращён на ~12h.

**Saved calendar:** ~2-3 days.

---

### B3. Apple Developer ID enrollment не учтён в calendar

**Проблема:** F2 (~6h Антон) предполагает что Apple Developer cert уже есть. Реалистично:
- Apple Developer Program enrollment для юр.лица (РФ): 5-10 рабочих дней верификация документами компании (D-U-N-S, юр.лицо)
- Microsoft Authenticode EV cert: 3-5 дней валидация
- Без этих cert'ов macOS notarization невозможен → app не запустится без Gatekeeper warning

**Impact:** если cert ordering происходит в финальной фазе → +2 недели calendar только на бюрократию.

**Fix:** Block 0 NEW — cert procurement стартует параллельно с Block 1 (5-10 days lead time снят с финала).

**Saved calendar:** до 2 weeks slip risk avoided.

---

### B4. ZIP миграция без concurrent-access strategy

**Проблема:** Block 1A не специфицировал:
- Что если bundle открыт в app, а пользователь редактирует через другой процесс?
- ZIP не thread-safe для concurrent reader/writer
- Atomic write миссинг → crash в момент сохранения = corrupted bundle

**Impact:** premium product = no data loss. Bundle = валюта продукта (proxy training 2-3h). Loss = катастрофа для пилота.

**Fix:** Block 1A явно включает:
- Read-only mmap + advisory lock (POSIX `flock` / Windows `LockFileEx`)
- Atomic write через temp file + atomic rename (POSIX-атомарен в одном volume)
- Optimistic concurrency: bundle-level revision counter в manifest
- Migration tool с **dry-run + automatic backup** (last 3 versions rotated)

**Effort added:** ~2h в Block 1A (12h → стало уже учтённое).

---

## Findings — HIGH (9)

### H1. Нет design system integration в Block 2

**Проблема:** `06_Aurora_Design_system/` существует с tokens.json (SSOT) + 4 TSX компонентов. План Block 2 строил с нуля без ссылки на design system → premium-фил невозможен без visual consistency.

**Fix:** Block 2A явно включает «Design System integration»:
- Import `tokens.json` → CSS custom properties
- Адаптация 4 TSX компонентов из `03_Hybrid_Design_System/` в Svelte
- Storybook (или histoire) для component gallery

**Effort:** ~3-4h добавляет, снимает рискы дизайна на этапе аудита.

---

### H2. WASM ≤200KB hard target без profiling

**Проблема:** реалистичная оценка WASM crate:
- ed25519-dalek (no_std) — 80-120 KB
- BLAKE3 — 30-50 KB
- ZIP reader — 100-150 KB
- serde_json — 80-100 KB
- Минимум 200KB на голый minimum, реалистично 350-500 KB

Hard target ≤200KB без baseline = гарантированный re-work.

**Fix:** WASM убран из v0.1.0 (B1 architectural fix). Web verifier в v0.1.1 backlog — сначала profile baseline, потом budget.

---

### H3. Calendar 6-8 weeks оптимистичен для solo dev

**Проблема:** реалистичный расчёт:
- 80-90h dev / 5-6h продуктивных в день = 14-18 рабочих дней = 3-4 недели чистого dev'а
- Audit gates → +1-2 дня на каждый из 3 = +6 дней
- Code signing setup даже с готовыми cert'ами — 3-5 дней (notarization, NSIS, CI matrix)
- Pilot calendar 2-3 недели + buffer на feedback loop
- Contingency для непредвиденного — 1-2 недели

Реалистично: 8-10 недель.

**Fix:** v1.3 calendar revised → **7-9 weeks realistic** с явным буфером. Best-case 6 weeks, worst 10.

---

### H4. Update mechanism / auto-updater отсутствует в плане

**Проблема:** после v0.1.0 → пилот ловит баг → как доставить fix?

Tauri v2 имеет встроенный updater (`tauri-plugin-updater`) но требует:
- Подписанный update manifest
- Endpoint для distribution
- Version semantics (background vs explicit confirm)
- Rollback strategy

**Fix:** новый sub-block **2E. Auto-updater + release infrastructure (~4h)**:
- Tauri updater plugin config
- Vercel-hosted manifest endpoint (`updates.auroraai.pro/launch/{version}`)
- Differential updates если bundle large

---

### H5. Нет crash reporting / observability в production

**Проблема:** пилот → ошибка → без telemetry мы узнаем когда клиент позвонит. Не premium.

**Fix:** новый sub-block **2F. Crash reporting + opt-in telemetry + audit log UI (~3h)**:
- Local SQLite log (extends Customer Success Lite B1.5 schema)
- Crash dump на panic + workflow errors → opt-in upload через signed Vercel endpoint
- Settings UI: «Send anonymous diagnostics» toggle (default OFF, premium = privacy first)
- Audit log UI в History panel (все operations visible)
- Performance metrics visible в footer
- In-app feedback channel (`Cmd+Shift+F` → screenshot + logs → GitHub Issue)

---

### H6. ECharts ~1MB minified — bundle обжорство

**Проблема:** ECharts полная — ~1MB minified, ~250KB gzipped. Используем 5% возможностей (radar + 1-2 chart types).

**Альтернативы:**
| Решение | Bundle | Pros | Cons |
|---|---|---|---|
| ECharts полная | ~1MB | Готовое всё | Bloat |
| Chart.js tree-shaken | ~100KB | Лёгкий, достаточный | Меньше types |
| Custom SVG | ~10-20KB | Premium control, perfect fit | Time investment |

**Fix:** Block 2D revised:
- Custom SVG component для radar (~2-3h, premium fit-for-purpose) — это quality stamp, ключевая визуализация
- Chart.js tree-shaken для forecast time series

---

### H7. License flow не designed (только mentioned)

**Проблема:** F4 говорит «licence flow activation (Tauri offline grace JWT)» без архитектуры. Память напоминает: aurora-platform-core уже имеет ADR-002 jwt-based-offline-grace + acquire_seat_atomic plpgsql function.

Должны переиспользовать, не изобретать.

**Fix:** новый sub-block **1B. License integration с aurora-platform-core JWT (~2h)** — wire existing flow, no duplication.

---

### H8. CI/CD должен стартовать в Block 1, не в F2

**Проблема:** план откладывал CI/CD на финал. Каждый commit Block 1+2 должен прогоняться через type check / tests / lint / build matrix. GitHub Actions free tier позволяет.

**Fix:** Block 0 NEW в самом начале:
- `.github/workflows/test.yml` — на каждый push/PR
- `.github/workflows/release.yml` — на tag push
- Branch protection main + pre-commit hooks локально

---

### H9. Memory streaming для больших bundle'ов

**Проблема:** real-data bundles 50-200MB не редкость (parquet history × N years). Загружать всё в RAM — fail на 8GB машинах.

**Fix:** новый sub-block **1C. Memory streaming reader (~3h)**:
- Streaming reader: read manifest first
- Lazy-load parquet pages on-demand
- LRU cache (configurable, default 512MB cap)

**DoD:** Bundle 200MB загружается peak <600MB RAM, time-to-first-interactive <500ms.

---

## Findings — MEDIUM (7)

### M1. Performance budgets не определены конкретно

**Проблема:** «Tauri app launches» — это не budget. Premium = imperceptible latency.

**Fix:** конкретные budgets в Block 3 как acceptance criteria:

| Операция | Target | Hard limit |
|---|---|---|
| Cold start | <2s | <3s |
| Wizard step transition | <200ms | <400ms |
| Similarity radar render | <100ms | <200ms |
| Bundle load (50MB typical) | <500ms | <1s |
| Forecast 12 weeks single proxy | <30s | <60s |
| Forecast 52 weeks multi-proxy N=3 | <90s | <180s |
| PDF Methodology Cert generation | <3s | <8s |
| Auto-save | <100ms (background) | invisible |

Эти budgets уже в `03_Architecture/PERFORMANCE_BUDGETS.md` — интегрированы в Block 3 audit.

---

### M2. Pilot success metrics не определены

**Проблема:** «Successful forecast cycle» — расплывчато.

**Fix:** конкретные F4 trigger metrics:
- ≥1 forecast end-to-end сгенерирован
- ≥1 posterior update с real recipient data
- ≥1 Methodology Certificate подписан + verified
- NPS ≥7 от pilot champion
- Customer commits к 1.5M+ contract на v0.1.x (не просто «нравится»)
- Zero data loss / corruption инцидентов
- ≤2 critical bugs requiring patch release

---

### M3. i18n half-implemented

**Проблема:** «ru / en» — равноценно? Для российского рынка ru-RU должен быть first-class, en-US — best-effort secondary.

**Fix:** Block 2D specifies:
- ru-RU first-class (проверен носителем языка)
- ICU MessageFormat для plurals
- ru-locale numbers (1 234,56 ₽), dates (8 мая 2026 г.)
- en-US scaffolding only для v0.1.0, full в v0.1.x

---

### M4. Onboarding в B6, не Block 2

**Проблема:** план отложил onboarding в B6 (последний sprint). Но Block 2 frontend без onboarding = empty state confusion на пилоте.

**Fix:** onboarding встроен в Block 2B:
- Welcome screen с 3 entry points
- Pre-loaded sample bundle (anonymized) — first-run wow за 60 секунд
- Guided tour первого forecast'а
- Glossary в Help menu

---

### M5. Backup/restore strategy для customer .aurora files

**Проблема:** `.aurora` bundle = валюта продукта. Premium = data protection.

**Fix:** Block 1A добавляет:
- Auto-backup на каждое save: `bundle.aurora` + `bundle.aurora.backup` (last 3 versions rotated)
- Manual export "Save as..." для версионирования у клиента
- Optional cloud backup integration (Yandex.Disk / Dropbox / iCloud) — opt-in, encrypted client-side, defer на v0.1.1

---

### M6. Test pyramid distribution не специфицирована

**Проблема:** 344 tests — отлично, но какое распределение?

**Fix:** Premium = comprehensive coverage target:
- Unit (pytest engines + Rust unit) — 70% (~280)
- Integration (pytest workflow) — 20% (~80)
- E2E (Playwright) — 10% (~30+) — план говорит ≥10, mало для пилотного качества

Block 2D revised: ≥30 E2E tests (не ≥10).

---

### M7. Российские compliance требования

**Проблема:** план говорит только WCAG AA. Российский премиум-продукт требует:
- ГОСТ Р 52872-2019 (web accessibility)
- ФЗ-152 «О персональных данных» (даже если local-first, должна быть policy)
- Реестр российского ПО (опционально, но trust signal для гос-сегмента)

**Fix:** Block 2D a11y pass расширен на ГОСТ Р 52872-2019. ФЗ-152 policy в `06_References/PRIVACY_POLICY.md` (defer на пилот). Реестр — Phase C+ goal.

---

## Findings — PREMIUM UX (12)

### P1. Motion design + micro-interactions

**Что:** premium-фил ICP analyst-perfectionists требует subtle motion.

**Implementation в Block 2D:**
- Page transitions: spring-based (`svelte/motion`), 200-300ms easeOutCubic
- Skeleton screens вместо spinner'ов
- Success moments: subtle haptic-feel (animation + checkmark + soft chime опционально)
- Hover states: все interactive elements чётко affordant

---

### P2. Dark mode + theme system

**Что:** 2026 baseline, premium = supports both modes.

**Implementation в Block 2D:**
- Auto-switch по системной теме default
- Manual toggle в settings
- Smooth transitions between themes (CSS variables)
- tokens.json уже supports themes

---

### P3. First-run wow moment

**Что:** 30-60 секунд от open до «вау, это работает».

**Implementation в Block 2B:**
1. Welcome screen с 3 entry points (Sample / Import / New)
2. «Try sample forecast» → pre-loaded bundle
3. 3 клика → forecast generated → Methodology Cert preview
4. CTA: «Now try with your data»

---

### P4. Methodology Certificate как премиум-артефакт

**Что:** trust artifact клиента, показывает руководству, аудиторам.

**Implementation:**
- Custom typography (Equity для serif body + Inter Display для headings)
- Watermark с Aurora seal
- QR-код в footer → ссылка на verification page
- Cryptographic signature визуально (hex monospace, partial reveal с tooltip полного hash)
- Generous whitespace, scientific publication aesthetic
- Не «PDF report» — printable artifact

Reference: financial audit report или scientific publication aesthetic.

---

### P5. Real progress visualization (не fake)

**Что:** `feedback_no_lying_progress_ui.md` — никаких setTimeout fake stages.

**Implementation в Block 2D:**
- C3 Workflow Engine emits real events → frontend listens
- Stage cards: «1. Adapting proxy priors (12s)» → «2. Sampling posterior (45s)» → «3. Validating CI (3s)»
- Live MCMC chains visualization (если sampling >10s — мини-график конвергенции)
- ETA calculation на base benchmark + текущий прогресс
- Cancelable: ESC key + UI button → cleanup graceful

---

### P6. Audit log UI visible

**Что:** все операции логируются + видны пользователю.

**Implementation в Block 2F:**
- History panel: timestamp + operation + actor (user/system) + outcome
- Filterable по дате, типу
- Premium = transparent + compliance value

---

### P7. Performance metrics visible

**Что:** premium users (analysts) хотят видеть.

**Implementation в Block 2F:**
- Footer: «Forecast computed in 23s (target ≤30s ✓)»
- App version + model version + methodology version always visible
- About panel: build hash, signing key fingerprint, license validity

---

### P8. Cryptographic transparency UI

**Что:** verification visible, не hidden.

**Implementation в Block 2C:**
- «Methodology Cert verified ✓ Aurora AI on 2026-05-15 14:32 MSK using key 0x4F3E…»
- Click → expandable detail с полной chain of trust
- Tamper detection: bundle modified → красный banner, нельзя dismiss

---

### P9. Source citations в UI

**Что:** каждое methodology decision окружено tooltip'ами.

**Implementation в Block 2B:**
- «Hierarchical Bayesian priors (Konstantinopoulos et al., 2014)» с link на paper
- «BMA fallback (Hoeting et al., 1999)»
- «ESS-based weight schedule» — formula visible on click

---

### P10. In-app feedback channel

**Что:** pilot-критично — frictionless feedback.

**Implementation в Block 2F:**
- `Cmd+Shift+F` → quick form
- Auto-attach: screenshot, app version, recent log lines, system info
- Submit → Vercel function → GitHub Issue
- User видит: «Спасибо! Issue #142 создан»
- Critical для improvement velocity на пилоте

---

### P11. Sound design (опционально)

**Что:** премиум-сигнал.

**Implementation в Block 2D (опционально):**
- Soft chime на «Forecast complete» (opt-out в settings)
- Volume в settings, mute everything default option
- Не keyboard click (анти-паттерн)

---

### P12. Дидактичность над замысловатостью

**Что:** Premium ≠ ажурно. Premium = уверенность через простоту.

**Principles в Block 2A Design System:**
- Lots of whitespace
- Clear typography hierarchy (max 3-4 sizes used)
- Limited color palette (semantic colors only)
- Иконки минимально, только функциональные
- Reference: Linear / Notion / Figma — не Adobe-style toolbar overload

---

## Findings — TRUST & CONFIDENCE (5)

### T1. Versioning visible во всех артефактах

**Implementation:**
- App: footer + About panel
- Generated bundle: manifest.json metadata
- PDF cert: footer
- Premium = transparent versioning

---

### T2. Methodology paper publicly accessible

**Implementation:**
- `auroraai.pro/methodology` — PDF + HTML с полной матем. документацией
- Academic citations machine-readable (BibTeX)
- Reproducibility: open synthetic test data
- Trust signal: «вот наша наука, проверяй»

В success criteria v0.1.0 GA.

---

### T3. Show signing chain prominently

**Implementation в Block 2C:**
- After verification: «Signed by Aurora AI (Materia Medica licensed)» + key fingerprint
- Tamper alert если signature mismatch — красный banner, нельзя dismiss
- Premium = trust visible

---

### T4. Open source где возможно

**Implementation:**
- WASM web verifier (v0.1.1) — open source MIT — клиент может verify без приложения
- Methodology engine spec — open
- Premium B2B = transparency builds trust over secrecy

---

### T5. Compliance certifications planning

**Implementation как Phase C+ goal:**
- ИСО 27001 (information security) — long-term
- SOC 2 Type II — для enterprise tier
- Signal на сайте «Working towards SOC 2» как trust marker

---

## Summary table — Block changes v1.2 → v1.3

| Block | v1.2 | v1.3 | Reason |
|---|---|---|---|
| Block 0 | — | NEW (~3h Маша + Антон фон) | H8 CI/CD + B3 cert procurement |
| Block 1 | 1A ZIP / 1B C2 adapters / 1C audit (~25-30h) | 1A ZIP+concurrency / 1B license / 1C streaming / 1D audit (~20-22h) | B2 (1B перенесён) + B4 (concurrency) + H7 (license) + H9 (streaming) |
| Block 2 | 2A scaffold / 2B Wizard / 2C WASM / 2D polish (~30h) | 2A scaffold+DS / 2B Wizard+onboard / 2C native verify / 2D i18n+motion+SVG / 2E updater / 2F crash+telemetry+audit log (~32-35h) | B1 (WASM убран) + H1 (DS) + H4 (updater) + H5 (telemetry) + H6 (custom SVG) + M3-M4 (onboard, i18n) + 12 PREMIUM UX |
| Block 3 | Audit (~10h) | Audit + perf budgets (~10h) | M1 perf budgets enforcement |
| Block 4 | — | NEW Phase A C2 adapters parallel (~12h) | B2 critical path freed |
| Final | F1 deploy / F2 signing / F3 pilot / F4 GA (~15-20h) | Same + cert procurement уже в Block 0 | Calendar smoothed |

---

## Calendar impact

| Metric | v1.2 | v1.3 | Delta |
|---|---|---|---|
| Total dev effort | ~80-90h | ~92-102h | +12h (premium UX) |
| Critical path effort | ~80-90h | ~80-90h | 0 (Block 4 parallel) |
| Calendar realistic | 6-8 weeks | 7-9 weeks | +1 week (буфер на slip) |
| Hidden work risk | Высокий (cert / observability / updater) | Низкий | All revealed upfront |
| Premium UX coverage | Откладывалось в B6 | Встроено в Block 2 | Premium baseline в v0.1.0 GA |

**Net effect:** план чуть длиннее по effort (+12h), но **drastically более устойчив к slip'у** + premium-quality на запуске.

---

## Lessons learned (для следующих planning сессий)

1. **План — это документ, который тоже надо аудитить fresh-eyes pass'ом.** Pattern «4 audit waves backend» applies to planning too.
2. **Architectural decisions (WASM vs native) — verify physics до написания плана.** Block 2C WASM был copy-paste из спеки без проверки контекста (desktop vs web).
3. **Critical path discipline:** что реально блокирует следующий шаг, а что можно parallel'ить.
4. **Cert/infra lead times — externals на critical path надо стартовать day 1.**
5. **Premium UX = core scope, не B6 polish.** ICP (analyst-perfectionists) ожидает quality везде.
6. **Realistic estimates лучше optimistic.** 7-9 weeks с буфером > 6-8 weeks с slip riskами.

---

## Apply status

✅ All 37 findings (4 BLOCKER + 9 HIGH + 7 MEDIUM + 12 PREMIUM UX + 5 TRUST) применены в `00_Overview/ROADMAP.md` v1.3.

**Next action:** старт Block 0 (CI/CD setup) immediately, Антон параллельно стартует cert procurement.

---

**Audit подготовлен:** Маша Маленькая (Claude Opus 4.7), 2026-05-08
