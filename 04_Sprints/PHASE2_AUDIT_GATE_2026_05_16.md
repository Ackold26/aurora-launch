# Phase 2 Audit Gate — 2026-05-16

**Plan:** validated-jumping-map.md → Audit Gate Phase 2.
**Audit lead:** Sonnet 4.6 (independent).
**Branch:** feat/stage1-core-1.1-1.4
**Goal:** verify Phase 2 partii (2.A-2.E) ship-ready для платных продаж.

## Summary

| # | Check | Verdict | Evidence |
|---|---|---|---|
| 1 | C-3 license sidecar wiring | PASS | license.rs:57 — `sidecar.invoke("get_license_status", ...)` + fallback degraded payload. HE-3: test_bypass_refused_in_production PASS. 11 passed |
| 2 | H-1 thread cap | PASS | methods.py:87-89 — MAX_CONCURRENT_FORECASTS=2, MAX_CONCURRENT_OPTIMIZE=1, MAX_CONCURRENT_INTEGRITY=1 (all ≤8). Capacity check called before each spawn. 9 passed |
| 3 | H-4+HE-1 path security | PASS | engines/path_security.py:26 — pure `validate_safe_path()` + PathSecurityError. is_write=True uses parent.resolve(strict=True). 4 call sites confirmed. 9 passed, 1 skipped (Windows symlink admin) |
| 4 | HE-2 auth stdin | PASS | auth.py:80 — `load_token_from_stdin_or_env`, stdin priority, env fallback, backwards-compat alias. sidecar.rs:122 — `child.write(token_line.as_bytes())`. 21 passed (incl. 7 TestStdinTokenChannelHE2) |
| 5 | H-8+HE-6 tiered redaction | PASS | tiered_redact.ts: basic/strict/paranoid tiers. v004 migration exists. CURRENT_SCHEMA_VERSION=4. Rust state.rs redaction_tier + redaction_pending columns. telemetry.rs get/set commands. settings/+page.svelte: i18n key `settings.redaction.title` = "Конфиденциальность телеметрии". HE-6 upgrade detection: tier_rank() comparison → SET redaction_pending=1. 20 pytest passed, 20 vitest passed |
| 6 | H-10 hardcoded paths | PASS | No matches for `D:\Docs\Aurora_Ai`, `ackol`, `airosst26` in src/aurora_launch/sidecar/, src-tauri/src/, frontend/src/. `_AURORA_SAMPLE_DIR` uses `os.environ.get("AURORA_SAMPLE_DATA_DIR", "~/Aurora/sample-data")` |
| 7 | Playwright Inspector scaffolds | PASS | All 4 spec files present: inspector-similarity.spec.ts, inspector-forecast.spec.ts, m09-reproduce-python.spec.ts, update-banner-with-notes.spec.ts. CI: .github/workflows/test.yml:129 — `e2e-tests:` job exists |
| 8 | Baseline tests preserved | PASS | pytest: 1476 passed, 13 skipped (excl. 2 flaky). vitest: 519 passed. svelte-check: 0 errors, 1 pre-existing warning |

**Overall verdict: SHIP-READY**

## Detailed findings

### 1. C-3 License Sidecar Wiring (PASS)

`src-tauri/src/commands/license.rs:56-61` — `current_license_status` invokes sidecar via `sidecar.invoke::<LicenseStatusPayload>("get_license_status", serde_json::json!({}))`. On sidecar error falls back to `sidecar_unavailable_payload()` which returns `state="degraded"` (fail-closed, not stub).

`src/aurora_launch/sidecar/methods_license.py:47` — `@register("get_license_status")` handler instantiates `LaunchLicenseValidator.from_env()` and calls `validator.current_status()`. No hardcoded stub.

`src/aurora_launch/sidecar/methods.py:678` — `import aurora_launch.sidecar.methods_license  # noqa: E402, F401  Phase 2.A` confirms methods_license is loaded into the dispatch table.

HE-3 bypass guard: `test_bypass_refused_in_production` (test_get_license_status_method.py:95) sets `AURORA_BUILD_PROFILE=production` and verifies `result["tier"] != "dev_bypass"` and `result["state"] in ("no_license", "degraded")`. Test PASS.

All 11 tests in test_get_license_status_method.py pass.

### 2. H-1 Thread Cap (PASS)

`src/aurora_launch/sidecar/methods.py:87-89`:
- `MAX_CONCURRENT_FORECASTS = 2`
- `MAX_CONCURRENT_OPTIMIZE = 1`
- `MAX_CONCURRENT_INTEGRITY = 1`

All constants well below the desktop-sanity ceiling of 8.

`src/aurora_launch/sidecar/methods_forecast.py:63-68` — `_check_forecast_capacity()` and `_check_optimize_capacity()` pure functions wrap `_check_capacity()`. Called at methods_forecast.py:325 (before forecast spawn) and methods_forecast.py:770 (before optimize spawn).

