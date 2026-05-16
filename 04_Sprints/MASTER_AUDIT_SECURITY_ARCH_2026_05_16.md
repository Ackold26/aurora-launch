# MASTER AUDIT: Security + Architecture + Engineering Quality
## Aurora Launch Planner — 2026-05-16
### Branch: `feat/stage1-core-1.1-1.4` | HEAD: `21e693e` | 18 autonomous commits

**Audit team (roles):** Security Engineer | Staff Software Architect | QA Lead | Engineering Manager  
**Scope:** Stages 1–4 autonomous session work.  
**Existing audits excluded:** `AUDIT_BLOCK_1ABCD.md`, `AUDIT_BLOCK_2_FRONTEND.md`, `STAGE3_4_FINAL_AUDIT_2026_05_16.md` — findings therein are not re-listed.  
**Standard:** World-class / category-defining B2B desktop SaaS.

---

## 1. Executive Summary

Aurora Launch Planner demonstrates **unusually high security consciousness for a 0.1.x product**. The auth-token design for sidecar IPC is genuinely correct (CSPRNG + hmac.compare_digest + env-var isolation + hex validation), and the license bypass gate using compile-time embedding is architecturally sound. These are strong foundations.

The three critical concerns that must be addressed before any sustained pilot:

1. **CRITICAL — Unbounded Forecast Thread Pool** (`methods.py`): `start_forecast` and `optimize_budget` register threads in module-level dicts with no concurrency cap. A malicious or confused user (or a UI bug causing rapid re-submit) can spawn hundreds of PyMC/NumPy threads, exhausting RAM and degrading or crashing the sidecar with no recovery path.

2. **HIGH — Symlink Attack Surface on File Paths** (`DataSourceWatcher`, `import_aurora_bundle`, `save_bundle target_path`, `LocalOptimizerClient`): No `Path.resolve()` call before file operations on customer-supplied paths. On Windows, NTFS junctions and directory junctions are transparent to `is_file()` and `exists()`, allowing a prepared adversary to redirect filesystem operations to protected locations. For a pharma-sector pilot this is a meaningful audit failure.

3. **HIGH — Production License Enforcement is a Stub** (`license.rs`): `current_license_status()` in Rust returns `no_license` unconditionally in production and delegates to Python sidecar in a Block 4 TODO that was never wired. In production builds, `has_feature()` therefore always returns `false` — meaning the UI *currently enforces* license gates (good) but via a wrong state rather than a real SDK check. The product cannot be monetised until this is wired.

**Strong positives:**
- Auth token: 32-byte CSPRNG, constant-time compare, hex validation, env-isolation — textbook correct.
- Build profile gate (license bypass): compile-time embedding via `build.rs` is the right architecture.
- Bundle integrity chain: zip-slip defense + per-entry SHA-256 + manifest cross-check in both Rust and Python — genuinely multi-layered.

**Overall maturity: 68/100** — Strong security thinking at component level; architecture has critical scalability gaps and several wiring stubs that block production hardening.

---

## 2. Security Findings

### Severity Matrix

| ID | Severity | Category | Component | Likelihood | Impact |
|----|----------|----------|-----------|-----------|--------|
| SEC-01 | CRITICAL | DoS / Memory exhaustion | `methods.py` | HIGH | HIGH |
| SEC-02 | HIGH | Path traversal (symlink/junction) | All file I/O | MEDIUM | HIGH |
| SEC-03 | HIGH | License enforcement stub | `license.rs` | CERTAIN | COMMERCIAL |
| SEC-04 | HIGH | Auth token in process env namespace | `sidecar.rs` | LOW | HIGH |
| SEC-05 | HIGH | Hardcoded developer machine paths | `methods.py` | CERTAIN | MEDIUM |
| SEC-06 | MEDIUM | CSP unused origin + no MITM defense | `tauri.conf.json` | LOW | MEDIUM |
| SEC-07 | MEDIUM | Telemetry stored unencrypted | `telemetry.rs` | LOW | MEDIUM |
| SEC-08 | MEDIUM | `generate_reproduce_script` scope | `reproduce_script.py` | LOW | LOW |
| SEC-09 | MEDIUM | `parse_data_file` arbitrary path | `methods.py` | LOW | MEDIUM |
| SEC-10 | LOW | Auth token length oracle | `auth.py` | VERY LOW | VERY LOW |
| SEC-11 | LOW | `macOSPrivateApi: true` undocumented | `tauri.conf.json` | N/A | LOW |

---

### SEC-01 — CRITICAL: Unbounded Forecast Thread Pool (DoS / Memory Exhaustion)

**Attack vector:** Local (user controls the UI, or UI has a submit bug)  
**Likelihood:** HIGH — no debouncing guard in UI; rapid clicks or repeated API calls spawn N threads.  
**Impact:** Process RSS exhaustion → sidecar crash → app requires hard-restart; potential data loss if autosave mid-write.

**Description:**  
`_forecast_threads`, `_optimize_threads`, and `_integrity_threads` are plain `dict[str, threading.Thread]` with no capacity bound (lines 66–68 in `methods.py`). `_start_forecast()` (line 1191) unconditionally spawns a `threading.Thread` after validating only that `project_id` is plausible. There is no check of the form `if len(_forecast_threads) >= MAX: raise ValueError(...)`.

Each forecast thread loads PyMC which allocates large JAX/NumPy posterior arrays. At `n_iterations=100`, `horizon_weeks=52`, one thread uses ~300–600 MB RSS. Ten concurrent threads = 3–6 GB. On a typical 8 GB analyst laptop the OS OOM-kills the sidecar process.

Same structural gap exists for `_optimize_threads` (line 2021) and `_integrity_threads` (line 67).

