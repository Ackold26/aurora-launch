# Aurora Launch - Reuse Map from Aurora Econometrica

**Status:** v1.0 (2026-05-04)
**Authority:** P9 в `00_Overview/PRINCIPLES.md`

## Контекст

Aurora Launch не parallel codebase к Aurora Econometrica - это **расширение** через shared engines + design system + Tauri shell template. Цель: 80%+ reuse, минимизировать engineering overhead, ensure consistency между Suite apps.

Этот документ - explicit map: что переиспользуем, что расширяем, что новое.

---

## 1. Полностью переиспользуем (zero changes)

### 1.1 Engines (Bayesian MMM core)

| Module | Source path | Purpose в Launch |
|---|---|---|
| `engines/modeler.py` | `Aurora_Econometrica/engines/modeler.py` | Bayesian MMM training (после adapt-step) |
| `engines/decomposer.py` | `Aurora_Econometrica/engines/decomposer.py` | Decomposition contributions (за periods 12/26/52) |
| `engines/optimizer.py` | `Aurora_Econometrica/engines/optimizer.py` | Budget optimization (post-launch reallocation) |
| `engines/scenario.py` | `Aurora_Econometrica/engines/scenario.py` | What-if scenarios |
| `engines/conformal.py` | `Aurora_Econometrica/engines/conformal.py` | Conformal Prediction CI (Aurora differentiator) |

**Phase A integration:** эти engines extracted в `aurora-platform-core` package (Phase A deliverable). Aurora Launch imports как dependency.

**Code path traces:**
- After `launch_adapt.extract_proxy_priors()` → `modeler.train(model_data, priors=transferred_priors)`
- Forecast generation → `decomposer.contributions_per_channel()` для launch periods
- Budget allocation → `optimizer.optimize(constraints=launch_anchors_constraints)`

### 1.2 Reporting layer

| Module | Source path | Purpose в Launch |
|---|---|---|
| `aurora_html/` | `Aurora_Econometrica/aurora_html/` | HTML interactive report adapter |
| `aurora_pptx/` | `Aurora_Econometrica/aurora_pptx/` | PPTX template engine |
| Rust XLSX writer | `Aurora_Econometrica/src-tauri/src/xlsx_writer/` | XLSX export |

**Reuse mechanism:** shared narrative_adapter pattern (как в Econometrica) - aurora_html + aurora_pptx pull data from common adapter.

**Launch-specific:** новый template `launch_forecast.report.yaml` в `aurora_pptx/launch_forecast/` (новые секции, но shared engine).

### 1.3 Design System

| Asset | Source | Purpose |
|---|---|---|
| Aurora tokens.json | `D:/Docs/Aurora_Ai/Standards/tokens.json` | Aurora Hybrid Design System |
| Aurora hybrid components (4 TSX) | `06_Aurora_Design_system/03_Hybrid_Design_System/` | UI primitives |
| Sacred Lime + Aurora Deep + Gold tokens | tokens.json | Visual identity |
| Inter Variable + Lora WOFF2 | `aurora_html/assets/fonts/` | Typography |
| Aurora wordmark (custom letterforms) | `06_Aurora_Design_system/05_Logo/` | Branding |

**Per-app accent:** Aurora Launch = **Electric Blue** (per Suite strategy 2026-05-02).

### 1.4 Tauri shell template

Aurora Launch boots от Phase A Tauri shell template:
- Standard cabinets layout (Home, Pipeline, Settings, Help)
- Updater integration (cross-app shared)
- License management (cross_app_license framework Phase A)
- Window management
- Theme switching (light / dark / fun)
- Help system framework

**Aurora Launch specifics:** custom cabinets pour Pipeline (4 launch-specific steps).

### 1.5 Data layer (Phase A Data Studio)

| Component | Phase A deliverable | Reuse в Launch |
|---|---|---|
| DSM Group importer | Data Studio MVP | Полное reuse - import proxy DSM data |
| Mediascope TV importer | Data Studio MVP | Полное reuse - import proxy MS TV |
| Mediascope Digital importer | Data Studio MVP (Phase B parallel) | Полное reuse |
| AdIndex Digital Budget importer | Data Studio Phase B | Полное reuse (alternative source) |
| Custom CSV/XLSX import | Data Studio MVP | Полное reuse (recipient history fallback) |
| Format adapters | Data Studio Phase B (Aurora Launch Sprint B0.5) | Полное reuse |

