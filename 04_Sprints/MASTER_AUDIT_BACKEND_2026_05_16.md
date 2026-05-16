# MASTER AUDIT — Backend + DevOps + Performance
**Aurora Launch Planner** | ветка `feat/stage1-core-1.1-1.4` | HEAD `21e693e`  
**Дата:** 2026-05-16  
**Аудиторы:** CTO + Staff Software Architect + DevOps Architect + Performance Engineer (Claude Sonnet 4.6 autonomous)  
**Scope:** Python sidecar + Rust shell + CI/CD + Build infrastructure + Tests  
**Предварительно прочитаны:** STAGE1_AUDIT, STAGE2_AUDIT, STAGE3_4_FINAL_AUDIT — дублирование исключено.

---

## 1. Executive Summary

### Top-3 Critical Concerns

**1. Module-level `_cancel_event` в `LaunchOrchestrator` — race condition при параллельных forecast вызовах (Critical)**  
`launch_orchestrator.py:32` содержит единственный `_cancel_event: threading.Event = threading.Event()` на уровне модуля. Когда `budget_optimizer.py` запускает N параллельных `forecast_fn(spend_plan)` (в одном треде последовательно, но в будущем — параллельно), или когда два forecast-треда стартуют почти одновременно, `_cancel_event.clear()` в одном вызове `forecast_recipient()` сбрасывает флаг активного watchdog-а другого вызова. Это приводит к тому, что один forecast отменяет watchdog другого — budget optimizer может зависнуть или получить неверный результат.

**2. `ProjectDB.set_current_version()` — пропущен `_write_lock` (High)**  
Метод `set_current_version()` выполняет `UPDATE projects SET current_version_id...` через `_tx()` без предварительного `with self._write_lock`. Все остальные write-методы (`create_project`, `save_version`, `delete_project`, `_update_gc_metadata`) корректно захватывают lock. Эта аномалия допускает race condition при concurrent revert + GC или revert + save_version — возможна повреждение HEAD pointer проекта.

**3. `_optimize_threads` / `_optimize_cancel_flags` не дренируются при `shutdown` (High)**  
`_shutdown()` handler дренирует `_forecast_threads` и `_integrity_threads`, но полностью игнорирует `_optimize_threads` и `_optimize_cancel_flags`. При shutdown с активным `optimize_budget` задание продолжает выполнение (N forecast-итераций), удерживая CPU и не получая сигнал отмены. Тред daemon=True, поэтому Python завершится — но budget optimizer в этот момент может держать открытый SQLite writer lock (через ProjectDB), блокируя WAL checkpoint при следующем запуске.

### Три «уже хорошо»

1. **DI ServiceContainer** — чистая архитектура с per-slot locks, двойная проверка (`get_project_db` → DI → fallback), корректная test isolation через `reset_services_for_testing`. Лучше среднего по индустрии для sidecar процессов.
2. **WAL + write_lock на ProjectDB** — правильное сочетание: `check_same_thread=False` для concurrent readers + `_write_lock` для serialized writers. GC thread теперь идёт через `_resolve_db()` (исправление из Stage 2 audit).
3. **Release pipeline** — updater pubkey substitution step добавлен (Stage 2 B-1 fix), smoke test перед upload, SHA-pinned community actions, per-job least-privilege permissions. Зрелость CI для пилотной стадии.

### Общая оценка: ★★★½ (3.5/5)

Зрелый каркас, правильные паттерны для большинства threading/DI задач. Три серьёзные дыры в новом коде этой сессии + системная слабость: 2300-строчный god module без признаков разбивки.

---

## 2. Architecture Issues

