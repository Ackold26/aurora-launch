# Aurora Launch

**MMM forecasting product для запуска новых брендов via ad-hoc proxy intake.**

Phase B Aurora Analytics Suite product. Spec: [`03_Architecture/PHASE_B_REQUIREMENTS.md`](03_Architecture/PHASE_B_REQUIREMENTS.md).

## Status

- v0.1.0-b05 — Sprint B0.5 implementation (BC Test Corpus & Format Adapters + Reproducibility CLI)
- Phase B B1-B6 sprints — pending Phase A Weeks 4-7 completion

## Что внутри

```
aurora-launch/
├── 00_Overview/               Принципы, roadmap, product boundaries
├── 01_Concept/                Multi-proxy UX decision rules
├── 02_Data_Spec/              Pydantic schemas SSoT
├── 03_Architecture/           Architecture decisions, math reference
│   ├── decisions/             ADRs
│   ├── PHASE_B_REQUIREMENTS.md  ⭐ Implementation contract
│   └── PROXY_INTAKE_PROTOCOL.md  ⭐ D002 — ad-hoc proxy intake workflow
├── 04_Sprints/                Pilot client plan
├── 05_Sessions/               Session logs
├── 06_References/             Pricing, sales playbook, audit reports
├── src/aurora_launch/         Implementation
│   ├── engines/               Math + business logic
│   ├── tools/                 CLI tools
│   └── schemas/               Pydantic models
└── tests/                     Tests + synthetic corpus fixtures
```

## Quick start

```bash
# Install
uv sync --all-extras

# Run tests
uv run pytest

# Generate synthetic corpus project
uv run aurora-corpus generate fmcg_food_snacks_savoury baseline --seed 42 --output ./test_project.aurora

# Verify reproducibility of an .aurora bundle
uv run aurora-launch-reproduce <bundle.aurora> <expected_hash>
```

## Запуск для разработки

Зависит от `uv` (см. https://docs.astral.sh/uv/) и Python 3.11+.

```bash
# Полная установка (включая dev-зависимости и опциональные группы)
uv sync --all-extras

# Запуск всех тестов
uv run pytest

# Параллельный прогон (быстрее на больших наборах)
uv run pytest -n auto

# Только определённый файл
uv run pytest tests/test_sidecar_protocol_server.py -v

# С покрытием кода
uv run pytest --cov=aurora_launch --cov-report=term-missing
```

### Линтеры и проверки типов перед коммитом

```bash
# Форматирование и быстрые проверки
uv run ruff check .
uv run ruff format --check .

# Проверка типов
uv run mypy src/aurora_launch
```

### Запуск sidecar локально

```bash
# Sidecar читает JSON-RPC со stdin, отдаёт ответ в stdout
echo '{"id":1,"method":"ping","params":{},"auth":"<token>"}' | \
  AURORA_SIDECAR_TOKEN=<token> uv run python -m aurora_launch.sidecar
```

### CLI-инструменты

| Команда | Назначение |
|---|---|
| `aurora-corpus generate <category> <variant>` | Генерация синтетического тестового корпуса |
| `aurora-launch-reproduce <bundle> <hash>` | Проверка репродуцируемости бандла по хэшу |
| `aurora-launch-detect <file>` | Распознавание формата входного файла |

Полный список: `uv run python -c "import aurora_launch.cli; ..."` или `pyproject.toml` секция `[project.scripts]`.

## Структура хранилища

| Директория | Содержание |
|---|---|
| `00_Overview/` | Принципы продукта, roadmap, границы охвата |
| `01_Concept/` | UX-решения для multi-proxy intake |
| `02_Data_Spec/` | Pydantic-схемы (источник истины) |
| `03_Architecture/` | Архитектурные решения, ссылки на математику |
| `03_Architecture/decisions/` | ADR (Architecture Decision Records) |
| `03_Architecture/PHASE_B_REQUIREMENTS.md` | ⭐ Контракт реализации Phase B |
| `03_Architecture/PROXY_INTAKE_PROTOCOL.md` | ⭐ D002 — рабочий процесс ad-hoc proxy intake |
| `04_Sprints/` | План пилотных клиентов, спринт-логи |
| `05_Sessions/` | Логи рабочих сессий по разработке |
| `06_References/` | Pricing, sales playbook, аудиторские отчёты |
| `Final/` | Финальные документы (deployment, installer) |
| `src/aurora_launch/` | Реализация |
| `src/aurora_launch/engines/` | Математика + бизнес-логика |
| `src/aurora_launch/sidecar/` | JSON-RPC сервер для общения с Tauri-оболочкой |
| `src/aurora_launch/tools/` | CLI-инструменты |
| `src/aurora_launch/schemas/` | Pydantic-модели |
| `tests/` | Тесты + синтетические тестовые фикстуры |
| `migrations/` | SQL-миграции для Supabase |

## Содействие проекту

Перед серьёзными правками — обязательное чтение `aurora-meta/ENGINEERING_INVARIANTS.md` (живой документ инженерных уроков; pre-flight read mandatory). Особое внимание:

- **ИНВ-05** — криптографические утверждения требуют атакующего сценария первым
- **ИНВ-09** — verify config consumption end-to-end до объявления готовым
- **ИНВ-13** — verify infrastructure assumptions (`pip install -e .` ≠ `uv sync`; `cargo test` ≠ `wasm-pack test`)
- **ИНВ-15** — adapter wiring path completeness end-to-end

Стиль коммитов: `<тип>(<охват>): <краткое описание>` в imperative mood.
Пример: `feat(sidecar): graceful shutdown drains in-flight forecasts`.

Сообщения коммитов на английском (стандарт open-source); комментарии в коде — русский или английский по контексту.

## Architectural foundation

- **D002 restored:** ad-hoc proxy intake (no donor library) per `03_Architecture/PROXY_INTAKE_PROTOCOL.md`
- **Trust Stack (CP-1):** every artifact signed Ed25519, every result reproducible, every metric с uncertainty
- **Privacy by Architecture (CP-4):** local-first, data never leaves customer machine
- **Reproducibility Ceremony (CP-7):** Methodology Certificate as artifact, public WASM verifier on `verify.auroraai.pro`

См. `03_Architecture/PHASE_B_REQUIREMENTS.md` §1 для full Cross-cutting Principles.

## Dependencies

- Python 3.11+
- aurora-platform-core v0.1.0+ (path-based dev, git+https in release)
- Phase A components: aurora_inference, aurora_studio, aurora_schema_registry

## License

Proprietary. Aurora Analytics, 2026.