**Attack scenario:**  
User opens the wizard 10 times in rapid succession (double-click on Start, slow network, frustration re-click) or an IPC client sends 100 `start_forecast` calls. Sidecar spawns 100 PyMC threads. RSS hits 16 GB. OS OOM-kills sidecar. Rust side sees `CommandEvent::Terminated`, cancels pending IPC (B4-S2), but if a forecast thread was mid-`save_version` the ProjectDB WAL transaction may be orphaned.

**Recommended fix:**
```python
MAX_CONCURRENT_FORECASTS: int = 3  # user-visible limit; tune per pilot feedback

@register("start_forecast")
def _start_forecast(params):
    with _THREADS_LOCK:
        live = sum(1 for t in _forecast_threads.values() if t.is_alive())
        if live >= MAX_CONCURRENT_FORECASTS:
            raise ValueError(
                f"Too many concurrent forecasts ({live}/{MAX_CONCURRENT_FORECASTS}). "
                "Cancel a running forecast before starting a new one."
            )
    # ... rest of existing logic
```

Also add `le=2000` validator to `BudgetSearchRequest.n_iterations` to cap memory per optimization task.

**Effort:** 30 min for cap; 15 min for `n_iterations` bound. **ROI:** Eliminates entire DoS class.

---

### SEC-02 — HIGH: Symlink / NTFS Junction Attack on Customer-Supplied Paths

**Attack vector:** Local (attacker prepares NTFS junction or symlink before user action)  
**Likelihood:** MEDIUM — requires local write access; pharma-sector shared workstations increase likelihood.  
**Impact:** Write operations (save_bundle, autosave) redirected to arbitrary files; read operations expose files outside expected scope.

**Description:**  
The following locations accept a string path from IPC and use `.exists()` or `.is_file()` without first calling `.resolve()` to canonicalize the path:

- `methods.py:897` `_import_aurora_bundle`: `bundle_path = Path(bundle_path_raw)` then `bundle_path.exists()` — NTFS junction follows transparently.
- `methods.py:1048` `_save_bundle`: `target_path = Path(params["target_path"])` — passed to `BundleZipWriter.write()` which calls `os.replace(tmp, path)`.
- `engines/data_source_watcher.py:238` `_check_folder_source`: `folder = Path(config.path)` → `folder.is_dir()` — junction to a sensitive directory appears as a normal folder.
- `services/optimizer_client.py:224` `LocalOptimizerClient.__init__`: `db_path.is_file()` — junction to another SQLite DB could be opened.
- `engines/bundle_container.py:94` `BundleZipReader.read`: `path.exists()` on caller-supplied path.

**Attack scenario (save_bundle):**  
Attacker creates NTFS junction: `C:\Users\victim\Documents\ProjectX.aurora` → `C:\Windows\System32\evil.dll`. User triggers "Save bundle" for project X. `target_path = Path("C:\\Users\\victim\\Documents\\ProjectX.aurora")`. `os.replace(tmp_path, target_path)` follows the junction. On Windows, replacing a DLL requires elevated privileges (blocked by ACL), but error message reveals the resolved path. More realistic target: user's own important file replaced by a bundle ZIP.

**Recommended fix:**
```python
_ALLOWED_ROOTS: list[Path] = [
    Path(platformdirs.user_data_dir("Aurora Launch")),
    Path.home() / "Documents",
    Path(os.environ.get("APPDATA", "")),
    Path(os.environ.get("LOCALAPPDATA", "")),
]

def _validate_customer_path(raw: str, *, must_be_file: bool = False) -> Path:
    """Resolve and validate that path is within allowed roots. Raises ValueError on violation."""
    resolved = Path(raw).resolve()
    if not any(str(resolved).startswith(str(r.resolve())) for r in _ALLOWED_ROOTS):
        raise ValueError(
            f"Path {raw!r} resolves to {resolved} which is outside allowed directories. "
            f"Aurora Launch only operates within AppData, Documents, or similar user directories."
        )
    if must_be_file and not resolved.is_file():
        raise ValueError(f"Expected a file at {raw!r}, got directory or missing.")
    return resolved
```

Call `_validate_customer_path()` at the top of each affected IPC handler.

**Effort:** 2 hours to add helper and call in 6 locations. **ROI:** HIGH for regulated-sector pilots.

---

### SEC-03 — HIGH: Production License Enforcement is an Unfired Stub

**Attack vector:** Any production user  
**Likelihood:** CERTAIN — code is provably disconnected  
**Impact:** Paid features gated by UI (good), but gating reason is `no_license` instead of a real validation. Monetisation blocked.

**Description:**  
`src-tauri/src/commands/license.rs` lines 27–51:

```rust
// Block 2 stub: returns degraded by default; Block 4 invokes Python
// LaunchLicenseValidator.from_env().current_status() via sidecar.
let is_dev = crate::BUILD_PROFILE == "dev";
if is_dev {
    // ... dev bypass grants all features
} else {
    Ok(LicenseStatusPayload {
        state: "no_license".into(),
        detail: "Block 4 wires real LicenseSDK via Python sidecar".into(),
        ...
    })
}
```

In production builds `state: "no_license"` means every `has_feature()` call returns `false`. The Python-side `LaunchLicenseValidator` (correct, complete) is never called. The sidecar method `get_license_status` is not registered in `methods.py` (`list_methods()` output does not include it).

This is not a vulnerability — it fails-closed (no access to paid features). But it means:
- All production installs show "no license" 
- Trial period cannot start
- The product cannot be sold

**Recommended fix:**
1. Register `get_license_status` in `methods.py` calling `LaunchLicenseValidator.from_env().current_status().model_dump()`.
2. In `license.rs`, call `sidecar.invoke("get_license_status", {}).await` and deserialize response.

**Effort:** 3 hours. **Priority:** Block 5 / pre-commercial.

---

### SEC-04 — HIGH: Auth Token Visible via Process Environment

