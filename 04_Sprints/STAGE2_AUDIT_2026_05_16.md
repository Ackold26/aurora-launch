# Stage 2 Red-Team Audit — 2026-05-16

**Scope:** коммиты `b462c81`..`553a0ef` (этапы 1.3d, 2.5, 2.7, 2.8, 2.9)
**Ветка:** `feat/stage1-core-1.1-1.4`
**Аудитор:** Claude Sonnet 4.6 (autonomous red-team pass)
**Статус:** READ-ONLY — fixes НЕ применены

---

## Summary

| Severity | Count |
|---|---|
| BLOCKER | 2 |
| HIGH | 4 |
| MEDIUM | 4 |
| LOW | 3 |
| FALSE-POSITIVE | 2 |
| **Total** | **15** |

---

## BLOCKER — Критические баги, блокируют production ship

---

### B-1 — Updater pubkey placeholder остаётся `"EMBED_AT_RELEASE_TIME"` в shipped binary

**Категория:** Security / Auto-update
**Файлы:** `src-tauri/tauri.conf.json:77`, `src-tauri/build.rs:42-61`

**Описание:**

`tauri.conf.json` содержит:
```json
"plugins": { "updater": { "pubkey": "EMBED_AT_RELEASE_TIME" } }
```

`build.rs` (строки 44-61) проверяет `AURORA_UPDATER_PUBKEY` env var, но **не патчит `tauri.conf.json`**. Вместо этого он только делает:
```rust
println!("cargo:rustc-env=AURORA_UPDATER_PUBKEY={}", updater_pubkey);
```

Это Rust compile-time env var — он недоступен `tauri_build::build()`. Tauri plugin-updater читает pubkey из `tauri.conf.json` на этапе `tauri_build::build()` (bakes всю конфигурацию в бинарник). Никакого кода который патчит `tauri.conf.json` перед сборкой нет ни в `build.rs`, ни в `release.yml`.

**Доказательство:**
- `release.yml` передаёт `AURORA_UPDATER_PUBKEY: ${{ secrets.AURORA_UPDATER_PUBKEY }}` как env в build step (строка 258), но нет ни одного `jq`/`sed`/Python шага, который бы заменил placeholder в файле.
- Комментарий в `build.rs` строка 42-43: _"The build replaces the placeholder in tauri.conf.json (or fails the build)"_ — **ложный** (wishful code comment без реализации).
- `build.rs` panic gate гарантирует что `cargo build --release` без env var падает. Но panic gate не значит что pubkey попадает в `tauri.conf.json`.

**Последствие:** production binary содержит `"EMBED_AT_RELEASE_TIME"` как pubkey → `tauri-plugin-updater` воспримет его как literal pubkey строку (не Ed25519 bytes) → либо signature verification всегда падает (banner показывает error) → **auto-update полностью нерабочий** в production, И/ИЛИ updater принимает любую подпись (зависит от реализации plugin при invalid pubkey format).

**Suggested fix:**
В `release.yml` перед шагом `Build Tauri app`, добавить python/jq шаг:
```bash
python3 -c "
import json, os
conf = json.load(open('src-tauri/tauri.conf.json'))
conf['plugins']['updater']['pubkey'] = os.environ['AURORA_UPDATER_PUBKEY']
json.dump(conf, open('src-tauri/tauri.conf.json', 'w'), indent=2)
"
```
И обновить комментарий в `build.rs` (или убрать `cargo:rustc-env` для pubkey — он не используется).

**Effort:** 30 мин

---

### B-2 — GC thread читает `_PROJECT_DB` напрямую, игнорирует DI container

**Категория:** DI / Thread-safety / Test isolation
**Файлы:** `src/aurora_launch/sidecar/methods.py:267, 271, 285, 293, 294`

**Описание:**

