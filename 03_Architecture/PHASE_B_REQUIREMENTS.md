# Aurora Launch — Phase B Requirements

**Version:** v1.0 (Pass 1 — foundations + sprints B0.5/B1/B1.5/B2)
**Date:** 2026-05-08
**Author:** Маша Маленькая (Claude Opus 4.7)
**Status:** Draft, in progress (Pass 2 — sprints B3-B6 + audit)
**Plan reference:** `Desktop/AURORA_LAUNCH_PHASE_B_PLAN_v1.1.md`
**Phase A handoff:** assumes `aurora-platform-core` v0.1.0 (Weeks 1-3 shipped) + v0.2.0 (Weeks 4-7 in progress)

---

## §0 Executive Summary

### 0.1 What this is

Этот документ — **definitive implementation contract** для всех 7 sprint'ов Phase B Aurora Launch (B0.5 / B1 / B1.5 / B2 / B3 / B4 / B5 / B6). Когда Phase A platform foundation ship'нется, implementer (вероятно Антон + я + Phase B contractor) читает этот документ и начинает работать без debate'ов «что именно delivers B2?».

Spec foundation'но опирается на:
- 10 принципов в `00_Overview/PRINCIPLES.md` (P1-P10)
- 14 ADRs в `03_Architecture/decisions/`
- Closed Q&A sessions S001-S010 (концепт finalized 2026-05-04)
- Audited Phase A spec v0.2 (`aurora-platform-core/.../PHASE_A_REQUIREMENTS.md`) — 8 components × frozen contracts
- Restored D002 (`03_Architecture/PROXY_INTAKE_PROTOCOL.md`) — отказ от donor library, ad-hoc proxy intake authoritative

### 0.2 Audience

**Primary:**
- Phase B implementer (Антон + я для math/UI, или Phase B contractor если Антон занят с Эконометрика customer success)
- QA / pilot test lead (Sprint B6)

**Secondary:**
- Маша небесная (cross-machine coordination + sales materials reflecting spec)
- Phase A team (verify Aurora Launch dependencies remain satisfiable)
- External auditor (если Phase B+ потребует security review of WASM verifier, signing service, etc.)

### 0.3 Sprint timeline (revised post-D002)

**Total Phase B duration:** 8-10 недель calendar после Phase A complete.

| Sprint | Calendar weeks | LOC est | Owner | Critical path |
|---|---|---|---|---|
| B0.5 | 1 (5 days) | ~1500 LOC code + 600 tests | Антон+я | YES |
| B1 | 1 (5 days) | ~2000 LOC + 1200 tests | Антон+я | YES |
| B1.5 | 3 days (parallel B1) | ~600 LOC + 300 tests | я | NO (parallel) |
| B2 | 1.5 (7-8 days) | ~3000 LOC (1800 frontend + 1200 backend + WASM) | Антон+я | YES |
| B3 | 2 (10 days) | ~2500 LOC + 1500 tests | Антон+я | YES |
| B4 | 1 (5 days) | ~2200 LOC + 800 tests | Антон+я | YES |
| B5 | 1 (5 days) | ~1500 LOC + 1000 tests | Антон+я | YES |
| B6 | 1 (5 days) | ~1000 LOC + 500 tests + pilot validation | Антон+я+pilot clients | YES |

Sequential B0.5 → B1 → B2 → B3 → B4 → B5 → B6, B1.5 parallel B1.

### 0.4 Success criteria summary

Phase B ships v1.4.0 alpha-tag когда:

1. All 7 sprints meet их DoD (defined per sprint section)
2. Pilot validation: 3 parallel pilots (Pharma/FMCG/Cosmetics) complete end-to-end Aurora Launch workflow с signed Methodology Certificate
3. Performance budgets met cross-tier (cold/warm/premium HW)
4. WCAG AA compliance audit passes with zero serious issues
5. WASM verifier external security review passes (no privacy/integrity findings)
6. North Star metrics measurable per §6.5

**v1.4.0 GA** (separate gate): first paid customer conversion после 12-week pilot validation window.

### 0.5 Plan v1.1 fixes inherited

Этот spec applies 12 fixes from plan v1.1 (post-audit 2026-05-08):

- **B1** Reproducibility CLI tool ships in B0.5 + integrated B4 Cert recipe
- **B2** Single canonical Methodology Certificate format (universal across tiers)
- **B3** i18n infrastructure from B2 (not deferred Phase B+)
- **H1** PDF tech stack — B0.5 spike (Tauri webview / Typst / ReportLab)
- **H2** Dual-signature scheme (local Aurora install + Aurora-organization Vercel Edge)
- **H3** 3 verifier formats (web / standalone HTML / CLI)
- **H4** 3-tier onboarding (10min pre-prepared example + 20min real submission + async completion)
- **H5** Synthetic templates only (no real anonymized customer data)
- **H6** Simple text input в B2 (defer autocomplete + AI suggestion)
- **H7** Two-pass incremental delivery (Pass 1 commit before Pass 2 starts)
- **H8** «Update Estimate» rename (closed-form predictions only)
- **H9** Single canonical report template + 3 framing presets (not 24 sub-templates)

---

## §1 Cross-cutting Principles

7 принципов next-gen elevation, применяемых сквозно во всех 7 sprint'ах. Каждое решение должно явно ссылаться на CP-N в design rationale.

### CP-1 Trust Stack

**Принцип:** каждый artifact signed, каждый result reproducible, каждая metric с uncertainty.

**Realization:**
- Каждый `.aurora` bundle имеет SHA-256 manifest hash + JCS RFC 8785 canonical hash + Ed25519 dual signature (local + Aurora) + composite signing payload (manifest_sha256 || reproducibility_token, audit R8 closure)
- Каждая Methodology Certificate содержит reproducibility recipe (Aurora Launch version + bundle hash + `aurora-launch-reproduce <bundle> <expected_hash>` CLI command)
- Каждая числовая метрика в reports сопровождается uncertainty (CI / std / posterior interval / N samples)
- Hash chain — Cert hash matches bundle's manifest hash (verifier checks both)

**Per-sprint applications:**
- B0.5: synthetic corpus has stable seed → deterministic hash. `aurora-launch-reproduce` CLI scaffolded.
- B1: schema registry with hash chain validation, BFS migration determinism + commutativity tests
- B2: similarity score с confidence (`0.72 ± 0.05 based on 6 dimensions, 2 high-uncertainty`)
- B3: prior predictive checks visualize что модель «expects» до fit
- B4: Methodology Certificate centerpiece deliverable, dual-sig scheme
- B5: posterior update event audit trail с before/after model hashes (audit-fixed)
- B6: end-to-end reproducibility test on 1+ pilot bundle

### CP-2 Performance as Feature

**Принцип:** explicit p50/p95/p99 budgets per UI interaction, enforced в CI.

**Realization:**
- Не только train ≤30s, но и proxy form save ≤200ms p95, similarity radar update ≤16ms (60fps p99.9), sensitivity slider drag ≤16ms p99.9
- Animation timings calibrated (280ms ease-in-out — premium pacing, не дефолтные 200/400ms)
- p50 (typical) для customer experience baseline
- p95 (acceptable) для CI gate
- p99 (rare worst-case) для tracking jank
- p99.9 для animation frames (1-in-1000 = visible glitch)

**Per-sprint applications:**
- B0.5: synthetic corpus generation `<30s` per project — perf benchmark in B0.5 includes
- B2: WASM module ≤200KB gzipped, calc latency ≤16ms p99
- B3: prior predictive 50 samples ≤2s p95
- B4: PPTX gen ≤30s p95, PDF Cert ≤10s p95, XLSX ≤15s p95
- B5: Update Estimate ≤2s p95, full update ≤45s p95
- B6: cold start ≤4s p95 premium HW, ≤8s cold HW

Detailed budgets table в §3.

### CP-3 Educational by Design

**Принцип:** workflow учит методологии, customer выходит more informed чем зашёл.

**Realization:**
- Каждый step имеет contextual help (1-2 sentence «why this matters», не documentation dump)
- Glossary встроен — hover на term показывает definition + link
- Explainable verdicts (B2): «Medium because pricing tier mismatch (-0.3) + lifecycle stage difference (-0.2)»
- Per-channel transfer caveat heatmap (B3): customer видит per-channel transfer strength
- Templates = synthetic case studies (B6) — full methodology trail visible

