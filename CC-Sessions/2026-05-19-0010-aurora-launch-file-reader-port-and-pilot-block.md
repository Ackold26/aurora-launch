---
tags: [session, compressed]
type: session
updated: 2026-05-19
---

# Quick Reference

Port file reader из Aurora Econometrica MMM Optimizer в Aurora Econometrica Launch Planner (Backlog #7). Replace canonical-fields wizard на role-based detection. **Port closed and pushed** — 3 commits Aurora Launch + 1 commit aurora-meta (INV-41). **Pilot НЕ доведён до конца** — упёрлись в каскад инфра-блокеров Tauri dev на новой машине, при поднятии окна возник sidecar spawn fail + UX/brand gap дискуссия.

**Topic:** Aurora Launch file reader port + pilot block
**Key files:**
- `D:/Docs/Aurora_Ai/Aurora Launch/docs/FILE_READER_PORT_DESIGN.md` (656 LOC контракт)
- `D:/Docs/Aurora_Ai/Aurora Launch/src/aurora_launch/engines/validator.py` (549 LOC port)
- `D:/Docs/Aurora_Ai/Aurora Launch/src/aurora_launch/utils/column_detection.py` (831 LOC port)
- `D:/Docs/Aurora_Ai/Aurora Launch/src/aurora_launch/sidecar/methods_validation.py` (новый, 130 LOC)
- `D:/Docs/Aurora_Ai/Aurora Launch/src/aurora_launch/schemas/wizard_session.py` (Pydantic migration)
- `D:/Docs/Aurora_Ai/Aurora Launch/src-tauri/src/commands/adapters.rs` (Rust commands)
- `D:/Docs/Aurora_Ai/Aurora Launch/frontend/src/lib/components/DataPreviewTable.svelte` (новый, 305 LOC)
- `D:/Docs/Aurora_Ai/Aurora Launch/frontend/src/routes/wizard/+page.svelte` (STEPS 7→6 + integration)
- `D:/Docs/Aurora_Ai/aurora-meta/ENGINEERING_INVARIANTS.md` (INV-41)

**Status:**
- ✅ Port: pushed `7eb9cc9` на `feat/stage1-core-1.1-1.4`
- ✅ aurora-meta: pushed `1229656` INV-41 на `main`
- ✅ All tests green: pytest 1545/1545, vitest 537/537, cargo check 0, svelte-check 0
- 🟡 Pilot: окно открылось, file picker → `analyze_data_file` упал на `state not managed for field sidecar` (sidecar spawn fail)
- 🟡 UX gap exposed: «весь UI не в стиле Aurora» (welcome screen, не моего port'а)
- 🟡 Working tree dirty: `package.json` (новый, root proxy) + `tauri.conf.json` (visible: true) — НЕ закоммичено
- ⏳ Pending: pilot diagnosis + UX direction + Backlog #8/#9

---

## Learnings

### L1 — Audit pass mandatory after Sonnet delegation
Sonnet'ы прошли все тесты зелёным (pytest 1543/1543, vitest 537/537, svelte-check 0). Я отчиталась «готов к коммиту». Антон попросил детальный аудит → нашла **6 проблем** включая **CRITICAL**: `validate_wide_table` принимал любой role string в `role_overrides` без whitelist guard. Frontend TS Literal type — НЕ страховка для backend handler.

Зелёные тесты ≠ audited код. Semantic gaps (gate coverage, dead state, recovery flow, recompute drift) тесты не ловят.

**Saved as:** `feedback_audit_after_sonnet_delegation.md` + cross-product invariant **INV-41** в aurora-meta.

### L2 — Tauri dev first-run на новой машине = predictable chain блокеров
5 шагов каскадных проблем при попытке pilot:
1. Tauri CLI не локально → `npm install -D @tauri-apps/cli@^2 --legacy-peer-deps` (peer-deps конфликт histoire+Svelte5)
2. CLI из `frontend/` не находит `../src-tauri/tauri.conf.json` (ищет вниз) → запускать из root
3. CLI из root выбирает `aurora-cloud/` как cwd для beforeDevCommand (alphabetically первый subdir с package.json) → нужен root proxy `package.json`
4. Окно `visible: false` без вызова `.show()` нигде в коде → app spawned silent
5. SidecarManager spawn упал silent (env_logger без `RUST_LOG=info` показывает только errors) → команды падают `state not managed`

**Saved as:** `feedback_tauri_dev_first_run_chain.md` — pre-dev checklist для всех Aurora Tauri продуктов.

### L3 — Дизайн-док как контракт между Opus и parallel Sonnet'ами
656 LOC `FILE_READER_PORT_DESIGN.md` дал Sonnet'ам точные сигнатуры handler'ов, Pydantic shapes, файловый inventory, acceptance criteria. Sonnet'ы first-try выдали working code с минимальными отклонениями (Sonnet 1a сделал `auto_detected?` optional где Pydantic required — мелочь). Без дизайн-дока — drift и interface mismatch.

### L4 — `npm --prefix path` vs root proxy package.json
Tauri CLI определяет «project root» как ближайший package.json от cwd. Если в корне Aurora Launch нет package.json, npm идёт в подпапки (aurora-cloud `vercel dev` вместо frontend Vite). **Решение чище** — root proxy `package.json` со скриптами `npm --prefix frontend run dev/build`. Tauri конфиг остаётся стандартным `"npm run dev"`.

### L5 — CRLF/LF noise в git diff
`git diff --stat` показал 3 ADR файла в aurora-meta изменены (16+/4−), но реальный `git diff` пуст — только EOL normalization. Перед commit делать `git diff --ignore-all-space --stat` чтобы отделить content от noise.

---

## Decisions

### D1 — 4 архитектурных Q1-Q4 (от Антона 2026-05-18 утром)

| Q | Решение | Обоснование |
|---|---|---|
| **Q1.** Слить шаг `mapping` в `import` или оставить | **Слить (7→6 шагов)** | UX simplification; mapping — пережиток raw-source эпохи (это теперь Studio); роль правится в превью |
| **Q2.** `parse_data_file` deprecated или полностью удалить | **Удалить полностью** | Launch не в продакшн, BC не нужна; `.aurora` bundles используют `import_aurora_bundle` |
| **Q3.** Карточки OLS/Bayes из Optimizer портировать | **Не портировать** | Launch — Planner, не тренирует модель сам |
| **Q4.** Role override UI: dropdown vs click-cycle бэдж | **Dropdown в превью-таблице** | Excel-паттерн, accessible, consistency с Optimizer |

### D2 — Strategy: 3-commit chain (Б)
Альтернатива (А) one commit, (Б) три commit'а. Выбран **Б** — design doc → backend → frontend+Rust. Ревью проще, при rollback можно вырезать только UI-часть.

### D3 — Pydantic schema migration: отбросить old drafts через ValidationError
Старые wizard sessions с полями `column_mapping`/`mapping_done` не migr'ятся — `_wizard_session_load` ловит ValidationError, возвращает `{"session": None}` + log warning. Launch не в продакшн, реальных user drafts нет. Альтернатива (migrate-on-load) — overhead без выгоды.

### D4 — `methods_validation.py` дублирует detected recompute из validator
Опции:
- (A) Re-call validate_data после patching column roles (overhead read_excel)
- (B) Modify validator.py принимать `role_overrides` (divergence с Optimizer-shared file)
- (C) Document risk + NOTE-комментарий + sync mandatory при изменении validator

Выбран **(C)** — минимум divergence + INV reminder. Validator.py остаётся идентичным Optimizer.

### D5 — Push после pilot (но Антон сказал «пуш» раньше)
Изначально реко было «не пушить до pilot smoke». Антон явно сказал push → запушено сразу. Pilot ловится в following session.

### D6 — INV-41 в aurora-meta cross-product
Audit нашёл pattern: backend JSON-RPC handler с string union/enum input → whitelist guard mandatory. Cross-product applicable (Optimizer/Launch/Legal/Studio). Записано как INV-41 в `aurora-meta/ENGINEERING_INVARIANTS.md`, sister к INV-22/30/37.

---

## Pending

### P1 — Sidecar spawn diagnosis (BLOCKER pilot)
Окно открылось, но `analyze_data_file` падает с `state not managed for field sidecar`. Причина — `SidecarManager::spawn()` упал silent. Логи info-уровня скрыты без `RUST_LOG=info`.

Следующая сессия — запустить с env vars:
```powershell
$env:RUST_LOG="info"
$env:AURORA_BUILD_PROFILE="dev"
$env:AURORA_PROJECT_DB_KEY="none"
$env:AURORA_LAUNCH_TESTING="1"
cd "D:\Docs\Aurora_Ai\Aurora Launch"
npx --yes @tauri-apps/cli@^2.0.0 dev
```

В output ищем строку:
- `Sidecar manager initialised` → spawn OK, проблема в другом
- `Sidecar spawn failed (degraded mode...)` → конкретный error reason

Возможные причины: PyInstaller binary `aurora-sidecar-x86_64-pc-windows-msvc.exe` падает на init (ProjectDB encryption keychain), target-triple mismatch для Tauri shell plugin, env var conflict.

### P2 — Реальный pilot smoke до конца
7-пунктный чеклист (после P1 fix):
1. Stepper 6 шагов
2. «Выбрать файл» → диалог → xlsx из MMM Optimizer testdata → toast
3. DataPreviewTable: 20 строк + sticky-row + цветные точки + «авто» бэдж
4. Правка роли через dropdown → бэдж исчезает
5. Next → блокирующая validate → переход к Proxy
6. Reload → recovery dialog → восстановлены роли + оранжевый hint про перезагрузку файла
7. Stepper показывает 6 кружков, не 7

### P3 — UX/Aurora brand direction
Антон сказал «весь UI не в стиле Aurora» (welcome screen). Это **вне scope port'а**, но требует решения:

Варианты:
- **(A)** Premium dark усиленный — добавить gold/lime accents в существующую dark Aurora тему (`--color-brand-gold-primary` #C5A46D, `--color-brand-sig-lime` #CCFF00)
- **(B)** Cream day mode — переключить default на Aurora cream `#F7F5EE` + deep navy text + gold accent
- **(C)** Brand decorations — добавить sacred geometry, gold borders, lime sigils, illustrations

Требует design review с креативным директором. Не одноминутный фикс. Скорее всего отдельный sprint после P1/P2.

### P4 — Working tree infra fixes (НЕ закоммичено)
```
Aurora Launch/
  M src-tauri/tauri.conf.json   ← "visible": false → true
  ?? package.json               ← root proxy {"dev": "npm --prefix frontend run dev"}
```

Реко: отдельный commit `chore(launch): dev tauri runtime fixes` (root proxy + window visibility). Без них следующий dev на новой машине наступит на те же грабли.

Иначе откатить и решить другим путём (e.g. убрать sibling `aurora-cloud/` чтобы не было ambiguity, или добавить `.show()` в frontend onMount).

### P5 — Format adapters orphan (~550 LOC, 6 файлов)
После удаления `parse_data_file` модуль `engines/format_adapters/` стал orphan. Файлы:
- `registry.py` (87 LOC)
- `dsm_v2023.py`, `dsm_v2024.py` (176), `dsm_v2025.py`
- `mediascope_adex.py` (104), `mediascope_tv_index.py`
- `__init__.py`

Решено в design doc §6: удаление **отдельным коммитом следующей сессии**, чтобы текущая port-серия осталась атомарной.

### P6 — Backlog Launch следующие task
- **#8 Auto-update infra** — replace Vercel+Yandex+Ed25519 (Phase 2.9/2.10) на Optimizer pattern: GitHub Releases + Supabase Edge Function `quzhkfvglqmppxcrindh` + GitHub Pages `Ackold26/rosst-updates` fallback. ~6-8ч eng + 1-2ч Антон. Production checklist в backlog. Cost: 0₽ free tier.
- **#9 Cert signing reports** — облачная Ed25519 подпись PPTX/HTML/XLSX + QR embed + verify endpoint `verify.auroraai.pro/r/{report_id}`. ~1-2 дня, depends on #8.

---

## Errors & Workarounds

### E1 — `npm error code ERESOLVE` peer-deps conflict (Histoire + Svelte 5)
```
peer svelte@"^3.0.0 || ^4.0.0" from @histoire/plugin-svelte@0.17.17
Conflicting peer dependency: svelte@4.2.20
```
**Workaround:** `--legacy-peer-deps` flag для всех npm install в этом repo.

### E2 — `"tauri" не является внутренней или внешней командой`
**Cause:** Tauri CLI отсутствует в `node_modules/.bin/`, не в global PATH.
**Workaround:** `npx --yes @tauri-apps/cli@^2.0.0 dev` или `npm install -D @tauri-apps/cli@^2.0.0 --legacy-peer-deps`.

### E3 — `Couldn't recognize the current folder as a Tauri project`
**Cause:** CLI запущен из `frontend/`, который sibling `src-tauri/`. CLI ищет вниз, родителя не видит.
**Workaround:** запускать из root Aurora Launch.

### E4 — `npm error path Aurora Launch\aurora-cloud\frontend\package.json`
**Cause:** Tauri CLI выбрал `aurora-cloud/` как cwd для `beforeDevCommand` (alphabetically первый subdir с package.json).
**Workaround:** создан root `Aurora Launch/package.json` с proxy scripts → npm root = Aurora Launch/, `npm run dev` идёт правильно.

### E5 — Окно не появляется
**Cause:** `tauri.conf.json::app.windows[0].visible = false` + никто не зовёт `getCurrentWindow().show()` ни в Rust, ни в frontend.
**Workaround:** изменено `visible: true`. Альтернатива — добавить show() в frontend `onMount` или Rust `setup()`.

### E6 — `state not managed for field sidecar on command analyze_data_file`
**Cause:** `SidecarManager::spawn()` в `lib.rs:152` упал silent (env_logger без `RUST_LOG=info` info-уровень не выводит). При spawn fail → `manage()` не вызывается → команды зависящие от State падают.
**Workaround (для диагностики):** перезапустить с `$env:RUST_LOG="info"` + dev env vars. **Real fix** — выяснить почему spawn упал (sidecar binary crash на init? target-triple? env var?).

### E7 — CRLF/LF noise в git diff (aurora-meta)
**Cause:** `git diff --stat` показал 3 ADR файла изменены (16+/4−), но реальный diff пуст — only EOL normalization (autocrlf).
**Workaround:** `git diff --ignore-all-space --stat` → empty → safe откат через `git checkout -- <files>`.

---

## Setup & Config Changes

### S1 — Aurora Launch root `package.json` (NEW)
```json
{
  "name": "aurora-launch-root",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "npm --prefix frontend run dev",
    "build": "npm --prefix frontend run build"
  }
}
```
**Why:** Tauri CLI cwd disambiguation — без него `npm run dev` ищет в sibling subdirs (aurora-cloud Vercel).
**Status:** NOT committed, working tree dirty.

### S2 — `src-tauri/tauri.conf.json::visible` false → true
**Why:** окно создаётся скрытым, никто не зовёт `.show()` в коде → app spawned silent.
**Status:** NOT committed, working tree dirty.

### S3 — Pydantic `WizardSession` migration
- `WizardStep`: `Literal["import", "mapping", "proxy", "similarity", "anchors", "forecast", "cert"]` → `Literal["import", "proxy", "similarity", "anchors", "forecast", "cert"]`
- `step` bound: `Field(ge=0, le=6)` → `Field(ge=0, le=5)`
- Удалён `class ColumnMapping` + поля `column_mapping`, `mapping_done`
- Добавлен `class ColumnRoleAssignment` + поля `column_roles`, `validation_done`
**Migration strategy:** старые drafts отбрасываются через `ValidationError` catch в `_wizard_session_load`. Launch не в продакшн.
**Status:** committed `3f81c68`.

### S4 — Sidecar method registration
В `methods.py` late imports добавлен `import aurora_launch.sidecar.methods_validation`. Удалён re-export `UnsupportedFormatError` из `methods_project`.
**Status:** committed `3f81c68`.

### S5 — Rust invoke_handler
В `lib.rs::run()` `invoke_handler!`:
- Удалено: `commands::adapters::parse_data_file`, `commands::adapters::list_adapters`
- Добавлено: `commands::adapters::analyze_data_file`, `commands::adapters::validate_wide_table`
**Status:** committed `7eb9cc9`.

### S6 — Audit env vars для dev mode (pending P1)
Pre-dev checklist (не applied permanently):
```powershell
$env:RUST_LOG="info"
$env:AURORA_BUILD_PROFILE="dev"
$env:AURORA_PROJECT_DB_KEY="none"
$env:AURORA_LAUNCH_TESTING="1"
```
**Why:** sidecar spawn info-level logs скрыты + `methods.py:_get_project_db()` отказывается boot с `none` key без explicit dev profile.
**Status:** pending — применяется ручно next session, не permanent.

---

## Files Modified (Full Inventory)

### Aurora Launch — Created
| Path | LOC | Status |
|---|---|---|
| `docs/FILE_READER_PORT_DESIGN.md` | 656 | committed `c8a086c` |
| `src/aurora_launch/engines/validator.py` | 549 | committed `3f81c68` (port из Optimizer) |
| `src/aurora_launch/utils/column_detection.py` | 831 | committed `3f81c68` (port из Optimizer) |
| `src/aurora_launch/sidecar/methods_validation.py` | 130 | committed `3f81c68` |
| `tests/test_validator.py` | 162 | committed `3f81c68` (10 unit tests) |
| `tests/test_methods_validation.py` | ~250 | committed `3f81c68` (13 integration + 2 audit regressions) |
| `frontend/src/lib/components/DataPreviewTable.svelte` | 305 | committed `7eb9cc9` |
| `package.json` (root) | 9 | working tree, NOT committed |

### Aurora Launch — Modified
| Path | Change | Status |
|---|---|---|
| `src/aurora_launch/sidecar/methods.py` | late import + remove re-export | committed `3f81c68` |
| `src/aurora_launch/sidecar/methods_project.py` | удалён `parse_data_file` + `_CANONICAL_FIELDS_REGISTRY` + `UnsupportedFormatError` + try/except в `_wizard_session_load` | committed `3f81c68` |
| `src/aurora_launch/sidecar/server.py` | `UnsupportedFormatError` → `SidecarSecurityError` mapping | committed `3f81c68` |
| `src/aurora_launch/schemas/wizard_session.py` | Pydantic migration (S3) | committed `3f81c68` |
| `src/aurora_launch/tools/export_typescript.py` | `ColumnMapping` → `ColumnRoleAssignment` | committed `3f81c68` |
| `tests/test_wizard_session_handlers.py` | new shape expectations | committed `3f81c68` |
| `tests/test_sidecar_protocol_server.py` | removed UnsupportedFormatError test | committed `3f81c68` |
| `src-tauri/src/commands/adapters.rs` | parse_data_file/list_adapters → analyze_data_file/validate_wide_table | committed `7eb9cc9` |
| `src-tauri/src/lib.rs` | invoke_handler updated | committed `7eb9cc9` |
| `src-tauri/tauri.conf.json` | `visible: true` (S2) | working tree, NOT committed |
| `frontend/src/lib/ipc/client.ts` | types + methods replaced | committed `7eb9cc9` |
| `frontend/src/lib/stores/wizardSession.svelte.ts` | makeBlankSession new fields | committed `7eb9cc9` |
| `frontend/src/lib/types/aurora-schemas.d.ts` | auto-regen после Pydantic migration | committed `7eb9cc9` |
| `frontend/src/lib/i18n/locales/ru.json` | -1 + 20 keys preview/role/validation/recovery | committed `7eb9cc9` |
| `frontend/src/lib/i18n/locales/en.json` | symmetric | committed `7eb9cc9` |
| `frontend/src/routes/wizard/+page.svelte` | STEPS 7→6, state, pickImport, runValidation gate, render | committed `7eb9cc9` |
| `frontend/tests/e2e/_helpers/mock-ipc.ts` | analyze_data_file + validate_wide_table mocks | committed `7eb9cc9` |
| `frontend/tests/e2e/wizard-happy-path.spec.ts` | 6 шагов + recovery navigation | committed `7eb9cc9` |
| `frontend/tests/e2e/wizard.a11y.spec.ts` | 6 шагов adjustments | committed `7eb9cc9` |

### Aurora Launch — Deleted
- `frontend/src/lib/components/ColumnMappingTable.svelte` (207 LOC)
- `frontend/src/lib/utils/auto_map_columns.ts` (169 LOC)
- `frontend/tests/unit/auto_map_columns.test.ts`
- `frontend/tests/unit/ColumnMappingTable.test.ts`
- `tests/test_parse_data_file_column_mapping.py`

### aurora-meta — Modified
- `ENGINEERING_INVARIANTS.md` — INV-41 (Backend JSON-RPC handler whitelist union string values) committed `1229656` pushed

### Memory updates
- `C:\Users\ackol\.claude\projects\D--Docs-Aurora-Ai\memory\feedback_audit_after_sonnet_delegation.md` (new)
- `C:\Users\ackol\.claude\projects\D--Docs-Aurora-Ai\memory\feedback_tauri_dev_first_run_chain.md` (new)
- `C:\Users\ackol\.claude\projects\D--Docs-Aurora-Ai\memory\MEMORY.md` — top-entry + pickup hook

---

## Full Session Notes

### Phase 0: Recon (Opus)
Параллельно запущены 2 Explore агента:
- **Agent 1:** разведка Optimizer source — `validator.py` (549 LOC, role detection, data_preview, validate_data), `ImportStep.svelte` (1128 LOC, drag-drop, engine card OLS/Bayes, hardcoded RU), HTTP FastAPI sidecar pattern.
- **Agent 2:** разведка Launch target — Tauri 2 + Svelte 5 + SvelteKit 2.5, JSON-RPC stdio sidecar pattern `@register` decorator, существующий canonical-fields wizard (ColumnMappingTable 207 LOC + auto_map_columns 169 LOC), wizard step 0-6, svelte-i18n с ru.json/en.json.

После recon — 4 архитектурных вопроса Антону (D1). Получены ответы → запись design doc.

### Phase 1: Sonnet delegation
**Sonnet 1a (backend) + Sonnet 1b (frontend) запущены параллельно** с design doc как контрактом.

**Sonnet 1a output:**
- Создал 5 файлов (LOC totals выше)
- Изменил 6 файлов (methods.py, methods_project.py, server.py, schemas/wizard_session.py, tools/export_typescript.py + 2 теста)
- Удалил `tests/test_parse_data_file_column_mapping.py`
- pytest: 1543/1543 passed (8 skipped baseline)
- Отклонения от дизайн-дока: 4 малых (existed utils/__init__.py не пустой; SidecarSecurityError для missing file вместо status='error' — корректно security-wise; дополнительные правки server.py + export_typescript.py не были в design doc).

**Sonnet 1b output:**
- Создал DataPreviewTable.svelte (305 LOC)
- Изменил 7+ файлов
- Удалил 4 файла (ColumnMappingTable + auto_map_columns + их тесты)
- svelte-check: 0 errors (2 baseline tabindex warnings)
- vitest: 537/537 passed
- Отклонения: переписал Playwright happy path через recovery dialog паттерн (file picker не моким) — defensible workaround.

### Phase 2: Integration + Audit (Opus)

**Integration:**
- Rust commands wiring (adapters.rs replaced, lib.rs::invoke_handler updated)
- `npm run gen:types` с PYTHONIOENCODING=utf-8 — TS regenerated, новые типы корректны
- Удалила `as unknown as` casts в wizard +page.svelte и wizardSession.svelte.ts (поменяла на `satisfies WizardSession`)

**Audit pass (Opus) — нашёл 6 проблем:**

| # | Severity | Issue | Fix |
|---|---|---|---|
| 1 | **CRITICAL** | `validate_wide_table` пропускал любой role string в `role_overrides` | `_VALID_ROLES = frozenset(...)` + ValueError + 2 регрессии |
| 2 | **HIGH** | `validate_wide_table` нигде не вызывался из UI | `runValidation()` + `next()` gate + `$effect` сброса validationDone при role change |
| 3 | **MEDIUM** | `methods_validation.py` дублирует detected recompute | NOTE-комментарий + sync warning + cross-link к alternatives |
| 4 | **MEDIUM** | Dead state `importedAdapter`/`importedRecordCount` | Удалено |
| 5 | **MEDIUM** | Recovery flow с headers но без rows — confusing | Оранжевый callout `wizard.import.recovery_hint` (RU+EN) |
| 6 | LOW | `auto_detected?` optional в TS — generator behavior | Документировано, не баг |

**Final tests after audit:**
- pytest: 1545/1545 passed (+2 регрессий)
- vitest: 537/537 passed
- cargo check: exit 0
- svelte-check: 0 errors (2 baseline warnings)

### Commits + Push
3-commit chain (стратегия Б):
1. `c8a086c` docs(launch): file reader port design (Optimizer→Launch)
2. `3f81c68` feat(launch): port wide-table file reader from Optimizer (backend)
3. `7eb9cc9` feat(launch): port file reader frontend + IPC wiring

Aurora-meta:
- `1229656` INV-41: Backend JSON-RPC handler whitelist union string values

Push: оба repo на origin.

CRLF/LF noise в 3 ADR файлах aurora-meta — откатано через `git checkout` (см. E7).

### Pilot attempt
Антон запустил dev — каскад блокеров E1→E6:

**E1 (peer-deps)** → `--legacy-peer-deps` workaround
**E2 (CLI missing)** → `npx --yes @tauri-apps/cli@^2.0.0 dev`
**E3 (CLI cwd)** → переключение на root `Aurora Launch/`
**E4 (Vercel cwd)** → создан root `package.json` proxy (S1, NOT committed)
**E5 (окно нет)** → `visible: false` → `true` (S2, NOT committed)
**E6 (state not managed)** → sidecar spawn fail, нужен `RUST_LOG=info` + dev env vars для диагностики (P1)

### UX feedback (P3)
Окно открылось. Антон: «весь UI не в стиле Aurora». Скрин показал welcome screen — generic dark theme, синий `#2E5BFF` accent, нет gold (`#C5A46D`) или sacred lime (`#CCFF00`) brand-акцентов, контраст низкий на банере.

Это **existing-product UX issue**, не от моего port'а — welcome page я не трогала, port затрагивает только wizard step 0 (DataPreviewTable) который Антон не дошёл проверить из-за E6.

Решение направления (P3) — отдельный design pass, не закрывается в этой сессии. Антон сказал «займёмся проектом позднее, с этой части».

### Wrap-up
- 2 feedback memory created (audit + tauri infra)
- MEMORY.md updated с top-entry + pickup hook
- Working tree: 2 infra-fix файла НЕ закоммичено (P4)
- Pilot НЕ доведён (P1+P2 на следующую сессию)

**Pickup trigger:** «продолжаем Launch» / «продолжаем pilot Launch» / «возвращаемся к UI Launch»