Весь DI-контейнер (этап 2.7) маршрутизирует `_get_project_db()` через `get_services()` → если тест инжектировал mock через `set_services_for_testing(container)`, все HTTP-handlers корректно используют mock. Но `_gc_thread_body()` читает **модульную переменную `_PROJECT_DB` напрямую** (строки 267, 271, 285, 293, 294):

```python
if _PROJECT_DB is not None:  # line 267 — bypass DI
    last_ran_at, _ = _PROJECT_DB.get_gc_metadata()  # line 271
...
collected = _PROJECT_DB.gc_orphan_blobs()  # line 293
_PROJECT_DB._update_gc_metadata(collected)  # line 294
```

**Последствие 1 (test isolation):** Если тест через `set_services_for_testing(mock_container)` инжектирует mock ProjectDB, GC thread (если он уже запущен) продолжает вызывать методы на `_PROJECT_DB` (реальный или None). Тест-изоляция нарушена — GC thread может обращаться к закрытой/несуществующей БД из предыдущего теста.

**Последствие 2 (production hang):** При shutdown: `shutdown` handler сначала сбрасывает `_PROJECT_DB = None` (строка 1830), затем `get_services().clear()`. GC thread между этими двумя операциями может поймать `_PROJECT_DB is not None` в строке 267 (предыдущая итерация цикла), войти в `gc_orphan_blobs()` — пока shutdown завершает clear. Это UaF-подобный паттерн (Use after Free) на Python объекте.

**POSSIBLE** — в production маловероятно (GC проверяет раз в 7 дней, shutdown обычно быстрее), но в тестовой среде реализуемо.

**Suggested fix:**
В `_gc_thread_body()` заменить прямые обращения к `_PROJECT_DB` на вызов `_get_project_db()` (с проверкой на None). Это маршрутизирует через DI + double-checked locking:
```python
db = _get_project_db() if _PROJECT_DB is not None else None
if db is None:
    ...
last_ran_at, _ = db.get_gc_metadata()
```

**Effort:** 45 мин

---

## HIGH — Серьёзные проблемы, должны быть закрыты до production

---

### H-1 — `window.location.reload()` ненадёжен в Tauri webview для перезапуска sidecar

**Категория:** Handshake / UX
**Файлы:** `frontend/src/lib/components/HandshakeIncompatibleModal.svelte:48-50`

**Описание:**

```typescript
function reload() {
  window.location.reload();
}
```

В Tauri 2 webview `window.location.reload()` перезагружает HTML/JS фронтенд, но **НЕ перезапускает Rust shell и Python sidecar**. Handshake mismatch происходит на уровне Rust↔Python процессов — перезагрузка webview не убьёт несовместимый sidecar. После reload фронтенд снова подпишется на `sidecar://handshake_complete`, получит то же самое `compatible: false` (sidecar всё ещё жив и несовместим), и modal появится снова.

Правильный API для full app restart в Tauri: `relaunch()` из `@tauri-apps/plugin-process` (уже импортирован в `UpdateAvailableBanner.svelte:22`). `relaunch()` завершает весь процесс Tauri и запускает новый — убивает sidecar, перечитывает конфигурацию.

**Доказательство:**
- `UpdateAvailableBanner.svelte` строка 22 уже использует `import { relaunch } from '@tauri-apps/plugin-process'`
- `HandshakeIncompatibleModal` использует `window.location.reload()` — несоответствие паттернов в одном проекте.

**Suggested fix:**
```typescript
import { relaunch } from '@tauri-apps/plugin-process';

async function reload() {
  try {
    await relaunch();
  } catch (e) {
    // fallback для dev / тестов где plugin-process может быть недоступен
    window.location.reload();
  }
}
```

**Effort:** 20 мин

---

### H-2 — Download progress: `chunkLength` — delta, а НЕ накопленный total (POSSIBLE — требует проверки commit версии)

**Категория:** UX / Update banner
**Файлы:** `frontend/src/lib/components/UpdateAvailableBanner.svelte`

**Описание:**

