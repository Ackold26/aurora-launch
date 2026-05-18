# File Reader Port — Optimizer → Launch

**Status:** Design (Phase 0)
**Author:** Маша маленькая (Opus 4.7), assisted by 2 × Sonnet (parallel)
**Date:** 2026-05-18
**Branch target:** `feat/stage1-core-1.1-1.4` (HEAD `354c37c`)
**Backlog ticket:** #7 (per `MEMORY.md` 2026-05-17 architectural note)

---

## 1. Цель и scope

Перенести «приёмник широкой таблицы» из Aurora Econometrica MMM Optimizer в Aurora Econometrica Launch Planner.

**Что меняется в UX:**
- Шаги мастера: 7 → 6 (удаляется отдельный шаг `mapping`).
- На первом шаге пользователь сразу видит превью таблицы (20 строк) + автоматически определённые роли колонок (KPI / реклама / контрольная / дата / не использовать).
- Ошибки автоопределения исправляются выпадающим списком в каждой строке превью.
- Канонические поля Aurora (brand_name / sales_value_rub / channel_name и т.д.) больше не показываются — это пережиток из периода, когда Launch планировал сам разбирать сырые источники DSM/Mediascope. Сейчас это задача Aurora Data Studio.

**Что НЕ меняется:**
- Sidecar IPC contract (JSON-RPC stdio, newline-delimited, `@register` decorator).
- Аутентификация sidecar (auth token).
- Path security (`validate_safe_path` + `_get_allowed_roots`).
- Wizard session autosave/recovery механика.
- Шаги Proxy → Similarity → Anchors → Forecast → Cert (без изменений).

**Что отложено в backlog:**
- Удаление модуля `engines/format_adapters/` (DSM/Mediascope/AdEx адаптеры, ~550 LOC). После port'а они становятся orphan, удаление — отдельным коммитом следующей сессии.

---

## 2. Архитектурное решение (4 ответа от Антона 2026-05-18)

| Вопрос | Решение | Обоснование |
|---|---|---|
| Q1. Шаг `mapping` отдельно или слить | **Слить** | UX 7→6 шагов; mapping — пережиток raw-source эпохи; роль правится в превью |
| Q2. Старый метод `parse_data_file` | **Удалить полностью** | Launch не в продакшн, BC не нужна; `.aurora` bundles используют `import_aurora_bundle`, не `parse_data_file` |
| Q3. Карточка OLS/Bayes из Optimizer | **Не портировать** | Launch не тренирует модель сам |
| Q4. Правка роли колонки | **Выпадающий список в превью** | Привычный Excel-паттерн, доступность с клавиатуры, консистентность с Optimizer |

---

## 3. Новые JSON-RPC методы (sidecar)

Два метода вместо трёх — преобразование «предпросмотр + определение ролей» делается одним вызовом, чтобы избежать race conditions и лишних round-trips.

### 3.1 `analyze_data_file`

Читает файл, возвращает превью первых N строк + автоматически определённые роли колонок.

**Params:**
```json
{
  "path": "/абсолютный/путь/к/файлу.xlsx",
  "n_rows": 20
}
```

**Result:**
```json
{
  "status": "ok",
  "file_name": "Кагоцел_РФ.xlsx",
  "size_kb": 142.6,
  "shape": [156, 12],
  "headers": ["date", "sales_packs", "tv_grp", "olv_impressions", "competitor_share", ...],
  "rows": [["2024-01-07", 142000, 850.2, ...], ...],
  "dtypes": {"date": "datetime64[ns]", "sales_packs": "int64", ...},
  "columns": [
    {"name": "date",              "role": "date",    "confidence": 0.97, "kind": "date"},
    {"name": "sales_packs",       "role": "kpi",     "confidence": 0.85, "kind": "target_count"},
    {"name": "tv_grp",            "role": "media",   "confidence": 0.85, "kind": "physical"},
    {"name": "olv_impressions",   "role": "media",   "confidence": 0.85, "kind": "physical"},
    {"name": "competitor_share",  "role": "control", "confidence": 0.90, "kind": "signed_competitor"}
  ]
}
```

**Error envelope:**
```json
{"status": "error", "message": "Файл не найден: /path/to/file.xlsx"}
```

`status === "error"` → frontend показывает toast + не переходит к следующему шагу. Никаких HTTP кодов — это JSON-RPC внутри sidecar.