| # | Severity | Категория | Описание | Файл:строка | Impact | Fix complexity |
|---|---|---|---|---|---|---|
| A-01 | **Critical** | Thread-safety | Module-level `_cancel_event` разделяется между всеми вызовами `LaunchOrchestrator.forecast_recipient()` — watchdog одного вызова может быть сброшен другим | `launch_orchestrator.py:32,187` | Budget optimizer получает неверные результаты; watchdog не срабатывает при реальном зависании | S |
| A-02 | **High** | Thread-safety | `set_current_version()` не захватывает `_write_lock` — аномалия среди всех write-методов | `project_db.py:702-722` | Race condition при concurrent revert + GC → HEAD pointer corruption | S |
| A-03 | **High** | Lifecycle | `_optimize_threads` / `_optimize_cancel_flags` не дренируются в `shutdown()` | `methods.py:1903-2015` | Budget optimizer на момент shutdown удерживает CPU + потенциально SQLite lock | S |
| A-04 | **High** | Missing API | `ProjectDB` не имеет методов `kv_get` / `kv_set` — `ConsentManager` вызывает их через `_DbKvShim`, который перехватывает все `Exception` и молча возвращает `None` | `methods.py:2217-2242`, `project_db.py` | Consent setting никогда не сохраняется в БД — всегда хранится только в памяти процесса | M |
| A-05 | **Medium** | God module | `methods.py` = 2346 строк, ~35 registered методов, 8+ threading dicts, смешивает: dispatch, singletons, DI, lifecycle, domain logic | `methods.py:1-2346` | Любое изменение в файле требует понимания всего контекста; merge conflicts гарантированы на 3+ devs | L |
| A-06 | **Medium** | Global state | `_cancel_event` + `_cancel_flags` + `_forecast_threads` + `_integrity_threads` + `_optimize_threads` — пять разных threading dict/event без общего registry | `methods.py:64-68, 2021-2022` | Новые типы background tasks (будущий cloud sync) добавят шестой set; shutdown drain нужно обновлять вручную | M |
| A-07 | **Medium** | POSSIBLE DI leak | `ServiceContainer.clear()` не закрывает `ProjectDB` (только обнуляет ссылку) — документировано как WARNING в коде, но shutdown вызывает `clear()` ПОСЛЕ `_PROJECT_DB.close()` через глобальный lock. Безопасен в текущем коде, хрупкий при рефакторинге | `services.py:115-128` | Если порядок shutdown поменяется → ProjectDB закрывается без `close()` → WAL checkpoint не сброшен | S (убедиться) |
| A-08 | **Medium** | Missing index | SQL в `list_projects()` делает correlated subquery `COUNT(*) FROM versions WHERE project_uuid = ?` для каждого проекта. При 1000 проектов = 1001 SQL операция | `project_db.py:322-342` | N+1 pattern: при x100 нагрузке (100 проектов с 100 версиями) list может занять >1с | M |
| A-09 | **Medium** | Missing index | `check_integrity()` вызывает `blob_store.list_all()` — итерация всего filesystem blob directory. При 10k+ блобов = тысячи `os.scandir` вызовов блокируют sidecar thread | `project_db.py:858` | При x100 нагрузке (10k блобов) integrity check занимает десятки секунд | M |
| A-10 | **Medium** | Thread isolation | `LaunchOrchestrator()` создаётся заново в каждом runner() треде budget optimizer (строка 2108). Но `_cancel_event` — module-level. При N concurrent optimizer calls (N orchestrators, 1 cancel_event) первый `.clear()` сбрасывает watchdog остальных | `methods.py:2108`, `launch_orchestrator.py:32` | Дублирует A-01, усугубляет: каждый budget split-eval конкурирует за один event | |
| A-11 | **Low** | Autosave gap | Autosave файлы (.autosave.json) хранятся незашифрованными рядом с зашифрованной ProjectDB. Если DB-файл украден отдельно — данные защищены; если папка целиком — autosave утекает в plaintext | `autosave.py`, `methods.py:165` | PII exposure (имена проектов, рабочие состояния wizard) при физическом доступе | M |
| A-12 | **Low** | Cyclic dep risk | `methods.py` импортирует `services.py` (OK), `services.py` не импортирует `methods.py` (OK — через callback). Но `_DbKvShim` определён inline в `methods.py:2217` — это domain logic внутри dispatch layer. Нарушает SRP. | `methods.py:2217-2241` | Tech debt: `ConsentManager` store interface нужно переместить в `persistence/` | S |

---

## 3. Performance Bottleneck Map

### При x10 нагрузке (10 проектов, 10k weekly_actuals)

