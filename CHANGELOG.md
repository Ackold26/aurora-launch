# Changelog

## v0.1.2-b05 — 2026-05-08 (post-audit-2 hardening)

### Audit fixes (B-A2-1..3 + H-A2-1..7 + M-A2-1..7)

**BLOCKER fixes:**
- B-A2-1: workflow YAML config flat reading (was assuming nested `params` key — defaults never applied). `AuroraLaunchStepBase` now reads flat config minus reserved keys.
- B-A2-2: posterior_update step moved к separate workflow file `aurora_launch_posterior_update.v1.yaml` (was `is_on_demand: true` config flag не respected by Workflow engine eager DAG execution).
- B-A2-3: error message references replaced fictional `aurora-launch-workflow-steps` entry-point group → real explanation about resolver allowlist (audit A16).

**HIGH fixes:**
- H-A2-2: `_AuroraLaunchStepBase` → `AuroraLaunchStepBase` (public class, was private). Backward-compat alias kept.
- H-A2-3: this CHANGELOG entry added (was: H-Audit-3/4/5/6 + 3 adapters not reflected).
- H-A2-5: `AuroraLaunchBundleMetadata.aurora_launch_version` Optional (was required → would break reading legacy bundles).
- H-A2-6: DSM V2023 `_normalize_date()` logs warning on unexpected format (was: silent passthrough).
- H-A2-7: workflow YAML `apply_recipient_magnitudes` now depends on `select_engine` (DAG gap closed — magnitude formula varies by engine choice).

**MEDIUM fixes:**
- M-A2-6: unit tests added для 5 new step executors в aurora-platform-core (`tests/test_aurora_launch_steps.py`).

## v0.1.1-b05 — 2026-05-08 (audit-1 hardening + B0.5 nice-to-haves)

### Added
- `src/aurora_launch/schemas/bundle.py` — `AuroraLaunchBundleMetadata` composition pattern (H-Audit-6).
- `src/aurora_launch/engines/format_adapters/dsm_v2023.py` — DsmAdapterV2023 (subclass V2024, comma sep + DD.MM.YYYY → ISO).
- `src/aurora_launch/engines/format_adapters/dsm_v2025.py` — DsmAdapterV2025 forward-compat scaffolding (tab sep + ISO 8601 datetime + new SKU/Region/Pricing_segment columns).
- `src/aurora_launch/engines/format_adapters/mediascope_tv_index.py` — MediascopeTvIndexAdapterV1 (multi-row header heuristic + TVR/GRP/Reach metrics).

### Audit fixes (B-Audit-1..5 + H-Audit-1..7 applied inline)
- B-Audit-1: dates use proper datetime arithmetic (was 30-day-month approximation).
- B-Audit-2: composite signing R8 closure with `data_artifacts_hash` (was forgeable).
- B-Audit-3: `compute_bundle_hash` recomputes repro_token independently (was trusting stored value).
- B-Audit-4: CI cross-platform (was path-deps + /tmp + Windows skip).
- B-Audit-5: awareness category logit-scale synthesis (was sales-driven default).
- H-Audit-1: reproduce CLI version skew warning.
- H-Audit-2: Pydantic verdict_validator → model_validator(mode="after").
- H-Audit-3: 14 categories full coverage (`_CATEGORY_RESPONSE_PARAMS_TABLE`).
- H-Audit-5: workflow YAML standard-fields-only (cleanup_callbacks/telemetry/performance_budgets distributed into step config).
- M-Audit-1: `py.typed` marker (PEP 561).
- M-Audit-2: LICENSE file.

## v0.1.0-b05 — 2026-05-08

**Sprint B0.5 — BC Test Corpus & Format Adapters + Reproducibility CLI**

### Added

- Python project bootstrap (uv + pyproject.toml + Python 3.11+)
- `src/aurora_launch/schemas/` — Pydantic v2 SSoT для proxy + synthetic corpus
- `src/aurora_launch/engines/corpus_generator/` — synthetic MMM data generation:
  - Hill saturation + adstock decay per channel
  - Category-specific seasonality (FMCG impulse / OTC pharma / cosmetics / etc.)
  - Deterministic via `np.random.PCG64(seed)` cross-platform
  - JCS RFC 8785 canonical hash для bundle integrity
  - Composite `manifest_sha256` + `reproducibility_token` (R8 closure)
- `src/aurora_launch/engines/format_adapters/` — plug-in registry + built-in adapters:
  - `DsmAdapterV2024` (full implementation pattern)
  - `MediascopeAdExAdapterV1` (preserves «Channek» typo signature)
  - `AdapterRegistry` — auto-detection + plug-in extensibility
  - `ProxyDataSource` Protocol — abstract contract Phase B+ extensions
- `src/aurora_launch/tools/reproduce.py` — **`aurora-launch-reproduce` CLI**
  (BLOCKER B1 deliverable per PHASE_B_REQUIREMENTS.md §4.1):
  - Headless reproducibility verification
  - Exit codes 0 (match) / 1 (mismatch) / 2 (error)
  - JSON output mode для CI/CD
  - Cross-mode: manifest_sha256 OR reproducibility_token
- `src/aurora_launch/tools/corpus_cli.py` — **`aurora-corpus` CLI**:
  - `list-categories` — show supported categories
  - `generate <category> <variant> --seed <N>` — single project
  - `generate-all` — full 5-project corpus
- `tests/` — comprehensive unit + integration tests (40+ tests):
  - Schema validation (proxy + synthetic_corpus)
  - Corpus generator determinism + tampering detection
  - Reproduce CLI (match/mismatch/error/json output/check_mode)
  - Format adapters (registry + DSM + Mediascope)
- `decisions/ADR-006-pdf-rendering.md` — Tauri webview print API primary,
  ReportLab fallback, Typst deferred Phase B+
- `.github/workflows/ci.yml` — multi-OS (Ubuntu + Windows), multi-Python (3.11/3.12)

### Architecture decisions

- **uv workspace structure flat** for aurora-launch (single app)
- **Path-based dependency** на aurora-platform-core for local dev
- **aurora-launch-reproduce** ships as bundled CLI script via project.scripts
- **PDF rendering** Tauri webview primary (per ADR-006)

### Phase B implementation contract — B0.5 sprint complete

Per `03_Architecture/PHASE_B_REQUIREMENTS.md` §4.1:
- ✅ AC0.5.1 Synthetic generation deterministic
- ✅ AC0.5.2 Format adapter auto-detection
- ✅ AC0.5.3 BC test parametrized
- ✅ AC0.5.4 aurora-launch-reproduce headless CLI
- ✅ AC0.5.5 PDF tech stack ADR recorded
- ✅ AC0.5.6 Plug-in architecture extensibility
- ✅ AC0.5.7 CI gate enforces BC
- ✅ AC0.5.8 Performance budget per generation (verified <30s)

### Pending (Sprint B0.5 nice-to-haves)

- DSM V2023 + V2025 adapters (template proven via V2024)
- Mediascope TV Index adapter (V1)
- 8+ corpus projects (currently 5 representative; adding 3+ during Phase B+ expansion)
- Real ProgressCallback integration (Phase A C3 dep)

— Маша Маленькая (Claude Opus 4.7), 2026-05-08