### 1.6 Trust 3 Hierarchical Bayesian (shipped в Econometrica v1.0.16)

- Hierarchical priors brand vs performance (existing)
- Channel categorization
- Validate UI badges layer

**Launch use:** Trust 3 hierarchical engine - **base for proxy → recipient transfer** (single-proxy mode = direct, multi-proxy mode = true hierarchical).

### 1.7 Conformal Prediction (Aurora differentiator) - **adapted для transfer scenario**

- Distribution-free CI (S-OLS-1, S-Bayes-1) в Aurora Econometrica
- Triple-CI: frequentist β + bootstrap ROI HDI + conformal PI

**ВАЖНО:** Conformal Prediction (Vovk 2005) предполагает **exchangeability** training data. Transfer scenario (proxy → recipient) violates это assumption. Прямое reuse `engines/conformal.py` некорректно.

**Adaptation strategy для Launch (Sprint B5):**
- **Pre-launch (zero recipient data):** conformal CI from proxy + transfer uncertainty inflation factor (calibrated на synthetic transfers с known truth)
- **Post-launch (some recipient data):** hybrid approach
  - Recipient data >= 12 weeks: standard conformal на recipient calibration set (proxy в priors only)
  - Recipient data 4-12 weeks: hybrid weighted
  - Recipient data < 4 weeks: still inflated proxy CI
- **Reference:** Tibshirani et al. 2019 "Conformal Prediction Under Covariate Shift" (NeurIPS)

**Implementation:** новый module `engines/launch_conformal.py` (НЕ direct reuse `engines/conformal.py`):
```python
# engines/launch_conformal.py
class LaunchConformalCalibrator:
    """Conformal CI adapted для transfer scenarios."""

    INFLATION_FACTOR_BY_SIMILARITY = {
        # Higher similarity = lower inflation needed
        "high": 1.2,    # similarity >= 0.85
        "medium": 1.5,  # 0.65-0.85
        "low": 2.0,     # 0.50-0.65
    }

    def calibrate_pre_launch(
        self, proxy_forecast, similarity_score: float
    ) -> ConformalCI:
        """Inflated proxy CI based on similarity tier."""
        ...

    def calibrate_with_recipient(
        self, recipient_data, weeks_count: int
    ) -> ConformalCI:
        """Standard conformal на recipient calibration set."""
        ...
```

**Launch:** uncertainty decomposed по источникам (proxy / transfer / anchor / sampling - см. ForecastHorizon.uncertainty_decomposition в schema extensions).

### 1.8 KPI Registry pattern (shipped v1.2.0 Foundation)

Existing config pattern:
- `kpi_sales` config (frozen)
- `kpi_awareness` config (frozen)

**Launch use:** kpi_sales config - используется как-есть. Awareness config не используется (P8 boundary - awareness в Brand).

---

## 2. Расширяем (additive changes, не breaking)

### 2.1 Pickle schema (v3.0 additive)

**Existing v2.0** (Econometrica):
- `model_version`, `intercept_mean`, `control_betas_mean`, `media_stds`
- `kpi_config` (sales / awareness frozen)
- ... existing fields

**Launch additions (additive, default None / [] / {}):**
- `proxy_brand_metadata: Optional[ProxyBrandMetadata]` (см. DATA_REQUIREMENTS Section 5.1)
- `recipient_anchors: Optional[RecipientAnchorsV1]`
- `transfer_provenance: Optional[TransferProvenance]` - какие parameters transferred
- `forecast_horizons: Optional[ForecastHorizons]` - 12/26/52 results
- `posterior_update_log: List[PosteriorUpdateEvent]` - audit trail
- `consulting_hours_log: Optional[List[ConsultingEvent]]` - hour tracking

**Type definitions для new schema fields:**

