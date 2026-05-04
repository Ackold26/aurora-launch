# Phase A — Requirements (7 Components)

**Status:** Draft v0.1 (2026-05-05) — Маша маленькая. Финальная версия в `aurora-meta/SPECS/PHASE-A.md` (доработка Маши небесной с sales/marketing/risks углами).

**Что это:** детальный спек 7 компонентов Aurora Phase A платформы — extracted core (Inference Core + Data Studio + Workflow Engine), shell-уровень (Tauri shell template + Common Services + Schema Registry / cross_app_license), и доверительный layer (Web verifier для Methodology Certificate).

**Источник истины:**
- Aurora Эконометрика current production code (`D:/Docs/Aurora_Ai/Dev/Aurora_Econometrica/`) — extraction baseline для Inference Core, Reporting layer, Sidecar pattern.
- Aurora Launch `03_Architecture/REUSE_FROM_ECONOMETRICA.md` — Launch consumer requirements.
- Aurora Data Studio `03_Architecture/REUSE_FROM_ECONOMETRICA.md` — Studio additive requirements.
- 5 ADRs от Маши небесной в `aurora-knowledge/Decisions/` (pending 2026-05-11): aurora-studio-freemium-strategy, aurora-studio-positioning-infrastructure-not-free, aurora-launch-as-econometrica-upsell, methodology-certificate-public-web-verifier, launch-demo-strategy-real-client-data-first.
- 1 architecture file от Маши небесной: `phase-a-future-monetization-scaffold.md`.
- Memory: `project_econometrica_target_architecture_v3.md`, `project_econometrica_phase2_planning_mode.md`, `project_aurora_launch_principles.md`, `project_aurora_data_studio_concept.md`.

**Допущения (если изменятся — переделать spec):**
- A1. Phase A starts after Aurora Эконометрика v1.2.0 commercial ship (math-fix-v1.0.13 → main merge).
- A2. Aurora Launch Phase B requires ALL 7 Phase A components shipped + regression GREEN на Aurora Эконометрика as Aurora Optimize rebrand.
- A3. Aurora Data Studio Phase A scope = Этап 1 (per Маша небесная strategic correction 2026-05-05). НЕ defer'ится в Q1 2027. Defer'ится только Studio Pro standalone (Этап 2).
- A4. Single-platform Python sidecar pattern сохраняется — НЕ multi-process / NЕ remote inference в Phase A.
- A5. Windows-only Phase A (consistent с Эконометрика production). Mac/Linux deferred Phase D+.
- A6. Multi-tenant cloud — out of scope Phase A. Local-first default.

**Глобальные DoD invariants** (применяются ко всем 7 компонентам):
- Code merged в main + tagged + push.
- Pytest suite extended, parallel-runnable, 80%+ coverage of public API surface.
- Integration test against Aurora Эконометрика regression corpus (Кагоцел + Венарус) — pass.
- API documented в `aurora-platform-core/docs/<component>.md` (markdown с примерами).
- Released as semver-versioned package (`aurora-platform-core==0.1.0` initial).
- ADR'ы для irreversible decisions добавлены в `aurora-knowledge/Decisions/`.
- CHANGELOG entry с миграционными нотами для consumer apps (Эконометрика / Launch / Studio).

**Component dependency graph:**

```
                    ┌─────────────────────────────────┐
                    │  C6  Schema Registry + license  │
                    └──┬───────────────────────────┬──┘
                       │ (schema versioning)       │ (license tier scaffolding)
                       ▼                           ▼
   ┌───────────────────────────┐         ┌─────────────────────┐
   │  C1  Inference Core       │         │  C5  Common Services│
   │  (Bayesian/OLS engines)   │         │  (Auth/License/Upd) │
   └───┬──────────────┬────────┘         └────────┬────────────┘
       │              │                            │
       ▼              ▼                            ▼
   ┌─────────┐   ┌──────────────┐         ┌───────────────────┐
   │ C2 Data │   │ C3 Workflow  │         │ C4 Tauri shell    │
   │ Studio  │   │ Engine       │         │ template          │
   └────┬────┘   └──────┬───────┘         └─────────┬─────────┘
        │               │                            │
        └───────────────┴────────────┬───────────────┘
                                     │
                                     ▼
                       ┌───────────────────────────────┐
                       │  C7 Web verifier              │
                       │  (verify.auroraai.pro WASM)   │
                       └───────────────────────────────┘
```

**Build order:** C6 (foundation) → C1 + C5 (parallel) → C2 + C3 + C4 (parallel after C1+C5) → C7 (last, needs C1 hash output spec).

---

## Component 1: Inference Core

**Goal:** Extract Aurora Эконометрика's MMM math layer в standalone Python package `aurora-platform-core` (sub-package `aurora_inference`). Этот компонент — ядро всех 5+1 Suite apps; его API — единственный contract для Bayesian/OLS моделирования, decomposition, optimization, scenario analysis, conformal prediction, awareness modeling, и causal layer.

### 1.1 Scope

**Входит:**

| Module (extracted) | Source path в Эконометрике | Public API surface | Breaking changes vs source |
|---|---|---|---|
| `aurora_inference.modeler` | `sidecar/econometrica/engines/modeler.py` (1216 LOC) | `train_model(config, project_dir, progress_callback) -> dict`, `check_compiler() -> bool`, `get_mcmc_params(has_compiler) -> dict` | Никаких. 1:1 extract. |
| `aurora_inference.ols_modeler` | `engines/ols_modeler.py` (509) | `train_ols(...)`, `recommend_engine(n_obs, override) -> dict` | Никаких. 1:1. |
| `aurora_inference.decomposer` | `engines/decomposer.py` (738) | `decompose(...)`, `compute_roi_verdict(...)` | Никаких. 1:1. |
| `aurora_inference.optimizer` | `engines/optimizer.py` (1403) | `optimize(config, project_dir) -> dict` (+ private adstock/mROAS helpers exposed как internal API) | Никаких. 1:1. |
| `aurora_inference.scenario` | `engines/scenario.py` (740) | `predict_scenario(...)`, `delete_scenario(...)`, `compare_scenarios(...)` | Никаких. |
| `aurora_inference.validator` | `engines/validator.py` (419) | `detect_column_role`, `detect_column_role_with_confidence`, `detect_adstock_type`, `detect_date_frequency`, `compute_histogram`, `data_preview`, `validate_data` | **Move:** `data_preview` и `validate_data` функции остаются Inference-API; column role detection + histogram → дублируются в `aurora_data_studio.validators` (С2) с unified contract. |
| `aurora_inference.persistence` | `engines/persistence.py` (352) | `load_model_with_compat`, getters: `get_kpi_type`, `is_awareness_model`, `get_adstock_type`, `get_weibull_params`, `has_baseline_posterior`, `get_baseline_posterior`, `get_feature_flags`, `get_channel_categories`, `get_training_granularity`, `infer_granularity_at_load`, `get_seasonality`, `infer_seasonality_at_load`, `get_x_norm_quantiles`, `infer_x_norm_quantiles_at_load`, `is_hierarchical_model` | **Move:** `load_model_with_compat` BFS migration logic → переезжает в C6 SchemaRegistry. Persistence helpers остаются + import из C6. |
| `aurora_inference.awareness` | `engines/awareness.py` (189) | `s_curve(x, L, k, x0)`, `forecast_awareness(...)`, `awareness_to_sales(...)` | Никаких. |
| `aurora_inference.adstock_selector` | `engines/adstock_selector.py` (131) | `select_adstock_type(...)` (auto adstock detection) | Никаких. |
| `aurora_inference.backtest` | `engines/backtest.py` (257) | `backtest(...)` (rolling-origin validation) | Никаких. |
| `aurora_inference.channel_action` | `engines/channel_action.py` (363) | `compute_channel_action_summary(...)` (Block C/D refactor v1.0.16) | Никаких. |
| `aurora_inference.causal` | `engines/causal/` (DiD/SCM/CausalForest + preflight + common + _panel_data) | `causal_preflight(...)`, `causal_did(...)`, `causal_scm(...)`, `causal_forest(...)`, `causal_consistency(...)` | Никаких. 1:1. |
| `aurora_inference.conformal` | `engines/conformal.py` (Sprint 1.5 ship) | `ConformalCalibrator.calibrate_ols(...)`, `ConformalCalibrator.calibrate_bayes(...)` | Никаких. |
| `aurora_inference.trust3_hierarchical` | существующий код в modeler.py для hierarchical priors brand vs perf | `build_hierarchical_priors(channel_categories, ...)`, `extract_hierarchical_warnings(...)` | **Refactor:** выделить в отдельный submodule (currently embedded в `train_model`). |
| `aurora_inference.kpi_registry` | существующий KPI configs (sales / awareness frozen в v1.2.0 foundation) | `get_kpi_config(kpi_type) -> KPIConfig`, `register_kpi(...)`, frozen `KPI_SALES` + `KPI_AWARENESS` | **New module** (configs существуют, но не organized как registry). |

**API contract style:** все top-level public функции принимают `config: dict` (Pydantic v2 internal validation) + `project_dir: str` + optional `progress_callback`, возвращают `dict[str, Any]` (JSON-serializable, schema documented). Это сохраняет sidecar IPC contract.

**Не входит (deferred / out-of-scope Phase A):**
- ❌ Pricing math (cross-price elasticity, profit optimum) — Aurora Pricing Phase C, новый module.
- ❌ Multi-output модель (cannibalization / halo) — Aurora Portfolio Phase D.
- ❌ Forward-buy lag math — Aurora Promo Phase C, дополнение.
- ❌ Joint Bayesian для proxy → recipient — Phase D revisit per ADR-003.
- ❌ Time-varying coefficients (DLM premium avatar C) — отложено per `project_econometrica_premium_avatars.md`.
- ❌ Aurora Launch–specific extensions (`launch_adapt`, `launch_validators`, `single_proxy_transfer`, `multi_proxy_hierarchical`, `launch_posterior_update`, `launch_forecast`, `launch_conformal`, `similarity_calculator`) — Aurora Launch repo, Phase B.
- ❌ Reporting (HTML/PPTX/XLSX) — НЕ часть Inference Core. Reuse как Reporting Studio (deferred sub-component, in-scope Phase A через separate package `aurora_reporting`, координируется с C2/C3).
- ❌ Server.py FastAPI handlers — переезжают в C3 (Workflow Engine) как HTTP/IPC adapter layer.
- ❌ JAX compiler check / vswhere logic — остаётся как-есть, helper functions internal.

### 1.2 Acceptance Criteria (Given / When / Then)

**AC1.1 — Pure extraction, zero functional drift.**
- GIVEN Aurora Эконометрика regression corpus (Кагоцел trained model `.pickle` + Венарус trained model + 4 ROSST_AI test fixtures).
- WHEN `aurora_inference.modeler.train_model(config, project_dir)` invoked с identical config (extracted from Эконометрика regression test).
- THEN output dict has identical keys (`model_data`, `metrics`, `diagnostics`, etc.) и numerical values match Эконометрика baseline within `rtol=1e-6` for deterministic seeds (NumPyro fixed `random.PRNGKey(42)`), and within `rtol=1e-3` for stochastic comparisons (Gelman-Rubin, ESS).