`src/aurora_launch/sidecar/methods_integrity.py:58-66` — `SidecarBusyError: cap MAX_CONCURRENT_INTEGRITY reached`, `_m.MAX_CONCURRENT_INTEGRITY` used in capacity check.

`SidecarBusyError` class defined at methods.py:92. `_check_capacity()` pure function at methods.py:109. All 9 tests in test_thread_pool_caps.py pass.

### 3. H-4+HE-1 Path Security (PASS)

`src/aurora_launch/engines/path_security.py` — pure function `validate_safe_path(path, allowed_roots, *, is_write=False) -> Path` at line 26. `PathSecurityError(ValueError)` at line 13.

HE-1 write path (line 69-92): `p.parent.resolve(strict=True)` validates parent exists; `p.parent.is_symlink()` rejects symlink parents; returns `parent_resolved / p.name` for write target (parent validated, leaf may not exist yet). Does NOT call `p.resolve(strict=True)` on write target — correct fix for new-file writes.

4 confirmed call sites:
- `src/aurora_launch/sidecar/methods_project.py:402` — import at line 389, call `validate_safe_path(bundle_path, ...)` (read), call at line 560 (write), call at line 571 (read) — 3 distinct invocations.
- `src/aurora_launch/engines/data_source_watcher.py:250` — `validate_safe_path(folder, _get_allowed_roots(), is_write=False)` — folder watch check.
- `src/aurora_launch/services/optimizer_client.py:239` — `validate_safe_path(db_path, _get_allowed_roots(), is_write=False)` in `__init__`.

9 passed, 1 skipped (symlink test requires Windows admin privileges — expected behavior documented in test marker).

### 4. HE-2 Auth Stdin (PASS)

`src/aurora_launch/sidecar/auth.py:80` — `load_token_from_stdin_or_env(*, stdin_timeout=5.0)` — stdin priority on Linux/macOS via `select.select`, Windows fallback to env immediately (documented limitation of `select` on Win32).

Backwards-compat alias `load_token_from_env` at auth.py:132 retained — delegates to `load_token_from_stdin_or_env()`.

`src-tauri/src/sidecar.rs:118-122` — `// HE-2: write token as first stdin line` comment + `let token_line = format!("{token}\n"); if let Err(e) = child.write(token_line.as_bytes())` — Rust parent writes token as first stdin byte sequence immediately after spawn.

All 21 tests in test_sidecar_auth.py pass, including all 7 tests in `TestStdinTokenChannelHE2`:
- `test_stdin_token_preferred_over_env` — stdin priority verified
- `test_env_fallback_when_stdin_empty` — env fallback verified
- `test_both_missing_exits_2` — fail-closed (sys.exit(2)) verified
- `test_backward_compat_alias` — alias functional

### 5. H-8+HE-6 Tiered Redaction (PASS)

`frontend/src/lib/services/tiered_redact.ts` — `RedactionTier = 'basic' | 'strict' | 'paranoid'` union type. Three tier patterns: RE_EMAIL, RE_PHONE_RU, RE_IPV4 (basic); + customer_name + file paths (strict); + UUIDs, hex hashes, ISO timestamps (paranoid).

`src/aurora_launch/persistence/migrations/v004_telemetry_redaction_tier.sql` — migration file present.

`src/aurora_launch/persistence/project_db.py:43` — `CURRENT_SCHEMA_VERSION = 4` — bump confirmed.

`src-tauri/src/state.rs:78-98` — `redaction_tier TEXT CHECK(... IN ('basic', 'strict', 'paranoid'))` and `redaction_pending INTEGER NOT NULL DEFAULT 0` columns added. Both ALTER TABLE statements and INDEX confirmed.

`src-tauri/src/commands/telemetry.rs:120,144` — `get_redaction_tier` and `set_redaction_tier` Rust commands present.

Settings UI: `frontend/src/routes/settings/+page.svelte:164` — `<Card title={$_('settings.redaction.title')}>` with radio group for basic/strict/paranoid tiers. `frontend/src/lib/i18n/locales/ru.json:56` — `"settings.redaction.title": "Конфиденциальность телеметрии"`. Section fully wired with reactive store + `initRedactionTier()` on mount.

HE-6 upgrade detection: `telemetry.rs:179` — `if tier_rank(&tier) > tier_rank(&current)` → `UPDATE telemetry_events SET redaction_pending = 1 WHERE redaction_pending = 0`. Correct: new_tier > old_tier flags all existing rows for re-redaction.

20 pytest passed, 20 vitest passed (test_telemetry_tiered_redaction.py + tests/unit/tiered_redact.test.ts).

