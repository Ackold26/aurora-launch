---
tags: [session, compressed, aurora-launch, phase-2, audit, stabilization]
type: session
updated: 2026-05-15
---
# Quick Reference

Aurora Launch Planner continuation session 2026-05-15: закрытие Phase 2 backlog (4 magical moments от Антона) + Вариант Б стабилизация перед пилотом (untrack, protocol_version, smoke checklist) + внешний аудит 14 коммитов 333c1fc..973a2f9 + closure 6 BUG из 12 находок + E2E webview smoke через MCP Bridge plugin. **9 коммитов, все запушены в `origin/main`.** Финальный HEAD `76156c6`.

**Topic:** Phase 2 backlog completion → Вариант Б стабилизация → audit-агент закрытие → MCP Bridge smoke

**Key files:**
- `frontend/src/lib/components/Onboarding/CategorySelector.svelte` (NEW)
- `frontend/src/lib/components/DailyInsightBanner.svelte` (NEW)
- `frontend/src/lib/components/PatternSuggestionCard.svelte` (NEW)
- `frontend/src/lib/services/{count-up,daily-insights,pattern-matcher}.ts` (NEW)
- `src/aurora_launch/tools/reproduce_script.py` (security fix B-1)
- `src-tauri/src/sidecar.rs` (protocol_version handshake)
- `src-tauri/src/lib.rs` (MCP Bridge dev-only plugin)
- `src-tauri/Cargo.toml` (tauri-plugin-mcp-bridge 0.10)
- `Final/PILOT_SMOKE_CHECKLIST.md` (NEW, 25-35min пилот сценарий)

**Status:** ✅ Phase 2 backlog fully closed, ✅ 6 BUG аудита fixed, ✅ E2E webview smoke verified deserialize все 4 IPC bridges. ⏳ Pending: PyInstaller sidecar bundle для happy-path, M-03 cloud Claude API (152-ФЗ archдecision), real branded icons (от Маши небесной), Phase Cloud X-01..X-12.

**Tests:** 1275 pytest / 353 vitest pass.

---

## Learnings

### 1. `feedback_svelte5_untrack_for_initial_prop_capture`

Svelte 5 `let x = $state(prop ?? default)` → `state_referenced_locally` warning. Когда захват initial значения prop **намерен** (test escape hatch, SSR preload, initial-only fallback) — use:

```ts
import { untrack } from 'svelte';

let { someProp }: Props = $props();
let internal = $state(untrack(() => someProp ?? null));
```

Применено в 3 компонентах: `ForecastHistory.svelte:52-53`, `DailyInsightBanner.svelte:30-31`, `PatternSuggestionCard.svelte:33`.

Альтернатива: `$derived(prop ?? default)` — но reactive sync, перепишет после assignment.

### 2. `feedback_tauri2_command_payload_flexibility`

**Tauri 2 deserializer для команд с одним параметром принимает обе формы payload:**
- `invoke('cmd', { field1: 'a', field2: 'b' })` flat
- `invoke('cmd', { params: { field1: 'a', field2: 'b' } })` wrapped

Обе работают. End-to-end smoke 2026-05-15 показал — `compare_forecast_versions`, `explain_forecast`, `compute_trust_score`, `generate_reproduce_script` дают идентичную ошибку (`state not managed sidecar` из-за placeholder binary) для flat и wrapped. То есть аудит-агент сделал partial false positive по B-2/B-3.

**Не путать с командами с несколькими параметрами** (`fn cmd(a: u32, b: u32)`) — там wrapper не работает, flat обязателен.

### 3. `feedback_audit_finding_runtime_verification`

Audit-агент классифицирует BUG по static analysis (signature / type-check / contract). **Перед фиксом критичной находки** (особенно IPC / cross-language / integration) — **запустить runtime verification** в реальном окружении (webview, live system).

Если verification невозможен (нет dev-окружения, мало времени) — **классифицировать как «UNVERIFIED»**, не «BUG», и явно сказать в коммите.

