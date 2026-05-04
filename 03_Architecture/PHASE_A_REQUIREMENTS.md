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

> **Status:** spec pending — будет в следующей итерации.

---

## Component 4: Tauri shell template

> **Status:** spec pending — будет в следующей итерации.

---

## Component 5: Common Services

> **Status:** spec pending — будет в следующей итерации.

---

## Component 6: Schema Registry + cross_app_license

> **Status:** spec pending — будет в следующей итерации.

---

## Component 7: Web verifier (Methodology Certificate)

> **Status:** spec pending — будет в следующей итерации.
