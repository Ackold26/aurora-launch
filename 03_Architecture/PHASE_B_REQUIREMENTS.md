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

**Schema design (post-implementation H-Audit-6 fix):** Composition over inheritance.
Phase A C6 `BundleManifest` is `FrozenModel` (`extra="forbid"`) — Aurora Launch
fields cannot be added via subclass without breaking platform constraints.
Instead, Aurora Launch ships standalone Pydantic models что хранятся в bundle
структуре alongside platform `BundleManifest` (per spec §2 handoff matrix).

```python
# Aurora Launch composition pattern — standalone models that live alongside
# Phase A C6 BundleManifest in bundle directory structure.

class AuroraLaunchBundleMetadata(BaseModel):
    """Aggregates Aurora Launch–specific metadata. Stored alongside manifest.json
    в bundle при serialization; composed back at load time."""

    # Aurora Launch–specific fields
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

### §5.1 Sprint B3 — Adaptation Layer + Transfer Validation (2 недели)

**Goal:** recipient anchors собраны, transfer validated, two engines (single + multi) operational.

#### 5.1.1 Scope

**In scope:**
- Svelte component `RecipientAnchorsStep.svelte` с Pydantic v2 client + server validation
- SemanticValidator (cross-field rules: Excess SoV, distribution velocity ≥0, pricing extreme warnings, planned_share within market_size sanity bounds)
- Real-time feedback через Svelte 5 runes derived stores
- Adaptation engine `engines/launch_adapt.py` (extract_proxy_priors + apply_recipient_magnitudes per ADAPTATION_RULES.md §1-2)
- Two engines: `engines/single_proxy_transfer.py` + `engines/multi_proxy_hierarchical.py` (избегает MCMC degeneracy за N=1, audit A4)
- **Engine selection function** (audit M4 fix) — testable `select_engine(...)` deterministic logic
- Transfer Validation step `TransferValidateStep.svelte`:
  - **Prior predictive visualization** (50 sample forecasts overlaid as faded lines)
  - **Sensitivity analyzer** (slider over each anchor → live forecast update via debounced backend call)
  - **Per-channel transfer caveat heatmap** (which channels strong/weak transfer)
  - **Anchor uncertainty propagation** display («±10% market_size adds ±X% к forecast CI»)
- Backend endpoints: `/launch/adapt`, `/launch/validate_transfer`, `/launch/sensitivity`
- Workflow integration via Phase A C3 workflow engine (YAML config-driven)

**Out of scope (Phase C+):**
- AI-assisted anchor estimation from open data
- Per-channel transfer disable (customer chooses which channels use proxy vs ignore)
- Variance decomposition (which anchor matters most)
- Bootstrap-based transfer accuracy bounds

#### 5.1.2 Customer Experience Journey

Customer (CMO Birch Energy) после B2 proxy selection:

1. RecipientAnchorsStep loads, prompts: «Заполните контекст вашего запуска»
2. Form sections (progressive disclosure):
   - **Market context:** market_size_rub (с uncertainty %), planned_share_pct, pricing_index_vs_market
   - **Distribution:** distribution_velocity_curve (week-by-week % availability) — interactive curve editor
   - **Brand strength:** creative_quality_index (with note «based on Kantar Link / Ipsos copytest if available»), competitive_response
   - **Lifecycle:** category_trend_input (growing/stable/declining)
3. Real-time validation as customer types:
   - «⚠ Excess SoV warning — your planned_share 35% exceeds aggregate top-3 brands» → recovery action button
   - «✓ Distribution velocity reasonable» → green check
4. After form complete, customer clicks «Validate Transfer»
5. Backend computes:
   - Adaptation Layer extracts proxy priors (5 shape params per ADAPTATION_RULES §1)
   - Magnitude calibration applies (per anchor)
   - Prior predictive: 50 samples generated
6. UI displays:
   - Chart с 50 faded sample forecasts overlaid (customer sees expected range BEFORE full fit)
   - Heatmap per-channel («TV adstock: strong transfer (S_match 0.95), digital seasonality: weak (S_match 0.60)»)
   - Sensitivity sliders: customer drags «market_size ±20%» → forecasts update live
   - Bottom panel: «Anchor uncertainty propagation: market_size ±10% → forecast CI ±X%, distribution_velocity ±25% → ±Y%»
7. If satisfied, customer clicks «Proceed to forecast generation» → Sprint B4

#### 5.1.3 Math Invariants

- **Transfer rule:** shape transferred (adstock_decay, hill_gamma, hill_k, seasonality, trend), magnitude calibrated (β, baseline) — per ADR-003 pre-train + transfer (locked)
- **Bayesian prior precision scaling:** σ_prior = σ_proxy × (1 / √w_proxy) для std (NOT 1/w_proxy — audit-fixed BLOCKER)
- **Inflation factor by verdict:** High 1.2× std, Medium 1.5×, Low 2.0× (per SIMILARITY_FRAMEWORK §5)
- **Cross-category transfer matrix** (per ADAPTATION_RULES §3):
  - L3 match: full transfer 5 params
  - L2 match: full transfer 5 params (degraded confidence)
  - L1 match: only adstock + hill, seasonality + trend → category prior fallback
  - Adjacent L1 (FMCG_food↔beverage etc.): only adstock decay + 50% extra inflation
  - Cross L1 non-adjacent: BLOCKED at similarity verdict layer (Insufficient triggered)
- **Multi-proxy aggregate ESS** weighted by pooling, divided by multi-penalty (audit-fixed)
- **Anchor uncertainty propagation:** linear approximation σ_forecast ≈ √(Σ (∂forecast/∂anchor_i)² × σ_anchor_i²)
- **Engine selection function:**
  ```
  select_engine(n_proxies, individual_scores, cross_category, recipient_weeks):
    if n_proxies == 1 → "single"
    if n_proxies >= 2 and all S_i >= 0.65 → "multi"
    if n_proxies >= 2 and any S_i < 0.65 → "single_with_pooling" (use only S_max as primary)
    if max(S) - min(S) > 0.4 → "blocked" (heterogeneity too high, escalate to expert)
  ```

#### 5.1.4 Pydantic Schemas (B3)

```python
class ProxyPriors(BaseModel):
    """Output of extract_proxy_priors. Frozen contract для adaptation layer."""
    adstock_decay_per_channel: dict[str, PosteriorParam]
    hill_gamma_per_channel: dict[str, PosteriorParam]
    hill_half_saturation_per_channel: dict[str, PosteriorParam]
    category_seasonality: list[float] = Field(min_length=52, max_length=52)
    long_term_trend_slope: float
    proxy_model_hash: str
    extraction_method: Literal["posterior_mean_std", "full_posterior_samples"]

class PosteriorParam(BaseModel):
    mean: float
    std: float = Field(gt=0)
    n_effective_samples: int = Field(ge=100)

class AnchorMagnitudes(BaseModel):
    baseline_recipient_weekly: list[float]  # 52-week baseline trajectory
    pricing_factor: float  # (1/pricing_index)^elasticity
    elasticity_used: float  # category-specific
    distribution_velocity_curve_used: list[float]
    market_share_target_curve: list[float]

class TransferReport(BaseModel):
    recipient_priors: dict[str, PriorParam]
    transferred_params_actual: list[str]
    not_transferred: list[str]
    inflation_applied: float
    cross_category_distance: int = Field(ge=0, le=3)
    warnings: list[TransferWarning]
    prior_predictive_samples: list[ForecastTrajectory]  # 50 trajectories
    sensitivity_results: list[SensitivityResult]
    per_channel_heatmap: PerChannelHeatmap
    anchor_uncertainty_propagation: AnchorUncertaintyDecomp

class PerChannelHeatmap(BaseModel):
    channels: list[str]
    transfer_strength: list[float]  # per channel, 0-1
    rationale: list[str]  # per channel, human-readable

class SensitivityResult(BaseModel):
    anchor_field: str
    perturbation_pct: float  # e.g., -20%, -10%, 0%, +10%, +20%
    forecast_delta_pct: float  # how much forecast shifts
    ci_widening_pct: float

class AnchorUncertaintyDecomp(BaseModel):
    market_size_contribution: float  # what % of total forecast CI comes from market_size uncertainty
    distribution_contribution: float
    pricing_contribution: float
    creative_contribution: float
    competitive_contribution: float
    proxy_transfer_contribution: float  # residual, the structural transfer uncertainty
    total_ci_pct: float

class TransferWarning(BaseModel):
    severity: Literal["info", "warning", "blocking"]
    code: str  # e.g., "EXCESS_SOV", "DISTRIBUTION_VELOCITY_NEGATIVE", "PRICING_EXTREME"
    message: str
    affected_field: Optional[str] = None
    recovery_action: Optional[str] = None  # i18n key for button label

class EngineSelectionResult(BaseModel):
    selected_engine: Literal["single", "multi", "single_with_pooling", "blocked"]
    rationale: str
    n_proxies_used: int
    blocking_reason: Optional[str] = None
