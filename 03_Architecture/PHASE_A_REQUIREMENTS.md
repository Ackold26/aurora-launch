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

**AC1.1 — Pure extraction, zero functional drift.** (audit-revised B8)
- GIVEN Aurora Эконометрика regression corpus (Кагоцел trained model `.pickle` + Венарус trained model). **Note:** test corpus stored privately (`tests/fixtures/private/`, gitignore'd) — синхронизируется через secure channel между Антоном и Машей маленькой; Маша небесная не имеет direct access (см. R4 в audit report).
- WHEN `aurora_inference.modeler.train_model(config, project_dir)` invoked с identical config (extracted from Эконометрика regression test).
- THEN output dict has identical keys (`model_data`, `metrics`, `diagnostics`, etc.) и numerical values match Эконометрика baseline within `rtol=1e-4` for deterministic seeds (NumPyro fixed `random.PRNGKey(42)`), and within `rtol=1e-2` for stochastic diagnostics (Gelman-Rubin, ESS, divergent transitions count).
- **Cross-machine numerical determinism caveat:** bit-exact equality невозможна across (Python version, JAX version, XLA backend, hardware) variations. `rtol=1e-4` accommodates типичный floating-point operation order drift. Test fixtures regenerated quarterly on reference machine (Антон's primary dev box); CI runners use looser `rtol` if flakiness обнаружена.

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

**AC1.5 — Conformal Prediction triple-CI работает out-of-the-box.** (audit-revised H4)
- GIVEN trained Bayesian model + calibration set (20% holdout, n_calibration ≥ 50 для default tightness assertion).
- WHEN `aurora_inference.conformal.ConformalCalibrator.calibrate_bayes(model, calibration_data)` invoked.
- THEN returns ConformalCI dict с `lower`, `upper`, `coverage_level` (default 0.9). Tightness varies с n_calibration:
  - **n ≥ 50:** intervals ≤ ±2σ + 10% tolerance (Aurora differentiator — distribution-free + tighter than naive Gaussian).
  - **n < 50:** intervals expected wider (quantile inflation `(1-α)(1+1/n)` — math limitation per Vovk 2005). Validate **conservative coverage instead**: empirical coverage ≥ stated 0.9 within ±0.05 на test sample.
- Aurora Launch projects часто start с n < 12 weeks recipient calibration → AC must handle small-n gracefully, not assert universal tightness.

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
- [ ] **Atomic write fix (audit B7):** все `pickle.dump` calls в Inference Core migrated к helper `aurora_inference.io.atomic_write_pickle(path, data)` using `os.replace()` (Python 3.3+ atomic overwrite cross-platform). **Inherits + fixes existing Эконометрика bug** где `engines/modeler.py:1131` + `engines/ols_modeler.py:416` пишут pickle direct (process kill mid-write → corrupt model). Phase A C1 takes ownership of this fix.
- [ ] **Persistence helper formalization (audit refinement):** ad-hoc `setdefault(...)` fix-ups в `load_model_with_compat` formalized как explicit migrations через C6 SchemaRegistry. No silent defaulting outside registry.
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

**Source taxonomy (audit-revised B10 + H10):** task profile YAML `sources` field references **9 source kinds**, не только 5 raw adapters:

| Source kind | Type | Phase A | Description |
|---|---|---|---|
| `dsm_group` | raw_adapter | ✅ | DSM Group monthly XLSX (above table) |
| `mediascope_adex` | raw_adapter | ✅ | Mediascope AdEx (above table) |
| `mediascope_tv_index` | raw_adapter | ✅ | Mediascope TV Index Polometers (above) |
| `digitalbudget` | raw_adapter | ✅ | DigitalBudget (above) |
| `custom_xlsx` | raw_adapter | ✅ | Tier 2 LLM fallback (above) |
| `mediascope_brandpulse` | raw_adapter | ❌ Phase B+ | Brand health tracker — adapter pending Sprint S2 после Phase A. Task profiles using BrandPulse declare `phase_availability: phase_b_plus` per field. |
| `aurora_artifact_reference` | artifact_reference | ✅ | Existing `.aurora` bundle, **referenced not parsed**. Use cases: scenario_what_if reads prior budget_optimization output; new_brand_forecast imports Эконометрика project as proxy (per strategic correction 2026-05-05). Schema-versioned via SchemaRegistry BFS migration on read. |
| `derived_internal` | derived | ✅ | Engine-computed (Chow-Lin disaggregation, seasonality decomposition, etc.) — НЕ user upload. Studio computes from other sources. Task profile may also accept `user_input_form` override. |
| `user_input_form` | ui_input | ✅ | Structured form values (Pydantic-validated). Не file upload, не parsed source. Examples: ProxyBrandMetadata, RecipientAnchorsV1, target_audience definition. |

**`AuroraArtifactReferenceAdapter`** (новый класс, audit B10):
```python
class AuroraArtifactReferenceAdapter(SourceAdapter):
    """References existing .aurora bundle without re-parsing.

    metadata fields (in adapter result):
        referenced_bundle_path: Path
        referenced_app: str            # "aurora_optimize", "aurora_econometrica", ...
        referenced_task: str | None    # "budget_optimization" if known
        live_project: bool             # True если bundle still being edited
        legacy: bool                   # True для pre-v3.0 bundles
        original_schema_version: str
    """
    source_id: str = "aurora_artifact_reference"

    def detect(self, file_path: Path) -> DetectResult:
        """Detect .aurora ZIP signature + schema_version compatibility."""

    def parse(self, file_path: Path, variant: str | None = None) -> AdapterResult:
        """Read manifest.json, run SchemaRegistry.migrate() to v3.0,
        return AdapterResult с extracted metadata + bundle path для downstream consumption."""
```

#### 2.1.B AI parser stack (Tier 1 / Tier 2 / Tier 3)

Per ADR-001 `tiered-hybrid-ai-parser`:

- **Tier 1 — Heuristic + signature match.** `aurora_data_studio.source_adapters.<src>` runs first. Filename pattern + header pattern + cell signature (e.g., AdEx weights summing to 1.0) → high-confidence match (≥ 0.85). Fast (< 100 ms per file). Default for all 5 known sources.
- **Tier 2 — Local LLM.** `aurora_data_studio.engines.llm_parser` — llama.cpp wrapper around Phi-3.5-mini Q4 GGUF (~2.5 GB installer overhead, 4-6 GB RAM при inference). Used когда Tier 1 confidence < threshold (e.g., custom client XLSX без known signature). Local-only (privacy-first для фарма/financial ICP). Output: `WorkbookInference` Pydantic model (см. Studio existing `engines/llm_parser/output_models.py`).
- **Tier 3 — Cloud LLM (opt-in).** `aurora_data_studio.engines.cloud_parser` — Anthropic SDK wrapper, default OFF. Toggle в Settings + per-session confirm. **PII redaction = NER + whitelist (audit fix H1)**, не regex-only — см. 2.1.G privacy.

**Tier escalation rules** (per ADR-001):
- Tier 1 confidence ≥ **threshold_t1** → use Tier 1 result.
- threshold_t2 ≤ confidence < threshold_t1 → fall through Tier 2.
- Tier 2 confidence ≥ **threshold_t1_local** → use.
- < threshold_t1_local (или Tier 2 disabled) → fall through Tier 3 (если opt-in) или surface к user через MappingReviewStep.

**Threshold calibration (audit fix H3):** initial defaults `threshold_t1=0.85, threshold_t2=0.50, threshold_t1_local=0.70` — **heuristic guesses, not calibrated**. DoD requires per-source threshold tuning via cross-validation на eval corpus:
- Target precision ≥ 0.95 для Tier 1 (low FP rate, prefer escalation if uncertain).
- Target recall ≥ 0.85 для Tier 2 (catch most cases).
- Tunable per `source_id` (DSM heuristic likely much higher confidence threshold than custom XLSX).
- Brier Score < 0.15 (existing DoD) measures **calibration quality**, не threshold optimality — это independent quality dimension.

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

**Schema namespace separation (audit-revised B9):** manifest.json combines TWO independent identifiers — НЕ путать:
- **`schema_version`** — registry-managed bundle schema (per C6 SchemaRegistry kind `aurora_bundle`). Single value across ALL bundles regardless of source task: `"3.0"` Phase A. Drives forward-compat / migration.
- **`bundle_layout_id`** — task-specific layout identifier (e.g., `optimize_v3.0`, `optimize_scenario_v3.0`, `launch_v3.0`, `brand_bridge_v3.0`). Describes WHICH parquet files + JSON shapes are inside (per task profile YAML `output_bundle_target.bundle_layout_id`). НЕ semver-versioned per task — увеличивается suffix `_v2` если layout changes additively.

Example manifest.json:
```json
{
  "schema_version": "3.0",
  "bundle_layout_id": "launch_v3.0",
  "bundle_metadata": {...},
  ...
}
```

Naming convention для `bundle_layout_id`: `<app_short>_<task_short_optional>_v<n>` где app_short = aurora prefix removed (`optimize`, `launch`, `brand`). Documented в `04_Task_Profiles/README.md`.

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

Per Studio existing PRINCIPLES P5-P7 + audit-revised H1:

1. **Default = no data leaves machine.** Tier 1 + Tier 2 fully local.
2. **Cloud Tier 3 — opt-in.** Toggle в Settings, default OFF.
3. **PII redaction = NER + whitelist approach** (audit fix H1; regex alone insufficient для B2B-фарма XLSX где content почти 100% identifying):
   - **Layer 1 — Russian NER** (Natasha library OR DeepPavlov RuBERT NER) для PER/ORG/LOC entity recognition в text columns.
   - **Layer 2 — Whitelist (default):** redact ALL string content; keep numbers + ISO dates + canonical column headers + user-confirmed tokens. Aggressive default — minimizes leak surface.
   - **Layer 3 — User-driven explicit redaction:** at first Tier 3 invocation, show preview of what will be sent + allow manual additions to whitelist (e.g., «keep `TV channel codes` since they're public catalogs»).
   - **Layer 4 — Regex для known patterns:** email, INN, phone, IBAN, MAC, IP — каскадная redaction.
4. **No model training on customer data.** Phi pretrained, Anthropic terms — no training (verified в ADR-001).
5. **Audit trail.** Redaction log + tier decisions saved per session, accessible через `AdvancedSettingsStep` → "Open audit log". Log records: original token → redacted placeholder → restoration mapping (encrypted local-only).

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

**AC2.3 — Tier 3 opt-in only с PII redaction (NER + whitelist).** (audit-revised H1)
- GIVEN Settings "Enable cloud parser (Tier 3)" toggle = ON, sample XLSX с brand names + manufacturer names + person names в content.
- WHEN parser falls through к Tier 3.
- THEN before HTTP request: 4-layer redaction applied (regex + NER + whitelist + user-confirmed). Audit log shows replaced strings:
  - "Кагоцел" → "[BRAND_001]" (Russian NER catches PER/ORG/BRAND).
  - "Materia Medica" → "[ORG_001]".
  - "Иванов А.С." → "[PERSON_001]" (NER PER).
  - "8 (800) 555-1234" → "[PHONE_001]" (regex).
  - Random column-header text NOT in whitelist (e.g., "Кампания Q1 спецакция") → "[REDACTED_001]" (whitelist default-aggressive).
- HTTP request to Anthropic API contains только redacted version; response un-redacted local-side через mapping table (mapping encrypted в session-local memory, never persisted).
- **First Tier 3 invocation per session:** preview UI shows redaction list + allows user manual whitelist additions before send.

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

**AC2.7 — Bundle composer atomic write + ZIP integrity.** (audit-revised B7)
- GIVEN composed canonical data + provenance + quality results.
- WHEN `bundle_composer.compose(output_path="my_project.aurora")` invoked.
- THEN: (1) `.aurora.tmp` written first; (2) **`os.replace(tmp_path, output_path)`** used для atomic overwrite (Python 3.3+ — atomic cross-platform; **NOT `os.rename` which fails on Windows если target exists**); (3) previous version pre-moved к `.aurora.bak.1` (rolling 4 backups) BEFORE replace; (4) SHA-256 signature in manifest.json matches recomputed hash; (5) `unzip + cat manifest.json` works на любой машине без Python.
- **Crash-safety invariant:** при любой process kill mid-write, либо old `.aurora` exists intact (replace not yet committed), либо new `.aurora` exists complete (replace committed). Никогда — partial/corrupt state.

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
- [ ] **Tier escalation thresholds calibrated** (audit fix H3): per-source thresholds tuned via cross-validation, target precision ≥ 0.95 для Tier 1, recall ≥ 0.85 для Tier 2. Documented в `engines/source_adapters/<src>/threshold_calibration.json`.
- [ ] **PII redaction NER layer integrated** (audit fix H1): Russian NER (Natasha или DeepPavlov RuBERT) embedded в `engines/cloud_parser/redaction.py`. UI preview at first Tier 3 invocation per session.
- [ ] **Atomic write helper** (audit fix B7): `engines/bundle_composer/io.py:atomic_write_aurora` использует `os.replace()`. Property test verifies crash-safety invariant.
- [ ] **Phi-3.5-mini license review** (audit fix M3): redistribution в Aurora installer verified (Phi-3-mini Apache 2.0 since June 2024; Phi-3.5 likely same — но manual confirmation required pre-ship).
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
| `composite` | Sequence of sub-steps + **explicit cleanup_callable_ref per sub-step** (audit fix H6) | inputs to first sub-step | output of last sub-step + on_partial_failure rollback (state + side effects) |
| `decision` | Branch на condition (jinja2-style expression evaluating state) | condition expression | next step id |
| `artifact_export` | Write report files | model_data + format list | file paths списком |
| `__end__` | Terminal state | — | — |

**Composite step rollback semantics (audit fix H6):** при `on_partial_failure: rollback_to_previous_step`, engine invokes **`cleanup_callable_ref`** for each completed sub-step **в обратном порядке**. Cleanup callable обязан remove side effects (uploaded files, temp artifacts, partial pickles). Workflow YAML schema validation enforces: каждый sub-step с side effects MUST declare cleanup_callable_ref OR explicitly mark `side_effects_free: true`. Phase A scope: filesystem cleanup primary; database cleanup (if Phase B+ adds DB writes) — extension.

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

**AC3.4 — Long-running step с progress streaming.** (audit-revised H5)
- GIVEN `train` step (Bayesian MCMC).
- WHEN client connects к progress channel — **either SSE endpoint** `/workflow/.../step/train/progress` (Phase A default) **или native Tauri event** `workflow:progress:{wf_id}:{step_id}` (Phase B+ optimization).
- THEN streams ProgressEvent JSON chunks (`{"step": "train", "progress": 0.42, "message": "MCMC sampling chain 2/4", "ts": "..."}`); chunk frequency: max(every 5 sec OR every 5% progress increment OR on chain transition boundary); final event `{"status": "completed", "result": {...}}`.
- **Mechanism choice:** Phase A SSE для simplicity + HTTP-only contract (existing `sse-starlette` библиотека). Phase B+ migration к Tauri native events (`emit`/`listen`) — lower latency (~10ms vs ~100ms SSE), more idiomatic для desktop. Workflow engine API exposes both — frontend chooses.

**AC3.5 — Cooperative cancel.**
- GIVEN `train` step running.
- WHEN POST `/workflow/.../step/train/cancel` invoked.
- THEN training stops within 30 sec (cooperative checkpoint); state saved; `current_step` returns `train` status `cancelled`; resume rolls back к previous step.

**AC3.6 — Composite step rollback on partial failure (state + side effects).** (audit-revised H6)
- GIVEN `transfer_validate` composite step с 3 sub-steps (`extract_priors`, `apply_magnitudes`, `prior_predictive`); `extract_priors` declares `cleanup_callable_ref: aurora_launch.engines.launch_adapt.cleanup_extracted_priors`.
- WHEN sub-step `apply_magnitudes` fails (RecipientAnchors invalid).
- THEN rollback applied в TWO phases:
  1. **State dict restored** к началу `transfer_validate`.
  2. **Side effects cleanup:** для each completed sub-step **в обратном порядке** (LIFO), engine invokes registered `cleanup_callable_ref`. В этом примере: `extract_priors` cleanup removes `project_dir/extracted_priors_*.json` artifacts.
- Next_step = `recipient_anchors` (per `on_partial_failure: rollback_to_previous_step`).
- **No silent stale state:** disk + state dict consistent после rollback.

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
  "min_window_size": "1280x720",                      // audit fix M1: 1024x600 too small для Aurora Launch ProxySelectionStep similarity radar + 6-dim form
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

**Goal:** 5 shared cross-app сервисов в одном пакете `aurora-platform-core/common_services/` — Auth (Supabase), License (cross_app_license framework + tier scaffolding free/pro/team/agency), Updates (auto-updater), Telemetry (opt-in event collection для Этап 2 monetization decisions), Feature Flags (gate Pro candidate features). Цель — каждый Aurora app использует identical infrastructure, без дублирования кода.

### 5.1 Scope

#### 5.1.A Auth (Supabase)

`common_services.auth`:

API:
```python
class AuthClient:
    def sign_up(email: str) -> SignUpResult                # email + magic link
    def sign_in_with_magic_link(email: str) -> SignInResult
    def verify_magic_link(token: str) -> Session
    def get_session() -> Session | None                    # cached locally
    def refresh_session() -> Session
    def sign_out() -> None
    def on_auth_state_change(callback) -> Unsubscribe
```

**Existing pattern** (Aurora Эконометрика uses Supabase auth + `feedback_online_only_license`). Phase A enhancement: extract в shared package.

**Session storage:** locally encrypted (per-machine key, OS DPAPI Windows / Keychain Mac / libsecret Linux). Default to OS-native; fallback to AES-256 + key file in `%APPDATA%\Aurora\session.bin`.

#### 5.1.B License framework (cross_app_license)

`common_services.license`:

**Schema (Supabase tables):**
- `user_accounts` — Supabase auth user.
- `app_licenses` — per-user x per-app license assignments.
- `license_tiers` — tier definitions (free / pro / team / agency / enterprise).
- `license_slots` — для floating concurrent license (Studio Team/Agency tiers).
- `license_features` — tier × feature flag matrix.

**Tier model (Phase A scaffolding, per Маша небесная monetization scaffold):**

```python
class LicenseTier(str, Enum):
    FREE = "free"        # default fallback (e.g., Studio Этап 1, no payment)
    PRO = "pro"          # paid tier 1
    TEAM = "team"        # paid tier 2 (multi-seat)
    AGENCY = "agency"    # paid tier 3 (multi-seat + cross-tenant)
    ENTERPRISE = "enterprise"  # custom contract

class LicenseScope(BaseModel):
    user_id: str
    app_id: str           # "aurora_launch", "aurora_optimize", "aurora_data_studio", ...
    tier: LicenseTier
    features: list[str]   # e.g., ["studio.feature.advanced_charts"]
    valid_from: datetime
    valid_until: datetime | None  # None = perpetual
    seats_total: int = 1
    seats_available: int = 1      # для floating concurrent
```

**API:**
```python
class LicenseClient:
    def check_license(app_id: str) -> LicenseResult
    def has_feature(feature_id: str) -> bool
    def acquire_slot(app_id: str) -> SlotToken            # для floating
    def heartbeat(slot_token: str) -> None                # 60s interval
    def release_slot(slot_token: str) -> None
    def get_tier(app_id: str) -> LicenseTier
    def upgrade_tier_url(target_tier: LicenseTier) -> str  # checkout URL

@license_required(app_id="aurora_launch", feature="train_model")
def train_model(...): ...                                  # decorator
```

**Floating license heartbeat / TTL** (per Studio ADR-003 + audit fix H7):
- Heartbeat каждые 60 сек.
- Server-side TTL 5 минут (slot reclaimable если 3 missed heartbeats).
- Cron cleanup runs every minute on Supabase Edge Function.
- **Client retry logic (audit fix H7):** при transient network error на heartbeat, client retries up to 3 attempts within 30 sec window с exponential backoff (5s, 10s, 15s). Только после 3 consecutive failures без success — UI shows "Connection lost" + saves session work locally + attempts re-acquire on reconnect. Это prevents wrongful slot reclamation при transient network glitch.

**Cross-app license activation:**
- Аutomatic при purchase any econometric app: Studio Solo activated (per Studio bundle-activation primary path).
- В Этапе 1: всё Suite tier-equivalent (free для Studio scope = full access всем покупателям).
- Этап 2 (Q4 2026 / Q1 2027): tier gates activated через feature flags.

#### 5.1.C Auto-updater

`common_services.updates`:

Per Aurora Эконометрика production pattern:
- rosst-updates `latest.json` polled at startup + interval (configurable, default 24h).
- Supabase `app_versions` table SOURCE OF TRUTH.
- Edge Function PATCH on release.
- SHA-256 verification before install.
- NSIS installer download + execute.
- Tauri JS pre-update hook: graceful sidecar shutdown (per `project_econometrica_install_lock_2026_05_04` Phase 3.1).

**API:**
```python
class UpdateClient:
    def check_for_update(app_id: str, current_version: str) -> UpdateInfo | None
    def download_update(info: UpdateInfo, progress_callback) -> Path
    def verify_signature(installer_path: Path, expected_hash: str) -> bool
    def install_update(installer_path: Path) -> None      # graceful shutdown + exec installer
```

**Phase A enhancement:** sidecar deployed в `%LOCALAPPDATA%\<app_id>\sidecar-{version}\` (per-version, no Program Files locks per memory).

#### 5.1.D Telemetry

`common_services.telemetry`:

Per coordination doc Section 4 + `phase-a-future-monetization-scaffold.md` (Маша небесная pending):

```python
class TelemetryClient:
    def emit(event_name: str, app: str, feature: str, metadata: dict) -> None
    def flush() -> None                                    # send buffered batch
    def is_opt_in() -> bool
    def opt_in() -> None
    def opt_out() -> None

class TelemetryEvent(BaseModel):
    event_name: str
    user_id_anon: str       # UUID per install
    app: str
    feature: str
    timestamp: datetime
    metadata: dict[str, str | int | float]
```

**Storage / transport:**
- Local: append-only `~/.aurora/telemetry/events.jsonl`, rotated daily, 90-day retention.
- Server (если opt-in): batch upload к `https://telemetry.auroraai.pro/events` каждые 60 минут или при flush().
- Anonymized user_id_anon (UUID per install, не tied к Supabase user_id).
- No PII, no data content. Feature usage signals only.

**Default state:** OFF (фарма ICP privacy concern). User opts-in через Settings → Telemetry → "Help us improve Aurora".

**Storage retention:** server side aggregated indefinite (для Этап 2 analysis). Individual events retain 90 дней.

#### 5.1.E Feature flags

`common_services.feature_flags`:

```python
class FeatureFlags:
    @classmethod
    def is_enabled(feature_id: str, app_id: str | None = None) -> bool
    @classmethod
    def get_all() -> dict[str, bool]

    # Decorators:
    @classmethod
    def require(feature_id: str): ...  # raises FeatureDisabled if off
```

**Default flags для Phase A** (per Маша небесная monetization scaffold + Studio + Launch needs):

```python
DEFAULT_FLAGS = {
    # Studio Этап 1 (all on)
    "studio.feature.multi_project_workspace": True,
    "studio.feature.advanced_charts": True,
    "studio.feature.pdf_export_quality_report": True,
    "studio.feature.team_collaboration": True,
    "studio.feature.tier3_cloud_unlimited": True,

    # Launch (all on)
    "launch.feature.multi_proxy": True,
    "launch.feature.posterior_update": True,
    "launch.feature.consulting_hours_widget": True,

    # Common
    "common.telemetry.opt_in_default": False,  # OFF default (фарма ICP)
    "common.theme.fun_mode": True,
    "common.cloud_llm.opt_in_default": False,  # OFF default

    # Этап 2 candidates (currently на)
    "studio.tier.gates_active": False,           # Этап 2 = True
    "launch.tier.gates_active": False,           # Этап 2 = True (если standalone tier)
}
```

**Override mechanism:**
- Flags могут быть overridden license tier (Этап 2): `license_features` table.
- Local override через env var (dev only): `AURORA_FF_<flag_id>=true`.
- Remote config (Phase B+) — not Phase A.

### 5.2 Acceptance Criteria

**AC5.1 — Auth flow end-to-end.**
- GIVEN clean install, no session.
- WHEN user enters email → magic link sent → clicks link in email.
- THEN session token persisted (encrypted local storage); `get_session()` returns valid session; user signed in across all Aurora apps на same machine (cross-app shared session).

**AC5.2 — License check на startup.**
- GIVEN signed-in user without active Aurora app license.
- WHEN spawning aurora_launch.
- THEN License cabinet shows "Not licensed" + "Activate" button; train_model() decorator raises `LicenseError`; UI redirects to activation flow.

**AC5.3 — Cross-app license activation.**
- GIVEN user purchases Aurora Optimize → Supabase license created с tier=PRO.
- WHEN user opens Aurora Data Studio.
- THEN Studio автоматически Solo tier activated (per ADR-002 bundle-activation primary path); `get_tier("aurora_data_studio")` returns SOLO; full Studio scope accessible.

**AC5.4 — Floating license slot acquisition.** (audit-revised H7)
- GIVEN Studio Team license (3 slots), 2 пользователя already connected.
- WHEN 3rd user opens Studio.
- THEN `acquire_slot()` succeeds; heartbeat starts (60s interval с retry logic 3×30s window on transient errors); `seats_available=0` reported.
- WHEN 4th user opens Studio.
- THEN `acquire_slot()` raises `NoSlotsAvailable` + UI message "All Team seats occupied, ..."
- WHEN 3rd user experiences transient network glitch (1 missed heartbeat).
- THEN client retries 3× с exponential backoff; if all 3 succeed → no impact (slot retained); if all 3 fail → UI shows "Connection lost" + saves session work locally + re-acquires on reconnect. **Slot НЕ reclaimed wrongfully.**

**AC5.5 — TTL slot reclamation.**
- GIVEN floating slot with last heartbeat 6 минут назад.
- WHEN cron cleanup runs.
- THEN slot released; `seats_available` incremented; new user может acquire.

**AC5.6 — Auto-update verifies + installs.**
- GIVEN current_version=1.0.0, server side `latest.json` for v1.1.0.
- WHEN startup check_for_update() runs.
- THEN UpdateInfo returned (URL, hash, release_notes); user clicks "Install"; downloaded; signature verified; pre-update hook fires (sidecar shutdown); NSIS installer launches.

**AC5.7 — Telemetry default OFF + opt-in functional.**
- GIVEN clean install.
- WHEN `is_opt_in()` checked.
- THEN returns False; `emit()` calls written к local jsonl но НЕ uploaded.
- WHEN user opts in via Settings.
- THEN `is_opt_in()` returns True; next `flush()` uploads buffered events; future events upload в batches.

**AC5.8 — Feature flags decorator gate.**
- GIVEN feature `studio.feature.advanced_charts` = False (mock Этап 2 state).
- WHEN code attempts `@FeatureFlags.require("studio.feature.advanced_charts")` call.
- THEN raises `FeatureDisabled("studio.feature.advanced_charts")`; UI graceful handling показывает upgrade prompt.

**AC5.9 — Encrypted session storage.**
- GIVEN authenticated session.
- WHEN session.bin file inspected на disk.
- THEN content NOT plain JSON (cannot extract token via `cat`); requires either OS DPAPI/Keychain access OR per-machine key.

**AC5.10 — Privacy в telemetry payload.**
- GIVEN any emitted telemetry event.
- WHEN inspected via Wireshark (if uploaded).
- THEN payload contains anonymized user_id (UUID), event_name, app, feature, timestamp, metadata; NO email, NO Supabase user_id, NO file content, NO PII.

### 5.3 Definition of Done

- [ ] **AC5.1–AC5.10 все pass.**
- [ ] **Code merged в `aurora-platform-core/common_services/`** + tagged.
- [ ] **Supabase schema migrations** applied: `user_accounts` (existing), `app_licenses` (extended schema), `license_tiers` (new), `license_slots` (new), `license_features` (new), `app_versions` (existing — verified consistency).
- [ ] **Edge Functions:** acquire-slot, heartbeat, release-slot, status (per Studio ADR-003) + cron cleanup. All deployed.
- [ ] **rosst-updates `latest.json`** integration verified для 3 apps (Launch / Studio / Optimize rebrand).
- [ ] **Pytest + integration tests:** 80+ tests. Coverage ≥ 80%.
- [ ] **Telemetry endpoint** `https://telemetry.auroraai.pro/events` functional (FastAPI on Yandex.Cloud or Vercel).
- [ ] **Feature flags registry** finalized + frozen + documented.
- [ ] **Migration guide для Aurora Эконометрика:** existing licensing → cross_app_license framework. Backwards compat: Эконометрика v1.0.16 license keys auto-migrate.
- [ ] **API docs:** `aurora-platform-core/docs/common_services.md`.
- [ ] **CHANGELOG entry.**
- [ ] **ADRs:**
  - `aurora-knowledge/Decisions/aurora-cross-app-license-framework.md`
  - `aurora-knowledge/Decisions/aurora-telemetry-opt-in-default.md`
  - `aurora-knowledge/Decisions/aurora-feature-flags-default-on-stage1.md`

### 5.4 Test Data Requirements

**Synthetic license fixtures:**
- `tests/fixtures/licenses/free_solo.json` — minimal license.
- `tests/fixtures/licenses/team_3seats_2used.json` — for AC5.4.
- `tests/fixtures/licenses/agency_10seats.json` — for slot tests.
- `tests/fixtures/licenses/expired.json` — for renewal flow.

**Mock auth flow:**
- Mock Supabase server (or test project ref) для magic link flow.
- Mock email delivery (capture link without sending).

**Mock telemetry receiver:**
- Local FastAPI receiver simulating `telemetry.auroraai.pro/events`.

**Mock auto-update server:**
- Local rosst-updates simulator с `latest.json`.
- Test installers (valid + tampered).

**Property-based tests:**
- Slot acquisition concurrency: random N concurrent acquire/release пар → state consistency.
- TTL math: random heartbeat sequences → correct reclamation timing.

### 5.5 Зависимости

**Внутренние:**
- **Зависит от:** C6 Schema Registry (license schema versioning).
- **Не зависит от:** C1, C2, C3, C4, C7. Common Services — pure infrastructure layer, не имеет UI/math зависимостей.

**Блокирует:**
- C4 Tauri shell template (license/auth/update embedded в shell).
- C3 Workflow engine (`@license_required` decorator).
- C1 Inference Core (gating wraps `train_model` etc.).
- All Aurora apps Phase A/B/C.

**Внешние:**
- **Supabase project** (existing, used by Aurora Эконометрика).
- **supabase-py >= 2.0** SDK.
- **httpx >= 0.26** для telemetry transport.
- **cryptography >= 42** for session storage encryption.
- **pywin32 (Windows)** для DPAPI native API.

**Координационные:**
- **Маша небесная ADRs** (3 sign-offs).
- **Антон approval:**
  - Tier 3 cloud LLM cap policy (Studio AC2.x).
  - Telemetry server hosting (Vercel vs Yandex.Cloud — RU-data-localization concern для фарма ICP).
- **Aurora Эконометрика maintainer:** license migration confirmation.

### 5.6 Open questions для Маши небесной

1. **Telemetry server hosting:** Vercel (consistent с auroraai.pro static) или Yandex.Cloud (data-localization для РФ)? Default proposal: Yandex.Cloud для compliance + Russian data residency. Cost trade-off: ~3000₽/мес минимум.

2. **License key storage architecture:** Supabase server-side primary + cached client-side. Какой fallback при offline (нет интернета at startup)? Default: cached license valid 7 days offline, then "Please connect к internet" UI.

3. **Pro tier feature gating timeline:** Phase A — все flags ON, Этап 2 (Q4 2026 / Q1 2027) — некоторые OFF for free tier. Migration guide требуется. Default: Phase A flags не actively gated; Этап 2 introduces `license.tier.gates_active` flag = True, активируя per-tier matrix.

4. **Cross-app session sharing UX:** signed in to Aurora Optimize → opening Aurora Studio = automatic sign-in (shared session). Confirm? Default: yes, single sign-on across Aurora apps на same machine. Different machine = re-sign-in.

5. **Telemetry events frequency cap:** local jsonl size cap (e.g., 100 MB)? Если flush() failed (offline), buffered events accumulate. Default: hard cap 50 MB local, oldest events dropped at cap with warning log.

---

## Component 6: Schema Registry + cross_app_license

**Goal:** Foundation layer для всех остальных компонентов. Schema Registry — централизованная versioned миграция pickle / `.aurora` / workflow_state файлов через BFS migration path; cross_app_license — relational schema в Supabase для license tier scaffolding (free/pro/team/agency) с самого начала, чтобы избежать breaking changes Этапа 2. Этот компонент собирается ПЕРВЫМ (build order foundation — всё остальное от него depend'ится).

### 6.1 Scope

#### 6.1.A Schema Registry — module API

`aurora_platform_core.schema_registry`:

```python
from typing import Callable, Dict, List, Tuple

MigrationFn = Callable[[dict], dict]

class SchemaRegistry:
    """Versioned schema migration via BFS path resolution.

    Supports multiple schema kinds: pickle/.aurora/workflow_state/license/etc.
    Each kind has independent version graph.
    """

    _migrations: Dict[str, Dict[Tuple[str, str], MigrationFn]] = {}
    _kind_target_versions: Dict[str, str] = {}

    @classmethod
    def register(cls, kind: str, from_version: str, to_version: str):
        """Decorator to register migration."""
        def decorator(fn: MigrationFn):
            cls._migrations.setdefault(kind, {})[(from_version, to_version)] = fn
            return fn
        return decorator

    @classmethod
    def set_target(cls, kind: str, version: str):
        """Set current target version for a kind. Apps call once at module load."""
        cls._kind_target_versions[kind] = version

    @classmethod
    def migrate(cls, data: dict, kind: str = "aurora_bundle", target_version: str | None = None) -> dict:
        """Migrate `data` to target_version (default = registered target for kind).

        BFS through migration graph. Raises:
            UnknownSchemaVersion: data["schema_version"] not in graph
            NoMigrationPath: cannot reach target_version
            CircularMigration: cycle detected (registry validation step)
        """

    @classmethod
    def find_path(cls, kind: str, start: str, end: str) -> list[Tuple[str, str]] | None:
        """Public: BFS search returning list of (from, to) tuples or None."""

    @classmethod
    def validate_registry(cls, kind: str) -> RegistryValidationResult:
        """Pre-flight: detect cycles, dead-ends, unreachable versions, and
        validate that all registered migrations are pure functions (idempotency)."""
```

**Schema kinds в Phase A:**
- `aurora_bundle` — `.aurora` ZIP container (manifest.json + pickle artifacts).
- `pickle_model` — `.pickle` model files (Aurora Эконометрика legacy + new).
- `workflow_state` — `.workflow_state.json` engine state.
- `license` — Supabase license rows (для backwards compat при schema changes).
- `recipient_anchors` — Aurora Launch RecipientAnchorsV1 + future versions.
- `task_spec` — Aurora Studio YAML task profiles.

#### 6.1.B Combined v3.0 schema (aurora_bundle kind)

Per Aurora Launch REUSE Section 2.1 + Studio REUSE «Pickle additive schema» + coordination doc Section 5.

**Migration registry для `aurora_bundle`:**

```python
@SchemaRegistry.register("aurora_bundle", "1.0", "2.0")
def migrate_aurora_v1_to_v2(data: dict) -> dict:
    """v1.0 -> v2.0: Robyn-style normalization (Эконометрика 2026-04-25)."""
    data.setdefault("intercept_mean", None)
    data.setdefault("control_betas_mean", None)
    data.pop("media_stds", None)  # replaced by spend/mean normalization
    return data

@SchemaRegistry.register("aurora_bundle", "2.0", "3.0")
def migrate_aurora_v2_to_v3(data: dict) -> dict:
    """v2.0 -> v3.0: combined Launch + Studio additive fields."""
    # Studio fields
    data.setdefault("bundle_metadata", None)
    data.setdefault("provenance", None)
    data.setdefault("quality_gates_results", None)
    data.setdefault("signature", None)
    # Launch fields
    data.setdefault("proxy_brand_metadata", None)
    data.setdefault("recipient_anchors", None)
    data.setdefault("transfer_provenance", None)
    data.setdefault("forecast_horizons", None)
    data.setdefault("posterior_update_log", [])
    data.setdefault("consulting_hours_log", None)
    return data

SchemaRegistry.set_target("aurora_bundle", "3.0")
```

**Forward-compat helper** (per Aurora Launch REUSE):

```python
from packaging import version

MIN_APP_FOR_SCHEMA: dict[str, dict[str, str]] = {
    "aurora_bundle": {
        "1.0": "1.0.0",
        "2.0": "1.0.10",
        "3.0": "1.4.0",  # Phase A → Phase B Suite v1.4.0
    },
    "pickle_model": {...},
    # ...
}

class CompatResult(BaseModel):
    can_open: bool
    reason: str | None = None
    suggested_action: Literal["update_app", "use_compatible_version", "ignore_warning"] | None = None

def check_forward_compatibility(
    data: dict, kind: str, current_app_version: str
) -> CompatResult: ...
```

#### 6.1.C cross_app_license schema (Supabase)

Per C5 Section 5.1.B + Studio ADR-003 (floating license).

**Tables:**

```sql
-- Existing (extended)
CREATE TABLE user_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  metadata JSONB
);

-- NEW
CREATE TABLE license_tiers (
  id TEXT PRIMARY KEY,                -- "free", "pro", "team", "agency", "enterprise"
  display_name TEXT NOT NULL,
  description TEXT,
  is_paid BOOLEAN NOT NULL,
  seats_default INT NOT NULL DEFAULT 1,
  features JSONB NOT NULL DEFAULT '[]'::jsonb,    -- list of feature_id strings
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Required для exclusion constraint (audit fix B5):
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE app_licenses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES user_accounts(id) NOT NULL,
  app_id TEXT NOT NULL,                            -- "aurora_launch", "aurora_optimize", ...
  tier_id TEXT REFERENCES license_tiers(id) NOT NULL,
  seats_total INT NOT NULL DEFAULT 1,
  valid_from TIMESTAMPTZ NOT NULL DEFAULT now(),
  valid_until TIMESTAMPTZ,                         -- NULL = perpetual
  metadata JSONB,
  schema_version TEXT NOT NULL DEFAULT '1.0',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  -- Audit fix B5: prevent overlapping licenses for same (user, app).
  -- UNIQUE (user_id, app_id, valid_from) недостаточен — допускает overlap.
  -- Exclusion constraint enforces «at most 1 active license per (user, app) at any moment».
  EXCLUDE USING gist (
    user_id WITH =,
    app_id WITH =,
    tstzrange(valid_from, COALESCE(valid_until, 'infinity'::timestamptz)) WITH &&
  )
);

CREATE TABLE license_slots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  license_id UUID REFERENCES app_licenses(id) NOT NULL,
  user_id UUID REFERENCES user_accounts(id) NOT NULL,
  machine_fingerprint TEXT NOT NULL,
  acquired_at TIMESTAMPTZ DEFAULT now(),
  last_heartbeat_at TIMESTAMPTZ DEFAULT now(),
  released_at TIMESTAMPTZ,
  UNIQUE (license_id, user_id, machine_fingerprint, released_at)
);

CREATE TABLE license_features (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tier_id TEXT REFERENCES license_tiers(id) NOT NULL,
  feature_id TEXT NOT NULL,                        -- e.g., "studio.feature.advanced_charts"
  enabled BOOLEAN NOT NULL DEFAULT true,
  metadata JSONB,
  UNIQUE (tier_id, feature_id)
);

-- INDEX'ы
CREATE INDEX idx_app_licenses_user_app ON app_licenses(user_id, app_id);
CREATE INDEX idx_license_slots_license_active ON license_slots(license_id) WHERE released_at IS NULL;
CREATE INDEX idx_license_slots_heartbeat ON license_slots(last_heartbeat_at) WHERE released_at IS NULL;
```

**Default seed (Phase A, audit-revised B3):**

```sql
INSERT INTO license_tiers (id, display_name, is_paid, seats_default, features) VALUES
  ('free', 'Free', false, 1, '[]'::jsonb),
  ('pro', 'Pro', true, 1, '[]'::jsonb),
  ('team', 'Team', true, 3, '[]'::jsonb),
  ('agency', 'Agency', true, 10, '[]'::jsonb),
  ('enterprise', 'Enterprise', true, 9999, '[]'::jsonb),
  -- Special tier для legacy demo client migration (audit fix B3):
  ('trial_6mo', 'Demo legacy 6-month trial', false, 1, '[]'::jsonb);

-- Studio Этап 1: все features в free (per стратегия 2026-05-05).
INSERT INTO license_features (tier_id, feature_id, enabled) VALUES
  ('free', 'studio.feature.multi_project_workspace', true),
  ('free', 'studio.feature.advanced_charts', true),
  ('free', 'studio.feature.pdf_export_quality_report', true),
  ('free', 'studio.feature.team_collaboration', true),
  ('free', 'studio.feature.tier3_cloud_unlimited', true),
  -- Aurora Launch features (per S009 PRICING_TIERS)
  ('pro', 'launch.feature.multi_proxy', true),
  ('pro', 'launch.feature.posterior_update', true),
  ('pro', 'launch.feature.consulting_hours_quarterly_review', true),
  ('enterprise', 'launch.feature.white_label', true),
  ('enterprise', 'launch.feature.api_access', true),
  ('enterprise', 'launch.feature.dedicated_success_manager', true);
```

**Migration mechanism:** schema bumps applied through Supabase migrations folder (Alembic-style versioning). Versioned via Supabase CLI.

**Backwards compat (audit-revised B3):** existing Aurora Эконометрика v1.0.16 license keys auto-migrate с **`tier_id="trial_6mo"`** (NOT "pro" — paid tier без payment record создаёт ledger inconsistency). `valid_until = migration_date + 6 months` per Aurora Suite migration plan (memory `project_econometrica_target_architecture_v3` § «Customer Migration Strategy»: «демо-клиенты получают **free 6-month trial** на Aurora Suite после ship Phase B»). После 6 months — pre-renewal sales conversation; expired trial → graceful read-only mode (open existing projects, no new analysis).

**Acquire-slot transaction (audit fix B6):** Edge Function MUST использовать `SERIALIZABLE` isolation level + SELECT FOR UPDATE pattern для предотвращения race conditions при concurrent slot acquire от different machines:

```typescript
// supabase/functions/acquire-slot/index.ts (skeleton)
await supabase.rpc('acquire_license_slot', {
  p_license_id: licenseId,
  p_user_id: userId,
  p_machine_fingerprint: machineFingerprint
});

// SQL function:
CREATE OR REPLACE FUNCTION acquire_license_slot(
  p_license_id UUID, p_user_id UUID, p_machine_fingerprint TEXT
) RETURNS TABLE(slot_id UUID, ok BOOLEAN, reason TEXT)
LANGUAGE plpgsql
AS $$
DECLARE
  v_seats_total INT;
  v_seats_used INT;
  v_slot_id UUID;
BEGIN
  -- Lock license row + count active slots в same transaction
  SELECT seats_total INTO v_seats_total
  FROM app_licenses WHERE id = p_license_id FOR UPDATE;

  SELECT count(*) INTO v_seats_used
  FROM license_slots WHERE license_id = p_license_id AND released_at IS NULL;

  IF v_seats_used >= v_seats_total THEN
    RETURN QUERY SELECT NULL::UUID, FALSE, 'no_slots_available';
    RETURN;
  END IF;

  INSERT INTO license_slots (license_id, user_id, machine_fingerprint)
    VALUES (p_license_id, p_user_id, p_machine_fingerprint)
    RETURNING id INTO v_slot_id;

  RETURN QUERY SELECT v_slot_id, TRUE, NULL::TEXT;
END;
$$;
```

**activate-bundle idempotency:** UPSERT semantic — repeated invocation with same `(user_id, app_id_purchased)` does NOT create duplicate licenses. Studio Solo activation safe under repeated triggers (renewal, sync errors, Edge Function retries).

#### 6.1.D Edge Functions (per Studio ADR-003)

```
supabase/functions/
├── acquire-slot/index.ts        # POST: { license_id, machine_fingerprint } -> slot_token
├── heartbeat/index.ts           # POST: { slot_token } -> { ok, expires_in_seconds }
├── release-slot/index.ts        # POST: { slot_token }
├── status/index.ts              # GET: { license_id } -> { seats_total, seats_available, active_machines[] }
├── reclaim-stale-slots/index.ts # CRON every minute: release slots с last_heartbeat > 5 min ago
└── activate-bundle/index.ts     # POST: { app_id_purchased } -> auto-create Solo licenses for related apps
```

#### 6.1.E Validators / pre-flight checks

`aurora_platform_core.schema_registry.validators`:

```python
def validate_registry_health() -> ValidationReport:
    """Run at app startup. Detect:
    - Cycles in any kind's migration graph.
    - Dead-end versions (registered but unreachable).
    - Missing target_version setting for declared kinds.
    - Migrations that produce data with schema_version != to_version.
    """

def validate_data_integrity(data: dict, kind: str) -> bool:
    """Check that data["schema_version"] field exists + valid."""

def hash_canonical(data: dict) -> str:
    """Stable SHA-256 hash of canonical JSON for tamper detection."""
```

**Не входит:**
- ❌ GUI for migration management (visual schema editor) — out-of-scope ever.
- ❌ Multi-tenancy в license tables (separate orgs / workspaces) — Phase D+.
- ❌ Audit log table для license changes — Phase B+ enhancement.
- ❌ License renewal automation (Stripe / Robokassa integration) — Phase C+.
- ❌ Per-feature usage metering — Phase B+ (telemetry covers это).
- ❌ License delegation / sub-licenses (agency assigns sub-seats к brand клиентам) — Phase B+.

### 6.2 Acceptance Criteria

**AC6.1 — BFS migration v1.0 → v3.0 chains через v2.0.**
- GIVEN data dict с `schema_version="1.0"` + legacy fields (e.g., `media_stds`).
- WHEN `SchemaRegistry.migrate(data, kind="aurora_bundle")`.
- THEN returns data с `schema_version="3.0"`, `media_stds` removed (v1→v2), Launch + Studio combined fields added (v2→v3).

**AC6.2 — Migration idempotency + path determinism.** (audit-revised H8)
- GIVEN v3.0 data.
- WHEN `migrate(migrate(data))` invoked.
- THEN result equals `migrate(data)` (no double-processing); migration registry validation confirms purity.
- **Path determinism (audit fix H8):** при registry с multiple equal-length BFS paths between same `(start, end)` versions, registry MUST register migrations as **commutative** (testable via property test: `path_A(data) == path_B(data)` для random data dicts). Если non-commutative обнаружен → `validate_registry_health()` warns + ADR-required resolution. Phase A scope: registry simple enough что commutativity holds trivially (linear chain v1→v2→v3); Phase B+ enforcement required при graph branching.

**AC6.3 — Cycle detection at registry validation.**
- GIVEN registry with cycle (e.g., 1.0→2.0→1.0 hypothetical bug).
- WHEN `validate_registry_health()` runs at startup.
- THEN raises `CircularMigration("kind=aurora_bundle, cycle: 1.0→2.0→1.0")`.

**AC6.4 — Forward-compat check graceful warning.**
- GIVEN `.aurora` bundle с schema_version="3.0", current app version 1.0.10 (которая supports max v2.0).
- WHEN `check_forward_compatibility(data, "aurora_bundle", "1.0.10")`.
- THEN returns `CompatResult(can_open=False, reason="требует Aurora >= 1.4.0", suggested_action="update_app")`.

**AC6.5 — License tier seed correctness.**
- GIVEN fresh Supabase project with migrations applied.
- WHEN `SELECT * FROM license_tiers ORDER BY id`.
- THEN returns 5 rows: free / pro / team / agency / enterprise с правильными seats_default + is_paid.

**AC6.6 — Cross-app bundle activation Edge Function.**
- GIVEN user purchases Aurora Optimize (Эконометрика rebrand).
- WHEN `activate-bundle` Edge Function called с `app_id_purchased="aurora_optimize"`.
- THEN auto-creates Solo Studio license for same user (per ADR-002 bundle-activation primary path); license row has tier="free"; user immediately accessible Studio.

**AC6.7 — Floating slot acquire concurrency safety.** (audit-revised B6)
- GIVEN 3-seat Team license, 2 active slots от machines M1, M2.
- WHEN 5 users from machines M3, M4, M5, M6, M7 simultaneously call `acquire-slot` Edge Function.
- THEN **exactly 1 succeeds** (per `SERIALIZABLE` transaction + `SELECT ... FOR UPDATE` pattern на app_licenses row); 4 receive `NoSlotsAvailable` 409 Conflict response. **NO race conditions corrupt slot count** (UNIQUE column в license_slots недостаточно — different machine_fingerprints все unique → 5 INSERT'ы все succeed без serializable transaction).
- Property test: 100 random concurrency scenarios, varying license seats + concurrent attempts → invariant `count(active_slots) ≤ seats_total` holds 100% времени.

**AC6.8 — Slot reclamation cron correctness.**
- GIVEN slot с `last_heartbeat_at = now() - 6 minutes`.
- WHEN `reclaim-stale-slots` cron runs.
- THEN slot's `released_at` set to current time; new acquire-slot succeeds for that license.

**AC6.9 — Aurora Эконометрика legacy license auto-migration.** (audit-revised B3)
- GIVEN Эконометрика v1.0.16 user with existing license row (pre-tier schema). Per memory `project_econometrica_target_architecture_v3` — это ТОЛЬКО демо-клиенты, нет paying customers.
- WHEN database migration applied + cross_app_license deployed.
- THEN existing license row updated с `tier_id="trial_6mo"` default (NOT "pro" — paid tier без payment record нарушает ledger); `valid_until = migration_timestamp + 6 months` per Aurora Suite migration plan; user opening Эконометрика → no flow changes (license check still passes). Pre-renewal sales conversation triggered 30 days before `valid_until`.

**AC6.10 — Hash canonical determinism.**
- GIVEN identical data dict в two different orderings (key insertion order varies).
- WHEN `hash_canonical(data)` called on both.
- THEN identical SHA-256 hashes (canonical JSON sort_keys=True).

### 6.3 Definition of Done

- [ ] **AC6.1–AC6.10 все pass.**
- [ ] **Code merged в `aurora-platform-core/schema_registry/`** + tagged.
- [ ] **Migration registry** for 6 kinds: `aurora_bundle`, `pickle_model`, `workflow_state`, `license`, `recipient_anchors`, `task_spec` — at least v1.0 → current target documented + tested.
- [ ] **Supabase migrations applied** в production project: 5 new tables (license_tiers, app_licenses extended, license_slots, license_features) + 5 Edge Functions deployed.
- [ ] **`MIN_APP_FOR_SCHEMA` registry** + `check_forward_compatibility` helper documented.
- [ ] **Pytest suite ≥ 80 tests:** BFS path resolution, idempotency, cycle detection, forward compat, schema bump roundtrips.
- [ ] **Property-based tests:** random valid migration graphs (Hypothesis) → BFS finds shortest path always.
- [ ] **Integration test с Aurora Эконометрика fixture:** legacy `.pickle` v1.0 → load through Schema Registry → migrate to v3.0 → save → reload — no data loss.
- [ ] **License migration test:** Aurora Эконометрика v1.0.16 production-like license rows → applied schema migrations → backwards compat verified (existing licenses still pass `check_license`).
- [ ] **Edge Function tests:** acquire/heartbeat/release/reclaim concurrency tested на staging Supabase project.
- [ ] **API docs:** `aurora-platform-core/docs/schema_registry.md` + `aurora-platform-core/docs/cross_app_license.md`.
- [ ] **CHANGELOG entry.**
- [ ] **ADRs:**
  - `aurora-knowledge/Decisions/aurora-schema-registry-bfs-migration.md`
  - `aurora-knowledge/Decisions/aurora-cross-app-license-tier-scaffolding.md` (Studio ADR-003 superseded или extended).

### 6.4 Test Data Requirements

**Synthetic schema fixtures:**
- `tests/fixtures/schemas/aurora_bundle/v1.0_minimal.json`
- `tests/fixtures/schemas/aurora_bundle/v2.0_with_robyn.json`
- `tests/fixtures/schemas/aurora_bundle/v3.0_full_launch_studio.json`
- Round-trip: v1.0 → migrate → v3.0 vs handcrafted v3.0 expected → equal.

**Real Aurora Эконометрика regression:**
- `tests/fixtures/real/aurora_v1.0.16_kagocel.pickle` — load through Schema Registry, migrate to current target.

**Supabase staging project:**
- Test project ref для Edge Function integration tests (separate from production).

**Concurrency fixtures:**
- 5+ test users for slot acquisition AC6.7.

**Property-based:**
- Hypothesis strategies для random migration graphs + random data dicts.

### 6.5 Зависимости

**Внутренние:**
- **Зависит от:** ничего из Phase A. C6 — foundation, собирается ПЕРВЫМ.
- **Используется:** C1 (persistence layer), C3 (workflow state), C5 (license schema, telemetry endpoint), C2 (bundle composer), C7 (signature verification).

**Блокирует:**
- ВСЕ остальные 6 компонентов Phase A. Build order: C6 first.

**Внешние:**
- **Pydantic v2** — все schemas.
- **packaging >= 23.0** — version comparison.
- **Supabase CLI** — migrations management.
- **Deno** (для Edge Functions runtime).

**Координационные:**
- **Антон approval:** schema_version strategy (single combined "3.0" for Studio + Launch vs separate). Default: combined (per coordination doc decision).
- **Маша небесная ADR sign-offs.**
- **Aurora Эконометрика maintainer:** legacy license auto-migration verified против production data.

### 6.6 Open questions для Маши небесной

1. **Migration rollback strategy:** если v2.0→v3.0 migration fails mid-way (e.g., disk full at file write), rollback к v2.0 или surface error? Default: rollback (atomic write paradigm). Phase A scope: file-level atomicity (temp file + rename), не in-process transactional rollback.

2. **License schema migration script для Эконометрика clients:** demo customers получают free 6mo Suite trial per memory `project_econometrica_target_architecture_v3.md`. Это applied как INSERT INTO app_licenses со специальным tier="trial_6mo"? Или extend "free" tier valid_until 6 месяцев? Default: new tier `trial_6mo` для clarity в analytics.

3. **schema_version в pickle vs `.aurora` bundle manifest.json:** pickle файл содержит schema_version в pickled dict; .aurora ZIP manifest.json также. Если они расходятся (corruption / manual editing), какой priority? Default: manifest.json wins (canonical для bundle), pickle field warning logged.

4. **Edge Function deployment orchestration:** Studio + Launch sharing same Supabase project → 5 Edge Functions deployed once. Studio team owns acquire/heartbeat/release/reclaim, Launch / Optimize own activate-bundle? Or all owned by platform team? Default: platform team owns all (Маша + Антон), per-app teams contribute changes through ADR.

5. **Schema versioning bump cadence:** combined v3.0 freezes Phase A. Когда v4.0 (Pro tier features Этап 2)? Per Studio strategic correction Q4 2026 / Q1 2027. Phase A scope = v3.0 frozen until pilot data lands. Confirm.

---

## Component 7: Web verifier (Methodology Certificate)

**Goal:** Public web tool `verify.auroraai.pro` — статический WebAssembly client, который позволяет любой стороне (регулятор / customer's CFO / customer's юрист / external audit) verify integrity Aurora's Methodology Certificate PDF + связанного `.aurora` файла **без отправки данных на сервер**. Это критичный trust-builder для фарма ICP — данные не покидают браузер пользователя, гарантировано через open-source WASM client.

### 7.1 Scope

**Входит:**

#### 7.1.A Methodology Certificate format spec

Per Aurora Launch ADR-002 + Sprint B4 deliverable spec (`02_Data_Spec/REPORT_SECTIONS_SPEC.md` Section 8 + Methodology Certificate PDF block).

**PDF structure:**
- **Page 1 (Starter / Pro tiers):** Aurora seal header + project metadata + headline forecast + tier badge (Gold/Silver/Bronze) + signature panel (visible hash) + version stamps + методология footer.
- **Page 2 (Pro+ tier only):** detailed math (priors used, sampler diagnostics, Gelman-Rubin, ESS, divergent transitions count, posterior predictive p-value) + audit trail summary.

**Embedded metadata (PDF info dictionary):**
```json
{
  "Title": "Aurora Methodology Certificate",
  "Subject": "<project_name>",
  "Producer": "Aurora <app_id> v<engine_version>",
  "Keywords": "AURORA_METHODOLOGY_CERT_v1",
  "/AuroraSignatureSHA256": "<sha256_hex>",
  "/AuroraEngineVersion": "aurora-platform-core==0.1.0; aurora-launch==1.4.0",
  "/AuroraGeneratedAt": "2026-05-XX T HH:MM:SS UTC",
  "/AuroraSchemaVersion": "3.0",
  "/AuroraBundleHash": "<sha256_of_companion_aurora_bundle>"
}
```

**Future-proofing for Ed25519 (audit fix H2):** info dict использует suffixed key `/AuroraSignatureSHA256` (не plain `/AuroraSignature`) чтобы Phase D+ мог добавить `/AuroraSignatureEd25519` без breaking changes. Phase A SHA-256 = **integrity check** (data not tampered); Phase D+ Ed25519 = **proof of origin** (Aurora private key signed). Marketing copy в UI должен честно framing'овать: «Verification confirms data integrity» (Phase A), не «Aurora authenticated this report».

**Companion `.aurora` file:** must be supplied вместе с PDF при verification (drag-drop both). Bundle's manifest.json contains:
```json
{
  "schema_version": "3.0",
  "bundle_metadata": {
    "target_app": "aurora_launch",
    "target_task": "new_brand_forecast",
    "engine_version": "aurora-platform-core==0.1.0; aurora-launch==1.4.0",
    "generated_at": "2026-05-XX T HH:MM:SS UTC"
  },
  "signature_sha256": "<sha256_hex>"
}
```

**Hash signature scope (audit fix B4):** signature computes hash over **canonical bundle data + canonical bundle_metadata EXCLUDING time-varying fields**. Specifically excluded из hash scope:
- `bundle_metadata.generated_at` — varies per generation, byte-different even with same inputs.
- PDF info dict `/AuroraGeneratedAt` — same.
- PDF `/CreationDate`, `/ModDate` — PDF library auto-sets timestamps.

Included в hash scope: bundle data parquet bytes + bundle_metadata fields {target_app, target_task, engine_version, schema_version, data_provenance hashes}.

**Reproducibility invariant (audit-revised B4):** two runs of same project at T1 ≠ T2 with identical inputs + deterministic seeds → produced bundles + PDFs have **identical signatures** (despite different generated_at timestamps). Это allows verifier to confirm «same project re-generated» as legitimate state, не tampered.

**PDF signature embedding flow:**
1. Generate PDF with placeholder `/AuroraSignatureSHA256` = "0000...".
2. Compute canonical hash over bundle (exclude generated_at).
3. Patch PDF info dict с computed hash via `lopdf` или similar low-level edit.
4. Bundle ↔ PDF coupling: bundle's `signature_sha256` field IS the same hash, PDF's `/AuroraBundleHash` references it for cross-check.

#### 7.1.B WebAssembly verifier client

**Stack:** Rust + `wasm-pack` → static JS bundle deployed на `verify.auroraai.pro`.

**Bundle target size:** ≤ 500 KB gzipped (per Aurora Launch REUSE WASM bundle ≤ 200 KB target — но verifier needs ZIP + PDF parsers + SHA-256). Actual estimate: 350-450 KB gzipped.

**Functionality:**

```
User opens verify.auroraai.pro
  ↓
Drag-drop PDF + .aurora ZIP (both required)
  ↓
WASM client:
  1. Parses PDF info dictionary → extracts /AuroraSignature, /AuroraEngineVersion, /AuroraGeneratedAt, /AuroraBundleHash
  2. Reads .aurora ZIP → extracts manifest.json
  3. Verifies bundle's "signature" field == recomputed SHA-256 of canonical manifest.json bytes
  4. Verifies PDF /AuroraBundleHash == bundle's signature
  5. Displays результат:
     ✓ Verified — signatures match. Engine version: <ver>. Generated: <ts>.
     ✗ Mismatch — explanation of which check failed.
```

**Deliberately NO network calls** during verification (verified via CSP headers + open-source code review).

#### 7.1.C UI Layout

Static HTML page (no SPA framework) с минималистичной UI per Aurora Hybrid Design System:

```
┌──────────────────────────────────────────────────────────────────┐
│  [Aurora seal]   verify.auroraai.pro                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│   Verify Aurora Methodology Certificate                            │
│   Проверьте подлинность отчёта без отправки данных на сервер.     │
│                                                                    │
│   ┌──────────────────────┐    ┌──────────────────────┐            │
│   │  📄  Drop PDF here    │    │  📦  Drop .aurora    │            │
│   │  Methodology Cert     │    │      bundle here     │            │
│   └──────────────────────┘    └──────────────────────┘            │
│                                                                    │
│   [Verify]                                                         │
│                                                                    │
│   ─────────────────────────────────────────────────────────       │
│                                                                    │
│   Result:                                                          │
│   ✓  Verified — signatures match.                                 │
│       Engine: aurora-platform-core==0.1.0; aurora-launch==1.4.0   │
│       Generated: 2026-05-15 14:23 UTC                             │
│       Project hash: a1b2c3...d4e5f6                               │
│                                                                    │
│   [Privacy Notice] All processing in your browser. No upload.      │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

**Locales:** RU + EN (toggle in header).

**a11y:** WCAG AA contrast verification, keyboard-navigable drop zones (file input fallback), screen reader announcements для verification results.

**Privacy banner:** prominent "All processing in your browser. No data leaves your device. Open-source: <link>." с clickable link to GitHub repo of WASM verifier.

#### 7.1.D Hosting / deployment

**Hosting:** Vercel (consistent с auroraai.pro static site).

**DNS:** `verify.auroraai.pro` CNAME к Vercel; existing auroraai.pro DNS provider unchanged.

**Build:** GitHub Actions:
- Trigger: push to `main` of `aurora-verifier-wasm` repo (new repo).
- Steps: cargo build wasm32 + wasm-pack pack + bundle JS + deploy Vercel.
- Output: static directory с `index.html`, `verifier.wasm`, `verifier.js`, locale strings.

**Open source:** entire WASM verifier repo public on GitHub (`Ackold26/aurora-verifier`), MIT license. Audit-friendly — anyone can build from source + verify deployed bundle = source.

#### 7.1.E Phase A scaffolding ↔ Phase B integration

**Phase A deliverable:**
- Static `verify.auroraai.pro` site live.
- WASM verifier handles PDF + `.aurora` v3.0 schema.
- Methodology Certificate PDF generation hook в `aurora_inference.persistence` (signature embedding).

**Phase B (Aurora Launch B4):** Methodology Certificate PDF generation per launch forecast (WeasyPrint per Aurora Launch S006 PDF generator decision). Phase A WASM verifier already supports this format.

**Не входит:**
- ❌ Server-side verification API (`POST /verify` endpoint) — explicitly NOT для privacy invariant.
- ❌ Verification audit log (server-side history of verifications) — NOT для privacy.
- ❌ PDF generation в WASM — Phase A scope = verifier only, generation = Inference Core / Aurora Launch B4.
- ❌ Signature signing с асимметричной криптографией (Ed25519) — Phase A = symmetric SHA-256 hashing (deterministic reproducibility focus). Asymmetric signing — Phase D consideration if customer demand (e.g., customer wants Aurora's private key to sign, customer verifies с public key). 
- ❌ Web verifier для других файлов (audit logs, other formats) — out-of-scope.
- ❌ Multi-tab / batch verification — single PDF + single bundle at a time.

### 7.2 Acceptance Criteria

**AC7.1 — Static site deployed + DNS resolves.**
- GIVEN production deployment.
- WHEN user opens https://verify.auroraai.pro в browser.
- THEN page loads within 2 sec; HTML render within 500 ms; WASM module fetched + initialized within 3 sec; UI fully interactive.

**AC7.2 — Drag-drop happy path.**
- GIVEN valid Methodology Certificate PDF + companion `.aurora` bundle.
- WHEN user drags PDF к first dropzone + bundle к second + clicks Verify.
- THEN within 5 sec на reference machine: result displays "✓ Verified" + engine version + generated timestamp + project hash; no network calls observed (verified via DevTools Network tab).

**AC7.3 — Detect tampered PDF (signature mismatch).**
- GIVEN PDF где байт изменён (e.g., narrative text edited).
- WHEN verified против untampered bundle.
- THEN result "✗ Signature mismatch" + specific reason "PDF /AuroraSignature does not match recomputed hash".

**AC7.4 — Detect tampered bundle (manifest mismatch).**
- GIVEN bundle where manifest.json edited (e.g., adversary меняет engine_version).
- WHEN verified против untampered PDF.
- THEN result "✗ Bundle integrity failure" + reason "Recomputed bundle hash does not match manifest's signature field".

**AC7.5 — Detect mismatched PDF + bundle pair.**
- GIVEN PDF от project A + bundle от project B (different projects).
- WHEN verified.
- THEN result "✗ Pair mismatch" + reason "PDF /AuroraBundleHash does not match supplied bundle's hash".

**AC7.6 — Privacy invariant (no network calls).**
- GIVEN any verification flow (success или mismatch).
- WHEN DevTools Network tab open during entire process.
- THEN: only initial static asset fetches (HTML + WASM + CSS + i18n strings); zero requests during verification; CSP header `connect-src 'self'` set + verified.

**AC7.7 — Error messages constructive (no false-positives).**
- GIVEN incompatible PDF (e.g., regular non-Aurora PDF).
- WHEN dropped + Verify clicked.
- THEN result "Not an Aurora Methodology Certificate" (detection by absence of `/AuroraSignature` PDF metadata key); does NOT say "verification failed" (would be misleading).

**AC7.8 — i18n RU + EN.**
- GIVEN browser language preference RU.
- WHEN page first opens.
- THEN UI strings в RU; toggle "EN" в header.
- WHEN toggle clicked.
- THEN strings switch live к EN; preference saved в localStorage.

**AC7.9 — a11y compliance.**
- GIVEN keyboard-only navigation (Tab, Enter).
- WHEN user navigates с keyboard.
- THEN: drop zones reachable via Tab; pressing Enter opens file picker (fallback); verification result announced via screen reader (`aria-live="polite"`); WCAG AA contrast verified with auto-tools (axe-core или Lighthouse).

**AC7.10 — Reproducibility test.** (audit-revised B4)
- GIVEN same Aurora project trained twice with identical inputs + deterministic seeds (NumPyro `random.PRNGKey(42)`) at T1 и T2.
- WHEN both runs export Methodology Certificate + bundle.
- THEN: PDF byte-level NOT identical (different `/AuroraGeneratedAt` + `/CreationDate`); BUT **`/AuroraSignatureSHA256` values match** (signature scope excludes timestamps per Section 7.1.A); bundle `signature_sha256` matches between runs; verifier displays «✓ Verified — same project re-generated at different times».
- This validates **content reproducibility**, не bytewise file equality (which is impossible due to embedded timestamps).

### 7.3 Definition of Done

- [ ] **AC7.1–AC7.10 все pass.**
- [ ] **`aurora-verifier-wasm` GitHub repo published** (Ackold26/aurora-verifier), MIT license, README с build instructions.
- [ ] **WASM bundle ≤ 500 KB gzipped** (measured + documented).
- [ ] **`verify.auroraai.pro` live** через Vercel + DNS configured + HTTPS verified.
- [ ] **PDF info dictionary writer** в `aurora_inference.persistence` (или `aurora_reporting`): `embed_methodology_signature(pdf_path, signature, engine_version, ...)`.
- [ ] **`.aurora` manifest.json schema v3.0** finalized с `signature` field — coordinated с C2 bundle composer.
- [ ] **Pytest для verifier** (Rust unit tests на WASM module): hash computation, ZIP parsing, PDF info dict parsing, mismatch detection. ≥ 30 tests.
- [ ] **E2E browser test** (Playwright): drag-drop PDF + bundle, verify success/mismatch flows. 5+ scenarios.
- [ ] **Privacy CSP audit:** `connect-src 'self'` strict, verified via response headers + manual audit.
- [ ] **a11y audit report** (axe-core или Lighthouse) — passes WCAG AA.
- [ ] **i18n strings** (RU + EN) frozen + reviewed by native speaker.
- [ ] **CHANGELOG entry.**
- [ ] **ADR:**
  - `aurora-knowledge/Decisions/methodology-certificate-public-web-verifier.md` (Маша небесная pending) — verified Accepted.
  - `aurora-knowledge/Decisions/aurora-pdf-signature-deterministic-sha256.md` (new) — rationale: SHA-256 vs Ed25519 trade-off для Phase A.

### 7.4 Test Data Requirements

**Reference Aurora project pairs (PDF + bundle):**
- `tests/fixtures/verifier/valid_kagocel/` — PDF + bundle (from Aurora Эконометрика production-like flow).
- `tests/fixtures/verifier/valid_launch_synthetic/` — PDF + bundle (from Aurora Launch Phase B test flow).

**Tampered cases:**
- `tests/fixtures/verifier/tampered_pdf_text.pdf` — narrative byte-edited.
- `tests/fixtures/verifier/tampered_pdf_metadata.pdf` — info dict edited.
- `tests/fixtures/verifier/tampered_bundle_manifest.aurora` — manifest.json edited.
- `tests/fixtures/verifier/mismatched_pair/` — PDF от project A + bundle от project B.

**Edge cases:**
- Non-Aurora PDF (regular invoice / random PDF).
- Corrupted ZIP (invalid bytes).
- Empty bundle.
- Future schema_version="4.0" (backwards compat: should fail gracefully с "newer schema, please update verifier").

**Reproducibility test:**
- Two Aurora project runs с identical inputs + seeds → produced PDFs match byte-by-byte (per AC7.10).

**Browser compatibility matrix:**
- Chrome 120+, Firefox 121+, Edge 120+, Safari 17+ (manual smoke test).

### 7.5 Зависимости

**Внутренние:**
- **Зависит от:** C1 Inference Core (`aurora_inference.persistence` для PDF info embedding hook), C2 Data Studio (bundle composer producing `signature` field), C6 Schema Registry (forward-compat для bundle schema version).
- **Не зависит от:** C3 (workflow engine), C4 (Tauri shell), C5 (no auth required для verifier — public tool).

**Блокирует:**
- Aurora Launch Sprint B4 — Methodology Certificate ship requires verifier live (otherwise customer gets PDF без verification path).
- Trust-builder для фарма pilot kickoffs (per S008 PILOT_CLIENT_PLAN — verifier mentioned in pilot trust-building materials).

**Внешние:**
- **Rust + wasm-pack** для WASM build.
- **lopdf Rust crate** для PDF info dict parsing (audit fix M7: chosen over pdfium-render — lopdf 200-500 KB vs pdfium 5+ MB; Phase A scope = info dict only, no full PDF rendering, lopdf sufficient).
- **zip Rust crate** для ZIP parsing.
- **sha2 Rust crate** для SHA-256.
- **Vercel** hosting (free tier для static — Phase A; Pro tier ~$20/mo если бandwidth growth).

**Координационные:**
- **Маша небесная ADR sign-off:** `methodology-certificate-public-web-verifier.md`.
- **Антон approval:** verifier scope (deterministic SHA-256 vs Ed25519 — Phase A choice). Confirmed default: SHA-256 для Phase A simplicity.
- **Аntoн approval:** Vercel hosting cost projection (likely free для Phase A, scales to ~$20-50/mo при customer growth).

### 7.6 Open questions для Маши небесной

1. **SHA-256 vs Ed25519 для signing (audit-revised H2):** Phase A default = SHA-256 deterministic hashing — это **integrity check (data not tampered)**, не **proof of origin**. Любой может recompute SHA-256 от bundle data — signature не доказывает что Aurora generated it. Для фарма regulatory trust — Ed25519 signing с Aurora's private key даёт proof of origin (verifier confirms «Aurora signed this»). PHASE_A spec future-proof'ен: PDF info dict использует suffixed `/AuroraSignatureSHA256`, легко добавить `/AuroraSignatureEd25519` Phase D+ без breaking. Marketing copy в Phase A UI HONESTLY framing'ует «integrity verified» вместо «authenticity verified» — overpromise рискует backfire при дispute scenario.

2. **Scope of `bundle_metadata` в hash:** какие поля из manifest.json включаются в canonical hash computation? Default proposal: `target_app`, `target_task`, `engine_version`, `generated_at`, `schema_version`, `data_provenance`. Изменение reasons / human comments — не входит (allows customer-side annotations без breaking signature).

3. **Verifier UX flow для multi-page certificate (Pro+ tier):** Pro+ Methodology Certificate = 2 страницы (math + diagnostics). Single signature covers оба или per-page signatures? Default: single signature (entire PDF is one artifact).

4. **Локаль для verifier по умолчанию:** RU primary (фарма ICP в РФ). Если browser language = EN (международные регуляторы / external auditors) — auto-switch к EN. Default: detect navigator.language, fallback к RU.

5. **Verifier versioning:** verifier WASM version coupled с schema_version it supports. Если customer тестирует bundle v3.1 в verifier built for v3.0 → graceful "newer schema, please update verifier при https://verify.auroraai.pro" message. Phase A scope = single deployed version (latest); old verifier versions не archived. Confirm.