**Anti-pattern detection (CP-3 + CP-6):** flags «leader as proxy for challenger» с failure mode explanation.

### CP-4 Privacy by Architecture

**Принцип:** local-first не feature, а foundation. Privacy не opt-in option.

**Realization:**
- Все business data live on customer machine
- Telemetry payload — только runtime metrics (latency, error counts, feature usage). Zero business identifiers.
- Verifier WASM — sandbox client-side, no network calls во time verification (verifier code published reproducible build для external audit)
- Anonymization protocol invariant — synchronized random factor R, brand→code, period shift (per `PROXY_INTAKE_PROTOCOL.md` Шаг 3)

**Privacy architecture diagram (per spec §1.x or appendix):**
- Tauri app ↔ local sidecar (loopback only)
- Tauri app ↔ aurora-platform staging/prod (license check + telemetry only, opt-in)
- Tauri app ↔ Vercel Edge (signing service ONLY at sign time, payload = hashes not data)
- WASM verifier ↔ user's browser (sandbox, no network)
- Methodology Certificate emails / shares — customer's choice, не automated

### CP-5 Premium Pacing

**Принцип:** каждый transition intentional, no abrupt UI jumps.

**Realization:**
- Loading states не spinner — progressive disclosure (training shows convergence trace, parameter posterior emerging)
- State transitions имеют 280ms ease-in-out (calibrated, не default)
- Empty states имеют preview content
- Error states имеют recovery action visible (CP-6 integration)

### CP-6 Failure as First-Class

**Принцип:** Insufficient verdict БЛОКИРУЕТ forecast generation. Refuse to deceive. Failure modes have UX. Escalation paths visible.

**Realization:**
- Insufficient (S<0.50) — hard block, не warning
- Каждый failure mode имеет UX с recovery options (3 buttons typical)
- Escalation contact visible — «can't find proxy» → «Schedule consulting call с Антоном» button
- Anti-pattern detector flags problems before they cause failures

**Failure modes catalog (per workflow step from PROXY_INTAKE_PROTOCOL):**
- Step 1 Discovery: customer can't name proxy → suggest 6-dimension framework, schedule expert call
- Step 2 Verification: no DSM data → return to step 1, alternative proxy
- Step 3 Anonymization: customer privacy concern → enhanced anonymization options + legal review
- Step 4 Data ingestion: format adapter mismatch → custom adapter request, 2-week ETA
- Step 5 Trust 3 training: convergence failure → smaller model variant or different proxy
- Step 6 Transfer: insufficient anchors → gather more anchors (workshop), or accept Insufficient
- Step 7 Methodology Cert: signing service down → local signature only, queue Aurora signature

### CP-7 Reproducibility Ceremony

**Принцип:** Methodology Certificate = signed claim, not paperwork. Это artifact что делает Aurora «auditable software», не «consulting deliverable».

**Realization:**
- Single canonical format (BLOCKER B2 fix) — universal across all tiers
- Dual-signature (BLOCKER H2 fix) — local + Aurora
- 3 verifier formats (HIGH H3 fix) — web + standalone HTML + CLI
- Reproducibility recipe = `aurora-launch-reproduce <bundle> <expected_hash>` exit 0 если match (BLOCKER B1 fix)
- Recipe runs headless, не requires Tauri install для verification

**Cert content tiers (progressive disclosure, не tier-based product gating):**
1. Plain language summary (1 paragraph) — visible default
2. Methodology overview (1 page) — expandable
3. Mathematical detail (appendix) — hidden by default
4. Source links / DOIs (footer)

---

## §2 Phase A Handoff Matrix

Aurora Launch consumes Phase A platform components. Frozen contracts из `aurora-platform-core/.../PHASE_A_REQUIREMENTS.md`.

### 2.1 Contract dependencies

| Phase A | Component | Aurora Launch use cases | Frozen API surface | Risk if changes |
|---|---|---|---|---|
| C1 | `aurora_inference` | modeler.train, decomposer, optimizer, scenario, validator, persistence, awareness, conformal, causal, trust3_hierarchical, kpi_registry | Function signatures + Pydantic returns | HIGH — math foundation |
| C2 | `aurora_studio` | source adapters (DSM/Mediascope), AI parser stack Tier 1/2/3, bundle composer, anonymization protocol | `IngestProxy(spec)` + `ComposeBundle(...)` | HIGH — proxy intake foundation |
| C3 | `aurora_workflow` | YAML config-driven steps, FastAPI route gen, state persistence, callback bus | `RunWorkflow(yaml_config, project_dir, callbacks)` | MEDIUM — orchestration |
| C4 | `aurora_shell_template` | cookiecutter Tauri shell для Aurora Launch app | Project skeleton + IPC contracts | LOW — one-time init |
| C5 | `aurora_common` | Auth, License (cross_app_license), Updates, Telemetry, FeatureFlags | API per sub-module | MEDIUM — runtime infra |
| C6 | `aurora_schema_registry` | BFS migration, manifest hash (JCS), composite signing, additive-only invariants | `SchemaRegistry.migrate(v_from, v_to, bundle)` | HIGH — schema foundation |
| C7 | `aurora_verifier` | Vercel Edge signing service + Yandex.Cloud KMS + WASM verifier core | `Sign(payload) -> ed25519_sig` + `Verify(sig, payload, pubkey) -> bool` | HIGH — trust stack |
| C8 | `aurora_reporting` | aurora_html / aurora_pptx / Rust XLSX writer / narrative_adapter / charts / pdf_writer (NEW для Methodology Cert) | Per-format `RenderReport(spec, data) -> bytes` | MEDIUM — reports |

### 2.2 Contract version pinning

Aurora Launch `pyproject.toml`:
```toml
[tool.poetry.dependencies]
aurora-inference = "^0.1.0"
aurora-studio = "^0.1.0"
aurora-workflow = "^0.1.0"
aurora-common = "^0.1.0"
aurora-schema-registry = "^0.1.0"
aurora-verifier = "^0.1.0"
aurora-reporting = "^0.1.0"
```

Caret = MINOR + PATCH compatible. MAJOR version bump в Phase A → одно-pass Aurora Launch spec update + re-audit.

### 2.3 Phase A→B contract change protocol

Если Phase A component contract меняется mid-Phase B (e.g., `aurora_inference.modeler.train_model` signature changes):

1. Phase A team commits change на feature branch
2. Notification to Aurora Launch (INBOX_TO_MN) с migration path
3. Aurora Launch spec update (one-pass through affected sprint sections)
4. Re-audit cross-doc consistency
5. Aurora Launch dev branch merges Phase A change after spec update

Этот protocol prevents silent breakage. Frozen contracts versioned.

### 2.4 What Aurora Launch DOES NOT depend on (clean separation)

- Phase A C1 internals (модель weights, sampler config) — Aurora Launch использует только public API
- Phase A C2 ingestion implementation (HTTP server, sidecar) — Aurora Launch вызывает через workflow engine
- Phase A C7 KMS rotation procedure — Aurora Launch verifies signatures, не manages keys
- Phase A C8 PPTX/HTML/XLSX template internals — Aurora Launch ships own templates через aurora_reporting plugin slot

Это ensures Aurora Launch can pin Phase A version, не tied to Phase A internal refactors.

---

## §3 Performance Budgets Unified

Single source of truth для всех Phase B sprints. CI enforces p95 budgets.

### 3.1 Per-operation budgets (3 HW tiers × 4 percentiles)

