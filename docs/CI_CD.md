# Aurora Launch — CI/CD Reference

## Workflow Overview

| Файл | Триггер | Назначение |
|---|---|---|
| `ci.yml` | push/PR → main | Python lint + pytest 3.11/3.12 × 3 OS + corpus reproducibility |
| `test.yml` | push/PR → main | Rust cargo, Frontend Vitest+svelte-check, Cloud Edge Functions |
| `sidecar-build.yml` | push main/tags + paths | PyInstaller per-OS sidecar binary |
| `release.yml` | tag push `v*` | Full release: test → sidecar → app → publish |
| `bench.yml` | PR → main | Pilot flow cold start performance gate |

---

## Matrix: Python pytest (ci.yml)

```
OS:      ubuntu-22.04 | macos-14 | windows-2022  (→ latest alias в test-release job)
Python:  3.11 | 3.12
```

- Authoritative Python runner. `test.yml` не запускает Python pytest (audit M1-WORKFLOW-7).
- Coverage upload только с `ubuntu-latest + py3.11` (избегаем дублирования артефактов).
- `pymc` / `pytensor` входят в runtime deps — Bayesian engine доступен на всех OS.

---

## Matrix: Frontend (test.yml)

```
OS:  ubuntu-22.04 | macos-14 | windows-2022
```

Node.js 20 с `npm ci`. Запускает `gen:tokens → svelte-check → vitest`. Три OS проверяют
platform-specific npm/node поведение (symlinks, path separators, esbuild binary selection).

---

## Rust (test.yml)

Только `ubuntu-22.04`. Причина: `libwebkit2gtk-4.1-dev` + GTK stack доступны только через
`apt`. macOS и Windows Rust validation происходит в `release.yml build-app` (полный
`tauri build`). Cargo check + cargo test --lib покрывают unit-level logic.

Если в будущем нужна Windows/macOS Cargo проверка на PR — добавить отдельный job без
GTK зависимостей через `cargo check --target <triple> --no-default-features`.

---

## PyInstaller: cross-platform sidecar (sidecar-build.yml)

### Почему нельзя cross-compile

PyInstaller встраивает Python интерпретатор + все импортируемые пакеты в один бинарник.
Результирующий бинарник привязан к libc/dylib ABI целевой OS. Cross-compilation не
поддерживается PyInstaller — отдельный job на каждой OS обязателен.

### Артефакты (Tauri sidecar naming convention)

| Runner | Артефакт |
|---|---|
| `windows-2022` | `aurora-sidecar-x86_64-pc-windows-msvc.exe` |
| `ubuntu-22.04` | `aurora-sidecar-x86_64-unknown-linux-gnu` |
| `macos-14` (Apple Silicon) | `aurora-sidecar-aarch64-apple-darwin` |
| `macos-13` (Intel) | `aurora-sidecar-x86_64-apple-darwin` |

Tauri sidecar lookup: ищет `src-tauri/binaries/aurora-sidecar-{triple}[.exe]`.
Именно поэтому суффикс = полный Rust target triple.

### Build isolation (HIGH-4)

Два раздельных pip окружения в одном job:
1. `pip install -e ".[dev]"` → запуск pytest (sidecar tests)
2. `pip uninstall pytest pytest-cov ...` + `pip install pyinstaller>=6.0` → PyInstaller build

Цель: не включать dev tooling (pytest/ruff/mypy) в бинарник. Каждый добавленный
import-reachable пакет увеличивает бинарник и attack surface.

---

## Release pipeline (release.yml)

```
validate → test-release (3 OS) → build-sidecar (4 OS) → build-app (4 OS) → publish
```

### build-app: macOS ad-hoc codesign

Для pilot/internal distribution используется ad-hoc подпись (`codesign --sign -`).
Позволяет открыть DMG без Gatekeeper prompt на той же машине. Для публичного
релиза необходима замена на:
- `APPLE_CERTIFICATE` + `APPLE_CERTIFICATE_PASSWORD` (Developer ID Application)
- `xcrun notarytool` для нотаризации

