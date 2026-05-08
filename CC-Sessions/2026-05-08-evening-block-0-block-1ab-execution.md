# CC Session — 2026-05-08 evening — Block 0 + 1A + 1B execution

**Duration:** ~5-6h
**Models used:** Opus 4.7 (1M context, max effort) для планирования + Sonnet 4.6 medium для Block 0 + Opus 4.7 medium для Block 1A/1B
**Outcome:** ROADMAP v1.3 + AUDIT v1.2 + Block 0 + Block 1A + Block 1B all shipped

## Quick Reference

**HEAD:** `93f69c1` aurora-launch
**Branch:** `main`
**Tests:** 423 passed (was 344, +79: 50 Block 1A + 29 Block 1B)
**Lines added:** ~2950 (1838 Block 1A + 778 Block 1B + ~330 CI/CD)

## What was decided

### 1. ROADMAP v1.3 (post-audit)

User requested critical audit of v1.2 plan. Produced **37 findings** (4 BLOCKER + 9 HIGH + 7 MEDIUM + 12 PREMIUM UX + 5 TRUST). Applied all → ROADMAP v1.3.

Major architectural revisions:
- **WASM removed from Tauri desktop scope** (architectural confusion fix B1) — native Rust IPC verification instead. Web verifier WASM defer to v0.1.1.
- **Phase A C2 adapters moved off critical path** — Block 4, parallel with Final F1.
- **Premium UX (12 components) moved into Block 2** — was deferred to B6.
- **Block 0 NEW** — CI/CD foundation + cert procurement parallel start.
- **Calendar 6-8 weeks → 7-9 weeks realistic** with slip buffer.

### 2. Cert procurement: deferred to Final F2b

Юрлицо ещё не зарегистрировано. Пилот идёт без OS code signing:
- Windows: NSIS unsigned → SmartScreen warning, 2 клика обхода. Installation Guide PDF.
- macOS: ad-hoc подпись (`codesign --sign -`, без Apple ID) → unidentified developer, 3 клика обхода.
- Tauri update signing: ed25519 self-generated (без юрлица).
- F2b (Authenticode + Apple Developer) — после регистрации юрлица. Блокирует **GA публичный релиз, не пилот**.

### 3. Model usage strategy (per block)

| Block | Model | Reason |
|---|---|---|
| Planning / audit | Opus 4.7 max | Critical thinking, fresh-eyes red-team |
| Block 0 (CI/CD) | Sonnet 4.6 medium | Mechanical YAML, well-known patterns |
| Block 1A (foundation) | Opus 4.7 medium | Concurrency reasoning, atomic write, locking |
| Block 1B (license) | Opus 4.7 medium | Decided to keep — integration with crypto/platform-core |
| Block 2 (frontend) | Opus 4.7 medium | Design decisions; mechanical write phase OK |
| Block 3 (audit) | **Opus 4.7 max** | **Critical — last quality gate before pilot** |
| Block 4 (adapters) | Sonnet 4.6 medium | Wiring existing things |
| Final | Sonnet (deploy) / Opus (pilot bugs) | Mixed |

## What was shipped

### Block 0: CI/CD foundation (HEAD `28e05d3`)

- `.github/workflows/ci.yml` v2 — separate lint/test/corpus jobs, macOS in matrix (was Ubuntu+Win), concurrency cancel-in-progress, cache-dependency-glob
- `.github/workflows/release.yml` NEW — tag `v*` triggers: version/tag parity check + full test on 3 platforms + GitHub Release with CHANGELOG extract. Tauri matrix stubbed `TODO(block-2)`.
- `.pre-commit-config.yaml` NEW — ruff format+check, trailing-whitespace, yaml/toml/json check, no-commit-to-branch main, mypy. Rust hooks stubbed.
- `.github/dependabot.yml` NEW — weekly pip + github-actions. Cargo stubbed.

### Block 1A: Real `.aurora` ZIP container (HEAD `82898d0`)