**HW tiers (per `PERFORMANCE_BUDGETS.md`):**
- Cold: i3 4th gen / 8GB RAM / HDD (regional analyst laptop, 2017-2018 era)
- Warm: i5 8th gen / 16GB RAM / SSD (typical agency analyst, 2020-2023)
- Premium: i7 12th gen / 32GB RAM / NVMe SSD (Антон's box, premium customer)

| Operation | Tier | p50 | p95 | p99 | p99.9 (animations) |
|---|---|---|---|---|---|
| Cold start (Tauri load → main window) | Cold | 6s | 8s | 10s | — |
| | Warm | 4s | 6s | 8s | — |
| | Premium | 2.5s | 4s | 6s | — |
| Project save (anchors form) | All | 100ms | 200ms | 400ms | — |
| Similarity radar update (slider drag) | All | 8ms | 14ms | 16ms | 16ms |
| Proxy form save (validate + persist) | Warm | 150ms | 300ms | 600ms | — |
| Prior predictive 50 samples (B3) | Cold | 4s | 6s | 10s | — |
| | Warm | 1.5s | 2.5s | 4s | — |
| | Premium | 0.5s | 1s | 2s | — |
| Sensitivity slider drag (B3) | All | 8ms | 14ms | 16ms | 16ms |
| Train single proxy | Cold | 60s | 90s | 120s | — |
| | Warm | 25s | 45s | 60s | — |
| | Premium | 15s | 25s | 35s | — |
| Train multi-proxy N=3 | Cold | 180s | 240s | 360s | — |
| | Warm | 60s | 120s | 180s | — |
| | Premium | 35s | 60s | 90s | — |
| Report PPTX generation | Warm | 18s | 30s | 50s | — |
| PDF Methodology Cert | Warm | 6s | 10s | 18s | — |
| XLSX export | Warm | 8s | 15s | 25s | — |
| Posterior update full | Warm | 25s | 45s | 70s | — |
| Update Estimate (closed-form) | All | 0.5s | 2s | 4s | — |
| WASM verifier load | Web | 200ms | 500ms | 1s | — |

### 3.2 Budget enforcement

CI gates через `pytest-benchmark` (Python) + `cargo bench` (Rust WASM) + Playwright trace assertions (UI).

Regression alerts: ≥10% p95 increase from baseline → CI fails. Ratchet baseline quarterly, не lock forever.

### 3.3 Budget violation procedure

При perf miss в Phase B:
1. Classify: hot path (gates user flow) vs cold path (rare)
2. Hot path: блокирует sprint completion. Optimize или escalate scope reduction.
3. Cold path: tracking issue created, fix backlog'd Phase B+ unless trivial.

---

## §4 Pass 1 Sprints

### §4.1 Sprint B0.5 — BC Test Corpus & Format Adapters (1 неделя)

**Goal:** ad-hoc proxy intake validation pipeline tested на synthetic + format adapter foundation готова.

#### 4.1.1 Scope

**In scope:**
- Synthetic project generator CLI (`aurora corpus generate <category> <variant> <seed>`)
- 8+ synthetic .aurora projects (FMCG_food.snacks_savoury / FMCG_beverage.beverage_carbonated / OTC_pharma.OTC_cold_flu / Cosmetics.skincare_premium / Telecom.telecom_b2c_mobile / Banking.banking_retail / awareness-only / cross-category-edge-case)
- 3 format adapters (`DsmAdapterV2023`, `DsmAdapterV2024`, `DsmAdapterV2025`) + Mediascope AdEx V1/V2/V3 + TV Index V1
- Auto-detection logic (file signature matching → adapter selection)
- Plug-in `ProxyDataSource` abstract Pydantic-based contract (per-deal extensibility)
- BC test pytest fixture set (parametrized over corpus items)
- CI gate — schema changes без BC pass = blocked
- **`aurora-launch-reproduce` CLI scaffold** (BLOCKER B1) — headless reproducibility check tool, ships v0.1.0
- **PDF tech stack spike** (HIGH H1) — evaluate Tauri webview print API / Typst / ReportLab in 0.5 day, decision записывается в `decisions/ADR-006-pdf-rendering.md`

**Out of scope (Phase B+ или other sprint):**
- AI parser stack Tier 1/2/3 — это Phase A C2 deliverable, Aurora Launch использует через workflow
- Real client data corpus (anonymized .aurora) — собирается в B6 от pilot clients, не B0.5

#### 4.1.2 Customer Experience Journey

Customer sprint B0.5 не видит напрямую (developer foundation). Внутренний customer (Антон или я при testing):

1. Команда `aurora corpus generate fmcg_impulse high_seasonality --seed 42` создаёт synthetic .aurora project в `<output_dir>/fmcg_impulse_high_seasonality_42.aurora` за <30s
2. Проект имеет realistic structure (104 weeks weekly data, 6 channels, FMCG_food.snacks_savoury L3 taxonomy, premium tier, leader brand, national distribution, always-on media maturity, mature lifecycle)
3. Property: same seed → identical bundle hash (deterministic)
4. Команда `aurora-launch-reproduce <bundle> <expected_hash>` exits 0 если bundle hash matches expected, exit 1 otherwise

#### 4.1.3 Math Invariants

- **Synthetic data preserves stationarity** (no unit roots in generated time series)
- **Hill saturation shape conforms к realistic categorical bounds** (γ_c ∈ [0.5, 4.0], k_c × spend_max ∈ [0.5, 5.0])
- **Adstock decay reversibility test:** apply forward → apply reverse → compare to original within float precision
- **ROI ratios across channels preserved within bundle** (synchronized R factor invariant from PROXY_INTAKE_PROTOCOL applied identically)
- **Property test:** seed → synthetic project → bundle hash, deterministic across machines (within JCS canonical hash, not bit-exact pickle)

#### 4.1.4 Pydantic Schemas (B0.5)

```python
# engines/corpus_generator.py

class SyntheticProjectSpec(BaseModel):
    seed: int = Field(ge=0, lt=2**32)
    category_l3: Literal[
        "FMCG_food.snacks_savoury", "FMCG_food.snacks_sweet", "FMCG_food.dairy_yogurt",
        "FMCG_beverage.beverage_carbonated", "FMCG_beverage.beverage_juice",
        "OTC_pharma.OTC_cold_flu", "OTC_pharma.OTC_pain",
        "Cosmetics.skincare_premium", "Cosmetics.haircare_premium",
        "Telecom.telecom_b2c_mobile", "Banking.banking_retail",
    ]
    variant: Literal["baseline", "high_seasonality", "volatile", "low_data", "cross_category_edge"]
    n_weeks: int = Field(ge=104, le=312)
    n_channels: int = Field(ge=4, le=12)
    pricing_tier: Literal["ECONOMY", "MAINSTREAM", "PREMIUM", "LUXURY"] = "MAINSTREAM"
    brand_size: Literal["LEADER", "CHALLENGER", "NICHE"] = "CHALLENGER"
    distribution: Literal["NATIONAL", "REGIONAL", "NICHE"] = "NATIONAL"
    media_maturity: Literal["ALWAYS_ON", "PULSING", "PROMO_DRIVEN", "DORMANT"] = "ALWAYS_ON"
    lifecycle: Literal["NEW", "GROWING", "MATURE", "DECLINING"] = "MATURE"

class FormatAdapterContract(BaseModel):
    """Abstract contract для plug-in ProxyDataSource."""
    adapter_id: str  # e.g., "dsm_v2024"
    adapter_version: str
    schema_version: str  # data schema version (DSM uses year-based)
    sample_files_glob: list[str]  # для auto-detection
    canonical_record_mapping: dict[str, str]  # source columns → CanonicalRecord fields
    detected_signatures: list[str]  # text/binary signatures для disambiguation

class ProxyDataSource(Protocol):
    """Phase B+ extensibility point. Phase B ships built-in DSM/Mediascope adapters."""
    def detect(self, file_path: Path) -> bool: ...
    def parse(self, file_path: Path) -> list[CanonicalRecord]: ...
    def get_metadata(self) -> AdapterMetadata: ...
```

#### 4.1.5 Engine Function Signatures (B0.5)

```python
# engines/corpus_generator.py
def generate_synthetic_project(
    spec: SyntheticProjectSpec,
    output_dir: Path,
) -> Path  # returns path to .aurora bundle

def list_corpus_categories() -> list[str]  # для CLI help

# engines/format_adapters/registry.py
class AdapterRegistry:
    def register(self, adapter: ProxyDataSource) -> None: ...
    def detect(self, file_path: Path) -> Optional[ProxyDataSource]: ...
    def list_adapters(self) -> list[FormatAdapterContract]: ...

# tools/reproduce.py (CLI tool, B1 BLOCKER fix)
def reproduce_check(
    bundle_path: Path,
    expected_hash: str,
    aurora_launch_version: str,
    rtol: float = 1e-4,
) -> ReproduceResult  # exit code 0 = match, 1 = mismatch
```

#### 4.1.6 Acceptance Criteria

**AC0.5.1 — Synthetic generation deterministic.**
- GIVEN `SyntheticProjectSpec(seed=42, category_l3="FMCG_food.snacks_savoury", variant="baseline")`
- WHEN `generate_synthetic_project(spec)` invoked
- THEN output bundle path exists, manifest_sha256 matches across 3 invocations on same machine + 2 different machines (rtol bit-exact in JCS canonical, not pickle)

**AC0.5.2 — Format adapter auto-detection.**
- GIVEN sample DSM file `<test_data>/dsm_v2024_sample.xlsx`
- WHEN `AdapterRegistry.detect(file_path)` invoked
- THEN returns `DsmAdapterV2024` instance (not V2023, not V2025), verified via `adapter.adapter_id == "dsm_v2024"`

**AC0.5.3 — BC test parametrized.**
- GIVEN synthetic corpus 8+ projects in `<corpus_dir>/`
- WHEN pytest collects parametrized BC test
- THEN each corpus item runs identically through workflow steps (load → validate schema → render preview), no errors

**AC0.5.4 — `aurora-launch-reproduce` headless CLI.**
- GIVEN bundle path + expected hash
- WHEN `aurora-launch-reproduce <bundle> <expected_hash> --rtol=1e-4` invoked
- THEN exit code 0 if hash matches (within JCS), exit code 1 if mismatch, stderr контрастный diff

**AC0.5.5 — PDF tech stack decision recorded.**
- GIVEN B0.5 spike completed (~0.5 day)
- WHEN spike artifacts reviewed
- THEN `decisions/ADR-006-pdf-rendering.md` exists с decision (Tauri webview / Typst / ReportLab) + rationale + fallback path

**AC0.5.6 — Plug-in architecture extensibility.**
- GIVEN custom `MyDataSource(ProxyDataSource)` implementation в test file
- WHEN registered via `AdapterRegistry.register(MyDataSource())`
- THEN `AdapterRegistry.list_adapters()` includes custom + built-ins

**AC0.5.7 — CI gate enforces BC.**
- GIVEN PR introducing schema breaking change (e.g., remove field из ManifestV3)
- WHEN CI runs BC test suite
- THEN CI fails с clear error pointing to broken corpus item

**AC0.5.8 — Performance budget per generation.**
- GIVEN synthetic project generation
- WHEN measured on Warm HW
- THEN p95 ≤30s per project (measured via pytest-benchmark)

#### 4.1.7 Test Plan + DoD

**Unit tests (~40 tests):**
- corpus_generator: 8 categories × variant matrix, deterministic seed property, schema conformance
- format_adapters: detection accuracy (positive + negative), parsing correctness, schema mapping
- reproduce CLI: hash match / mismatch / file not found / version skew

**Integration tests (~15 tests):**
- End-to-end corpus item → workflow load → validate → preview
- Adapter registry discovery + plug-in registration

**Property-based tests (~10 tests):**
- Synthetic seed determinism across machines
- Adstock decay reversibility
- ROI ratio invariance under synchronized R

**Performance tests:**
- Generation ≤30s p95 Warm
- BC test suite ≤2min total (parallel)

**DoD checklist:**
- [ ] All 65 tests pass on Windows + Linux
- [ ] 8+ synthetic projects committed to `tests/fixtures/synthetic_corpus/`
- [ ] Format adapter registry has 3 DSM + 3 Mediascope AdEx + 1 TV Index = 7 built-in adapters
- [ ] `aurora-launch-reproduce` CLI documented in README + man page
- [ ] PDF spike ADR-006 committed
- [ ] CI BC gate active

#### 4.1.8 Open Questions (B0.5)

- **OQ-B0.5-1:** Synthetic data generation engine — reuse Aurora Эконометрика's `simulator.py` или fresh impl? **Recommend reuse** для consistency.
- **OQ-B0.5-2:** PDF tech stack — Tauri webview print API capabilities (CSS @page rules, headers/footers, fonts)? **Decide в spike day 1.**
- **OQ-B0.5-3:** Reproduce CLI distribution — bundled с Aurora Launch installer или separate download? **Recommend bundled** (~5MB Python + dependencies via PyOxidizer).

#### 4.1.9 Dependencies

- **Phase A:** C2 `aurora_studio.adapters.base.CanonicalRecord` (used in adapter outputs), C6 `aurora_schema_registry.SchemaRegistry` (manifest hash)
- **Internal:** none (B0.5 is foundation sprint)

---

### §4.2 Sprint B1 — Pickle Schema Extension + Schema Registry (1 неделя)

**Goal:** Aurora Launch–specific schema fields ship'нуты в `.aurora` v3.0 + migration path safe.

#### 4.2.1 Scope

**In scope:**
- `engines/schema_registry.py` extension — register Aurora Launch fields (proxy_brand_metadata, transfer_provenance, recipient_anchors, forecast_horizons, methodology_certificate_ref)
- Pydantic v2 models для всех Launch schemas (BaseModel + JSON Schema export)
- BFS migration v2 (Эконометрика legacy) → v3 (Launch-extended) — additive only
- Composite signing payload `manifest_sha256 || reproducibility_token` (R8 closure, audit S2.7 fix)
- KPI registry дополнение для launch-specific (sales-only, awareness Phase B+)
- BC tests against B0.5 corpus PASS
- `aurora schema diff v2 v3` CLI tool (developer ergonomics, not customer-facing)
- TypeScript interface auto-generation (для Svelte 5 components в B2)

**Out of scope:**
- Full Эконометрика → Launch migration UX (B6 deliverable)
- Schema for posterior update event log (B5 schema)
- Schema fuzzing tool (Phase B+)

#### 4.2.2 Customer Experience Journey

Customer не видит B1 directly, но experiences результат:

1. Existing Эконометрика customer (Materia Medica) opens v2 project в Aurora Launch
2. Sees migration prompt: «This project will be upgraded to v3 schema. Backup created at `<path>.aurora.bak`. Continue?»
3. Migration completes <5s
4. Project opens с new fields populated as defaults (proxy_brand_metadata=null until customer selects proxy in B2)
5. Customer не теряет data, Эконометрика workflow продолжает working seamlessly

#### 4.2.3 Math Invariants

- **Migration BFS-optimal** — гарантия no information loss across version chain (formal property test: round-trip v2→v3→v2 preserves all v2 fields)
- **Hash stability** — same project content (after migration) → same manifest_sha256 across machines (JCS canonical, not pickle)
- **Additive-only** — v3 strictly extends v2, no field removal allowed (CI invariant test)
- **Composite signing closure** — file tampering detected (R8 закрыт): swap parquet + recompute manifest_sha256 still fails verification because reproducibility_token не recomputable без original

#### 4.2.4 Pydantic Schemas (B1)

```python
# Extended ManifestV3 для Aurora Launch
class ManifestV3Launch(ManifestV3):  # ManifestV3 import from aurora_schema_registry (Phase A C6)
    # Aurora Launch–specific fields (additive)
    proxy_brand_metadata: Optional[ProxyBrandMetadata] = None
    transfer_provenance: Optional[TransferProvenance] = None
    recipient_anchors: Optional[RecipientAnchors] = None
    forecast_horizons: Optional[ForecastHorizons] = None
    methodology_certificate_ref: Optional[MethodologyCertificateRef] = None

class ProxyBrandMetadata(BaseModel):
    proxy_code: str = Field(pattern=r"^[A-Z][A-Z0-9_-]{2,32}$")  # e.g., "COFFEE-2026-Q2", "KAG-2024"
    similarity_dimensions: SimilarityDimensionScores
    similarity_score: float = Field(ge=0.0, le=1.0)
    verdict: Literal["High", "Medium", "Low", "Insufficient"]
    inflation_factor: float = Field(ge=1.0, le=3.0)
    multi_proxy_config: Optional[MultiProxyConfig] = None
    intake_workflow_version: str = "1.0"  # PROXY_INTAKE_PROTOCOL.md version
    anonymization_applied: AnonymizationDetails

class AnonymizationDetails(BaseModel):
    synchronized_random_factor: float  # the R factor (per Шаг 3)
    period_shift_months: int = Field(ge=-24, le=24)
    brand_name_replaced: bool = True
    manufacturer_removed: bool = True

class SimilarityDimensionScores(BaseModel):
    category_l1_match: float = Field(ge=0.0, le=1.0)
    category_l2_match: float = Field(ge=0.0, le=1.0)
    category_l3_match: float = Field(ge=0.0, le=1.0)
    pricing_tier_match: float = Field(ge=0.0, le=1.0)
    brand_size_match: float = Field(ge=0.0, le=1.0)
    distribution_match: float = Field(ge=0.0, le=1.0)
    media_maturity_match: float = Field(ge=0.0, le=1.0)
    lifecycle_match: float = Field(ge=0.0, le=1.0)
    weights_used: dict[str, float]  # which weight profile applied (per category)

class TransferProvenance(BaseModel):
    transferred_params: list[Literal["adstock_decay", "hill_gamma", "hill_k", "seasonality", "trend"]]
    not_transferred: list[str]  # explicit list для audit trail
    proxy_model_hash: str
    recipient_model_hash: str
    adaptation_rules_version: str  # ADAPTATION_RULES.md spec version
    cross_category_distance: int = Field(ge=0, le=3)  # 0=L3, 1=L2, 2=L1, 3=adjacent_L1
    inflation_factor_applied: float

class RecipientAnchors(BaseModel):
    market_size_rub: PositiveFloat
    market_size_uncertainty_pct: float = Field(ge=0.0, le=50.0, default=10.0)
    planned_share_pct: float = Field(ge=0.1, le=50.0)
    distribution_velocity_curve: list[DistributionPoint]
    pricing_index_vs_market: float = Field(ge=0.5, le=3.0, default=1.0)
    creative_quality_index: float = Field(ge=0.5, le=2.0, default=1.0)
    competitive_response: Literal["mild", "moderate", "aggressive"] = "moderate"
    pause_duration_months: int = Field(ge=0, le=120, default=0)  # for paused brand mode (was ge=12 — audit-fixed)
    category_trend_input: Literal["growing", "stable", "declining"] = "stable"

class DistributionPoint(BaseModel):
    week_index: int = Field(ge=0)
    distribution_pct: float = Field(ge=0.0, le=100.0)

class ForecastHorizons(BaseModel):
    horizons_weeks: list[Literal[12, 26, 52]]
    forecasts: dict[int, ForecastResult]  # keyed by horizon
    conformal_calibration_n: int  # for CI tightness conditional на ≥50 (audit H4)

class ForecastResult(BaseModel):
    weekly_predictions: list[float]
    weekly_lower_ci: list[float]
    weekly_upper_ci: list[float]
    coverage_target: float = 0.95
    conformal_method: Literal["split", "weighted_jackknife"] = "split"

class MethodologyCertificateRef(BaseModel):
    cert_id: UUID
    cert_hash_sha256: str
    cert_version: str
    signed_local: bool
    signed_aurora: bool  # may be False if offline at sign time, backfill on next online
    signing_service_url: str = "https://sign.auroraai.pro/v1/launch"
    verifier_urls: dict[Literal["web", "html", "cli"], str]
```

**TypeScript interface generation:**
```bash
aurora schema export-ts --version v3 --output ../frontend/src/types/aurora-launch-schema.ts
```

#### 4.2.5 Engine Function Signatures (B1)

```python
# engines/schema_registry_launch.py
def register_launch_schemas() -> None:
    """Called at app startup. Registers Aurora Launch–specific Pydantic models with Phase A C6 registry."""

def migrate_v2_to_v3(bundle_v2: AuroraBundle) -> AuroraBundle:
    """BFS migration. Preserves all v2 fields, adds v3 fields с None defaults."""

def validate_launch_schema(bundle: AuroraBundle) -> ValidationResult:
    """Comprehensive Pydantic + cross-field semantic validation."""

# tools/schema_diff.py
def diff_schemas(v_from: str, v_to: str) -> SchemaDiffReport:
    """Developer tool. Outputs human-readable diff."""

# tools/composite_signing.py (R8 closure)
def compute_reproducibility_token(bundle: AuroraBundle) -> str:
    """Hash of (manifest_sha256 || all parquet hashes || all pickle hashes). Cannot be forged без original files."""

def verify_composite_signature(bundle: AuroraBundle, signature: bytes, pubkey: bytes) -> bool:
    """Verifies signature over (manifest_sha256 || reproducibility_token)."""
```

#### 4.2.6 Acceptance Criteria

**AC1.1 — v2→v3 migration round-trip preserves data.**
- GIVEN existing v2 .aurora bundle from Эконометрика test fixture
- WHEN `migrate_v2_to_v3(bundle_v2)` invoked
- THEN result.schema_version == "3.0", all v2 fields preserved, v3-new fields present с None/default values

**AC1.2 — Composite signing closes R8 file tampering.**
- GIVEN signed bundle, attacker swaps parquet file + recomputes integrity files + recomputes manifest_sha256
- WHEN `verify_composite_signature(...)` called
- THEN returns False (because reproducibility_token mismatch — attacker cannot recompute it without original parquet)

**AC1.3 — Hash stability across machines.**
- GIVEN identical bundle content (synthetic project from B0.5)
- WHEN manifest_sha256 computed on Windows + Linux
- THEN identical hashes (JCS canonical RFC 8785)

**AC1.4 — Additive-only invariant enforced.**
- GIVEN PR removing field из ManifestV3Launch
- WHEN CI runs additive-only test
- THEN CI fails с clear error about removed field

**AC1.5 — TypeScript interfaces auto-generated.**
- GIVEN `aurora schema export-ts --version v3`
- WHEN command run
- THEN `frontend/src/types/aurora-launch-schema.ts` updated, valid TypeScript, имеет all Pydantic field types correctly mapped

**AC1.6 — Pydantic validators catch invalid data.**
- GIVEN RecipientAnchors с `market_size_rub=-100`
- WHEN validation invoked
- THEN raises ValidationError pointing to invalid field

**AC1.7 — Schema registry composability.**
- GIVEN Phase A C6 SchemaRegistry + Aurora Launch register_launch_schemas()
- WHEN `SchemaRegistry.list_versions()` called
- THEN includes both Эконометрика legacy + Launch v3.0 entries

**AC1.8 — KPI registry extension.**
- GIVEN Aurora Launch app launches
- WHEN customer creates new launch project
- THEN KPI options include "sales_revenue_rub" (default), "units_sold" (alt), with awareness deferred to B+

**AC1.9 — BFS migration with v1 → v3 chain.**
- GIVEN legacy v1 .aurora bundle (pre-v2 Эконометрика)
- WHEN `SchemaRegistry.migrate(from_v=1, to_v=3, bundle)` invoked
- THEN BFS path v1→v2→v3 traversed, all intermediate transformations applied, final bundle valid v3

**AC1.10 — Bundle backup rotation.**
- GIVEN customer migrates 5 projects in a row (creating 5 .aurora.bak files in same project dir)
- WHEN customer migrates 6th project
- THEN oldest .aurora.bak deleted (rolling 4 backups invariant)

#### 4.2.7 Test Plan + DoD

**Unit tests (~50):**
- Schema field validation (Pydantic), 30+ field-level tests
- BFS migration paths (v1→v2→v3, v2→v3, v3→v3 no-op)
- Composite signing payload generation
- TypeScript export correctness

**Property-based tests (~15):**
- Migration round-trip (v2→v3→v2 preserves data — though we don't actually downgrade, the test validates information preservation)
- BFS commutativity in graph paths (если multiple paths exist, results match)
- JCS hash stability across input ordering

**Integration tests (~10):**
- Real Эконометрика fixture (Кагоцел) v2 → v3 migration
- Schema registry composability с Phase A C6

**Performance tests:**
- Migration ≤5s p95 Warm (для 5MB-50MB bundles)

**DoD checklist:**
- [ ] 75 tests pass
- [ ] All v3 schemas have docstrings + JSON Schema export valid
- [ ] TypeScript types committed to frontend repo (cross-dep с Phase A frontend, coordinate)
- [ ] BFS migration documented в `docs/SCHEMA_MIGRATION.md`
- [ ] Composite signing R8 closure tested w/ attack scenario
- [ ] BC tests against B0.5 corpus PASS (post-migration corpus items still valid)

#### 4.2.8 Open Questions (B1)

- **OQ-B1-1:** Migration backup retention — confirmed 4 rolling per memory? Or configurable?
- **OQ-B1-2:** Cross-app license enforcement — где validate (Phase B B1 schema layer vs Phase A C5 license module)? **Recommend C5** для consistency.
- **OQ-B1-3:** Schema diff output format — Markdown for humans + JSON for tooling? Unified? **Recommend dual output.**

#### 4.2.9 Dependencies

- **Phase A:** C6 `aurora_schema_registry` (BFS engine, manifest hash, composite signing infrastructure)
- **Internal:** B0.5 (BC tests against corpus)

---

### §4.3 Sprint B1.5 — Customer Success Lite (3 дня parallel B1)

**Goal:** consulting hours tracker от старта Phase B + cross-device sync foundation.

#### 4.3.1 Scope

**In scope:**
- SQLite local table `consulting_log` (per-machine cache + offline buffer)
- Sync to aurora-platform staging/prod (Phase A C5 license module integration)
- Auto-log session events (proxy review, posterior update, methodology question, training run)
- Hours tracker UI sidebar widget
- Predictive depletion calculation
- CSV export для billing
- Quarterly customer-facing usage PDF auto-generated (premium touch)
- User preferences table (audience framing default, chart style, etc. — UX finding U6)

**Out of scope:**
- Real-time customer-facing portal (Phase C+)
- Session video recording (Phase C+)
- Hour budget enforcement / blocking (consulting is advisory, не hard limit)

#### 4.3.2 Customer Experience Journey

Customer (Materia Medica analyst, 6 months into year):
1. Opens Aurora Launch, sidebar shows badge: «Consulting hours: 22h / 30h used»
2. Hover shows breakdown: «Proxy review: 4h, Anchors workshop: 6h, Posterior updates: 3h, Methodology questions: 9h»
3. Predictive: «At current rate, 38h by year-end. Consider Pro tier upgrade.»
4. Customer feels Aurora honest about value delivery

Quarterly: Aurora auto-emails PDF usage summary к customer's success contact:
> «Q3 2026 Aurora Launch usage summary for Materia Medica:
> - 8 launches initiated (6 completed, 2 in progress)
> - 18h consulting used (avg 3h/launch)
> - 4 posterior updates (3 partial pooling, 1 BMA fallback)
> - Average forecast accuracy at 12-week validation: ±11% (within Medium tier expectation)
> - Recommended actions: ...»

#### 4.3.3 Math Invariants

- Hours tracking deterministic (event timestamps + duration)
- Cross-device sync conflict resolution: last-write-wins per event (events are append-only, conflicts rare)
- Predictive depletion: linear extrapolation от last 4 weeks usage rate (não rocket science, no false precision)

#### 4.3.4 Pydantic Schemas (B1.5)

```python
class ConsultingLogEntry(BaseModel):
    event_id: UUID
    customer_id: UUID  # from C5 license
    machine_id: UUID  # для cross-device dedup
    timestamp_start: datetime
    duration_minutes: int = Field(ge=1)
    event_type: Literal[
        "proxy_review", "anchors_workshop", "posterior_update",
        "methodology_question", "training_run_supervised", "report_review",
        "pilot_kickoff", "quarterly_review", "custom"
    ]
    project_id: Optional[UUID] = None  # linked .aurora project if applicable
    notes: Optional[str] = Field(default=None, max_length=2000)
    consulting_hours_charged: Decimal = Field(ge=0)  # may be 0 для self-service events

class UsageSummary(BaseModel):
    period_start: datetime
    period_end: datetime
    total_hours_used: Decimal
    total_hours_allowed: Decimal  # from license tier
    breakdown_by_event_type: dict[str, Decimal]
    n_launches_initiated: int
    n_launches_completed: int
    n_posterior_updates: int
    avg_forecast_accuracy_12w: Optional[float] = None  # measured retroactively if data available

class UserPreferences(BaseModel):
    customer_id: UUID
    preferred_audience_framing: Literal["cfo", "cmo", "marketer", "balanced"] = "balanced"
    preferred_chart_style: Literal["minimal", "detailed", "premium"] = "premium"
    chart_color_palette: Literal["default", "high_contrast", "color_blind_safe"] = "default"
    notifications_enabled: bool = True
    quarterly_pdf_email: bool = True
    favorite_proxies: list[str] = Field(default_factory=list, max_length=10)
```

#### 4.3.5 Engine Function Signatures (B1.5)

```python
# engines/customer_success/tracker.py
def log_event(entry: ConsultingLogEntry) -> None:
    """Local SQLite + queue for sync."""

def sync_pending() -> SyncResult:
    """Flush local buffer к aurora-platform. Idempotent."""

def get_usage_summary(period_start: datetime, period_end: datetime) -> UsageSummary: ...

def predict_depletion(current_usage_rate_h_per_week: Decimal, hours_remaining: Decimal) -> int:
    """Returns ETA в days. Linear extrapolation."""

# engines/customer_success/quarterly_pdf.py
def generate_quarterly_summary_pdf(customer_id: UUID, quarter: str) -> bytes: ...

# engines/customer_success/preferences.py
def load_preferences(customer_id: UUID) -> UserPreferences: ...
def save_preferences(prefs: UserPreferences) -> None: ...
```

#### 4.3.6 Acceptance Criteria

**AC1.5.1 — Auto-log triggers on event.**
- GIVEN customer завершает proxy review session in Aurora Launch
- WHEN session ends (via UI «Done» button)
- THEN ConsultingLogEntry persisted в SQLite + queued для sync

**AC1.5.2 — Cross-device sync.**
- GIVEN customer uses Aurora Launch on Machine A (logs 2h), then Machine B
- WHEN Machine B opens Aurora Launch + syncs
- THEN sidebar shows total 22h (consolidated, not 20h)

**AC1.5.3 — Sidebar widget displays hours used.**
- GIVEN customer has consulting_log entries totaling 22h
- WHEN customer opens main app window
- THEN sidebar widget shows «22h / 30h used» с breakdown tooltip

**AC1.5.4 — Predictive depletion.**
- GIVEN customer averaging 3h/week, 12 weeks remaining в year, 8h consulting hours remaining
- WHEN customer hovers depletion indicator
- THEN tooltip: «At current rate, depletion in 18 days, ~32 days before year-end. Consider Pro tier.»

**AC1.5.5 — CSV export for billing.**
- GIVEN customer requests CSV export
- WHEN export triggered
- THEN file `consulting_<customer>_<period>.csv` produced with all columns (timestamp, event_type, duration, project_id, notes, hours_charged)

**AC1.5.6 — Quarterly PDF generation.**
- GIVEN end of quarter Q3 2026
- WHEN scheduled job runs (or manual trigger)
- THEN PDF generated, emailed to customer's success contact, archived locally

**AC1.5.7 — User preferences persist.**
- GIVEN customer changes preferred_audience_framing → "cfo"
- WHEN customer opens Aurora Launch on different machine
- THEN preference синhronized (after sync), CFO framing default

**AC1.5.8 — Idempotent sync.**
- GIVEN customer's network drops during sync mid-batch
- WHEN sync retries
- THEN no duplicate entries, all original entries persist (event_id deduplication)

#### 4.3.7 Test Plan + DoD

**Unit tests (~25):**
- Tracker logging, sync queueing, conflict resolution
- Predictive depletion math
- CSV export format correctness
- PDF generation snapshot tests

**Integration tests (~10):**
- Cross-device sync via aurora-platform staging
- Real session event auto-trigger

**DoD:**
- [ ] 35 tests pass
- [ ] Sidebar widget integrated with main app shell (Phase A C4 template)
- [ ] Quarterly PDF template approved by Антон
- [ ] Sync resilience tested (network drops, retry logic)
- [ ] Preferences UI integrated в Settings

#### 4.3.8 Open Questions (B1.5)

- **OQ-B1.5-1:** Auto-log triggers — какие events count toward consulting hours? (Likely: any event с consulting_hours_charged > 0, configurable per Антон's billing policy.)
- **OQ-B1.5-2:** CSV format — какой billing system Антон uses?
- **OQ-B1.5-3:** Quarterly PDF triggers — automatic email или customer opt-in?

#### 4.3.9 Dependencies

- **Phase A:** C5 license module (customer_id, hours_allowed, tier), C5 telemetry (event ingestion endpoint), C8 reporting (PDF generator base)
- **Internal:** parallel с B1 (no schema deps), uses ConsultingLogEntry stored locally + synced

---

### §4.4 Sprint B2 — Proxy Selection Cabinet UI + WASM Similarity (1.5 недели)

**Goal:** customer выбирает прокси-бренд + заполняет similarity dimensions + видит explainable verdict + multi-proxy expert mode functional.

#### 4.4.1 Scope

**In scope:**
- Svelte 5 component `ProxySelectionStep.svelte` — single proxy mode (default) + multi-proxy mode (expert toggle, 2-3 proxies)
- Similarity radar chart (D3.js или ECharts — decide spike) с real-time updates
- 6+2 dimension form (8 total: L1/L2/L3 + 5 other dimensions)
- WASM similarity calculator (Rust + wasm-bindgen, ≤200KB gzipped)
- Verdict display с **explainable rationale** (per-dimension contribution)
- Anti-pattern detector (e.g., «leader as proxy for challenger»)
- Insufficient verdict → forecast generation BLOCKED (CP-6 hard block)
- **Simple text input для proxy name** (HIGH H6 fix — no autocomplete, no AI)
- **i18n infrastructure** (BLOCKER B3 fix) — all strings via `$t()`, ru.json populated, en.json stub
- Pydantic backend validation (mirror WASM logic для server-side enforcement)
- Vitest + Pytest integration tests

**Out of scope (Phase C+ scaffolding hooks only):**
- AI-assisted proxy suggestion (feature flag `FEATURE_AI_PROXY_SUGGEST_ENABLED` defaults False — schema field `proxy_brand_metadata.ai_suggestion_metadata: Optional` ready)
- Brand autocomplete from DSM database (legal/operational issue per HIGH H6)
- Multi-proxy AI auto-discovery (Phase C+)

#### 4.4.2 Customer Experience Journey

Customer (CMO of new beverage brand «Birch Energy»):

1. Opens Aurora Launch project → reaches Proxy Selection step (workflow Step 4 per PROXY_INTAKE_PROTOCOL)
2. Sees prompt: «Какой существующий бренд вы считаете наиболее похожим на ваш запуск?»
3. Types «Lipton Iced Tea» в text input field
4. Selects category L3 from dropdown («FMCG_beverage.beverage_juice»)
5. Selects pricing tier from radio («PREMIUM»)
6. Selects brand size («CHALLENGER»), distribution («NATIONAL»), media maturity («ALWAYS_ON»), lifecycle («GROWING»)
7. Live similarity radar updates as customer fills fields (each field change → WASM call <16ms → radar redraw)
8. Verdict appears at bottom: «**Medium (0.72)**. Decent fit. Pricing tier match strong. Lifecycle stage shows uncertainty.»
9. Per-dimension breakdown expandable: «Category L3 1.0 (perfect), Pricing PREMIUM↔PREMIUM 1.0, Brand size CHALLENGER↔CHALLENGER 1.0, Distribution NATIONAL↔NATIONAL 1.0, Media maturity ALWAYS_ON↔ALWAYS_ON 1.0, Lifecycle GROWING↔MATURE 0.6. Weighted aggregate 0.72.»
10. If unhappy with verdict, customer clicks «+ Add second proxy» → multi-proxy mode → tabs appear, second proxy form, partial pooling weights configurable, combined verdict updates
11. Anti-pattern detector flags если applicable: «⚠ Detected: leader-as-proxy-for-challenger. Consider using a different proxy or adjusting positioning. [Learn more]»
12. If verdict is «Insufficient (S<0.50)», forecast generation step **disabled** с explanation: «Cannot proceed. Aurora refuses to generate forecast on Insufficient similarity to maintain methodology integrity. Options: (a) try different proxy, (b) add multi-proxy mode, (c) schedule consult с Антоном.»

#### 4.4.3 Math Invariants

- **Symmetry:** S(A, B) = S(B, A) для symmetric dimensions (categorical match не ordered)
- **Verdict thresholds enforced:** S≥0.85 High, 0.65-0.85 Medium, 0.50-0.65 Low, <0.50 Insufficient (per SIMILARITY_FRAMEWORK.md)
- **Multi-proxy combined:**
  - S_aggregate = sum(w_i × S_i) / sum(w_i)
  - inflation_multi_penalty = 1 + 0.05 × (N - 1)
  - effective_inflation = base_verdict_inflation × multi_penalty
- **Multi-proxy floor warnings:** individual S_i < 0.5 → flag, max(S) - min(S) > 0.3 → flag heterogeneity
- **Per-category weight profiles:** OTC_PHARMA emphasizes category (0.40), FMCG_IMPULSE emphasizes pricing (0.25) — per SIMILARITY_FRAMEWORK §4
- **Property test:** for any pair (A, B) с identical fields → S = 1.0; для disjoint categories → S < 0.5

#### 4.4.4 Pydantic Schemas (B2)

```python
class ProxyEntry(BaseModel):
    proxy_brand_name: str = Field(min_length=1, max_length=200)  # plaintext input от customer
    proxy_brand_code: str  # generated for anonymization
    category_l1: str
    category_l2: str
    category_l3: str
    pricing_tier: Literal["ECONOMY", "MAINSTREAM", "PREMIUM", "LUXURY"]
    brand_size: Literal["LEADER", "CHALLENGER", "NICHE"]
    distribution: Literal["NATIONAL", "REGIONAL", "NICHE"]
    media_maturity: Literal["ALWAYS_ON", "PULSING", "PROMO_DRIVEN", "DORMANT"]
    lifecycle: Literal["NEW", "GROWING", "MATURE", "DECLINING"]

class RecipientProfile(BaseModel):
    """Mirror structure to ProxyEntry but for recipient (the new brand)."""
    recipient_brand_name: str = Field(min_length=1, max_length=200)
    category_l1: str
    category_l2: str
    category_l3: str
    pricing_tier: Literal["ECONOMY", "MAINSTREAM", "PREMIUM", "LUXURY"]
    brand_size_target: Literal["LEADER", "CHALLENGER", "NICHE"]
    distribution_target: Literal["NATIONAL", "REGIONAL", "NICHE"]
    media_maturity_planned: Literal["ALWAYS_ON", "PULSING", "PROMO_DRIVEN", "DORMANT"]
    lifecycle_stage: Literal["NEW", "GROWING"]  # Aurora Launch only — new brand

class VerdictExplanation(BaseModel):
    dimension_id: str
    dimension_score: float
    weight_applied: float
    contribution: float  # = dimension_score × weight_applied
    rationale: str  # human-readable, e.g., "Category L3 perfect match"

class AntiPatternFlag(BaseModel):
    pattern_id: Literal[
        "leader_as_proxy_for_challenger",
        "premium_as_proxy_for_economy",
        "always_on_as_proxy_for_dormant",
        "cross_l1_with_low_seasonality_match",
    ]
    severity: Literal["warning", "blocking"]
    message: str  # i18n key
    learn_more_url: str

class ProxyVerdict(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    label: Literal["High", "Medium", "Low", "Insufficient"]
    inflation_factor: float = Field(ge=1.0)
    explanations: list[VerdictExplanation]  # per-dimension contributions
    anti_patterns_detected: list[AntiPatternFlag]
    block_forecast: bool  # True iff label == "Insufficient"
    confidence_uncertainty: float  # std error of score estimate

class MultiProxyConfig(BaseModel):
    proxies: list[ProxyEntry] = Field(min_length=2, max_length=3)
    pooling_weights: list[float] = Field(min_length=2, max_length=3)
    combined_score: float
    multi_penalty: float  # 1 + 0.05 × (N-1)
    effective_inflation: float
    floor_warnings: list[FloorWarning]

    @field_validator("pooling_weights")
    @classmethod
    def weights_sum_to_one(cls, v: list[float]) -> list[float]:
        if abs(sum(v) - 1.0) > 1e-6:
            raise ValueError(f"Pooling weights must sum to 1.0, got {sum(v)}")
        return v

class FloorWarning(BaseModel):
    warning_type: Literal["individual_below_0_5", "spread_above_0_3"]
    affected_proxy_codes: list[str]
    message: str
```

#### 4.4.5 Engine Function Signatures (B2)

**Rust (compiled to WASM):**
```rust
// crates/similarity_wasm/src/lib.rs

#[wasm_bindgen]
pub fn calculate_similarity(
    recipient_json: &str,
    proxy_json: &str,
    weights_json: &str,
) -> String  // returns SimilarityResult JSON

#[wasm_bindgen]
pub fn compute_verdict(
    score: f64,
    multi_penalty: f64,
    explanations_json: &str,
) -> String  // returns Verdict JSON

#[wasm_bindgen]
pub fn detect_anti_patterns(
    recipient_json: &str,
    proxy_json: &str,
    score: f64,
) -> String  // returns Vec<AntiPatternFlag> JSON
```

**Python (mirror logic для backend validation):**
```python
# engines/similarity_calculator.py
def calculate_similarity(
    recipient: RecipientProfile,
    proxy: ProxyEntry,
    weights: dict[str, float],
) -> SimilarityResult: ...

def compute_verdict(
    score: float,
    multi_penalty: float = 1.0,
    explanations: list[VerdictExplanation] = None,
) -> ProxyVerdict: ...

def detect_anti_patterns(
    recipient: RecipientProfile,
    proxy: ProxyEntry,
    score: float,
) -> list[AntiPatternFlag]: ...

def aggregate_multi_proxy(
    proxies: list[ProxyEntry],
    pooling_weights: list[float],
    recipient: RecipientProfile,
) -> MultiProxyConfig: ...

# engines/similarity_weights.py
def get_weights_for_category(category_l1: str, category_l2: str) -> dict[str, float]:
    """Returns weight profile per SIMILARITY_FRAMEWORK §4."""
```

#### 4.4.6 Acceptance Criteria

**AC2.1 — WASM bundle ≤200KB gzipped.**
- GIVEN production WASM build
- WHEN measured (gzip)
- THEN ≤200KB. (If >200KB, split into core ≤100KB + extended ≤100KB lazy-loaded.)

**AC2.2 — Similarity radar updates ≤16ms p99.**
- GIVEN customer drags pricing_tier dropdown
- WHEN value changes
- THEN WASM call returns + radar redrawn within 16ms p99 (60fps target)

**AC2.3 — Verdict explainability.**
- GIVEN proxy verdict «Medium (0.72)»
- WHEN customer expands explanation panel
- THEN displays per-dimension contributions с rationale в plain language

**AC2.4 — Anti-pattern detection.**
- GIVEN recipient is CHALLENGER, proxy is LEADER, all other dimensions match
- WHEN verdict computed
- THEN AntiPatternFlag «leader_as_proxy_for_challenger» appears с warning severity

**AC2.5 — Insufficient verdict blocks forecast.**
- GIVEN verdict label = «Insufficient» (S < 0.50)
- WHEN customer attempts to advance к forecast generation step
- THEN UI shows hard block с 3-button recovery: «Try different proxy / Add multi-proxy / Schedule consult»

**AC2.6 — Multi-proxy mode functional.**
- GIVEN customer adds 2nd proxy с pooling weights 0.6/0.4
- WHEN calculated
- THEN combined_score updates correctly per formula, multi_penalty = 1.05 (N=2), effective_inflation = base × 1.05

**AC2.7 — Multi-proxy floor warnings.**
- GIVEN multi-proxy config с individual scores [0.85, 0.42] (one below 0.5)
- WHEN aggregated
- THEN FloorWarning «individual_below_0_5» raised для proxy 2

**AC2.8 — i18n infrastructure functional.**
- GIVEN `messages/ru.json` populated
- WHEN customer opens app on system с RU locale
- THEN all UI strings render in Russian, no hardcoded strings detected

**AC2.9 — Backend Pydantic validation mirrors WASM.**
- GIVEN identical inputs to WASM and Python implementations
- WHEN both compute verdict
- THEN identical scores within 1e-9 floating-point tolerance

**AC2.10 — Per-category weight profile applied.**
- GIVEN recipient is OTC_PHARMA category
- WHEN similarity computed
- THEN OTC_PHARMA_WEIGHTS profile used (category 0.40, ATC structure emphasized) per SIMILARITY_FRAMEWORK §4

#### 4.4.7 Test Plan + DoD

**Frontend tests (Vitest, ~40):**
- Component rendering (single + multi-proxy mode)
- Field interactions
- Radar chart updates
- Verdict display + explanation panel
- Anti-pattern UI rendering

**Backend tests (Pytest, ~50):**
- Similarity calc per dimension (positive + negative + edge)
- Verdict computation
- Multi-proxy aggregation
- Anti-pattern detection
- Per-category weight profiles

**Property-based tests (~20):**
- Symmetry S(A,B) = S(B,A)
- Identical fields → S = 1.0
- Disjoint L1 → S < 0.5
- Multi-proxy ordering invariance (swap proxies, swap weights → same combined)

**Performance tests:**
- WASM call ≤16ms p99
- Bundle size ≤200KB gzip

**Integration tests:**
- Frontend ↔ WASM data flow
- Frontend ↔ Backend Pydantic validation parity

**DoD:**
- [ ] 110 tests pass
- [ ] WASM bundle ≤200KB verified
- [ ] i18n: all UI strings via $t(), no hardcoded RU
- [ ] Insufficient verdict blocks downstream workflow
- [ ] Anti-pattern detector covers 4+ patterns

#### 4.4.8 Open Questions (B2)

- **OQ-B2-1:** Charting library — D3.js vs ECharts? **Recommend ECharts** (Эконометрика already uses, consistency, less custom code).
- **OQ-B2-2:** WASM crate selection — `nalgebra` vs raw arrays for 6×6 dimension calc? **Recommend raw arrays** (smaller bundle).
- **OQ-B2-3:** AI proxy suggestion via local Phi-3.5 (Phase A C2 bundled) — silent feature B2 with feature flag? Per audit M2.

#### 4.4.9 Dependencies

- **Phase A:** C2 source adapters (для proxy data ingestion в downstream B3), C4 Tauri shell template
- **Internal:** B1 (Pydantic schemas из ProxyBrandMetadata)

---

## §5 Pass 2 Sprints (B3 / B4 / B5 / B6)

**Status:** В разработке (Pass 2 of two-pass delivery per HIGH H7 fix).

Pass 1 ship'нут как foundation. Pass 2 будет добавлен после mini-audit Pass 1 + commit.

---

## §6 Quality Gates & Audit Findings Registry

**Pass 1 self-audit pending.**

---

## §7 Cross-doc Consistency Audit

**Pending Pass 2 completion.**

---

## Appendices

### Appendix A: Pydantic Catalog (Pass 1)

Все B0.5/B1/B1.5/B2 Pydantic models above. Полный catalog после Pass 2 ship.

### Appendix B: Engine Signature Catalog (Pass 1)

Все B0.5/B1/B1.5/B2 function signatures above. Full catalog after Pass 2.

### Appendix C: Glossary

См. `02_Data_Spec/SIMILARITY_FRAMEWORK.md` Section 1 (dimension definitions). Phase B+ extension.

### Appendix D: Known Limitations & Decisions Deferred

- AI-assisted proxy suggestion — Phase C+ (после pilot data accuracy benchmark)
- Brand autocomplete from DSM database — Phase C+ (legal/operational)
- Adaptive narrative LLM-driven — Phase C+ (template-based в Phase B B4)
- Counterfactual posterior update preview — Phase C+ (B5 ships closed-form Estimate only)

---

**End Pass 1.** Total LOC: ~1850. Pass 2 in progress.
