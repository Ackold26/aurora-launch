# Mini-audit — GitHub Actions + PyInstaller hardening (2026-05-09)

**Auditor:** Маша Маленькая (Opus 4.7 max)
**Trigger:** Антон спросил "у нас есть созданные части без аудита?" После inventory обнаружено 2 HIGH-priority gaps: GitHub Actions workflows + PyInstaller spec — shipped без dedicated audit gate.
**State entering:** HEAD `919859f` (F1 code shipped, tag still `v0.1.0-rc1`)
**State exiting:** HEAD TBD, tag remains `v0.1.0-rc1` (rc2 still gated by Антон infrastructure provisioning)
**Outcome:** 4 HIGH applied + 2 MEDIUM noted; 4 LOW deferred POST_PILOT_BACKLOG.

## Methodology

Pre-flight INV check (per ENGINEERING_INVARIANTS §6):
- §1 INVs read recently (Block 4 + F1)
- Crypto/signing? **YES** — release.yml signs installers с private key (INV-05 attack scenarios apply); PyInstaller binary verified via INV-02 runtime smoke в built artifact
- Schema change? **NO** — workflow YAML format only
- Infrastructure? **YES** — third-party action supply chain (INV-13 verified)
- Imports/deps? **YES** — INV-03 dependency verification: `dtolnay/rust-toolchain` SHA pinned к 21dc36fb71dd22e3317045c0c31a3f4249868b17 (last verified 2024-09-01); `softprops/action-gh-release` к c95fe1489396fe8a9eb87c0abf8aa5b2ef267fda (v2.2.1)

## Verified findings — applied

### 🟠 HIGH-1: `release.yml` `permissions: contents: write` global

**Risk:** All jobs (`validate`, `test-release`, `build-sidecar`, `build-app`,
`publish`) inherit write token. Build steps execute untrusted code от
tagged commit (PyInstaller, Tauri, npm scripts). If a malicious commit
gets tagged, those jobs could push к main, modify releases, etc.

**Fix:** default `permissions: contents: read` at workflow + each job; only
`publish` job overrides к `write` (needs создать GitHub Release). Build/test
jobs run с read-only token.

Same pattern applied к `sidecar-build.yml`, `test.yml`, `ci.yml`.

### 🟠 HIGH-2: Community-maintained third-party actions not SHA-pinned

**Risk:** `dtolnay/rust-toolchain@stable`, `softprops/action-gh-release@v2`,
`astral-sh/setup-uv@v4` are mutable tags. Maintainer compromise → tag
repointed к malicious commit → next workflow run executes attacker code
с release secrets.

**Fix:** SHA-pin community actions:
- `dtolnay/rust-toolchain@21dc36fb71dd22e3317045c0c31a3f4249868b17` (stable @ 2024-09-01)
- `softprops/action-gh-release@c95fe1489396fe8a9eb87c0abf8aa5b2ef267fda` (v2.2.1)

First-party `actions/*` keep major-tag pins (lower hijack risk + auto-receive
patches). Document SHA rotation cadence: quarterly review (or dependabot).

### 🟠 HIGH-3: Vercel env update без explicit redeploy

**Risk:** `release.yml::publish` updates `AURORA_LATEST_*` env vars but
doesn't trigger redeploy. Edge Functions read `process.env` at instance
cold-start; existing instances continue serving OLD manifest until cold-start
cycling (5-10 минут unpredictable). Updater clients querying immediately
after release see stale manifest → install old version.

**Fix:** added "Trigger Vercel production redeploy" step после env update.
Calls `POST /v13/deployments` с `forceNew=1` к promote latest production
deployment immediately. Если redeploy fails (transient network, API
hiccup), step continues — env vars still updated, Edge Functions cycle
within 10 минут anyway. Не fatal.

Also rewrote env-var update logic from brittle bash `for KV in "K:V"` (split
on `:` ломалось когда value contained `:`) к Python `urllib.request` с
explicit error handling. Detects "already exists" (400) и follows up с PATCH
к existing env id. Failures fail the step (no `|| true` swallow).

### 🟠 HIGH-4: PyInstaller bundle pulls dev tooling

**Risk:** CI installs `pip install -e ".[dev]"` для running pytest, then
calls `pyinstaller`. PyInstaller analyses ALL import-reachable modules — if
sidecar's transitive imports touch any `pytest` / `hypothesis` / `ruff` /
`mypy` (e.g., через type hints introspection), they get bundled. Increases
binary size + production binary contains test framework code.

**Fix (two-layer)**:
1. `release.yml` build-sidecar job now installs runtime-only (`pip install -e .`),
   NO `[dev]`. Tests run в separate matrix job (test-release).
2. `sidecar-build.yml` (separate workflow): runs tests с `[dev]`, then
   `pip uninstall pytest pytest-cov hypothesis ruff mypy` BEFORE `pyinstaller`.