**AC1.2 — Public API stability contract.**
- GIVEN `aurora_inference` package installed at version 0.1.0.
- WHEN consumer imports `from aurora_inference import modeler, decomposer, optimizer, scenario, validator, persistence, awareness, conformal, causal, trust3_hierarchical, kpi_registry`.
- THEN all imports succeed; `dir()` of each module exposes documented public surface (Section 1.1 table); `from aurora_inference import __version__` returns "0.1.0".

**AC1.3 — Backwards compat для existing .pickle models.**
- GIVEN existing Aurora Эконометрика project с `.aurora` или legacy `.pickle` (schema_version 1.0 / 2.0).
- WHEN `aurora_inference.persistence.load_model_with_compat(path)` invoked.
- THEN model loads без errors; `SchemaRegistry.migrate(data, target_version="3.0")` (C6) auto-applied; getter helpers (`get_kpi_type`, `is_hierarchical_model`, etc.) return correct values для legacy + current schemas.

**AC1.4 — Trust 3 hierarchical priors callable как separate API.**
- GIVEN channel_categories dict with brand vs performance assignments.
- WHEN consumer calls `aurora_inference.trust3_hierarchical.build_hierarchical_priors(channel_categories, prior_config)` standalone (вне `train_model`).
- THEN returned PriorConfig dict matches priors that `train_model` would inject; consumer может pass priors to custom `modeler.train_model` invocation (для Aurora Launch transfer learning use case Phase B).

**AC1.5 — Conformal Prediction triple-CI работает out-of-the-box.**
- GIVEN trained Bayesian model + calibration set (20% holdout).
- WHEN `aurora_inference.conformal.ConformalCalibrator.calibrate_bayes(model, calibration_data)` invoked.
- THEN returns ConformalCI dict с `lower`, `upper`, `coverage_level` (default 0.9), и intervals tighter than naive ±2σ (Aurora differentiator validated).

**AC1.6 — KPI Registry pattern enforces frozen configs.**
- GIVEN KPI_SALES config (frozen v1.2.0).
- WHEN consumer attempts `kpi_registry.KPI_SALES.likelihood_family = "negbinom"`.
- THEN `pydantic.ValidationError: cannot mutate frozen config` raised. `kpi_registry.get_kpi_config("sales")` returns same Pydantic instance (singleton).

**AC1.7 — Causal layer integration test.**
- GIVEN preflight-passing dataset с known DiD treatment effect (synthetic ground truth).
- WHEN `aurora_inference.causal.causal_did(config, project_dir)` invoked.
- THEN returns ATE estimate within ±5% of synthetic ground truth (existing test corpus в Эконометрике passes); placebo test fails при random treatment assignment.

**AC1.8 — Awareness pipeline reusable.**
- GIVEN sales-only model trained.
- WHEN consumer calls `aurora_inference.awareness.forecast_awareness(config, project_dir)` followed by `awareness_to_sales(...)`.
- THEN returns awareness trajectory + sales lift attributable to awareness; matches Aurora Brand v1.2.0 dual-posterior reference output.

**AC1.9 — Optimizer constraint API explicit.**
- GIVEN `optimize(config, project_dir)` call с `config["constraints"]` containing per-channel mins/maxes + total budget cap + per-group constraints.
- WHEN optimizer runs.
- THEN result respects all constraints (no channel выше max, total = budget cap ±0.1%); per-group precedence order applied (3-level: per-channel > per-group > global per `project_econometrica_v1_2_0_foundation`).

**AC1.10 — JAX compiler fallback graceful.**
- GIVEN Windows machine без MSVC compiler.
- WHEN `aurora_inference.modeler.check_compiler()` returns `False`, then `train_model(...)` invoked.
- THEN training completes through CPU-only NumPyro path (slower but functional); `result["diagnostics"]["compiler_warning"]` flag set; CHANGELOG note for Aurora app's user-facing message.

### 1.3 Definition of Done

- [ ] **AC1.1–AC1.10 все pass** (см. Section 1.4 для test data).
- [ ] **Code merged в `aurora-platform-core` main** + tag `aurora-platform-core/v0.1.0`.
- [ ] **Pytest suite migration:** existing 838 Aurora Эконометрика pytest cases migrated к `aurora-platform-core/tests/inference/`. Parallel-runnable (`-n auto`). Coverage `aurora_inference` package ≥ 80% (line + branch).
- [ ] **Integration regression:** Aurora Эконометрика v1.0.16 → переключение на `aurora-platform-core==0.1.0` (depend как `pip install`) + full regression GREEN на Кагоцел + Венарус corpus. Baseline metrics (R², MAPE, posterior predictive p-value) match within `rtol=1e-6`.
- [ ] **API docs:** `aurora-platform-core/docs/inference.md` — public API reference с примерами (минимум 1 working example per module).
- [ ] **Migration guide:** `aurora-platform-core/docs/migration_v0.0_to_v0.1.md` — для Aurora Эконометрика maintainer + Aurora Launch / Studio consumer.
- [ ] **CHANGELOG entry:** `aurora-platform-core/CHANGELOG.md` v0.1.0 section.
- [ ] **ADR:** `aurora-knowledge/Decisions/aurora-platform-core-package-extraction.md` (Accepted) — extraction rationale + module boundaries + breaking changes catalog.
- [ ] **Pickle/`.aurora` schema_version ≥ 3.0 после extraction** — bumped через C6 SchemaRegistry. Existing v2.0 `.pickle` files auto-migrate at load.
- [ ] **CI:** GitHub Actions workflow для `aurora-platform-core` runs pytest + lint (ruff) + type check (mypy на public API).

### 1.4 Test Data Requirements

**Synthetic (CI-friendly, fast):**
- `tests/fixtures/synthetic_mmm_minimal.json` — 52 weeks, 3 channels, 1 KPI sales, known coefficients (для exact recovery test, AC1.1 stochastic part).
- `tests/fixtures/synthetic_mmm_hierarchical.json` — 104 weeks, 8 channels (4 brand + 4 performance), Trust 3 ground truth (для AC1.4).
- `tests/fixtures/synthetic_did_panel.json` — DiD panel data с known ATE = 0.15 (для AC1.7).
- `tests/fixtures/synthetic_awareness_trajectory.json` — known Weibull adstock + S-curve params (для AC1.8).

**Real anonymized (slower, ground truth = production accepted):**
- `tests/fixtures/kagocel_v1.0.16_baseline.pickle` — anonymized Кагоцел trained model (per donor anonymization protocol Section 3 of DONOR_LIBRARY_SHORTLIST). Used as **acceptance** baseline для `rtol=1e-6` numeric comparison.
- `tests/fixtures/venarus_v1.1.0_baseline.pickle` — anonymized Венарус (PREMIUM tier categorical contrast).

**Edge cases (regression registry):**
- Hierarchical N=1 channel category degeneracy (audit-fixed v1.0.16) — must NOT silently fail.
- F1 cumulative anchor convention (audit-fixed) — backend + Rust adstock factor agreement.
- Untrained-channel guard (decomposer) — return `None` ROI, не NaN.
- Y_actual truncation discrepancy (`project_econometrica_y_actual_truncation_investigation`) — Phase 2.7 backend audit deliverable; pickle `y_actual` length consistency check.
- Lift formula canonical ratio (`project_econometrica_lift_formula_audit`) — backend + frontend `predictKPI` whatif must agree within ±0.5 п.п.
- XLSX export columns for v1.0.13 (`project_econometrica_xlsx_export_issues`) — confirms Inference Core output shape consistent (CI=0/Δ=0/efficiency=0 issue is Excel writer side, not Inference; AC validates Inference output integrity).

**Property-based tests (Hypothesis):**
- Adstock Toeplitz convolution: shape preservation across bin-size changes.
- Hill saturation monotonicity: `f(x1) <= f(x2)` для `x1 <= x2` всегда.
- Optimizer constraint satisfaction: random feasible constraint sets always yield feasible solutions or explicit infeasibility errors.
- BFS schema migration idempotency: `migrate(migrate(data))` == `migrate(data)`.

### 1.5 Зависимости

**Внутренние (другие Phase A компоненты):**
- **Зависит от:** C6 (Schema Registry) — `load_model_with_compat` использует `SchemaRegistry.migrate()` для BFS path resolution. C1 в production callable только after C6 v0.1 published.
- **Не зависит от:** C2/C3/C4/C5/C7. Inference Core — pure math layer, не имеет UI/IPC/Auth/license зависимостей. License gate накладывается consumer apps на vызов `train_model` etc.

**Блокирует:**
- C2 (Data Studio) — bundle composer пишет model artifacts (`.aurora/models/*.pickle`) created by Inference Core. Studio Phase A scope требует stable `aurora_inference.persistence` API.
- C3 (Workflow Engine) — workflow steps invoke Inference Core functions. YAML config schema references `aurora_inference.<module>.<function>` callable IDs.
- C4 (Tauri shell) — sidecar Python process shipper bundles `aurora-platform-core` deps (PyInstaller spec). Shell template build pipeline assumes stable package.
- C5 (Common Services) — license check decorator wraps Inference Core callables (`@license_required("inference.train")`); needs stable API surface.
- C7 (Web verifier) — `MethodologyCertificate` PDF embeds `engine_version = aurora_inference.__version__` + parameter hashes from `aurora_inference.persistence`. Verifier WASM compares hashes — stable serialization required.
- Aurora Launch B0.5+ (downstream Phase B) — Launch's `engines/launch_adapt.py`, `launch_validators.py`, etc. import `aurora_inference.modeler`, `decomposer`, `conformal`, `trust3_hierarchical`. Phase B cannot start без C1 ship.
- Aurora Эконометрика → Aurora Optimize rebrand — same.

**Внешние:**
- **NumPyro >= 0.13, JAX >= 0.4.20** — pinned в `requirements.txt`. JAX CPU-only build для Windows compat.
- **PyMC >= 5.10** — для backup engine + dual-posterior path (per `project_econometrica_v1_2_0_foundation`).
- **scikit-learn >= 1.4** — OLS modeler.
- **pandas >= 2.1, numpy >= 1.26** — standard.
- **Pydantic v2** — config validation + KPI registry (`@frozen=True` поддержка).
- **MSVC** (опционально) — для NumPyro JAX faster compilation на Windows; fallback на CPU NumPyro если отсутствует (AC1.10).

**Координационные:**
- **Маша небесная ADR:** `aurora-knowledge/Decisions/aurora-platform-core-package-extraction.md` — needs её sign-off на module boundary decisions (что extracted vs что оставлено в Aurora app repos).
- **Антон approval:** breaking changes в `validator.py` (column role detection split между C1 и C2) — нужен confirmation что Эконометрика UI не сломается. Mitigation: оба места экспортируют identical contract; deprecation cycle 1 minor для consumer choice.

### 1.6 Open questions для Маши небесной