**4 new modules + 1 CLI + 50 tests:**

- `engines/bundle_lock.py` — cross-platform advisory file lock (POSIX `fcntl.flock` / Windows `msvcrt.locking`), sidecar `.aurora.lock`, PID write for diagnostics, `BundleLockError` on contention.
- `engines/bundle_manifest.py` — `BundleManifest` Pydantic v2 model per ADR-002. Frozen + extra=forbid. JCS RFC 8785 canonical serialization (rfc8785). Composite bundle hash with **length-prefix encoding** for R8 closure (no '|' separator collision). Revision counter for optimistic concurrency. `with_revision_bump()` immutable update pattern.
- `engines/bundle_container.py` — `BundleZipWriter` + `BundleZipReader`. Format auto-detection (ZIP magic vs JSON `{`). Backwards-compat: legacy `.aurora.json` reads via synthesized manifest. Atomic write via existing `atomic_write_bundle` (rolling backups .bak.1..bak.4). Optimistic concurrency: `BundleConflictError` if disk revision drifted. **Strict integrity check**: detects tampered/missing/extra files (per Phase A audit C3 fix). **Zip-slip defense**: rejects `/`, `..`, drive letters.
- `tools/migrate_bundle.py` — `aurora-launch-migrate-bundle` CLI. Single-file or batch (`--input-dir`). Dry-run mode. Always creates `.migrate-bak` before write. Validates by reading back + verifying composite hash. Atomic temp+rename, rollback on any failure.

**Tests:** BundleManifest semantics, format detection, round-trip writer↔reader, integrity (tamper/missing/extra), zip-slip rejection, backwards-compat legacy reads, optimistic concurrency, file locking, migration tool plan/dry-run/real/preserve.