**Attack vector:** Local process with ptrace/process inspection capability  
**Likelihood:** LOW on Windows; MEDIUM on Linux/macOS (both are target platforms per `tauri.conf.json` bundle targets).  
**Impact:** Attacker reads `AURORA_SIDECAR_AUTH_TOKEN` and can inject arbitrary IPC commands as if authenticated.

**Description:**  
The 32-byte random token is passed as an environment variable. On Linux, any process with `CAP_SYS_PTRACE` or read access to `/proc/$PID/environ` can retrieve it. On macOS, `task_for_pid()` without SIP enabled exposes it. The `auth.py` comment acknowledges this as an explicit threat-model decision: "adversary with full process inspection can read env vars; goal is defense against opportunistic local probes, not against root-level attackers."

This is an acceptable threat model for a desktop app — it matches how all OS keychain and browser password managers work. The gap is that it is not documented for customers. A pharma client's security team will ask about this in a vendor questionnaire.

**Recommended fix:** Add SECURITY.md section: "IPC Auth Token Threat Model" explaining the design decision, the threat-model boundary, and that the app does not provide cryptographic isolation against elevated-privilege attackers on the same machine.

**Effort:** 1 hour (documentation only). **Priority:** Before any enterprise pilot sign-off.

---

### SEC-05 — HIGH: Hardcoded Developer Machine Paths in Shipped Binary

**Attack vector:** Any user on any machine other than the developer's  
**Likelihood:** CERTAIN — affects `load_sample_bundle` on every non-developer install  
**Impact:** Feature non-functional; error message exposes developer username and internal directory structure.

**Description:**  
`methods.py` lines 925–940:
```python
_SAMPLE_BUNDLE_PATHS: dict[str, Path] = {
    "kagotsel_venarus": Path(
        "C:/Users/ackol/Desktop/Аврора - материалы для обучения и тестирования"
        "/Эконометрика - тестовые файлы/XLSX"
        "/Кагоцел РФ+_данные для эконометрики + наши данные 29.08.xlsx"
    ),
    # ... two more paths with C:/Users/ackol/...
}
```

Error message on any other machine:
```
FileNotFoundError: Sample XLSX not found at C:/Users/ackol/Desktop/...
Ensure pilot test files are present on this machine.
```

This exposes developer username `ackol`, directory structure, and confirms dev OS is Windows. For a pharma-regulated pilot where all audit logs are retained, this is a data confidentiality risk. For Materia Medica pilot specifically: if they inspect error logs, they see Aurora's internal developer machine structure.

**Recommended fix:**
```python
_SAMPLE_BUNDLE_ROOT = Path(
    os.environ.get("AURORA_SAMPLE_BUNDLE_DIR", "")
    or platformdirs.user_data_dir("Aurora Launch")
) / "sample_bundles"

_SAMPLE_BUNDLE_PATHS: dict[str, str] = {
    "kagotsel_venarus": "kagocel_rf_plus.xlsx",
    "venarus_baseline": "venarus_baseline.xlsx",
    "multi_proxy": "mmx_2021_2025.xlsx",
}
# Full path resolved at runtime:
# _SAMPLE_BUNDLE_ROOT / _SAMPLE_BUNDLE_PATHS[scenario]
```

Ship sample XLSXs as part of installer under `$APPDATA/aurora-launch/sample_bundles/`.

**Effort:** 1 hour code + installer packaging change.

---

### SEC-06 — MEDIUM: CSP Includes Unused Origin + No Update Endpoint MITM Defense

**Description:**  
`tauri.conf.json` line 34:
```
connect-src 'self' ipc: http://ipc.localhost https://updates.auroraai.pro https://feedback.auroraai.pro
```

`https://feedback.auroraai.pro` is in `connect-src` but no frontend code makes requests to it. The in-app feedback dialog calls `ipc.captureFeedback()` which routes to the local Rust `feedback` command — not to any external endpoint. Dead CSP scope.

The Ed25519 updater signature check (BLOCKER-3 fix) correctly prevents binary substitution even if the update endpoint is MITM'd. However, a MITM on `updates.auroraai.pro` could serve a stale manifest permanently, blocking security updates from reaching users (update-suppression attack).

**Recommended fix:**
1. Remove `https://feedback.auroraai.pro` from CSP until implemented.
2. Consider adding a `X-Content-Type-Options: nosniff` equivalent or signed manifest timestamp validation to detect update-suppression.

**Effort:** 5 minutes (remove dead origin).

---

### SEC-07 — MEDIUM: Telemetry Events Stored in Unencrypted Rust SQLite

**Description:**  
`src-tauri/src/commands/telemetry.rs`: events are stored in `state.sqlite` (Rust SQLite, separate from the encrypted Python ProjectDB). No encryption is applied to this DB. The TypeScript telemetry service strips `project_uuid`, `project_name`, `brand_name` client-side, but the Rust `log_event` command accepts raw `payload: serde_json::Value` and stores it without server-side PII validation.

If a future event payload accidentally includes PII (regression), it would be stored in plaintext. The `error_occurred` event stores a `stack_fingerprint` (8-char hash) — this is safe, but the hash is deterministic and could theoretically be reverse-correlated across multiple error events.

For a 152-ФЗ compliance claim (data stays local, encrypted), the telemetry DB being unencrypted is a gap.

**Recommended fix:** Apply the same `PRAGMA key` approach as `ProjectDB` to the Rust SQLite. Or: validate at `log_event` that `payload` keys do not include `project_uuid`, `brand_name`, `customer_name`.

**Effort:** 2 hours.

---

### SEC-08 — MEDIUM: `generate_reproduce_script` — Partial Mitigation

**Description:**  
`tools/reproduce_script.py` lines 76–80 correctly uses `json.dumps(bundle_path)` for the bundle path literal, preventing classic Python code injection. The comment documents the threat: `'x"); import os; os.system("..."); Path("y'` style injection.

