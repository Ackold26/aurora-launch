# Stage 1 Red-Team Audit — Aurora Launch
**Дата:** 2026-05-16  
**Ветка:** `feat/stage1-core-1.1-1.4`, HEAD `54f38d4`  
**Scope:** 7 коммитов этапа 1 (пункты 1.1–1.8 ROADMAP_POST_V0_1_0)  
**Аудитор:** Claude Sonnet 4.6 (автономный static + runtime analysis)

---

## Summary

| Severity   | Count |
|------------|-------|
| BLOCKER    | 1     |
| HIGH       | 3     |
| MEDIUM     | 5     |
| LOW        | 3     |
| FALSE-POSITIVE | 5 |

**Всего findings: 12** (плюс 5 FALSE-POSITIVE, описанных в конце)

---

## BLOCKER

### B-1 · `spend_plan` принимает NaN/Infinity — JCS canonical serialization падает

**Файл:** `src/aurora_launch/schemas/forecast_bundle.py` — `ForecastJsonV1`, поле `spend_plan: dict[str, list[float]] | None`  
**Категория:** Reliability / Backwards-compat  
**Effort:** S

**Описание.**  
`ForecastPoint` и `RecipientAnchorsPayload` защищены `@field_validator` через `_reject_non_finite`. Поле `spend_plan` — `dict[str, list[float]]` — **не имеет аналогичного валидатора**. Pydantic принимает `spend_plan={"tv": [float("nan")]}` без ошибки.

Последствия:
1. `to_bundle_bytes()` вызывает `json.dumps`. Python по умолчанию сериализует `NaN` как токен `NaN` (невалидный JSON — RFC 4627 §2.4 запрещает).
2. `to_canonical_bytes()` вызывает `rfc8785.dumps` — **падает с `FloatDomainError: nan is not representable in JCS`** (подтверждено runtime).
3. Файл `forecast.json` в bundle может стать невалидным и нечитаемым загрузчиком.

**Путь атаки:** frontend передаёт в `compose_forecast_json` → sidecar → `compose_forecast_json_bytes` → `ForecastJsonV1` с NaN spend_plan → bundle записан с `json.dumps` (сырой `NaN`-литерал) → последующий `load_forecast_json` падает на `json.JSONDecodeError` при парсинге.

**Подтверждено:**
```python
f = ForecastJsonV1(horizon_weeks=1, weekly_points=[...], spend_plan={"tv": [float("nan")]})
f.to_canonical_bytes()  # FloatDomainError: nan is not representable in JCS
```

**Suggested fix:** добавить `@field_validator("spend_plan", mode="before")` аналогичный `_trajectory_finite` в `RecipientAnchorsPayload` — итерировать по всем каналам и значениям, вызывать `_reject_non_finite`. Либо добавить в `_points_match_horizon` `model_validator(mode="after")` проверку каждого значения `spend_plan`.

---

## HIGH

### H-1 · TypeScript-генератор: новый синтаксис `X | None` (Python 3.10+) → `unknown`

**Файл:** `src/aurora_launch/tools/export_typescript.py` — `_python_type_to_ts()`  
**Категория:** DRY / Reliability  
**Effort:** S

**Описание.**  
Функция `_python_type_to_ts` проверяет `if origin is Union` (из `typing`). Однако `ForecastJsonV1` объявляет поля через new-style Python 3.10+ синтаксис `X | Y`, который производит `types.UnionType` — **не `typing.Union`**. Проверка `origin is Union` возвращает `False`, и функция доходит до fallback `return "unknown"`.

**Подтверждено:**
```python
ForecastJsonV1.model_fields["anchors"].annotation  # types.UnionType
_python_type_to_ts(annotation, {})                 # → "unknown"
```

**Затронутые поля в `aurora-schemas.d.ts`:**
- `ForecastJsonV1.anchors: unknown` (должно быть `RecipientAnchorsPayload | null`)
- `ForecastJsonV1.spend_plan: unknown` (должно быть `Record<string, number[]> | null`)
- `ForecastJsonV1.produced_at: unknown` (должно быть `string | null`)
- `RecipientAnchorsPayload.seasonality: unknown` (должно быть `number[] | null`)
- `BundleManifest.aurora_launch_schema_version: unknown`

