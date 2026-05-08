# Full-Project Critical Audit — 2026-05-09

**Auditor:** Маша Маленькая (Claude Opus 4.7 max effort)
**Methodology:** parallel reconnaissance via 3 Explore-агентов over неаудированную часть после Block 1D, followed by mandatory **personal verification** of every claimed finding before applying any fix. False positives explicitly documented и rejected.
**Pre-audit state:** HEAD `f4ea549`, tag `v0.1.0-alpha1`, 485 tests passing
**Post-audit state:** HEAD TBD, 510 tests passing
**Outcome:** 4 HIGH applied + 3 MEDIUM applied + 8 false positives explicitly rejected with reasoning. 5 LOW/MEDIUM deferred with owners.

## Why this audit

Antоn asked: "сделай его идеальным, найди скрытые ошибки до их проявления." Block 1D covered storage / lock / persistence / manifest / streaming / license. ~3 000 LoC of math, schemas, format adapters, CLI tools, customer success, corpus generator remained unaudited.

## Methodology

1. **Code inventory** (lines, modules, sub-packages) executed first.
2. **Parallel Explore agents** — three concurrent reconnaissance agents с distinct briefs (math/forecasting; schemas+adapters; CLI+tracker+corpus). Each told to NOT fabricate findings, отмечать `needs verification` for unclear cases.
3. **Personal verification** — every claimed finding read in context. Mathematical claims checked against Tibshirani 2019 (conformal) и Bayesian first principles (variance ratio). Adapter collisions tested with concrete example filenames. Path-traversal claims evaluated for trust model (desktop CLI vs hosted service).
4. **Apply only verified findings.** Document false positives с reasoning.

## Verified findings — applied

### 🟠 HIGH-1: Pydantic schemas без `model_config` (silent unknown field acceptance)

**File:** `src/aurora_launch/schemas/proxy.py`

`ProxyEntry`, `SimilarityDimensionScores`, `AnonymizationDetails`, `ProxyBrandMetadata` все наследовали Pydantic defaults — `extra="ignore"`. Это означает:

- `ProxyEntry(..., admin_override=True)` silently accepts and drops the field.
- Inconsistent with rest of codebase (forecast.py / adaptation.py / posterior_update.py / bundle.py все используют `frozen=True, extra="forbid"`).
- Defence-in-depth concern для bundle ingestion: an attacker bundle с extra fields не вызывает validation failure — just silent drop.

**Fix:** introduced shared `_FROZEN_CONFIG = ConfigDict(frozen=True, extra="forbid")`, applied to all four classes. Also added `weights_sum_to_unity_if_present` model_validator to `SimilarityDimensionScores` (если weights_used non-empty, must sum к ~1.0 ±0.05 — was previously unvalidated).

### 🟠 HIGH-2: DSM V2024 adapter ловит V2023/V2025 файлы (version collision)

**File:** `src/aurora_launch/engines/format_adapters/dsm_v2024.py`

V2024 detection: `path.suffix == ".xlsx" and ".dsm" in name_lower → True`. Файлы вида `data.dsm.2023.xlsx` (V2023 glob `*.dsm.2023.xlsx`) проходят V2024's substring check. Registry order has V2024 last (highest priority в reverse iteration), поэтому V2024 wins — V2023 файл silently parsed как V2024. V2024 expects ISO date + semicolon; V2023 has DD.MM.YYYY + comma → parse silently produces garbage records.

Header sniff также не помогает — V2024 sniffer accepted any `;`-separated header containing `Бренд` или `Дата`, не различая V2023's `Дата_продажи` column.

**Fix:**
1. V2024.detect() explicitly rejects file names containing year markers `2023` или `2025` (when combined с "dsm" в имени).
2. CSV header sniff требует semicolon separator AND V2024 field marker AND absence of V2023's distinct `Дата_продажи` column.
3. Added test `test_v2024_rejects_2023_marker_in_xlsx` + registry dispatch verification.

### 🟠 HIGH-3: Format adapters читали весь файл в memory без cap

**Files:** все adapters в `src/aurora_launch/engines/format_adapters/*.py`

Pattern везде: `lines = [line.strip() for line in f if line.strip()]` — full materialisation. На 5GB malicious CSV → OOM kill. Aurora Launch consumes proxy data из customer-supplied files в pilot deployment — trust boundary is real.