```python
# engines/launch_schema_extensions.py
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class TransferProvenance(BaseModel):
    """Audit trail для что именно перенесено из proxy в recipient."""
    schema_version: Literal["1.0"] = "1.0"
    proxy_engine_version: str  # e.g., "single_proxy_transfer/0.1.0"
    transferred_parameters: List[Literal[
        "adstock_decay_per_channel",
        "hill_saturation_shape",
        "reach_freq_curve_shape",
        "category_seasonality",
        "long_term_trend",
    ]]
    excluded_parameters: List[str]  # e.g., ["beta_magnitude", "baseline"]
    similarity_aggregate: float = Field(ge=0, le=1)
    transfer_timestamp: datetime
    notes: Optional[str] = None

class ForecastHorizon(BaseModel):
    """Single horizon forecast result with full uncertainty decomposition."""
    horizon_weeks: int = Field(ge=1, le=52)
    mean: List[float]  # length == horizon_weeks
    ci_50_lower: List[float]
    ci_50_upper: List[float]
    ci_80_lower: List[float]
    ci_80_upper: List[float]
    ci_95_lower: List[float]
    ci_95_upper: List[float]
    # uncertainty decomposition: total = sum of sources
    uncertainty_decomposition: dict[Literal[
        "proxy_uncertainty",
        "transfer_uncertainty",
        "anchor_uncertainty",
        "sampling_uncertainty",
    ], float]

class ForecastHorizons(BaseModel):
    """All three forecast horizons (12/26/52 weeks)."""
    horizon_12w: ForecastHorizon
    horizon_26w: ForecastHorizon
    horizon_52w: ForecastHorizon

class PosteriorUpdateEvent(BaseModel):
    """Audit log entry for posterior update."""
    timestamp: datetime
    weeks_of_recipient_data: int
    proxy_weight_before: float = Field(ge=0, le=1)
    proxy_weight_after: float = Field(ge=0, le=1)
    triggering_data_hash: str  # SHA-256 of incremental recipient data
    note: Optional[str] = None

class ConsultingEvent(BaseModel):
    """Hour tracking entry."""
    timestamp: datetime
    event_type: Literal[
        "proxy_review",
        "posterior_update_session",
        "methodology_question",
        "training",
        "onsite",
        "kickoff",
        "quarterly_review",
    ]
    duration_minutes: int = Field(gt=0, le=600)
    note: Optional[str] = None
```

**Backwards compat:**
- Старые .aurora открываются в Launch (Launch fields = None defaults)
- Новые .aurora с Launch fields открываются в Econometrica - launch fields ignored
- Forward-incompatibility: при попытке Econometrica < v1.0.16 открыть v3.0 schema - explicit warning + suggested action

**Forward compat check helper:**

```python
from packaging import version

# Map: schema_version -> minimum app version that supports it
MIN_APP_FOR_SCHEMA = {
    "1.0": "1.0.0",
    "2.0": "1.0.10",
    "3.0": "1.4.0",  # Aurora Launch / Suite v1.4.0
}

class CompatResult(BaseModel):
    can_open: bool
    reason: Optional[str] = None
    suggested_action: Optional[Literal[
        "update_app", "use_compatible_version", "ignore_warning"
    ]] = None

def check_forward_compatibility(
    data: dict, current_app_version: str
) -> CompatResult:
    schema_ver = data.get("schema_version", "1.0")
    min_app = MIN_APP_FOR_SCHEMA.get(schema_ver)
    if not min_app:
        return CompatResult(
            can_open=False,
            reason=f"Unknown schema_version: {schema_ver}",
        )
    if version.parse(current_app_version) < version.parse(min_app):
        return CompatResult(
            can_open=False,
            reason=(
                f"Этот project требует Aurora >= {min_app} "
                f"(установлена {current_app_version}). Обновите приложение."
            ),
            suggested_action="update_app",
        )
    return CompatResult(can_open=True)
```

**Schema registry pattern** (Sprint B1) - corrected implementation:

