# Aurora Launch - Test Strategy

**Status:** v1.0 (2026-05-04)
**Source:** Critical audit finding A11

## Контекст

Тест strategy для Aurora Launch критична потому что:
- Premium pricing (1.5-3M/год) = high stakes на correctness
- Transfer learning math сложнее чем standard MMM (proxy + recipient + posterior update)
- Backwards compat critical (старые .aurora projects must open в Launch)
- Regression risk в shared engines (Optimize/Brand не должны сломаться)

Этот документ - test pyramid + coverage targets + property-based design.

---

## 1. Test Pyramid

```
       ╱╲           E2E (5%)
      ╱──╲          → Tauri WebDriver smoke на critical flows
     ╱────╲
    ╱──────╲       Integration (15%)
   ╱────────╲      → Real engines, mock UI
  ╱──────────╲
 ╱────────────╲   Unit (80%)
─────────────── → Pure functions, mock external deps
```

**Targets (revised post-audit 2026-05-04):**
- Math layer (Bayesian/MCMC): **70-80% line coverage** + **property-based suite** (Hypothesis 50+ properties) + **10+ reference comparison tests** (vs Robyn / pymc / Stan где applicable). MCMC stochastic outputs не allow реальное 90% coverage.
- API layer (pure functions): **90%+ line coverage**
- Glue / UI layer: **80%+ line coverage**
- Integration: critical flows covered (proxy → adapt → forecast)
- E2E: smoke tests на pilot scenarios (Sprint B6)

**Test approach для MCMC code:**
- Property-based testing (Hypothesis) - math invariants
- Reference comparison - same data → comparable inference vs Robyn/pymc
- Posterior predictive checks
- Simulation-Based Calibration (SBC) - используется в Aurora Econometrica v1.0.16
- Goodness-of-fit tests
- Coverage метрика на математических branches не самоцель

---

## 2. Unit Tests (80%, ~400+ tests target Phase B)

### 2.1 Math layer (`engines/`)

**`engines/launch_adapt.py`:**
- `test_extract_proxy_priors_returns_shape_only()` - assert magnitudes NOT в priors
- `test_apply_recipient_magnitudes_rescales_correctly()` - β scale matches anchors
- `test_extract_priors_uncertainty_propagated()` - prior variance reflects model uncertainty
- `test_apply_to_zero_anchors_raises()` - validate critical anchors required

**`engines/single_proxy_transfer.py`:**
- `test_single_proxy_no_hierarchical_degeneracy()` - no MCMC divergences с single proxy
- `test_train_with_recipient_data_partial()` - partial pooling working
- `test_forecast_horizons_consistent()` - 12 ⊂ 26 ⊂ 52 means

**`engines/multi_proxy_hierarchical.py`:**
- `test_multi_proxy_hierarchical_with_n_2()` - works correctly, no degeneracy
- `test_multi_proxy_hierarchical_with_n_3()` - works correctly
- `test_partial_pooling_weights_sum_to_one()` - weight normalization
- `test_extreme_proxy_outlier_robust()` - one bad proxy doesn't dominate

**`engines/launch_posterior_update.py`:**
- `test_ess_based_weighting_monotonic()` - more recipient data → less proxy weight
- `test_initial_state_full_proxy()` - T=0 → 100% proxy
- `test_proxy_weight_floor_at_5_percent()` - residual proxy in priors
- `test_audit_trail_logged()` - each update event recorded

**`engines/launch_validators.py`:**
- `ProxyDataValidator` tests - 24+ months coverage, gaps, currency consistency
- `RecipientAnchorsSemanticValidator` tests - SoV/share consistency, distribution velocity, pricing extreme
- `TransferConfidenceCalculator` tests - threshold mapping (High/Medium/Low/Insufficient)