| Компонент | Ожидаемое поведение | Bottleneck |
|---|---|---|
| `list_projects()` | ~10ms (N+1 SQL, но мало данных) | Начинает ощущаться |
| `check_data_source_updates()` | <100ms (scan папок) | Нет — `DataSourceWatcher` правильно ограничен `_MAX_FOLDER_SCAN_FILES=5000` |
| Budget optimizer (n=500) | 30-90с | Последовательные forecast evals, нет прогресс-событий — UI слепой |
| GC thread | <1с (7-дневный интервал) | Нет проблем |
| Blob integrity check | ~500ms (1k блобов) | Начинает ощущаться при scan |

### При x100 нагрузке (100 проектов, 100k weekly_actuals)

| Компонент | Прогнозируемое поведение | Что сломается первым |
|---|---|---|
| `list_projects()` | 500ms-2s из-за N+1 correlated subquery | **Первым** — sidecar RPC timeout видим из Rust |
| `check_integrity()` | 30-60с (10k+ блобов filesystem scan) | **Вторым** — блокирует sidecar на всё время scan (synchronous) |
| Budget optimizer (n=500, 5+ channels) | Random search: 500 × forecast × 5ch = неуправляемо | **Третьим** — без timeout UI зависает навсегда |
| SQLite WAL при concurrent save_version + GC | Latency spikes 100-500ms | Возможна lock contention при x100 write frequency |
| PyInstaller binary cold start | ~2-4с (112 MB binary, Windows AV scan) | Startup regression при heavy imports в `__init__` |

### Cold start latency

- PyInstaller binary: ~2-4с на HDD Windows (AV scan + decompress Python runtime)
- На SSD: ~0.5-1.5с
- Bench gate: 2с для Python import (корректно). **Но bench не тестирует binary cold start** — только `import aurora_launch`.
- `bench.yml` тестирует только `ubuntu-22.04`, нет Windows gate где latency выше.

---

## 4. DevOps Risks + Improvements

### 4.1 Критические

| # | Severity | Описание | Файл | Fix |
|---|---|---|---|---|
| D-01 | **High** | `tools/bench_pilot_flow.py` существует, но `bench.yml` не проверяет **реальный** binary cold start — только Python import time. Эти числа разные на порядок (import ~300ms, binary spawn 2-4с) | `bench.yml:50-66` | Добавить отдельный job с PyInstaller binary spawn timing |
| D-02 | **High** | `ci.yml` комментирует Rust jobs: `# TODO(block-2): Add Tauri/Rust build jobs here` — Rust cargo check/test НЕ запускается в основном CI, только в `test.yml`. `test.yml` запускает `cargo check` но без `cargo test` на Windows/macOS | `ci.yml:169-187` | Rust jobs активированы в test.yml, но ci.yml продолжает нести obsolete TODO комментарий — misleading |
| D-03 | **Medium** | `sidecar-build.yml` запускает только 2 теста (`test_sidecar_auth.py`, `test_sidecar_protocol_server.py`) перед build — не весь suite. Broken sidecar logic может попасть в binary | `sidecar-build.yml:86` | Запускать полный `pytest` перед build, не subset |
| D-04 | **Medium** | Release pipeline не проверяет **версию PyInstaller** между sidecar-build.yml и release.yml — у них разные install sequences. Рассинхронизация версий PyInstaller может дать разные binaries | `release.yml:136`, `sidecar-build.yml:93` | Pinned `pyinstaller==X.Y.Z` в обоих местах |
| D-05 | **Medium** | `release.yml` build-sidecar job использует `actions/setup-python` с `cache: pip` — кэш включает wheel artifacts. PyInstaller кэширует `.pyc` и bundled files которые могут быть stale при смене deps без полного cache invalidation | `release.yml:91-96` | Добавить cache key include `packaging/aurora-sidecar.spec` и `pyproject.toml` hash |
| D-06 | **Low** | `bench.yml` запускается только на `ubuntu-22.04` — нет Windows gate. Binary cold start на Windows с AV scan может быть 3-5× медленнее. Реальные пользователи — Windows. | `bench.yml:30` | Добавить windows-2022 matrix leg с более мягким threshold (4-6с) |