```python
# engines/schema_registry.py

from typing import Callable, Dict, List, Tuple
from packaging import version

class SchemaRegistry:
    """Centralized pickle schema versions + migrations с topological resolution."""

    _migrations: Dict[Tuple[str, str], Callable] = {}

    @classmethod
    def register(cls, from_version: str, to_version: str):
        """Decorator: регистрирует migration из from_version в to_version."""
        def decorator(fn: Callable[[dict], dict]):
            cls._migrations[(from_version, to_version)] = fn
            return fn
        return decorator

    @classmethod
    def migrate(cls, data: dict, target_version: str = "3.0") -> dict:
        """Migrate data к target_version, выбирая optimal path через registered migrations."""
        current = data.get("schema_version", "1.0")
        if current == target_version:
            return data

        path = cls._find_migration_path(current, target_version)
        if path is None:
            raise ValueError(
                f"No migration path from {current} to {target_version}. "
                f"Available migrations: {list(cls._migrations.keys())}"
            )

        for from_v, to_v in path:
            migration_fn = cls._migrations[(from_v, to_v)]
            data = migration_fn(data)
            data["schema_version"] = to_v

        return data

    @classmethod
    def _find_migration_path(
        cls, start: str, end: str
    ) -> List[Tuple[str, str]] | None:
        """BFS поиск minimal migration path. Returns list of (from, to) tuples or None."""
        from collections import deque

        if start == end:
            return []

        # BFS на migration graph
        queue = deque([(start, [])])
        visited = {start}

        while queue:
            current, path = queue.popleft()
            for (from_v, to_v) in cls._migrations.keys():
                if from_v == current and to_v not in visited:
                    new_path = path + [(from_v, to_v)]
                    if to_v == end:
                        return new_path
                    visited.add(to_v)
                    queue.append((to_v, new_path))

        return None  # No path found


# Registered migrations:

@SchemaRegistry.register("1.0", "2.0")
def migrate_v1_to_v2(data: dict) -> dict:
    """v1.0 -> v2.0: Robyn-style normalization (Econometrica 2026-04-25)."""
    # Existing migration from Econometrica
    data.setdefault("intercept_mean", None)
    data.setdefault("control_betas_mean", None)
    if "media_stds" in data:
        del data["media_stds"]  # replaced by spend/mean normalization
    return data

@SchemaRegistry.register("2.0", "3.0")
def migrate_v2_to_v3(data: dict) -> dict:
    """v2.0 -> v3.0: add Launch fields с defaults (additive)."""
    data.setdefault("proxy_brand_metadata", None)
    data.setdefault("recipient_anchors", None)
    data.setdefault("transfer_provenance", None)
    data.setdefault("forecast_horizons", None)
    data.setdefault("posterior_update_log", [])
    data.setdefault("consulting_hours_log", None)
    return data
```

**Test coverage:**
```python
def test_v1_to_v3_chains_through_v2():
    data_v1 = {"schema_version": "1.0", "media_stds": [1.0, 2.0]}
    data_v3 = SchemaRegistry.migrate(data_v1, target_version="3.0")
    assert data_v3["schema_version"] == "3.0"
    assert "media_stds" not in data_v3  # v1->v2 stripped
    assert data_v3["proxy_brand_metadata"] is None  # v2->v3 added
```

### 2.2 Validate UI (badges extension)

Existing badges layer показывает: data quality, model fit, divergences.

**Launch extension:** add proxy quality badges:
- Tier badge (Gold / Silver / Bronze / Insufficient)
- Similarity score
- Anchors completeness
- Transfer confidence
- Posterior update status (если applicable)

Same UI component, additional badges. No breaking changes.

### 2.3 Help system (launch-specific docs in shared format)

Existing help HTML structure (FTS5 search, categorized sections):
- Add Launch-specific sections: "Подбор прокси", "Recipient Anchors", "Transfer Validation", "Posterior Update"
- Same shared design tokens + visual language
- Cross-link с Econometrica help (для Optimize/Brand handoff scenarios)

---

## 3. Новое (Aurora Launch specific)

### 3.1 Engines (новые modules)

**`engines/launch_adapt.py`**:
```python
def extract_proxy_priors(model: TrainedModel) -> ProxyPriors:
    """Extract adstock + hill shapes + uncertainty bounds from proxy model."""
    ...

def apply_recipient_magnitudes(
    priors: ProxyPriors,
    anchors: RecipientAnchorsV1,
) -> RecipientPriors:
    """Rescale magnitudes (β, baseline) using recipient anchor data."""
    ...
```

**`engines/launch_validators.py`**:
- `ProxyDataValidator` - DSM + Mediascope sufficiency
- `RecipientAnchorsSemanticValidator` - cross-field domain rules
- `TransferConfidenceCalculator` - aggregate similarity + verdict

**`engines/single_proxy_transfer.py`** (audit A4 - separate engine):
- Direct prior assignment from one proxy
- Bayesian update с recipient data
- No hierarchical complications

**`engines/multi_proxy_hierarchical.py`** (audit A4):
- True hierarchical Bayesian (N≥2 proxies)
- Partial pooling weights
- Group-level hyperpriors

**`engines/launch_posterior_update.py`** (Sprint B5):
- ESS-based weight schedule
- Bayesian Model Averaging как промежуточный
- Re-fit с new recipient data

