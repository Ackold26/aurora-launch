# STAGE 3/4 Final Red-Team Audit — 2026-05-16

**Scope:** Этапы 3.4 (cross-product), 3.5 (auto-refresh), 4.3 (a11y), 4.4 (budget optimizer).
**Commits audited:** `c94f52e`, `2ad0aa4`, плюс коммит 3.5 / 152-ФЗ opt-in.
**Аудитор:** Claude Sonnet 4.6 (red-team pass).
**Статус:** pre-PR gate.

---

## Severity legend

| Метка | Описание |
|---|---|
| BLOCKER | Crash / data-loss / security — блокирует PR |
| HIGH | Неправильное поведение видимое пользователю, ложный сигнал, потеря состояния |
| MEDIUM | Деградация UX или технический долг с риском роста |
| LOW | Стилистика, minor UX |
| FALSE-POSITIVE | Проверено, проблемы нет |

---

## BLOCKER

---

### B-01 · LocalOptimizerClient не проверяет, что путь — файл, а не директория

**File:** `src/aurora_launch/services/optimizer_client.py` lines 220–225

**Описание:**
`LocalOptimizerClient.__init__()` использует `db_path.exists()` для проверки пути из `AURORA_OPTIMIZER_DB_PATH`. Если customer установил переменную в путь директории (опечатка: `AppData\Roaming\aurora-econometrica-gui\` вместо `…\aurora-econometrica-gui.db`), `exists()` вернёт `True`, клиент создастся без ошибки, но при первом SQL-запросе выбросит `sqlite3.OperationalError: unable to open database file`. Эта ошибка не перехватывается `OptimizerNotConfigured` (там только `NotImplementedError`), и пробьётся до sidecar как необработанный exception.

**Доказательство:** `db_path.exists()` возвращает `True` для директории. `list_projects()` / `get_history()` сейчас поднимают `NotImplementedError` (schema TBD) — но когда схема будет реализована, sqlite3 упадёт c OperationalError вместо OptimizerNotConfigured.

**Suggested fix:**
```python
if not db_path.exists() or not db_path.is_file():
    raise OptimizerNotConfigured(
        f"Optimizer DB not found or is not a file at {db_path}. ..."
    )
```

**Effort:** 5 минут.

---

### B-02 · `_hard_reset_module_singletons` не сбрасывает `_consent_manager` и `_dismissed_refresh`

**File:** `src/aurora_launch/sidecar/methods.py` lines 102–105 vs 2177–2181

**Описание:**
`_hard_reset_module_singletons()` (вызываемая из `reset_services_for_testing()`) обнуляет только `_PROJECT_DB` и `_AUTOSAVE`. Однако `_consent_manager` и `_dismissed_refresh` — тоже module-level singletons в том же файле. Между тестами `_consent_manager` остаётся инициализированным с предыдущим `db_store`, а `_dismissed_refresh` содержит UUID из предыдущего теста. Это разрушает изоляцию тестов для любого теста, который вызывает `get_refresh_consent` / `check_data_source_updates` / `dismiss_refresh_trigger` — они получают state от предыдущего теста.

**Доказательство:** Строки 2177, 2180 — module-level переменные, не упомянуты в строке 103.

**Suggested fix:**
```python
def _hard_reset_module_singletons() -> None:
    global _PROJECT_DB, _AUTOSAVE, _consent_manager  # noqa: PLW0603
    _PROJECT_DB = None
    _AUTOSAVE = None
    _consent_manager = None
    _dismissed_refresh.clear()  # set — нельзя переприсвоить global, clear() безопасен
```

**Effort:** 5 минут.

---

## HIGH

---

### H-01 · `LocalOptimizerClient` — оба public метода поднимают `NotImplementedError`, код попадёт в production

**File:** `src/aurora_launch/services/optimizer_client.py` lines 229–249

**Описание:**
`LocalOptimizerClient.list_projects()` и `get_history()` поднимают `NotImplementedError` ("schema TBD"). В `_validate_against_optimizer` (methods.py) ловится только `OptimizerNotConfigured`, а не `NotImplementedError`. Если customer случайно установит `AURORA_OPTIMIZER_DB_PATH`, sidecar создаст `LocalOptimizerClient` успешно, а при первом вызове `validate_against_optimizer` получит `NotImplementedError` вместо graceful degradation. Это неперехваченное исключение пробьётся к JSON-RPC как server error, а не как `{"available": false}`.

**Доказательство:** `methods.py` line 1816–1819 ловит только `OptimizerNotConfigured`. `LocalOptimizerClient` никогда не регистрируется в ServiceContainer в production code (нет startup-time wiring в `methods.py`), но если кто-то допишет это — поломка гарантирована.

**Suggested fix:** До реализации схемы Optimizer — либо (а) не экспортировать `LocalOptimizerClient` публично и задокументировать явно, (б) добавить catch `NotImplementedError` в `_validate_against_optimizer` → return `{"available": False, "reason": "schema_not_finalized"}`.

**Effort:** 30 минут.

---

### H-02 · `_scan_folder_max_mtime` итерирует ВСЕ файлы папки — O(N) stat-calls при N>>1

**File:** `src/aurora_launch/engines/data_source_watcher.py` lines 84–95

**Описание:**
`folder.iterdir()` + `child.stat()` в цикле — синхронная операция на каждый файл в папке. Если customer хранит в папке архив DSM-экспортов (несколько лет по 52 недели = 200–500 XLSX), каждый вызов `check_for_updates()` делает 200–500 stat-syscalls в main sidecar thread. На Windows с HDD это занимает 200–2000 мс — замораживает sidecar на это время для всех параллельных IPC-запросов.

**Suggested fix:**
- Минимально: добавить `max_files` hard cap (например, 1000) с `logger.warning()` при превышении.
- Правильно: запускать scan в `ThreadPoolExecutor` worker, не в JSON-RPC handler thread.
- Перспективно: `os.scandir()` вместо `iterdir()` + отдельного `stat()` (DirEntry уже кеширует stat на Windows/Linux).

**Effort:** 30 минут (cap + warning) или 2–4 часа (async scan).

---

### H-03 · `RefreshAvailableBanner` не получает `projectUuid` из layout — функциональность §3.5 мертва в production

**File:** `frontend/src/routes/+layout.svelte` line 242; `frontend/src/lib/components/RefreshAvailableBanner.svelte` lines 46–49, 101

**Описание:**
`+layout.svelte` монтирует `<RefreshAvailableBanner />` без передачи `projectUuid` и `sources`. В компоненте `projectUuid` default = `''` (пустая строка). В `checkTriggers()` (строка 101) ветка `else if (projectUuid)` falsy для пустой строки → `triggers` всегда остаётся `[]`. Баннер никогда не покажет "новые данные обнаружены" для конкретного проекта — только opt-in dialog на первом запуске. Функциональность §3.5 ("баннер при новых данных") фактически мертва в production.

**Suggested fix:** В `+layout.svelte` добавить:
```typescript
import { activeBundle } from '$lib/stores/bundle';
```
и передать: `<RefreshAvailableBanner projectUuid={$activeBundle?.project_id ?? ''} sources={...} />`

Нужно решить откуда брать `sources` (data source config хранится в bundle metadata или в отдельном IPC вызове).

**Effort:** 1–2 часа (включая IPC для sources).

---

### H-04 · `BudgetSearchRequest` не валидирует `sum(cap.min) <= total_budget`

**File:** `src/aurora_launch/schemas/budget_optimization.py` lines 91–98; `src/aurora_launch/engines/budget_optimizer.py` lines 118–123

**Описание:**
Validator `caps_do_not_exceed_budget` проверяет только `cap.min > total_budget` для каждого канала по отдельности. Feasibility требует `sum(cap.min for all channels) <= total_budget`. Пример: 3 канала с `min=40_000` каждый, `total_budget=100_000`. Каждый min < budget → validator проходит. В `_random_splits()` `total_slack = 100_000 - 120_000 = -20_000 < 0` → код возвращает `[split] * n` где все каналы на своём min (sum = 120_000 > budget — overspent split передаётся в forecast_fn).

**Suggested fix:**
```python
total_min = sum(cap.min for cap in self.channel_caps.values())
if total_min > self.total_budget:
    raise ValueError(
        f"Sum of channel_caps mins ({total_min}) > total_budget ({self.total_budget})"
    )
```

**Effort:** 20 минут (validation + test).

---

### H-05 · `_optimize_budget` runner — emit failure на `OSError`/`ValueError` глотает другие exception types

**File:** `src/aurora_launch/sidecar/methods.py` lines 2126–2137

**Описание:**
В `runner()` except-блоке `events.emit(optimize_budget_failed)` обёрнут в `except (OSError, ValueError): pass`. Если `events.emit` поднимет что-то кроме `OSError`/`ValueError` (например, `RuntimeError` при закрытом stdout, или `BrokenPipeError` в production), весь except-блок падает без fallback и без логирования. Customer получает зависший optimize handle (finally снимает флаги, но событие не эмитировано), и никогда не узнает о причине сбоя.

**Suggested fix:** Расширить inner except до `except Exception as emit_exc: logger.error(...)`:
```python
except Exception as emit_exc:
    logger.error(
        "optimize_budget: failed to emit failed event for %s: %s",
        handle, emit_exc
    )
```

**Effort:** 15 минут.

---

### H-06 · `ConsentManager.get()` читает `_cached` вне lock — race condition при concurrent calls

**File:** `src/aurora_launch/engines/data_source_watcher.py` lines 404–419

**Описание:**
`get()` читает `self._cached` без lock (строка 406: `if self._cached is not None`), а `set()` обновляет `self._cached` под lock. Если два JSON-RPC handler'а параллельно вызывают `get_refresh_consent()` и `set_refresh_consent()`, первый handler может прочитать stale `_cached`. Дополнительно: `self._store.get()` в строках 411–414 вызывается вне `_lock` — если store не thread-safe, это data race.

**Suggested fix:**
```python
def get(self) -> Optional[RefreshConsentSetting]:
    with self._lock:
        if self._cached is not None:
            return self._cached
        if self._store is None:
            return None
        try:
            raw = self._store.get(_CONSENT_KEY)
            if raw is None:
                return None
            self._cached = RefreshConsentSetting.model_validate(raw)
            return self._cached
        except Exception as exc:
            logger.warning("ConsentManager.get failed: %s", exc)
            return None
```

**Effort:** 15 минут.

---

### H-07 · `Card.svelte` с `role="article"` — избыточная ARIA роль, семантически некорректная для card container

**File:** `frontend/src/lib/components/Card.svelte` lines 30–36

**Описание:**
Когда `interactive=false`, компонент рендерит `<article role="article">`. По WAI-ARIA 1.2: `<article>` уже имеет implicit role `article`. Явный `role="article"` redundant и выдаёт предупреждение в axe/Lighthouse ("element has redundant role"). Более серьёзно: `<article>` семантически — standalone document (независимый контент). Card используется как контейнер для UI sections (табы Inspector, поля настроек) — `<article>` семантически некорректен. Правильная роль для немодального surface-контейнера — `region` с `aria-label={title}` или `<div>` без role.

**Suggested fix:**
```svelte
<svelte:element
  this={interactive ? 'button' : 'div'}
  role={interactive ? 'button' : (title ? 'region' : undefined)}
  aria-label={!interactive && title ? title : undefined}
  ...
```

**Effort:** 30 минут + smoke тест screen reader.

---

## MEDIUM

---

### M-01 · Severity thresholds 15%/35% захардкожены в двух местах — риск расхождения

**Files:** `src/aurora_launch/schemas/cross_product.py` lines 168–170; `src/aurora_launch/sidecar/methods.py` lines 1848–1857

**Описание:** Пороги deviation severity определены дважды. Если thresholds изменятся в одном месте, `CrossProductValidation` validator будет бросать `ValueError` при попытке создать объект с "верными" по старому коду severity.

**Suggested fix:** Вынести в константы в `cross_product.py` и импортировать в `methods.py`.

**Effort:** 30 минут.

---

### M-02 · `BestSpendPlan.expected_total_sales` — misleading naming (sum of point estimates, not E[X])

**File:** `src/aurora_launch/schemas/budget_optimization.py` line 111

**Описание:** `expected_total_sales` = sum(point_forecast across horizon) — это детерминированный mode/median, а не математическое ожидание (E[Sales | spend_plan]). Customer знакомый с probability может неверно интерпретировать это как posterior mean. В UI, вероятно, отображается как "Ожидаемые продажи" что усиливает путаницу.

**Suggested fix:** Переименовать в `point_total_sales` или добавить явный docstring: "Sum of point_forecast (mode/median, NOT mean of predictive distribution)".

**Effort:** 1 час (rename + i18n).

---

### M-03 · `_scan_folder_max_mtime` — clock setback создаёт permanent false negative

**File:** `src/aurora_launch/engines/data_source_watcher.py` line 254

**Описание:** При manual clock reset НАЗАД — новый XLSX файл получит mtime < `last_seen` → триггер не сработает навсегда для данного файла, пока файл не обновится повторно. Не задокументировано.

**Suggested fix:** Добавить в docstring предупреждение о clock skew. Опционально: если `last_checked_at` + grace period < now, ре-establish baseline.

**Effort:** 15 минут (документация).

---

### M-04 · `CommandPalette` — `onkeydown` на `<li role="option">` избыточен и может вызвать двойную активацию с некоторыми AT

**File:** `frontend/src/lib/components/CommandPalette.svelte` lines 144–152

**Описание:** WAI-ARIA 1.2 listbox pattern: клавиатурная активация option происходит ТОЛЬКО через `aria-activedescendant` в combobox input. `<li>` не должен получать keyboard focus напрямую. `onkeydown` на `<li>` — dead code при стандартном использовании; однако NVDA в "application mode" может передавать keydown на visual-focus element (li с aria-selected), что приведёт к двойному вызову `cmd.action()` + `onClose()`.

**Suggested fix:** Убрать `onkeydown` с `<li>` — клавиатурная активация через input `handleKeydown`. `onclick` на `<li>` достаточен для mouse/pointer.

**Effort:** 15 минут.

---

### M-05 · Z-index конфликт: `CommandPalette` (9999) перекрывает `HandshakeIncompatibleModal` (9999)

**File:** `frontend/src/routes/+layout.svelte`; `CommandPalette.svelte:187`; `HandshakeIncompatibleModal.svelte:130`

**Описание:** Оба компонента имеют `z-index: 9999`. `CommandPalette` монтируется позже в DOM (после `HandshakeIncompatibleModal`), поэтому при одновременном показе (Ctrl+K нажата когда handshake invalid modal активен) CommandPalette перекроет блокирующий handshake modal. Customer сможет выполнять команды навигации хотя приложение должно быть полностью заблокировано.

**Suggested fix:** `HandshakeIncompatibleModal` → `z-index: 10000`. Добавить в `tokens.css` z-index registry:
```css
--z-index-banner: 890;
--z-index-update-banner: 900;
--z-index-toaster: 1000;
--z-index-feedback: 1100;
--z-index-palette: 9000;
--z-index-blocking-modal: 10000;
```

**Effort:** 30 минут.

---

### M-06 · `opt-in` banner показывается при каждом cold start — нет rate limiting по `last_prompted_at`

**File:** `frontend/src/lib/components/RefreshAvailableBanner.svelte` lines 83–87

**Описание:** Когда `consent === null`, banner показывает opt-in. Если customer закрывает приложение без нажатия Accept/Decline — при следующем старте consent снова `null`, banner снова показывается. `last_prompted_at` записывается только после явного действия пользователя. Это создаёт annoying repeat experience при каждом запуске до явного выбора.

**Suggested fix:** При первом показе баннера вызвать `ipc.recordOptInShown()` или записать `last_prompted_at` без изменения `enabled`. При следующем старте — если `last_prompted_at` в последние 7 дней — не показывать.

**Effort:** 2 часа.

---

### M-07 · 152-ФЗ: проверить explicit description собираемых данных в opt-in тексте

**File:** `frontend/src/lib/components/RefreshAvailableBanner.svelte`; i18n key `refresh.optin.detail`

**Описание:** i18n ключ `refresh.optin.detail` должен явно указать: (1) сканируются только mtime локальных файлов, (2) данные не покидают устройство, (3) включение/отключение доступно в Settings. Без просмотра реального i18n файла нельзя подтвердить compliance. Если описание недостаточно — это нарушение §9 152-ФЗ (явное согласие на обработку ПД).

**Suggested fix:** Проверить `frontend/src/lib/i18n/ru.json` ключ `refresh.optin.detail`. Убедиться что текст содержит все 3 элемента.

**Effort:** 1 час (review + правка).

---

### M-08 · `_random_splits` post-clip renormalization может не достигать `total_budget` при tight multi-channel constraints

**File:** `src/aurora_launch/engines/budget_optimizer.py` lines 130–147

**Описание:** При tight constraints (многие каналы up-capped), после `np.clip(raw, per_channel_min, per_channel_max)` renormalization (`diff * headroom / head_sum`) не всегда восстанавливает сумму до `total_budget` — clip уже обрезал headroom до нуля. Результат: split с sum < total_budget (underspend). forecast_fn получит меньший spend чем запрошен без уведомления.

**Suggested fix:** После renormalize: `assert abs(raw.sum() - total_budget) <= 1e-6 or log warning`. Добавить тест с tight-cap 3-channel scenario.

**Effort:** 30 минут.

---

## LOW

---

### L-01 · `inspector/+page.svelte` — `role="document"` на modal content div нестандартен

**File:** `frontend/src/routes/inspector/+page.svelte` line 615

**Описание:** `<div class="reproduce-modal-content" role="document">` — `role=document` это implicit role `<html>`. На inner div вызывает предупреждения в axe/NVDA.

**Suggested fix:** Убрать `role="document"`.

**Effort:** 5 минут.

---

### L-02 · `TutorialCarousel.svelte` — `onskip` prop опциональный без fallback при Escape

**File:** `frontend/src/lib/components/Onboarding/TutorialCarousel.svelte` line 84

**Описание:** `handleKey` вызывает `skip()` → `onskip?.()`. Если `onskip` не передан, Escape ничего не делает — carousel не закрывается. Carousel должен иметь дефолтное поведение при Escape (или явно задокументировать что caller обязан передавать `onskip`).

**Suggested fix:** Добавить default handler или required prop.

**Effort:** 15 минут.

---

### L-03 · `MockOptimizerClient` — `import math` внутри цикла (PEP 8 violation)

**File:** `src/aurora_launch/services/optimizer_client.py` line 163

**Описание:** `import math` стоит внутри `for i in range(self._n_weeks):` цикла. Performance OK (Python кеширует в sys.modules), но нарушает PEP 8 и ruff `C0415`.

**Suggested fix:** Переместить в top-level imports.

**Effort:** 2 минуты.

---

### L-04 · `ChannelCap` — finite check пропускает `int` inputs, работает только для `float`

**File:** `src/aurora_launch/schemas/budget_optimization.py` lines 37–41

**Описание:** `_finite` validator: `if isinstance(v, float): _check_finite(v)`. `int` inputs пропускаются — технически корректно (int всегда finite), но может скрыть будущие edge cases если JSON десериализация вернёт `float` вместо `int`.

**Suggested fix:** Defensive: `if isinstance(v, (int, float))`.

**Effort:** 5 минут.

---

## FALSE-POSITIVE

---

### FP-01 · SQLite write lock при concurrent Optimizer — NOT A BUG (current)

`LocalOptimizerClient` поднимает `NotImplementedError` — SQL не выполняется. Вопрос о WAL/locks актуален при реализации схемы — tracked в CROSS_PRODUCT_INTEGRATION.md.

---

### FP-02 · MockOptimizerClient неизвестный brand_code — NOT A BUG

`get_history()` строка 151 проверяет `brand_code not in self._brand_codes` → `None`. Graceful. "Default" используется только для генерации данных ЕСЛИ brand_code присутствует в `_brand_codes`.

---

### FP-03 · Запрос будущих недель к Optimizer — NOT A BUG (current)

Period filter не реализован в MockClient — known skeleton limitation. В production LocalOptimizerClient период будет filtered SQL-ом.

---

### FP-04 · Enter в CommandPalette input вызывает двойную команду (bubble) — FALSE POSITIVE

`handleKeydown` прикреплён ТОЛЬКО к backdrop div, не к input напрямую. Enter bubbles один раз — одна активация. Двойного срабатывания нет. `onkeydown` на `<li>` redundant (M-04) но не создаёт double-fire из-за focus model (focus остаётся в input).

---

### FP-05 · Cyrillic font fallback на Windows 7 / old Linux — NOT A BUG

`overrides.css` определяет полную цепочку: `'Inter' → -apple-system → BlinkMacSystemFont → 'Segoe UI' → 'Roboto' → 'Helvetica Neue' → 'Arial' → 'Cantarell' → 'Ubuntu' → 'Liberation Sans' → sans-serif`. Self-hosted `@fontsource/inter` включает cyrillic subset — загружается локально. Таuri webview (WebView2 / WKWebView) всегда имеет встроенный rendering с системными шрифтами. На Linux с только Liberation Sans — есть cyrillic. Даже если все named fonts отсутствуют, `sans-serif` resolver даст OS default с cyrillic support.

---

## Summary Table

| # | Severity | Title | File | Effort |
|---|---|---|---|---|
| B-01 | BLOCKER | LocalOptimizerClient: directory vs file path | optimizer_client.py:220 | 5m |
| B-02 | BLOCKER | _hard_reset не сбрасывает _consent_manager/_dismissed_refresh | methods.py:102 | 5m |
| H-01 | HIGH | LocalOptimizerClient NotImplementedError не перехватывается | optimizer_client.py:229 | 30m |
| H-02 | HIGH | _scan_folder_max_mtime O(N) stat в main thread | data_source_watcher.py:84 | 30m–4h |
| H-03 | HIGH | RefreshAvailableBanner projectUuid не передан — §3.5 мертва | +layout.svelte:242 | 1–2h |
| H-04 | HIGH | BudgetSearchRequest: sum(cap.min) не валидируется | budget_optimization.py:91 | 20m |
| H-05 | HIGH | _optimize_budget runner: emit failure глотает не-OSError/ValueError | methods.py:2127 | 15m |
| H-06 | HIGH | ConsentManager.get() race condition — cached read вне lock | data_source_watcher.py:406 | 15m |
| H-07 | HIGH | Card.svelte: role="article" redundant + semantically wrong | Card.svelte:35 | 30m |
| M-01 | MEDIUM | Severity thresholds захардкожены в двух местах | cross_product.py:168 | 30m |
| M-02 | MEDIUM | expected_total_sales misleading naming | budget_optimization.py:111 | 1h |
| M-03 | MEDIUM | clock setback → permanent false negative в watcher | data_source_watcher.py:254 | 15m |
| M-04 | MEDIUM | CommandPalette: onkeydown на li избыточен, риск AT double-fire | CommandPalette.svelte:144 | 15m |
| M-05 | MEDIUM | Z-index: CommandPalette перекрывает HandshakeIncompatibleModal | layout.svelte CSS | 30m |
| M-06 | MEDIUM | opt-in banner при каждом cold start — нет rate limiting | RefreshAvailableBanner.svelte:83 | 2h |
| M-07 | MEDIUM | 152-ФЗ: проверить explicit description в opt-in тексте | i18n/ru.json | 1h |
| M-08 | MEDIUM | _random_splits post-clip underspend при tight constraints | budget_optimizer.py:130 | 30m |
| L-01 | LOW | role="document" на modal div | inspector/+page.svelte:615 | 5m |
| L-02 | LOW | TutorialCarousel: onskip опциональный без fallback | TutorialCarousel.svelte:84 | 15m |
| L-03 | LOW | import math внутри цикла в MockOptimizerClient | optimizer_client.py:163 | 2m |
| L-04 | LOW | ChannelCap finite check только для float | budget_optimization.py:37 | 5m |

**Итого:** 2 BLOCKER, 7 HIGH, 8 MEDIUM, 4 LOW, 5 FALSE-POSITIVE.

---

## Топ-3 самых опасных

**1. H-03** — `RefreshAvailableBanner` не получает `projectUuid` → вся feature §3.5 "новые данные" мертва в production. Пользователь видит opt-in, может нажать "Включить", но "Обновить прогноз" никогда не появится.

**2. B-02** — `_hard_reset_module_singletons` пропускает `_consent_manager`/`_dismissed_refresh` → CI может давать false-green на тестах auto-refresh из-за state pollution между тестами. Маскирует реальные баги.

**3. H-04** — `BudgetSearchRequest` не валидирует `sum(cap.min) <= total_budget` → infeasible spend plans при multi-channel tight constraints молча передаются в forecast engine.

---

*Дата: 2026-05-16. Auditor: Claude Sonnet 4.6 (red-team mode). Следующий шаг: Opus review + apply fixes.*