### 4.2 Rollback strategy отсутствует

Нет документированного rollback procedure при broken release:
- Нет auto-rollback в updater manifest (Tauri updater не поддерживает rollback из коробки)
- Нет versioned artifact retention policy (artifacts retention=7 дней → после 7 дней старый binary недоступен)
- Нет `latest_stable.json` endpoint отдельно от `latest.json`

**Рекомендация (Medium, effort M):** хранить `latest_stable.json` и обновлять только при явном promote шаге. Retention увеличить до 90 дней для release artifacts.

### 4.3 Disaster Recovery для ProjectDB

- Нет backup механизма — при corruption пользователь теряет все проекты
- `vacuum()` метод существует, но не вызывается из sidecar и нет scheduled cleanup
- PRAGMA `integrity_check` не выполняется при startup (только `_maybe_gc_on_open`)

**Рекомендация (High, effort M):** при каждом `_get_project_db()` после успешного open — копировать `projects.db` в `projects.db.bak.YYYYMMDD` (максимум 7 копий, FIFO). `shutil.copy2` на SQLite WAL safe после `PRAGMA wal_checkpoint(FULL)`.

---

## 5. Observability Gaps

| # | Severity | Описание | Файл | Impact |
|---|---|---|---|---|
| O-01 | **High** | `optimize_budget` thread: нет прогресс-событий. N-итерационный search выполняется без единого `optimize_budget_progress` event — UI слепой 30-120с | `methods.py:2096-2165` | Пилотный customer принимает приложение за зависшее |
| O-02 | **High** | Sidecar stderr → Rust `log::warn` — нет структурированного формата. Python traceback попадает в unstructured string. Невозможно aggregate/filter по error type | `sidecar.rs:184-186` | Production диагностика требует ручного парсинга multi-line logs |
| O-03 | **Medium** | Нет метрики времени выполнения каждого JSON-RPC метода. `serve_once()` не инструментировано — нет percentile данных по latency | `server.py:56-97` | Невозможно определить какие методы медленны без профилировщика |
| O-04 | **Medium** | `_DbKvShim.get/set` перехватывают `except Exception: pass/return None` — consent persistence failures полностью молча. Нет warning в log | `methods.py:2225-2232` | Consent не сохраняется, но ни пользователь ни разработчик об этом не знает |
| O-05 | **Medium** | GC thread log: "Periodic GC: running" ТОЛЬКО если db is not None. Если db None (первые 60с startup) — GC цикл молча пропускается 60-секундными интервалами без log | `methods.py:296-323` | Невозможно диагностировать почему GC не запускается при startup race |
| O-06 | **Medium** | Отсутствует telemetry для forecast latency (start_forecast → forecast_completed elapsed_ms есть в event, но не агрегируется). Нет p50/p95/p99 для customer sessions | `methods.py:1365-1373` | Невозможно SLO установить без данных |
| O-07 | **Low** | `check_integrity()` не логирует сколько времени заняла проверка. При 10k+ блобов — нет duration в `integrity_check_completed` event | `methods.py:1697-1712` | Нельзя проактивно обнаружить деградацию |
| O-08 | **Low** | `autosave.py` логирует на уровне `_log.info` — нет structured fields (project_uuid, slot, bytes_written). Невозможно correlation по проекту | `autosave.py` | Minor diagnostic gap |

---

## 6. Specific Risks этой сессии

### Risk 1: `_cancel_event` shared state → budget optimizer race

**Что именно поломается:**

`budget_optimizer.find_best_spend_plan()` вызывает `forecast_fn` последовательно (строка 280 budget_optimizer.py). Каждый `forecast_fn(spend_plan)` вызывает `orchestrator.forecast_recipient()`, который делает `_cancel_event.clear()` (строка 187 orchestrator). Watchdog timer запускается с `_cancel_event`. **Проблема:** если пользователь в этот момент нажимает "Cancel Forecast" на другом forecast handle — `cancel.set()` в forecast thread вызывает `flag.set()` на ДРУГОМ cancel Event (per-forecast), но `_cancel_event` — module-level и общий. Если в будущем (следующий sprint) budget optimizer запустится параллельно с обычным forecast — `_cancel_event.clear()` в одном вызове сбрасывает watchdog другого.