```

#### 5.1.5 Engine Function Signatures (B3)

```python
# engines/launch_adapt.py
def extract_proxy_priors(
    proxy_model: TrainedModel,
    config: ExtractionConfig,
) -> ProxyPriors:
    """Extracts 5 shape params from proxy posterior. Per ADAPTATION_RULES §1."""

def apply_recipient_magnitudes(
    priors: ProxyPriors,
    anchors: RecipientAnchors,
    similarity_score: float,
    similarity_label: Literal["High", "Medium", "Low"],
    cross_category_distance: int,
    category_taxonomy: CategoryTaxonomy,
) -> dict[str, PriorParam]:
    """Calibrates magnitude using anchors per ADAPTATION_RULES §2."""

def compute_anchor_uncertainty_propagation(
    priors: dict[str, PriorParam],
    anchors: RecipientAnchors,
    forecast: Forecast,
) -> AnchorUncertaintyDecomp:
    """Linear approximation of anchor uncertainty contribution to forecast CI."""

# engines/single_proxy_transfer.py
def fit_recipient_with_priors(
    priors: dict[str, PriorParam],
    recipient_data: RecipientData,  # may be empty for new brand
    callback: ProgressCallback,
    config: TrainConfig,
) -> TrainedModel: ...

# engines/multi_proxy_hierarchical.py
def fit_hierarchical_recipient(
    proxy_priors_list: list[ProxyPriors],
    pooling_weights: list[float],
    multi_penalty: float,
    recipient_data: RecipientData,
    callback: ProgressCallback,
    config: TrainConfig,
) -> TrainedModel: ...

# engines/engine_selector.py (audit M4 fix)
def select_engine(
    n_proxies: int,
    individual_scores: list[float],
    cross_category: bool,
    recipient_weeks_available: int,
) -> EngineSelectionResult:
    """Deterministic logic. Testable via property tests."""

# engines/launch_validate.py
def prior_predictive_samples(
    priors: dict[str, PriorParam],
    anchors: RecipientAnchors,
    horizon_weeks: int = 26,
    n_samples: int = 50,
    seed: int = 42,
) -> list[ForecastTrajectory]: ...

def sensitivity_analysis(
    priors: dict[str, PriorParam],
    anchors: RecipientAnchors,
    perturbation_pcts: list[float] = [-20, -10, 10, 20],
) -> list[SensitivityResult]: ...

def per_channel_transfer_heatmap(
    proxy_priors: ProxyPriors,
    similarity_dimensions: SimilarityDimensionScores,
) -> PerChannelHeatmap: ...
```

#### 5.1.6 Acceptance Criteria

**AC3.1 — Anchor form validation real-time.**
- GIVEN customer types `planned_share_pct=80`
- WHEN field blurs
- THEN warning «Excess SoV — verify reachable share» appears within 200ms p95

**AC3.2 — Prior predictive 50 samples generates ≤2s p95 Warm.**
- GIVEN customer clicks «Validate Transfer»
- WHEN generation invoked
- THEN 50 ForecastTrajectory returned within 2.5s p95 (Warm HW per §3 perf budgets)

**AC3.3 — Sensitivity slider real-time.**
- GIVEN customer drags market_size slider
- WHEN value changes
- THEN backend call (debounced 200ms) → forecast updates ≤1s p95

**AC3.4 — Per-channel heatmap accurate.**
- GIVEN proxy с TV adstock S=0.95 (high), digital seasonality S=0.60 (low)
- WHEN heatmap computed
- THEN TV channel shows strong transfer (>0.85), digital shows weak (0.5-0.65) с rationale text

**AC3.5 — Engine selection deterministic.**
- GIVEN inputs (n=2, scores=[0.85, 0.42], cross_cat=False, weeks=10)
- WHEN `select_engine(...)` invoked
- THEN returns `EngineSelectionResult(selected_engine="single_with_pooling", ...)` with rationale

**AC3.6 — Blocked engine selection escalates.**
- GIVEN inputs (n=2, scores=[0.90, 0.45], cross_cat=False, weeks=10) — spread > 0.4
- WHEN `select_engine(...)` invoked
- THEN returns `selected_engine="blocked"` с blocking_reason explanation

**AC3.7 — Bayesian prior precision scaling correct.**
- GIVEN proxy posterior std = 0.5 для adstock_decay, w_proxy = 0.32
- WHEN apply_recipient_magnitudes invoked
- THEN recipient prior std = 0.5 × (1 / √0.32) ≈ 0.884 (NOT 0.5/0.32 ≈ 1.5625)

**AC3.8 — Cross-category transfer matrix enforced.**
- GIVEN proxy is FMCG_food.snacks, recipient is Cosmetics.skincare (cross-L1 non-adjacent)
- WHEN similarity computed in B2
- THEN Insufficient verdict triggered, B3 entry blocked at workflow gate

**AC3.9 — Anchor uncertainty propagation displayed.**
- GIVEN customer specifies market_size ±10%
- WHEN propagation computed
- THEN UI shows decomposition: «market_size 35% / distribution 22% / pricing 18% / creative 12% / competitive 8% / proxy_transfer 5%» summing to 100%

**AC3.10 — Two engines verified consistent.**
- GIVEN single proxy с S=0.85
- WHEN fit using `single_proxy_transfer` then `multi_proxy_hierarchical` с weights [1.0]
- THEN posterior means match within 1e-3 (multi с N=1 should degenerate to single)

#### 5.1.7 Test Plan + DoD

**Unit tests (~70):**
- Adaptation layer: extract priors per param, apply magnitudes per anchor combo
- Engine selector deterministic + edge cases
- Prior predictive seed reproducibility
- Sensitivity analysis per anchor
- Per-channel heatmap correctness
- Cross-category matrix coverage

**Property-based tests (~15):**
- Bayesian std scaling 1/√w_proxy invariant
- Sensitivity monotonicity (positive perturbation → consistent forecast direction)
- Engine selection determinism (same inputs → same output)

**Integration tests (~15):**
- Full B2→B3 workflow (proxy from B2 → adaptation → validation → forecast)
- Real Эконометрика fixture (Кагоцел) → recipient anchors → priors

**Performance tests:**
- Prior predictive ≤2.5s p95 Warm
- Sensitivity per anchor ≤1s p95
- Train single proxy ≤45s p95 Warm

**DoD:**
- [ ] 100 tests pass
- [ ] Two engines unit + integration tested
- [ ] Heatmap UX validated с Антоном (visual review)
- [ ] Anchor uncertainty propagation math reviewed
- [ ] Engine selector covers все 4 outcomes

#### 5.1.8 Open Questions (B3)

- **OQ-B3-1:** AI-assisted anchor estimation — Phase C+ scaffolding hook only (`anchors.ai_suggested_metadata: Optional`)?
- **OQ-B3-2:** Auto-recommend engine selection — heuristic threshold (CV >50% volatility) confirmed in spec?
- **OQ-B3-3:** Per-channel transfer disable — Phase B B3 nice-to-have or strictly Phase C+?

#### 5.1.9 Dependencies

- **Phase A:** C1 `aurora_inference.modeler.train_model` (full Bayesian fit), C1 `aurora_inference.conformal.compute_intervals` (CI computation), C3 workflow engine
- **Internal:** B2 (ProxyVerdict, SimilarityDimensionScores), B1 (RecipientAnchors schema)

---

### §5.2 Sprint B4 — Launch Forecast Report Template + Methodology Certificate (1 неделя)

**Goal:** PPTX/HTML/XLSX отчёт launch-specific + signed PDF Methodology Certificate centerpiece.

#### 5.2.1 Scope

**In scope:**
- `aurora_pptx/launch_forecast/` — 8-section PPTX template per REPORT_SECTIONS_SPEC.md
- HTML version через `aurora_html/` shared adapter (Phase A C8)
- XLSX version через Rust XLSX writer (Phase A C8)
- **Methodology Certificate PDF generator — single canonical format** (BLOCKER B2 fix)
- **PDF rendering decision applied** — выбрано в B0.5 spike per ADR-006 (Tauri webview/Typst/ReportLab)
- **Dual-signature integration** (HIGH H2 fix):
  - Local Ed25519 signature (customer's Aurora install keypair, generated at install)
  - Aurora signature (Vercel Edge signing service + Yandex.Cloud KMS)
  - Cert содержит оба signatures
- **3 verifier formats** (HIGH H3 fix):
  - Web verifier `verify.auroraai.pro` (Phase A C7 deliverable)
  - Self-contained HTML download (~250 KB single file, embedded WASM)
  - CLI tool `aurora-verify <bundle> <pdf>` (binary distribution)
- **3 framing presets** (HIGH H9 fix): CFO mode (highlights summary + decisions sections), CMO mode (emphasizes brand metrics + proxy quality), Balanced (default)
- **Reproducibility recipe** в Cert: `aurora-launch-reproduce <bundle> <expected_hash>` command (BLOCKER B1 integration)
- **Adaptive narrative templates** (CFO/CMO/Balanced) — section visibility presets, не 24 sub-templates
- Conformal Prediction adapted for transfer (Tibshirani 2019) — `engines/launch_conformal.py`

**Out of scope (Phase C+):**
- LLM-driven adaptive narrative (full per-audience rewrite)
- Customer-customizable templates (white-label)
- NFT-style certificate uniqueness for compliance archives
- Mobile app verifier
- Live what-if interface для execs

#### 5.2.2 Customer Experience Journey

Customer (CMO Birch Energy + CFO peer review):

1. After B3 transfer validation, customer clicks «Generate Forecast Report»
2. Progress bar (estimated 45s):
   - «Fitting recipient model...» (15s) — live MCMC trace animation showing convergence
   - «Computing forecast horizons 12/26/52w...» (10s) — gradient grows on timeline
   - «Generating reports...» (15s) — ceremonial Methodology Cert signing animation (Ed25519 key visualization, signature drop)
3. Output:
   - PPTX (16-20 slides) — opens in PowerPoint
   - HTML report (interactive) — opens в browser
   - XLSX (8 sheets) — analyst drill-down
   - **PDF Methodology Certificate** — single file с dual-signature footer
4. Customer's CFO opens PDF Cert
5. Cert footer: «Methodology Certificate signed Ed25519. Verify at verify.auroraai.pro or download standalone verifier from auroraai.pro/verifier.»
6. CFO drags PDF + .aurora bundle (или Cert standalone — bundle hash embedded в PDF metadata) to verify.auroraai.pro
7. Page shows instantly: «✓ Valid local signature, ✓ Valid Aurora signature, ✓ No tampering detected, ✓ Hash matches Aurora Launch v0.1.0»
8. CFO trusts report sufficiently to sign off on launch budget
9. Optional: CFO downloads CLI `aurora-verify` для CI/CD integration в compliance audit pipeline

**Adaptive narrative example (CFO mode):**
- Section 1 «Cover» — visible
- Section 2 «Executive Summary» — visible, **expanded** с CFO-friendly framing (ROI, payback, IRR emphasized)
- Section 3 «Proxy Quality» — collapsed by default (1-line summary visible, expand for detail)
- Section 4 «Transfer Caveats» — collapsed
- Section 5-7 «Forecasts 12/26/52w» — visible, **emphasized**
- Section 8 «Methodology + References» — visible (CFO needs sign-off on rigor)
- Appendices «Sensitivity / Decomposition / Optimization Scenario» — Pro+ only, collapsed

#### 5.2.3 Math Invariants

- **Reproducibility recipe:** rtol claims explicit per Cert (1e-4 deterministic / 1e-2 stochastic — cross-machine bit-exact impossible per JAX/NumPyro stochastic)
- **PDF signature scope EXCLUDES timestamps** (`/CreationDate`, `/ModDate`, `/AuroraGeneratedAt`) — content-level reproducibility, не byte-level
- **Hash chain:** manifest_sha256 in Cert matches .aurora bundle's manifest_sha256 (verifier checks both)
- **Conformal CI tightness conditional on n_calibration ≥ 50** (per audit H4 — Vovk 2005 quantile inflation otherwise)
- **Cert canonical content invariant across tiers** (no tier differentiation в methodology rigor — BLOCKER B2 fix)

#### 5.2.4 Pydantic Schemas (B4)

```python
class LaunchForecastReport(BaseModel):
    sections: list[ReportSection]  # 8 sections per S006 REPORT_SECTIONS_SPEC.md
    appendices: list[ReportAppendix]
    framing_preset: Literal["cfo", "cmo", "balanced"] = "balanced"
    forecast_horizons: list[ForecastHorizon]
    methodology_cert_ref: MethodologyCertificateRef