**POSSIBLE** — при проверке обнаружено что файл имеет более новую версию (с комментарием `// Audit A-1 (этап 2.10)`) где исправление уже применено. Если это коммит В SCOPE данного аудита — см. ниже.

Оригинальный код (который мог быть в scope):
```typescript
downloadProgress = Math.min(100, Math.round((chunkLen / totalLen) * 100))
```
где `chunkLen = progress.data?.chunkLength ?? 0` — **размер одного chunk**, не накопленный. Progress bar прыгал бы случайно (0%→50%→2%→80%).

Исправленная версия накапливает `downloadedBytes += chunkLength` и корректно обрабатывает `Started`/`Progress`/`Finished` events.

**Если исправление уже в рабочей ветке** — FALSE-POSITIVE. Если этот файл не был изменён в scope этапа 2.9 и исправление пришло из другой ветки — **verify**.

**Suggested fix:** если bug активен — накапливать bytes через локальный аккумулятор.

**Effort:** 15 мин (если bug активен)

---

### H-3 — `forecastCompleted = true` но `forecastPoints` может быть пустым при edge case

**Категория:** Wizard save flow / Data integrity
**Файлы:** `frontend/src/routes/wizard/+page.svelte:296-298`

**Описание:**

`saveBundle()` guard:
```typescript
if (!forecastCompleted || forecastPoints.length === 0) {
  pushToast({ level: 'danger', title: 'Сначала дождитесь окончания прогноза' });
  return;
}
```

Guard корректен. Однако есть edge case: `forecastCompleted` устанавливается в `true` в обработчике `sidecar://forecast_completed` (строка 217), который обновляет `forecastStatus.progress = 1` — но **не** проверяет что `forecastPoints` непустой. Если Python sidecar отправил `forecast_completed` без предшествующих `forecast_progress` событий (e.g., очень короткий forecast с horizon=1 week завершился до первого progress event), то `forecastCompleted = true` но `forecastPoints = []`.

В текущей кодовой базе `forecastPoints` заполняется только из `forecast_progress` events — кейс realистичен при крайне быстром forecast или network buffering.

**Последствие:** `composeForecastJson` получит `weekly_points: []`. Сохранится пустой `forecast.json`. Inspector M-09 будет молча рендерить пустой конус.

**Suggested fix:**
В обработчике `sidecar://forecast_completed` дополнительно присваивать точки из `payload.forecast?.points` если они есть:
```typescript
// Fallback: если forecast_progress events потерялись, использовать payload.points
if (forecastPoints.length === 0 && summary?.points?.length) {
  forecastPoints = summary.points.map((p, i) => ({
    weekIndex: i,
    point: p.point_forecast,
    ciLower: p.ci_lower,
    ciUpper: p.ci_upper,
  }));
}
```

**Effort:** 30 мин

---

### H-4 — `set_services_for_testing` не сбрасывает модульные `_PROJECT_DB`/`_AUTOSAVE`

**Категория:** DI / Test isolation
**Файлы:** `src/aurora_launch/sidecar/services.py:120-145`, `src/aurora_launch/sidecar/methods.py:74-83`

**Описание:**

`set_services_for_testing(new_container)` заменяет глобальный `_services` объект. После вызова `get_services()` вернёт `new_container`. Но модульные переменные `_PROJECT_DB` и `_AUTOSAVE` в `methods.py` не сбрасываются.

`_get_project_db()` проверяет DI container **первым** (строка 172-175):
```python
_svc = get_services()
_container_db = _svc.get_project_db()
if _container_db is not None:
    return _container_db
```

Если контейнер теста не содержит `project_db` (т.е. `container.project_db = None`), функция падает на строку 179: `if _PROJECT_DB is not None: return _PROJECT_DB` — и возвращает **реальный** singleton из предыдущего теста (если предыдущий тест инициализировал DB).

Это нарушает test isolation когда:
1. Тест A: инициализирует реальный `_PROJECT_DB` (side effect)
2. Тест B: `set_services_for_testing(ServiceContainer())` — пустой container
3. `_get_project_db()` в тесте B вернёт `_PROJECT_DB` из теста A