**`engines/launch_forecast.py`** (Sprint B4):
- Forecast generation 12/26/52 weeks
- Uncertainty decomposition (proxy + transfer + anchor + sampling)
- Hierarchical uncertainty propagation

**`engines/similarity_calculator.py`** + WASM module (Sprint B2):
- Similarity score computation (audit B4)
- Same code Python (backend) + Rust → WASM (UI real-time)

### 3.2 Frontend cabinets (новые Svelte components)

| Component | Sprint | Purpose |
|---|---|---|
| `ProxySelectionStep.svelte` | B2 | Single + multi-proxy selection, similarity radar |
| `RecipientAnchorsStep.svelte` | B3 | Form Pydantic-validated с real-time feedback |
| `TransferValidateStep.svelte` | B3 | Prior predictive + sensitivity + Tier badge |
| `PosteriorUpdateStep.svelte` | B5 | Re-fit с new data + weight reduction visualization |
| `LaunchDashboard.svelte` | B6 (premium) | "My Aurora" entry point с активными launches |
| `SimilarityRadarChart.svelte` | B2 | Live radar visualization |
| `ForecastConeChart.svelte` | B4 | 52-week expanding cone animation |
| `TierBadge.svelte` | B4 | Gold/Silver/Bronze visual badge |
| `ConsultingHoursWidget.svelte` | B1.5 | Hours tracker sidebar |
| `MethodologyCertificateGenerator.svelte` | B4 | PDF export |

### 3.3 Reports

**`aurora_pptx/launch_forecast/`** - 8-section template (Sprint B4):
1. Cover (Aurora seal, project, date, version)
2. Executive Summary (key metrics, tier badge, CFO framing)
3. Proxy Quality (similarity radar, dimensions, verdict)
4. Transfer Caveats (что переносится, uncertainty decomposition)
5. Forecast 12 weeks
6. Forecast 26 weeks
7. Forecast 52 weeks
8. Methodology + References + Model Card + Hash signature

**`aurora_html/launch_forecast/`** - HTML version (через shared adapter).

**`launch_certificate/`** - Methodology Certificate PDF generator.

**PDF generator decision (S006):**

PDF generation tools comparison:
| Tool | Pros | Cons | Bundle impact |
|---|---|---|---|
| **WeasyPrint** | HTML-first (reuses aurora_html), CSS styling | Heavy (Python-side, ~50MB deps incl GTK) | +50MB sidecar |
| **ReportLab** | Mature, programmatic | Verbose API, не HTML | +10MB |
| **Headless Chromium** | Full HTML/CSS/JS support | Very heavy (~200MB), slow startup | +200MB |
| **Rust printpdf / genpdf** | Native, fast, small | Limited features (no full HTML) | +5MB |

**Recommended:** **WeasyPrint** для Sprint B4 - reuse aurora_html templates + minimal new code. 50MB acceptable для premium product (Aurora Optimize installer уже 189MB).

**Alternative path:** Methodology Certificate genera через **Rust printpdf** для smallest footprint (если bundle size critical в Phase D).

### 3.4 Backend API (Aurora Launch routes)

См. DATA_REQUIREMENTS.md Section 7.2 - 12 endpoints под `/launch/v1/`.

### 3.5 Sample/Template data

**`fixtures/launch_templates/`**:
- FMCG Snacks Launch template (anchors + sample DSM + sample MS)
- OTC Pharma Launch template
- Premium Cosmetic Launch template
- Energy Drink Launch template
- Telecom Service Launch template

Used for:
- Onboarding new users (Sprint B6)
- Integration tests (Sprint B5)
- Sales demo (Sprint B6)

---

## 4. Coordination с Phase A Platform Foundation

### 4.1 Critical dependencies

Aurora Launch cannot start dev до:

| Dependency | Phase A status | Affects Launch sprint |
|---|---|---|
| Inference Core extracted в `aurora-platform-core` | required | All sprints |
| Data Studio MVP (DSM + MS importers) | required | B0.5, B1, B2 |
| Tauri shell template | required | B2+ (UI starts) |
| Workflow Engine | required | B2+ |
| `cross_app_license` framework | required | B6 ship |
| `schema_registry` pattern | required | B1 |

### 4.2 Phase A → Phase B handoff checklist