Тест `test_b1_typescript_export.py::test_optional_str` использует `Optional[str]` (old-style) → проходит. Новый `str | None` не покрыт — баг не пойман CI.

**Impact:** потеря типовой безопасности в TS при работе с `ForecastJsonV1`. Разработчик не получает TS-ошибку при передаче неверного типа. Особенно критично для `spend_plan`: `unknown` вместо `Record<string, number[]>` скрывает несовместимость форматов до runtime.

**Suggested fix:**
```python
import types as _types_module
# В начале _python_type_to_ts, после вычисления origin:
if origin is Union or isinstance(py_type, _types_module.UnionType):
    args = get_args(py_type)
    ...
```
Добавить тест: `assert _python_type_to_ts(str | None, {}) == "string | null"`.

---

### H-2 · `release.yml`: updater manifest — коллизия `.exe` vs `.msi` для Windows

**Файл:** `.github/workflows/release.yml`, шаг `Compose updater manifest`, строки ~304-315  
**Категория:** Reliability  
**Effort:** S

**Описание.**  
Скрипт сборки манифеста итерирует по `*.sig` файлам и маппит installer к платформе:
```python
if fname.endswith(('.msi', '.exe')):
    key = 'windows-x86_64'
```
Tauri на Windows генерирует **два** installer'а: NSIS (`.exe`) и MSI (`.msi`), оба с `.sig` файлами. Первый обработанный заполняет `platforms["windows-x86_64"]`, второй **молча перезаписывает** его. Порядок `glob.glob` нестабилен — результат недетерминирован.

**Последствия:** авто-апдейтер Tauri может получить MSI вместо NSIS (или наоборот). Tauri автоапдейтер использует NSIS (`.exe`), MSI не поддерживается апдейтером. Если `windows-x86_64` ключ указывает на MSI, **авто-апдейтер Windows сломан**.

**Suggested fix:** в условии для Windows разбить на два отдельных ключа или явно приоритизировать NSIS:
```python
if fname.endswith('.exe') and '-setup' in fname:
    key = 'windows-x86_64'
elif fname.endswith('.msi'):
    key = 'windows-x86_64-msi'  # или пропустить для updater manifest
```
Либо добавить проверку: если `'windows-x86_64'` уже в `platforms` и новый файл — `.msi`, пропустить.

---

### H-3 · `_normalize_legacy_to_v1`: legacy bundle с неизвестным `engine_mode` → ValidationError без user-friendly сообщения

**Файл:** `src/aurora_launch/schemas/forecast_bundle.py` — `_normalize_legacy_to_v1()` и `load_forecast_json()`  
**Категория:** Backwards-compat / Reliability  
**Effort:** S

**Описание.**  
Если legacy bundle содержит `engine_mode` строку, не входящую в текущий `EngineMode` Literal (`"pure_transfer" | "transfer_with_bias_check" | "ols_with_proxy_priors" | "bayesian_with_proxy_priors"`), `_normalize_legacy_to_v1` копирует её as-is, а `ForecastJsonV1.model_validate` падает с `ValidationError` про `literal_error`.

**Подтверждено:**
```python
load_forecast_json(json.dumps({
    "weekly_points": [...], "horizon_weeks": 1, "engine_mode": "old_legacy_mode_v0"
}).encode())
# ValidationError: engine_mode - Input should be 'pure_transfer', ...
```

Пользователь видит raw Pydantic stacktrace, а не понятное сообщение. Сравните: для `version != "1"` сделан явный `raise ValueError(...)` с советом обновить Aurora Launch — отличный паттерн. Для `engine_mode` такой защиты нет.

**Suggested fix:** в `_normalize_legacy_to_v1` добавить:
```python
_KNOWN_ENGINE_MODES = {"pure_transfer", "transfer_with_bias_check", "ols_with_proxy_priors", "bayesian_with_proxy_priors"}
if normalized.get("engine_mode") not in _KNOWN_ENGINE_MODES:
    # unknown legacy mode — degrade gracefully to pure_transfer default
    normalized["engine_mode"] = "pure_transfer"
```
Или залогировать предупреждение + override.