**Path security:** `validate_safe_path(path, _get_allowed_roots(), is_write=False)`. На violation — `SidecarSecurityError`.

### 3.2 `validate_wide_table`

Финальная валидация таблицы перед переходом к Proxy. Учитывает user role overrides.

**Params:**
```json
{
  "path": "/абсолютный/путь/к/файлу.xlsx",
  "role_overrides": {
    "competitor_share": "control",
    "some_metric": "unused"
  }
}
```
Поле `role_overrides` опционально (`null` или отсутствует — используются авто-роли).

**Result:**
```json
{
  "status": "ok",
  "verdict": "ГОТОВ К МОДЕЛИРОВАНИЮ",
  "file": {"name": "...", "rows": 156, "cols": 12, "size_kb": 142.6},
  "columns": [/* same shape as analyze_data_file.columns + stats/histogram/adstock_type */],
  "detected": {
    "date": "date",
    "kpi": ["sales_packs"],
    "media": ["tv_grp", "olv_impressions"],
    "control": ["competitor_share"],
    "n_predictors": 3,
    "ratio": 52.0,
    "date_frequency": "weekly"
  },
  "available_kpi_types": ["sales_packs", "leads", "registrations", "loyalty_cards", "subscriptions", "app_installs", "count_custom"],
  "issues": [],
  "warnings": [{"type": "short_period", "message": "...", "severity": "warning"}],
  "high_correlations": [],
  "full_correlation_matrix": {"labels": [...], "matrix": [[...]]}
}
```

`status` ∈ {`ok`, `warning`, `error`}; `verdict` — русский текст из Optimizer (`ГОТОВ К МОДЕЛИРОВАНИЮ` / `ГОТОВ К МОДЕЛИРОВАНИЮ (с оговорками)` / `ТРЕБУЕТ ДОРАБОТКИ`).

---

## 4. Изменения по слоям

### 4.1 Python sidecar

**Новые файлы:**

1. `src/aurora_launch/utils/__init__.py` — пусто.
2. `src/aurora_launch/utils/column_detection.py` — копия из Optimizer (`Dev/Aurora_Econometrica/sidecar/econometrica/utils/column_detection.py`, 831 LOC). Минимально нужна функция `classify_column(name: str) -> ColumnKind`. **Берём весь файл целиком** — он самодостаточен, не зависит от Econometrica-specific модулей.
3. `src/aurora_launch/engines/validator.py` — port из Optimizer (`Dev/Aurora_Econometrica/sidecar/econometrica/engines/validator.py`, 549 LOC). Изменения при port:
   - Import statement: `from aurora_launch.utils.column_detection import classify_column` вместо `from utils.column_detection import classify_column`.
   - Никаких других правок не требуется — функции pure (нет I/O state, нет глобальных синглтонов).
4. `src/aurora_launch/sidecar/methods_validation.py` — новый модуль с двумя `@register` handler'ами (схемы выше).

**Содержимое `methods_validation.py` (skeleton, ~120 LOC):**