**Также**: при `n_iterations=500` с 5 каналами budget optimizer делает 500 `forecast_recipient()` вызовов, каждый вызывает `_cancel_event.clear()` перед стартом — watchdog предыдущей итерации немедленно сбрасывается. Это значит forecast_budget_seconds PER ITERATION фактически не работает в budget context — watchdog каждой итерации сбрасывается следующей.

**Рекомендованный fix:** передавать `cancel_event: threading.Event` как параметр в `forecast_recipient()` и `LaunchOrchestrator` вместо module-level state. Budget optimizer создаёт per-search cancel_event, forecast thread использует per-forecast cancel_event.

```python
# orchestrator.py: убрать module-level _cancel_event
def forecast_recipient(self, ..., cancel_event: threading.Event | None = None) -> OrchestrationResult:
    cancel = cancel_event or threading.Event()
    cancel.clear()
    watchdog = _start_watchdog(effective_budget, cancel)
```

**Severity: Critical | Effort: M**

---

### Risk 2: `kv_get/kv_set` не существуют в `ProjectDB` → consent никогда не персистируется

**Что именно поломается:**

`_get_consent_manager()` создаёт `_DbKvShim` который вызывает `self._db.kv_get(key)` и `self._db.kv_set(key, value)`. Поиск `kv_get|kv_set` по всему `src/` возвращает ТОЛЬКО строки в `methods.py:2225,2231` — метода в `ProjectDB` не существует.

`_DbKvShim.get()` перехватывает `except Exception: return None`, поэтому `AttributeError: 'ProjectDB' object has no attribute 'kv_get'` молча проглатывается.

**Последствие:** consent setting **никогда** не записывается в БД. После перезапуска sidecar `_consent_manager` пересоздаётся с `_cached=None`, `_store` возвращает None на всех вызовах. Пользователь даёт согласие на auto-refresh → sidecar перезапускается → согласие сброшено → `check_data_source_updates` возвращает `{"triggers": []}` (consent disabled) → auto-refresh функция полностью нерабочая.

**Рекомендованный fix:** добавить `kv_get` и `kv_set` в `ProjectDB` через отдельную migration таблицу `kv_store`:

```sql
-- v003_kv_store.sql
CREATE TABLE IF NOT EXISTS kv_store (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (3, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
```

```python
def kv_get(self, key: str) -> Any:
    row = self._conn.execute("SELECT value_json FROM kv_store WHERE key = ?", (key,)).fetchone()
    return json.loads(row["value_json"]) if row else None

def kv_set(self, key: str, value: Any) -> None:
    with self._write_lock, self._tx():
        self._conn.execute(
            "INSERT INTO kv_store (key, value_json, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at",
            (key, json.dumps(value, ensure_ascii=False), _utc_now_iso()),
        )
```

**Severity: High | Effort: S (schema migration + 2 methods)**

---

### Risk 3: `shutdown()` не дренирует optimize_budget threads

**Что именно поломается:**

`_shutdown()` строка 1936: `handles = list(_forecast_threads.keys())`. Далее: join `_forecast_threads`, join `_integrity_threads`, stop `_GC_THREAD`, close `_AUTOSAVE`, close `_PROJECT_DB`, clear DI container.

`_optimize_threads` и `_optimize_cancel_flags` нигде в `_shutdown()` не упомянуты.

**Последствие:** при shutdown во время `optimize_budget`:
1. `_PROJECT_DB.close()` вызывается — WAL checkpoint flush начинается
2. `_optimize_threads[handle]` (daemon thread) продолжает вызывать `orchestrator.forecast_recipient()` → `LaunchOrchestrator._forecast_recipient_impl()` → потенциально обращается к ProjectDB через DI (зависит от impl)
3. Python interpreter начинает teardown → daemon thread аварийно завершается
4. WAL checkpoint может остаться в невалидном состоянии при следующем открытии

**Рекомендованный fix:**