**Suggested fix:**
`reset_services_for_testing()` должна также сбрасывать модульные переменные:
```python
def reset_services_for_testing() -> None:
    global _services
    with _services_lock:
        _services = ServiceContainer()
    # Сбросить module-level синглтоны чтобы избежать test pollution
    import aurora_launch.sidecar.methods as _m
    _m._PROJECT_DB = None  # noqa: SLF001
    _m._AUTOSAVE = None    # noqa: SLF001
```
Или добавить явный параметр `reset_module_singletons: bool = False`.

**Effort:** 45 мин

---

## MEDIUM — Требуют внимания, но не блокируют pilot

---

### M-1 — `handleId: 'wizard-new'` совпадёт с реальным handle если UUID случайно совпадает

**Категория:** Wizard save / Handle collision
**Файлы:** `frontend/src/routes/wizard/+page.svelte:337`, `src-tauri/src/commands/bundle.rs:384`

**Описание:**

Wizard вызывает:
```typescript
await ipc.saveBundleViaSidecar({ handleId: 'wizard-new', targetPath, ... });
```

В `bundle.rs:save_bundle`:
```rust
match bundles.get(&handle_id) {
    Some(handle) => Some(handle.path.clone()),
    None => None, // Initial save — fresh-create branch
}
```

Handle IDs назначаются через `Uuid::new_v4().to_string()` (строка 164) — они никогда не будут строкой `"wizard-new"`. Collision **невозможна в production**. Но если кто-то откроет bundle с handle_id вручную установленным в `"wizard-new"` (e.g., тест, фаззинг), `save_bundle` вернёт `source_path` реального bundle вместо fresh-create → wizard перезапишет существующий bundle с минимальным forecast.json.

**POSSIBLE** — в production нереализуемо, но архитектурный запах.

**Suggested fix:**
Передавать `handleId: null` или отдельный параметр `fresh_create: true` вместо magic string. В `bundle.rs` добавить ветку:
```rust
if handle_id == "wizard-new" || handle_id.is_empty() {
    return Ok(None); // always fresh-create
}
```

**Effort:** 20 мин

---

### M-2 — `reload()` в handshake modal не защищает от double-click

**Категория:** UX / Handshake modal
**Файлы:** `frontend/src/lib/components/HandshakeIncompatibleModal.svelte:48-50, 97-101`

**Описание:**

```typescript
function reload() {
  window.location.reload(); // synchronous intent, but...
}
```
Кнопка «Перезапустить приложение» не disabled после первого клика. Если пользователь кликнет дважды быстро — два reload вызова. При переходе на `relaunch()` (H-1) это становится важнее: `relaunch()` — async, между первым и вторым кликом есть window. Второй `relaunch()` вызов во время первого может вызвать undefined behavior (double process restart).

**Suggested fix:**
Добавить `restarting = $state(false)` и `disabled={restarting}` на кнопку, установить перед вызовом.

**Effort:** 10 мин

---

### M-3 — Update banner dismiss-per-session: critical security update невидим после dismiss

**Категория:** Update banner / UX risk
**Файлы:** `frontend/src/lib/components/UpdateAvailableBanner.svelte:131-133, 45`

**Описание:**

```typescript
function dismiss() {
  dismissedThisSession = true;
}
```

`dismissedThisSession` — `$state(boolean)`, сбрасывается только при reload/restart. После dismiss banner не появится до следующего перезапуска, даже если через 8 часов той же сессии обнаруживается critical security patch. `checkForUpdate()` вызывается **один раз при mount** (строка 70), повторной проверки нет.

**Последствие:** пользователь закрывает "update available" banner → пользуется 8 часов → приходит security patch → не увидит уведомление до следующего перезапуска. При slow-upgrading пользователях (закрывают app раз в несколько дней) окно уязвимости может быть > 24h.