**`engines/similarity_calculator.py`:**
- `test_similarity_score_range_0_1()` - bounds
- `test_perfect_similarity_returns_1()` - identical dimensions
- `test_zero_similarity_returns_0()` - completely different
- `test_weights_sum_to_1()` - validation
- `test_python_wasm_consistency_within_tolerance()` - same logic in Python (backend) + Rust→WASM (frontend) дают same score within 1e-6 numerical tolerance (floating point arithmetic differences ожидаемы)
- Golden test fixtures (10-20 known input → output pairs, regenerate when intentional change)

**`engines/launch_forecast.py`:**
- `test_horizon_uncertainty_monotonic()` - CI grows с horizon
- `test_decomposition_sums_to_total()` - components add up
- `test_negative_forecast_blocked()` - sales can't be negative
- `test_uncertainty_decomposition_complete()` - sum of sources = total

**`engines/schema_registry.py`:**
- `test_v2_to_v3_migration_preserves_data()` - no data loss
- `test_unknown_schema_version_raises()` - safety
- `test_forward_compat_default_fields()` - new optional fields default None

### 2.2 Backend API (`sidecar/launch_routes.py`)

- Each endpoint: success path + 3-5 error cases
- Pydantic validation tests per endpoint
- Authentication tests
- Rate limiting (если applicable)

### 2.3 Frontend stores (`src/lib/stores/launch*.ts`)

- Reactive store updates
- Derived store correctness
- Validation flow integration

### 2.4 Format adapters (`engines/data_adapters/`)

- DSM V2023, V2024 each: detect + parse + canonicalize
- Mediascope TV V2023, V2024
- Mediascope Digital V2023, V2024
- AdIndex Digital Budget V2023, V2024
- V2025 adapters добавляются когда vendors release 2025 formats (~июль 2026)
- Edge cases: empty file, corrupted format, mixed encodings, partial data

### 2.5 Pydantic schemas

- Field validation per `RecipientAnchorsV1`
- Cross-field validators (e.g., paused brand consistency)
- JSON schema export round-trip (Pydantic → JSON Schema → Pydantic)

---

## 3. Integration Tests (15%, ~80 tests target Phase B)

### 3.1 Full proxy → forecast flow

```python
# tests/integration/test_full_launch_flow.py

def test_full_launch_flow_fmcg_snacks():
    """End-to-end: import → validate → adapt → train → forecast."""

    # 1. Import proxy data
    dsm_df = parse_dsm_excel("fixtures/proxy_fmcg_snacks_dsm.xlsx")
    ms_df = parse_ms_excel("fixtures/proxy_fmcg_snacks_ms.xlsx")

    proxy_validator = ProxyDataValidator()
    result = proxy_validator.validate(dsm_df, ms_df)
    assert result.is_sufficient

    # 2. Recipient anchors
    anchors = RecipientAnchorsV1(
        market_size_rub=5_000_000_000,
        planned_share_pct=3.0,
        # ...
    )
    semantic_validator = RecipientAnchorsSemanticValidator()
    issues = semantic_validator.validate(anchors)
    assert len([i for i in issues if i.severity == "error"]) == 0

    # 3. Train proxy model
    proxy_model = train_proxy_model(dsm_df, ms_df)

    # 4. Adapt
    priors = extract_proxy_priors(proxy_model)
    recipient_priors = apply_recipient_magnitudes(priors, anchors)

    # 5. Forecast
    forecast = generate_forecast(recipient_priors, horizons=[12, 26, 52])

    assert forecast.horizons[0].mean.shape[0] == 12
    assert forecast.horizons[1].mean.shape[0] == 26
    assert forecast.horizons[2].mean.shape[0] == 52
    assert forecast.uncertainty_decomposition.total > 0
```

### 3.2 Posterior update flow