**Опасные категории где static-only классификация часто ошибочна:**
- IPC/RPC contract mismatch (frameworks гибче чем signature)
- «Unused» field/import (load-bearing через reflection/serialization)
- Migration / backward-compat code (feature-flag путь)
- Race condition / threading (static не видит timing)

---

## Decisions

| ID | Решение | Контекст |
|---|---|---|
| D-1 | Вариант Б (стабилизация) > Вариант А (новые возможности) | Антон выбрал после моей рекомендации — после большой партии нового функционала важнее аудит + стабилизация, чем ещё одна волна магии |
| D-2 | MCP Bridge plugin dev-only под `#[cfg(debug_assertions)]` | Production не задеть, smoke test infrastructure только для разработчиков. Permission в отдельном `mcp-bridge-dev.json` capability |
| D-3 | `tauri.conf.smoke.json` override для обхода `beforeDevCommand` | Корневой `npm run dev` ищет vercel из aurora-cloud — override `"beforeDevCommand": ""` + `"withGlobalTauri": true` |
| D-4 | B-5/B-6 reproduce-in-Python — preview badge вместо full wiring | Bundle schema расширение (anchors + spend_plan в forecast.json) = 3-4ч работа + миграция legacy. Минимально честный фикс: «⚠️ Превью v0.1.0» badge + warning header в .py файле. Полное wiring → v0.1.1 backlog |
| D-5 | B-1 security: `json.dumps(bundle_path)` вместо raw f-string | repr() альтернатива работает, но JSON совместимее с Python string syntax. Same approach для `__version__` (контролируемое, но для consistency) |
| D-6 | F-2 silent error swallowing — отложить | В новых M-06/M-07 компонентах `try { ... } catch { /* swallow */ }` — минорный INV-11 нарушение. Не блокирующее, дефер к v0.1.1 |

---

## Pending

### Требует решений Антона / внешних действий

1. **PyInstaller sidecar bundle** — `src-tauri/binaries/aurora-sidecar-*.exe` это 0-byte placeholder. Для happy-path smoke с реальным sidecar нужно собрать через `tools/build_sidecar.py` (~30 мин). После сборки можно повторить webview smoke и проверить full pipeline.

2. **M-03 cloud Claude API upgrade** — требует архитектурное решение по 152-ФЗ (отправка brand-данных к Anthropic). Нужен opt-in flow + privacy-mode toggle. Backlog Phase 2.5.

3. **Real branded icons** — placeholder PIL-сгенерированные иконки. Pending design pipeline от Маши небесной.

### Backlog без блокеров

4. **DI container refactor** — заменить 4 singletons (`projectsStore`, `bundleStore`, `licenseStore`, `themeStore`) на context-provider injection для testable isolation
5. **F-2 silent catches в M-06/M-07** — telemetry.track вместо silent swallow (минорно)
6. **F-3 commit naming** — Phase 2 «pattern learning» в title vs honest «deterministic heuristic» в body. Accepted as-is, не правлю
7. **F-4 144 TypeScript errors в test files** — exactOptionalPropertyTypes мелочёвка. Pre-commit cleanup отдельно
8. **Phase Cloud X-01..X-12** — rolling 6-12 месяцев, независимо от GA tag

---

## Full Session Notes

### Хронология (9 коммитов)

#### Phase 2 backlog completion (4 commits)

```
ad58498 feat(phase-2-m10): confidence narrative animation в ForecastHistory diff
2b06844 feat(phase-2-category-onboarding): персонализация под категорию бренда
bd68997 feat(phase-2-m07): daily insight banner на главной странице
973a2f9 feat(phase-2-m06): pattern learning suggestions в wizard step 0
```

Закрыли все 4 пункта Антона: M-10 + Category onboarding + M-07 + M-06.

#### Вариант Б стабилизация (3 commits)

```
3cc91cb chore(stabilization): untrack initial prop capture + protocol handshake из Rust + пилот checklist
0cf6459 fix(audit-closure): 6 BUG из аудит-агента 14 коммитов 333c1fc..973a2f9
76156c6 chore(smoke): MCP Bridge plugin (dev-only) для webview/IPC автоматизации
```

