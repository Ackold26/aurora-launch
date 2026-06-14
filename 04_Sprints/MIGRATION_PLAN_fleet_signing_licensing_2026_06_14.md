# Migration Plan — Launch → Fleet signing & licensing unification

**Created:** 2026-06-14 · **Owner:** Маша маленькая (impl), Антон (backend + custody)
**Decision:** consolidate Launch onto the proven Econometrica/fleet stack for
**(A) update integrity** and **(B) licensing**; **keep** the Launch-unique
**(C) Methodology-Certificate signing** (no fleet equivalent), optionally
simplifying its key custody. Reverses ADR-007.

## Why (one paragraph)
Launch's "modern" mechanisms are half-built and depend on infra that does NOT
exist: the platform-core JWT licence needs an undeployed issuer backend (#52
Track B) + Launch would be its first unproven consumer; the `tauri-plugin-updater`
needs a minisign keypair that exists nowhere in the fleet. Econometrica solves
both, in production, across 7 products on ONE Supabase backend. Adopting the
fleet stack removes two bespoke technologies, eliminates new-backend work, and
unblocks the production installer. The Methodology Certificate (Ed25519,
regulatory reproducibility) has no fleet equivalent and stays.

---

## Target end-state

| Concern | From (Launch now) | To (fleet) |
|---|---|---|
| Update integrity | `tauri-plugin-updater` (minisign pubkey) | custom updater: SHA256 checksum in Supabase `app_versions` + GH Pages `rosst-updates/.../latest.json`, hosting GH Releases `aurora-releases` (110MB) |
| Licence | Rust IPC → Python `LaunchLicenseValidator` → `aurora_common.license` JWT SDK | Rust `online_auth.rs` (Supabase `/auth` + offline Ed25519 `license.rs`), product `launch` in `detect_product()` |
| Cert signing | local Ed25519, Veracrypt custody | **unchanged** (optional custody simplification — Phase D) |

---

## Phase 0 — Prep & decisions (~0.5 day; Маша + Антон)

0.1 Branch: `feat/fleet-unify-signing-licensing` off `feat/sprint-11-reuse-donors` (or main after that merges).
0.2 **Product mapping** (add `aurora-launch` to the fleet registry):
   - `CARGO_PKG_NAME` = `aurora-launch` · Supabase product id = **`launch`** · GH Pages folder `rosst-updates/launch/` · Storage/GH-Releases name `Aurora.Launch_X.Y.Z_x64-setup.exe` · `detect_product()` → `"launch"`.
   - Add row to `aurora-release-update` skill mapping table.
0.3 **Tier → cabinet mapping** (Антон approves the licence model):
   - Starter → `cabinets = ["launch_core","launch_proxy_single"]`
   - Pro → `+ "launch_proxy_multi"` (+ enterprise extras: white-label, telemetry export)
   - UI feature-gates read `cabinets` (membership test) instead of JWT tier flags.
0.4 **Backend prep (Антон / Supabase MCP)** — gating external dependency:
   - `app_versions`: INSERT row `product='launch'` (placeholder until first publish).
   - `licenses_product_check` + `content_versions_product_check` constraints: add `'launch'`.
   - `auth` Edge Function: add `launch` branch to `detect_product` + cabinets/`expires_at` response (mirror an existing product). Deploy (keep `verify_jwt` as-is).
   - Issue **one test licence** for product `launch` (machine fingerprint of a dev box) → for Phase B integration smoke.
   - Confirm the **fleet licence Ed25519 public key** (the one `license.rs` verifies against) — Launch must embed the SAME key so the same backend issues its licences.

---

## Phase A — Updater migration (plugin → checksum) (~1 day) — DO FIRST

> Self-contained, unblocks the production installer (removes the build.rs pubkey gate).

**Cargo (`src-tauri/Cargo.toml`):**
- ADD: `reqwest = { version = "0.12", default-features = false, features = ["rustls-tls","json","stream"] }`, `futures-util = "0.3"`, `obfstr = "0.4"` (or skip obfstr → plain const URLs), `log` (if not present).
- REMOVE: `tauri-plugin-updater = "2.0"`.