---

## MEDIUM

### M-1 · `detectReproduceMode`: отсутствует проверка `typeof` для не-object значений

**Файл:** `frontend/src/lib/utils/reproduce-mode.ts`  
**Категория:** Reliability  
**Effort:** S

**Описание.**  
Функция проверяет `anchors === null || anchors === undefined`, но TypeScript интерфейс допускает `Record<string, unknown>` — что в runtime JSON может прийти как `string`, `number`, `boolean`, или `array`. Для всех этих значений `anchors !== null && anchors !== undefined` → функция считает anchors валидными объектами и переходит к проверке `spendPlan`.

Если по какой-то причине bundle содержит `"anchors": "corrupted_string"`:
- `typeof anchors === "object"` → `false`, но функция не проверяет это
- `Object.keys(spendPlan)` может вернуть ненулевой массив
- `isReal = true` → передаёт `"corrupted_string"` как `anchors` в `generateReproduceScript`
- sidecar получает строку вместо dict → `RecipientAnchorsPayload.model_validate("corrupted_string")` → сidecar 400-эквивалент, но UX broken

**Suggested fix:**
```typescript
if (anchors === null || anchors === undefined || typeof anchors !== 'object' || Array.isArray(anchors)) {
  return { isReal: false, reason: 'anchors absent or wrong type (legacy bundle)' };
}
```

---

### M-2 · `tools/generate_icons.py`: hardcoded абсолютный Windows-путь как DEFAULT_SOURCE

**Файл:** `tools/generate_icons.py`, строка 37-39  
**Категория:** Reliability / DRY  
**Effort:** S

**Описание.**  
```python
DEFAULT_SOURCE = Path(
    "D:/Docs/Aurora_Ai/06_Aurora_Design_system/05_Logo/Flat/Deliverable/"
    "aurora-deliverable-gold-accent.png"
)
```
Скрипт **завершается с `sys.exit(2)`** если файл не найден (строка 80). В CI этот путь недоступен → `exit 2`. В release pipeline не вызывается напрямую (иконки закоммичены), но:
1. README/onboarding новых разработчиков: запуск без `--source` сразу падает с exit 2, без понятной инструкции где взять мастер-файл.
2. Если CI когда-нибудь добавит иконки в pipeline — немедленный failure.

**Suggested fix:** добавить `--help` текст с инструкцией; либо сделать fallback на placeholder (существующий `src-tauri/icons/128x128.png`), логируя предупреждение что используется placeholder. Путь в `DEFAULT_SOURCE` заменить на `None`, и при `None` — fallback + warning вместо exit 2.

---

### M-3 · `sveltekit-stubs.d.ts`: `goto` stub не включает `state` опцию (SvelteKit 2.x)

**Файл:** `frontend/src/types/sveltekit-stubs.d.ts`, строки 37-40  
**Категория:** Reliability / DRY  
**Effort:** S

**Описание.**  
Текущий stub:
```typescript
export function goto(
  url: string,
  opts?: { replaceState?: boolean; noScroll?: boolean; keepFocus?: boolean }
): Promise<void>;
```
SvelteKit 2.x добавил опцию `state?: Record<string, unknown>` для History API state. Если сейчас или в будущем код использует `goto('/path', { state: { from: 'wizard' } })`:
- TypeScript молча принимает (так как `opts` не проверяет лишние ключи в runtime)
- Но теоретически кто-то мог явно annotate свой код через этот тип

Также отсутствует `invalidateAll?: boolean` как опция `goto` (в реальном SvelteKit это отдельная функция, но некоторые паттерны передают флаги через opts).

**Impact:** LOW-MEDIUM — runtime шим (`vite.config.ts` alias) определяет реальное поведение, stub только для type-check. Но если кто-то использует `state` → TypeScript не предупредит.

**Suggested fix:** добавить `state?: Record<string, unknown>` в опции.

---

### M-4 · `smart-defaults.ts`: два silent `catch {}` без console.warn