**Fix:** new module-level `MAX_INPUT_FILE_BYTES = 256 * 1024 * 1024` (256 MB — far above any legitimate DSM/Mediascope export; annual TV index ≈10 MB) + `assert_file_size_ok()` helper + `FormatAdapterFileTooLarge` exception. Every built-in adapter calls helper before opening. Test coverage: `TestAdapterFileSizeCap` (4 tests).

### 🟠 HIGH-4: `migrate_bundle` silently overwrites existing target

**File:** `src/aurora_launch/tools/migrate_bundle.py`

`os.replace(tmp_path, plan.target)` is unconditional. Если customer accidentally runs `aurora-launch-migrate-bundle bundle.aurora.json` дважды — first run produces `bundle.aurora` ZIP, second run overwrites that ZIP с newly migrated content (which is identical, but **target is silently replaced**). More importantly: if target was hand-edited between runs, that edit silently lost. Backup is created of source (`.migrate-bak`), not target.

**Fix:** added `--force` CLI flag. `_migrate_one()` checks `plan.target != plan.source and plan.target.exists() and not force` → prints refusal с suggested `--force` flag and returns False. Default behaviour = safe-by-default. Test coverage: 3 tests включая overwrite-with-force happy path.

### 🟡 MEDIUM-1: `last_modified` comment в `compute_update_estimate` инвертирован

**File:** `src/aurora_launch/engines/launch_posterior_update.py:323`

Original comment: `σ_after / σ_before ≈ √(w_proxy_before / w_proxy_after) для recipient std`. Code computed `sqrt(new_weights.w_proxy / current_pooling.w_proxy)` — that is `sqrt(w_after / w_before)`, not `sqrt(w_before / w_after)`.

**Verification:** derivation from first principles. With `n_eff ∝ 1/w_proxy` (more recipient data → w_proxy shrinks) и σ ∝ 1/√n_eff → σ ∝ √w_proxy. Therefore `σ_after / σ_before ≈ √(w_after / w_before)`. **Code is correct;** только comment was inverted, misleading any future maintainer (and the audit agent itself was confused into reporting it as a math bug).

**Fix:** comment rewritten с full derivation, marked as audit-driven correction.

### 🟡 MEDIUM-2: NaN propagation в `determine_verdict` silently routes к "Insufficient"

**File:** `src/aurora_launch/engines/similarity_calculator.py`

`if score >= VERDICT_THRESHOLDS["High"]: return "High"` — NaN comparison via `>=` is always False, so NaN scores fell through to "Insufficient". This masks upstream computation errors as "low similarity" which is incorrect feedback for users.

**Fix:** explicit `math.isfinite(score)` check at top — non-finite raises `ValueError` с diagnostic message pointing к `compute_aggregate_score` upstream. Test coverage: 5 tests (NaN/+Inf/-Inf rejected, normal scores unchanged, boundaries unchanged).

### 🟡 MEDIUM-3: Posterior update diagnostics labeled as real numbers

**File:** `src/aurora_launch/engines/launch_posterior_update.py:445-449`

Output payload returned `"diagnostics": {"gelman_rubin_max": 1.02, "ess_min": 850, "divergent_transitions_count": 0}`. These are **placeholder constants** — real MCMC diagnostics will be wired в B5.2 после PyMC fit integration. UI dashboards consuming this payload would show fake convergence metrics to users.

**Fix:** renamed key to `diagnostics_stub`, prefixed every metric с `_stub_`, added `_note` field referencing B5.2 sprint.

## Verified false positives — rejected

For methodology integrity, I list each finding agents reported but **rejected after personal verification**, с reasoning. Future audits should not re-litigate these:

### ❌ FP-1: "Conformal quantile off-by-one — should use `1-coverage`"

**Reasoning:** Tibshirani 2019 split conformal: для (1-α) coverage, quantile index is ⌈(n+1)·(1-α)⌉ smallest residual. Code uses `coverage_target` directly (which IS 1-α, e.g., 0.95). For n=100 coverage=0.95: `ceil(101 × 0.95) - 1 = 95` (0-indexed) = 96th smallest = 95th percentile of residuals. Correct.

