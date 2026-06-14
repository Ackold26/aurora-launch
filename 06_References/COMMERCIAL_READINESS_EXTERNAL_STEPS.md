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

## Track B — License — MIGRATED to fleet online_auth + offline Ed25519 (ADR-007 REVERSAL)

**Reframed 2026-06-14 (fleet-unify migration):** the platform-core JWT plan below
is **obsolete**. Launch's licence client now uses the fleet model (Supabase
`/auth` cabinets + offline Ed25519 `license.json`), the same as Econometrica + 6
other products — see the **REVERSAL** note in ADR-007. No JWT issuer to deploy,
no `aurora_common` bundling.

**In code (✅, Phase B DONE — online live-verified):** `commands/online_auth.rs`
(Supabase `/auth`, `detect_product="launch"`, 24h cache, offline fallback) +
`commands/license.rs` (offline Ed25519, `has_feature` = cabinets membership,
fail-closed, dev-bypass gate) + `crypto/{fingerprint,ed25519}.rs`. Command surface
unchanged for the frontend. The online path is live-verified against prod with a
Starter test licence.

**Backend done (✅, this session):** `licenses_product_check` += `'launch'`; a
Starter test licence (cabinets `launch_core` + `launch_proxy_single`) issued for
the dev box fingerprint `c8780e…87e9f`. No Edge Function deploy needed (`auth` is
product-agnostic — cabinets come from the `licenses` row).

**External steps (⏳ — Anton):**

1. **Offline `license.json` for the integration smoke (long-pole):** sign a
   `license.json` for the dev fingerprint with the **fleet private key** (the
   gen_license pipeline / custody) — cabinets matching the test licence,
   `expires_at` `YYYY-MM-DD`, `machine_fingerprint_hash = c8780e…87e9f`. Drop it
   via the in-app **Import licence** (or `%APPDATA%\pro.auroraai.launch\license.json`)
   → then run the offline smoke: server-unreachable → `grace` state, expiry,
   machine-mismatch reject. Once green, **retire the Python licence path**
   (`engines/license_validator.py` + sidecar `get_license_status` /
   `has_license_feature`).
2. **Issue production licences** per customer/tier into the fleet `licenses` table
   (online) + a signed `license.json` (offline fallback). Tier → cabinets:
   Starter = `[launch_core, launch_proxy_single]`, Pro = `+ launch_proxy_multi`.
3. **Per-seat annual subscription** productization (`expires_at` supported) —
   pricing per `06_References/PRICING_TIERS.md`.

**Obsolete (removed by the ADR-007 reversal — do NOT do these):** bundling
`aurora_common`, deploying a JWT issuer backend, the `HAS_PLATFORM_CORE` flag, and
the `license_validator.py` JWT hardening notes (that Python path is being retired).

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