В `_shutdown()` после строки 1959 (after integrity_threads drain) добавить:

```python
# Drain in-flight budget optimization tasks (§4.4)
opt_handles = list(_optimize_threads.keys())
for ohandle in opt_handles:
    oflag = _optimize_cancel_flags.get(ohandle)
    if oflag is not None:
        oflag.set()
for ohandle in opt_handles:
    othread = _optimize_threads.get(ohandle)
    if othread is not None:
        othread.join(timeout=_SHUTDOWN_PER_FORECAST_TIMEOUT_S)
```

**Severity: High | Effort: S (8 строк)**

---

### Risk 4: ConsentManager инициализируется с `db=None` если ProjectDB ещё не ready

**Что именно поломается:**

`_get_consent_manager()` строка 2215 вызывает `db = _get_project_db()`. Если ProjectDB ещё не инициализирован (первый вызов `check_data_source_updates` до первого `_get_project_db()`), то `_get_project_db()` выполнит lazy init — OK. **Но**: если init ProjectDB упал (`SidecarStorageError`), `_get_consent_manager()` перехватывает `except Exception` и создаёт `ConsentManager(db_store=None)` — in-memory только.

Это вторичный risk: `_consent_manager` singleton сохраняется с `db_store=None` НАВСЕГДА, даже если ProjectDB потом инициализируется. Перезапуск sidecar нужен для восстановления.

**Рекомендованный fix (POSSIBLE):** при успешном `_get_project_db()` проверять `_consent_manager._store is None` и при необходимости переинициализировать с новым store. Либо ConsentManager не должен быть singleton — создаётся fresh с актуальным db на каждый вызов `check_data_source_updates`.

**Severity: Medium | Effort: M**

---

### Risk 5: DataSourceWatcher создаётся заново на каждый `check_data_source_updates` вызов

**Что именно поломается:**

`_check_data_source_updates()` строка 2307: `watcher = DataSourceWatcher(project_uuid=project_uuid, db=db)` — создаётся новый экземпляр. `DataSourceWatcher.__init__()` вызывает `_load_from_db()` (SQL запрос к ProjectDB). При N вызовах в сессию (каждый раз при открытии проекта) → N SQL запросов.

**Также**: `watcher._dismissed` — instance-level set, не shared между вызовами. Если пользователь dismiss → `_dismissed_refresh` (module-level) правильно обновляется — OK. Но check `self._project_uuid in self._dismissed` (строка 188) проверяет `self._dismissed` (пустой у нового instance), а не `_dismissed_refresh`. Дублирование: `_dismissed_refresh` в `methods.py` + `_dismissed` в DataSourceWatcher — два несинхронизированных dismiss registry.

**Рекомендованный fix:** кэшировать DataSourceWatcher per project_uuid в DI container или в module-level dict.

**Severity: Medium | Effort: M**

---

## 7. Test Coverage Map

### Покрытие по модулям

| Модуль | Есть тест? | Качество | Gaps |
|---|---|---|---|
| `persistence/project_db.py` | Да (`test_phase_0_persistence.py`, `test_db_migrations.py`) | Хорошее | Нет теста concurrent write_lock race; нет теста `set_current_version` без lock |
| `persistence/autosave.py` | Да (`test_phase_0_2_autosave.py`) | Хорошее | 1 autosave flake (transient timer) — root cause неизвестен |
| `engines/budget_optimizer.py` | Да (`test_budget_optimizer.py`) | Среднее | Нет теста shared `_cancel_event` race; нет теста при параллельных вызовах; нет теста cancel mid-search |
| `engines/data_source_watcher.py` | Да (`test_data_source_watcher.py`) | Хорошее | Нет теста при dismiss через module-level vs instance-level sets |
| `services/optimizer_client.py` | Да (`test_cross_product_validation.py`) | Среднее | LocalOptimizerClient не тестируется (NotImplementedError); нет интеграционного теста с реальным Optimizer DB |
| `sidecar/services.py` | Да (`test_di_container.py`) | Хорошее | Нет теста register_reset_callback с mock |
| `schemas/auto_refresh.py` | Да (`test_auto_refresh_consent.py`) | Среднее | Нет теста persistence через kv_get/kv_set (которые не существуют в ProjectDB) |
| `engines/launch_orchestrator.py` | Да (`test_phase_pi_2_4_orchestrator.py`) | Среднее | Нет теста `_cancel_event` pollution между concurrent calls |
| `sidecar/methods.py` (shutdown) | Частично (`test_phase_pi_3b_sidecar_handlers.py`) | Слабое | Нет теста `_optimize_threads` не дренируется при shutdown |
| `persistence/project_db.py` (`kv_get/kv_set`) | **Нет** | Отсутствует | Методы не существуют — тесты impossible |