**Remaining gap:** The generated script is run by the customer locally. If the bundle itself (which was loaded before script generation) contains a malicious `manifest.json` with crafted entry paths, those paths appear in the generated script's comments (documentation only, not executed). However, `anchors` and `spend_plan` data from IPC params are serialized with `json.dumps(ensure_ascii=False)` — Unicode RTL override characters could craft misleading script display in some editors, though not execution risk.

**This is low severity** — the primary vector is documented and mitigated. Note it for completeness.

---

### SEC-09 — MEDIUM: `parse_data_file` Accepts Arbitrary Filesystem Path

**Description:**  
`methods.py:1096`:
```python
path = params["path"]  # raw string from IPC, no scope validation
adapter = registry.detect(path)
records = adapter.parse(path)  # calls openpyxl.load_workbook(path)
```

`openpyxl.load_workbook()` opens any path the Python process can read. Without scope validation, this enables reading XLSX files from arbitrary locations (system files, other users' documents if path is known). Exploitation requires the auth token (SEC-04 dependency), reducing likelihood significantly.

**Recommended fix:** Apply `_validate_customer_path()` from SEC-02 fix. **Effort:** 15 minutes once helper exists.

---

### SEC-10 — LOW: Auth Token Length-Mismatch Early-Exit Oracle

**Description:**  
`auth.py:65`:
```python
if len(presented) != len(expected):
    raise AuthError("auth length mismatch")
if not hmac.compare_digest(presented, expected):
    raise AuthError("auth token invalid")
```

The early-exit on length mismatch occurs before `hmac.compare_digest`. An attacker can determine the expected token length by sending tokens of varying lengths and observing the error message difference ("auth length mismatch" vs "auth token invalid"). The expected length (64 chars) is already publicly documented by the `auth.py` module-level comment and `EXPECTED_TOKEN_HEX_LEN = 64` constant, so this leaks no new information. But it violates constant-time comparison principles.

**Recommended fix:**
```python
# Pad to same length before compare_digest to avoid length oracle
presented_padded = presented.ljust(len(expected))[:len(expected)]
if not hmac.compare_digest(presented_padded, expected):
    raise AuthError("auth token invalid")  # single message for length AND content mismatch
```

**Effort:** 10 minutes.

---

### SEC-11 — LOW: `macOSPrivateApi: true` Without Rationale

**Description:**  
`tauri.conf.json:8`: `"macOSPrivateApi": true`. Enables private macOS APIs (transparent windows, NSVisualEffectView vibrance). No comment explains why. If macOS App Store distribution is planned, this flag may trigger review flags. If it is not needed, enabling it increases attack surface.

**Effort:** 5 minutes to verify and add comment or remove.

---

## 3. Architecture Findings

### 3.1 Module Layering Assessment

The layering is conceptually correct:
```
frontend (Svelte) → Rust IPC → SidecarManager → Python JSON-RPC → methods.py
                                                                      ↓
                                                    engines/ (pure computation, portable)
                                                    persistence/ (storage layer)
                                                    services/ (DI container + cross-product)
                                                    schemas/ (Pydantic models, shared types)
```

The `engines/` layer is genuinely portable — it does not import from `persistence/` or `services/`. This means the math engines (Bayesian, conformal prediction, budget optimizer) can be extracted to a server-side deployment with minimal changes. This is an architectural strength.

**A3-01 — `methods.py` is a God Module (2300+ lines, 30+ handlers):**  
`methods.py` currently: registers 30 IPC methods, owns 4 module-level singletons, manages 4 thread pool dicts, handles `GC_STOP_EVENT`, contains inline business logic (data extraction helpers in `_compare_forecast_versions`). This violates Single Responsibility and makes handler isolation impossible.

Recommended split:
```
sidecar/
  methods/
    __init__.py          # imports all submodules to trigger @register decorators
    registry.py          # _METHODS dict, register decorator, dispatch(), list_methods()
    forecast.py          # start_forecast, cancel_forecast, get_forecast_status
    project.py           # create/list/get/delete_project, list/compare_versions
    bundle.py            # save_bundle, parse_data_file, compose_forecast_json
    system.py            # ping, negotiate, shutdown, get_memory_report
    optimizer.py         # optimize_budget, get_optimize_status
    auto_refresh.py      # check_data_source_updates, set_consent, dismiss_trigger
```

**A3-02 — Half-DI / Half-Singleton Creates Test Pollution:**  
`services.py` implements `ServiceContainer` as the DI mechanism, but `methods.py` still maintains parallel module-level singletons (`_PROJECT_DB`, `_AUTOSAVE`, `_GC_THREAD`, `_consent_manager`, `_dismissed_refresh`) which must be manually reset. This is acknowledged in existing stage audits (B-02). Root cause: DI was added incrementally; module-level vars remain as "backward-compat" fallback, creating two sources of truth.

**A3-03 — SPOF: Sidecar Process = Single Point of Failure:**  
The entire application is blocked when the sidecar is unavailable. There is no degraded mode for UI operations that don't need Python (viewing saved bundles already loaded, reading cached project list). The `HandshakeIncompatibleModal` blocks correctly on incompatibility, but there's no timeout-then-degrade path for sidecar startup delay (common on slow machines with large PyMC import).

**A3-04 — Cross-Cutting Concerns Not Centralized:**  
`logger = logging.getLogger(__name__)` is instantiated at module level in 40+ files. No root logger configuration or structured logging adapter. Logs from the sidecar go to stderr (collected by Rust's `CommandEvent::Stderr`) but format is unstructured text. Future observability pipeline (Sentry, Datadog, etc.) requires a format migration.

**A3-05 — Domain Language Inconsistency:**  
- "project_uuid" in DB methods vs "project_id" in `_start_forecast` params — same concept, two names.
- "proxy" means both: the proxy brand (source brand) AND the proxy posterior (statistical artifact). Both usages appear in the same file.
- "version_id" (integer PK) vs "revision" (per-project monotonic counter) — both increment per save, not obvious from naming which is which at a glance.
- "anchor" means recipient brand parameters in most places, but "anchors" in `compose_forecast_json` means the full `RecipientAnchors` object — overloaded.

**A3-06 — Future Cloud Migration Complexity:**  
If Aurora moves computation server-side (Vercel Edge, AWS Lambda), the following must be rewritten:
- `ProjectDB` (SQLite → cloud DB; all SQL queries)
- `BlobStore` (local filesystem → S3 or equivalent)
- `_SAMPLE_BUNDLE_PATHS` (absolute developer paths)
- `DataSourceWatcher` (filesystem polling → webhook-driven)
- `AutosaveManager` (local temp file → cloud draft storage)

This is ~40% of the codebase. However, the clean `engines/` layer (pure math, no I/O) is portable. The gap is that `persistence/` and `services/` have zero abstraction over "local vs remote" storage — there are no repository interfaces, only concrete implementations.

---

## 4. Engineering Quality Scorecard

### 4.1 Testing Pyramid Balance

| Layer | Count | Quality | Gap |
|-------|-------|---------|-----|
| Unit (pytest) | 1,435 | Strong; Hypothesis property tests present | — |
| Unit (vitest) | 389 | Good; covers stores, services, components | — |
| Integration (pytest) | ~120 est. | Reasonable (DB, migration, autosave tests) | — |
| E2E (Playwright) | 8 spec files | **Runs against mocked IPC, not real Tauri** | **Critical** |
| Security (pytest) | ~15 | Auth bypass, zip-slip, signature forge — good | Symlink tests missing |
| Performance regression | 0 | **None whatsoever** | **Gap** |
| Cross-OS | CI: Windows + Linux | macOS CI missing | Medium |
| Cross-browser | Chrome only | Single browser | Low |

**Pyramid verdict: Inverted at the top.** The E2E tests exist and are well-structured, but they test the frontend against mocked IPC. The actual Rust↔Python boundary is only tested by `PILOT_SMOKE_CHECKLIST.md` (manual). For a product with two language boundaries (Rust↔Python via JSON-RPC over stdin/stdout), zero automated integration testing of that boundary is a significant gap.

**Autosave flaky test:** Mentioned in comments as known; pattern is timer-dependent test without time injection — inherently flaky in CI with variable load.

### 4.2 Code Quality Dimensions

| Dimension | Score | Key Findings |
|-----------|-------|-------------|
| Naming clarity | 7/10 | Good in most places; `project_id` vs `project_uuid` inconsistency; `_ScoredCandidate` etc. appropriate |
| Abstractions | 6/10 | Under-abstracted: `methods.py` god module. `ServiceContainer` with `Any`-typed slots reduces type safety value |
| Duplication | 6/10 | `platformdirs` / `~/.aurora-launch` fallback pattern repeated in `_get_project_db()` and `_get_autosave_manager()`. Extract to `_resolve_data_root()` helper |
| Error hierarchy | 8/10 | Strong: `ProjectDBError`, `SidecarStorageError`, `MigrationError`, `AuthError`, `LicenseFeatureRequired` — explicit |
| Type safety | 7/10 | `mypy strict = true` set (correct). `ServiceContainer` slots all `Any` — reduces value |
| Docstrings | 7/10 | Module-level docstrings excellent. Some method docstrings missing in `budget_optimizer.py` |
| Code comments | 9/10 | Exceptional comment density for a new codebase — rare positive |

### 4.3 Developer Experience

**Strong DX:**
- `filterwarnings = ["error"]` in `pyproject.toml` with narrow allowlist — excellent CI discipline
- `AURORA_PROJECT_DB_PATH` env override for test DB isolation
- `SidecarManager.auth_token_for_test()` constructor separates concerns cleanly
- Pre-commit config present and active

**DX Gaps:**
- `_SAMPLE_BUNDLE_PATHS` hardcoded to developer machine (SEC-05): feature is non-functional for any other developer or tester.
- No `CONTRIBUTING.md` or development setup guide. A new developer has no documented path to run the full stack locally.
- `uv.lock` is 232 KB with no CI check for lock drift (`uv sync --locked` equivalent not in CI per cursory check).
- Build requires manual `AURORA_UPDATER_PUBKEY` env var. The `secrets/updater-pubkey.txt` convention is documented but not automated.

### 4.4 Documentation Inventory

| Document | Status | Notes |
|----------|--------|-------|
| README.md | Present | Reasonable for stage |
| CHANGELOG.md | Present | Good |
| SECURITY.md | **Missing** | Required for pharma clients |
| CONTRIBUTING.md | **Missing** | Required before any external contributor |
| Sidecar API schema | Docstrings only | No machine-readable schema (OpenAPI, JSON Schema) |
| ADRs | Referenced but not found in `03_Architecture/` | Loose coupling between docs and code |
| Deployment runbook | `Final/F1_DEPLOYMENT_RUNBOOK.md` — excellent | |
| Installer buildbook | `Final/F2a_INSTALLER_BUILDBOOK.md` — excellent | |

---

## 5. Compliance and Privacy Gaps

### 5.1 152-ФЗ Compliance Status

| Requirement | Status | Gap |
|-------------|--------|-----|
| Explicit opt-in for data collection | Done | `RefreshConsentSetting` + telemetry opt-in |
| PII scrubbing in telemetry events | Done (client-side) | Server-side validation missing (SEC-07) |
| Data residency (local-only) | Done | Telemetry DB unencrypted (SEC-07) |
| Audit log for regulated operations | Partial | Logs event types but not forecast inputs |
| Right to deletion | **Missing** | No documented user-data deletion flow |
| Data processing agreement template | **Missing** | Needed for pharma B2B contracts |

**Right to Deletion Gap:**  
When a user deletes a project, `delete_project()` correctly cascades and decrements blob ref-counts. But the telemetry DB (Rust SQLite in `state.sqlite`) retains all events indefinitely. There is no "delete all my data" workflow. For GDPR-adjacent obligations common in international pharma companies operating in Russia, this is a contract risk.

### 5.2 Pharma-Sector Specific (Materia Medica Pilot)

**Audit log sufficiency:**  
For a pharma regulatory submission where the forecast supports a marketing budget decision, the audit trail must record: who ran the forecast, with what inputs (parameter hash), on what date, and that the methodology certificate hash was verified. The current `audit_log.rs` records IPC call event types and timestamps but not forecast inputs or parameter hashes.

**Methodology certificate gap:**  
`build_certificate()` returns:
```json
{
  "dual_signature_status": {
    "local_signed": false,
    "aurora_signed": false,
    "aurora_pending": true
  }
}
```

No forecast currently has an actual verified Ed25519 signature. The "Methodology Certified" claim in marketing materials is accurate for the *design* but not yet for the *implementation*. This must be resolved before any regulatory submission context.

---

## 6. Session-Specific Risk Analysis

### Stage 1.3 — `compose_forecast_json`: IPC Input Lacks Deep Validation

**Risk (HIGH):**  
`weekly_points` is a raw list from IPC consumed with `.get()` fallback patterns. A malicious or misbehaving IPC call with `weekly_points: [{"point": null, "ci_lower": null, "ci_upper": null}]` passes the `required-params` check, reaches `compose_forecast_json_bytes()`, and produces a `forecast.json` with `null` point forecasts. The finite validator (Audit A-3 fix, line 33 in `forecast_bundle.py`) guards at bundle-write level, but `weekly_points` items are not individually validated at the IPC entry point.

**What breaks:** `forecast.json` written with `null` values. Inspector shows NaN. Compare-versions computes `null_delta`. Reproduce script generates invalid Python that errors on execution.

**Fix:** Add Pydantic `WeeklyPoint` model with `float` fields and `_finite_check` validator; validate at IPC entry in `_compose_forecast_json`.

### Stage 2.5 — DB Migrations: No Customer Data Preservation Gate

**Risk (MEDIUM):**  
Migrations v001 and v002 are DDL-only (`CREATE TABLE IF NOT EXISTS`, `INSERT OR IGNORE`) and are currently safe. But there is no automated test that: seeds a real ProjectDB with sample data, applies all migrations, and verifies data integrity afterward. When v003 migration is added (e.g., a column with `NOT NULL DEFAULT`), customer data loss could slip through CI undetected.

**Fix:** Add `tests/test_migrations.py` with: create DB at version N-1 with seed data → apply migration N → assert row count and key field values preserved. This is an integration test pattern absent from the current test suite.

### Stage 2.7 — DI Container: `globals()` Manipulation

**Risk (LOW):**  
`_hard_reset_module_singletons()` uses `globals().__setitem__()` to reset `_consent_manager` and `_dismissed_refresh`. This works because the function is defined in `methods.py` where those variables live. However, any future refactoring that moves these variables to a submodule (recommended in A3-01) would silently break the reset — the `globals()` call would target the wrong module's namespace.

**Fix:** Use explicit `global _PROJECT_DB, _AUTOSAVE, _consent_manager` declarations. Static analysis tools (mypy, pylint) understand `global` declarations but not `globals()` manipulation.

### Stage 2.9 — Updater Ed25519: Update-Suppression Attack

**Risk (MEDIUM):**  
The updater endpoint URL includes `{{current_version}}`:
```
https://updates.auroraai.pro/launch/{{target}}/{{arch}}/{{current_version}}
```

An attacker controlling DNS of `updates.auroraai.pro` (rogue DNS, MITM) can serve a stale manifest indefinitely, suppressing security updates. The Ed25519 binary signature check (BLOCKER-3) prevents binary substitution, but update-suppression is not covered.

**Mitigation:** Add a `min_manifest_timestamp` field to update manifest payload; client rejects manifests older than (current_build_date - 30 days). Or: add an out-of-band "minimum required version" endpoint that the client polls separately.

### Stage 3.4 — `LocalOptimizerClient`: TOCTOU on `is_file()` Check

**Risk (LOW):**  
`db_path.is_file()` passes; between check and `sqlite3.connect(db_path)`, a different process swaps the symlink target. Race window is microseconds. Real threat requires both write access to the symlink location AND precise timing. Covered by SEC-02 general fix (`resolve()` + scope check).

### Stage 3.5 — `DataSourceWatcher`: mtime Detection Race

**Risk (ACCEPTABLE):**  
If customer writes an XLSX file while the watcher is scanning, the mtime may be read before the file flush completes, resulting in one scan-cycle delay in triggering. This is eventual consistency — not data corruption. Document as known limitation; no fix required.

### Stage 4.4 — Budget Optimizer: `n_iterations` Unbounded

**Risk (HIGH):**  
`BudgetSearchRequest.n_iterations` has no maximum validator in the Pydantic schema (`budget_optimization.py`). With `n_iterations=1000000`, the optimizer spawns a 120-second thread generating 1M Dirichlet samples. Combined with SEC-01 (unbounded thread pool), multiple such requests exhaust RAM and CPU.

**Fix:** Add `n_iterations: int = Field(default=100, ge=1, le=2000)` to `BudgetSearchRequest`. Emit a `optimize_budget_capped` warning event if IPC requested more than the limit.

---

## 7. Tech Debt Map

### Critical Hotspots (address before sustained pilot)

| Location | Lines | Debt Type | Priority |
|----------|-------|-----------|----------|
| `methods.py` | 2300+ | God module: thread pools + singletons + 30 handlers | P1 (pre-v0.2) |
| `methods.py:925-940` | 15 | Hardcoded developer absolute paths | **P0** |
| `license.rs:24-52` | 28 | Block 4 stub — real license enforcement missing | **P0** (pre-commercial) |
| All IPC handlers | ~6 locations | Missing `Path.resolve()` scope check | P0 (before pharma pilot) |
| `methods.py:102-114` | 12 | `globals()` manipulation in reset function | P2 |
| `services.py` + `methods.py` | ~200 | Half-DI dual-singleton pattern | P2 (post-launch) |

### Medium-Priority Debt

| Location | Debt Type |
|----------|-----------|
| `budget_optimization.py` schema | `n_iterations` unbounded |
| `telemetry.rs` SQLite | Unencrypted despite ProjectDB having SQLCipher |
| `diagnostics.py:53` | `_SENSITIVE_LOG_MARKERS` missing `AURORA_DB_KEY_HEX` |
| Playwright E2E specs | All run against mocked IPC — no real Tauri boundary testing |
| `_get_project_db()` / `_get_autosave_manager()` | Identical `platformdirs` fallback — extract to `_resolve_data_root()` |
| `gc_thread_body()` | `db._update_gc_metadata()` private method access (`# noqa: SLF001`) — encapsulation violation |
| `check_same_thread=False` in `ProjectDB` | Comment says "concurrent reads safe"; concurrent writes still require `_write_lock`; not all write paths acquire it (verify `update_project_metadata()` called from GC thread) |

### Recommended Refactoring Sequence

1. **SEC-05 quick fix** (hardcoded paths → configurable, 1h) — zero regression risk, enables multi-dev workflow
2. **SEC-01 quick fix** (thread cap, 30min) — prevents DoS in current pilot
3. **Add `_validate_customer_path()` helper** + call in 6 locations (2h) — closes symlink family
4. **Add `n_iterations` Pydantic validator** (15min) — closes optimizer DoS
5. **Write migration integration test** (1h) — protects customer data on future migrations
6. **Wire license sidecar method** (3h) — enables monetisation
7. **Split `methods.py` into subpackage** (8h) — prerequisite for all future handler isolation
8. **Commit to full DI** — move lazy-init into `ServiceContainer`, delete module-level singletons (4h after #7)
9. **Add structured logging** (4h) — prerequisite for future observability
10. **E2E tests against real Tauri** (8h) — closes the biggest testing blind spot

---

## 8. Top-10 Quick Wins (Security + DX)

| # | Action | File | Effort | Benefit |
|---|--------|------|--------|---------|
| 1 | Remove hardcoded dev paths (`_SAMPLE_BUNDLE_PATHS`) | `methods.py:925` | 1h | SEC-05 closed; enables multi-dev |
| 2 | Add `MAX_CONCURRENT_FORECASTS = 3` cap | `methods.py:1191` | 30m | SEC-01 DoS eliminated |
| 3 | Add `n_iterations: int = Field(le=2000)` | `budget_optimization.py` schema | 15m | Optimizer DoS cap |
| 4 | Remove `feedback.auroraai.pro` from CSP | `tauri.conf.json:34` | 5m | Dead scope removed |
| 5 | Fix `_hard_reset_module_singletons` with explicit `global` | `methods.py:102` | 15m | Correct test isolation |
| 6 | Add `Path.resolve()` to `_import_aurora_bundle` and `_save_bundle` | `methods.py:897,1048` | 30m | Partial SEC-02 |
| 7 | Add `SECURITY.md` with auth token + data residency docs | new file | 2h | Pharma pilot sign-off unblocked |
| 8 | Add migration integration test (seed → migrate → assert) | `tests/test_migrations.py` | 1h | Stage 2.5 risk closed |
| 9 | Remove or justify `macOSPrivateApi: true` | `tauri.conf.json:8` | 5m | Attack surface documented |
| 10 | Add `CONTRIBUTING.md` with local dev setup | new file | 2h | Multi-dev DX |

---

## 9. Top-10 Strategic Improvements (x100 Scale)

At x100 scale (1000 projects, 100 concurrent sessions, 10 simultaneous pilots):

1. **Bounded ThreadPoolExecutor for forecasts**: Replace `threading.Thread` spawns with a `concurrent.futures.ThreadPoolExecutor(max_workers=N)` with priority queue and backpressure event (`forecast_queued`). Enables user-visible queue position and graceful degradation.

2. **ProjectDB sharding**: Single `projects.db` for 1000 projects with complex JSON metadata + concurrent GC/writes will show WAL contention. Consider per-project DB files with a central index DB, or migration to DuckDB for analytical queries.

3. **Sidecar restart strategy with state recovery**: Implement exponential-backoff auto-respawn on `CommandEvent::Terminated` with auth token rotation + pending request replay queue. Current behavior: app shows error, user must manually restart.

4. **Structured logging pipeline**: Replace unstructured `log::warn!` and `logging.getLogger(__name__)` with structured JSON logs (`tracing` in Rust, `structlog` in Python). Required for log aggregation, alerting, and debugging in multi-pilot environment.

5. **Full DI migration**: Commit fully to `ServiceContainer` — move lazy-init logic into `ServiceContainer.get_or_create_*()` methods, delete module-level singleton vars from `methods.py`, eliminate `_hard_reset_module_singletons` entirely. Enables true handler isolation testing.

6. **Wire real license enforcement** (SEC-03): The Python `LaunchLicenseValidator` is complete and correct. Wire it. This is not a strategic improvement — it is a business blocker that is already code-complete on the Python side.

7. **Bundle content-addressed delta compression**: At 1000 projects with frequent re-forecasting, the `BlobStore` will accumulate large numbers of near-identical posterior blobs (same proxy, slightly different normalization). A delta-compression layer on top of SHA-256 content-addressing would reduce storage 5–10×.

8. **Audit log enrichment for regulatory contexts**: Add forecast input hash (hash of anchors + spend_plan + seed) + operator identity (machine_id from license) + methodology certificate fingerprint to each `audit_log` entry. Required for pharma regulatory submissions.

9. **E2E tests against real Tauri runtime**: Current Playwright tests are valuable but test against mocked IPC. Add a CI job that: builds debug Tauri binary → starts it → runs Playwright against `http://localhost:5173` served by real Tauri. This is the only automated test of the Rust↔Python boundary.

10. **Security penetration test before first paid pilot**: Commission a lightweight pentest (1 week, external) focused on: auth token extraction via process inspection, path traversal via IPC, license bypass attempts, bundle integrity forgery. The Ed25519 bundle chain and build-profile gate are solid — but external validation builds customer trust.

---

## 10. What Prevents World-Class / Category-Defining Status

Aurora Launch has genuine technical ambition. The methodology certificate, conformal prediction, proxy-transfer architecture, and reproduce-this-forecast Python generator are rare capabilities in a desktop analytics tool. The technical ambition is real. The gaps are execution:

**Gap 1 — Testing covers correctness but not resilience.**  
1,435 pytest + 389 vitest tests verify correct outputs for valid inputs. There are almost no tests that verify system behavior under stress: sidecar killed mid-forecast, ProjectDB WAL corrupt, malicious bundle loaded, 100 concurrent IPC calls. World-class products have both correctness tests AND resilience tests.

**Gap 2 — The monetisation system is a code stub.**  
`license.rs` returns `no_license` in production. The Python `LaunchLicenseValidator` is complete. The bridge is missing. Until this is wired, the product works correctly but cannot be sold — every install behaves as a demo with license gates active but un-enforced by real validation logic.

**Gap 3 — Architecture supports 10 users, not 100.**  
A single Python sidecar process with unbounded thread dicts, a single `projects.db` SQLite file, and no request queuing will degrade non-linearly. Five pharma analysts each running 2-hour Bayesian forecasts simultaneously is a realistic pilot scenario; the current architecture will OOM on it.

**Gap 4 — "Certified" methodology is an aspiration, not yet an implementation.**  
`dual_signature_status: {local_signed: false, aurora_signed: false, aurora_pending: true}` is the current production state for every forecast. The C7 signing service is deferred. The reproduce-script and certificate HTML template are real and valuable, but the "certified" claim requires an actual signature.

**What would elevate it to world-class:** Bounded concurrency with user-visible queue feedback. Real license enforcement wired. One genuine Ed25519-signed methodology certificate in production. E2E tests against the real Tauri runtime. And a `SECURITY.md` that a pharma client's security team can read without scheduling a call.

The foundation is architecturally sound. The gap is hardening.

---

## Appendix: Finding Cross-Reference Table

| Finding ID | Severity | Primary File | Section Reference |
|------------|----------|-------------|------------------|
| SEC-01 Thread bomb | CRITICAL | `methods.py:66,1191,2021` | §2 |
| SEC-02 Symlink/Junction | HIGH | `methods.py:897,1048`, `data_source_watcher.py:238`, `optimizer_client.py:224` | §2 |
| SEC-03 License stub | HIGH | `src-tauri/src/commands/license.rs:24` | §2 |
| SEC-04 Auth token env | HIGH | `sidecar.rs:108`, `auth.py:40` | §2 |
| SEC-05 Dev hardcoded paths | HIGH | `methods.py:925-940` | §2 |
| SEC-06 CSP dead origin | MEDIUM | `tauri.conf.json:34` | §2 |
| SEC-07 Telemetry unencrypted | MEDIUM | `src-tauri/src/commands/telemetry.rs` | §2 |
| SEC-08 Reproduce script scope | MEDIUM | `tools/reproduce_script.py:76` | §2 |
| SEC-09 parse_data_file path | MEDIUM | `methods.py:1096` | §2 |
| SEC-10 Length oracle | LOW | `auth.py:65` | §2 |
| SEC-11 macOSPrivateApi | LOW | `tauri.conf.json:8` | §2 |
| A3-01 God module | — | `methods.py` entire | §3 |
| A3-02 Half-DI | — | `services.py`, `methods.py` | §3 |
| A3-03 SPOF sidecar | — | `sidecar.rs`, `server.py` | §3 |
| A3-04 Unstructured logging | — | All Python + Rust modules | §3 |
| A3-05 Domain language | — | `methods.py` params | §3 |
| A3-06 Cloud migration complexity | — | `persistence/`, `services/` | §3 |
| Stage 1.3 weekly_points null | HIGH | `methods.py:543-570` | §6 |
| Stage 2.5 migration gate | MEDIUM | `migrator.py`, `project_db.py` | §6 |
| Stage 2.7 globals() | LOW | `methods.py:108`, `services.py:171` | §6 |
| Stage 2.9 update suppression | MEDIUM | `tauri.conf.json:73-77` | §6 |
| Stage 3.4 TOCTOU | LOW | `optimizer_client.py:224` | §6 |
| Stage 3.5 mtime race | ACCEPTABLE | `data_source_watcher.py:275` | §6 |
| Stage 4.4 n_iterations | HIGH | `budget_optimization.py` schema | §6 |

---

*Document generated: 2026-05-16. Audit conducted by Claude Sonnet 4.6 in roles: Security Engineer, Staff Software Architect, QA Lead, Engineering Manager. Scope: Branch `feat/stage1-core-1.1-1.4`, HEAD `21e693e`, 18 autonomous commits (Stages 1–4). Existing audit documents excluded to avoid duplication.*
