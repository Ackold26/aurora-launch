# Changelog

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