```python
"""Validation method handlers — JSON-RPC dispatch для file analysis.

Phase: file reader port (2026-05-18).

Methods:
- analyze_data_file: preview + auto-detected column roles
- validate_wide_table: full validation with role overrides
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from aurora_launch.sidecar.methods import (
    SidecarSecurityError,
    _get_allowed_roots,
)


def register(name: str):
    from aurora_launch.sidecar.methods import register as _register
    return _register(name)


@register("analyze_data_file")
def _analyze_data_file(params: dict[str, Any]) -> dict[str, Any]:
    """Preview file + auto-detect column roles."""
    from aurora_launch.engines.path_security import (
        PathSecurityError,
        validate_safe_path,
    )
    from aurora_launch.engines.validator import (
        data_preview,
        detect_column_role_with_confidence,
    )
    from aurora_launch.utils.column_detection import classify_column

    path_raw = str(params.get("path", "")).strip()
    if not path_raw:
        raise ValueError("path must be non-empty")
    n_rows = int(params.get("n_rows", 20))

    try:
        path = validate_safe_path(Path(path_raw), _get_allowed_roots(), is_write=False)
    except PathSecurityError as e:
        raise SidecarSecurityError(str(e)) from e

    preview = data_preview(str(path), n_rows=n_rows)
    if preview.get("status") != "ok":
        return preview  # error envelope passes through

    columns = []
    for name in preview["headers"]:
        role, confidence = detect_column_role_with_confidence(name)
        kind = classify_column(name)
        columns.append({
            "name": name,
            "role": role,
            "confidence": confidence,
            "kind": kind,
        })

    return {**preview, "columns": columns}


@register("validate_wide_table")
def _validate_wide_table(params: dict[str, Any]) -> dict[str, Any]:
    """Full validation with optional role overrides."""
    from aurora_launch.engines.path_security import (
        PathSecurityError,
        validate_safe_path,
    )
    from aurora_launch.engines.validator import validate_data

    path_raw = str(params.get("path", "")).strip()
    if not path_raw:
        raise ValueError("path must be non-empty")
    role_overrides = params.get("role_overrides") or {}
    if not isinstance(role_overrides, dict):
        raise ValueError("role_overrides must be a dict or null")

    try:
        path = validate_safe_path(Path(path_raw), _get_allowed_roots(), is_write=False)
    except PathSecurityError as e:
        raise SidecarSecurityError(str(e)) from e

    result = validate_data(str(path))

    # Apply role overrides if provided. Mutate columns + recompute detected lists.
    if role_overrides and result.get("status") != "error":
        for col_info in result.get("columns", []):
            if col_info["name"] in role_overrides:
                col_info["role"] = role_overrides[col_info["name"]]
                col_info["confidence"] = 1.0  # user override = max confidence
        # Recompute detected lists
        detected = {"date": None, "kpi": [], "media": [], "control": []}
        for col_info in result.get("columns", []):
            role = col_info["role"]
            name = col_info["name"]
            if role == "date":
                detected["date"] = name
            elif role == "kpi":
                detected["kpi"].append(name)
            elif role == "media":
                detected["media"].append(name)
            elif role == "control":
                detected["control"].append(name)
        n_pred = len(detected["media"]) + len(detected["control"])
        detected["n_predictors"] = n_pred
        detected["ratio"] = round(result["file"]["rows"] / max(n_pred, 1), 1)
        detected["date_frequency"] = result.get("detected", {}).get("date_frequency", "unknown")
        result["detected"] = detected

    return result
```

**Регистрация модуля в `methods.py`:**

Добавить `import aurora_launch.sidecar.methods_validation  # noqa: E402, F401` в блок late imports (после строки 678 в `methods.py`).

**Удалить из `methods_project.py`:**
- `parse_data_file` handler (строки 638–686).
- `_CANONICAL_FIELDS_REGISTRY` (строки 611–635).
- `UnsupportedFormatError` class (строки 603–604).

**Удалить из `methods.py`:**
- Re-export `from aurora_launch.sidecar.methods_project import UnsupportedFormatError` (строка 682).

**Pydantic schemas:**

`src/aurora_launch/schemas/wizard_session.py`:

- `WizardStep` Literal: убрать `"mapping"`.
  ```python
  WizardStep = Literal["import", "proxy", "similarity", "anchors", "forecast", "cert"]
  ```
- `step` field bound: `Field(ge=0, le=5, default=0)`.
- Удалить класс `ColumnMapping` целиком.
- Удалить поля `column_mapping`, `mapping_done`.
- Добавить класс `ColumnRoleAssignment`:
  ```python
  class ColumnRoleAssignment(BaseModel):
      """Роль колонки + флаг ручного override (после user правки в превью)."""
      model_config = _FROZEN

      name: str = Field(min_length=1)
      role: Literal["kpi", "media", "control", "date", "unused", "unknown"]
      confidence: float = Field(ge=0.0, le=1.0)
      auto_detected: bool = True
  ```
- Добавить поля в `WizardSession`:
  ```python
  # Step 0 (import): roles assigned after analyze_data_file
  column_roles: list[ColumnRoleAssignment] = Field(default_factory=list)
  validation_done: bool = False
  ```

**Migration `wizard_session_load`:**

`methods_project.py:_wizard_session_load` — обернуть `db.kv_get(...)` так, чтобы при `ValidationError` (старая shape) возвращать `{"session": None}` + log warning. Sonnet 1a реализует через try/except внутри handler.

**Удалить файлы:**
- `tests/test_parse_data_file_column_mapping.py`

**Добавить pytest:**
- `tests/test_validator.py` (port + adapt minimal версии из Optimizer `test_validator_available_kpi_types.py`).
- `tests/test_methods_validation.py` — integration через `dispatch("analyze_data_file", ...)` и `dispatch("validate_wide_table", ...)` с tmp_path xlsx fixture.

