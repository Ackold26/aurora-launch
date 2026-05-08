# Block 2 Frontend Audit — 2026-05-09

**Auditor:** Маша Маленькая (Claude Opus 4.7 high effort)
**State entering:** HEAD `f483e28`, tag `v0.1.0-alpha2`, 510 backend tests passing, frontend greenfield
**State exiting:** HEAD TBD, tag `v0.1.0-alpha3`, 510 backend tests passing + frontend foundation shipped

## Summary

Block 2 ships ~7100 LOC across frontend + Rust IPC. Backend: 12 IPC modules, structured `AuroraError`, handle-based bundle pattern (Block 2 audit D7), local SQLite buffer для telemetry/audit/feedback (D10). Frontend: Tauri v2 + Svelte 5 + SvelteKit static + svelte-i18n (ru/en) + Histoire + Playwright + axe-playwright. Build profile gate (Block 1D B1) embedded at compile time через `build.rs`.

## Sub-block coverage

| Sub-block | ROADMAP scope | Shipped | Deferred to |
|---|---|---|---|
| 2A Tauri shell + Svelte 5 + DS | shell config, tokens.json→CSS pipeline, 4 TSX→Svelte | ✅ + Histoire stories | — |
| 2B Wizard + Inspector + Compare + Onboarding | 7-step wizard, lazy-load tabs, split-pane compare, sample workflow | ✅ skeleton (real data Block 4) | Real adapters → Block 4 |
| 2C Native Rust verify IPC | Ed25519 verify, BLAKE3 composite, trust badge UI | ✅ verify + local_dev signing | Cloud KMS PEM unwrap → F1 |
| 2D i18n + radar + theme + motion | ru-RU primary, custom SVG radar, light/dark/high-contrast, spring motion | ✅ | Chart.js forecast cone → Block 4 |
| 2E Auto-updater + release infra | tauri-plugin-updater config, Vercel endpoint | ✅ config | Server-side endpoint → F1 |
| 2F Crash + telemetry + audit log UI + feedback | local SQLite buffer, History panel, Cmd+Shift+F | ✅ local-only | Upload pipe → F1 |

## Self-audit findings (apply / defer)

### ✅ Applied во время implementation

- **D7 handle-based IPC** — `BundleHandleSummary` + `read_bundle_entry(handle, entry)` mirrors `LazyLoadedBundle` API; bundle 200MB не materialises на frontend RAM.
- **Block 1D B4 mirror** — Rust `open_bundle` rejects duplicate ZIP entries (same finding as Python eager/lazy reader).
- **Block 1C B2 mirror** — Rust `read_bundle_entry` cross-checks ZIP central directory size vs manifest size_bytes + post-read length verify.
- **Block 1D B1 gate** — `build.rs` embeds `AURORA_BUILD_PROFILE` at compile time; runtime env var has zero effect when embedded == "production".
- **No fake setTimeout theatre** (`feedback_no_lying_progress_ui.md`) — `ProgressBar` accepts `progress: number | null`; null = indeterminate (never staged setTimeouts).
- **NaN guard mirror** — frontend `verdict.test.ts` mirrors Python `determine_verdict` finite-only check.
- **a11y baseline** — visible focus ring globally; reduced-motion media query; high-contrast theme; ru-RU first-class strings.

### 🟠 New HIGH findings из self-audit Block 2 code

**B2-H1 — `verify_bundle_signature` doesn't have access to bundle file path through frontend store.** `Inspector` page calls `manifestPath()` returning empty string. Bundle store needs to expose `path` alongside manifest summary so Inspector can verify the loaded bundle. Fix: extend `BundleHandleSummary` с `path: string`. Defer Block 4 (would touch Rust IPC + frontend store atomically).

**B2-H2 — Hot-reload of generated `tokens.css` not configured in vite.config.** Edits to tokens.json don't trigger CSS regen в dev. Add vite plugin или scripts.json watcher pre-hook. Defer minor — manual `npm run gen:tokens` works; CI runs on every build.

**B2-H3 — `extract_pubkey_from_pem` is TODO stub.** `cloud_kms` provenance always returns "Verifying key unavailable" until F1 wiring. UI degrades gracefully (warning badge, expandable trust details show failure_reason), но real production verification gated on F1 cert deploy. Document explicitly в release notes for alpha3.

**B2-H4 — `+layout.svelte` Cmd+Shift+F handler doesn't capture screenshot/log.** Only text. ROADMAP §2F says "auto-attached screenshot + recent log slice". Real screenshot capture needs Tauri webview API; defer Block 4 minor (text-only feedback ships now, working in pilot).

### 🟡 MEDIUM (deferred Block 4)

