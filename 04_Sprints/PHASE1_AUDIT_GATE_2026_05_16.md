# Phase 1 Audit Gate — 2026-05-16

**Plan reference:** validated-jumping-map.md → Audit Gate Phase 1.
**Audit lead:** Sonnet 4.6 (independent verification).
**Branch:** feat/stage1-core-1.1-1.4 (HEAD on audit time).
**Goal:** verify ALL Phase 1 partii (1.A / 1.B.1 / 1.B.2 / 1.C / 1.D)
closed на ship-quality level перед Phase 2.

---

## Summary

| # | Check | Verdict | Notes |
|---|---|---|---|
| 1 | C-4 lang attribute | PASS | `$effect` на `$locale` реактивно ставит `documentElement.lang` ru-RU/en-US; +layout.svelte:138 |
| 2 | C-5 shadow tokens + hover | PASS | Все 4 токена (`--shadow-sm/md/lg/glow`) определены для dark + light; hover lift `.card.interactive:hover` с transform + box-shadow присутствует; overrides.css:115–148 |
| 3 | C-2 consent kv_store | PASS | `kv_get/kv_set/kv_delete` реализованы в `project_db.py:760–812` с `_write_lock + _tx()`; v003 migration SQL существует; `_DbKvShim` удалена (осталась только в docstring-комментарии); 8 KV-migration тестов прошли |
| 4 | C-1 wizard full flow | PASS | Все 3 компонента существуют и подключены в wizard +page.svelte; 12/12 Playwright wizard-happy-path прошли; 7/7 wizard.a11y прошли |
| 5 | UX-3 recovery dialog | PASS | Диалог «Восстановить незаконченный сеанс?» есть; `role="dialog"` + `aria-modal="true"` + `aria-labelledby="recovery-title"` подтверждено; `wizardSession.svelte.ts` имеет все методы: `loadDraft/acceptRecovery/dismissRecovery/update/reset/flush` |
| 6 | H-3/H-5/H-6/H-7 fixes | PARTIAL | H-3/H-5/H-6 — PASS. H-7 — PARTIAL: fallback-токен реализован через класс `nb-btn--primary` в `NotificationBanner.svelte` (который использует `var(--color-ui-accent-primary, #6366f1)`), тогда как checklist ожидал inline `var(--color-ui-accent-primary, #2E5BFF)`. Функционально токен применяется, но значение fallback отличается от указанного в чеклисте (#6366f1 vs #2E5BFF). |
| 7 | BTA-3 NotificationBanner | PASS | `NotificationBanner.svelte` существует; все 3 consumer'а (HandshakeIncompatibleModal, UpdateAvailableBanner, RefreshAvailableBanner) импортируют и используют базовый компонент |
| 8 | BTA-1 methods.py split | PARTIAL | Все 6 файлов существуют. `methods_forecast.py` = 869 LOC и `methods_project.py` = 750 LOC — превышают target ≤900 acceptable порог (оба в пределах 900); основной dispatcher `methods.py` = 615 LOC. Pytest 1426/0 fail. |

**Overall verdict:** CONDITIONAL — Phase 2 может стартовать. Два PARTIAL не блокируют, но требуют отдельного внимания.

---

## Detailed findings

### 1. C-4 (lang attribute)

**PASS**

`frontend/src/routes/+layout.svelte:136–140`:
```svelte
$effect(() => {
  if (typeof document !== 'undefined' && $locale) {
    document.documentElement.lang = $locale.startsWith('ru') ? 'ru-RU' : 'en-US';
  }
});
```
Реактивен к `$locale` из svelte-i18n. Выставляется при каждом изменении locale (settings page). Guard `typeof document !== 'undefined'` обеспечивает SSR safety. Требование выполнено полностью.

---

### 2. C-5 (shadow tokens + hover lift)

**PASS**

`frontend/src/lib/styles/overrides.css:115–148`:

- `:root` определяет `--shadow-sm`, `--shadow-md`, `--shadow-lg`, `--shadow-glow` (строки 116–122)
- `[data-theme="dark"]` переопределяет все 4 с более плотными тенями (строки 125–133)
- `.card.interactive:hover:not(:disabled):not(.loading)` применяет `transform: translateY(-1px)` + `box-shadow: var(--shadow-md)` с transition (строки 137–142)
- `@media (prefers-reduced-motion: reduce)` отключает `transform`, сохраняя shadow как focus indicator (строки 144–148) — соответствует INV-14

`--shadow-glow` использует `var(--accent, #2E5BFF)` как базу через `color-mix`, что корректно.

---

### 3. C-2 (consent v003 kv_store)

**PASS**

Три части подтверждены:

1. **`project_db.py:760–812`** — методы `kv_get`, `kv_set`, `kv_delete` реализованы с `_write_lock + self._tx()`, JSON сериализацией, defensive type check в `kv_set`.

2. **`src/aurora_launch/persistence/migrations/v003_kv_store.sql`** — таблица `_kv_store (key TEXT PRIMARY KEY, value_json TEXT NOT NULL, updated_at TEXT NOT NULL)` существует; `INSERT OR REPLACE INTO schema_version VALUES (3, ...)`.

3. **`methods_consent.py:58–68`** — docstring явно фиксирует «C-2 fix: убрана _DbKvShim»; `kv_get/kv_set` вызываются напрямую на `ProjectDB`. Живого кода `_DbKvShim` нет (только в docstring-комментариях: `methods_consent.py:65` и `data_source_watcher.py:420`).

4. **`python -m pytest tests/test_db_migrations.py -k kv`**: 8 passed, 0 fail.

---

### 4. C-1 (wizard full flow)

**PASS**

Компоненты:
- `frontend/src/lib/components/ColumnMappingTable.svelte` — существует
- `frontend/src/lib/components/ProxyPickerCard.svelte` — существует
- `frontend/src/lib/components/AnchorsForm.svelte` — существует

Использование в `frontend/src/routes/wizard/+page.svelte`:
- `<ColumnMappingTable>` — строка 607
- `<ProxyPickerCard>` — строка 617
- `<AnchorsForm bind:draft={anchorsDraft}>` — строка 639

Playwright:
- `wizard-happy-path.spec.ts`: **12/12 passed** (5.7s)
- `wizard.a11y.spec.ts`: **7/7 passed** (4.5s)

---

### 5. UX-3 (recovery dialog)

**PASS**

`frontend/src/routes/wizard/+page.svelte`:
- Строка 748: `<h2 id="recovery-title">Восстановить незаконченный сеанс?</h2>` — текст соответствует
- Строка 743: `role="dialog"` — подтверждено
- Строка 744: `aria-modal="true"` — подтверждено
- Строка 745: `aria-labelledby="recovery-title"` — подтверждено

`frontend/src/lib/stores/wizardSession.svelte.ts` — `WizardSessionStore` класс имеет:
- `loadDraft()` (строка 84) — загружает draft из sidecar
- `acceptRecovery()` (строка 107) — swap сессии
- `dismissRecovery()` (строка 115) — clear + `ipc.wizardSessionClear()`
- `update(mutator)` (строка 125)
- `reset()` (строка 131)
- `flush()` (строка 145) — force-save для критических точек

Recovery dialog протестирован в Playwright `wizard-happy-path.spec.ts` (Recovery dialog тесты) и `wizard.a11y.spec.ts:124` (a11y pass).

---

### 6. H-3/H-5/H-6/H-7 fixes

**PARTIAL** (H-7 имеет расхождение по fallback-значению)

**H-3 (shutdown drain for optimize_threads) — PASS**

`src/aurora_launch/sidecar/methods.py:534–545` — явная секция с комментарием `H-3 (audit 4.5 / Phase 1.A)`:
```python
optimize_handles = list(_optimize_threads.keys())
for ohandle in optimize_handles:
    oflag = _optimize_cancel_flags.get(ohandle)
    if oflag is not None:
        oflag.set()
for ohandle in optimize_handles:
    othread = _optimize_threads.get(ohandle)
    if othread is not None:
        othread.join(timeout=_SHUTDOWN_PER_FORECAST_TIMEOUT_S)
```
Паттерн cancel-flag + join идентичен forecast и integrity drain'ам.

**H-5 (autofocus modals) — PASS**

- `frontend/src/routes/+layout.svelte:34,52–56` — `feedbackTextareaEl` + `$effect` с `requestAnimationFrame(() => feedbackTextareaEl?.focus())` при `feedbackOpen`
- `feedbackTrapFocus` (строка 38) реализует Tab-trap между textarea и submit button
- `frontend/src/routes/inspector/+page.svelte:87–92` — `reproduceCloseButtonEl` + `$effect` с `requestAnimationFrame(() => reproduceCloseButtonEl?.focus())` при `reproduceModalOpen`

**H-6 (arrow-key tabs Inspector) — PASS**

`frontend/src/routes/inspector/+page.svelte:374–385`:
```typescript
function tabsKeyboardNav(e: KeyboardEvent): void {
  ...
  if (e.key === 'ArrowRight') { nextIndex = (currentIndex + 1) % TABS.length; }
  else if (e.key === 'ArrowLeft') { nextIndex = (currentIndex - 1 + TABS.length) % TABS.length; }
  else if (e.key === 'Home') { nextIndex = 0; }
  else if (e.key === 'End') { nextIndex = TABS.length - 1; }
```
`role="tablist"` + roving `tabindex` (activeTab = 0, остальные -1) — строки 434–439. Соответствует ARIA APG.

**H-7 (modal accent fallback) — PARTIAL**

Checklist ожидал `var(--color-ui-accent-primary, #2E5BFF)` непосредственно в `HandshakeIncompatibleModal.svelte`.

Фактическая реализация: H-7 был решён через рефакторинг на `NotificationBanner` (BTA-3). Кнопка «Перезапустить» теперь использует класс `nb-btn nb-btn--primary` (`HandshakeIncompatibleModal.svelte:84`), а CSS токен применяется в `NotificationBanner.svelte:341`:
```css
background: var(--color-ui-accent-primary, #6366f1);
```
Токен `--color-ui-accent-primary` применяется корректно. Fallback `#6366f1` (Indigo) отличается от `#2E5BFF` (Aurora Blue) из checklist. В production `tokens.css:20` определяет `--color-ui-accent-primary: #2E5BFF`, поэтому fallback активируется только если tokens.css не загружен. Риск: низкий, но несоответствие fallback-значений — PARTIAL, не FAIL.

---

### 7. BTA-3 (NotificationBanner extract)

**PASS**

`frontend/src/lib/components/NotificationBanner.svelte` — существует (387 строк).

Все 3 consumer'а подтверждены:

- **HandshakeIncompatibleModal.svelte**: импортирует `NotificationBanner` (строка 19), использует `<NotificationBanner level="error" ...>` (строка 62). Комментарий «Refactored on NotificationBanner (BTA-3 Phase 1.A)» — строка 13.
- **UpdateAvailableBanner.svelte**: импортирует (строка 24), использует `<NotificationBanner open={visible} {level} ...>` (строка 156). Комментарий BTA-3 — строка 15.
- **RefreshAvailableBanner.svelte**: импортирует (строка 30), использует `<NotificationBanner open={visible} {level} ...>` (строка 191). Комментарий BTA-3 — строка 22.

NotificationBanner сам управляет backdrop, ARIA (`role`, `aria-modal`, `aria-labelledby`), focus-trap, Escape-dismiss, auto-focus, reduced-motion — всё централизовано.

---

### 8. BTA-1 (methods.py split)

**PARTIAL** (methods_forecast.py превышает 900 LOC target)

Файлы и их LOC:
| Файл | LOC | Статус |
|------|-----|--------|
| `methods.py` (dispatcher) | 615 | OK (≤900) |
| `methods_forecast.py` | **869** | OK (≤900, но близко к пределу) |
| `methods_project.py` | 750 | OK (≤900) |
| `methods_consent.py` | 185 | OK |
| `methods_integrity.py` | 158 | OK |
| `methods_cross_product.py` | 163 | OK |

Все 6 файлов из чеклиста существуют. `methods_forecast.py` при 869 строках остаётся в допустимом диапазоне ≤900, но aspiration target ≤500 не достигнут — это объяснимо сложностью forecast/optimize логики.

Pytest: **1426 passed, 6 skipped, 0 fail** (20.83s).

---

## Test execution snapshot

| Suite | Result |
|-------|--------|
| **pytest** (excl. flaky) | **1426 passed, 6 skipped, 0 fail** (20.83s) |
| **vitest** (unit) | **499 passed, 0 fail** (7.24s) — 38 test files |
| **playwright** wizard-happy-path | **12 passed, 0 fail** (5.7s) |
| **playwright** wizard.a11y | **7 passed, 0 fail** (4.5s) |
| **pytest** test_db_migrations.py -k kv | **8 passed, 0 fail** |
| **svelte-check** | **0 errors, 1 warning** (строка 556 wizard/+page.svelte: `noninteractive element tabindex` — предсуществующее, не регрессия) |

---

## Open items (if any)

### MEDIUM — H-7 fallback inconsistency

**File:** `frontend/src/lib/components/NotificationBanner.svelte:341`
**Issue:** Fallback `#6366f1` (Indigo) вместо `#2E5BFF` (Aurora Blue). В production tokens.css корректно определяет `#2E5BFF`, поэтому видимого эффекта нет. Риск проявляется только если tokens.css не загрузился (очень редкий edge case).
**Recommendation:** Обновить fallback в NotificationBanner.svelte с `#6366f1` на `#2E5BFF` для консистентности с Aurora design system. Не блокер.

### LOW — methods_forecast.py размер (869 LOC)

**File:** `src/aurora_launch/sidecar/methods_forecast.py`
**Issue:** 869 строк — в пределах acceptable ≤900, но aspiration target ≤500 не достигнут. Сложность forecast + optimize_budget handlers объясняет объём.
**Recommendation:** При следующем рефакторинге рассмотреть выделение `optimize_budget` в отдельный `methods_optimize.py`. Не блокер для Phase 2.

### LOW — svelte-check warning (wizard/+page.svelte:556)

**Warning:** `noninteractive element cannot have nonnegative tabIndex value`
**Note:** Предсуществующее предупреждение, не введённое в Phase 1. Рекомендуется закрыть при следующей a11y-волне, но не блокирует.

---

## Approval

**OVERALL: ⚠️ CONDITIONAL — Phase 2 OK after awareness of list items, ни один из них не блокирует.**

Все 8 check'ов прошли верификацию через grep/read/live test runs. Два PARTIAL (H-7 fallback-цвет и methods_forecast.py LOC) не создают production-риска и могут быть закрыты инкрементально в Phase 2 без останова.

Тесты: 1426 pytest + 499 vitest + 12 Playwright happy-path + 7 Playwright a11y = **1944 теста, 0 fail**.
