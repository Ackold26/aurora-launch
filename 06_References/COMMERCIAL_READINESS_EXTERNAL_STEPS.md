# Commercial readiness — external steps (Anton)

**Created:** 2026-06-14 (Sprint 11 commercial-readiness review)
**Audience:** Антон (holds signing keys, cloud infra, sales)

Sprint 11 ground-truth review established that the three commercial blockers are
**already implemented in code** — the remaining work is external (keys, backend,
hosting, pilot data), not application code. This runbook lists those steps.

> Status legend: ✅ in code · ⏳ external (this doc) · 🔬 needs pilot data

---

## Track A — Auto-updater — MIGRATED to fleet checksum updater (ADR-008)

**Reframed 2026-06-14 (fleet-unify migration):** the minisign /
`tauri-plugin-updater` plan is **obsolete**. Launch now uses the fleet
SHA256-checksum updater (same as Econometrica + 6 other products). There is **no
keypair to generate, no pubkey to embed, no signing step** — integrity = SHA256
checksum from the server JSON, verified in Rust. The `build.rs` pubkey gate that
**blocked the production installer is removed.** Onboarding is now backend-only.

**In code (✅, Phase A DONE):** `src-tauri/src/commands/updater.rs` (checksum
model, dual endpoint Supabase `app-update` Edge Function + GH-Pages
`latest.json`), `UpdateAvailableBanner.svelte` on IPC commands
(`check_update`/`download_update`/`apply_update`), no plugin, no minisign. See
**ADR-008**.

**Backend done (✅, this session):** `app_versions` placeholder row
`product='aurora-launch'`; `licenses_product_check` += `'launch'`. No Edge
Function deploy needed (`app-update` / `auth` are product-agnostic).

**External steps (⏳ — Anton, per the `aurora-release-update` skill):**

1. Add `launch` (product id **`aurora-launch`**) to the `aurora-release-update`
   skill mapping table.
2. On each release: build the production installer from the repo root —
   `AURORA_BUILD_PROFILE=production tauri build` (**no signing env needed**) —
   then upload `Aurora.Launch_X.Y.Z_x64-setup.exe` to GitHub Releases
   `Ackold26/aurora-releases` (~110 MB → GH Releases, not Supabase Storage <50 MB).
3. Compute the installer SHA256 and
   `UPDATE app_versions SET version, download_url (GH Release asset URL),
   checksum, release_notes WHERE product='aurora-launch'`.
4. Publish `rosst-updates/aurora-launch/latest.json` (GH-Pages fallback — mirror
   of the same version / url / checksum).
5. **Smoke:** install N-1, publish N, confirm banner → download → checksum verify
   → install → relaunch end-to-end (VM).

**Obsolete (removed by ADR-008 — do NOT do these):** minisign
`tauri signer generate`, embedding a pubkey in `tauri.conf.json`,
`createUpdaterArtifacts` / `.sig` signing, `TAURI_SIGNING_PRIVATE_KEY`, the
`updates.auroraai.pro` endpoint, and the `AURORA_UPDATER_PUBKEY` CI patch/assert.

---

## Track B — License activation (`SPRINT_BUFFER #52`)

**In code (✅):** Launch's licence client is fully wired to the platform-core
JWT SDK — see **ADR-007**. `license.rs` (Rust IPC shell) → `LaunchLicenseValidator`
(`engines/license_validator.py`) → `aurora_common.license.LicenseSDK`. Enforcement
made real in the C-3 closure (Phase 2.A). Tier flags `launch_proxy_single` /
`launch_proxy_multi` exist in `aurora_common.tier_matrix`. Fail-closed: when
`aurora_common` is absent the validator denies all paid features; when the sidecar
is unavailable the Rust layer returns a `degraded` state.

**Decision (ADR-007):** stay on platform-core JWT; do NOT switch to Econometrica's
cabinet/Supabase model (would be a destructive rewrite of working code).

**External steps (⏳):**

1. **Bundle `aurora_common`** as a real dependency in the production build
   (currently graceful-fallback). Retire the `HAS_PLATFORM_CORE` flag /
   `try/except ImportError` in `license_validator.py` once it is reliably present.
2. **Deploy the JWT issuer backend:** Ed25519 keypair + an issue/refresh endpoint
   the SDK can validate against (the SDK already does Ed25519 JWT verify, 24h TTL,
   7-day offline grace, machine-ID binding, jti revocation).
3. **Integration smoke on a REAL signed token** (Launch is the first production
   consumer of this SDK — unit tests alone are insufficient): verify online
   validation, offline-grace window, machine-ID mismatch rejection, expiry.
4. **Per-seat annual subscription** productization (`expires_at` already supported
   by the SDK) — pricing tiers per `06_References/PRICING_TIERS.md`.

**Recommended hardening (audit 2026-06-14, defense-in-depth — apply during activation):**
- `license_validator.py::_info_to_status` trusts `aurora_common` to raise on
  expiry; add a local safety net before mapping state:
  `if info.valid_until and info.valid_until < datetime.now(timezone.utc): → EXPIRED`.
  (Verify against the SDK's `valid_until` tz semantics with a real token.)
- Grace-day display uses `timedelta.days` (truncates → off-by-one pessimistic);
  use `math.ceil(total_seconds/86400)` for the `offline grace day N/7` string.
  These paths are skipped in CI when `aurora_common` is absent — exercise them in
  the real-token integration smoke (step 3).

---

## Track C — Modeling validation (Π.2.5 / Π.2.6)

**In code (✅):** `ols_with_priors.py` (OLS + proxy priors) and
`bayesian_with_priors.py` (closed-form conjugate Bayesian + posterior samples)
are implemented and green (49 tests). `dispatch_table.py` routes Modes 3/4 to
them, with graceful `pure_transfer` degradation when recipient data is
insufficient (< 5 observations) — this is correct behaviour, not a stub.

**Needs pilot data (🔬):**

1. **CI calibration check.** The posterior covariance uses
   `Σ̂ = σ²·(XᵀX + λΩ⁻¹)⁻¹` with `λ = shrinkage` (default 0.3), which is a
   pragmatic ridge weighting, **not** the exact conjugate posterior (that would
   use `σ²Ω⁻¹` inside). Consequence: the 95% CI width depends on the `shrinkage`
   knob rather than being the strict Bayesian posterior. For the product's
   "honest, calibrated CI" promise this MUST be validated once a pilot brand
   accumulates 5+ real observations: does the 95% CI actually capture actuals at
   ~90%+? If mis-calibrated, either (a) set `λ = σ²` for true conjugacy, or
   (b) implement the master-plan formula `σ_β = √(σ_β_OLS² + σ_β_proxy²·shrinkage²)`
   explicitly. Tracked as a Sprint-12+ pilot-gated item.
2. Mode-4 currently uses the analytical Gaussian posterior (fast, `r_hat=1.0` by
   construction). Real PyMC MCMC remains available if non-Gaussian priors are
   ever needed (`use_real_mcmc` future hook noted in `bayesian_with_priors.py`).