**Add `src-tauri/src/commands/updater.rs`** (copy-adapt Econometrica `updater.rs`):
- Port verbatim: `VersionInfo`, `check_supabase`, `check_github_pages`, `check_for_updates`, `download_update` (progress events via `tauri::Emitter`), `verify_checksum` (SHA256), `is_newer` (+ its 3 unit tests — prerelease-aware, the `8dfc631` fix).
- Adapt to Launch: endpoints → `…supabase.co/functions/v1/app-update` + `ackold26.github.io/rosst-updates/launch/latest.json`; `apply_update` sidecar stop → Launch's `SidecarManager` shutdown (NOT `econ_sidecar::stop_sidecar`); errors → Launch `AuroraError` (add `UpdateFailed{code,msg}` variant or reuse `Other`).
- Register Tauri commands in `lib.rs`: `check_for_updates`, `download_update`, `apply_update`.

**Remove plugin wiring:**
- `lib.rs`: drop `.plugin(tauri_plugin_updater::Builder::new().build())`.
- `tauri.conf.json`: delete `plugins.updater` block (the `active/endpoints/pubkey EMBED_AT_RELEASE_TIME`).
- `capabilities/default.json`: remove `updater:default/allow-check/allow-download/allow-install`.
- `build.rs`: **REMOVE the `AURORA_UPDATER_PUBKEY` production gate** (lines ~36-62) — no longer needed (checksum model). Keep `AURORA_BUILD_PROFILE` embed.

**Frontend rewrite (`frontend/src/lib/components/`):**
- `UpdateAvailableBanner.svelte`: replace `import('@tauri-apps/plugin-updater').check()` → `invoke('check_for_updates',{currentVersion})`; `update.downloadAndInstall(cb)` → `invoke('download_update')` + `listen('update-progress', …)` for the bar + `invoke('apply_update')`. Keep banner states (idle/available/downloading/error).
- `RefreshAvailableBanner.svelte` / `+layout.svelte`: rewire if they touch the plugin (content-refresh banner may be separate — verify).
- `UpdateAvailableBanner.test.ts`: swap `vi.mock('@tauri-apps/plugin-updater')` → mock `@tauri-apps/api/core` `invoke` + `@tauri-apps/api/event` `listen`.

**Gates:** `cd src-tauri && cargo test` (incl. `is_newer` tests) · `cd frontend && npx vitest run UpdateAvailableBanner` · `npm run check` (svelte) · build smoke `npm run tauri:build` (now succeeds in **production** profile too — gate gone).

**Backend publish (Антон, per `aurora-release-update` skill):** GH Release `aurora-releases` (110MB) + `app_versions` row (version/download_url/checksum/notes) + `rosst-updates/launch/latest.json`.

**Commit:** `refactor(updater): migrate Launch to fleet checksum updater (drop plugin-updater + minisign)`.

---

## Phase B — Licence migration (platform-core JWT → fleet online_auth) (~2-3 days)

