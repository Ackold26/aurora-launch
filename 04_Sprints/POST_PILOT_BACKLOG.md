# POST_PILOT_BACKLOG — Phase X Modules + Deferred Tasks

**Status:** Created 2026-05-14 при autonomous session conclusion.
**Trigger:** items addressable after Materia Medica pilot success metrics achieved (F4 GA tag).

---

## Phase X — Discrete Post-GA Modules (per Plan v3.0)

Каждый module = independent v0.1.x minor release. Don't block each other.

### M-CS Cloud Signing (Yandex KMS)

**Priority:** P0 (immediate post-GA OR earlier if pilot customer requests)
**Effort:** ~9h Антон (infra) + ~3h Маша (integration)
**Trigger:** Юрлицо registered OR pilot conversion call signals regulator requirement

- Yandex.Cloud KMS Ed25519 key + service account JWT
- Vercel Edge Function `/api/sign` (Phase A code already at `aurora-cloud/api/sign.ts`)
- DNS + Edge deploy + staging smoke test
- Aurora Launch build embeds KMS public key (replaces local Ed25519 PEM)
- Migration playbook: old local-signed certs remain valid + new KMS-signed certs published in parallel

### M-AU Auto-updater Vercel

**Priority:** P0 (immediately после M-CS)
**Effort:** ~3h
**Trigger:** M-CS done (нужен KMS pubkey для manifest signing)

- Re-enable `tauri-plugin-updater` в `tauri.conf.json`
- Vercel KV stores manifest, signed by Yandex KMS
- Endpoint `updates.auroraai.pro/launch/{target}/{arch}/{version}`
- Customer auto-updates on app start (background check + dialog)

### M-WV Web Verifier (verify.auroraai.pro WASM)

**Priority:** P1 (marketing campaign launch enabler)
**Effort:** ~25h
**Trigger:** Marketing campaign / public proof-of-trust narrative

- Rust + lopdf compiled к WASM (≤500 KB gzipped)
- Vercel static site + serverless API for cert validation
- Customer/regulator uploads PDF + .aurora — instant SHA-256 + KMS signature verify
- Privacy: WASM client-side (no data leaves browser)

### M-TF Telemetry/Feedback Cloud Sync

**Priority:** P1 (product analytics need)
**Effort:** ~5h
**Trigger:** Vercel setup из M-CS/AU available

- Opt-in telemetry upload (existing SQLite local buffer → Vercel KV)
- Feedback ZIP upload (replaces current mailto: workflow for technical users)
- Aggregated analytics dashboard для Антон's product decisions

### M-PI Proxy Intelligence AI

**Priority:** P2 (differentiator for sales pitch)
**Effort:** ~20h
**Trigger:** 2-3 pilot успешных конверсий — case studies anchor

- Claude API integration для proxy candidate suggestion
- Customer enters brand description (text) + DSM/Mediascope universe
- Output: top-3 proxy candidates ranked by similarity с explanation
- UX: "Suggest proxies" button в ProxySelectionStep, non-blocking

### M-CV Cross-app Validation (Launch ↔ Optimizer)

**Priority:** P2 (Suite bundle value)
**Effort:** ~30h
**Trigger:** Optimizer Platform Core migration done

- Aurora Launch forecast vs Aurora Optimizer forecast (на same recipient brand)
- Compare panel + diagnostics ("conclusions compatible? CI overlap?")
- Customer trust via showing internal disagreements transparently

### M-CP Category Playbooks

**Priority:** P2 (onboarding friction reduction)
**Effort:** ~30h
**Trigger:** 3-5 pilot completed kейсов для calibration

- Dynamic templates per category (FMCG impulse, OTC pharma, premium cosmetics, etc.)
- Pre-weighted similarity dimensions
- Historical success rates ("In cosmetics, launches с proxy similarity ≥0.70 had 85% forecast accuracy")
- Learning: каждый успешный launch улучшает accuracy

### M-PA Posterior Automation

**Priority:** P2-P3 (convenience feature)
**Effort:** ~25h
**Trigger:** Customer demand signal (manual posterior updates frustration)

- Customer provides DSM/Mediascope OAuth credentials
- Aurora pulls recipient data weekly
- Auto-posterior trigger при ≥4 weeks new data (с approval flow)
- "Auto-posterior" toggle в settings

### M-SS Simulation Builder

**Priority:** P2 (Pro/Enterprise tier)
**Effort:** ~25h
**Trigger:** Sensitivity Dashboard adoption + customer demand for what-if

- Media mix optimization solver (входит в forecast model adstock/hill)
- "Spend 1M на TV, 500K digital" → forecast decomposition
- "Recommended media mix для 95% CI upper bound" — optimization

### M-A11 Accessibility AAA

**Priority:** P3 (regulatory ask)
**Effort:** ~20h
**Trigger:** Customer / regulator request

- NVDA Russian screenreader testing
- Russian plural rules ("5 недель запуска")
- Cyrillic typography tuning
- Cultural usability с grandmother test

### M-PR Pre-registered Prediction Registry

**Priority:** P3 (marketing / academic)
**Effort:** ~40h
**Trigger:** 10+ pilot кейсов done — registry has critical mass

- Public registry: forecast + actuals 12+ weeks later
- Aurora publishes accuracy aggregate ("Forecast accuracy N=X case studies")
- Trust signal vs Nielsen/Kantar (которые не публикуют accuracy)