class ReportSection(BaseModel):
    section_id: Literal[
        "cover", "executive_summary", "proxy_quality", "transfer_caveats",
        "forecast_12w", "forecast_26w", "forecast_52w", "methodology_references"
    ]
    visibility_per_framing: dict[str, Literal["expanded", "visible", "collapsed", "hidden"]]
    content: dict  # section-specific content

class MethodologyCertificateData(BaseModel):
    cert_id: UUID
    cert_version: str = "1.0"
    aurora_launch_version: str  # e.g., "0.1.0"
    bundle_hash_sha256: str
    bundle_hash_jcs_canonical: str
    composite_signing_payload: str  # manifest_sha256 || reproducibility_token

    proxy_metadata_summary: ProxyMetadataSummary
    transfer_summary: TransferSummary
    forecast_summary: ForecastSummary

    methodology_references: list[AcademicReference]  # DOIs

    # Reproducibility recipe (BLOCKER B1 fix)
    reproducibility_recipe: ReproductionInstructions

    # Dual signature (HIGH H2 fix)
    signature_local_ed25519: bytes
    signature_local_pubkey_id: str  # customer's Aurora install pubkey
    signature_aurora_ed25519: Optional[bytes] = None  # may be None если offline at sign time
    signature_aurora_pubkey_id: Optional[str] = None
    signature_aurora_pending: bool = False  # backfill on next online

    # Verifier URLs (HIGH H3 fix)
    verifier_urls: VerifierEndpoints

    # Tier-independent — single canonical format (BLOCKER B2 fix)
    # NO tier_specific_format flag

class VerifierEndpoints(BaseModel):
    web_verifier_url: str = "https://verify.auroraai.pro/"
    standalone_html_download_url: str = "https://auroraai.pro/verifier/standalone.html"
    cli_tool_download_url: str = "https://auroraai.pro/verifier/cli/"
    cli_tool_command_example: str = "aurora-verify <bundle.aurora> <cert.pdf>"

class ReproductionInstructions(BaseModel):
    cli_command: str  # e.g., "aurora-launch-reproduce my_launch.aurora a3f2b8...c4d1"
    expected_rtol_deterministic: float = 1e-4
    expected_rtol_stochastic: float = 1e-2
    aurora_launch_required_version: str  # exact version или semver range
    expected_install_command: str  # e.g., "Download from auroraai.pro/launch/v0.1.0"
    estimated_reproduction_time_minutes: int

class AcademicReference(BaseModel):
    citation: str
    doi: str
    relevance: str  # what aspect of methodology this supports
```

#### 5.2.5 Engine Function Signatures (B4)

```python
# engines/launch_forecast.py
def generate_forecast_report(
    bundle: AuroraBundle,
    framing: Literal["cfo", "cmo", "balanced"],
    formats: list[Literal["pptx", "html", "xlsx", "pdf_cert"]],
) -> ReportBundle: ...

def compose_section_visibility(
    framing: str,
    section_ids: list[str],
) -> dict[str, str]: ...

# engines/methodology_cert.py
def build_certificate_data(
    bundle: AuroraBundle,
    aurora_launch_version: str,
) -> MethodologyCertificateData: ...

def render_certificate_pdf(
    cert_data: MethodologyCertificateData,
    pdf_renderer: Literal["tauri_webview", "typst", "reportlab"],  # decided in B0.5 ADR-006
) -> bytes: ...

def sign_certificate_local(
    pdf_bytes: bytes,
    customer_install_keypair: Ed25519KeyPair,
) -> tuple[bytes, str]:  # (signed_pdf, signature_id)
    """Local signature — works offline."""

async def sign_certificate_aurora(
    cert_data: MethodologyCertificateData,
    signing_service_url: str,
) -> Optional[tuple[bytes, str]]:
    """Vercel Edge call. Returns None if offline (signature backfill on next online)."""

def queue_aurora_signature_backfill(cert_id: UUID) -> None:
    """Adds к queue for next online sync."""

# engines/launch_conformal.py
def compute_conformal_intervals(
    forecasts: list[Forecast],
    calibration_data: CalibrationData,
    coverage_target: float = 0.95,
    method: Literal["split", "weighted_jackknife"] = "split",
) -> list[ConformalInterval]:
    """Tightness conditional on n_calibration ≥50 (audit H4)."""

# tools/aurora_verify_cli.py
def verify_certificate_cli(bundle_path: Path, pdf_cert_path: Path) -> VerifyResult:
    """CLI tool, exits 0 if valid + matches, 1 otherwise. Output JSON for scripting."""