```python
def test_posterior_update_reduces_proxy_weight():
    # T=0 forecast
    initial_forecast = generate_forecast(...)
    initial_weight = compute_proxy_weight(initial_forecast)
    assert initial_weight > 0.95  # ~100%

    # Add 4 weeks recipient data
    updated_forecast = posterior_update(initial_forecast, new_data_4w)
    updated_weight = compute_proxy_weight(updated_forecast)
    assert updated_weight < initial_weight
    assert updated_weight > 0.6  # not too aggressive

    # Add 12 weeks total recipient data
    further_forecast = posterior_update(updated_forecast, new_data_8w_more)
    further_weight = compute_proxy_weight(further_forecast)
    assert further_weight < 0.5
```

### 3.3 Backwards compatibility (Sprint B0.5)

```python
# tests/integration/test_bc_corpus.py

import pytest
from pathlib import Path

@pytest.mark.parametrize("project_path", BC_TEST_CORPUS_PATHS)
def test_old_aurora_project_opens_in_launch(project_path: Path):
    """Old .aurora projects from Econometrica open в Launch без data loss."""
    project = open_aurora_project(project_path)

    # Critical fields preserved
    assert project.metadata is not None
    assert project.media_data is not None
    assert project.sales_data is not None

    # Launch fields default к None
    assert project.proxy_brand_metadata is None
    assert project.recipient_anchors is None

    # Re-export saves correctly
    exported = export_aurora_project(project)
    assert exported.exists()

    # Re-open consistent
    reopened = open_aurora_project(exported)
    assert reopened.metadata == project.metadata
```

### 3.4 Format adapter integration

```python
@pytest.mark.parametrize("dsm_format", ["V2023", "V2024", "V2025"])
def test_dsm_format_round_trip(dsm_format: str):
    fixture = f"fixtures/dsm_{dsm_format}.xlsx"
    detector = DsmFormatDetector()
    detected = detector.detect(pd.read_excel(fixture))
    assert detected == dsm_format

    adapter = get_dsm_adapter(detected)
    df = adapter.parse(fixture)

    # Canonical schema check
    expected_cols = {"brand_id", "period", "geo_code", "sales_rub", "sales_packs", ...}
    assert expected_cols.issubset(df.columns)
```

---

## 4. E2E Tests (5%, ~10 tests target Phase B)

### 4.0 Tauri E2E - tooling reality (post-audit note)

**Tauri WebDriver state (2026):** `tauri-driver` (alpha state) ограничен. Не все webview operations supported. Plan accordingly:

**E2E approach:**
- 5-10 critical smoke flows через `tauri-driver` (что works)
- **Manual smoke tests** (recorded scripts + checklist) для остальных
- Visual regression через screenshot comparison (Percy / Chromatic / local diff)
- **Phase D consideration:** переход на Playwright + custom Tauri bridge когда tooling matures

### 4.1 Tauri WebDriver smoke tests (Sprint B6)

```python
# tests/e2e/test_launch_smoke.py

def test_e2e_create_project_to_forecast(driver):
    """Smoke: create project, fill anchors, generate forecast."""

    driver.get("tauri://localhost")
    # ... navigation steps

    # Create project
    driver.click("button[data-test=new-project]")
    driver.fill("input[name=project-name]", "Smoke Test FMCG")

    # Proxy selection
    driver.click("[data-test=proxy-template-fmcg-snacks]")  # template loads sample

    # Anchors
    driver.fill("input[name=market_size_rub]", "5000000000")
    # ...

    # Generate forecast
    driver.click("button[data-test=generate-forecast]")
    driver.wait_for("[data-test=forecast-cone-chart]", timeout=120)

    # Assertion
    assert driver.is_element_visible("[data-test=tier-badge-silver]")
```

### 4.2 Pilot scenarios (Sprint B6)

- FMCG Snacks Launch end-to-end (pilot client cohort)
- OTC Pharma Launch end-to-end
- Premium Cosmetic Launch end-to-end

---

## 5. Property-Based Tests (Hypothesis)

Math invariants which MUST hold для any valid input:

### 5.1 Forecast invariants

