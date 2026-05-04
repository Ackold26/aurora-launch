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

> **Status:** spec pending — будет в следующей итерации (после C1 ship).

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