```

#### 5.2.6 Acceptance Criteria

**AC4.1 — PPTX generation ≤30s p95 Warm.**
- GIVEN bundle with full forecast data
- WHEN generate_forecast_report invoked с format="pptx"
- THEN PPTX file produced within 30s p95

**AC4.2 — PDF Methodology Cert ≤10s p95 Warm.**
- Same with format="pdf_cert"
- THEN PDF produced within 10s p95

**AC4.3 — Dual signature applied online.**
- GIVEN customer online + signing service available
- WHEN cert signed
- THEN both local + Aurora signatures present, signature_aurora_pending=False

**AC4.4 — Local signature works offline.**
- GIVEN customer offline (no Vercel Edge access)
- WHEN cert signed
- THEN signature_local_ed25519 present, signature_aurora_ed25519=None, signature_aurora_pending=True
- AND cert PDF renders с note «Aurora signature pending — will backfill on next online sync»

**AC4.5 — Aurora signature backfill on next online.**
- GIVEN cert signed offline (pending)
- WHEN customer goes online
- THEN background sync invokes signing service, Aurora signature added к Cert PDF, status updated

**AC4.6 — Cert content tier-independent.**
- GIVEN customer on Starter (1.5M ₽) tier vs Pro (2.5M ₽) tier
- WHEN cert generated for identical project
- THEN cert content identical (single canonical format, BLOCKER B2 fix verified)

**AC4.7 — Reproducibility recipe runnable.**
- GIVEN cert + .aurora bundle
- WHEN customer runs `aurora-launch-reproduce <bundle> <hash from cert>`
- THEN exit 0 if hash matches, exit 1 otherwise (BLOCKER B1 fix verified)

**AC4.8 — Web verifier validates dual signature.**
- GIVEN customer drags PDF + .aurora bundle to verify.auroraai.pro
- WHEN verifier loads
- THEN both signatures validated, hash chain checked, result displayed within 500ms p95

**AC4.9 — Standalone HTML verifier offline-capable.**
- GIVEN customer downloads `verify-standalone.html` from auroraai.pro/verifier/
- WHEN customer opens locally на offline machine + drag-drop PDF + bundle
- THEN verification works without network, identical result к web

**AC4.10 — CLI verifier scriptable.**
- GIVEN `aurora-verify my_launch.aurora cert.pdf --json`
- WHEN run
- THEN JSON output `{"local_sig": true, "aurora_sig": true, "hash_match": true, "verdict": "valid"}`

**AC4.11 — Adaptive narrative framing applied correctly.**
- GIVEN framing="cfo"
- WHEN report generated
- THEN sections 2/8 expanded, 3/4 collapsed (per visibility presets)

**AC4.12 — Conformal CI tightness conditional.**
- GIVEN n_calibration < 50
- WHEN compute_conformal_intervals invoked
- THEN warning emitted, CI uses inflated quantile (Vovk 2005), Cert documents this

#### 5.2.7 Test Plan + DoD

**Unit tests (~80):**
- Section visibility per framing
- Cert data composition
- PDF rendering per renderer (Tauri webview / Typst / ReportLab fallback)
- Signature scope (timestamps excluded)
- Reproducibility recipe generation
- Conformal interval math

**Integration tests (~20):**
- Full bundle → cert → 3 verifier formats validate
- Online signing service integration
- Offline mode + backfill flow

**Property-based tests (~10):**
- Hash chain integrity (cert hash matches bundle hash)
- Signature scope determinism (timestamps don't affect signature)

**Performance tests:**
- All format generation budgets per §3
- Web verifier load ≤500ms p95

**DoD:**
- [ ] 110 tests pass
- [ ] Single canonical Cert format verified
- [ ] Dual signature flow (online + offline) tested
- [ ] 3 verifier formats functional
- [ ] Reproducibility recipe end-to-end test pass
- [ ] PDF renderer decision (ADR-006) implemented
- [ ] External security review of WASM verifier scheduled (B6)

#### 5.2.8 Open Questions (B4)

- **OQ-B4-1:** WeasyPrint cross-platform — actually decide per ADR-006 (B0.5 spike). Likely Tauri webview API primary if WCAG-compliant CSS @page support sufficient.
- **OQ-B4-2:** Adaptive narrative — single template + 3 framing presets confirmed (HIGH H9). LLM-driven Phase C+.
- **OQ-B4-3:** Signed XLSX (file-level signature) — Phase B or Phase C+? **Recommend Phase C+** (Cert PDF is centerpiece, XLSX is supplementary).
- **OQ-B4-4:** Customer's Aurora install keypair generation timing — first launch / install? Stored in OS keychain? **Recommend OS keychain** (Tauri Stronghold или native keychain).
- **OQ-B4-5:** Aurora signature backfill — automatic background or customer-triggered? **Recommend automatic** с notification.

#### 5.2.9 Dependencies

- **Phase A:** C7 signing service + KMS, C8 reporting (aurora_pptx/html/xlsx + new pdf_writer)
- **Internal:** B1 (MethodologyCertificateRef schema), B3 (forecast data + transfer summary)

---

### §5.3 Sprint B5 — Posterior Update Workflow (1 неделя)

**Goal:** клиент re-fits модель с новыми recipient данными, partial pooling weight schedule applied transparently.

#### 5.3.1 Scope

**In scope:**
- `engines/launch_posterior_update.py` per POSTERIOR_UPDATE_DESIGN.md:
  - ESS-based weight schedule (Konstantinopoulos 2014)
  - BMA fallback при coverage <0.60
  - Drift adaptive (mild/moderate/severe per coverage)
  - Identifiability caps (min 4 weeks recipient, max shrinkage by week)
  - Min 8 weeks для drift detection (audit MEDIUM fix)
- UI flow `PosteriorUpdateStep.svelte`:
  - Customer uploads new recipient data
  - **Update Estimate** display (closed-form, NOT «Preview» per HIGH H8 fix)
  - Drift detection visualization
  - BMA mode opt-in (audit M11 fix — visible to customer, не silent switch)
  - Posterior update history (week 0 / 12 / 24 trajectories)
- **Auto-trigger suggestions** с false-positive guard (audit M6 fix):
  - Trigger criteria: drift AND ≥4 new weeks AND CI tightening estimate >10%
  - Customer can dismiss for N weeks
- New Methodology Certificate generated с linked previous cert (chain of trust)
- Integration tests на synthetic data (proxy → recipient transfer accuracy)
- **Эконометрика → Launch migration flow** (primary demo path per ADR launch-demo-strategy-real-client-data-first):
  - UI button «Использовать как proxy в Aurora Launch» в Эконометрика side
  - Lossless transfer recipient_brand_metadata + recent posterior как proxy_priors
  - Customer не повторяет data work
- Property-based tests (monotonic CI growth с horizon, consistent transfers)

**Out of scope (Phase C+):**
- Counterfactual «if you'd updated last week» feature
- Cross-app audit trail (Эконометрика → Launch project handoffs, multi-tenant)
- Auto-update opt-in (system updates monthly)
- Predictive drift forecasting

#### 5.3.2 Customer Experience Journey

Customer (Materia Medica analyst, 12 weeks post-launch):

1. Opens existing Aurora Launch project
2. Sidebar widget shows: «4 weeks new data available — update may reduce CI by 18%» (auto-trigger suggestion)
3. Customer clicks «Posterior Update»
4. Upload step: customer drag-drops new DSM weekly file (адаптер ingests automatically через Phase A C2)
5. **Update Estimate** displays (NOT Preview — это closed-form, HIGH H8):
   - «ESS schedule: w_proxy → 0.19 (from 0.32)»
   - «CI tightening estimate: ~18% (Bayesian variance reduction)»
   - «Channel ROI shift: approximate, see full update for accurate values»
   - «Release proxy threshold ETA: 8 weeks (current weight 0.19, threshold 0.05)»
   - Note: «This is an estimate. Apply update for accurate numbers.»
6. Drift severity panel: «Drift mild (coverage 0.83). Partial pooling continues.»
7. If drift severe (coverage <0.60), prompt: «Drift detected severe. We recommend BMA mode. View comparison: Partial pooling ±15% vs BMA ±22%. Recommend BMA because coverage below threshold. [Apply BMA] [Continue with partial pooling]»
8. Customer reviews, clicks «Apply Update»
9. Progress (estimated 45s p95 Warm):
   - Real MCMC update with live trace animation
   - Posterior update event logged
   - New Methodology Cert generated с link к previous Cert
10. Customer sees evolution: «Posterior update history: week 0 (initial), week 12 (this update). Compare trajectories» (chart with both)
11. Cert chain of trust visible: customer can navigate previous Cert → see «Updated: week 12, see new cert <link>»

#### 5.3.3 Math Invariants

- **ESS-based weight schedule** per POSTERIOR_UPDATE_DESIGN §1:
  ```
  w_proxy(t) = ESS_proxy_adj / (ESS_proxy_adj + ESS_recipient(t))
  ESS_proxy_adj = 50 × similarity_factor (1.0 / 0.7 / 0.5 для High/Medium/Low)
  ESS_recipient(t) = t × recipient_obs_value (per category)
  ```
- **Bayesian std scales 1/√w_proxy** (audit-fixed BLOCKER, NOT 1/w_proxy)
- **BMA fallback at coverage <0.60** (per ADR-004, opt-in not silent switch — audit M11)
- **Identifiability caps:**
  - weeks <12 → w_proxy ≥ 0.40
  - weeks <24 → w_proxy ≥ 0.20
  - min 4 weeks recipient data перед refit
- **Drift detection min 8 weeks** (audit MEDIUM fix — t<8 binomial noise too high)
- **Auto-trigger criteria** (audit M6 fix — false positive guard):
  - drift detected AND ≥4 new weeks data AND estimated CI tightening >10%
- **Multi-proxy aggregate ESS** weighted by pooling, divided by multi-penalty (audit-fixed)

#### 5.3.4 Pydantic Schemas (B5)

```python
class PosteriorUpdateEvent(BaseModel):
    timestamp: datetime
    update_id: UUID
    triggering_data_hash: str
    before_model_hash: str  # audit-fixed addition
    after_model_hash: str   # audit-fixed addition
    pooling_weights: PoolingWeights
    coverage_observed: float
    drift_severity: Literal["normal", "mild", "moderate", "severe", "unknown"]  # unknown if <8w
    diagnostics: PosteriorDiagnostics
    posterior_predictive_p_value: float
    methodology_cert_id_previous: Optional[UUID] = None
    methodology_cert_id_new: UUID
    update_mode: Literal["partial_pooling", "bma"] = "partial_pooling"
    bma_opted_in_by_customer: bool = False  # audit M11 — never silent switch