Agent confused α (miscoverage rate) с coverage (1-α). Reading the code's own comment "ceil((n+1) × coverage) / n" matches Tibshirani convention. **Code correct as-is.**

### ❌ FP-2: "Bayesian variance ratio inverted — `tightening` reversed"

**Reasoning:** see MEDIUM-1 above. Code direction is correct; comment was misleading. Agent followed comment, not derivation.

### ❌ FP-3: "Drift detection silent truncation via `strict=False`"

**File:** `launch_posterior_update.py:208-211`

Agent claimed `zip(forecast[:n_weeks], actual[:n_weeks], strict=False)` silently truncates. **But** `n_weeks = min(len(...), len(...))` is computed two lines above; both slices are exactly `n_weeks` long. `strict=False` is harmless when slices are equal-length by construction. Agent did not read scope.

### ❌ FP-4: "Path traversal в CLI tools (migrate_bundle, export_typescript, corpus_cli)"

**Reasoning:** Aurora Launch CLI tools are local desktop tools invoked by the operator on their own filesystem. The trust boundary is the OS user account. A user-invoked CLI passing `../../etc/passwd` operates с user-level permissions on user-readable files — это **expected behaviour**, not a vulnerability. Path traversal applies to network services receiving paths from untrusted clients, not to local desktop CLIs.

If Aurora ever exposes these CLIs through a network MCP server или web GUI accepting paths from remote users, traversal protection becomes load-bearing. For Phase B (desktop pilot): not applicable.

### ❌ FP-5: "PII в CSV billing export должно быть redacted"

**File:** `customer_success/tracker.py:240-280`

Agent suggested regex-based redaction of `notes` field for `api_key=`, `token=`, etc. **But:** `notes` is a user-provided free text field in their own consulting log, exported by the customer for their own billing. Aurora doesn't auto-log API keys; the customer chose what to type. Adding heuristic redaction creates false positives on legitimate "key=value" notes (e.g., "renewal_key=Q3-2026", "category_key=FMCG"). CSV-injection защита via apostrophe prefix is separate concern и уже implemented.

### ❌ FP-6: "tracker singleton race condition"

**Reasoning:** `_default_tracker` is module-level, but `log_event(db_path=None)` raises `RuntimeError` если not initialized. Initialization is caller's responsibility. SQLite connections opened per-call (not pooled) — safe for concurrent reads. Aurora is single-user Phase B desktop app. Phase D (multi-user web service) would need per-request scoping; not applicable now.

### ❌ FP-7: "synthesis category table missing 7 entries"

**File:** `engines/corpus_generator/synthesis.py:35-57`

Agent claimed 12 entries in table vs 14 в `CategoryL3` Literal. **Personal count:** 14 entries в table (FMCG_food.snacks_savoury, FMCG_food.snacks_sweet, FMCG_food.dairy_yogurt, FMCG_beverage.beverage_carbonated, FMCG_beverage.beverage_juice, FMCG_beverage.beverage_energy, OTC_pharma.OTC_cold_flu, OTC_pharma.OTC_pain, Cosmetics.skincare_premium, Cosmetics.haircare_premium, Telecom.telecom_b2c_mobile, Banking.banking_retail, awareness.brand_awareness_only, cross_category.cross_l1_edge). All 14 covered. Agent miscounted.

### ❌ FP-8: "corpus_cli --n-weeks lacks validation, OOM possible"

**Reasoning:** `SyntheticProjectSpec.n_weeks: int = Field(ge=104, le=312)` — Pydantic validation fires on `spec = SyntheticProjectSpec(...)` line 93 of corpus_cli.py. Out-of-range values rejected with ValidationError before generation. UX could be friendlier (click-level error vs Pydantic stack trace), но not a security/correctness bug. Reclassified as LOW (UX polish).

## Deferred — MEDIUM/LOW (documented, not applied this cycle)

| ID | Severity | Issue | Owner | Target |
|---|---|---|---|---|
| D1 | MEDIUM | `_verified_entries` set unbounded growth (Block 1C) | Block 4 | Hardening pass |
| D2 | MEDIUM | License validator uses private SDK methods `_read_cache`, `_verify_jwt` | Coordinate aurora-platform-core | Phase B+ |
| D3 | MEDIUM | Format adapters return strings без type coercion (downstream contract) | Block 4 | Hardening pass |
| D4 | LOW | corpus_cli error messages on out-of-range params (Pydantic stack traces) | Block 2 UX | Block 2 frontend |
| D5 | LOW | Zip-slip `:` check overly aggressive on POSIX | Block 4 | Hardening pass |