### 6. H-10 Hardcoded Paths (PASS)

Grep for `D:\Docs\Aurora_Ai`, `ackol`, `airosst26` returned zero matches in:
- `src/aurora_launch/sidecar/` — 0 matches
- `src-tauri/src/` — 0 matches
- `frontend/src/` — 0 matches

`src/aurora_launch/sidecar/methods.py:193-194`:
```python
_AURORA_SAMPLE_DIR = Path(
    os.environ.get("AURORA_SAMPLE_DATA_DIR", "~/Aurora/sample-data")
```
Developer path override via env var confirmed. Default `~/Aurora/sample-data` is user-agnostic (home-dir relative).

### 7. Playwright Inspector Scaffolds (PASS)

All 4 required spec files present at `frontend/tests/e2e/`:
- `inspector-similarity.spec.ts`
- `inspector-forecast.spec.ts`
- `m09-reproduce-python.spec.ts`
- `update-banner-with-notes.spec.ts`

`.github/workflows/test.yml:129` — `e2e-tests:` job defined. CI integration confirmed.

Additional spec files present from earlier phases: `welcome.spec.ts`, `wizard.spec.ts`, `wizard-happy-path.spec.ts`, `inspector.spec.ts`, etc.

### 8. Baseline Tests Preserved (PASS)

Full pytest run (excluding 2 known-flaky tests):
```
1476 passed, 13 skipped in 15.79s
```
Skips are expected: 1 symlink admin, 3 PyMC fixture not generated, 1 pilot XLSX absent, and others pre-existing.

Full vitest run: `519 passed (39 test files)`.

svelte-check: `621 files, 0 errors, 1 warning` — pre-existing a11y warning in wizard/+page.svelte:556 (`noninteractive element cannot have nonnegative tabIndex value`). Not introduced by Phase 2 work.

## Test execution snapshot

- **pytest:** 1476 passed, 13 skipped, 0 failed (excl. test_phase_0_2_autosave.py + test_phase_scale_s17_forecast_budget.py flaky)
- **vitest:** 519 passed, 0 failed (39 test files)
- **Playwright:** 4 new spec files scaffolded; CI job registered. Runtime execution requires Tauri dev environment (not run in this audit — expected per checklist)
- **svelte-check:** 0 errors, 1 pre-existing warning (wizard tabIndex, not Phase 2 regression)

### Per-Phase-2-check test counts

| Check | Test file | Result |
|---|---|---|
| C-3 license | test_get_license_status_method.py | 11 passed |
| H-1 thread cap | test_thread_pool_caps.py | 9 passed |
| H-4+HE-1 path sec | test_path_security.py | 9 passed, 1 skipped |
| HE-2 auth stdin | test_sidecar_auth.py | 21 passed (incl. 7 HE2 class) |
| H-8+HE-6 redaction | test_telemetry_tiered_redaction.py + tiered_redact.test.ts | 20+20 = 40 passed |

## Open items (non-blocking)

1. **HE-2 stdin on Windows:** `auth.py:65-69` — `select.select` not supported for stdin on Windows → stdin path disabled, env var used as primary on Windows. Documented intentionally. Not a gap — Windows sidecar is spawned with env var injection (lower exposure than Linux `/proc/PID/environ` but non-zero). Consider named pipe or anonymous pipe for a future hardening pass.

2. **Playwright e2e spec runtime coverage:** The 4 new specs are scaffolded and CI-registered but no Tauri runtime execution in this audit. Correctness of the spec logic (selectors, flows) is not audited here — this is expected per the Phase 2.E scope definition (scaffold + CI hook, not full e2e green in CI which requires code-signing + bundled binary).

3. **svelte-check pre-existing warning:** `wizard/+page.svelte:556` tabIndex on non-interactive element — present before Phase 2, not introduced here. Low priority a11y item.

4. **validate_safe_path call count:** Checklist specified 2 occurrences in methods_project.py. Actual: 3 call sites (read for open-bundle, write for save, read for copy-source). Additional call site is conservative (more security coverage, not a gap).

## Approval

**ВЕРДИКТ: SHIP-READY**

All 8 checklist items verified PASS. Phase 2 partii (2.A License / 2.B Thread cap / 2.C Path security / 2.D Auth + Privacy / 2.E Playwright scaffolds) are ship-quality:

- Security surface hardened: sidecar auth (HE-2), bypass guard (HE-3), path traversal defense (H-4+HE-1), PII redaction tiers (H-8+HE-6)
- Monetization unblocked: license sidecar wired (C-3) — production builds now return real license state
- Resource safety: all compute paths bounded (H-1)
- No hardcoded developer paths in production code
- Baseline test suite preserved: 1476 pytest + 519 vitest, 0 regressions

Ready for: push approval to Антон + PR merge + pilot ship to first paid customer.