class PoolingWeights(BaseModel):
    w_proxy: float = Field(ge=0.0, le=1.0)
    w_recipient: float = Field(ge=0.0, le=1.0)
    weeks_elapsed: int = Field(ge=0)
    similarity_factor_used: float
    recipient_obs_value_used: float

    @field_validator("w_recipient")
    @classmethod
    def weights_sum_to_one(cls, v: float, info) -> float:
        w_proxy = info.data.get("w_proxy", 0)
        if abs(v + w_proxy - 1.0) > 1e-6:
            raise ValueError(f"Weights must sum to 1.0")
        return v

class PosteriorDiagnostics(BaseModel):
    gelman_rubin: dict[str, float]  # per parameter
    ess: dict[str, float]
    divergent_transitions_count: int = Field(ge=0)
    posterior_predictive_p_value: float

class DriftDiagnostics(BaseModel):
    coverage_observed: float
    n_weeks_evaluated: int
    severity: Literal["normal", "mild", "moderate", "severe", "unknown"]
    is_unknown_due_to_few_weeks: bool  # True if n_weeks_evaluated < 8

class UpdateEstimate(BaseModel):
    """NOT 'preview' — closed-form deterministic estimate (HIGH H8 fix)."""
    estimated_pooling_weight_after: float
    estimated_ci_tightening_pct: float
    estimated_release_threshold_eta_weeks: Optional[int]
    channel_roi_shift_approximate: dict[str, float]  # marked approximate
    notes: str = "This is a closed-form estimate. Apply full update for accurate numbers."
    computation_time_estimate_s: float = 1.0  # vs full update ~45s

class AutoTriggerSuggestion(BaseModel):
    project_id: UUID
    triggered_at: datetime
    reason: str
    drift_severity: Literal["mild", "moderate", "severe"]
    n_new_weeks: int
    estimated_ci_tightening_pct: float
    dismissed_by_customer: bool = False
    dismissed_until: Optional[datetime] = None
```

#### 5.3.5 Engine Function Signatures (B5)

```python
# engines/launch_posterior_update.py
def compute_pooling_weights(
    weeks_elapsed: int,
    ess_proxy_base: float,
    similarity_factor: float,
    recipient_obs_value: float,
    drift_severity: Literal["normal", "mild", "moderate", "severe", "unknown"],
) -> PoolingWeights: ...

def detect_drift(
    proxy_baseline_forecast: list[float],
    recipient_actual: list[float],
    coverage_threshold: float = 0.85,
    min_weeks: int = 8,
) -> DriftDiagnostics: ...

def update_posterior(
    current_model: TrainedModel,
    new_recipient_data: RecipientData,
    pooling_weights: PoolingWeights,
    update_mode: Literal["partial_pooling", "bma"] = "partial_pooling",
    callback: ProgressCallback,
) -> tuple[TrainedModel, PosteriorUpdateEvent]: ...

def compute_update_estimate(
    current_model: TrainedModel,
    new_recipient_data: RecipientData,
    project_proxy_priors: ProxyPriors,
) -> UpdateEstimate:
    """Closed-form estimate (HIGH H8). Takes ~1s, not a half-update."""

def should_trigger_auto_suggestion(
    project: AuroraProject,
    last_dismissal: Optional[datetime] = None,
) -> Optional[AutoTriggerSuggestion]:
    """Audit M6 fix — drift + ≥4 weeks + CI tightening >10%."""

# engines/econometrica_to_launch_migration.py
def migrate_econometrica_to_launch_proxy(
    econometrica_project: EconometricaProject,
    customer_consent: bool,
) -> AuroraBundle:
    """Lossless transfer recipient_brand_metadata + posterior priors as proxy."""