```python
from hypothesis import given, strategies as st

@given(
    market_size=st.floats(min_value=1e6, max_value=1e12),
    share=st.floats(min_value=0.1, max_value=50),
    horizon=st.integers(min_value=1, max_value=52),
)
def test_forecast_mean_positive_for_positive_inputs(market_size, share, horizon):
    """Forecast mean cannot be negative для valid positive inputs."""
    anchors = build_anchors(market_size_rub=market_size, planned_share_pct=share)
    priors = build_priors_default()
    forecast = generate_forecast(priors, anchors, horizons=[horizon])
    assert all(f >= 0 for f in forecast.horizons[0].mean)


@given(horizon_pairs=st.lists(st.integers(1, 52), min_size=2, max_size=2, unique=True))
def test_uncertainty_grows_with_horizon(horizon_pairs):
    """CI width должна расти с horizon."""
    h1, h2 = sorted(horizon_pairs)
    forecast = generate_forecast(default_priors, default_anchors, horizons=[h1, h2])
    ci_width_h1 = forecast.horizons[0].ci_upper[-1] - forecast.horizons[0].ci_lower[-1]
    ci_width_h2 = forecast.horizons[1].ci_upper[-1] - forecast.horizons[1].ci_lower[-1]
    assert ci_width_h2 >= ci_width_h1


@given(weight=st.floats(min_value=0, max_value=1))
def test_partial_pooling_weight_in_range(weight):
    """Pooling weight всегда 0..1."""
    forecast = generate_forecast_with_weight(weight)
    actual_weight = forecast.proxy_weight
    assert 0 <= actual_weight <= 1
```

### 5.2 Similarity invariants

```python
@given(dim1=st.dictionaries(...), dim2=st.dictionaries(...))
def test_similarity_symmetric(dim1, dim2):
    """similarity(A, B) == similarity(B, A)."""
    score_ab = compute_similarity(dim1, dim2)
    score_ba = compute_similarity(dim2, dim1)
    assert abs(score_ab - score_ba) < 1e-9


@given(dims=st.dictionaries(...))
def test_similarity_self_is_one(dims):
    """Similarity к себе = 1.0."""
    assert compute_similarity(dims, dims) == 1.0
```

### 5.3 Schema migration invariants

```python
@given(v2_data=st.dictionaries(...))
def test_v2_to_v3_then_back_no_loss(v2_data):
    """Migration round-trip preserves все existing fields."""
    v3 = SchemaRegistry.migrate(v2_data, "3.0")
    # Check все original keys still present
    for key in v2_data:
        if key != "schema_version":
            assert key in v3
            assert v3[key] == v2_data[key]
```

---

## 6. Regression Tests

### 6.1 Aurora Optimize regression (CRITICAL)

Aurora Launch не должен сломать Optimize. CI gate:

```bash
# .github/workflows/aurora_launch.yml
- name: Optimize regression suite
  run: pytest Aurora_Econometrica/ -k "not slow"
  # All 552+ existing Optimize tests должны pass
```

### 6.2 Live-test client cases (Кагоцел, Венарус, FMCG)

Существующие cases в Aurora Optimize:
- Кагоцел post-fix Phase 0.1 (lift +6%, scale verdict)
- Венарус L22+L23 fixes
- FMCG synthetic case

Сохранить как **golden tests** - results не должны drift при Launch changes.

### 6.3 Performance regression (audit A9)

```python
# tests/performance/test_launch_performance.py

@pytest.mark.performance
def test_single_proxy_train_under_30s():
    proxy_data = load_fixture("proxy_fmcg_snacks_24m.xlsx")
    anchors = load_fixture("recipient_anchors_default.json")

    start = time.perf_counter()
    model = train_single_proxy_transfer(proxy_data, anchors)
    elapsed = time.perf_counter() - start

    assert elapsed < 30.0, f"Single-proxy train took {elapsed:.1f}s (budget 30s)"


@pytest.mark.performance
def test_multi_proxy_n3_train_under_90s():
    # Similar для multi-proxy N=3
    ...


@pytest.mark.performance
def test_forecast_52w_under_5s():
    ...
```