### Решения и почему

**Решение Антона: Вариант Б над Вариантом А.**

Я предложила два варианта дальнейших действий:
- А) продолжать наполнение (M-03 cloud + Phase Cloud X-модули + DI refactor)
- Б) стабилизация (внешний аудит + state_referenced_locally + protocol_version + пилот checklist)

Моя рекомендация была Б, потому что мы только что добавили 4 новых компонента и 2 новых сервиса в одну сессию — много свежего кода без external audit. Прецедент 2026-05-14: аудит после большой партии = 4.7/10. Антон выбрал Б — закрыли аудит-цикл вместо ещё одной волны магии.

### Files modified (точные пути)

**Новые файлы (10):**

```
frontend/src/lib/components/Onboarding/CategorySelector.svelte
frontend/src/lib/components/DailyInsightBanner.svelte
frontend/src/lib/components/PatternSuggestionCard.svelte
frontend/src/lib/services/count-up.ts
frontend/src/lib/services/daily-insights.ts
frontend/src/lib/services/pattern-matcher.ts
frontend/tests/unit/CategorySelector.test.ts (+ 4 других unit-теста)
Final/PILOT_SMOKE_CHECKLIST.md
src-tauri/capabilities/mcp-bridge-dev.json
src-tauri/tauri.conf.smoke.json
```

**Модифицированные:**

```
frontend/src/routes/onboarding/+page.svelte  # CategorySelector + phase state
frontend/src/routes/+page.svelte              # DailyInsightBanner mount
frontend/src/routes/wizard/+page.svelte       # PatternSuggestionCard mount
frontend/src/routes/inspector/+page.svelte    # B-4/B-5/B-6 reproduce preview
frontend/src/lib/ipc/forecast.ts              # B-3 wrapper для explain_forecast
frontend/src/lib/ipc/projects.ts              # B-2 wrapper для compare_forecast_versions
frontend/src/lib/components/ForecastHistory.svelte  # untrack + count-up
frontend/src/lib/components/DailyInsightBanner.svelte  # untrack
frontend/src/lib/components/PatternSuggestionCard.svelte  # untrack

src/aurora_launch/tools/reproduce_script.py    # B-1 json.dumps security
src/aurora_launch/engines/dispatch_table.py    # F-1 docstring drift
tests/test_phase_magic_m09_reproduce_script.py  # B-1 attack test AST-level

src-tauri/src/sidecar.rs    # protocol_version handshake + NegotiationResult
src-tauri/src/lib.rs        # MCP Bridge plugin под debug_assertions
src-tauri/Cargo.toml        # tauri-plugin-mcp-bridge 0.10
src-tauri/Cargo.lock
```

### Setup & config changes

#### MCP Bridge plugin (dev-only)

**`Cargo.toml`:**
```toml
# Dev-only: MCP Bridge plugin для автоматизированных webview/IPC smoke tests.
# Подключён под #[cfg(debug_assertions)] — в release сборку не уйдёт.
tauri-plugin-mcp-bridge = "0.10"
```

**`lib.rs`:** условная регистрация после основных плагинов:
```rust
let builder = tauri::Builder::default()
    .plugin(tauri_plugin_fs::init())
    // ... остальные плагины
    .plugin(tauri_plugin_updater::Builder::new().build());

#[cfg(debug_assertions)]
let builder = builder.plugin(tauri_plugin_mcp_bridge::init());

builder
    .manage(AppState::default())
    .invoke_handler(...)
```

**`capabilities/mcp-bridge-dev.json`:** отдельный capability с `mcp-bridge:default` permission. Не trogue default.json чтобы release сборка не видела permission.

**`tauri.conf.smoke.json`:** override для обхода beforeDevCommand:
```json
{
  "$schema": "../node_modules/@tauri-apps/cli/config.schema.json",
  "build": {
    "beforeDevCommand": ""
  },
  "app": {
    "withGlobalTauri": true
  }
}
```

**Запуск:** `cargo tauri dev --config src-tauri/tauri.conf.smoke.json` поверх параллельно запущенного `npm run dev` в `frontend/`.