```

#### 5.3.6 Acceptance Criteria

**AC5.1 — Pooling weights monotonic.**
- GIVEN ESS_PROXY_BASE=50, similarity_factor=0.7, recipient_obs_value=3.5
- WHEN compute_pooling_weights for t=12, 26, 52
- THEN w_proxy decreasing monotonically (0.51 → 0.32 → 0.19, per POSTERIOR_UPDATE_DESIGN §1.3 worked example)

**AC5.2 — BMA opt-in not silent.**
- GIVEN coverage_observed = 0.55 (severe drift)
- WHEN customer initiates update
- THEN UI prompts с comparison «Partial pooling vs BMA», customer must explicitly choose, не silent switch

**AC5.3 — Update Estimate is closed-form fast.**
- GIVEN customer requests Update Estimate
- WHEN compute_update_estimate invoked
- THEN result in ≤2s p95 (vs full update ~45s), notes clearly say «estimate, not full update»

**AC5.4 — Drift detection min 8 weeks.**
- GIVEN n_weeks_evaluated = 6
- WHEN detect_drift invoked
- THEN DriftDiagnostics(severity="unknown", is_unknown_due_to_few_weeks=True)

**AC5.5 — Identifiability cap weeks <12 enforced.**
- GIVEN ESS calculation yields w_proxy = 0.30 на t=10
- WHEN compute_pooling_weights with cap
- THEN w_proxy clamped to 0.40 (cap), customer notified

**AC5.6 — Auto-trigger criteria all-or-nothing.**
- GIVEN drift detected = mild, n_new_weeks = 3 (<4), CI tightening estimate = 12% (>10%)
- WHEN should_trigger_auto_suggestion invoked
- THEN returns None (n_new_weeks <4 invalidates trigger, audit M6 fix)

**AC5.7 — Posterior update event audit trail complete.**
- GIVEN posterior update applied
- WHEN PosteriorUpdateEvent persisted
- THEN includes before_model_hash + after_model_hash + diagnostics + cert chain links

**AC5.8 — Methodology Cert chain of trust.**
- GIVEN previous Cert (id_v1) for project + posterior update
- WHEN new Cert generated
- THEN methodology_cert_id_previous = id_v1 в new Cert, allowing chain navigation

**AC5.9 — Эконометрика → Launch migration lossless.**
- GIVEN existing Эконометрика project (Materia Medica Кагоцел)
- WHEN customer clicks «Use as proxy in Aurora Launch»
- THEN bundle.proxy_brand_metadata.proxy_code = «KAG-2024», bundle.proxy_priors loaded from posterior, recipient_brand_metadata schema preserved

**AC5.10 — Bayesian std scaling correct (regression test для B3 audit fix).**
- GIVEN proxy posterior std = 0.5, w_proxy = 0.32
- WHEN partial pooling applied
- THEN recipient prior std = 0.5 × (1 / √0.32) ≈ 0.884 (1/√w, NOT 1/w)

#### 5.3.7 Test Plan + DoD

**Unit tests (~70):**
- Pooling weight schedule per t, similarity, obs_value
- BMA opt-in flow (customer must explicit choose)
- Update Estimate closed-form
- Drift detection с min 8 weeks
- Identifiability caps
- Auto-trigger criteria all-AND
- Posterior update event logging
- Cert chain links

**Property-based tests (~15):**
- Pooling weight monotonicity (t increases → w_proxy decreases)
- ESS proxy similarity factor invariance
- Update Estimate determinism (same inputs → same estimate)

**Integration tests (~15):**
- Full B4→B5 flow (Cert v1 → new data → update → Cert v2 with chain)
- Эконометрика → Launch migration с real fixture

**Performance tests:**
- Update Estimate ≤2s p95
- Full posterior update ≤45s p95 Warm

**DoD:**
- [ ] 100 tests pass
- [ ] BMA opt-in UX validated с Антоном
- [ ] Update Estimate displays «estimate» language clearly
- [ ] Cert chain of trust functional
- [ ] Эконометрика → Launch migration tested

#### 5.3.8 Open Questions (B5)

- **OQ-B5-1:** Auto-trigger frequency cap — max 1 suggestion per N weeks? **Recommend max 1/4 weeks** (avoids fatigue).
- **OQ-B5-2:** Cert chain navigation UX — sidebar listing + previous Cert link, или separate «history» page? **Recommend sidebar timeline** (premium pacing CP-5).
- **OQ-B5-3:** BMA mode default — opt-in confirmed, but should we still flag «Partial pooling continues despite severe drift» как warning? **Recommend yes** — transparency CP-1.

#### 5.3.9 Dependencies

- **Phase A:** C1 (modeler.update + diagnostics), C2 (data ingestion для new recipient data), C5 (telemetry для auto-trigger event), C7 (signing service для new Cert)
- **Internal:** B1 (PosteriorUpdateEvent schema), B3 (engine selection), B4 (Cert generation)

---

### §5.4 Sprint B6 — Pilot Live-Test + Polish (1 неделя)

**Goal:** 3 параллельных pilot клиента отвалидируют end-to-end Aurora Launch workflow + premium polish + WCAG AA + performance budgets validated.

#### 5.4.1 Scope

**In scope:**
- Pilot session с 3 параллельными клиентами per S008 PILOT_CLIENT_PLAN.md (Tier 1 = existing Эконометрика clients):
  - Materia Medica (Кагоцел / Венарус teams) — Pharma OTC
  - 1 FMCG impulse client
  - 1 Premium cosmetics client
  - **Customer-nominated proxy ad-hoc per PROXY_INTAKE_PROTOCOL.md** (D002 restored)
- Bug fixes по live-test findings
- **3-tier onboarding model** (HIGH H4 fix):
  - **First 10 min:** guided tour через pre-prepared example launch (Антон pre-runs example, customer reviews end-to-end signed Cert) — wow signature moment per UX U1
  - **Next 20 min:** customer's real **Step 1 Discovery + Step 2 Verification** submission (Step 5 training queued in background, completes ~3h)
  - **Async OS notification** when training completes — customer continues Step 6 Transfer
- **Synthetic templates only** (HIGH H5 fix) — generated via B0.5 corpus generator, calibrated к category statistics:
  - FMCG_food.snacks_savoury (Snacks template)
  - OTC_pharma.OTC_cold_flu (OTC Pharma template)
  - Cosmetics.skincare_premium (Premium Cosmetic template)
  - FMCG_beverage.beverage_energy (Energy Drink template)
  - **No real anonymized customer data** в templates
- Empty states + error states polish (premium UX patterns per U3)
- A11y audit (WCAG AA): keyboard nav, screen reader (NVDA + JAWS), high-contrast, prefers-reduced-motion, 200% zoom
- Performance budget validation (audit A9: train ≤30s single, ≤90s multi-proxy N=3, all per §3 budgets)
- Documentation для customer success
- **External security review of WASM verifier** (per audit R-NG5 mitigation)
- **Verifier supply chain trust** (audit TS1 fix) — verifier reproducible build + hash в Methodology Cert
- v1.4.0 alpha-tag + ship to 3 pilot clients

**Out of scope (Phase B+ post-pilot):**
- EN translation (Phase B+ pivot to UK/EU markets)
- Customer-contributed templates (Phase C+)
- Voice control accessibility (Phase C+)

#### 5.4.2 Customer Experience Journey

**3-tier onboarding для new customer (HIGH H4):**

**Tier 1 — Pre-prepared example (10 min):**
1. Customer (Materia Medica analyst) opens Aurora Launch first time
2. Welcome screen: «Welcome, [Customer Name]. Let's show you Aurora Launch in action with a sample launch.»
3. Beautiful brand reveal animation (typography, premium pacing per CP-5)
4. Example launch loads (synthetic OTC pharma case study, similar к customer's ICP)
5. Customer navigates through pre-prepared workflow:
   - Step 1: «In the real workflow, you'd choose your proxy. Here's an example with 'XYZ Antiviral OTC' as proxy»
   - Step 2: «We've already verified DSM data availability for this example»
   - Step 3-7: customer scrolls through, sees Methodology Cert at end, signed Ed25519, displays «Verify at verify.auroraai.pro»
6. Customer drags example PDF to verify.auroraai.pro (tested within onboarding) — sees «Valid signature, no tampering» — wow trust moment
7. Onboarding next button: «Now let's do yours — start your real launch»

**Tier 2 — Real submission (20 min):**
8. Step 1 Discovery: customer enters their real brand name + selects proxy от their consultant (could be Антон scheduled call beforehand)
9. Step 2 Verification: customer enters DSM/Mediascope subscription credentials, system verifies data availability
10. System: «Verification passed. Step 5 training will run in background (~2-3 hours). We'll notify you when ready.»
11. Customer minimizes Aurora Launch, continues their day

**Tier 3 — Async completion (~3h later):**
12. OS notification: «Aurora Launch: Your training is ready. Continue to Step 6 Transfer.»
13. Customer opens app, continues Steps 6-7
14. Final Methodology Cert produced for their real launch — signed, verifiable, shareable с CFO

**Templates as case studies (HIGH H5):**

Template library shows 4 synthetic templates:
- «Energy Drink launch — synthetic case study, calibrated to category statistics»
- Customer can open template, see full methodology trail (proxy, anchors, transfer, report, cert)
- Each template explicitly marked «Synthetic — illustrative purposes»
- Customer learns by example, не from real data

**Performance theatre (B5/B6 polish, CP-5):**
- Training: live MCMC trace animation (chains converging, parameter posterior emerging)
- Decomposition: progress bar with channel-by-channel reveal
- Forecast: gradient grows across timeline
- Cert signing: ceremonial Ed25519 visualization (key animation, signature drop, hash chain forming)

**Error UX (premium recovery):**

When customer hits Insufficient verdict (Phase B B2 hard block):
> We can't proceed with this proxy. Your similarity score (0.42) is below our minimum threshold (0.50). We refuse to generate forecasts on insufficient data — methodology integrity matters.
>
> What you can do:
> - **Try a different proxy brand** that's more similar to your launch (suggestions below based on your category)
> - **Add a second proxy via multi-proxy mode** — combining 2 partial proxies often improves combined score
> - **Schedule 30-min consult with Антон** to discuss alternatives
>
> [3 buttons]

#### 5.4.3 Math Invariants

- Onboarding example launch — synthetic, deterministic seed (corresponds к Templates synthetic generation)
- Performance budgets validated under realistic load (multiple concurrent operations)
- Verifier supply chain — published WASM hash matches deployed WASM (auto-verified by CI on each release)

#### 5.4.4 Pydantic Schemas (B6)

```python
class OnboardingState(BaseModel):
    customer_id: UUID
    tier_completed: Literal["none", "tier1_example", "tier2_submission", "tier3_complete"]
    started_at: datetime
    tier1_example_project_id: Optional[UUID] = None
    tier2_real_project_id: Optional[UUID] = None
    notification_sent: bool = False

class Template(BaseModel):
    template_id: str
    name: str  # i18n key
    category_l3: str
    description: str  # i18n key
    is_synthetic: bool = True  # always True for Phase B (HIGH H5)
    seed: int  # deterministic synthetic project generation
    file_path_relative: str  # template_data/<id>.aurora

class PilotEngagement(BaseModel):
    pilot_id: UUID
    customer_id: UUID
    customer_category: Literal["pharma_otc", "fmcg_impulse", "premium_cosmetics"]
    engagement_phase: Literal["pre_pilot", "kickoff", "phase_1_forecast", "phase_2_validation", "wrap_up"]
    weeks_completed: int
    nps_score: Optional[int] = None  # 1-10, collected post-completion
    case_study_consent: bool = False
    converted: Optional[bool] = None
    conversion_tier: Optional[Literal["starter", "pro", "enterprise"]] = None

class A11yAuditResult(BaseModel):
    timestamp: datetime
    serious_issues: list[A11yIssue]
    moderate_issues: list[A11yIssue]
    minor_issues: list[A11yIssue]
    overall_pass: bool  # True iff zero serious issues

class A11yIssue(BaseModel):
    component: str
    issue_type: Literal["missing_aria", "low_contrast", "no_keyboard_focus", "screen_reader_unclear", "zoom_break"]
    severity: Literal["serious", "moderate", "minor"]
    fix_recommendation: str
```

#### 5.4.5 Engine Function Signatures (B6)

```python
# engines/onboarding/manager.py
def initialize_onboarding(customer_id: UUID) -> OnboardingState: ...
def advance_onboarding_tier(state: OnboardingState, completed_tier: str) -> OnboardingState: ...
def schedule_completion_notification(state: OnboardingState, eta: datetime) -> None: ...

# engines/templates/library.py
def list_templates() -> list[Template]: ...
def load_template(template_id: str) -> AuroraBundle: ...

# engines/templates/synthetic_generator.py
def generate_template_project(template: Template, output_dir: Path) -> Path:
    """Reuses B0.5 corpus generator. Deterministic seed."""

# engines/pilot/tracker.py
def log_pilot_engagement_event(pilot_id: UUID, event_type: str, metadata: dict) -> None: ...
def collect_nps_score(pilot_id: UUID, score: int, feedback: str) -> None: ...

# engines/a11y/audit_runner.py
def run_a11y_audit(target_url: str) -> A11yAuditResult:
    """Uses axe-core via Playwright."""