**Файл:** `frontend/src/lib/services/smart-defaults.ts`, строки 98, 110  
**Категория:** Reliability / DRY  
**Effort:** S

**Описание.**  
В рамках коммита `01cba2e` ("Silent catches → console.warn") заменено 6 мест в `PatternSuggestionCard`, `DailyInsightBanner`, `daily-insights.ts`, `pattern-matcher.ts`. Однако в `smart-defaults.ts` остались два `catch {}` без логирования:

```typescript
// Строка 98
try { timezone = Intl.DateTimeFormat()...; } catch { /* silent */ }

// Строка 110
try { locale = navigator.language...; } catch { /* silent */ }
```

Эти конкретно — jsdom/SSR окружения, где `Intl` или `navigator` может отсутствовать. Silencing оправдан, **но не соответствует паттерну из коммита** и может скрыть реальные баги в будущих окружениях (например, странный Tauri webview конфиг).

**Suggested fix:** добавить `console.warn('[smart-defaults] timezone/locale fallback:', e)` — те же паттерны что в `daily-insights.ts`.

---

### M-5 · CI: отсутствует gate проверки drift TS-типов (`gen:types`)

**Файлы:** `.github/workflows/test.yml`, `.github/workflows/ci.yml`  
**Категория:** Reliability / DRY  
**Effort:** M

**Описание.**  
`npm run check` (svelte-check) в `test.yml` запускается **без** предварительного `npm run gen:types`. Скрипт `generate-types.mjs` имеет fallback (пишет stub если Python недоступен), но в CI с Python доступным нужно регенерировать и проверять diff.

Если разработчик изменит Pydantic-схему (например, добавит поле в `ForecastJsonV1`) и **не запустит** `npm run gen:types` локально, `aurora-schemas.d.ts` останется стale. CI пропустит это:
- `svelte-check` работает со stale `.d.ts` — не падает
- Frontend code с новым полем получит `undefined` в runtime

**Suggested fix:** в `test.yml` (frontend job) перед `npm run check` добавить:
```yaml
- working-directory: frontend
  run: npm run gen:types
- working-directory: frontend
  run: git diff --exit-code src/lib/types/aurora-schemas.d.ts || (echo "DRIFT: aurora-schemas.d.ts is stale, run npm run gen:types"; exit 1)
```

---

## LOW

### L-1 · `build_sidecar.py`: 10s smoke-test timeout — рискованно для slow CI runners

**Файл:** `tools/build_sidecar.py`, строка 208  
**Категория:** Reliability  
**Effort:** S

**Описание.**  
`proc.communicate(timeout=10)` — 10 секунд. PyInstaller-бинари при первом запуске распаковывают embedded Python (~200-400 MB) во временную директорию. На медленных CI-раннерах (shared GitHub Actions runners с перегрузкой, или Windows с медленным антивирусом) это может занять 15-30+ секунд. В этом случае smoke-тест упадёт с `TimeoutExpired` не потому что бинарь сломан, а потому что медленный диск.

Сам `sidecar-build.yml` использует команду `printf '%s\n' ... | "$BINARY" 2>err.log | grep -m1 '"pong"'` — без явного timeout, но сам `grep -m1` завершается после первой строки, что ограничивает время. Проблема специфична для `build_sidecar.py` (developer tool).

**Suggested fix:** увеличить timeout до 30s (`timeout=30`) или сделать его конфигурируемым через CLI флаг `--smoke-timeout`.

---

### L-2 · `release.yml`: `os.popen('date -u ...')` — deprecated, silent failure

**Файл:** `.github/workflows/release.yml`, строка ~319  
**Категория:** Reliability  
**Effort:** S

**Описание.**  
```python
'pub_date': os.popen('date -u +%Y-%m-%dT%H:%M:%SZ').read().strip(),
```
`os.popen` устарел с Python 3.0 (заменён `subprocess`). При ошибке возвращает пустую строку без exception — тихий failure. Кроме того, это уже вычислено в bash-переменной `PUB_DATE` выше, но Python-скрипт не читает её (она не экспортируется в env для этого подпроцесса).