1. **Reporting Studio scope в Phase A:** в этом spec'е Reporting (`aurora_html`, `aurora_pptx`, Rust XLSX writer) явно вынесен из Inference Core. Где он живёт? Предложение: отдельный `aurora-platform-core` sub-package `aurora_reporting`, in-scope Phase A но как **Component 1.5** (sub-component, not separate Phase A item — потому что 7 Phase A items уже locked). Альтернатива: оставить в Aurora Эконометрика repo и не extract'ить (но это блокирует Aurora Launch B4 reuse template).
2. **Awareness в Inference Core?** Awareness math (`s_curve`, Weibull adstock, dual-posterior) сейчас в `engines/awareness.py` Эконометрики. Это специфика Aurora Brand. Оставить в Inference Core (per Suite shared platform principle) или вынести в Aurora Brand-specific module? Default здесь: оставить в Inference Core, потому что Aurora Launch awareness ramp-up workflow тоже использует.
3. **Channel categorization auto-suggestion (`auto_suggest_categories` server endpoint):** это inference layer или Data Studio? Сейчас в server.py FastAPI route. Default predложение: extract в `aurora_inference.trust3_hierarchical.suggest_categories(...)` (math layer), HTTP shell остаётся в C3.
4. **JAX MSVC compiler dependency:** ship'аем pre-compiled JAX wheels внутри `aurora-platform-core` PyPI artifact (heavy ~200 MB) или оставляем `pip install jax[cpu]` user step? Default: included Windows wheels (per Aurora Эконометрика 189 MB installer pattern).

---

## Component 2: Data Studio

**Goal:** Доставить Aurora Data Studio Этап 1 scope (per Маша небесная strategic correction 2026-05-05) — task-aware AI data preparation infrastructure, accessible всем покупателям Suite. Studio превращает разрозненные XLSX/CSV файлы (DSM Group, Mediascope AdEx, Mediascope TV Index Polometers, DigitalBudget, custom client XLSX) в canonical `.aurora` bundle, готовый к consumption любым econometric app в Suite (Optimize / Launch / Brand / Pricing / Promo / Portfolio).

### 2.1 Scope

**Входит (Этап 1 freemium с Suite):**

#### 2.1.A Source adapters (Tier 1 heuristic + signature match)

Per Studio repo `engines/source_adapters/` (planned layout, см. Studio REUSE Section "Reuse Map (что новое)"). Module-per-source:

| Module | Source | Format variants supported | Studio repo spec |
|---|---|---|---|
| `aurora_data_studio.source_adapters.dsm_group` | DSM Group monthly XLSX | V2023, V2024 (per Aurora Launch DSM_FIELDS.md) | already documented |
| `aurora_data_studio.source_adapters.mediascope_adex` | Mediascope AdEx | V1 ISO datetime single-sheet, V2 «Jan 2024» abbreviated, V3 multi-sheet с `;` разделителями (per v0.3 real corpus 2026-05-04) | spec v0.2 в `02_Data_Spec/MEDIASCOPE_ADEX_FIELDS.md` |
| `aurora_data_studio.source_adapters.mediascope_tv_index` | Mediascope TV Index Polometers | V1 Week range «DD.MM.YYYY - DD.MM.YYYY», multi-row header (R1=audience labels, R2=column names), variable audience count 2-4+, «Channek» typo signature | spec v0.1 в `02_Data_Spec/MEDIASCOPE_TV_INDEX_FIELDS.md` |
| `aurora_data_studio.source_adapters.digitalbudget` | DigitalBudget category exports | TBD — спека ещё не написана (Q3 partial: 2 of 4 sources closed) | **Phase A deliverable spec** |
| `aurora_data_studio.source_adapters.custom_xlsx` | Generic fallback (Tier 2 LLM-driven) | Любой XLSX через Phi-3.5-mini structural inference | depends на 2.1.B |

**Adapter contract** (base class `aurora_data_studio.source_adapters.adapter_contract.SourceAdapter`):
```python
class SourceAdapter(ABC):
    source_id: str  # "dsm_group", "mediascope_adex", etc.

    @abstractmethod
    def detect(self, file_path: Path) -> DetectResult:
        """Return confidence score 0-1 + variant id (V1/V2/V3) или None."""

    @abstractmethod
    def parse(self, file_path: Path, variant: str | None = None) -> AdapterResult:
        """Parse в canonical schema. Variant from detect() или auto."""

    @abstractmethod
    def supported_variants(self) -> list[str]:
        """V1, V2, ..."""
```

`AdapterResult` Pydantic v2 model — canonical output schema (см. 2.1.D).

#### 2.1.B AI parser stack (Tier 1 / Tier 2 / Tier 3)

Per ADR-001 `tiered-hybrid-ai-parser`:

- **Tier 1 — Heuristic + signature match.** `aurora_data_studio.source_adapters.<src>` runs first. Filename pattern + header pattern + cell signature (e.g., AdEx weights summing to 1.0) → high-confidence match (≥ 0.85). Fast (< 100 ms per file). Default for all 5 known sources.
- **Tier 2 — Local LLM.** `aurora_data_studio.engines.llm_parser` — llama.cpp wrapper around Phi-3.5-mini Q4 GGUF (~2.5 GB installer overhead, 4-6 GB RAM при inference). Used когда Tier 1 confidence < threshold (e.g., custom client XLSX без known signature). Local-only (privacy-first для фарма/financial ICP). Output: `WorkbookInference` Pydantic model (см. Studio existing `engines/llm_parser/output_models.py`).
- **Tier 3 — Cloud LLM (opt-in).** `aurora_data_studio.engines.cloud_parser` — Anthropic SDK wrapper, default OFF. Toggle в Settings + per-session confirm. PII redaction layer (regex + structural rules) обязательная pre-processing (см. 2.1.G privacy).

**Tier escalation rules** (per ADR-001):
- Tier 1 confidence ≥ 0.85 → use Tier 1 result.
- 0.50 ≤ confidence < 0.85 → fall through Tier 2.
- Tier 2 confidence ≥ 0.70 → use.
- < 0.70 (или Tier 2 disabled) → fall through Tier 3 (если opt-in) или surface к user через MappingReviewStep.

**Pydantic output models** (already drafted в Studio repo):
- `ColumnInference(BaseModel)` — per-column inferred role + canonical_field_id + confidence.
- `SheetStructuralInference(BaseModel)` — sheet boundaries, header rows, data rows, frozen rows.
- `WorkbookInference(BaseModel)` — multi-sheet aggregate.
- `FieldMappingRequest/Response(BaseModel)` — refinement loop.
- `TierAuditEntry(BaseModel)` — audit trail (which tier produced which decision).

**41 canonical fields registry** — Studio existing draft. Phase A in-scope: финализировать registry + freeze schema.

#### 2.1.C Task profiles + Spec engine

Per Studio `04_Task_Profiles/` — 6 apps × N tasks taxonomy, ~20 YAML files. Already started: `aurora_optimize/budget_optimization.yaml` (proof-of-concept full spec).

| App folder | Sample tasks (Phase A in-scope) | Status |
|---|---|---|
| `aurora_optimize/` | budget_optimization, scenario_what_if, reach_planning | 1 done, 2 pending |
| `aurora_launch/` | new_brand_forecast, paused_brand_relaunch | 0 done, 2 pending |
| `aurora_brand/` | awareness_modeling, brand_to_sales_bridge | 0 done, 2 pending |
| `aurora_pricing/` | (Phase C) | out of scope Phase A |
| `aurora_promo/` | (Phase C) | out of scope Phase A |
| `aurora_portfolio/` | (Phase D) | out of scope Phase A |

**Phase A deliverable:** 7 task profile YAMLs (3 Optimize + 2 Launch + 2 Brand). Pricing/Promo/Portfolio task profiles — pending Phase C/D.

**Spec engine API:**
```python
# aurora_data_studio.engines.task_specs

def load_task_spec(app: str, task: str, version: str | None = None) -> TaskSpec:
    """Load YAML, validate схема, return Pydantic TaskSpec."""

def compatibility_matrix(spec: TaskSpec) -> dict[str, list[str]]:
    """Return canonical_field → list of source_ids that can provide it."""

def must_have_check(spec: TaskSpec, available_fields: set[str]) -> CheckResult:
    """Pass/fail + missing must-have list + nice-to-have suggestions."""
```

#### 2.1.D Bundle composer

`aurora_data_studio.engines.bundle_composer` — пишет `.aurora` bundle (ZIP container per Aurora Launch ADR-002).

```
my_project.aurora (ZIP)
├── manifest.json           # SSoT: bundle_metadata, schema_version, hashes
├── data/
│   ├── canonical_schema.parquet  # tidy-format unified data
│   ├── source_audit.json          # per-source provenance
│   └── quality_gates.json         # pass/warn/fail per gate
├── models/                  # populated по completed inference (Inference Core C1)
│   └── *.pickle
├── forecasts/               # populated by horizon-specific runs
│   └── horizon_NNw.pickle
└── signature.txt            # SHA-256 hash of contents
```

API:
```python
def compose(
    canonical_data: pd.DataFrame,
    task_spec: TaskSpec,
    sources: list[SourceProvenance],
    quality_results: list[QualityGateResult],
    output_path: Path,
) -> ComposeResult:
    """Atomic write: .aurora.tmp → atomic rename → 4-deep .bak rotation."""
```

Schema versioning через C6 SchemaRegistry (combined v3.0 fields с Aurora Launch — см. C6).

#### 2.1.E Quality gates

`aurora_data_studio.engines.quality_gates` — per Studio ROADMAP S4:

| Gate | Check | Severity levels |
|---|---|---|
| Coverage gate | Data range vs spec required range (e.g., 52 weeks for adstock identification) | pass / warn / fail |
| Anomaly gate | Outliers (z-score > 4), missing periods, duplicates | warn / fail |
| Lineage gate | Provenance chain integrity (source files exist, hashes match) | fail only |
| Unit consistency gate | All numeric columns в task spec canonical_units | warn / fail |
| Cross-source coherence gate | E.g., DSM sales vs Mediascope TV airing periods overlap ≥ 80% | warn |

Customizable thresholds per task (defined в YAML task profile).

#### 2.1.F Cabinets / UI flow (7 Svelte cabinets)

Per Studio wireframes folder (already drafted ASCII layouts):

1. `TaskSelectStep` — app + task choice (decision tree, mode toggle Assisted/Expert).
2. `DataSpecStep` — must-have / nice-to-have checklist auto-rendered from task spec YAML.
3. `UploadStep` — drag-drop file upload + tier badges per file.
4. `MappingReviewStep` — AI suggestion table (column → canonical_field) + manual override.
5. `QualityGatesStep` — pass/warn/fail dashboard.
6. `BundleExportStep` — provenance preview + `.aurora` export.
7. `AdvancedSettingsStep` — cloud opt-in, mode toggle, telemetry opt-in.

**Premium UX requirements** (per `UX_PRINCIPLES.md`):
- Dual-mode persona (Assisted = менеджер по рекламе / Expert = эконометрист), sticky per user.
- WCAG AA contrast verification.
- Aurora Hybrid Design System tokens (Sacred Lime + Aurora Deep + Gold).
- Per-app accent (Studio = Sacred Lime primary).
- Lora display + Inter body + JetBrains Mono.

#### 2.1.G Privacy invariants (критично для фарма ICP)

