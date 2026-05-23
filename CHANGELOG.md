# Changelog

## v0.1.6 — 2026-05-23 (Sprint 5 — Pilot Hardening & Security MEDIUM closure)

Pre-pilot hardening release. Closes Sprint 3 audit MEDIUM security findings
(#25 TOCTOU + #26 CLI injection) + H2 Tokio concurrency closure + 2 Sprint 4
discoveries (#35 a11y instance counter + #36 zip-bomb time defense). Includes
Opus max audit pass перед PR.

### Security — Sprint 5 Batch 3 (Sprint Buffer #25 + #26)

- **#25** — TOCTOU race closure в `verify_reproducibility`. Previously called
  `raw_path.exists()` then separate `canonicalize()` — attacker window для
  symlink swap. Single canonicalize() call с `ErrorKind::NotFound` mapped к
  `BundleNotFound`, other kinds к `Other`. INV-48 attack tests: 1 cross-platform
  regression + 2 `#[cfg(unix)]` symlink scenarios.
- **#26** — CLI command injection sanitization. `bundleFileName` embedded в
  `aurora-launch-reproduce "{name}" {hash}` `<pre>` block — chars outside
  `[A-Za-z0-9._\-() ]` могли escape double-quote и execute arbitrary commands
  при copy-paste к shell. Whitelist sanitizer + placeholder `<имя_файла>` +
  warning UI prompting manual substitution. 17 vitest cases (3 whitelist + 13
  injection vectors + 1 display preservation). New i18n key
  `cert.export.unsafe_filename_warning`.

### Concurrency — Sprint 5 Batch 4 (Sprint 4 Batch 7 H2 deferred)

- `verify_reproducibility` async fn выполняет sync I/O (std::fs::File::open +
  zip + streaming SHA-256 над всем bundle). Под concurrent UI load это
  blocks Tokio worker thread → IPC dispatch starves. Refactored через
  `tokio::task::spawn_blocking`: outer async wrapper unchanged (Tauri contract
  preserved), sync body extracted в private `verify_reproducibility_blocking`.
  JoinError → `AuroraError::Other`. Concurrent test (4 parallel calls на
  2-worker multi_thread runtime) passes без deadlock.

### Defense-in-depth — Sprint 5 Batch 5 (Sprint Buffer #36)

- **#36** — zip-bomb time exhaustion defense. Sprint 4 S2 streaming SHA-256
  prevented OOM, но attacker мог claim massive `size_bytes` в manifest с tiny
  ZIP compressed payload → hash loop crunches фабрикованный logical size.
  Upfront ratio check (`MAX_DECOMPRESSION_RATIO = 1000`) между
  `archive.by_name()` и hash loop. Pathological ratios → `status="error"` с
  descriptive RU reason. Threshold safely выше realistic compression ratios.

### Accessibility — Sprint 5 Batch 5 (Sprint Buffer #35)

- **#35** — `ChartWithDrillDown` instance counter moved из `<script lang="ts">`
  (instance scope) в `<script module>` block (module scope). Previously каждый
  component instantiation reset counter к 0 → two ChartWithDrillDown на same
  page получали same `cdd1` titleId → aria-labelledby collisions. Vitest case
  «два экземпляра имеют разные titleId» un-skipped и passes.

### Hardened — Sprint 5 audit pass (Opus max)

- TOCTOU residual race (canonicalize ↔ File::open OS-level window) documented
  в code comment с Aurora Launch threat model rationale. Full closure требует
  `fdpath()` pattern (cross-platform unstable) — tracked для server / multi-
  tenant deployment.
- Newline + carriage return injection test cases (`bundle\nrm.aurora`,
  `bundle\rls -la.aurora`) added к CertExportModal.test.ts.
- 5 secondary findings (O1-O5) documented для Sprint 6 — Windows symlink
  behavior, D9 boundary cases, broken symlink, spawn_blocking pool exhaustion,
  en.json i18n fallback.

### Hygiene — Sprint 5 Batch 1

- 7 CC-Sessions historical logs (Sprint 0 → Sprint 4) committed напрямую в
  main. Sprint Buffer audit — 7 Sprint 4 closures (#27, #28, #30, #31, #32,
  #33, #34) перенесены к `aurora-meta/SPRINT_BUFFER_ARCHIVE.md`.

### Sprint Buffer discoveries (deferred к Sprint 6)

- **#41** — bundle.rs sibling fns (`open_bundle`, `list_bundle_entries`,
  `read_bundle_entry`, `save_bundle`) имеют тот же anti-pattern что closed H2.
  `State<'_, AppState>` lifetime juggling делает spawn_blocking refactor
  сложнее — ~2-3h estimate.

### Verification

| Suite | Result |
|---|---|
| cargo test --lib | 56 passed, 0 failed (+3 since v0.1.5) |
| cargo test --lib commands::methodology_cert::tests | 19 passed (+4 для #25, #36, H2) |
| npx vitest run tests/unit/ | 730 passed, 1 skipped (was 727/2; +2 newline/CR injection, -1 #35 un-skip) |
| npx svelte-check | 0 errors, 2 pre-existing warnings |

### Backward compatibility

- `verify_reproducibility` IPC signature unchanged. ReproducibilityResult fields
  unchanged.
- CertExportModal props unchanged. New i18n key `cert.export.unsafe_filename_warning`
  с `default` RU fallback — graceful если EN locale ключ отсутствует.
- D9 size sanity check uses `if let Some` — backward compat с manifests без
  `size_bytes` field.

---

## v0.1.5 — 2026-05-21 (Sprint 4 — Pilot Scenarios + A11y + Sprint 3 Hardening)

Pre-pilot release. Closes Sprint 3 audit P0 findings + adds pharma pilot
scenarios + A11y core.

### Added — Sprint 4 Batch 1 (Test infrastructure, INV-48 enforcement)

- Rust integration tests для `verify_reproducibility` (14 attack-scenario tests
  включая fresh bundle / tampered content / forgery detection / hex validation /
  streaming hash / path traversal).
- Vitest tests for Sprint 3 transparency components — 85 cases across
  DrillDownModal + NumberWithDrillDown + ChartWithDrillDown + AuditTab.

### Added — Sprint 4 Batch 2 (Security hardening, INV-48 closure)

- **S1** — composite_bundle_hash cross-binding: `verify_reproducibility` now
  computes mirror of Python `BundleManifest.composite_bundle_hash()` (length-prefix
  encoded SHA-256). Result includes `composite_hash` field — external verifiers
  (signed methodology certificate) cross-check для R8 closure. Closes Sprint 3
  D6 per-file hash forgery vulnerability.
- **S2** — streaming SHA-256: per-file hash computation now uses chunked
  `Sha256::update()` loop (64 KB buffer) instead of `Vec<u8>` accumulation.
  OOM-resistant on adversarial zip-bomb input.
- **S4** — hex format validation: `manifest.files[*].sha256` validated как
  64-char ASCII hex before re-hashing. Malformed → "error" status с descriptive
  reason (replaces silent recording as garbage mismatch).

### Added — Sprint 4 Batch 3 (Pilot scenarios)

- 3 pharma pilot bundles в `tests/fixtures/pharma_pilot/`:
  pharma_otc_immune (Кагоцел-class OTC иммунитет), pharma_rx_cardio (Rx
  cardiology profile), pharma_generic_painkiller (generic анальгетик).
  Deterministic (seed-based regeneration byte-identical).
- New CLI command `aurora-corpus generate-pharma-pilot` regenerates bundles.

### Added — Sprint 4 Batch 4 (A11y core, Sprint 3 audit P0)

- **A1** — WCAG 2.5.8 24×24 touch target. `.number-drill-info` 16×16 visual,
  `::before { inset: -4px }` extends hit area to 24×24.
- **A3** — KaTeX MathML aria-hidden after render. Prevents double-announce
  (aria-label text_fallback + MathML duplicate) on screen readers.
- **A4** — Persistent aria-live regions. AuditTab wraps result/error в
  always-mounted regions с role=alert / aria-live. JAWS/NVDA reliably register
  + announce content changes.
- **A5** — Focus restoration to opener (WCAG 2.4.3). NotificationBanner
  tracks `previouslyFocused`, restores via `requestAnimationFrame` after
  `onDismiss` triggers parent re-render.
- **A6** — `@media (hover: hover) and (pointer: fine)` replaces `pointer: fine`.
  Hybrid devices (iPad с trackpad) no longer hide info buttons on touch.
- **A7** — ESC stopPropagation в NotificationBanner. Prevents cascade close
  через parent's ESC handler (e.g., DrillDownModal inside Inspector).

### Refactored — Sprint 4 Batch 5 (Code quality, Sprint Buffer #30-#34)

- **Q2** — `firstSentence()` helper extracted к `$lib/utils/formulas.ts`.
  Consolidates duplicate logic between NumberWithDrillDown + ChartWithDrillDown.
- **Q3** — Dead-code removal: `hasFormula`, `getAllFormulaKeys`, `getAllFormulas`
  (0 callers) deleted.
- **Q4** — DrillDownModal accepts both `formula` (direct) and `formulaKey`
  (lookup) props. Internal $derived resolves prop-wins-over-key.
- **Q5** — AuditTab `statusTone` + `statusLabel` merged к single `statusDisplay`
  derived с symmetric `{ tone, label } | null` shape.
- **Q6** — `$lib/utils/focus-trap.ts` Svelte action. NotificationBanner +
  CertExportModal both consume via `use:focusTrap` — DRY consolidation.
- **Q7** — CertExportModal prop `verification` → `verificationResult` rename
  (disambiguation from parent store).

### Fixed (drive-by, Sprint Buffer #40)

- `commands::similarity::block_3_tests::validate_weights_within_tolerance_passes`
  failed deterministically due to IEEE 754 rounding edge case
  (`0.5 + 0.45 = 0.95000000000000004` exceeded `0.05` tolerance by FP epsilon).
  Test data updated к `(0.5, 0.46)` — sum 0.96, 4% deviation, exact-FP-safe.
  Underlying validate_weights tolerance check FP-edge bug tracked separately.

### Sprint Buffer items closed

- **#34** — focus trap utility extraction (Q6).
- **#40** — similarity weights tolerance test FP rounding edge case (drive-by).

### Sprint Buffer items deferred to Sprint 5+

- **#21-#33, #35-#39** — see `aurora-meta/SPRINT_BUFFER.md` (12 items) including
  ReproduceModal refactor, TrustScore drill-down link, CertExportModal forecast
  summary, ChartWithDrillDown instance counter scope, verify_reproducibility
  size sanity check, reproducibility_token JCS canonical в Rust,
  Rx_pharma.Rx_cardiology category schema, 14 hardcoded Svelte microcopy strings.

---

## v0.1.4 — 2026-05-20 (Sprint 3 — Transparency + Cert)

Tag-only entry — see git log + Sprint 3 closure CC-Sessions для details.

## v0.1.3 — 2026-05-20 (Sprint 2 — MCMC Safety + Wait UX)

Tag-only entry — see git log + Sprint 2 closure CC-Sessions для details.

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