### 4.2 Rust commands

`src-tauri/src/commands/adapters.rs` — переименовать в `validation.rs` (или оставить `adapters.rs` — semantically теперь не «адаптеры», но это меньшая рефакторинг-цена; **оставляем `adapters.rs`** ради минимального diff).

**Удалить:**
- `ParseDataFileInput`, `ParseDataFileResult` structs.
- `parse_data_file` command.
- `AdapterInfo` struct.
- `list_adapters` command.

**Добавить:**
```rust
#[derive(Serialize, Deserialize, Debug)]
pub struct AnalyzeDataFileInput {
    pub path: String,
    pub n_rows: Option<u32>,
}

#[tauri::command]
pub async fn analyze_data_file(
    sidecar: State<'_, Arc<SidecarManager>>,
    input: AnalyzeDataFileInput,
) -> AuroraResult<serde_json::Value> {
    sidecar.invoke("analyze_data_file", serde_json::json!({
        "path": input.path,
        "n_rows": input.n_rows.unwrap_or(20),
    })).await
}

#[derive(Serialize, Deserialize, Debug)]
pub struct ValidateWideTableInput {
    pub path: String,
    pub role_overrides: Option<std::collections::BTreeMap<String, String>>,
}

#[tauri::command]
pub async fn validate_wide_table(
    sidecar: State<'_, Arc<SidecarManager>>,
    input: ValidateWideTableInput,
) -> AuroraResult<serde_json::Value> {
    let mut params = serde_json::json!({"path": input.path});
    if let Some(overrides) = input.role_overrides {
        params["role_overrides"] = serde_json::to_value(overrides).unwrap();
    }
    sidecar.invoke("validate_wide_table", params).await
}
```