Per Studio existing PRINCIPLES P5-P7:
1. **Default = no data leaves machine.** Tier 1 + Tier 2 fully local.
2. **Cloud Tier 3 — opt-in.** Toggle в Settings, default OFF.
3. **PII redaction обязательная** перед каждым cloud call (regex layer + structural rules: brand names, manufacturer names, contact info, IBAN/INN patterns).
4. **No model training on customer data.** Phi pretrained, Anthropic terms — no training (verified в ADR-001).
5. **Audit trail.** Redaction log + tier decisions saved per session, accessible через `AdvancedSettingsStep` → "Open audit log".

#### 2.1.H Telemetry events (Phase A scaffolding для Этапа 2)

Per coordination doc Section 4 (`COORDINATION_WITH_DATA_STUDIO.md`):

Studio events: `studio.task_selected`, `studio.source_uploaded`, `studio.format_variant_detected`, `studio.mapping_intervention`, `studio.quality_gate_result`, `studio.bundle_exported`, `studio.cloud_optin_toggle`, `studio.pro_feature_gated`.

Storage: local `~/.aurora/telemetry/events.jsonl` + opt-in batched send. Default OFF (фарма ICP privacy concern).

#### 2.1.I Feature flags scaffolding

Per `aurora-knowledge/Architecture/phase-a-future-monetization-scaffold.md` (Маша небесная pending). All Pro-кандидат features помечены flag'ом, на Этапе 1 включены:
- `studio.feature.multi_project_workspace` = True (Этап 1) / TBD Этап 2.
- `studio.feature.advanced_charts` = True (Этап 1).
- `studio.feature.pdf_export_quality_report` = True (Этап 1).
- `studio.feature.team_collaboration` = True (Этап 1).
- `studio.feature.tier3_cloud_unlimited` = True (Этап 1) / TBD Этап 2 (cap?).

**Не входит (Этап 2 / out-of-scope Phase A):**
- ❌ Multi-project workspaces UI (cross-project navigation cabinet).
- ❌ Team collaboration (shared mappings, review workflows, comments).
- ❌ PDF export reports beyond MethodologyCertificate (data quality executive summary, lineage diagrams).
- ❌ Tier 3 cloud unlimited usage (Phase A: opt-in + capped).
- ❌ Custom connector SDK (1С / SAP / GA4 / Yandex.Wordstat / Mediascope BrandPulse adapter authoring tooling).
- ❌ Per-tier UI отличия (free/pro/team/agency badge gating).
- ❌ Payment integration / paywall UX.
- ❌ Bundle pricing скидки Launch+Studio (отменены — Studio = инфраструктура per Маша небесная).

### 2.2 Acceptance Criteria (Given / When / Then)

**AC2.1 — Tier 1 happy path: known source.**
- GIVEN валидный DSM Group monthly XLSX (Кагоцел fixture, V2024 variant).
- WHEN user в UploadStep drag-drop'ает файл.
- THEN `dsm_group.detect()` returns confidence ≥ 0.95 + variant "V2024"; `dsm_group.parse()` produces canonical schema rows; UI badge "DSM Group ✓ V2024" green; время от upload до success badge < 2 секунды.

**AC2.2 — Tier 2 fallthrough: unknown XLSX.**
- GIVEN custom client XLSX (e.g., 1С-стиль фарма sales report) без known source signature.
- WHEN user uploads.
- THEN Tier 1 confidence < 0.85 → Tier 2 invoked → Phi-3.5-mini Q4 inference returns `WorkbookInference` с per-column `ColumnInference` (canonical_field_id + confidence); UI MappingReviewStep shows AI suggestions + manual override option.

**AC2.3 — Tier 3 opt-in only с PII redaction.**
- GIVEN Settings "Enable cloud parser (Tier 3)" toggle = ON, sample XLSX с brand names + manufacturer names в content.
- WHEN parser falls through к Tier 3.
- THEN before HTTP request: PII redaction log shows replaced strings (e.g., "Кагоцел" → "[BRAND_1]", "Materia Medica" → "[MANUFACTURER_1]"); request to Anthropic API contains только redacted version; response un-redacted local-side через mapping table.

**AC2.4 — Mediascope AdEx 3 variants robust detection.**
- GIVEN 3 fixture files: V1 (ISO datetime, 63K rows, Пиво безалкогольное), V2 («Jan 2024» abbreviated, 9.7K rows, Недвижимость Тюмень), V3 (multi-sheet с `;` разделителями, 100K+ rows, ТЦ + Туризм).
- WHEN sequentially uploaded.
- THEN each detected с correct variant; `;`-разделители в Advertisers/Article columns split правильно; multi-sheet detection: Sheet1 (summary) деdup'ится против category sheets; canonical schema output identical structure across 3 variants.

**AC2.5 — Mediascope TV Index multi-row header.**
- GIVEN PaloMars Тюмень file с 3 audiences (включая «All 25-55 BC» Broadcast Coverage), R1=audience labels, R2=column names, «Channek» typo signature.
- WHEN parsed.
- THEN R1+R2 merged correctly (e.g., "All 25-55 BC.Reg. Stand. TVR (20)" canonical column name); duration normalization preserved (Reg. TVR vs Reg. Stand. TVR (20)); audience assignment в `audience_id` column.

**AC2.6 — Task spec must-have validation.**
- GIVEN task spec `optimize.budget_optimization.v1` (must_have: sales_target + ad_spend_by_channel min 2 channels min 52 periods).
- WHEN user uploads only sales_target file (no ad spend).
- THEN `must_have_check` returns `passed=False` + `missing=["ad_spend_by_channel"]`; UI DataSpecStep shows red checkmark на ad_spend_by_channel + suggested sources `[mediascope_adex, digitalbudget, custom_xlsx]`.

**AC2.7 — Bundle composer atomic write + ZIP integrity.**
- GIVEN composed canonical data + provenance + quality results.
- WHEN `bundle_composer.compose(output_path="my_project.aurora")` invoked.
- THEN `.aurora.tmp` written first, atomic rename к `.aurora`, previous version moved к `.aurora.bak.1` (rolling 4 backups); SHA-256 signature in manifest.json matches recomputed hash; `unzip + cat manifest.json` works на любой машине без Python.

**AC2.8 — Quality gates: warn vs fail behavior.**
- GIVEN bundle с partial coverage (45 weeks vs 52 required) + 1 outlier (z=4.5).
- WHEN quality gates run.
- THEN Coverage gate = warn (45 < 52, but ≥ 80%); Anomaly gate = warn (1 outlier, < 5% threshold); Lineage gate = pass; UI QualityGatesStep allows proceeed-with-warning (yellow banner) + capture decision в audit trail.

**AC2.9 — Bundle reading by Aurora Launch.**
- GIVEN `.aurora` bundle composed by Studio v0.1.0 для task `launch.new_brand_forecast.v1`.
- WHEN Aurora Launch ProxySelectionStep imports the bundle.
- THEN Launch reads через `aurora_data_studio.engines.bundle_composer.read()` (or shared `aurora-platform-core` reader); SchemaRegistry.migrate ensures forward-compat; `bundle_metadata.target_app == "launch"` validation passes; data accessible для proxy candidate scoring.

**AC2.10 — Privacy invariant audit (no leakage Tier 1+2 mode).**
- GIVEN Tier 3 cloud OFF in Settings (default), full Studio session с 5 source uploads + bundle export.
- WHEN network monitoring runs (e.g., Wireshark / Fiddler) during session.
- THEN no outbound HTTP requests к anthropic.com / google.com / любым third-party (только Supabase license heartbeat + auto-update check, документированы в C5); telemetry если enabled — только к auroraai.pro telemetry endpoint, payload anonymized per spec.

### 2.3 Definition of Done

- [ ] **AC2.1–AC2.10 все pass.**
- [ ] **Code merged в `aurora-data-studio` main** + tag `v0.1.0`. Aligned с `aurora-platform-core==0.1.0` (C1) deps.
- [ ] **Source adapters: 4 production-ready** (DSM, Mediascope AdEx 3 variants, TV Index, DigitalBudget — Phase A spec). Custom XLSX — Tier 2 fallthrough only.
- [ ] **Tier 2 LLM integration:** Phi-3.5-mini Q4 GGUF model packaged с installer (~2.5 GB overhead documented in INSTALL.md). llama.cpp wrapper functional на Windows. Cold start < 30 сек, warm inference < 5 сек на 1 sheet.
- [ ] **Tier 3 cloud:** Anthropic Haiku integration с PII redaction layer + audit trail. Toggle UI в AdvancedSettingsStep.
- [ ] **Task profiles:** 7 YAMLs (3 Optimize + 2 Launch + 2 Brand) ship'нуты в `04_Task_Profiles/`. Schema validation passes для всех.
- [ ] **41 canonical fields registry** finalized + frozen (`engines/llm_parser/canonical_fields.py`). Doc'd в `02_Data_Spec/CANONICAL_FIELDS.md`.
- [ ] **Pytest suite:** 100+ tests, parallel-runnable. Fixtures: synthetic 10 wild XLSX (existing) + real corpus 5 files (existing) + edge cases (multi-sheet, mixed RU/EN, vertical layout, merged cells). Coverage ≥ 80%.
- [ ] **Property-based tests:** adapter idempotency (parse twice = same canonical), JSON round-trip (Pydantic models serialize/deserialize losslessly), multi-sheet detection (Sheet1 dedup vs category sheets).
- [ ] **Brier Score eval methodology** (per existing `engines/llm_parser/eval_methodology.md`): Phi-3.5-mini calibration measured против golden labels на 10 synthetic + 5 real corpus. Brier Score < 0.15 for accepted ship.
- [ ] **API docs:** `aurora-data-studio/docs/api.md` + per-cabinet UX docs.
- [ ] **CHANGELOG entry.**
- [ ] **ADRs:**
  - `aurora-knowledge/Decisions/aurora-data-studio-canonical-fields-registry.md` (frozen schema rationale).
  - Studio existing ADR-001 (tiered hybrid AI) + ADR-002 (standalone SKU bundle activation) + ADR-003 (floating license) — verified Accepted.
  - New ADR `aurora-data-studio-phase-a-etap-1-scope.md` documenting Маша небесная strategic correction 2026-05-05.
- [ ] **NSIS installer** (Windows): Studio.exe + Phi-3.5-mini Q4 GGUF model bundled OR downloaded on first run (decision: bundled — simpler UX, larger installer ~2.7 GB total).
- [ ] **Privacy audit report:** independent review (manual or via Маша небесная) confirming AC2.10 invariant — no data leaves machine in default config.

### 2.4 Test Data Requirements

**Synthetic (CI-friendly):**
- `tests/fixtures/synthetic/` — already exists в Studio repo: 10 wild XLSX (фарма 1С-стиль, FMCG clean, multi-sheet, mixed RU/EN, vertical layout, agency media plan, e-com emoji, B2B wide-format, telecom ARPU, P&L с merged cells) + `golden_labels.json` (canonical answer key per file).

**Real corpus (anonymized):**
- `tests/fixtures/real/mediascope_adex/` — 3 файла per v0.3 (Пиво / Недвижимость Тюмень / ТЦ-Туризм multi-sheet).
- `tests/fixtures/real/mediascope_tv_index/` — 2 файла PaloMars (Казань-Пермь-Нижний / Тюмень).
- `tests/fixtures/real/dsm_group/` — Кагоцел + Венарус anonymized DSM extracts.
- `tests/fixtures/real/digitalbudget/` — **Phase A deliverable: 1-2 sample exports от Антона** (currently missing, см. Q3 partial pending).
- `tests/fixtures/real/custom_xlsx/` — **Phase A deliverable: 3-5 client XLSX** (currently missing).