**Suggested fix:**
```python
import datetime
pub_date = datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
```
Или читать `os.environ.get('PUB_DATE', '')`.

---

### L-3 · `tools/generate_icons.py` и `tools/build_sidecar.py`: нет тестов

**Файлы:** `tools/generate_icons.py`, `tools/build_sidecar.py`  
**Категория:** Test  
**Effort:** M

**Описание.**  
Оба инструмента — pure-Python CLI-скрипты с нетривиальной логикой (`detect_target_triple`, `find_built_binary`, `smoke_test`, логика именования иконок). Ни одного unit-теста. Для `build_sidecar.py` ошибка в `copy_binary` или `detect_target_triple` может привести к некорректному сидекару в релизе — незамеченному до smoke-теста в release pipeline.

**Suggested fix:** минимальные unit-тесты:
- `test_detect_target_triple_windows()` — mock `platform.system() = "Windows"` → assert result == "x86_64-pc-windows-msvc"
- `test_generate_icons_square_crop()` — mock PIL Image, verify crop math
- `test_find_built_binary_with_exe()` — mock `REPO_ROOT / "dist" / "aurora-sidecar.exe"` exists → assert not None

Для tooling это `LOW` — не блокирует релиз, но техдолг.

---

## FALSE-POSITIVE

### FP-1 · `load_forecast_json`: version="2" обрабатывается неверно

**Вывод:** FALSE-POSITIVE. Проверка `elif raw_version != "1": raise ValueError(...)` (строки 224-231) с ясным сообщением реализована. Тест `test_not_a_dict_raises` и `test_invalid_json_raises` покрыты. Pydantic `Literal["1"]` — defence-in-depth. Всё корректно.

---

### FP-2 · NaN/Infinity в `weekly_points` — не валидируется

**Вывод:** FALSE-POSITIVE. `_reject_non_finite` валидатор реализован в `ForecastPoint` (строки 32-42, 113-114). Тесты подтвердили rejection NaN и Infinity. Именно `spend_plan` незащищён (см. B-1).

---

### FP-3 · `build_sidecar.py`: double-run race condition

**Вывод:** FALSE-POSITIVE. `PyInstaller --clean` (строка 148 `build_sidecar.py`) очищает spec-кэш при каждом запуске. `shutil.copy2` атомарно перезаписывает бинарь. Двойной запуск безопасен.

---

### FP-4 · CI: конфликт pip-кэша при матрице Python 3.11/3.12

**Вывод:** FALSE-POSITIVE. `actions/setup-python@v5` с `cache: pip` включает python-version в ключ кэша — стандартное поведение. Матрица 3.11 и 3.12 используют раздельные кэши.

---

### FP-5 · `sveltekit-stubs.d.ts`: `goto` без `invalidateAll`

**Вывод:** FALSE-POSITIVE. В SvelteKit `invalidateAll()` — отдельная функция, не опция `goto`. Стаб включает `export function invalidateAll(): Promise<void>` (строка 45). Всё правильно.

---

## Appendix: что проверено runtime

| Scenario | Result |
|---|---|
| `load_forecast_json` version="2" | Rejected с user-friendly message ✓ |
| `load_forecast_json` version=null | Treated as legacy, normalized ✓ |
| `compose_forecast_json_bytes` NaN in weekly_points | Rejected (ValidationError) ✓ |
| `compose_forecast_json_bytes` Infinity in ci_upper | Rejected (ValidationError) ✓ |
| `compose_forecast_json_bytes` negative horizon_weeks | Rejected ✓ |
| `compose_forecast_json_bytes` NaN in spend_plan | **ACCEPTED** → `to_canonical_bytes` crashes ✗ |
| `_normalize_legacy_to_v1` unknown engine_mode | Passes through → ValidationError ✗ |
| `_python_type_to_ts(str \| None, {})` | Returns "unknown" ✗ |
| `_python_type_to_ts(Optional[str], {})` | Returns "string \| null" ✓ |
| Windows .msi + .exe collision in updater manifest | Both match → non-deterministic overwrite ✗ |