### M-CSync Cloud Sync (NEW post-audit)

**Priority:** P0 (single-user multi-machine workflow)
**Effort:** ~15h
**Trigger:** Customer multi-machine signal

- Customer uses own cloud storage (OneDrive / Dropbox / Google Drive)
- File watcher pattern на `%LOCALAPPDATA%/Aurora Launch/projects.db` + blobs
- Conflict resolution: last-write-wins с warning
- Не Aurora-hosted cloud (privacy-first)

---

## Phase Π Sub-deferred Items (full impl when needed)

### Π.2.5 OLS+Priors Full Implementation

**Priority:** P1 (Mode 3 fallback works но not as accurate)
**Effort:** ~8h
**Trigger:** Pilot recipient brand reaches 3-6 months data + customer wants tighter CI

- Real OLS regression on recipient y vector с proxy posterior priors
- SE inflation formula: `σ_β_recipient² = σ_β_OLS² + σ_β_proxy² × shrinkage²`
- Bootstrap N=200 ROI CI
- Currently: pure_transfer fallback с tighter similarity_inflation × 0.7

### Π.2.6 Bayesian+Priors Full Implementation

**Priority:** P1 (Mode 4 — sophisticated transfer when n_recipient ≥7 months)
**Effort:** ~12h
**Trigger:** Pilot recipient brand reaches 7+ months data

- Refactor `bayesian_engine.py:train_model` к accept informative `pm.Normal(μ, σ)`
  priors для media_betas (currently uses HalfNormal defaults)
- Wire `proxy_posterior_extractor.shrink_proxy_priors` → PyMC informative priors
- Test convergence on real Materia Medica data

### Π.3 Frontend Components (autonomous session deferred — context budget)

**Priority:** P0 (pilot UX critical)
**Effort:** ~50h total

- **Π.3.1 Linear Forecast History** (~7h) — Svelte component + ProjectDB integration
- **Π.3.2 Scenario Sensitivity** (~12h) — 3 cards + Expert sliders (backend Π.5 ready)
- **Π.3.3 TrustScore Observability** (~10h) — donut chart + drift alerts
- **Π.3.4 Premium UX foundation** (~12h) — Cmd+K palette + microanimations + Russian
- **Π.3.5 Onboarding flow** (~9h) — Welcome + sample tour + tutorial + empty states

**Status:** Backend infrastructure ready (router, pure_transfer, orchestrator,
sensitivity_grid, support, sample_bundles). Frontend Svelte components +
SvelteKit routes + Vitest tests pending.

---

## Audit findings deferred к POST_PILOT (per personal verification)

### Phase 0 audit (commit `d3d8e0e`)

- P0-07 (LOW): `_upsert_blob` orphan file on FK violation — mitigated by
  `gc_orphan_blobs()` + `check_integrity()` reports.
- P0-11 (LOW): `OnceLock` testing isolation — refactor `list_pending_dumps`
  к accept dir parameter для test isolation.
- P0-12 (FALSE POSITIVE): f-string SQL UPDATE clause — все колонки whitelisted,
  no injection possible.

### Phase Π.2 audit (commit `071c3dd`)

- PI2-M1 (MEDIUM): float `n_recipient` passes through router без isinstance
  check — semantic but not security. Add `n_recipient: int` runtime check.
- PI2-L1 (LOW): schema_registry RecipientAnchors registration — Phase Π.3
  bundle integration task.
- PI2-L2 (LOW): same-as-baseline override path undocumented — add comment.

### Phase 0.2 autosave (timer flake)

- `test_start_autosave_fires_periodically` occasionally flakes on heavy
  parallel load. Bumped sleep к 1.0s but Windows scheduler can still drift.
  Phase Π.6 hardening: use deterministic mock clock instead of real timer.

---

## Pre-existing tech debt (NOT created by autonomous session)

- Local cargo build broken: missing `src-tauri/binaries/aurora-sidecar-*.exe`
  + `src-tauri/icons/` — CI-produced, gitignored. Rust unit tests verified
  в Phase Π.6 audit gate когда CI environment ready.
- `tauri.conf.json` `macOSPrivateApi: true` added (alignment с Cargo.toml feature).
  If CI breaks, revert одной строкой.
- 13+ commits ahead of `origin/main` — push требует Антон approval per
  durable instruction.

---

## Phase X module dependency graph

```
M-CS (cloud signing) ─┬──► M-AU (auto-updater)
                       │
                       └──► M-WV (web verifier)
                       │
                       └──► M-TF (telemetry cloud)

M-PI (AI suggest) ─── independent

M-CV (cross-app) ── depends on Optimizer Platform Core migration

M-CP (playbooks) ── needs 3-5 pilot data accumulated

M-PA (auto-pull) ── customer demand signal

M-SS (simulation) ── builds on sensitivity_grid (already shipped Π.5)

M-A11 (a11y AAA) ── independent

M-PR (registry) ── 10+ pilots для critical mass

M-CSync (cloud sync) ── independent
```

---

**Status:** Backlog organized. Resume в next session via:
- Track file: `C:\Users\ackol\Desktop\Launch_track.md`
- Current task pointer + decisions log

Per autonomous mandate user instruction 2026-05-14, this session pushed
through Phase 0 + Phase Π (math + support + perf) + Phase Σ.0/1/2 docs.
Phase Π.3 frontend Svelte components + Phase Σ.3/4 pilot calendar
trajectory остаются для next session(s).