## Test coverage

| Suite | Pre-audit | Post-audit | Δ |
|---|---|---|---|
| Block 1A bundle_container | 50 | 50 | — |
| Block 1B license_validator | 29 | 29 | — |
| Block 1C bundle_streaming | 62 | 62 | — |
| Block 1D + extended fixes | 16 | 41 | **+25** |
| Other (B1-B5, format, corpus, schemas, integration) | 328 | 328 | — |
| **Total** | **485** | **510** | **+25** |

Zero regressions через всю audit pass. Все existing tests pass after schema upgrades (frozen + extra=forbid) — это шок-тест: existing callers не передавали unknown fields, и ничего не depends on mutation post-construction. Schemas were already-clean внутренне; fix only sealed the external contract.

## "Make it perfect" — strategic suggestions (not applied; для дискуссии)

Ниже — observations не для immediate action, а как design-level recommendations при движении к v0.1.0 GA. Антону на review.

1. **Centralise schema config.** Каждый module сейчас определяет свой `_FROZEN_CONFIG = ConfigDict(...)`. Вынести в `aurora_launch.schemas._base` как `IMMUTABLE_FROZEN_CONFIG` константу; импортировать везде. Снижает risk нового schema без model_config.

2. **Numeric output stability.** `tightening_pct = max(0.0, ...)` clamping безопасно но тихо скрывает bugs (negative tightening = инверсия direction = upstream bug). Рассмотреть logging warning при clamp-event в DEBUG mode.

3. **Format adapter Protocol enforcement.** `ProxyDataSource` Protocol — но adapters не подписаны на Protocol явно (нет `class DsmAdapterV2024(ProxyDataSource):`). Mypy не проверит. Mark: `class DsmAdapterV2024(ProxyDataSource):` или add runtime check в `AdapterRegistry.register()`.

4. **CLI tools' tests use full migration.** `test_audit_extended_fixes.py::test_migrate_with_force_overwrites_target` runs full ZIP write/read/verify cycle. На большом suite — minor slowdown. Phase B+: split adapter unit tests из integration tests.

5. **Composite hash includes integrity_check setting via manifest.** Already true (manifest_sha256 включает все fields); but не явно tested. Add property-based test.

6. **License bypass: убрать вообще для production.** B1 fix gates через `AURORA_BUILD_PROFILE=dev`, but ideal is **compile-time elimination**: production builds не include the bypass code path. Tauri build.rs + Python conditional import. Currently bypass is feature-flag-gated; ideal is dead-code-eliminated.

7. **Audit findings repository.** This is the second comprehensive audit (Block 1D + this one). Patterns are emerging: silent unknown fields, missing input caps, version markers in adapter detection. Consider an `AUDIT_PATTERNS.md` listing recurring issue classes — checklist for new code review.

8. **Mathematical correctness regression tests.** Conformal coverage test — generate synthetic data с known coverage, verify intervals achieve ≥95% empirical coverage on 1000 trajectories. Currently tested for edge cases (n=1, empty); not for statistical correctness. Property-based с `hypothesis` would catch directional bugs (e.g., если кто-то flip the formula).

9. **Type hints на public API.** Several `Any` returns в handlers; tightening to specific TypedDict / Pydantic models would catch contract drift at type-check time. Currently relies on runtime testing.

10. **Documentation: `make it perfect` checklist.** Each module's docstring could include "**Trust boundary**: ...", "**Threading**: ...", "**Failure modes**: ..." sections. Currently scattered across feature docstrings.

## Release gate

✅ All HIGH findings fixed and tested.
✅ All applied MEDIUM fixes tested.
✅ False positives explicitly rejected с reasoning.
🟡 Deferred items have owners + target windows.

Tag bumped: **`v0.1.0-alpha2`** reflects post-audit state. Backend production-grade pending Block 2 frontend integration.

**Next step:** Block 2 frontend ship per ROADMAP v1.3, with audit-derived prerequisites carried forward.