Before Aurora Launch Sprint B0.5 start:
- [ ] `aurora-platform-core` package published (versioned)
- [ ] Data Studio MVP с importer test corpus (см. Sprint B0.5)
- [ ] Tauri shell template repository accessible
- [ ] Workflow Engine API documented
- [ ] License framework supports cross-app keys
- [ ] Schema registry tested на Aurora Optimize backwards compat
- [ ] Phase A regression suite (Aurora Optimize) GREEN

### 4.3 Shared codebase ownership

- `aurora-platform-core` - shared, owned by Aurora platform team (= Маша + Антон в обозримом)
- Aurora Launch specific code в Aurora Launch repo / sub-folder
- Cross-cutting changes coordinate через ADRs (Architecture Decision Records)

---

## 5. Code Path Traces

### 5.1 Sprint B2-B3: typical Launch project flow

```
1. User opens Aurora Launch app (Tauri shell от Phase A template)
   → Window manager (shared)
   → Theme + L10n (shared)

2. New project → ProjectSetupStep (Launch-specific)
   → Project metadata via Pydantic (Launch schema extension)

3. ProxySelectionStep
   → Upload DSM data
     → DsmFormatDetector (shared from Data Studio)
     → DsmFormatAdapterV2024 (Phase A Data Studio)
     → ProxyDataValidator.validate() (Launch-specific)
   → Fill 6 similarity dimensions
     → similarity_calculator.compute() (Rust → WASM, Launch-specific)
   → Display SimilarityRadarChart (Launch-specific Svelte)

4. RecipientAnchorsStep
   → Form bound к Pydantic RecipientAnchorsV1 (Launch-specific)
   → Real-time validateAnchors() through API
   → SemanticValidator runs server-side (Launch-specific)

5. TransferValidateStep
   → launch_adapt.extract_proxy_priors() (Launch-specific)
   → launch_adapt.apply_recipient_magnitudes() (Launch-specific)
   → Prior predictive checks via shared modeler.posterior_predictive()
   → TierBadge display (Launch-specific)

6. Train
   → Routing: single_proxy_transfer OR multi_proxy_hierarchical (Launch-specific)
   → Internal: shared modeler.train() с adapted priors
   → Streaming MCMC traces к UI (audit B6)

7. Forecast
   → launch_forecast.generate(horizons=[12, 26, 52]) (Launch-specific)
   → Uncertainty decomposition (Launch-specific)
   → ForecastConeChart animation (Launch-specific)

8. Decompose / Optimize
   → shared decomposer.py + optimizer.py
   → Constraints from anchors

9. Report
   → launch_forecast PPTX template (Launch-specific) on shared aurora_pptx engine
   → Methodology Certificate PDF (Launch-specific)
   → Save .aurora bundle с launch fields (extended schema)
```

### 5.2 Posterior update flow (Sprint B5)

```
1. User uploads new recipient DSM data (после 4 нед launch)
2. launch_posterior_update.compute_ess(recipient_data) (Launch-specific)
3. compute_pooling_weight() based on ESS (Launch-specific)
4. Re-fit model: shared modeler.train() с reduced proxy weight
5. Update .aurora bundle с posterior_update_log entry (audit trail)
6. Generate updated forecast + new methodology certificate
```

---

## 6. Anti-patterns (что НЕ делать)

### 6.1 НЕ копировать engines в Aurora Launch

❌ `Aurora_Launch/engines/modeler.py` (copy)
✅ `Aurora_Launch` imports `aurora_platform_core.modeler`

Reason: drift, double maintenance, regression risk.

### 6.2 НЕ модифицировать shared engines per-product

❌ `if product == "launch": ... else: ...` в shared modeler.py
✅ Composition: shared engine + Launch-specific wrapper

Reason: maintainability, testability.

### 6.3 НЕ создавать parallel design system

❌ "Aurora Launch tokens.json" с разными цветами
✅ Use shared tokens.json + per-app accent color override

Reason: visual inconsistency Suite-wide = trust collapse.

### 6.4 НЕ ship Launch до Phase A complete

❌ "Параллельно с Phase A разрабатываем"
✅ Phase A → Aurora Optimize regression GREEN → Sprint B0.5 starts

Reason: merge ад, flaky tests, broken commitments.

---

## Связанные документы

- `../00_Overview/PRINCIPLES.md` - P9 как принцип
- `../00_Overview/ROADMAP.md` - Phase A зависимости
- Memory: `project_econometrica_target_architecture_v3.md` - target arch
- Memory: `project_econometrica_v1_2_0_foundation_2026_04_28.md` - schema additive pattern