**Suggested fix (LOW priority для v0.1):**
После dismiss — не запрещать повторный показ если через N часов checkForUpdate() обнаруживает новую версию, отличную от уже dismissed. Или добавить periodic re-check (раз в 4 часа, только в idle state).

**Effort:** 2h (scope может быть велик — backlog material)

---

### M-4 — DB migration test 4 использует `apply_pending_migrations` на уже-мигрированной БД без проверки идемпотентности вставки

**Категория:** DB migration tests / Test correctness
**Файлы:** `tests/test_db_migrations.py:320-322`

**Описание:**

В тесте `TestFutureMigrationSkeleton.test_new_sql_migration_bumps_schema_version`:
```python
# Apply real v001 + v002 first
real_mig_dir = MIGRATIONS_DIR
apply_pending_migrations(conn, real_mig_dir)
assert get_current_version(conn) == CURRENT_SCHEMA_VERSION

# Now apply real + synthetic v003 from the copy
applied = apply_pending_migrations(conn, mig_copy)
```

`mig_copy` содержит копию реальных migrations (v001, v002) + synthetic v003. При втором вызове `apply_pending_migrations(conn, mig_copy)` мигратор должен пропустить v001 и v002 (уже применены). Тест предполагает что `len(applied) == 1`. Если мигратор использует `INSERT OR REPLACE INTO schema_version` без проверки существующих записей — вторичное применение v001/v002 может пройти молча (с OR REPLACE перезапишет), и `applied` может вернуть 3 вместо 1.

Это зависит от реализации `apply_pending_migrations`. Тест проверяет контракт, но сам тест не защищён от неправильной реализации идемпотентности в migrator.

**Suggested fix:**
Добавить явный assert что v001 и v002 НЕ в `applied`:
```python
assert not any(m.version in (1, 2) for m in applied), \
    "Migrations v001/v002 must not be re-applied"
```

**Effort:** 15 мин

---

## LOW — Косметика, технический долг

---

### L-1 — Handshake: пустой `_services_lock` в `set_services_for_testing` — race window

**Категория:** Thread-safety (теоретическая)
**Файлы:** `src/aurora_launch/sidecar/services.py:120-134`

**Описание:**

```python
def set_services_for_testing(svc: ServiceContainer) -> None:
    global _services  # noqa: PLW0603
    with _services_lock:
        _services = svc
```

`_services` — module-level variable, assignment атомарна в CPython (GIL). `_services_lock` защищает assignment но `get_services()` читает без lock:
```python
def get_services() -> ServiceContainer:
    return _services
```

В тестовой среде (single-threaded pytest, no worker threads from sidecar) это безопасно. В production (многопоточный sidecar) `set_services_for_testing` никогда не вызывается. **FALSE-POSITIVE для production** — только теоретический race в тестах с threaded pytest-workers.

**Effort:** 10 мин (добавить lock в get_services если хочется строгости)

---

### L-2 — `forecastEngineMode` fallback `'pure_transfer'` при null — silent assumption

**Категория:** Wizard save / Data correctness
**Файлы:** `frontend/src/routes/wizard/+page.svelte:322`

**Описание:**

```typescript
engine_mode: forecastEngineMode ?? 'pure_transfer',
```

Если `ForecastCompletedEvent.forecast` был null (старый путь emit без summary), `forecastEngineMode` останется null. Fallback `'pure_transfer'` тихо проставляется в `forecast.json` — даже если реальный engine был иным. Inspector M-09 reproduce будет использовать неверный engine_mode.

**Suggested fix:** Добавить log warning при fallback:
```typescript
if (!forecastEngineMode) {
  console.warn('[wizard] forecastEngineMode missing — defaulting to pure_transfer');
}
```

**Effort:** 5 мин

---

### L-3 — i18n: `updater.banner.dismiss_aria` используется дважды в одном баннере без семантического различия

**Категория:** i18n / Accessibility
**Файлы:** `frontend/src/lib/components/UpdateAvailableBanner.svelte:175, 215, 229`