**LLM eval corpus:**
- `tests/llm_eval/golden_labels.json` — ground truth для each file (canonical_field per column).
- `tests/llm_eval/brier_score_runner.py` — eval methodology runner (per existing `eval_methodology.md`).

**Property-based / fuzz:**
- Hypothesis strategies для random XLSX structure (variable header rows, merged cells, mixed types).
- ZIP integrity fuzz: random file inserts/deletes должны faithful surface через signature mismatch.

**Edge cases registry:**
- Multi-sheet AdEx с Sheet1 = summary duplicate → dedup'ится.
- TV Index с «Channek» typo → handled (vendor signature).
- File с emoji в column names (e-com fixture) → UTF-8 preservation.
- Windows cp1251 ↔ UTF-8 conversion (existing UTF-8 fix per v0.2).
- 100K+ rows file (ТЦ-Туризм) → memory profile peak < 2 GB.

### 2.5 Зависимости

**Внутренние:**
- **Зависит от:** C1 Inference Core (`aurora_inference.persistence` для bundle reader compat), C6 Schema Registry (combined v3.0 schema migration).
- **Зависит от Studio existing:** wireframes (7 ASCII layouts done), HTML mockups (TaskSelectStep + MappingReviewStep done), `engines/llm_parser/` skeleton (Pydantic output_models + prompt templates done), TestData/Studio/synthetic/ (10 XLSX done), 01_Concept/ docs (CONCEPT_FLOW + DECISION_TREES + CONVERSION_FUNNEL done).
- **Не зависит от:** C3 Workflow Engine (Studio имеет свой UI flow, не workflow-engine-driven), C4 Tauri shell (Studio = standalone Tauri app, использует shell template как parent но не блокируется).

**Блокирует:**
- Aurora Launch B0.5 — Launch consumes `.aurora` bundle from Studio. Adapter package (`source_adapters/`) — Studio team owns, Launch consumes. Launch B0.5 cannot start без Studio adapters shipping.
- Aurora Launch B1 — pickle schema v3.0 extension uses combined fields (Studio + Launch). Schema bumps coordinated.
- All Suite apps — `.aurora` bundle = canonical input format.

**Внешние:**
- **llama-cpp-python >= 0.2.50** — Phi-3.5-mini wrapper. Pinned.
- **anthropic >= 0.30** — SDK для Tier 3.
- **openpyxl >= 3.1, pyarrow >= 14.0, pandas >= 2.1** — XLSX/Parquet I/O.
- **Phi-3.5-mini Q4 GGUF** — bundled с installer, source: HuggingFace `microsoft/Phi-3.5-mini-instruct` Q4_K_M quantization.
- **Pydantic v2** — output models + adapter contract.

**Координационные:**
- **Маша небесная ADRs:** 4 strategic ADRs про Studio + 1 architecture file (phase-a-future-monetization-scaffold) — pending 2026-05-11 deadline.
- **Антон approval:** financial trade-off "bundled installer +2.5 GB" vs "first-run download" (default proposal: bundled, simpler UX). Также: tier 3 cloud LLM cost projections (capped vs unlimited на Этапе 1).
- **Coordination doc:** `COORDINATION_WITH_DATA_STUDIO.md` (committed `b523758`, draft v0.1) — adapter ownership, versioning, telemetry events. Final в `aurora-meta/COORDINATION-LAUNCH-STUDIO.md`.

### 2.6 Open questions для Маши небесной

1. **DigitalBudget адаптер spec — где брать тестовые файлы?** Q3 partial: 2 of 4 sources закрыты (AdEx + TV Index), DigitalBudget + 3-5 custom XLSX pending. Нужен запрос Антону на предоставление samples (1-2 DigitalBudget exports + 3-5 client XLSX). Без этих fixtures Phase A AC2.6 + adapter ship невозможны.

2. **Phi-3.5-mini bundling: installer +2.5 GB vs first-run download?** Default proposal: bundled (simpler UX, no internet at first run, фарма enterprise IT-policy friendly). Альтернатива: download via background после install (smaller installer, but breaks fully-offline use case). Decision impact: NSIS installer size (Aurora Эконометрика precedent ~189 MB; with Phi → ~2.7 GB total — large but still feasible).

3. **Tier 3 cloud unlimited cap на Этапе 1?** Если Этап 1 = full access всем покупателям Suite, tier 3 cloud = potentially unlimited Anthropic API spend. Нужен soft cap (e.g., 1M tokens / customer / month) с graceful degradation? Или hard cap с paywall? Default proposal: soft cap 500K tokens/customer/month с warning UI на 80% utilization.

4. **Per-app accent color у Studio:** Studio = Sacred Lime primary (per UX_PRINCIPLES). Aurora Launch = Electric Blue. Studio ↔ Launch transitions: navigation между UI должна сохранять continuity. Маша небесная — нужен standardized cross-app navigation pattern (например, breadcrumbs с per-app accent dots) или это можно отложить?

5. **Coordination с Aurora Эконометрика → Aurora Optimize rebrand:** Phase A finalizes Эконометрика как Aurora Optimize. Optimize task profiles (3 в `04_Task_Profiles/aurora_optimize/`) должны быть consistent с Aurora Эконометрика production input contract. Кто ownит alignment — Studio team или Optimize team? Default: Studio task spec — source of truth, Optimize app validates input against spec, breaking changes coordinate через ADR.

---

## Component 3: Workflow Engine

**Goal:** Заменить hardcoded server.py FastAPI handlers Aurora Эконометрика config-driven YAML pipeline orchestrator. Workflow Engine читает декларативный YAML («какие шаги, в каком порядке, какие validators, какие callable refs»), выполняет state machine, публикует HTTP/IPC routes автоматически. Это позволяет spawn новых Aurora apps (Launch / Brand / Optimize) **без копирования server.py logic** — каждый app имеет свой `<app>.workflow.yaml` поверх shared engine.

### 3.1 Scope

**Входит:**

#### 3.1.A YAML schema (Pydantic v2)

Канонический workflow descriptor:

```yaml
id: aurora_launch.new_brand_forecast.v1
schema_version: "1.0"
app: aurora_launch
title: "Прогноз для нового бренда через прокси"
description: |
  Multi-step launch forecasting workflow с proxy adaptation,
  recipient anchors validation, transfer scenarios, posterior update.

# Glob state shared между шагами:
state:
  - name: project_dir
    type: Path
    persistence: project_local
  - name: trained_model_hash
    type: str
    persistence: derivable

steps:
  - id: project_setup
    type: form
    title: "Метаданные проекта"
    schema_ref: aurora_launch.schemas.ProjectMetadata
    transitions:
      success: proxy_selection
      cancelled: __end__

  - id: proxy_selection
    type: cabinet_step
    title: "Выбор прокси-бренда"
    cabinet_ref: ProxySelectionStep      # Svelte component
    requires: [project_setup]
    actions:
      - id: upload_dsm
        type: file_upload
        adapter_ref: aurora_data_studio.source_adapters.dsm_group
        accept: ["xlsx"]
      - id: compute_similarity
        type: callable
        callable_ref: aurora_launch.engines.similarity_calculator.compute
        args_from_state: [proxy_metadata, recipient_metadata]
    validators:
      - validator_ref: aurora_launch.engines.launch_validators.ProxyDataValidator
        on_failure: stay
    transitions:
      success: recipient_anchors
      retry: proxy_selection

  - id: recipient_anchors
    type: form
    schema_ref: aurora_launch.schemas.RecipientAnchorsV1
    requires: [proxy_selection]
    transitions:
      success: transfer_validate

  - id: transfer_validate
    type: composite
    sub_steps:
      - id: extract_priors
        type: callable
        callable_ref: aurora_launch.engines.launch_adapt.extract_proxy_priors
      - id: apply_magnitudes
        type: callable
        callable_ref: aurora_launch.engines.launch_adapt.apply_recipient_magnitudes
      - id: prior_predictive
        type: callable
        callable_ref: aurora_inference.modeler.posterior_predictive
    on_partial_failure: rollback_to_previous_step
    transitions:
      success: train

  - id: train
    type: long_running_callable
    callable_ref: aurora_inference.modeler.train_model
    progress_streaming: enabled
    cancellable: true
    timeout_seconds: 1800
    transitions:
      success: forecast
      timeout: train_recovery

  - id: forecast
    type: callable
    callable_ref: aurora_launch.engines.launch_forecast.generate
    args:
      horizons: [12, 26, 52]
    transitions:
      success: report

  - id: report
    type: artifact_export
    artifact_kind: launch_forecast_report
    formats: [pptx, html, xlsx, pdf_methodology_certificate]
    transitions:
      success: __end__

error_codes:
  ranges:
    - prefix: "L"           # Launch-specific 1000-1999
      from: 1000
      to: 1999
  shared:
    - aurora_inference.error_codes  # Inference Core registry
    - aurora_data_studio.error_codes
```

**Pydantic v2 schema** (`aurora_workflow.schema.WorkflowDefinition`):
- Versioned (`schema_version` field, currently "1.0").
- Strict validation: unknown keys → error; callable_ref / cabinet_ref / adapter_ref must resolve at load time.
- Transitions form a directed graph; cycle detection at load (warn если есть cycles, fail если нет terminal `__end__`).

**Step types:**

| Type | Purpose | Input | Output |
|---|---|---|---|
| `form` | Pydantic schema-validated user input | UI form values | validated dict, persisted в state |
| `cabinet_step` | Svelte UI component с custom interactions | UI events (file upload, button clicks) | side-effects: file uploads, callable invocations |
| `callable` | Single function invocation (synchronous) | args from state / step inputs | dict result, persisted |
| `long_running_callable` | Background task с progress streaming | same as callable | streaming progress + final result |
| `composite` | Sequence of sub-steps в одной transactional unit | inputs to first sub-step | output of last sub-step + on_partial_failure rollback |
| `decision` | Branch на condition (jinja2-style expression evaluating state) | condition expression | next step id |
| `artifact_export` | Write report files | model_data + format list | file paths списком |
| `__end__` | Terminal state | — | — |

#### 3.1.B Workflow Engine API

```python
# aurora_workflow.engine

from pathlib import Path
from typing import Any, Callable, Iterator

class WorkflowEngine:
    """Stateful executor of WorkflowDefinition."""

    @classmethod
    def load(cls, yaml_path: Path) -> "WorkflowEngine":
        """Parse + validate YAML, resolve all *_ref'ы, return engine."""

    def start(self, project_dir: Path) -> WorkflowState:
        """Initialize fresh state, save .workflow_state.json в project_dir."""

    def resume(self, project_dir: Path) -> WorkflowState:
        """Load saved state, validate not corrupted, return state."""

    def current_step(self) -> StepDefinition:
        """Return current active step."""

    def execute_step(self, step_id: str, inputs: dict) -> StepResult:
        """Run single step. Validates pre-conditions (requires), runs validators,
        executes step type's logic, persists state. Returns StepResult."""

    def stream_progress(self, step_id: str) -> Iterator[ProgressEvent]:
        """For long_running_callable steps. Yields ProgressEvent chunks."""

    def cancel_step(self, step_id: str) -> None:
        """Cooperative cancel for long_running_callable."""

    def progress_summary(self) -> ProgressSummary:
        """Total steps, completed, current, estimated_remaining_seconds."""

class StepResult:
    step_id: str
    status: Literal["completed", "failed", "validation_failed", "cancelled"]
    outputs: dict
    next_step_id: str | None
    error_code: int | None      # from registry
    error_message: str | None
    elapsed_seconds: float
```