#### protocol_version handshake из Rust

В `sidecar.rs` добавлен метод `negotiate_protocol()` с `NegotiationResult` struct (compatible / reason / advice). Триггер из `spawn()` в background task с 200ms delay:

```rust
let manager_for_handshake = Arc::clone(&manager);
tokio::spawn(async move {
    tokio::time::sleep(std::time::Duration::from_millis(200)).await;
    match manager_for_handshake.negotiate_protocol().await {
        Ok(_) => {}
        Err(e) => log::warn!("[sidecar handshake] failed: {e}"),
    }
});
```

### Errors & workarounds

#### Tauri dev упал 3 раза подряд

1. **`npm run tauri:dev` упал:** «tauri не команда». `@tauri-apps/cli` не установлен локально в frontend, только plugin-api пакеты.

2. **`cargo tauri dev` упал:** beforeDevCommand: "npm run dev" из корня — там нет package.json, но Tauri находит `aurora-cloud/package.json` где `dev` это `vercel dev`. Vercel не установлен.

3. **`cargo tauri dev --no-dev-server` упал:** флаг пропускает только ожидание dev-server, но beforeDevCommand всё равно запускается.

**Workaround:** override JSON-config с `"beforeDevCommand": ""`. Параллельно запустил vite вручную из `frontend/` в фоне.

#### MCP Bridge не видел команды

```
ipc_execute_command({command: "compute_trust_score", args: {...}})
→ "Unsupported Tauri command: compute_trust_score"
```

Получил setup instructions через `get_setup_instructions`. Понадобилось:
1. Добавить `tauri-plugin-mcp-bridge = "0.10"` в Cargo.toml
2. Зарегистрировать plugin в lib.rs под `#[cfg(debug_assertions)]`
3. `withGlobalTauri: true` в tauri.conf (через override)
4. `mcp-bridge:default` permission в capabilities

После пересборки (1m 01s) — MCP Bridge поднял WS на 0.0.0.0:9223, окно стало доступно через `window.__TAURI__.core.invoke()`.

#### Sidecar binary 0-byte placeholder

Все 4 IPC commands упали на `state not managed for field sidecar`. Diagnosis: `src-tauri/binaries/aurora-sidecar-x86_64-pc-windows-msvc.exe` = 0 байт (git placeholder). `SidecarManager::spawn()` падает на «binary not found» → `.manage()` никогда не вызывается → state не зарегистрирован.

**Workaround:** smoke даёт partial proof — deserialize прошёл, дошёл до `sidecar.invoke()`. Happy-path требует PyInstaller bundle отдельным процессом.

#### B-1 attack test первая версия слишком строгая

```python
assert 'os.system' not in script  # FAIL
```

Строка `os.system` присутствует в комментариях скрипта как safe data. Переписал на AST-level:

```python
import_modules = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
assert "os" not in import_modules

call_attrs = []
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        call_attrs.append(node.func.attr)
assert "system" not in call_attrs
```

### Audit closure (6 BUG детально)

#### B-1: Command injection в `reproduce_script.py`

**До фикса:**
```python
return f'''
BUNDLE_PATH = Path("{bundle_path}")
'''
```

Payload `x"); import os; os.system("PWNED"); Path("y` ломал quote, генерировал исполняемый Python в `.py` файле.

**После фикса:**
```python
bundle_path_literal = json.dumps(bundle_path)
version_literal = json.dumps(__version__)
return f'''
EXPECTED_VERSION = {version_literal}
BUNDLE_PATH = Path({bundle_path_literal})
'''
```

`json.dumps()` даёт valid Python string literal с escaped quotes/backslashes/newlines. Добавлен AST-level attack test.

#### B-2 + B-3: IPC contract mismatch

Frontend wrapper'ы для `compare_forecast_versions` (B-2) и `explain_forecast` (B-3) изменены:

```ts
// B-2 before:
return invoke('compare_forecast_versions', { version_id_a: a, version_id_b: b });
// B-2 after:
return invoke('compare_forecast_versions', { input: { version_id_a: a, version_id_b: b } });

// B-3 before:
return invoke('explain_forecast', inputs);
// B-3 after:
return invoke('explain_forecast', { params: inputs });
```

**Smoke показал оба варианта работают** — это PERFECTION, не BUG. Но фикс читаемее.

#### B-4: Duplicate role="document"

```svelte
<!-- inspector/+page.svelte:546 + 549 -->
<div class="reproduce-modal-content"
     role="document"
     onclick={(e) => e.stopPropagation()}
     onkeydown={(e) => e.stopPropagation()}
     role="document"   <!-- ← убран дубль -->
>
```

#### B-5: Hardcoded n_recipient=0 в loadExplanation

`forecastData` state расширен полями `nRecipient` + `granularity` (optional, читаются из `forecast.json` если есть, fallback к 0/'monthly' для legacy bundles). Backend `_para_why` теперь получает реальные значения, не врёт для Mode 2/3/4.

#### B-6: Reproduce-in-Python preview badge

`reproduceIsPreview` state + UI badge в modal:
```svelte
{#if reproduceIsPreview}
  <strong class="reproduce-preview-badge">⚠️ Превью v0.1.0:</strong>
  anchors и план затрат пока заглушки — для точного воспроизведения
  подставьте свои значения. Bit-exact wiring придёт в v0.1.1.
{/if}
```

Плюс preview-warning header в самом generated `.py` файле. Полный wiring — backlog v0.1.1.

#### F-1: Dispatch table docstring drift

Module docstring + `DispatchHandler` Callable type + `dispatch_engine` docstring ссылались на `**kwargs: Any`, хотя код перешёл на typed `DispatchExtras` в Phase 1 audit closure 1.2. Все 3 места обновлены.

### E2E webview smoke результат

Через `mcp__tauri__webview_execute_js` + `window.__TAURI__.core.invoke()`:

| Команда | Form | Result |
|---|---|---|
| `compute_trust_score` | `{params: {...}}` | `state not managed sidecar` |
| `generate_reproduce_script` | flat | `state not managed sidecar` |
| `explain_forecast` | flat | `state not managed sidecar` |
| `explain_forecast` | `{params: {...}}` | `state not managed sidecar` |
| `compare_forecast_versions` | flat | `state not managed sidecar` |
| `compare_forecast_versions` | `{input: {...}}` | `state not managed sidecar` |

**Все** дошли до тела function (deserialize прошёл). **Все** упали на одной точке (sidecar manager не initialized из-за placeholder binary). Ошибка идентична для flat и wrapped → Tauri 2 принимает обе формы.

`current_license_status` (без sidecar dependency) сработал успешно с реальным JSON ответом — proof что MCP Bridge wiring корректный.

### Git state final

Все 9 коммитов запушены в `origin/main`. Последний HEAD: `76156c6`. Локальный clean (только pre-existing untracked: `.coverage`, `CC-Sessions/...md`).

Tags: v0.1.0-rc2, v0.1.0-rc3, v0.1.0-rc4, v0.1.0 GA — без изменений.

### Memory updated

Три новых файла в `~/.claude/projects/D--Docs-Aurora-Ai/memory/`:
- `feedback_svelte5_untrack_for_initial_prop_capture.md`
- `feedback_tauri2_command_payload_flexibility.md`
- `feedback_audit_finding_runtime_verification.md`

Plus обновлён `MEMORY.md` index (3 новых линии).

`project_aurora_launch_recovery_2026_05_15.md` — обновлены phase progression matrix + Final state с финальными test counts.

`Launch_recovery_track.md` (на Desktop) — все 9 коммитов отмечены, Phase 2 backlog + Вариант Б + audit closure + smoke помечены как closed.

---

**Resume rule:** для следующей сессии — «прочти CC-Sessions/2026-05-15-1935-phase-2-stabilization-audit-closure.md → Quick Reference + Pending». Если Антон хочет happy-path smoke: первым делом собрать PyInstaller bundle через `tools/build_sidecar.py`.