### Autosave flake root cause (POSSIBLE)

`test_phase_0_2_autosave.py` содержит timer tests с коротким interval. На Windows с `threading.Timer` может быть jitter ±100-200ms из-за OS thread scheduler quantum (15.6ms Windows default). Тест с `time.sleep(interval * 1.5)` может не дождаться timer callback при OS load spike.

**Рекомендованный fix:** использовать `threading.Event` с timeout вместо `time.sleep` в timer tests:

```python
fired = threading.Event()
with AutosaveManager(autosave_dir, interval_s=0.05, on_save=lambda: fired.set()) as mgr:
    assert fired.wait(timeout=1.0), "Timer did not fire within 1 second"
```

---

## 8. Top-10 Quick Wins (Effort S, Impact M+)

| # | Priority | Описание | Файл | Impact |
|---|---|---|---|---|
| QW-01 | 🔴 Critical | Добавить `_write_lock` в `set_current_version()` — одна строка | `project_db.py:702` | Устраняет thread-safety hole в write path |
| QW-02 | 🔴 Critical | Добавить drain `_optimize_threads` в `shutdown()` — 8 строк | `methods.py:~1959` | Устраняет Budget Optimizer не дренируется при shutdown |
| QW-03 | 🔴 High | Создать `v003_kv_store.sql` migration + `kv_get/kv_set` в ProjectDB | `project_db.py`, `migrations/` | Исправляет broken consent persistence — auto-refresh функция заработает |
| QW-04 | 🔴 High | Параметризовать `cancel_event` в `forecast_recipient()` — убрать module-level | `launch_orchestrator.py` | Устраняет _cancel_event race condition |
| QW-05 | 🟡 Medium | Добавить `is_file()` проверку в `LocalOptimizerClient.__init__` | `optimizer_client.py:224` | Уже в коде (из Stage 3/4 audit) — **VERIFY** реализован |
| QW-06 | 🟡 Medium | В `_DbKvShim.get/set` добавить `logger.warning()` при Exception | `methods.py:2225,2231` | Silent failures становятся видимыми |
| QW-07 | 🟡 Medium | Добавить `optimize_budget_progress` event каждые 10% итераций | `methods.py:2096` | Pilot customer видит progress 30-120с |
| QW-08 | 🟡 Medium | `bench.yml`: добавить Windows cold start gate (binary spawn, не import) | `bench.yml` | Real-world performance gate |
| QW-09 | 🟡 Medium | `sidecar-build.yml`: запускать полный `pytest`, не 2 файла | `sidecar-build.yml:86` | Catches broken sidecar logic перед PyInstaller |
| QW-10 | 🟢 Low | Пометить TODO comment в `ci.yml:169-187` как resolved + удалить | `ci.yml` | Misleading obsolete комментарий убирает confusion |

---

## 9. Top-10 Strategic Improvements (Effort M-L, Impact H)