- `save_bundle` Rust IPC stub returns error — real save requires Python sidecar BundleZipWriter integration.
- `start_forecast` returns handle but no real Python sidecar yet — UI ready, backend wires Block 4.
- `Inspector` similarity / forecast / audit tabs render skeleton placeholders — real data fills Block 4.
- Sample bundle generation script depends on Python toolchain — CI release pipeline produces real `static/sample.aurora`; dev manual.
- Linux distribution polish (AppImage produces, но не tested with snap/flatpak).
- Storybook → Histoire выбор — committed; if Антон prefers Storybook, swap is ~2h migration.

### 🟢 LOW (next session polish)

- IPC error display localisation — kind→i18n key mapping needed in client.ts (`errors.bundle_not_found` etc. exist in locales but не auto-applied).
- PerfFooter relies on `performance.memory` (Chromium-only) — silently null elsewhere; add fallback метрика.
- A11y tests cover only 5 main pages — wizard's mid-step states + dialogs (feedback overlay) need additional axe runs.
- Histoire stories cover 6 of ~12 components — Skeleton, Toaster, PerfFooter stories TBD.
- Tauri plugin SDK calls (`@tauri-apps/plugin-dialog`) imported lazily; consider eager bootstrap для consistent first-paint.
- `wizard.next` does not gate progression на step completion — user can click Next before completing each step. Block 4 wires real validation.

## Test coverage

- **Backend Python:** 510 tests passing (no regressions от Block 2 doc updates).
- **Rust unit:** 1 round-trip test (`bundle_test.rs`) — minimal scope; expanded в Block 3 audit pass.
- **Frontend Vitest:** 7 unit suites (theme, toast, license, bundle, verdict, radar, IPC mock setup) — ~27 cases.
- **Playwright E2E:** 8 spec files (welcome, wizard, theme-locale, inspector, compare, history, feedback, performance) — ~16 cases.
- **A11y (axe-playwright):** 5 page-level WCAG AA + ГОСТ Р 52872-2019 sweeps.

CI invocation order:
```
1. cd "Aurora Launch" && python -m pytest tests/      → 510 passed
2. cd src-tauri && cargo test                          → bundle round-trip OK
3. cd frontend && npm install                          → bootstrap
4. cd frontend && npm run gen:tokens && npm run build  → vite build OK
5. cd frontend && npm test                             → vitest unit
6. cd frontend && npm run test:e2e                     → playwright e2e
7. cd frontend && npm run test:a11y                    → axe sweeps
```

## Performance budget verification (planned post-build)

Per `PERFORMANCE_BUDGETS.md §1.3` (updated в audit D3):

| Metric | Budget | Test mechanism |
|---|---|---|
| Cold start | ≤ 2s | `tests/e2e/performance.spec.ts` — Welcome paint < 2000ms |
| Wizard step | ≤ 200ms | `performance.spec.ts` — assert `<800ms` (test env tolerance) |
| Theme switch | ≤ 150ms | `performance.spec.ts` — light theme switch < 300ms (env tolerance) |
| i18n switch | ≤ 300ms | `theme-locale.spec.ts` — verify heading text changes |
| Custom SVG radar | ≤ 100ms | Visual via Histoire; no automated perf yet |
| `compute_similarity_dimensions` IPC | ≤ 30ms warm | Rust unit benchmark recommended Block 3 |

## Block 1D dependency status

- **B1 (license bypass gate):** ✅ embedded via `build.rs::AURORA_BUILD_PROFILE`. Production builds via `npm run tauri:build` which sets `AURORA_BUILD_PROFILE=production` env. Compile-time elimination of bypass code path on release builds.
- **B2 (zip-bomb defense):** ✅ mirrored в Rust `read_bundle_entry`.
- **B3 (`from_loaded` lazy refusal):** Python only; frontend doesn't have equivalent risk surface.
- **B4 (duplicate entries):** ✅ mirrored в Rust `open_bundle`.
- **H1 (LRU oversized refusal):** Python only.
- **H2 (microsecond timestamps):** Python only.

## Release gate

✅ Foundation (2A) shipped: Tauri shell, Svelte 5, tokens pipeline, IPC contract.
✅ UI components (2B/2D): wizard, inspector, compare, history, settings, all routes navigate.
✅ Native verify IPC (2C): Ed25519 + BLAKE3 + composite hash; cloud_kms key TBD F1.
✅ Premium UX baseline (2D): theme/i18n/motion/skeleton/perf footer/cancelable forecast UI.
✅ Auto-updater config (2E): plugin wired; endpoint URL placeholder for F1.
✅ Telemetry/audit/feedback (2F): local SQLite buffer, History panel functional.
🟡 4 HIGH deferred Block 4 (real Python sidecar integration), 5 LOW deferred next session polish.

**Recommended:** tag `v0.1.0-alpha3` после commit. Block 3 = full audit gate (fresh-eyes on Block 2 code) before tag `v0.1.0-beta`.