#### 3.1.C HTTP/IPC adapter

`aurora_workflow.adapters.fastapi`:

```python
def generate_router(workflow: WorkflowDefinition) -> APIRouter:
    """Auto-generate FastAPI router from workflow YAML.

    Routes:
    - POST /workflow/{wf_id}/start                       # → engine.start()
    - POST /workflow/{wf_id}/resume                       # → engine.resume()
    - GET  /workflow/{wf_id}/current                      # → engine.current_step()
    - POST /workflow/{wf_id}/step/{step_id}/execute       # → engine.execute_step()
    - GET  /workflow/{wf_id}/step/{step_id}/progress      # SSE stream → stream_progress()
    - POST /workflow/{wf_id}/step/{step_id}/cancel        # → engine.cancel_step()
    - GET  /workflow/{wf_id}/state                        # → state JSON
    """
```

Это **replaces** existing Aurora Эконометрика server.py FastAPI handlers (`/compute/train`, `/compute/decompose`, etc.) — теперь генерируются из `aurora_optimize.budget_optimization.v1.workflow.yaml`. Эконометрика продолжает работать (backwards compat shim в Phase A): legacy routes proxy к workflow engine.

#### 3.1.D State persistence

`<project_dir>/.workflow_state.json`:
- `workflow_id` + `schema_version`.
- `current_step_id` + `completed_steps[]`.
- `state_dict` (form values, callable outputs, references к saved artifacts).
- `created_at` + `updated_at` ISO timestamps.
- `workflow_state_hash` (SHA-256 of canonical JSON, для tamper detection).
- `error_log[]` — circular buffer last 50 errors с timestamps.

Persisted после каждого `execute_step()` через atomic write + `.bak`.

Compat: state file reading через C6 SchemaRegistry (workflow_state schema versioned alongside `.aurora` bundle).

#### 3.1.E CLI tool

`aurora-workflow` shell command:

```bash
aurora-workflow list                                    # show available workflows
aurora-workflow run <wf_id> --project=PATH             # run interactively (REPL prompts)
aurora-workflow resume --project=PATH                   # resume interrupted
aurora-workflow status --project=PATH                   # show progress summary
aurora-workflow validate <yaml_path>                    # validate YAML без execution
aurora-workflow generate-routes <wf_id> --output=PATH  # generate FastAPI router stub
```

#### 3.1.F Reference workflows ship'ятся в Phase A

3 reference workflow YAMLs (поверх 7 task profile YAMLs из C2):

| Workflow | Path | App | Purpose |
|---|---|---|---|
| `aurora_optimize.budget_optimization.v1.workflow.yaml` | `aurora-platform-core/workflows/` | Optimize | Replicates Aurora Эконометрика current pipeline (validate → train → decompose → optimize → scenario → report) |
| `aurora_launch.new_brand_forecast.v1.workflow.yaml` | same | Launch | Sprint B2-B6 pipeline (proxy_selection → recipient_anchors → transfer_validate → train → forecast → report) |
| `aurora_brand.awareness_modeling.v1.workflow.yaml` | same | Brand | Awareness forecasting + dual-posterior bridge |

#### 3.1.G Error codes registry interop

Existing Aurora Эконометрика `error_codes.py` registry (numeric error codes per `project_econometrica_phase2_planning_mode`) — переезжает в `aurora-platform-core/error_codes.py` shared. Workflow YAML декларирует ranges per app:
- 0-999: Aurora Inference Core (shared).
- 1000-1999: Aurora Launch.
- 2000-2999: Aurora Optimize.
- 3000-3999: Aurora Brand.
- 4000-4999: Aurora Data Studio.
- 5000-5999: Aurora Common Services / Workflow Engine.

При validation YAML загрузки: ranges не overlap.

**Не входит (deferred / out-of-scope Phase A):**
- ❌ Visual workflow editor (drag-drop GUI для YAML construction) — Phase D consideration.
- ❌ Cross-workflow data sharing (Aurora Launch project → Aurora Optimize without re-export) — Phase B feature.
- ❌ Distributed execution (workflow steps on remote workers) — Phase D+.
- ❌ Workflow templating / inheritance (extending base workflow YAML) — Phase B+.
- ❌ Live workflow modification (hot-reload YAML без restart) — operational nice-to-have, deferred.
- ❌ Workflow scheduling (cron-style triggers) — out-of-scope Aurora business model (interactive desktop apps, not server-side jobs).
- ❌ Multi-user simultaneous workflow на same project (collaborative editing) — Phase D+.

### 3.2 Acceptance Criteria