**Bring crypto:** copy `src-tauri/src/crypto/fingerprint.rs` (+ minimal `crypto/mod.rs`) from Econometrica → Launch. (Ed25519 verify reuses Launch's existing `ed25519-dalek`.)

**Add `src-tauri/src/commands/online_auth.rs`** (copy-adapt, 433-line donor):
- `AuthRequest`/`AuthResponse`/`HeartbeatRequest`, `supabase_url()`, 24h cache (`CachedAuth`), `detect_product()` → returns `"launch"` for `CARGO_PKG_NAME=="aurora-launch"`, online `/auth` with offline fallback.
- Strip Econometrica-only response fields not used by Launch (vault/content-pack/frontend versions) — keep `status`, `cabinets`, `expires_at`, `app_min_version`, `update_required`, `update_url`.

**Replace `src-tauri/src/commands/license.rs`** (current IPC-shell → offline Ed25519, 331-line donor):
- Port Ed25519 JSON licence verify: licence file (`%APPDATA%\pro.auroraai.launch\license.json`), `expires_at`, machine fingerprint binding, `cabinets`, signature over canonical JSON, embed the **fleet licence pubkey** (Phase 0.4).
- Keep public command surface (`current_license_status`, `has_feature`, `require_feature`, `is_dev_build`) but back it with online_auth+license (Rust), NOT the Python sidecar. `has_feature(f)` = membership of `f` in resolved `cabinets`. Preserve fail-closed (no/expired/invalid licence → deny).
- Keep the `AURORA_LAUNCH_LICENSE_BYPASS` + `AURORA_BUILD_PROFILE==dev` double-gate (port to Rust if not already; build.rs already embeds profile).

**Retire Python licence path (additive-then-switch):**
- Deprecate `engines/license_validator.py` + the sidecar `get_license_status`/`has_license_feature` handlers (remove after Rust path verified live). Drop the planned `aurora_common.license` activation (#52 Track B obsolete).
- ⚠️ DO NOT touch `persistence/encryption.py` keyring (DB-encryption key — different concern).

**lib.rs:** register `online_auth` startup check (auth on launch, cache); license commands now Rust-only.

**Gates:** `cargo test` (+ port `is_expired`/fingerprint/offline-fallback unit tests) · **integration smoke on the real test licence** (Phase 0.4): online validate, offline-grace (Ed25519 cache), expiry, machine-mismatch reject, feature-gate both tiers · `npm run check` · `vitest` (license-UI tests updated to invoke-mocks).

**Backend (Антон):** `auth` Edge Function `launch` branch live; constraints updated; test licence issued.

**Commit(s):** `feat(crypto): port fingerprint` · `refactor(license): migrate Launch to fleet online_auth + offline Ed25519` · `chore(license): retire Python LicenseSDK path`.

---

## Phase C — ADRs & docs (~0.5 day, alongside A/B)

- **Rewrite ADR-007** Decision → "Adopt Econometrica `online_auth` for licence" with the new argument (fleet backend exists & is proven; Launch's JWT path needs an undeployed issuer + first-consumer risk; one backend, not two). Status: Accepted (supersedes the prior decision).
- **New ADR-008** — "Update integrity: fleet SHA256-checksum updater, drop `tauri-plugin-updater`/minisign."
- Update `06_References/COMMERCIAL_READINESS_EXTERNAL_STEPS.md`: Track A/B become "onboard `launch` to fleet pipeline" (no new infra), not "build keys/backend."
- `CHANGELOG.md` + memory.

---

## Phase D — Cert custody simplification (~0.5 day, SEPARATE, optional)

Methodology-Certificate **signing tech unchanged** (local Ed25519). Decision for Антон:
- **(a)** Simplify custody to `~/.secrets/rosst_launch_private.key` (Ed25519, same pattern as content-keys) + embed pubkey like the fleet — lighter, consistent.
- **(b)** Keep the Veracrypt+USB+safe ceremony (F1) for pharma-regulatory rigor.
Recommendation: (a) for pilot; revisit (b) if a regulator demands sealed-envelope custody. Either way, replace the `EMBED_AT_RELEASE_TIME` placeholder in `methodology_cert.rs:84` with the real pubkey (and/or wire it via build.rs) at release.

---

## Sequencing, estimates, risk

**Order:** Phase 0 → **A (updater, unblocks installer)** → B (licence) → C (docs) → D (separate). A and B both gated on Антон's backend (0.4) for publish/smoke; code can land behind it.

**Estimate:** A ~1d · B ~2-3d · C ~0.5d · D ~0.5d → ~4-5 days impl + Антон backend (~2-3h).

**Risks & mitigations:**
- Plugin removal leaves dangling refs → grep `plugin-updater`/`updater:` across src+frontend+conf+capabilities after removal; cargo+svelte gates catch.
- Licence rewrite touches enforcement → fail-closed preserved; test BOTH tiers + offline + expiry + bypass-gate; additive-then-switch (keep Python until Rust live-verified).
- Fleet licence pubkey mismatch → confirm the embedded pubkey == backend issuer key (0.4) before retiring Python path.
- Backend Edge Function edit must not break other products' `detect_product` → add a `launch` branch only, deploy, smoke an existing product too.
- Frontend updater UX parity → keep banner states; manual install/upgrade smoke on a VM.

**Rollback:** per-phase commits; updater = re-add plugin + conf/capabilities; licence = revert to Python path (kept until switch). No destructive backend ops (additive rows/branches).

**Definition of done:** production installer builds (no pubkey gate); auto-update works end-to-end via checksum (VM smoke N-1→N); licence validates online + offline on the fleet backend (test licence, both tiers); ADR-007 rewritten + ADR-008 added; cert signing unchanged.