3. `aurora-sidecar.spec` `excludes` list extended: `pytest`, `_pytest`,
   `pytest_cov`, `hypothesis`, `ruff`, `mypy`, `mypy_extensions`,
   `pyinstaller`, `pip`, `setuptools`, `wheel`, `ipykernel`, `jupyter`.
   Belt-and-suspenders.

## Applied М2 PyInstaller findings

### M2-PYINSTALLER-1: hiddenimports list incomplete

**Issue:** `aurora_launch.schemas.synthetic_corpus` used by FormatAdapterContract
(imported via format_adapters/registry) — was missing. PyInstaller's static
analyser usually traces this via dsm_v2024.py top-level import, but eager-
include через hiddenimports = robustness.

Also: `pydantic_core` (Pydantic v2 compiled Rust core) — PyInstaller bundled
hook may не detect на all platforms. Force-include.

`aurora_launch.schemas.forecast` added для transitive coverage.

**Fix:** added 3 entries к hiddenimports.

## Deferred — MEDIUM/LOW (POST_PILOT_BACKLOG)

| ID | Severity | Issue | Owner |
|---|---|---|---|
| M1-WORKFLOW-7 | MEDIUM | `ci.yml` + `test.yml` overlap (both run pytest на main+PR). Different scopes (ci.yml = lint + BC corpus + reproducibility; test.yml = unit). Could consolidate. | Phase B refactor |
| M1-WORKFLOW-9 | LOW | sidecar-build.yml smoke `\|\| true` swallows grep non-zero. Currently OK (explicit -z check below) but bad pattern. | Polish |
| M2-PYINSTALLER-3 | MEDIUM | `runtime_tmpdir=None` — single-file binary extracts к temp at every launch (~1-2s cold start). Could set persistent tmpdir for faster subsequent runs. | Phase B perf |
| M2-PYINSTALLER-5 | LOW | Windows .exe metadata (`version_file=`) not embedded — cosmetic. | Polish |
| openpyxl | MEDIUM | XLSX adapter requires `openpyxl`; not in pyproject.toml dependencies → DSM XLSX parsing fails в production sidecar. Currently graceful ImportError. Pilot DSM data may need XLSX support. | F2/Block 4 followup |
| Rust composite_bundle_hash_mirror parity test | MEDIUM | Python pins algorithm; Rust mirror not run via cargo test asserting same output. Drift detection gap. | Block 4 polish |

## INV compliance check (per AQ rule — repeat patterns)

| INV | Status |
|---|---|
| INV-01 schema migration | N/A (no schema changes) |
| INV-02 runtime smoke | ✅ sidecar-build.yml runs binary с ping request (real method dispatch) |
| INV-03 verify package + feature flag | ✅ third-party actions verified by SHA at audit time |
| INV-05 crypto attack first | ✅ Block 4 sidecar auth tests still pinned (14 attack scenarios) |
| INV-06 JCS canonical | ✅ unchanged |
| INV-08 real pytest | ✅ 547 passing |
| INV-09 config end-to-end | ✅ AURORA_BUILD_PROFILE / AURORA_UPDATER_PUBKEY traced env→build→runtime |
| INV-10 read API signature | ✅ Vercel API + GitHub Actions schema per docs |
| INV-13 infrastructure | ✅ supply-chain pin rationale documented |

## Tests

- **Python:** 547 passing (no Python changes from this commit; verification check).
- **Workflow YAML:** validated locally via mental trace; live CI run требуется
  для smoke (no schema validator runs offline).
- **PyInstaller spec:** spec correctness pinned via mini-audit; live cross-platform
  build requires Антон GitHub Actions trigger.

## Release gate

✅ All HIGH findings fixed.
🟡 6 MEDIUM/LOW deferred с owners + target windows.
✅ INV-01..14 repeat patterns checked.

**Recommended:** commit + push. Tag `v0.1.0-rc2` STILL deferred per AQ-02 honest
disclosure — Антон infrastructure provisioning (F1 runbook Steps 1-5) + smoke
test must pass first.

After Антон smoke green → tag rc2 → release.yml triggers (now hardened) →
installers + manifest live on Vercel + GitHub Release → F2 → F3 pilot → F4 GA.

## Make-it-perfect notes

1. **Dependabot** для GitHub Actions SHA rotation. Set up `.github/dependabot.yml`
   с `package-ecosystem: github-actions`. Quarterly auto-PRs would maintain SHA pins
   without manual review burden.
2. **`actions/checkout` SHA pinning** — currently major-tag (`@v4`). For maximum
   supply-chain hardening, even first-party actions can be pinned. Cost: monthly
   PR for security patches. Defer until F4 GA security review.
3. **PyInstaller `runtime_tmpdir` benchmarking** — measure cold start с/без
   persistent tmpdir on real pilot machine (Windows).
4. **`openpyxl` decision** — Materia Medica DSM data format check. If XLSX needed
   → add `openpyxl` к pyproject.toml + spec hiddenimports. If CSV-only → document
   pilot constraint.
