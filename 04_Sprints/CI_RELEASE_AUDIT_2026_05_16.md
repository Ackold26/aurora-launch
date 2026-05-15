# CI Release Pipeline Audit — 2026-05-16

**Scope:** `.github/workflows/release.yml` + `.github/workflows/sidecar-build.yml`  
**Context:** v0.1.0 GA, пункт 1.2 ROADMAP_POST_V0_1_0.md «Настроить автоматическую сборку при выпуске»  
**Статус применения:** Critical + High findings применены inline; Medium / Low — backlog.

---

## Summary

| Severity | Count | Applied inline | Backlog |
|---|---|---|---|
| Critical | 1 | 1 | 0 |
| High | 3 | 3 | 0 |
| Medium | 4 | 0 | 4 |
| Low | 3 | 0 | 3 |
| Cosmetic | 2 | 0 | 2 |
| **Total** | **13** | **4** | **9** |

---

## CRITICAL

### A-1 — Smoke test отсутствует в release.yml build-sidecar

**Severity:** Critical  
**Категория:** Reliability  
**Описание:** `sidecar-build.yml` содержит полноценный smoke test (строки 98–133): запускает собранный binary, отправляет ping через stdin, проверяет pong-ответ. В `release.yml` job `build-sidecar` (строки 114–139) этого шага нет совсем. Это означает, что broken binary может пройти через release pipeline и попасть в production GitHub Release. `sidecar-build.yml` запускается при push к main, но релизный тег срабатывает из другого контекста и использует независимую сборку без smoke.

**Доказательство:**  
- `release.yml` строки 114–139: шаги `checkout → setup-python → pip install → pyinstaller → rename → upload-artifact`. Нет шага smoke.  
- `sidecar-build.yml` строки 98–133: полный smoke с `grep -m1 '"pong"'` и проверкой exit code.

**Предлагаемое исправление:** Добавить smoke step в `release.yml` после `pyinstaller` и перед `rename binary`, идентичный `sidecar-build.yml` строкам 98–133. Применено — см. раздел «Applied Fixes».

**Effort:** S (копирование существующего шага)

---

## HIGH

### A-2 — DRY-violation: дублирование логики PyInstaller build

**Severity:** High  
**Категория:** DRY / Reliability  
**Описание:** Сборочная логика PyInstaller дублирована между `release.yml` (job `build-sidecar`, строки 96–139) и `sidecar-build.yml` (job `build`, строки 68–150). Оба workflow выполняют: `pip install`, `pyinstaller`, `rename binary`, `upload-artifact`. При этом `sidecar-build.yml` на 50–60 строк длиннее и содержит важные дополнения (step «Reinstall runtime-only for build», smoke test, `retention-days: 30`), которых нет в `release.yml`.

Риски от дублирования:
- Исправление в `sidecar-build.yml` (например, изменение spec-файла или env var) не переходит в `release.yml` автоматически.
- `release.yml` пропускает `pip uninstall pytest hypothesis ruff mypy || true` (HIGH-4 fix, зафиксированный в `sidecar-build.yml` строки 88–93), из-за чего релизный binary потенциально включает dev-зависимости.

**Доказательство:**  
- `release.yml` строки 122–125: `pip install --upgrade pip; pip install -e .; pip install pyinstaller` — нет uninstall dev-deps.  
- `sidecar-build.yml` строки 88–93: полный uninstall dev-deps перед PyInstaller.

**Предлагаемое исправление (backlog — размер L):** Вынести build-сайдкар в composite action `.github/actions/build-sidecar/action.yml` и подключать из обоих workflow через `uses: ./.github/actions/build-sidecar`. Это требует рефакторинга структуры.

**Краткосрочный inline fix (применён):** Добавить `pip uninstall` шаг в `release.yml` build-sidecar, выровняв его с `sidecar-build.yml`. Это закрывает dev-deps pollution без архитектурного рефакторинга.

**Effort inline fix:** S | **Effort composite action:** L

---

### A-3 — macOS ad-hoc codesign использует `|| true` (ошибки игнорируются)