### build-app: Linux outputs

`tauri build` на ubuntu-22.04 генерирует:
- `.AppImage` — universal Linux, не требует установки
- `.deb` — Debian/Ubuntu пакет

Оба собираются в одном job и загружаются в GitHub Release.

### build-app: Windows outputs

`tauri build` на windows-2022 с NSIS генерирует:
- `*_setup.exe` — NSIS installer
- `.msi` — MSI пакет (если включён в `tauri.conf.json`)

### Обязательные Secrets

| Secret | Назначение |
|---|---|
| `AURORA_UPDATER_PUBKEY` | Ed25519 public key для updater |
| `AURORA_UPDATER_PRIVATE_KEY` | Ed25519 private key (Tauri подписывает артефакты) |
| `AURORA_UPDATER_KEY_PASSWORD` | passphrase к private key |
| `VERCEL_TOKEN` | Vercel API token для updater manifest |
| `VERCEL_ORG_ID` | Vercel org |
| `VERCEL_PROJECT_ID` | Vercel project (updater endpoint) |
| `SIDECAR_SMOKE_TOKEN` | Auth token для sidecar smoke test (optional, auto-generated если отсутствует) |

---

## Bench gate (bench.yml)

Запускается на каждый PR. Измеряет холодный старт критического пути:

```
import aurora_launch  +  list_corpus_categories()
```

**Порог:** < 2.0s на ubuntu-22.04 GitHub runner.

Если порог превышен — PR блокируется. Типичные причины регрессии:
- Тяжёлый импорт добавлен на module level в `aurora_launch/__init__.py`
- Новый engine выполняет I/O при импорте (нарушение INV-02)
- Лишние транзитивные зависимости подключены без `TYPE_CHECKING` guard

Локальный запуск:
```bash
pip install -e .
python tools/bench_pilot_flow.py --limit 2.0
```

Расширение bench (POST_PILOT_BACKLOG):
- Full forecast bench (OLS + Bayesian) — ориентир <30s на ubuntu
- Corpus reproducibility timing
- Memory peak (PyMC chain allocation)

---

## Примерное время CI на PR

| Workflow | Jobs | ~Минуты |
|---|---|---|
| `ci.yml` | lint + test 6 cells + corpus | ~12–18 мин (параллельно) |
| `test.yml` | rust + frontend×3 + cloud | ~8–12 мин (параллельно) |
| `bench.yml` | cold-start | ~3–4 мин |
| **Итого PR** | | **~18–22 мин** (bottleneck: ci test matrix) |

Release дополнительно:
| Workflow | Jobs | ~Минуты |
|---|---|---|
| `release.yml` | validate + test×3 + sidecar×4 + app×4 + publish | ~35–50 мин |

---

## Cross-platform compatibility: потенциальные проблемы

| Область | Платформа | Риск | Митигация |
|---|---|---|---|
| `pathlib.Path` separator | Windows | `\\` vs `/` в строках | Уже используется `pathlib` — ОК |
| `tempfile` permissions | macOS (arm64) | SIP ограничения в `/tmp` | `tempfile.mkdtemp()` корректно |
| `msgpack` binary wheel | macos-14 | Нет wheel → build from source | Добавить `--only-binary=:all:` если медленно |
| PyMC / PyTensor | Windows | Опциональные C-extensions | `pip install pymc` включает prebuilt wheels |
| npm symlinks | Windows | NTFS symlinks требуют elevation | `npm ci` через git-bash (actions default) — ОК |
| `codesign` ad-hoc | macOS | Только для build-machine open | Задокументировано; pilot scope OK |
| Tauri GTK | Linux | `libwebkit2gtk-4.1-dev` apt-only | Явно установлен в build-app + test.yml rust jobs |
