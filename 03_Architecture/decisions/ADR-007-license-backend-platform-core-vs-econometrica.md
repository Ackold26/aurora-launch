# ADR-007: License backend — platform-core JWT SDK, NOT Econometrica online_auth

**Status:** ❌ SUPERSEDED (2026-06-14, same day) by the fleet signing & licensing
unification migration — Launch **DID** adopt the Econometrica/fleet `online_auth`
+ offline Ed25519 model. See the **REVERSAL** note below; the original decision
and its reasoning are kept for the record.
**Date:** 2026-06-14
**Authors:** Маша маленькая (Opus 4.8), Антон (decision owner)
**Sprint context:** Sprint 11 — commercial-readiness review

---

## ⛔ REVERSAL (2026-06-14, fleet-unify migration)

**New decision (supersedes the "Decision" section below): Aurora Launch adopts
the fleet `online_auth` (Supabase `/auth`, cabinets + `expires_at`) with an
offline Ed25519 `license.json` fallback — the same stack Econometrica + 6 other
products run in production. The platform-core `aurora_common.license` JWT path is
dropped.**

Why the original decision was reversed (Антон approved 2026-06-14):
1. **The decisive premise flipped.** The original ADR argued the JWT path was
   already-wired and low-risk. Re-examination found it depends on an **undeployed
   JWT-issuer backend** (#52 Track B) with Launch as its **first unproven
   production consumer** — i.e. it was *half-built on absent infra*, not a
   finished system. The fleet `online_auth` backend already exists and is proven
   across 7 products.
2. **The "doesn't unify Launch's cloud" counter-argument no longer holds.** The
   original ADR noted Launch's updater was on `updates.auroraai.pro` (minisign),
   so a Supabase licence wouldn't unify the cloud surface. **ADR-008 moved the
   updater onto the same fleet Supabase backend** — so adopting `online_auth` now
   *does* consolidate Launch onto ONE backend, eliminating two bespoke stacks.
3. **One backend, not two issuers to operate.** Deploying + running a separate
   JWT issuer for a single product is more operational surface than onboarding
   `launch` to the existing fleet `licenses` table (which is now done:
   constraint + test licence).

What this looks like in code (done — commits `6feed17`, `478e563`):
`commands/online_auth.rs` (Supabase `/auth`, `detect_product()="launch"`, 24h
cache) + `commands/license.rs` rewritten to offline Ed25519 (`license.json`,
fleet pubkey via `crypto/ed25519.rs`, machine binding, `has_feature` = cabinets
membership, fail-closed) + `crypto/fingerprint.rs`. The Python
`license_validator.py` path is left in place (additive-then-switch) until the
offline smoke on a real signed `license.json` confirms the Rust path, then retired.

**Live-verified:** the online path returns `status=ok` + the Starter test
licence's cabinets from the prod backend against this dev box's fingerprint.

The rest of this document is the **superseded original decision**, retained for
provenance.

---

## Context

Sprint 11 review identified license enforcement (`SPRINT_BUFFER #52`) as a
commercial blocker: Aurora Launch must sell by per-seat licence, so the licence
path must enforce paid features, not merely scaffold them.

During the review a reuse question was raised: Aurora Econometrica has a
**production-proven** licence/auth stack (`online_auth.rs` → Supabase
`/auth` + `/heartbeat` returning `cabinets` + `expires_at`, with an offline
Ed25519 JSON `license.rs` fallback) shipped to real customers (Кагоцел and the
wider ROSST / Aurora-AI family of 7 products via `detect_product()`). Why not
copy that proven system into Launch instead of relying on the platform-core
`aurora_common.license` SDK, which is unit-tested but has **no production
consumer yet** (Launch would be the first)?

The two systems use fundamentally different licensing models:

| | Econometrica `online_auth` | platform-core `aurora_common.license` |
|---|---|---|
| Model | cabinets + expiry date | JWT + tier feature-flags |
| Transport | Supabase Edge Functions | JWT issuer + Ed25519 verify |
| Enforcement side | Rust (`src-tauri`) | Python sidecar (`aurora_workflow` steps) |
| Offline | Ed25519 JSON fallback (24h cache) | 7-day offline grace (`OFFLINE_GRACE_DAYS`) |
| Production status | proven (multi-product) | tested, no consumer yet |

Critical fact discovered while reading the Launch codebase: Launch's
`src-tauri/src/commands/license.rs` is **already** a thin Rust IPC shell →
Python `LaunchLicenseValidator` (`engines/license_validator.py`) →
`aurora_common.license.LicenseSDK`. Enforcement was **already made real** in the
**C-3 closure (Phase 2.A)** — previously `current_license_status` was a hardcoded
stub; it now invokes the sidecar over real IPC and the Python side validates via
the JWT SDK. The feature-flag tiers Launch needs (`launch_proxy_single`,
`launch_proxy_multi`) are **already present** in `aurora_common.tier_matrix`.

The "same backend as the updater" consistency argument that applies to the
Econometrica family does **not** apply to Launch: Launch's auto-updater is the
official `tauri-plugin-updater` pointed at `updates.auroraai.pro` (minisign), not
the Supabase backend — so adopting Econometrica's Supabase licence would NOT
unify Launch's cloud surface, it would split it differently.

## Decision

**Aurora Launch stays on the platform-core `aurora_common.license` JWT SDK.**
We do NOT port Econometrica's `online_auth.rs` / cabinet model into Launch.

Rationale:
1. Launch's entire licence client is **already built and tested** against the
   JWT/tier model (`license_validator.py` adapter + `license.rs` IPC shell +
   C-3 enforcement closure). Switching to cabinets/Supabase = a destructive
   rewrite of working, shipped code for **no functional gain** (both models
   enforce; the JWT/tier model matches Launch's product design — paid features
   are tier flags, not cabinets).
2. platform-core is the intended cross-product SSOT for licence (see
   `SPRINT_BUFFER #51/#52` + shared-lib audit). Launch consuming it is
   **convergence**, not drift. (Econometrica's own stack is explicitly the
   legacy/parallel system per its CLAUDE.md rule 8.)
3. The "proven" advantage of Econometrica is its **backend + transport**, not
   its client model; that value is real but does not justify abandoning Launch's
   already-wired JWT client.

## Consequences

### Positive
- No rewrite of working code; C-3 closure preserved.
- Licence model matches Launch's tier-feature product design.
- Converges on the platform SSOT (anti-drift, #51/#52).

### Negative
- Launch is the **first production consumer** of `aurora_common.license` →
  before GA we MUST run an integration smoke on a real signed JWT token (not
  just the unit tests), and confirm offline-grace behaviour end-to-end.
- Depends on a **JWT issuer backend** that is not yet deployed for Launch
  (external — Anton). Until then production builds graceful-degrade to
  fail-closed (paid features denied).

### Neutral
- Econometrica keeps its own dual licence system unchanged; the two products
  deliberately use different licence backends. Acceptable — they are separate
  issuer/Supabase concerns, not shared runtime state.

## Alternatives Considered

### Option A: Port Econometrica `online_auth.rs` + `license.rs` (cabinets/Supabase)
- Pros: production-proven; live multi-product Supabase backend already running.
- Cons: cabinet/expiry model mismatches Launch's tier-flag design; enforcement
  would move to Rust, discarding the Python adapter + C-3 closure; destructive
  rewrite of tested shipped code; would NOT unify Launch's cloud surface (its
  updater is on `updates.auroraai.pro`, not Supabase).
- Why not chosen: high-risk rewrite for no functional gain.

### Option B: platform-core `aurora_common.license` JWT SDK — **CHOSEN**
- Pros: already wired + tested in Launch; matches product design; SSOT convergence.
- Cons: first production consumer (needs real-token integration smoke); issuer
  backend pending.

### Option C: Build a fresh Launch-only licence system
- Why not chosen: duplication; contradicts the entire platform-core shared-lib effort.

## Remaining work (`SPRINT_BUFFER #52` — EXTERNAL / Anton)
1. Activate `aurora_common` as a real bundled dependency in the production
   build; retire the `HAS_PLATFORM_CORE` graceful-fallback once available.
2. Deploy the JWT issuer backend (Ed25519 keypair + issue/refresh endpoint).
3. Integration smoke on a real signed token (online + offline-grace paths).
4. Per-seat annual-subscription productization (`expires_at` already supported).

See `06_References/COMMERCIAL_READINESS_EXTERNAL_STEPS.md` for the step-by-step.