**Severity:** High  
**Категория:** Reliability / Security  
**Описание:** `release.yml` строка 193:
```yaml
codesign --force --deep --sign - src-tauri/binaries/aurora-sidecar-${{ matrix.target }} || true
```
`|| true` глушит все ошибки codesign, включая критические (binary не найден, нет entitlements для нужных capabilities, сломанный sidecar). При ошибке codesign шаг «падает» в зелёный, Tauri build продолжается с неподписанным sidecar. Пользователи на macOS получат Gatekeeper prompt или полный отказ запуска.

**Доказательство:** `release.yml` строки 191–193.

**Предлагаемое исправление:** Разделить на два шага:
1. Попытка ad-hoc sign с явной обработкой exit code и диагностическим выводом.
2. Если codesign доступен — обязательный (без `|| true`). Если CI runner не имеет codesign (Linux leg) — skip через `if: startsWith(matrix.os, 'macos')` (уже есть).

Применено — добавлен явный exit code check без `|| true`. Для pilot/internal коммент остаётся.

**Effort:** S

---

### A-4 — pyproject.toml `requires-python` указывает `>=3.11,<3.13`, но test-release тестирует только 3.12

**Severity:** High  
**Категория:** Reliability / Test Coverage  
**Описание:** `pyproject.toml` строка 10: `requires-python = ">=3.11,<3.13"` — продукт официально поддерживает Python 3.11 и 3.12. `release.yml` job `test-release` (строка 86): `python-version: ['3.12']` — тестируется только 3.12. В `ci.yml` (не scope данного аудита) матрица вероятно включает 3.11, но это CI для dev-веток. Release pipeline должен верифицировать ВСЕ поддерживаемые версии перед тегом.

При выпуске на 3.11 можно неожиданно получить break от syntax/API разницы (например, `tomllib` module path changes, f-string edge cases, Pydantic v2 cpython optimizations).

**Доказательство:**  
- `pyproject.toml` строка 10: `requires-python = ">=3.11,<3.13"`  
- `release.yml` строки 84–86: `matrix: python-version: ['3.12']`

**Предлагаемое исправление:** Добавить `'3.11'` в matrix `python-version`:
```yaml
python-version: ['3.11', '3.12']
```
Применено в `release.yml`.

**Effort:** S

---

## MEDIUM

### B-1 — Нет кэширования PyInstaller build cache

**Severity:** Medium  
**Категория:** Performance  
**Описание:** Оба workflow используют `cache: pip` для Python packages, но PyInstaller имеет собственный analysis cache (`~/.pyinstaller/` на POSIX, `%APPDATA%\pyinstaller` на Windows). При повторных запусках без изменений spec-файла PyInstaller перезапускает весь analysis (~20–40s на matrix leg). `actions/cache` с ключом на хеш spec-файла + pyproject.toml сократит время build-sidecar на 30–60s на runner.

**Доказательство:** `sidecar-build.yml` строки 71–76: только `cache: pip`. Нет `actions/cache` для PyInstaller dirs.

**Предлагаемое исправление:**
```yaml
- name: Cache PyInstaller
  uses: actions/cache@v4
  with:
    path: |
      ~/.pyinstaller
      %APPDATA%\pyinstaller
    key: pyinstaller-${{ matrix.os }}-${{ hashFiles('packaging/aurora-sidecar.spec', 'pyproject.toml') }}
    restore-keys: pyinstaller-${{ matrix.os }}-
```
Добавить перед шагом `Build sidecar binary` в оба workflow.

**Effort:** S

---

### B-2 — Concurrency группа release-${{ github.ref }} не защищает от workflow_dispatch конкуренции

**Severity:** Medium  
**Категория:** Reliability  
**Описание:** `release.yml` строки 39–41:
```yaml
concurrency:
  group: release-${{ github.ref }}
  cancel-in-progress: false
```
При `workflow_dispatch` `github.ref` = `refs/heads/main` (или другая ветка). Если два ручных запуска запустятся одновременно с разными `inputs.version`, они войдут в ОДНУ concurrency group (оба ref = main), второй будет ждать первого. Это допустимо (`cancel-in-progress: false`), но неочевидно — два dispatch для разных версий не могут параллелиться. Кроме того, при tag push и одновременном dispatch ref разные → они не блокируют друг друга → риск race condition в Vercel env push.