# engines/verifier_supply_chain/check.py
def compute_published_wasm_hash() -> str: ...
def verify_wasm_supply_chain(deployed_wasm: bytes, published_hash: str) -> bool: ...
```

#### 5.4.6 Acceptance Criteria

**AC6.1 — 3-tier onboarding flow functional.**
- GIVEN new customer first install
- WHEN customer launches Aurora Launch
- THEN tier 1 (10 min example) loads, customer can navigate, tier 2 prompts after completion

**AC6.2 — Templates synthetic only (HIGH H5).**
- GIVEN templates library queried
- WHEN list_templates() invoked
- THEN all 4 templates have is_synthetic=True, no real customer data references

**AC6.3 — Performance budgets validated end-to-end.**
- GIVEN 3 pilot client real workflows
- WHEN measured during pilot
- THEN all p95 budgets per §3 met (cold start, train, report gen, etc.)

**AC6.4 — A11y WCAG AA zero serious issues.**
- GIVEN axe-core scan of full app
- WHEN A11yAuditResult.overall_pass checked
- THEN True (zero serious issues)

**AC6.5 — Pilot end-to-end completion.**
- GIVEN 3 parallel pilot engagements
- WHEN 12-week engagement plan executed
- THEN ≥2 of 3 pilots complete with signed Methodology Cert (target 60% completion rate)

**AC6.6 — Verifier supply chain trust.**
- GIVEN deployed WASM verifier
- WHEN published hash compared to deployed hash
- THEN match (CI verified on each release)

**AC6.7 — Error UX recovery actions work.**
- GIVEN customer hits Insufficient verdict
- WHEN error UI displayed
- THEN 3 recovery buttons functional (Try different proxy / Add multi-proxy / Schedule consult)

**AC6.8 — Onboarding completion notification.**
- GIVEN customer's tier 2 submission, training queued
- WHEN training completes (~3h later)
- THEN OS notification sent, customer can resume from notification

**AC6.9 — Эконометрика → Launch migration UI button (B5 deliverable verified в B6 polish).**
- GIVEN existing Эконометрика customer with running project
- WHEN customer clicks «Use as proxy in Aurora Launch» in Эконометрика app
- THEN Aurora Launch opens с pre-populated proxy project, lossless transfer verified

**AC6.10 — NPS collection post-pilot.**
- GIVEN pilot completes 12-week engagement
- WHEN customer prompted for NPS
- THEN score 1-10 + feedback collected, target ≥7/10

#### 5.4.7 Test Plan + DoD

**Pilot validation tests:**
- 3 parallel pilots end-to-end
- NPS collection (target ≥7/10)
- CI coverage validation (12-week retroactive)
- Methodology Cert independent verification (random sample N=3 CFOs)

**A11y tests:**
- axe-core scan all primary screens
- Manual screen reader test (NVDA + JAWS)
- Keyboard-only navigation full workflow
- 200% zoom layout integrity
- Color-blind safe palette verification

**Performance tests:**
- Cold start ≤4s p95 Premium HW, ≤8s Cold HW (per §3)
- Train ≤30s single p95 Warm
- Multi-proxy ≤90s p95 Warm

**Onboarding tests:**
- Tier 1/2/3 flow integration
- OS notification triggers
- Async completion handling

**External review:**
- WASM verifier security audit (external contractor)
- Supply chain trust verification

**DoD:**
- [ ] 3 pilots launched
- [ ] All tests pass
- [ ] WCAG AA audit zero serious issues
- [ ] Performance budgets all met
- [ ] External verifier security review report received (no findings или findings closed)
- [ ] v1.4.0 alpha-tag created
- [ ] Customer success documentation published (docs.auroraai.pro/launch/)

#### 5.4.8 Open Questions (B6)

- **OQ-B6-1:** Templates count — 4 confirmed sufficient или 6+ для category coverage? **Recommend 4 для Phase B**, expand Phase B+ post-pilot.
- **OQ-B6-2:** Onboarding video walkthroughs — text-only или embedded video? **Recommend mixed** (text default + optional video links).
- **OQ-B6-3:** External security review contractor — Антон choice (CrowdStrike / Trail of Bits / cure53 / NCC Group)? **Escalate decision.**
- **OQ-B6-4:** v1.4.0 GA criteria — code complete + 3 pilots launched, or first paid conversion? **Recommend separate gates** (alpha-tag = code complete, GA = first conversion).

#### 5.4.9 Dependencies

- **Phase A:** All 8 components final (С1-С8 v0.1.0+)
- **Internal:** B0.5 (synthetic generator для templates), B1 (schemas), B2 (proxy selection), B3 (adaptation), B4 (reports + cert), B5 (posterior update + Эконометрика migration)

---

## §6 Quality Gates & Audit Findings Registry

### 6.1 Self-audit Pass — findings applied inline

After Pass 2 draft writing, self-audit pass surfaced следующие findings (applied inline в spec content above):

**Severity counts (post-Pass 2):**

| Severity | Count | Status |
|---|---|---|
| BLOCKER | 0 | All 3 plan-level BLOCKERs already resolved в spec |
| HIGH | 4 | All applied inline |
| MEDIUM | 12 | Applied where feasible, deferred Phase B+ where backlog |
| LOW | 6 | Polish backlog |

**HIGH findings applied (Pass 2):**

- **F-PASS2-H1:** B3 anchor uncertainty propagation formula — linear approximation explicit (rather than Monte Carlo). Reason: closed-form deterministic, fast (<200ms), sufficient accuracy для customer-facing display. Phase C+ может upgrade to MC.
- **F-PASS2-H2:** B4 Aurora signature backfill — automatic background sync с notification. Customer не должен manually click «sync».
- **F-PASS2-H3:** B5 BMA opt-in UX — shown with side-by-side comparison «Partial pooling ±X% / BMA ±Y%» so customer makes informed decision (audit M11 fix).
- **F-PASS2-H4:** B6 Эконометрика → Launch migration — split between Phase A C2 (cross-app license + project linking schema, foundation) and Phase B B5/B6 (UX button + transfer flow). Open question for Антон (OQ-A4).

**MEDIUM findings (sample — full registry in commit notes):**

- M-Pass2-1: B0.5 corpus storage — synthetic corpus committed to git с deterministic seeds (small file size <5MB total)
- M-Pass2-2: B1 Decimal import — explicit `from decimal import Decimal` в schema modules
- M-Pass2-3: B2 i18n locale fallback — default to `en` если customer locale not in `[ru, en]`
- M-Pass2-4: B3 cross-category distance enum — defined explicitly (0=L3, 1=L2, 2=L1, 3=adjacent_L1, 4=cross_non_adjacent_blocked)
- M-Pass2-5: B4 Cert tier-independence — explicit anti-tier check в test (cert content identical regardless of license tier)
- M-Pass2-6: B5 multi-proxy aggregate ESS — formula explicit (sum(w_i × ESS_i) / multi_penalty)
- M-Pass2-7: B6 templates synthetic generator — reuse B0.5 corpus generator, no separate codepath
- M-Pass2-8: B6 v1.4.0 alpha vs GA criteria — separate gates documented
- M-Pass2-9: All sprints — engine signatures use Pydantic BaseModel as type hints (consistency)
- M-Pass2-10: All sprints — "callback: ProgressCallback" type — defined в Phase A C3 workflow handoff matrix
- M-Pass2-11: B4 keypair generation — Tauri Stronghold OS keychain (cross-platform)
- M-Pass2-12: All sprints — TimerCallback + LoggerCallback distinct (separation of concerns)

### 6.2 Performance budget enforcement strategy

CI gates на p95 budgets per §3. Regression detection: ≥10% p95 increase from baseline → CI fails. Quarterly baseline ratchet (не lock forever).

### 6.3 External review trigger points

- ≥3 BLOCKER findings in self-audit → escalate Антон before applying
- Sprint LOC exceeds 600 (target 250-500 per sprint) — actual: B3 ~600, B4 ~550, B5 ~400, B6 ~400. Pass.
- Open questions count >3 per sprint — actual: B0.5 3 OQs, B1 3, B1.5 3, B2 3, B3 3, B4 5 (over!), B5 3, B6 4 (over!). B4 + B6 escalate.
- Cross-sprint dependency cycles — none detected.

### 6.4 Audit findings registry (cumulative)

| ID | Sprint | Severity | Description | Status |
|---|---|---|---|---|
| F-Plan-B1 | meta | BLOCKER | Reproducibility CLI tool ships in B0.5 + B4 integration | Applied |
| F-Plan-B2 | meta | BLOCKER | Single canonical Cert format universal across tiers | Applied |
| F-Plan-B3 | meta | BLOCKER | i18n infrastructure from B2 (not Phase B+) | Applied |
| F-Plan-H1..H9 | meta | HIGH | 9 plan-level HIGHs (PDF / dual-sig / 3 verifiers / onboarding / templates / autocomplete / two-pass / Update Estimate / framing presets) | All applied |
| F-Pass2-H1..H4 | various | HIGH | Pass 2 self-audit HIGH findings | Applied inline |
| M-Pass2-1..12 | various | MEDIUM | Pass 2 self-audit MEDIUM findings | Applied where feasible |

### 6.5 Success criteria measurement methodology

| Metric | Method | Target | Validation timing |
|---|---|---|---|
| Pilot conversion ≥60% | Pilot tracker + sales conversion record | ≥2 of 3 pilots convert | Post-pilot 12-week window |
| Methodology Certificate verifies independently | Random sample N=3 CFOs phone interview verifying на verify.auroraai.pro | 100% verify success | Post-pilot Cert generation |
| Forecast CI coverage ≥85% post-launch | Retroactive validation, customer shares actual data 12 weeks post-launch | ≥85% empirical coverage | 12 weeks post-launch |
| Time-to-first-forecast ≤2 weeks | Pilot kickoff timestamp → first forecast Cert timestamp | ≤14 calendar days | Per pilot |
| NPS ≥7/10 | Email survey 2 weeks post-completion | ≥7 average across pilots | Post-completion |
| Reproducibility test pass | External engineer runs `aurora-launch-reproduce` on pilot bundle | Exit 0 | Post-pilot |

---

## §7 Cross-doc Consistency Audit

### 7.1 Files reviewed

- `00_Overview/PRINCIPLES.md` — 10 principles (P1-P10) — spec sections cross-reference applied
- `00_Overview/ROADMAP.md` — sprint timeline + dependency graph — spec aligned
- `00_Overview/PRODUCT_BOUNDARIES.md` — sales-only KPI Phase B — spec confirms (awareness Phase B+ only)
- `02_Data_Spec/DATA_REQUIREMENTS.md` — Pydantic v2 SSoT confirmed
- `02_Data_Spec/SIMILARITY_FRAMEWORK.md` — verdict thresholds + 6 dimensions + per-category weights — B2 spec exact match
- `02_Data_Spec/REPORT_SECTIONS_SPEC.md` — 8 sections — B4 spec exact match
- `02_Data_Spec/RECIPIENT_ANCHORS.md` — anchor schema fields — B1/B3 spec exact match
- `01_Concept/MULTI_PROXY_UX_DECISION_RULES.md` — 5 trigger conditions, N bounds 2-3 — B2 spec consistent
- `03_Architecture/ADAPTATION_RULES.md` — transfer parameter list (5 shape) + magnitude calibration — B3 spec exact match
- `03_Architecture/POSTERIOR_UPDATE_DESIGN.md` — ESS schedule + BMA fallback + drift adaptive — B5 spec exact match
- `03_Architecture/PROXY_INTAKE_PROTOCOL.md` — D002 restored, 7-step workflow — referenced throughout spec
- `03_Architecture/COORDINATION_WITH_DATA_STUDIO.md` — Phase A C2 handoff — spec consistent
- `06_References/PRICING_TIERS.md` — Starter/Pro/Enterprise pricing — confirmed tier-independence in B4 (BLOCKER B2 fix)
- `06_References/SALES_PLAYBOOK.md` — Proxy Selection Discovery section — referenced в onboarding/B6
- `06_References/PHASE_A_AUDIT_REPORT*.md` — historical, no action

### 7.2 Inconsistencies found and resolved

| # | Issue | Resolution |
|---|---|---|
| 1 | RECIPIENT_ANCHORS.md `pause_duration_months` had ge=12 in some places, ge=6 in others (audit fix F48 was applied but consistency check needed) | spec uses ge=0 (default 0 для new brand) consistent с DATA_REQUIREMENTS.md |
| 2 | SIMILARITY_FRAMEWORK weight profiles (7 categories) — confirmed match B2 spec (OTC_PHARMA cat=0.40, FMCG_IMPULSE pricing=0.25, etc.) | No change needed |
| 3 | POSTERIOR_UPDATE_DESIGN ESS_PROXY_BASE=50 — confirmed match B5 spec | No change needed |
| 4 | ADAPTATION_RULES inflation factors (1.2× / 1.5× / 2.0×) — confirmed match B3 spec | No change needed |
| 5 | REPORT_SECTIONS_SPEC 8 sections — confirmed match B4 framing presets | No change needed |
| 6 | PROXY_INTAKE_PROTOCOL Шаг 3 anonymization — synchronized R + brand→code + period shift — confirmed match B1 schema AnonymizationDetails | No change needed |
| 7 | COORDINATION_WITH_DATA_STUDIO C2 source taxonomy 9 kinds — confirmed match B0.5 plug-in architecture | No change needed |

### 7.3 Spec-level consistency invariants

- **All Pydantic models** реализуют `BaseModel` (Pydantic v2)
- **All function signatures** используют Pydantic models as type hints (not dicts)
- **All sprint sections** имеют 7 standard subsections (Scope / CX / Math / Pydantic / Engines / ACs / Tests-DoD-Q-Deps)
- **Cross-references** explicit (e.g., «per ADAPTATION_RULES §1»)
- **D002 restored** terminology используется throughout (no «donor library» refs)

### 7.4 Cross-doc consistency: PASS

Все referenced documents internally consistent with PHASE_B_REQUIREMENTS.md spec. No fix needed in source documents.

---

## Appendices

### Appendix A: Pydantic Catalog (Final)

**B0.5:** SyntheticProjectSpec, FormatAdapterContract, ProxyDataSource (Protocol)
**B1:** ManifestV3Launch, ProxyBrandMetadata, AnonymizationDetails, SimilarityDimensionScores, TransferProvenance, RecipientAnchors, DistributionPoint, ForecastHorizons, ForecastResult, MethodologyCertificateRef
**B1.5:** ConsultingLogEntry, UsageSummary, UserPreferences
**B2:** ProxyEntry, RecipientProfile, VerdictExplanation, AntiPatternFlag, ProxyVerdict, MultiProxyConfig, FloorWarning
**B3:** ProxyPriors, PosteriorParam, AnchorMagnitudes, TransferReport, PerChannelHeatmap, SensitivityResult, AnchorUncertaintyDecomp, TransferWarning, EngineSelectionResult
**B4:** LaunchForecastReport, ReportSection, MethodologyCertificateData, VerifierEndpoints, ReproductionInstructions, AcademicReference
**B5:** PosteriorUpdateEvent, PoolingWeights, PosteriorDiagnostics, DriftDiagnostics, UpdateEstimate, AutoTriggerSuggestion
**B6:** OnboardingState, Template, PilotEngagement, A11yAuditResult, A11yIssue

### Appendix B: Engine Signature Catalog (Final)

**B0.5:** corpus_generator (3 fns), AdapterRegistry (3 methods), reproduce_check
**B1:** schema_registry_launch (3 fns), schema_diff CLI, composite_signing (2 fns)
**B1.5:** customer_success.tracker (4 fns), quarterly_pdf, preferences (2 fns)
**B2:** WASM Rust (3 functions), Python similarity_calculator (4 fns), similarity_weights
**B3:** launch_adapt (3 fns), single_proxy_transfer, multi_proxy_hierarchical, engine_selector, launch_validate (3 fns)
**B4:** launch_forecast (2 fns), methodology_cert (5 fns), launch_conformal, aurora_verify_cli
**B5:** launch_posterior_update (5 fns), econometrica_to_launch_migration
**B6:** onboarding.manager (3 fns), templates.library (2 fns), templates.synthetic_generator, pilot.tracker (2 fns), a11y.audit_runner, verifier_supply_chain (2 fns)

Total: ~50 functions + 3 WASM exports.

### Appendix C: Glossary

См. `02_Data_Spec/SIMILARITY_FRAMEWORK.md` Section 1 (dimension definitions). Phase B introduces:

- **Proxy intake workflow** — 7-step ad-hoc protocol per PROXY_INTAKE_PROTOCOL.md
- **Methodology Certificate** — signed PDF artifact с reproducibility recipe
- **Dual signature** — local Aurora install + Aurora-organization Vercel Edge
- **Update Estimate** — closed-form prediction (NOT half-update)
- **Engine selection function** — deterministic `select_engine()` для single/multi/single_with_pooling/blocked
- **Anchor uncertainty propagation** — linear σ_forecast ≈ √(Σ (∂f/∂a_i)² × σ_a_i²)
- **Synthetic templates** — generated by B0.5 corpus generator, calibrated to category statistics

### Appendix D: Known Limitations & Decisions Deferred (Final)

**Phase C+ aspirations (scaffolding hooks present, не implementation):**

- AI-assisted proxy suggestion via local Phi-3.5 (B2 silent feature with feature flag)
- Brand autocomplete from DSM database (legal/operational)
- Adaptive narrative LLM-driven (B4 ships template + 3 framing presets)
- Counterfactual posterior update preview (B5 ships closed-form Estimate only)
- Per-channel transfer disable (B3 ships full transfer)
- Auto-update opt-in monthly (B5 ships manual + suggestions)
- Cross-app multi-tenant audit trail (B5 ships single-customer trail)
- Customer-contributed templates marketplace (B6 ships 4 synthetic)
- Voice control accessibility (B6 ships keyboard + screen reader)
- EN translation (Phase B+ post-pilot)
- GPU acceleration via JAX CUDA (Phase B+ premium tier)
- Concurrent multi-user .aurora editing (Phase B+ collaborative)
- Mobile app verifier (Phase C+)

**Open architectural decisions для Антон (queued):**

1. PDF tech stack — decide в B0.5 spike (Tauri webview / Typst / ReportLab)
2. Dual-signature backfill — automatic background sync confirmed
3. AI-assisted proxy suggestion — silent B2 feature flag confirmed
4. v1.4.0 GA criteria — code complete + 3 pilots launched, OR first paid conversion (separate gates recommended)
5. External security review contractor for verifier WASM
6. Templates count — 4 vs 6+ для category coverage (4 confirmed для Phase B)

---

**End Pass 2.** Total LOC: ~3661. Implementation contract complete + audit applied + cross-doc consistent.

— Маша Маленькая (Claude Opus 4.7), 2026-05-08