---

## 7. Test Corpus Management

### 7.1 Fixture files

`fixtures/` structure:
```
fixtures/
├── proxy/
│   ├── fmcg_snacks/
│   │   ├── dsm_24m.xlsx
│   │   ├── ms_tv_18m.xlsx
│   │   └── ms_digital_18m.xlsx
│   ├── otc_pharma/
│   ├── premium_cosmetic/
│   ├── energy_drink/
│   └── telecom/
├── recipient/
│   └── anchors_*.json
├── bc_corpus/
│   ├── kagocel_v1.0.16.aurora
│   ├── venarus_v1.0.16.aurora
│   ├── fmcg_synthetic_*.aurora
│   └── (10+ projects)
└── format_versions/
    ├── dsm_v2023.xlsx
    ├── dsm_v2024.xlsx
    ├── dsm_v2025.xlsx
    ├── ms_tv_v2023.xlsx
    ├── ms_tv_v2024.xlsx
    └── adindex_digital_v2024.xlsx
```

### 7.2 Synthetic data generation

Tools для test fixtures:
- `tools/generate_synthetic_proxy.py` - configurable scenarios
- `tools/generate_synthetic_recipient.py` - new brand / paused brand
- `tools/inject_format_version.py` - simulate format changes

### 7.3 Aurora_Test_Corpus repo (audit B9)

Recommendation: separate private repo `Aurora_Test_Corpus`:
- Versioned fixtures
- Real (with consent) + synthetic mix
- Linked в pytest через `pytest-datadir`
- Не git-LFS (DSM/MS файлы небольшие)

---

## 8. Coverage Reporting

### 8.1 Tools

- **Python:** `pytest-cov` + Coverage.py
- **Frontend:** Vitest coverage с c8
- **Combined report** через CodeCov / Coveralls

### 8.2 CI gates

`.github/workflows/aurora_launch.yml`:
- Unit coverage >= 90% (math layer) или 80% (UI/glue) - blocking
- Integration tests все pass - blocking
- E2E smoke tests pass на staging - blocking
- Regression Optimize/Brand pass - blocking
- Performance budgets met - blocking

### 8.3 Coverage targets per Sprint

| Sprint | Coverage target | Cumulative tests |
|---|---|---|
| B0 (concept) | N/A (docs only) | 0 |
| B0.5 (BC corpus) | N/A (fixtures) | 10+ corpus items |
| B1 (schema) | 90% schema | 30 |
| B1.5 (CS Lite) | 80% tracker | 40 |
| B2 (proxy UI) | 85% | 100 |
| B3 (adapt + transfer) | 90% math | 200 |
| B4 (reports) | 80% | 280 |
| B5 (posterior) | 90% math | 380 |
| B6 (pilot) | 90% overall | 480+ |

---

## 9. Test Authoring Guidelines

### 9.1 Naming conventions

- `test_<what>_<expected_behavior>()` - clear, readable
- `test_<what>_when_<condition>_then_<result>()` - for complex behavior

### 9.2 AAA pattern

```python
def test_extract_priors_returns_shape_only():
    # Arrange
    proxy_model = build_test_model()

    # Act
    priors = extract_proxy_priors(proxy_model)

    # Assert
    assert "adstock_decay" in priors
    assert "hill_shape" in priors
    assert "beta_magnitude" not in priors  # critical: shape only
```

### 9.3 Fixtures with `pytest-fixtures`

```python
@pytest.fixture
def fmcg_snacks_proxy_model():
    return load_pretrained_model("fixtures/proxy/fmcg_snacks/trained_model.pkl")

@pytest.fixture
def default_recipient_anchors():
    return RecipientAnchorsV1(...)
```

---

## Связанные документы

- `PERFORMANCE_BUDGETS.md` - performance test thresholds
- `../00_Overview/ROADMAP.md` - test deliverables per Sprint
- `REUSE_FROM_ECONOMETRICA.md` - shared engines test inheritance