**Предлагаемое исправление:** Изменить group key для лучшей изоляции:
```yaml
group: release-${{ github.ref }}-${{ github.sha }}
```
Или для dispatch через inputs.version:
```yaml
group: release-${{ github.event.inputs.version || github.ref }}
```

**Effort:** S

---

### B-3 — Updater manifest: platform key использует `.msi` и `.exe` из одного glob

**Severity:** Medium  
**Категория:** Reliability  
**Описание:** `release.yml` строки 244–248 (Python скрипт):
```python
if fname.endswith(('.msi', '.exe')):
    key = 'windows-x86_64'
```
Tauri на Windows создаёт ДВА артефакта: `.exe` (NSIS installer) и `.msi` (WiX installer — если включён). Оба попадут в glob `*.sig`. Если в `bundle.targets` есть оба, последний перезапишет первый в `platforms['windows-x86_64']`. В текущем `tauri.conf.json` (`targets: ["nsis", "dmg", "appimage", "deb"]`) — только NSIS, без MSI, поэтому критичности нет. Но при добавлении `wix` target поведение молчаливо сломается.

**Доказательство:** `tauri.conf.json` строка 39: `"targets": ["nsis", "dmg", "appimage", "deb"]` — MSI отсутствует, риск отложен. Python скрипт `release.yml` строки 244–248 не обрабатывает multiple Windows targets.

**Предлагаемое исправление:** Разделить ключи: `windows-x86_64-nsis` для `.exe`, `windows-x86_64-msi` для `.msi`. Или добавить `assert` что found не более одного Windows installer sig.

**Effort:** S (при добавлении MSI target)

---

### B-4 — Path filter в sidecar-build.yml не покрывает `src/aurora_launch/` (не sidecar-only)

**Severity:** Medium  
**Категория:** Reliability  
**Описание:** `sidecar-build.yml` строки 26–31:
```yaml
paths:
  - 'src/aurora_launch/sidecar/**'
  - 'packaging/aurora-sidecar.spec'
  - 'pyproject.toml'
  - '.github/workflows/sidecar-build.yml'
```
Trigger пропускает изменения в `src/aurora_launch/engines/**` и `src/aurora_launch/schemas/**` — эти модули импортируются sidecar (видно из `aurora-sidecar.spec` строки 46–67: `hiddenimports` включает `aurora_launch.engines.*`, `aurora_launch.schemas.*`). Изменение в `engines/launch_forecast.py` без изменения `sidecar/` не триггерит пересборку binary — старый binary может уйти в main.

**Предлагаемое исправление:** Добавить к paths:
```yaml
- 'src/aurora_launch/engines/**'
- 'src/aurora_launch/schemas/**'
```

**Effort:** S

---

## LOW

### C-1 — `actions/setup-python@v5` без SHA-pin в release.yml build-sidecar

