# ADR-008: Update integrity — fleet SHA256-checksum updater, NOT tauri-plugin-updater/minisign

**Status:** Accepted
**Date:** 2026-06-14
**Authors:** Маша маленькая (Opus 4.8), Антон (decision owner)
**Sprint context:** Fleet signing & licensing unification migration (see
`04_Sprints/MIGRATION_PLAN_fleet_signing_licensing_2026_06_14.md`).
**Relation:** Pairs with the licence half of the same migration (rewrites
**ADR-007** — done separately in Phase B).

## Context

Aurora Launch shipped the official `tauri-plugin-updater`, which authenticates
updates with a **minisign** signature: `tauri.conf.json` embeds a `pubkey` and
the plugin refuses any update whose `.sig` does not verify. `build.rs` enforced
this with a production gate (`BLOCKER-3`): a release build **panicked** unless
`AURORA_UPDATER_PUBKEY` was set to a real 64-char Ed25519 hex key.

That key **does not exist anywhere in the fleet** — no minisign keypair was ever
generated, and the placeholder `pubkey = "EMBED_AT_RELEASE_TIME"` shipped in the
config. Consequence: the **production installer could not be built at all** (the
build.rs gate aborted), and even if forced, the placeholder pubkey is fail-safe
(it refuses every update — auto-update never works). The updater was a
half-built mechanism depending on infra that was never stood up.

Meanwhile the rest of the Aurora fleet (7 products: Econometrica, Legal,
Creative-Hub, Smart Analytica, Oracle, DocMaster, …) ships auto-update in
**production** with a different, proven model: a **SHA256 checksum** delivered in
the server JSON. The client downloads the installer, hashes it, and refuses to
run it unless the hash matches `checksum` from the server. Integrity comes from
the trusted HTTPS channel + checksum, not from a signature plugin. One Supabase
backend (`app_versions` table, Edge Function `app-update`) with a GitHub Pages
`latest.json` fallback serves all of them. No minisign keypair, no custody
ceremony, no per-product key.

## Decision

**Adopt the fleet SHA256-checksum updater for Aurora Launch. Remove
`tauri-plugin-updater` and the minisign pubkey gate entirely.**

Concretely (Phase A of the migration):
- Port Econometrica's `commands/updater.rs` (checksum model) into Launch,
  adapted to Launch's `AuroraError` and `SidecarManager` shutdown.
- Endpoints: Supabase `…/functions/v1/app-update` (primary) + GitHub Pages
  `ackold26.github.io/rosst-updates/aurora-launch/latest.json` (fallback).
- Product id = `env!("CARGO_PKG_NAME")` = **`aurora-launch`** (fleet convention:
  the updater queries with the raw cargo package name — distinct from the short
  `detect_product()` name used for licensing; this matches the `app_versions`
  row and the GH-Pages folder).
- Remove the plugin wiring: `lib.rs` builder, `tauri.conf.json` `plugins.updater`,
  `capabilities/default.json` `updater:*`, the `tauri-plugin-updater` Cargo +
  npm dependencies, and the **`build.rs` `AURORA_UPDATER_PUBKEY` production gate**.
- Frontend `UpdateAvailableBanner.svelte` calls the Rust IPC commands
  (`check_update` / `download_update` / `apply_update`) + listens for
  `update-progress`, instead of the plugin's `check()` / `downloadAndInstall()`.
- Integrity is verified in Rust (`verify_checksum`, SHA256) — `download_update`
  refuses an empty/mismatched checksum.

The Methodology-Certificate Ed25519 signing (regulatory reproducibility) is a
**separate** concern and is unchanged by this ADR.

## Consequences

### Positive
- **Production installer unblocks immediately** — no minisign keypair, no
  `build.rs` panic. (`AURORA_BUILD_PROFILE=production cargo build --release`
  now succeeds with no `AURORA_UPDATER_PUBKEY`.)
- Removes a bespoke technology + a non-existent-infra dependency; converges on
  the proven fleet stack (one backend across 8 products now).
- Onboarding to the fleet is backend-only (a row in `app_versions` + a GH-Pages
  `latest.json`), no new keys or services — see Track A.
- Sidecar file-lock safety preserved: `apply_update` stops the `SidecarManager`
  before launching the installer, and a new `installer_hooks.nsh` PREINSTALL
  `taskkill` is the safety net (Launch had none — Econometrica's hook also adds
  loopback firewall rules, omitted here because Launch uses a stdin/stdout
  sidecar, not an HTTP one).

### Negative / trade-offs
- Integrity now relies on **HTTPS + SHA256 checksum**, not an offline signature.
  Threat model: an attacker who controls BOTH the TLS channel AND the server
  JSON could substitute installer+checksum together. This is the accepted
  fleet-wide posture (the checksum defends against corrupted/MITM-without-server
  downloads + accidental mismatch; the server + TLS are the trust root). Minisign
  would defend the additional "compromised server" case — revisit if a regulator
  or threat reassessment demands signed updates. `THREAT_MODEL.md §3.6` updated.
- The download URL must be HTTPS to a controlled host (GH Releases /
  `aurora-releases`, signed Supabase Storage URL) — enforced operationally, not
  cryptographically.

### Neutral
- Installer hosting moves to GitHub Releases (`Ackold26/aurora-releases`, the
  fleet pattern for ≥50 MB binaries — Launch is ~110 MB) referenced from the
  `app_versions` row / `latest.json`.

## Alternatives Considered

### Option A: Keep `tauri-plugin-updater`, generate a minisign keypair
- Pros: offline signature integrity (defends compromised-server case).
- Cons: requires a key-generation + custody ceremony that does not exist in the
  fleet; makes Launch the only product on a different updater; keeps the
  build.rs gate / placeholder-pubkey footgun. Higher operational burden for a
  threat (compromised Supabase + TLS) outside the current model.
- Why not chosen: cost/complexity ≫ benefit at pilot/early-sales stage; diverges
  from the fleet.

### Option B: Fleet SHA256-checksum updater — **CHOSEN**
- Pros: unblocks the production installer now; proven in production on 7 products;
  one backend; zero new key custody.
- Cons: integrity tied to HTTPS+checksum, not signature (see trade-offs).

### Option C: Disable auto-update for the pilot
- Why not chosen: the pilot needs a working update path to ship fixes during the
  engagement; "off" defers, doesn't solve, and leaves the build.rs gate blocking
  the installer regardless.

## Remaining work (EXTERNAL / Anton — Track A)
1. **Done (this session):** `app_versions` row `product='aurora-launch'`
   (placeholder v0.2.5, empty URL) inserted; no Edge Function change needed
   (`app-update` is product-agnostic).
2. On first real publish: upload the installer to GitHub Releases
   (`aurora-releases`), then `UPDATE app_versions` for `aurora-launch` with the
   real `version` / `download_url` / `checksum` (SHA256), and publish
   `rosst-updates/aurora-launch/latest.json`. Add `launch` to the
   `aurora-release-update` skill mapping table.
3. VM smoke: install N-1, publish N, confirm banner → download → checksum verify
   → install → relaunch end-to-end.

See `06_References/COMMERCIAL_READINESS_EXTERNAL_STEPS.md` (Track A) for the
step-by-step.