**Bug found and fixed during smoke testing:** `from_loaded()` was copying old `manifest.json` into `_files`, causing duplicate ZIP entry warning AND silent revision rollback (writer's fresh manifest with rev=N overwritten by old one with rev=N-1). Fix: skip `MANIFEST_FILENAME` in `from_loaded()`.

### Block 1B: License integration (HEAD `93f69c1`)

**2 new modules + 1 CLI + 29 tests:**

- `engines/license_validator.py` — `LaunchLicenseValidator` thin sync wrapper around `aurora_common.license.LicenseSDK` (Phase A). Three modes:
  - **Platform mode** (HAS_PLATFORM_CORE=True): real Ed25519 JWT verification + 7-day offline grace.
  - **Degraded mode** (aurora_common not installed): fail-closed on every gate.
  - **Dev bypass** (`AURORA_LAUNCH_LICENSE_BYPASS=1`): grants all for iteration.
  - Feature constants: `FEATURE_LAUNCH_PROXY_SINGLE` (trial+), `FEATURE_LAUNCH_PROXY_MULTI` (Pro+), `FEATURE_METHODOLOGY_CERT`, `FEATURE_WHITE_LABEL`.
  - `LicenseStatus.has_feature()` / `.require()` / `.is_usable` value semantics.
- `tools/validate_license_cli.py` — `aurora-launch-validate-license` diagnostic. Text or `--json`. Exit codes: 0=usable, 1=expired/invalid, 2=no license.

**Tests:** value semantics (active/grace grant, expired/invalid/no-license/degraded deny), bypass mode (truthy/falsy parsing), degraded mode (fail-closed), env construction, feature constants verified against `aurora_common.tier_matrix.ALL_FEATURES` (skipif platform-core absent).

## Changes to project planning docs

- `00_Overview/ROADMAP.md` v1.2 → v1.3 (Block 0/1/2/3/4 + Final structure).
- `04_Sprints/AUDIT_ROADMAP_v1.2.md` NEW — 37 findings with problem/impact/fix/saved-effort.

## Decisions / Lessons / Memory

**Saved memory entries:**
- `project_aurora_launch_v0_1_0_execution_plan.md` — load-bearing facts about Block 0/1/2/3/4/Final structure, calendar, premium UX baseline, pilot success metrics. **Update before next session if any of these change.**

**Implicit lessons (not yet memory-saved, candidates for future):**
- Smoke-testing during implementation catches bugs that pure unit tests miss (the duplicate `manifest.json` bug surfaced via `_read_manifest_from_zip(p).revision` print in REPL diagnostic, not in initial test design — test was added afterwards).
- Cert procurement is calendar-driven (5-10 days lead time). User confirmed deferring to Final F2b is acceptable for pilot.

## Pending — start of next session

### Immediate next: Block 1C — Memory streaming reader (~3h)

**Why:** Bundles in production can be 50-200MB (parquet history × N years). Eager-load in `BundleZipReader` (current Block 1A implementation) → fails on 8GB machines. Block 1C adds:
- Streaming reader: read manifest first (~few KB), lazy-load parquet pages on-demand
- LRU cache (configurable cap, default 512MB)
- Memory profiling integration (track peak RAM during bundle ops)

**Architecture:**
- New class `LazyLoadedBundle` in `bundle_container.py` (or separate module) that holds open `ZipFile` handle + lazily reads entries on access
- Replace `LoadedBundle.files: dict[str, bytes]` with file-like API: `loaded.open(entry) -> BinaryIO` (streaming) OR `loaded.read(entry) -> bytes` (eager, kept for simple consumers)
- `BundleZipReader.read(path, lazy=True)` flag — default lazy in production, eager в tests
- LRU cache: weak-references to recently accessed entries

**Risks to watch:**
- Open ZipFile handle must be released cleanly (context manager)
- Concurrent readers + lazy load + advisory shared lock interaction
- Performance regression for already-fast eager path (small bundles <10MB)
- Pickle deserialization assumes full bytes — may need helper to read entire entry into memory before unpickling

**Recommended model:** Opus 4.7 medium (memory management requires careful reasoning about lifetimes + handles + locks).

### Then: Block 1D — Audit gate (~3h)

Fresh-eyes red-team pass on Blocks 1A+1B+1C combined. Attack scenarios:
- Zip-slip variants (CVE-2018-1002200 pattern)
- Concurrent write race conditions
- Malicious manifest (oversized fields, recursive structures)
- License bypass attempts (env var spoofing, JWT replay)
- Lazy-load handle leaks

**Recommended model: Opus 4.7 max** (audit is critical quality gate).

### Block 1 deliverable after 1C+1D: tag `v0.1.0-alpha1`.

## Next session bootstrap commands

```bash
# Verify state
cd "D:/Docs/Aurora_Ai/Aurora Launch"
git log --oneline -10  # expect HEAD 93f69c1
python -m pytest tests/ --tb=no -q  # expect 423 passed

# Read context
cat 00_Overview/ROADMAP.md  # v1.3 plan
cat 04_Sprints/AUDIT_ROADMAP_v1.2.md  # findings
cat CC-Sessions/2026-05-08-evening-block-0-block-1ab-execution.md  # this log

# Start Block 1C
# (no skeleton yet — design first, then implement)
```

## Hand-off summary

**Status:** ahead of schedule. Block 1A estimated ~12h, took ~3-4h. Block 1B estimated ~2h, took ~1.5h. Block 0 took ~1h (foundation existed).

**On track for:** v0.1.0 GA в 7-9 weeks calendar. Block 1A+1B+0 closed in one autonomous session.

**Quality:** 423/423 tests, 0 regressions, lint clean, format applied. Three commits: `28e05d3` Block 0, `82898d0` Block 1A, `93f69c1` Block 1B (plus `9738f8c` docs/planning).

**Next session start:** Block 1C streaming reader → Block 1D audit gate → tag `v0.1.0-alpha1`.

---

**Подготовила:** Маша Маленькая (Claude Opus 4.7 / Sonnet 4.6 mixed), 2026-05-08 evening