**Severity:** Low  
**Категория:** Security  
**Описание:** В `release.yml` header коммент (строки 11–12) утверждает «First-party actions/* keep major-tag pins (lower hijack risk + auto patch)». Это обоснование корректно — `actions/*` управляются GitHub и имеют более строгий процесс выпуска чем community actions. SHA-pin для `actions/setup-python@v5` не является необходимостью, но стоит зафиксировать это решение в комментарии явно как исключение из политики SHA-pin.

**Доказательство:** `release.yml` строки 89, 117: `actions/setup-python@v5` без SHA.

**Предлагаемое исправление:** Добавить комментарий `# first-party GitHub action — major-tag pin accepted per audit policy`.

**Effort:** XS (cosmetic, но документирует security decision)

---

### C-2 — Vercel redeploy шаг не проверяет завершение деплоя

**Severity:** Low  
**Категория:** Reliability  
**Описание:** `release.yml` строки 349–397: после POST на `/v13/deployments` workflow не ожидает статус `READY`. Redeploy запускается и workflow продолжается, не зная завершился ли деплой. Комментарий в строке 395–396 объясняет это как приемлемое («Edge functions cycle within 10 минут»), но при мониторинге пайплайна через GitHub Actions статус будет «green» пока Vercel ещё перезагружается.

**Предлагаемое исправление:** Добавить polling loop (до 5 минут) проверяющий `GET /v13/deployments/{id}` до статуса `READY`. Или принять текущее поведение как документированный trade-off (fire-and-forget).

**Effort:** M

---

### C-3 — `pub_date` в updater manifest использует `os.popen('date -u ...')` вместо Python stdlib

**Severity:** Low  
**Категория:** Reliability  
**Описание:** `release.yml` строка 260:
```python
'pub_date': os.popen('date -u +%Y-%m-%dT%H:%M:%SZ').read().strip(),
```
`os.popen` запускает shell `date` command. На Windows этот шаг выполняется на ubuntu-latest runner (`publish` job), поэтому `date` доступен. Но если runner когда-либо сменится на Windows — команда сломается. `datetime.now(timezone.utc).strftime(...)` — stdlib Python и работает везде.

**Предлагаемое исправление:**
```python
from datetime import datetime, timezone
'pub_date': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
```

**Effort:** XS

---

## COSMETIC

### D-1 — Job name в sidecar-build.yml содержит `${{ matrix.target }}-${{ matrix.arch }}`

**Severity:** Cosmetic  
**Категория:** UX  
**Описание:** `sidecar-build.yml` строка 39: `name: ${{ matrix.target }}-${{ matrix.arch }}`. Target уже содержит arch (`x86_64-unknown-linux-gnu`), поэтому `arch` поле (`x86_64`) дублируется. В GitHub Actions UI job называется `x86_64-unknown-linux-gnu-x86_64` — избыточно.

**Предлагаемое исправление:** Упростить до `name: ${{ matrix.target }}` или `name: sidecar (${{ matrix.target }})`.

**Effort:** XS

---

### D-2 — `validate` job не проверяет soответствие версии в `tauri.conf.json`

**Severity:** Cosmetic  
**Категория:** Reliability  
**Описание:** `release.yml` строки 67–74: проверяется соответствие тега и `pyproject.toml`, но не `src-tauri/tauri.conf.json`. В `tauri.conf.json` сейчас `"version": "0.1.0"` (строка 4) — отдельное поле. При bump только pyproject без tauri.conf Tauri bundle создаст installer с неверной версией.

**Предлагаемое исправление:** Добавить в validate job:
```bash
TAURI_VER=$(python -c "import json; print(json.load(open('src-tauri/tauri.conf.json'))['version'])")
if [ "$TAURI_VER" != "$TAG_VER" ]; then
  echo "ERROR: tauri.conf.json version '$TAURI_VER' != tag '$TAG_VER'"; exit 1
fi
```

**Effort:** S

---

## Applied Fixes Log

| Finding | File | What changed | Lines affected |
|---|---|---|---|
| A-1 | `release.yml` | Добавлен smoke test step в build-sidecar | после строки 126 |
| A-2 | `release.yml` | Добавлен `pip uninstall dev deps` step перед pyinstaller | после строки 125 |
| A-3 | `release.yml` | Убран `|| true`, добавлен explicit exit code check | строка 193 |
| A-4 | `release.yml` | Добавлен `'3.11'` в python-version matrix test-release | строка 86 |

---

## Architectural Notes

1. **Главный архитектурный долг — отсутствие composite action.** Сейчас `release.yml` и `sidecar-build.yml` — два отдельных workflow с дублирующейся сборкой. Правильное решение (backlog B-1 архитектурный): `_sidecar-build.yml` как reusable workflow (`workflow_call` trigger) или `.github/actions/build-sidecar/action.yml` как composite action. Тогда `sidecar-build.yml` и `release.yml` оба вызывают один источник истины. Оценка effort: L (~4–6ч включая тестирование).

2. **sidecar-build.yml запускается при tag push независимо от release.yml.** Это означает, что при выпуске тега запускаются ОБА workflow параллельно, производя идентичные артефакты в двух разных контекстах. Артефакты из `sidecar-build.yml` никуда не публикуются (нет publish job) — они просто растрачивают 4 × runner minutes. После реализации composite action, `sidecar-build.yml` следует исключить из tag trigger (`tags: ['v*']`).

3. **tauri.conf.json `pubkey: "EMBED_AT_RELEASE_TIME"`** (строка 77) — placeholder, реальный ключ инъектируется через `AURORA_UPDATER_PUBKEY` env в build-app step (строка 199). Это корректная практика, но требует документирования в onboarding — новый разработчик может быть сбит с толку placeholder.