**AC3.1 — YAML schema strict validation.**
- GIVEN malformed workflow YAML (e.g., unknown step type "magic", or transition references missing step_id, or callable_ref не resolves в installed Python packages).
- WHEN `WorkflowEngine.load(yaml_path)` invoked.
- THEN raises `WorkflowValidationError` с specific message (line + column в YAML, what's wrong); no engine instance created.

**AC3.2 — Reference Optimize workflow runs end-to-end.**
- GIVEN `aurora_optimize.budget_optimization.v1.workflow.yaml` + Кагоцел fixture project.
- WHEN engine starts → executes all steps → reaches `__end__`.
- THEN final state matches Aurora Эконометрика v1.0.16 baseline output (model artifacts + report files); no regression vs hardcoded pipeline.

**AC3.3 — State persistence + resume.**
- GIVEN running Aurora Launch workflow at step `train` (long_running_callable, ~10 min).
- WHEN process killed at 50% completion.
- THEN `.workflow_state.json` reflects last completed step (`transfer_validate`); on `resume()`, engine restarts at `train` step (not from beginning); user-visible: "Resuming training from checkpoint" message.

**AC3.4 — Long-running step с progress streaming.**
- GIVEN `train` step (Bayesian MCMC).
- WHEN client connects к SSE endpoint `/workflow/.../step/train/progress`.
- THEN streams ProgressEvent JSON chunks (`{"step": "train", "progress": 0.42, "message": "MCMC sampling chain 2/4", "ts": "..."}`); chunk frequency ≥ every 5 sec; final event `{"status": "completed", "result": {...}}`.

**AC3.5 — Cooperative cancel.**
- GIVEN `train` step running.
- WHEN POST `/workflow/.../step/train/cancel` invoked.
- THEN training stops within 30 sec (cooperative checkpoint); state saved; `current_step` returns `train` status `cancelled`; resume rolls back к previous step.

**AC3.6 — Composite step rollback on partial failure.**
- GIVEN `transfer_validate` composite step с 3 sub-steps.
- WHEN sub-step `apply_magnitudes` fails (RecipientAnchors invalid).
- THEN rollback applied: state at start of `transfer_validate` restored (extract_priors output discarded); next_step = `recipient_anchors` (per `on_partial_failure: rollback_to_previous_step`).

**AC3.7 — FastAPI auto-generation.**
- GIVEN loaded workflow.
- WHEN `generate_router(workflow)` called.
- THEN returns `fastapi.APIRouter` с 7 endpoints (start/resume/current/execute/progress/cancel/state) + auto OpenAPI docs; routes mountable as `app.include_router(router, prefix="/workflow/aurora_launch.new_brand_forecast.v1")`.

**AC3.8 — Error codes namespace isolation.**
- GIVEN two workflows declaring overlapping ranges (Launch claims 1000-2500, Optimize claims 2000-2999).
- WHEN both loaded.
- THEN `WorkflowValidationError: error_code range conflict between aurora_launch (1000-2500) and aurora_optimize (2000-2999)`.

**AC3.9 — Backwards compat shim для Aurora Эконометрика.**
- GIVEN existing Aurora Эконометрика frontend hitting `/compute/train` legacy route.
- WHEN backwards compat shim deployed (Phase A interim).
- THEN request proxied through workflow engine: shim calls `engine.execute_step("train", inputs)` за кулисами, response shape identical к v1.0.16 contract.

**AC3.10 — CLI tool functional smoke test.**
- GIVEN `aurora-workflow` CLI installed.
- WHEN user runs `aurora-workflow validate aurora_launch.new_brand_forecast.v1.workflow.yaml`.
- THEN exits 0 with "Validation OK" message; if invalid YAML — exits 1 с descriptive error.

### 3.3 Definition of Done

- [ ] **AC3.1–AC3.10 все pass.**
- [ ] **Code merged в `aurora-platform-core`** (sub-package `aurora_workflow`) + tagged.
- [ ] **YAML schema** finalized + frozen + documented в `aurora-platform-core/docs/workflow_schema.md`.
- [ ] **3 reference workflow YAMLs** (Optimize budget_optimization + Launch new_brand_forecast + Brand awareness_modeling) — ship'нуты в `aurora-platform-core/workflows/`.
- [ ] **Pytest suite ≥ 60 tests** parallel-runnable. Fixtures: minimal valid workflow + 10+ invalid variants (missing transitions, type errors, ref errors).
- [ ] **Property-based tests:** state persistence idempotency (`load(save(state))` == `state`), workflow graph cycle detection, transition resolution determinism.
- [ ] **Integration test:** Aurora Launch new_brand_forecast workflow runs end-to-end на synthetic recipient + Кагоцел proxy fixture; produces valid `.aurora` bundle.
- [ ] **Backwards compat:** Aurora Эконометрика v1.0.16 legacy frontend → workflow engine shim — все 838 pytest cases pass via shim layer.
- [ ] **CLI tool** `aurora-workflow` installable as console script (`pyproject.toml` entrypoint), shipped с `aurora-platform-core`.
- [ ] **Error codes registry** consolidated в `aurora-platform-core/error_codes.py`, range allocation documented в `aurora-knowledge/Decisions/error-codes-namespace-allocation.md`.
- [ ] **API docs:** OpenAPI spec auto-generated; per-step type docs.
- [ ] **CHANGELOG entry.**
- [ ] **ADR:** `aurora-knowledge/Decisions/aurora-workflow-engine-yaml-driven.md` — rationale + chosen vs alternatives (Airflow / Prefect / Luigi rejected: too heavyweight для desktop app context).
- [ ] **Migration guide для Aurora Эконометрика maintainer:** `aurora-platform-core/docs/migration_econometrica_to_workflow.md` — пошагово как переключить с hardcoded server.py на workflow engine.

### 3.4 Test Data Requirements

**Synthetic workflows (CI-friendly):**
- `tests/fixtures/workflows/minimal_valid.yaml` — 2 steps + 1 transition.
- `tests/fixtures/workflows/all_step_types.yaml` — 1 step per type (form / cabinet / callable / long_running / composite / decision / artifact_export).
- `tests/fixtures/workflows/invalid_*.yaml` — 10+ variations (each broken in 1 specific way).

**Real workflows (regression):**
- 3 production reference workflows (Optimize / Launch / Brand) — must validate + execute end-to-end.

**State file fixtures:**
- `tests/fixtures/states/healthy_state.json` — valid mid-workflow state.
- `tests/fixtures/states/corrupted_*.json` — tamper detection: bad hash, malformed JSON, missing required keys.
- Aurora Эконометрика v1.0.16 production project state (for backwards compat shim test).

**Long-running step simulation:**
- Mock callable that streams progress events at controlled cadence + supports cooperative cancel.

**Property-based tests (Hypothesis):**
- Workflow graph: random step lists с random transitions → engine should detect cycles + missing terminal `__end__`.
- State persistence: random state dicts → save → load → equality.

### 3.5 Зависимости

**Внутренние:**
- **Зависит от:** C1 (Inference Core) — workflow steps reference `aurora_inference.*` callables. Must resolve at load time.
- **Зависит от:** C6 (Schema Registry) — workflow state persistence через versioned schema; reuse BFS migration path.
- **Зависит от:** C5 (Common Services) — `@license_required` decorator wraps callable steps execution.
- **Не зависит от:** C2 (Studio имеет независимый UI flow, не workflow-engine-driven Phase A; возможна интеграция Phase B+ если Studio task profiles адаптируются).
- **Не зависит от:** C4 (Tauri shell) — workflow engine = Python sidecar layer, shell template integrates engine но не блокируется.

**Блокирует:**
- Aurora Эконометрика → Aurora Optimize rebrand (Phase A late milestone) — Optimize uses workflow YAML вместо hardcoded server.py.
- Aurora Launch B2 — Launch UI flow declares в `aurora_launch.new_brand_forecast.v1.workflow.yaml`. B2 ProxySelectionStep cabinet integration через workflow engine.
- Aurora Brand B (Phase B) — same pattern.
- Spawn новых apps (Pricing / Promo / Portfolio Phase C/D) — workflow YAML = primary integration mechanism.

**Внешние:**
- **PyYAML >= 6.0** — YAML parser.
- **Pydantic v2** — schema validation.
- **FastAPI >= 0.110** — HTTP adapter (already used by Эконометрика server.py).
- **SSE-Starlette** — Server-Sent Events для progress streaming.
- **Click >= 8.1** — CLI framework.

**Координационные:**
- **Маша небесная ADR sign-off:** `aurora-workflow-engine-yaml-driven.md` decision.
- **Aurora Эконометрика team:** review backwards compat shim — ensures zero customer-visible regression при v1.0.16 → Optimize rebrand.
- **Аntoн approval:** workflow YAML = primary contract точка для добавления новых apps. Changes ahead require Антон's strategy alignment (новые workflows = новые apps = новые ICPs).

### 3.6 Open questions для Маши небесной

1. **Step retry policy: per-step или global?** Сейчас в Эконометрике retries hardcoded в frontend (user clicks "retry"). Workflow engine должен иметь declarative retry config? Default proposal: per-step optional `retry: {max_attempts: 3, backoff: exponential, retryable_errors: [TimeoutError]}`. Альтернатива: только UI-driven retry (engine не decides), workflow declares "stay" transition только.

2. **Async / streaming progress reach:** `long_running_callable` streams progress через SSE. Эконометрика currently uses HTTP polling (`/compute/train/progress` GET endpoint). Migration path: оставить poll-style backwards compat в shim layer OR force migrate frontend к SSE? Default: dual-mode (SSE primary + poll-style legacy endpoint maintained 1 minor version, deprecation warning).

3. **Workflow versioning forward/backward compat:** workflow YAML имеет `schema_version`. Если v1.1 adds optional fields, могут ли v1.0 engines загрузить v1.1 YAML (warn ignored fields)? Default: yes, additive only в minor bumps; major bumps strict.

4. **Composite step transactionality vs idempotency:** composite step `transfer_validate` с rollback — если 3rd sub-step fails, нужно ли откатывать file system side-effects (uploaded file persisted в `project_dir/uploads/`)? Default proposal: Phase A — only state dict rollback, file system side effects persist (cleanup deferred). Phase B — full transactional model possible.

5. **Workflow → workflow handoff (cross-app):** Aurora Эконометрика → Aurora Launch handoff (Эконометрика project → Launch proxy candidate) — это новый workflow или extension existing? Default: новый workflow `aurora_launch.import_from_econometrica.v1.workflow.yaml`, Phase B.

---

## Component 4: Tauri shell template

**Goal:** Boilerplate-репозиторий, из которого новые Aurora apps (Launch / Brand / Optimize / Pricing / Promo / Studio standalone) spawn'ятся за **дни, не недели**. Шаблон собирает: Tauri shell с Rust сторону, Svelte 5 runes frontend, Python sidecar pipe IPC, Aurora Hybrid Design System tokens, NSIS installer, auto-update pipeline, theme switching, help system framework, Sentry-style error reporting (если opt-in). Per-app кастомизация = N cabinets + per-app accent + per-app workflow YAML, остальное shared.

### 4.1 Scope

**Входит:**

#### 4.1.A Repository scaffolding

`aurora-shell-template` — отдельный GitHub repo (private). Cookiecutter-style template:

```
aurora-shell-template/
├── README.md                          # how to spawn new app
├── cookiecutter.json                  # config: app_id, app_name, accent_color, ...
├── {{cookiecutter.app_id}}/           # rendered template
│   ├── README.md
│   ├── package.json                   # name = {{cookiecutter.app_name}}
│   ├── pnpm-lock.yaml
│   ├── svelte.config.js
│   ├── vite.config.js
│   ├── tsconfig.json
│   ├── src/                           # Svelte 5 runes
│   │   ├── App.svelte
│   │   ├── routes/                    # default cabinets: Home, Settings, Help
│   │   ├── components/                # imports Aurora Hybrid DS
│   │   ├── stores/                    # state stores (license, theme, locale)
│   │   └── lib/sidecar_client.ts      # IPC pipe wrapper
│   ├── src-tauri/
│   │   ├── Cargo.toml
│   │   ├── tauri.conf.json
│   │   ├── build.rs
│   │   ├── src/
│   │   │   ├── main.rs
│   │   │   ├── lib.rs
│   │   │   ├── commands/              # Tauri commands (frontend → Rust IPC)
│   │   │   ├── econ_sidecar.rs        # → renamed to sidecar_runtime.rs
│   │   │   ├── crypto/
│   │   │   ├── session/
│   │   │   ├── metrics/
│   │   │   └── errors.rs
│   │   ├── installer_hooks.nsh        # NSIS pre-install kill sidecar (per project_econometrica_install_lock_2026_05_04)
│   │   ├── icons/                     # placeholder, replaced per-app
│   │   ├── help/                      # placeholder, replaced per-app
│   │   └── capabilities/              # Tauri 2.0 capabilities files
│   ├── sidecar/                       # Python sidecar
│   │   ├── {{cookiecutter.app_id}}_sidecar/
│   │   │   ├── server.py              # FastAPI app, mounts workflow router
│   │   │   ├── build_sidecar.py       # PyInstaller spec
│   │   │   └── requirements.txt       # base deps + aurora-platform-core
│   │   └── tests/
│   ├── deploy/                        # release pipeline scripts
│   ├── docs/
│   │   ├── INSTALL.md
│   │   ├── ARCHITECTURE.md
│   │   └── per_app_customization.md
│   ├── .github/workflows/
│   │   ├── build-and-release.yml      # cross-platform (initially Windows)
│   │   └── pytest-frontend-tests.yml
│   ├── lefthook.yml
│   └── pytest.ini
└── docs/
    ├── HOW_TO_SPAWN.md               # шаг-за-шагом
    └── DESIGN_DECISIONS.md
```

#### 4.1.B Cookiecutter parameters

```json
{
  "app_id": "aurora_launch",
  "app_name": "Aurora Launch",
  "app_title_ru": "Aurora Launch",
  "app_description": "MMM-прогноз для новых брендов и брендов с длительной паузой",
  "app_accent_color": "#0EA5E9",
  "app_accent_token_ref": "electric-blue-500",
  "app_icon_set": "default_aurora_seal",
  "default_locale": "ru",
  "supported_locales": ["ru", "en"],
  "tauri_app_identifier": "pro.auroraai.launch",
  "tauri_window_title": "Aurora Launch",
  "default_window_size": "1280x800",
  "min_window_size": "1024x600",
  "supabase_project_ref": "<filled at install>",
  "rosst_updates_endpoint": "<filled at install>",
  "license_app_key": "aurora_launch",
  "ship_includes_phi_model": false,
  "telemetry_default": "off"
}
```

**Result:** `cookiecutter aurora-shell-template` за ~5 минут спавнит ready-to-build Tauri app.

#### 4.1.C Default cabinets (shared shell)

Per Aurora Эконометрика production pattern:

| Cabinet | Purpose | Customization scope |
|---|---|---|
| `Home` | Welcome / project list / "Open recent" | Per-app: hero copy + CTA. |
| `Settings` | Theme, locale, telemetry opt-in, cloud opt-in (если applicable), license info | Universal — same across apps. |
| `Help` | FTS5-searchable help docs (existing pattern с BRAND_HINTS auto-injection) | Per-app: help docs content. |
| `About` | Version + signature + links | Per-app: text. |
| `License` | Activation, online status, slot usage (для floating license apps) | Per-app для cross_app_license tier. |

**App-specific cabinets** добавляются через cookiecutter `extra_cabinets` config + Svelte components.

#### 4.1.D Sidecar Python pipe IPC

Same pattern как Aurora Эконометрика (`sidecar_runtime.rs` ↔ FastAPI `server.py`):
- Tauri Rust spawn'ит sidecar exe at app start.
- Subprocess pipe communication (stdin/stdout) для bidirectional IPC.
- HTTP fallback (FastAPI on `127.0.0.1:RANDOM_PORT`) для streaming responses (SSE для long_running_callable progress).
- Error codes registry shared (см. C3.1.G).

**Phase A enhancement:** sidecar lifecycle hardened per `project_econometrica_install_lock_2026_05_04`:
- NSIS preinstall hook kills sidecar before file overwrite (eliminates v1.0.16→v1.2.0 silent install lock).
- Sidecar binary deployed в `%LOCALAPPDATA%\<app_id>\sidecar-{version}\econ_sidecar.exe` (per-version, no Program Files locks).
- Tauri JS pre-update hook: graceful shutdown call `/shutdown` endpoint before update install.

#### 4.1.E Aurora Hybrid Design System integration

Per Aurora Launch REUSE Section 1.3:
- `tokens.json` SSOT в `D:\Docs\Aurora_Ai\Standards\tokens\` — vendored copy в shell template.
- `Standards/build.py` runs at build time → generates CSS variables + Tauri theme + HTML report tokens.
- `--check` drift detection in CI (anchored timestamp regex per audit fix 2026-04-28).
- 4 Hybrid Design System TSX components imported.
- Lora display + Inter body + JetBrains Mono fonts (WOFF2).
- Aurora wordmark (custom letterforms) в `assets/`.
- Per-app accent overrides default Sacred Lime → `cookiecutter.app_accent_color`.

#### 4.1.F Theme switching (light / dark / fun)

Existing Aurora Эконометрика implementation extracted в shared store + tokens:
- Light theme — default.
- Dark theme — Sacred Lime + Aurora Deep dim.
- Fun theme — extra accent saturation + custom motion (used as Easter egg / customer satisfaction signal).

`prefers-reduced-motion` honored.

#### 4.1.G Help system framework

Existing pattern (FTS5 + BRAND_HINTS auto-injection через `sync_help_lists.py`):
- Markdown source в `src-tauri/help/<app_id>-source/*.md`.
- Lefthook hook auto-rebuilds HTML on Markdown change.
- Cross-link с aurora-platform-core help (для cross-app navigation).

#### 4.1.H NSIS installer + auto-update

Per Aurora Эконометрика production:
- NSIS script template (parametrized для cookiecutter app_id).
- SHA-256 signature verification.
- rosst-updates `latest.json` + Supabase `app_versions` table integration.
- Auto-update check at startup (configurable interval).
- **Phase A fix:** preinstall hook kill sidecar (cross-product fix, см. 4.1.D).

#### 4.1.I CI/CD pipeline (GitHub Actions)

Composite action `aurora-build-tauri-app`:
- Inputs: app_id, version, optional artifacts (Phi model bundle).
- Outputs: NSIS installer .exe + SHA-256 + release notes.
- Triggers: `push` to `main` tag `v*`.
- Cross-platform initially Windows-only; macOS/Linux scaffolding stubs Phase D+.

#### 4.1.J Spawning new app from template (developer journey)

```bash
# 1. Clone template
git clone github.com/Ackold26/aurora-shell-template

# 2. Run cookiecutter
cd aurora-shell-template
cookiecutter . --output-dir ../

# 3. Answer prompts (app_id, app_name, accent, ...)

# 4. cd into spawned repo
cd ../aurora_launch

# 5. Initial setup
pnpm install
cd src-tauri && cargo check
cd ../sidecar && pip install -r requirements.txt

# 6. Run dev
pnpm tauri dev

# 7. Add app-specific cabinets (per app workflow YAML)
# 8. Customize Help docs
# 9. Replace icons (см. project_aurora_unified_app_icon.md)
# 10. First build
pnpm tauri build
```

**Не входит:**
- ❌ Mobile / iOS / Android — Phase D+.
- ❌ Cross-platform Mac/Linux production builds — Phase D+ (template scaffolding только).
- ❌ App store / Microsoft Store distribution — Phase C+.
- ❌ Visual app builder (drag-drop UI generator) — out-of-scope ever.
- ❌ Dynamic plugin system (apps loadable at runtime) — Phase D+.

### 4.2 Acceptance Criteria

**AC4.1 — Cookiecutter render produces buildable Tauri app.**
- GIVEN clean dev environment (Node 20 + Rust 1.75 + Python 3.11 + MSVC).
- WHEN developer runs `cookiecutter aurora-shell-template` с valid params.
- THEN spawned repo: `pnpm install` succeeds, `cargo check` passes в src-tauri/, `pip install -r requirements.txt` succeeds в sidecar/, `pnpm tauri build` produces functional NSIS installer within 20 минут на reference machine (i7 / 16 GB).

**AC4.2 — Default cabinets functional out-of-box.**
- GIVEN fresh-spawned `aurora_launch` shell.
- WHEN user runs the binary.
- THEN: Home cabinet displays welcome + recent projects (empty list); Settings shows theme switcher (3 options) + locale switcher (RU/EN); Help cabinet opens FTS5-searchable docs (placeholder content); License cabinet shows "Not activated" state с link на activation flow.

**AC4.3 — Sidecar IPC reliable.**
- GIVEN running shell с sidecar.
- WHEN frontend invokes `sidecar_client.call("/health")`.
- THEN HTTP 200 response within 2 sec; sidecar process listed в task manager; killing sidecar process triggers Tauri shell graceful error UI ("sidecar disconnected, restart app").

**AC4.4 — Theme switching live without restart.**
- GIVEN running shell.
- WHEN user clicks theme switcher in Settings.
- THEN UI re-renders in new theme < 200 ms; tokens.json values applied (e.g., Sacred Lime active accent in light → Aurora Deep dim in dark); user preference persisted across restarts.

**AC4.5 — NSIS installer install lock fix.**
- GIVEN existing installed `aurora_launch v1.0.0` running (sidecar process active, holding `_internal/*.pyd` lock).
- WHEN auto-update kicks in to install `v1.0.1`.
- THEN preinstall hook kills sidecar process; install completes successfully (no "file in use" errors); shell restarts с new sidecar version (per `project_econometrica_install_lock_2026_05_04` Phase 3.1 fix).

**AC4.6 — Aurora Hybrid Design System drift detection.**
- GIVEN spawned shell с vendored `tokens.json`.
- WHEN `python Standards/build.py --check` runs in CI.
- THEN exits 0 (no drift); if developer manually edits vendored `tokens.json` → exits 1 с anchored timestamp regex showing diff; CI gate blocks merge.

**AC4.7 — Help system FTS5 search.**
- GIVEN populated help docs (e.g., placeholder Markdown 5+ pages).
- WHEN user types query "license activation" в help cabinet search.
- THEN FTS5 returns relevance-ranked snippets within 100 ms; click → full doc displayed с highlighted matches.

**AC4.8 — Auto-update verifies SHA-256 signature.**
- GIVEN tampered installer (modified bytes after build).
- WHEN auto-update downloads + verifies.
- THEN signature mismatch detected; UI displays "Update verification failed, please contact support"; tampered installer не запускается.

**AC4.9 — Workflow engine integration.**
- GIVEN spawned shell with workflow YAML in `aurora-platform-core/workflows/aurora_launch.new_brand_forecast.v1.workflow.yaml`.
- WHEN sidecar starts.
- THEN sidecar `server.py` auto-loads workflow + mounts FastAPI router (per C3); frontend `sidecar_client` connects + can execute workflow steps.

**AC4.10 — Production parity с Aurora Эконометрика.**
- GIVEN `aurora_optimize` (Эконометрика rebrand) spawned from template.
- WHEN running side-by-side с current production v1.0.16.
- THEN UX equivalent (same window size, theming, help system, license flow, auto-update); regression suite from Эконометрика passes на rebrand build.

### 4.3 Definition of Done

- [ ] **AC4.1–AC4.10 все pass.**
- [ ] **`aurora-shell-template` repo published** на GitHub (private), HEAD tagged `v1.0.0`.
- [ ] **3 spawned apps Phase A:** `aurora-launch` (existing), `aurora-data-studio` (existing), Aurora Эконометрика → `aurora-optimize` (rebrand). All spawn from template successfully + ship NSIS installers.
- [ ] **Cookiecutter HOW_TO_SPAWN.md** documented с screenshots / asciinema recording.
- [ ] **Pytest + Vitest suites** в template: 30+ tests verifying default cabinets, theme switching, IPC client, license stub, help system.
- [ ] **CI workflow `aurora-build-tauri-app`** action published в `.github/actions/`.
- [ ] **Migration guide для Aurora Эконометрика → Aurora Optimize:** stepwise refactor (rename + workflow YAML adoption + branding update + license tier scaffolding).
- [ ] **Install lock fix verified** на real prod scenario (forced auto-update v1.0.16→v1.2.0 reproduction test, per memory).
- [ ] **CHANGELOG entry** в `aurora-shell-template/CHANGELOG.md`.
- [ ] **ADR:** `aurora-knowledge/Decisions/aurora-shell-template-cookiecutter.md` (rationale: cookiecutter chosen vs Yeoman / custom CLI / monorepo).

### 4.4 Test Data Requirements

**Smoke test fixtures:**
- 3 cookiecutter param combinations (Aurora Launch, Aurora Optimize, Aurora Studio) → render → build → run smoke test.
- Tampered installer (modified bytes) for AC4.8.
- Mock auto-update server (rosst-updates simulator).
- Mock Supabase project_ref (license flow).

**Regression suite:**
- Aurora Эконометрика production test cases run against `aurora_optimize` rebrand.

**Manual / live tests (cannot fully automate):**
- Visual UI / accessibility / screen reader (manual QA checklist).
- Cross-version auto-update сценарий (требует physical install / уpdate).

### 4.5 Зависимости

**Внутренние:**
- **Зависит от:** C5 Common Services (license + auth + auto-update — shell embeds), C3 Workflow Engine (sidecar mounts workflow router), C1 Inference Core (sidecar deps include `aurora-platform-core`).
- **Не зависит от:** C2 (Studio = standalone Tauri app, использует shell template как любой другой spawned app), C6 (используется через C5 license flow), C7 (web verifier — отдельный WASM, не Tauri).

**Блокирует:**
- All Phase A app spawns: Aurora Launch / Studio / Optimize rebrand.
- All Phase B/C/D new app spawns (Brand / Pricing / Promo / Portfolio).

**Внешние:**
- **Tauri 2.0** (current Эконометрика production version).
- **Svelte 5 runes** (current).
- **Cookiecutter 2.5+** (Python).
- **Node 20 + Rust 1.75 + Python 3.11 + MSVC** (build deps).
- **NSIS 3.09** (Windows installer).
- **Supabase project** (license + app_versions table, существующая).
- **rosst-updates GitHub repo** (existing).

**Координационные:**
- **Антон approval:** decision на cookiecutter vs custom CLI (Антон может предпочесть простой CLI скрипт как менее tooling-heavy).
- **Маша небесная ADR sign-off.**
- **Aurora Эконометрика maintainer:** confirm that rebrand к Aurora Optimize via shell template = zero customer-visible regression.

### 4.6 Open questions для Маши небесной

1. **Cookiecutter vs custom CLI:** cookiecutter — стандартный Python tool, но тянет Jinja2 + dep на pip-install. Альтернатива: bash-script с rsync + sed substitution (no deps, но grosser). Default proposal: cookiecutter (cleaner DX, dev-only tool).

2. **Mac/Linux scaffolding в template:** включить early stubs (cargo features for cross-platform) для Phase D+ или строго Windows-only? Default: include scaffolding но disable build configs (`#[cfg(target_os="windows")]`); Phase D+ enable.

3. **Per-app icon set delivery:** Aurora Эконометрика unified icon = brand standard (per `project_aurora_unified_app_icon`). Template ships placeholder Aurora seal — каждый app overrides. Кто ownит icon design — Дима (per `project_aurora_design_system_hub`)? Default: per-app icon = required field cookiecutter, без placeholder fallback на ship.

4. **PyInstaller spec в template:** Эконометрика production использует custom PyInstaller spec для sidecar. Vendor it в template или каждый app пишет свой? Default: shared spec в template, override-able через extras.

5. **Localization (locales):** template supports RU + EN. Markets и контент разные per app (Studio = primarily РФ, Launch = primarily РФ). Phase A scope: ship RU только, EN scaffolding но не translate (deferred Phase B). Confirm?

---

## Component 5: Common Services

> **Status:** spec pending — будет в следующей итерации.

---

## Component 6: Schema Registry + cross_app_license

> **Status:** spec pending — будет в следующей итерации.

---

## Component 7: Web verifier (Methodology Certificate)

> **Status:** spec pending — будет в следующей итерации.