| # | Priority | Описание | Effort | Impact |
|---|---|---|---|---|
| ST-01 | 🔴 High | **Разбить `methods.py`** на 5 модулей: `handlers/lifecycle.py`, `handlers/project.py`, `handlers/forecast.py`, `handlers/optimizer.py`, `handlers/data_refresh.py`. Центральный dispatcher — 50 строк. | L | Maintainability: merge conflicts, onboarding, testability |
| ST-02 | 🔴 High | **Единый Thread Registry** вместо пяти разных dicts. `ThreadRegistry.register(handle, thread, cancel_flag)` + `drain_all(timeout=5.0)` вызывается из shutdown. Новые типы background tasks автоматически дренируются | M | Architecture: eliminates shutdown drift risk |
| ST-03 | 🔴 High | **ProjectDB backup on open** — копирование `projects.db` в rolling backup при каждом запуске (max 7 копий). Один `shutil.copy2` + `wal_checkpoint(FULL)` < 100ms | M | Disaster recovery: pilot customer не теряет данные при corruption |
| ST-04 | 🟡 Medium | **N+1 fix в `list_projects()`** — заменить correlated subquery на JOIN агрегацию: `SELECT p.*, COUNT(v.version_id) AS vcount FROM projects p LEFT JOIN versions v ON v.project_uuid = p.project_uuid GROUP BY p.project_uuid` | S | Performance: x100 load — list_projects < 50ms вместо 1-2с |
| ST-05 | 🟡 Medium | **Параллельный budget optimizer** — внутри `find_best_spend_plan` использовать `ThreadPoolExecutor(max_workers=min(4, cpu_count))` для параллельной оценки splits. С thread-safe `forecast_fn` (после ST-01 fix cancel_event) ускорение 2-4× | L | Performance + UX: 30-120с → 10-30с |
| ST-06 | 🟡 Medium | **DataSourceWatcher caching** — кэшировать instance per `project_uuid` в `_consent_manager` scope или DI container. Убрать `_load_from_db()` на каждый вызов `check_data_source_updates` | M | Performance: N SQL → 1 SQL per session per project |
| ST-07 | 🟡 Medium | **Autosave encryption** — использовать тот же ключ что и ProjectDB (из `encryption.get_or_create_db_key()`) для `_atomic_write_json` через `cryptography.fernet` или AES-GCM. | M | Security: autosave в plaintext рядом с зашифрованной DB |
| ST-08 | 🟡 Medium | **Structured sidecar stderr logging** — заменить `sys.stderr.write(f"[aurora-sidecar] ...")` на `structlog` или `logging.JSONFormatter`. Rust side парсит JSON вместо plain string | M | Observability: production диагностика без grep |
| ST-09 | 🟢 Low | **Rollback strategy** для updater — держать `latest_stable.json` отдельно от `latest.json`. Promote step требует manual approval. Release artifacts retention 90 дней | M | DevOps: ability to revert bad release |
| ST-10 | 🟢 Low | **SQLite integrity_check на startup** — после `_apply_schema()` выполнить `PRAGMA integrity_check` (или быстрый `PRAGMA quick_check`). Если возвращает не "ok" — предложить restore из backup (ST-03). | S | Reliability: corrupt DB обнаруживается при запуске, не в runtime |

---

## Appendix A: Counting-based Evidence

**`methods.py` complexity metrics (approximation):**
- Строки: ~2346
- Registered методов: 35 (`@register(...)` calls)
- Module-level dicts/events: 7 (`_METHODS`, `_cancel_flags`, `_forecast_threads`, `_integrity_threads`, `_integrity_cancel_flags`, `_optimize_threads`, `_optimize_cancel_flags`)
- Module-level singletons: 5 (`_PROJECT_DB`, `_AUTOSAVE`, `_GC_THREAD`, `_consent_manager`, `_dismissed_refresh`)
- `global` declarations: 7
- Threading locks: 4 (`_PROJECT_DB_LOCK`, `_AUTOSAVE_LOCK`, `_GC_THREAD_LOCK`, `_consent_lock`)

**CI/CD coverage gaps:**
- Python matrix: ✅ 3.11 + 3.12 × Ubuntu + Windows + macOS
- Rust: ✅ Ubuntu (test.yml), Windows/macOS via release.yml build-app
- Binary cold start Windows: ❌ нет gate
- Full pytest перед sidecar binary build: ❌ только 2 файла

**Missing schema elements:**
- `kv_get/kv_set` в ProjectDB: ❌ не существуют
- `set_current_version` + `_write_lock`: ❌ отсутствует
- `_optimize_threads` drain в shutdown: ❌ отсутствует
- `_cancel_event` parametrization: ❌ module-level shared