Возврат `serde_json::Value` сознательно — не дублируем shape в Rust, TS получает свою типизацию через generated schemas. Альтернатива (полные Rust struct'ы) — overkill для двух методов; если pattern приживётся в продукте, рефакторить можно позже.

`src-tauri/src/lib.rs` — в `invoke_handler`:
- Удалить `parse_data_file`, `list_adapters`.
- Добавить `analyze_data_file`, `validate_wide_table`.

### 4.3 TypeScript client + UI

**`frontend/src/lib/ipc/client.ts`:**

Удалить:
- `ParseDataFileInput`, `ParseDataFileResult` interfaces.
- `CanonicalFieldRegistryEntry`, `AdapterInfo` interfaces.
- `ipc.parseDataFile`, `ipc.listAdapters` методы.

Добавить:
```ts
export type ColumnRole = 'kpi' | 'media' | 'control' | 'date' | 'unused' | 'unknown';

export interface ColumnAssignment {
  name: string;
  role: ColumnRole;
  confidence: number;
  kind: string;
}

export interface AnalyzeDataFileInput {
  path: string;
  n_rows?: number;
}

export interface AnalyzeDataFileResult {
  status: 'ok' | 'error';
  message?: string;
  file_name?: string;
  size_kb?: number;
  shape?: [number, number];
  headers?: string[];
  rows?: Array<Array<string | number | null>>;
  dtypes?: Record<string, string>;
  columns?: ColumnAssignment[];
}

export interface ValidateWideTableInput {
  path: string;
  role_overrides?: Record<string, ColumnRole>;
}

export interface WideTableValidationResult {
  status: 'ok' | 'warning' | 'error';
  verdict?: string;
  message?: string;
  file?: { name: string; rows: number; cols: number; size_kb: number };
  columns?: Array<ColumnAssignment & { dtype?: string; stats?: Record<string, number>; histogram?: { counts: number[]; edges: number[] }; adstock_type?: string; date_stats?: Record<string, unknown> }>;
  detected?: {
    date: string | null;
    kpi: string[];
    media: string[];
    control: string[];
    n_predictors: number;
    ratio: number;
    date_frequency: string;
  };
  available_kpi_types?: string[];
  issues?: Array<{ type: string; message: string; severity: string }>;
  warnings?: Array<{ type: string; message: string; severity: string }>;
  high_correlations?: Array<{ col1: string; col2: string; correlation: number; risk: string }>;
  full_correlation_matrix?: { labels: string[]; matrix: number[][] };
}

// внутри ipc object:
analyzeDataFile: (input: AnalyzeDataFileInput) =>
  invoke<AnalyzeDataFileResult>('analyze_data_file', { input }),
validateWideTable: (input: ValidateWideTableInput) =>
  invoke<WideTableValidationResult>('validate_wide_table', { input }),
```

**Новый компонент `frontend/src/lib/components/DataPreviewTable.svelte`** (~180 LOC):

Props:
```ts
interface Props {
  headers: readonly string[];
  rows: ReadonlyArray<ReadonlyArray<string | number | null>>;
  dtypes: Readonly<Record<string, string>>;
  /** Bindable: текущие role assignments. Key = column name. */
  roleAssignments: Map<string, ColumnAssignment>;
}
```

Render:
- Заголовок «Обнаружено колонок: N · Строк данных: M · Размер: K КБ».
- Таблица с горизонтальной прокруткой:
  - Header row: имя колонки.
  - Role row (sticky): выпадающий список + цветной dot (зелёный/синий/серый/фиолетовый/тёмно-серый по role) + бэдж «авто» если confidence < 0.9 и `auto_detected = true`.
  - 20 data rows (или сколько пришло).
- `aria-label={`Роль колонки ${name}`}` на каждом select.
- Update Map при onchange — Map reassign (Svelte 5 reactivity).

Опции выпадающего списка (i18n keys):
- `kpi` → «Целевая (KPI)»
- `media` → «Реклама»
- `control` → «Контрольная»
- `date` → «Дата»
- `unused` → «Не использовать»
- `unknown` → «(не определена)» (отображается только если backend вернул `unknown` и user не правил)

**`frontend/src/routes/wizard/+page.svelte` изменения:**

1. STEPS array:
   ```ts
   const STEPS = ['import', 'proxy', 'similarity', 'anchors', 'forecast', 'cert'] as const;
   ```
2. Удалить state:
   - `sourceColumns`, `suggestedMapping`, `previewRows`, `columnMapping`, `mappingDone`.
3. Добавить state:
   - `previewHeaders: string[]`
   - `previewRows: Array<Array<string | number | null>>` (другой формат — массив массивов, не объектов; имя совпадает с локальной переменной — переименовать осторожно)
   - `previewDtypes: Record<string, string>`
   - `previewShape: [number, number] | null`
   - `previewFileName: string | null`
   - `previewSizeKb: number | null`
   - `roleAssignments: Map<string, ColumnAssignment>`
   - `validationDone: boolean`
4. `pickImport()` — заменить вызов `ipc.parseDataFile` на `ipc.analyzeDataFile`. После success наполнить state + сохранить в `wizardSession`.
5. Удалить блок `{:else if step === 1}` (mapping шаг). Сдвинуть индексы блоков proxy/similarity/anchors/forecast/cert: было `step === 2..6`, станет `step === 1..5`.
6. На шаге `step === 0` после загрузки файла под кнопкой выбора файла рендерить `<DataPreviewTable />`.
7. Импорт `ColumnMappingTable` — удалить.
8. Импорт `autoMapColumns` — удалить.
9. `persistCurrentStep()` — убрать `s.column_mapping`, `s.mapping_done`. Добавить:
   ```ts
   s.column_roles = Array.from(roleAssignments.values());
   s.validation_done = validationDone;
   ```
10. `applyRecoveredSession()` — заменить восстановление mapping на восстановление roleAssignments.

**`frontend/src/lib/stores/wizardSession.svelte.ts`:**

`makeBlankSession()` — заменить `column_mapping: []` + `mapping_done: false` на `column_roles: []` + `validation_done: false`.

**Удалить файлы:**
- `frontend/src/lib/components/ColumnMappingTable.svelte`
- `frontend/src/lib/utils/auto_map_columns.ts`
- `frontend/tests/unit/auto_map_columns.test.ts`
- `frontend/tests/unit/ColumnMappingTable.test.ts`

**`frontend/src/lib/i18n/locales/ru.json` изменения:**

Удалить:
- `wizard.step.mapping`

Изменить:
- `wizard.step.import`: "Импорт данных" → "Импорт и роли колонок" (опционально — можно оставить старый, Антон не возражал; **реко: оставить как есть**, в самом UI поясним «Aurora определила роли — поправьте при необходимости»).

Добавить:
```json
"wizard.import.preview.title": "Предпросмотр данных",
"wizard.import.preview.summary": "Найдено колонок: {cols} · Строк: {rows} · Размер: {sizeKb} КБ",
"wizard.import.preview.hint": "Aurora определила роль каждой колонки автоматически. Поправьте при необходимости — данные не сохраняются, пока вы не нажмёте «Далее».",
"wizard.import.role.kpi": "Целевая (KPI)",
"wizard.import.role.media": "Реклама",
"wizard.import.role.control": "Контрольная",
"wizard.import.role.date": "Дата",
"wizard.import.role.unused": "Не использовать",
"wizard.import.role.unknown": "(не определена)",
"wizard.import.role.dropdown_aria": "Роль колонки {name}",
"wizard.import.role.auto_badge": "авто",
"wizard.import.validation.warning_title": "Проверьте предупреждения",
"wizard.import.validation.error_title": "Требуется доработка",
"wizard.import.validation.no_date": "Не найдена колонка с датами",
"wizard.import.validation.no_kpi": "Не найдена целевая колонка",
"wizard.import.validation.no_media": "Не найдены рекламные колонки",
"wizard.import.validation.insufficient_data": "Данных слишком мало для модели",
"wizard.import.empty_hint": "Выберите файл XLSX или CSV — Aurora автоматически определит структуру."
```

Английский `en.json` обновить симметрично (Sonnet 1b переведёт с помощью контекста, проверю на аудите).

**`frontend/tests/e2e/_helpers/mock-ipc.ts`:**

- Удалить mock для `parse_data_file` и `list_adapters`.
- Добавить mock для `analyze_data_file` (возвращает sample preview из 3-4 колонок: date / sales_packs / tv_grp / competitor_share).
- Добавить mock для `validate_wide_table` (возвращает status=ok).

**`frontend/tests/e2e/wizard-happy-path.spec.ts`:**

- Тест «renders all 7 steps»: 7 → 6.
- Удалить тест «Step 1 — empty mapping hint visible without import».
- Заменить на тест «Step 0 — DataPreviewTable renders after import» (mock pickImport → assert role dropdown visible).
- Скорректировать `for` циклы навигации (на 1 меньше шагов до Proxy/Similarity/Anchors).

**`frontend/tests/e2e/wizard.a11y.spec.ts`:**

- Скорректировать счётчик шагов 7 → 6.
- Удалить a11y assertion'ы на `ColumnMappingTable`.

---

## 5. Стратегия коммитов

| # | Кто | Что | Размер |
|---|---|---|---|
| 1 | Sonnet 1a | port `validator.py` + `column_detection.py` + `methods_validation.py` + pytest, register module | ~1100 LOC new code + 80 LOC delete |
| 2 | Sonnet 1b | новый `DataPreviewTable.svelte`, перепил `wizard/+page.svelte`, новые `ipc.client.ts` методы, удаление `ColumnMappingTable`/`auto_map_columns`, i18n updates | ~500 LOC new, ~400 LOC delete |
| 3 | Я (Opus) | Pydantic `wizard_session.py` migration + Rust commands wiring + lib.rs invoke_handler + e2e mock-ipc/wizard-happy-path/a11y updates + svelte-check fix + integration smoke run | ~200 LOC change |

Phase 2 audit gate (я) — последняя проверка перед push:
- Sonnet'ы выполнили задачи по design doc'у точно (file:line check)?
- Соответствие IPC контрактам (request/response shape)?
- pytest + vitest + svelte-check + Playwright все зелёные?
- Manual smoke: загрузить sample wide table из Optimizer (Kagocel xlsx) → пройти Import + Proxy step → assert роли определены корректно.

После audit — один cumulative push к `origin`.

---

## 6. Что НЕ удаляем сейчас (orphan backlog)

`src/aurora_launch/engines/format_adapters/` (6 файлов, ~550 LOC):
- `registry.py` (87 LOC)
- `dsm_v2023.py`, `dsm_v2024.py` (~176), `dsm_v2025.py`
- `mediascope_adex.py` (104), `mediascope_tv_index.py`
- `__init__.py`

После удаления `parse_data_file` единственным потребителем был именно он. Эти файлы становятся orphan. Удаление — **отдельный коммит следующей сессии**, чтобы:
- Текущая port-серия осталась атомарной и быстро ревьюабельной.
- Если выяснится зависимость от adapter'а где-то ещё (тесты, документация) — фикс будет локализован.
- Adapter тесты в `tests/` (если есть) — отдельная проверка.

Sonnet'ы оставляют `format_adapters/` в покое.

---

## 7. Open risks

1. **WizardSession draft с старой shape** в существующих installer'ах → `wizard_session_load` должен ловить `ValidationError` и возвращать `null` без crash. Sonnet 1a реализует.
2. **TypeScript regeneration:** `npm run gen:types` пишется на Windows c cp1251 → Unicode trap (см. `feedback_windows_cp1251_unicode_traps.md`). Если Sonnet 1a меняет Pydantic, регенерацию делаю я с `PYTHONIOENCODING=utf-8`.
3. **Parallel Sonnet'ы и shared `+layout.svelte` / `i18n/ru.json` / `client.ts`** (см. `feedback_parallel_sonnet_shared_file_collision.md`): `client.ts` и `ru.json` правит **только Sonnet 1b**. Sonnet 1a их не трогает. Контракт зафиксирован в брифах.
4. **Pickle при тренировке модели** (INV-23a, INV-36) — к этой задаче не относится, Launch не тренирует.
5. **Path security** — оба новых метода обязательно идут через `validate_safe_path`. Sample data из Optimizer лежит в `AURORA_SAMPLE_DATA_DIR`; если этот корень не в `_get_allowed_roots()` — добавить в Phase 2 audit.

---

## 8. Файловый inventory

### Создаются
- `src/aurora_launch/utils/__init__.py`
- `src/aurora_launch/utils/column_detection.py` (port из Optimizer)
- `src/aurora_launch/engines/validator.py` (port из Optimizer)
- `src/aurora_launch/sidecar/methods_validation.py`
- `tests/test_validator.py`
- `tests/test_methods_validation.py`
- `frontend/src/lib/components/DataPreviewTable.svelte`
- `frontend/tests/unit/DataPreviewTable.test.ts`

### Модифицируются
- `src/aurora_launch/sidecar/methods.py` (late import)
- `src/aurora_launch/sidecar/methods_project.py` (удалить `parse_data_file`, `_CANONICAL_FIELDS_REGISTRY`, `UnsupportedFormatError`; добавить try/except в `_wizard_session_load`)
- `src/aurora_launch/schemas/wizard_session.py` (Step Literal, ColumnRoleAssignment, поля)
- `src-tauri/src/commands/adapters.rs` (delete + add commands)
- `src-tauri/src/lib.rs` (invoke_handler register)
- `frontend/src/lib/ipc/client.ts` (delete + add methods + types)
- `frontend/src/routes/wizard/+page.svelte` (STEPS, state, pickImport, render)
- `frontend/src/lib/stores/wizardSession.svelte.ts` (makeBlankSession)
- `frontend/src/lib/i18n/locales/ru.json` (delete `wizard.step.mapping`, add new keys)
- `frontend/src/lib/i18n/locales/en.json` (зеркально)
- `frontend/tests/e2e/_helpers/mock-ipc.ts` (replace mocks)
- `frontend/tests/e2e/wizard-happy-path.spec.ts` (6 шагов, новые asserts)
- `frontend/tests/e2e/wizard.a11y.spec.ts` (6 шагов)

### Удаляются
- `src/aurora_launch/sidecar/methods_project.py::parse_data_file` (handler + registry + UnsupportedFormatError)
- `frontend/src/lib/components/ColumnMappingTable.svelte`
- `frontend/src/lib/utils/auto_map_columns.ts`
- `frontend/tests/unit/auto_map_columns.test.ts`
- `frontend/tests/unit/ColumnMappingTable.test.ts`
- `tests/test_parse_data_file_column_mapping.py`

### НЕ трогаются (orphan backlog следующей сессии)
- `src/aurora_launch/engines/format_adapters/` (всё содержимое)

---

## 9. Acceptance criteria (Phase 2 audit)

- [ ] pytest всего sidecar пакета — зелёные.
- [ ] vitest unit — зелёные.
- [ ] svelte-check — 0 errors (новые компоненты не привнесли регрессий).
- [ ] Playwright `wizard-happy-path` + `wizard.a11y` — зелёные.
- [ ] `npm run gen:types` без ошибок (TypeScript regeneration после Pydantic правок).
- [ ] Manual smoke на sample xlsx: load → preview видна → роли назначены автоматически → role override через dropdown работает → Validate проходит → переход к Proxy → recovery dialog после reload восстанавливает roleAssignments.
- [ ] Никаких упоминаний `parse_data_file`, `ColumnMappingTable`, `auto_map_columns`, `column_mapping`, `mapping_done` вне CC-Sessions/04_Sprints/03_Architecture (исторические).