**Описание:**

Ключ `updater.banner.dismiss_aria` = "Скрыть уведомление об обновлении" используется как `aria-label` на кнопках «Позже» (available state) и «Позже» (ready state) и «×» (error state) — три разные кнопки с одинаковым aria-label. Screen reader пользователь не может различить «отложить установку» vs «закрыть ошибку».

**Suggested fix:** Добавить отдельные ключи `updater.banner.dismiss_update_aria` и `updater.banner.dismiss_error_aria`.

**Effort:** 20 мин (3 ключа + обновить шаблон)

---

## FALSE-POSITIVE

---

### FP-1 — `handleId: 'wizard-new'` — не коллизия с UUID handles

**Объяснение:** UUID v4 в виде строки `"xxxxxxxx-xxxx-4xxx-..."` никогда не равна `"wizard-new"`. Rust lookup `bundles.get(&"wizard-new")` → `None` → fresh-create путь. Логика корректна. (Отмечено в M-1 как запах, но не баг.)

---

### FP-2 — Timing window в handshake pull vs event

**Описание (из аудит-задания):** "что если pull тоже промахивается (timing window)?"

**Анализ:** Реализация (строки 22-41 HandshakeIncompatibleModal) правильно обрабатывает все случаи:
1. Подписка на event ПЕРЕД pull (строка 22 перед строкой 34)
2. Если event пришёл между subscribe и pull — обработчик event сработает, pull вернёт уже-установленный статус (they converge)
3. Если pull возвращает `null` (handshake ещё не завершён) — event прилетит позже и обновит `result`
4. При ошибке pull (строка 38) — `console.warn`, ждём event

Единственный edge-case: handshake завершился между `await listen()` и `await ipc.getHandshakeStatus()` — но `handshake_state` Mutex в Rust уже содержит результат к моменту pull. **FALSE-POSITIVE.**

---

## Cross-cutting Observations

### CO-1 — UpdateAvailableBanner + HandshakeIncompatibleModal: z-index стек корректен

- Update banner: `z-index: 900` (не blocking, normal flow)
- Feedback overlay: `z-index: 1100`
- Handshake modal backdrop: `z-index: 9999`

Handshake modal всегда поверх update banner. Корректно — handshake блокирующий, banner информационный.

### CO-2 — DI container + handshake state: нет путаницы

`handshake_state` живёт в `SidecarManager` (Rust Mutex), `ServiceContainer` хранит Python-side синглтоны. Это разные слои без пересечений. Нет проблемы.

### CO-3 — `reset_services_for_testing` не закрывает ресурсы

`services.py:clear()` имеет предупреждение: "call close() before clear() in production so DB locks are released". В тестах с mock объектами это нормально, но если тест открыл реальный ProjectDB через set_project_db() — `reset_services_for_testing()` не вызовет `.close()`. Тест fixture должен явно закрывать DB до reset. Документировано в docstring, но риск утечки file handle в неаккуратных тестах.

---

## Приоритет закрытия

| # | Finding | Effort | Risk |
|---|---|---|---|
| 1 | B-1 pubkey placeholder | 30m | Updater полностью нерабочий |
| 2 | H-1 reload() → relaunch() | 20m | Handshake recovery не работает |
| 3 | B-2 GC bypass DI | 45m | Test pollution + shutdown race |
| 4 | H-4 DI test isolation | 45m | Test pollution |
| 5 | H-3 empty forecastPoints | 30m | Silent corrupt bundle |
| 6 | M-2 double-click reload | 10m | UX |
| 7 | M-1 wizard-new magic string | 20m | Architecture |
| 8 | M-4 migration test assert | 15m | Test gap |
| 9 | L-1, L-2, L-3 | <30m | Polish |
| 10 | M-3 dismiss + re-check | 2h | Backlog |

---

*Аудит завершён 2026-05-16. Следующий шаг: Антон ревьюит, применяет fixes в порядке приоритета.*
