# Aurora Launch — Frontend

Tauri v2 + Svelte 5 + Vite + Histoire frontend for Aurora Launch desktop application.

## Status

- **Stack:** Tauri v2 (Rust backend), Svelte 5 (runes), SvelteKit (static adapter), Vite, svelte-i18n, Histoire, Playwright + axe-playwright
- **Block:** Block 2 (foundation + UI components + IPC + telemetry/audit log + tests)
- **Tag target:** `v0.1.0-alpha3` after Block 2 audit gate

## Layout

```
frontend/
├── src/
│   ├── app.css, app.html, app.d.ts        — global shell
│   ├── routes/                             — SvelteKit pages (welcome, wizard, inspector, compare, history, settings)
│   └── lib/
│       ├── components/                     — Svelte components + .story.svelte для Histoire
│       ├── stores/                         — Svelte stores (theme, license, bundle, toast)
│       ├── ipc/                            — typed IPC client wrapping @tauri-apps/api/core
│       ├── i18n/                           — svelte-i18n setup + ru/en locales
│       ├── styles/                         — generated tokens.css + base.css
│       └── types/                          — generated Pydantic→TS schemas
├── tests/
│   ├── unit/                               — Vitest tests (stores, helpers)
│   └── e2e/                                — Playwright E2E + a11y + perf
├── scripts/
│   ├── generate-tokens-css.mjs            — tokens.json → CSS custom properties
│   ├── generate-types.mjs                 — Pydantic → TS via export_typescript.py
│   └── build-sample-bundle.mjs            — synthesize FMCG sample bundle
├── static/                                 — assets bundled into Tauri (sample.aurora goes here)
├── histoire.config.ts                      — component gallery
├── playwright.config.ts                    — E2E + a11y projects
├── vite.config.ts, svelte.config.js, tsconfig.json
└── package.json
```

## Common scripts

```bash
npm install                           # bootstrap dependencies (CI или dev)
npm run dev                           # vite dev server (no Tauri)
npm run build                         # production build (frontend only)
npm run gen:tokens                    # regenerate src/lib/styles/tokens.css
npm run gen:types                     # regenerate src/lib/types/aurora-schemas.d.ts
npm run histoire                      # component gallery (port 6006)
npm run test                          # vitest unit suite
npm run test:e2e                      # playwright E2E
npm run test:a11y                     # axe-playwright accessibility
npm run tauri:dev                     # full Tauri shell + Rust backend
npm run tauri:build                   # AURORA_BUILD_PROFILE=production tauri build
npm run tauri:build:dev               # AURORA_BUILD_PROFILE=dev — bypass enabled
```

## Build profile gate (Block 1D B1)

License bypass (`AURORA_LAUNCH_LICENSE_BYPASS=1`) requires **two** env vars
simultaneously:

1. `AURORA_LAUNCH_LICENSE_BYPASS=1` (truthy)
2. `AURORA_BUILD_PROFILE=dev`

Production builds (`npm run tauri:build`) **always** set `AURORA_BUILD_PROFILE=production`
which is **embedded at compile time** через `src-tauri/build.rs`. Setting the env
var в production at runtime has zero effect — bypass code path is gated on the
embedded constant.

## IPC commands inventory

См. `src/lib/ipc/client.ts` для typed signatures. Backend implementations
в `../src-tauri/src/commands/`:

- `bundle` — open / close / list / read / get_manifest / save (handle-based)
- `similarity` — compute_similarity_dimensions / aggregate_score
- `forecast` — start / cancel / get_status (Block 4 wires real Python sidecar)
- `methodology_cert` — verify_bundle_signature / generate_local_dev_signature
- `license` — current_status / has_feature / require_feature / is_dev_build
- `telemetry` — log_event / list_events / get_opt_in / set_opt_in (local-only buffer)
- `feedback` — capture / list_pending (Cmd+Shift+F)
- `audit_log` — list_audit_entries
- `build_info` — get_build_info

## Development workflow

1. `cd frontend && npm install`
2. `npm run gen:tokens` — generate CSS from tokens.json (committed; auto-runs on build)
3. `npm run dev` для frontend-only iteration с mocked IPC
4. `cd .. && AURORA_BUILD_PROFILE=dev cargo run -p aurora-launch` для real Tauri shell
5. После changes к Pydantic schemas: `npm run gen:types`

## Block 2 deferred (handed to Block 4 / Block F1)

- Real forecast generation (Python sidecar via `tauri-plugin-shell` or sidecar binary)
- C7 cloud signing (Vercel Edge Function + KMS) — `verify_bundle_signature` works for
  `local_dev` and `sample` provenance; `cloud_kms` waits for F1 deploy
- Telemetry upload pipe to Vercel signed endpoint (events buffer locally now)
- Feedback upload to Vercel function → GitHub Issue (queued locally now)
- Real auto-update endpoint (`updates.auroraai.pro`) — config wired, server-side TBD
- Linux distribution polish (Block 2 ships Tauri config Linux-compatible; AppImage/DEB
  готовы); v0.1.1 backlog для Snap/Flatpak

## Testing strategy

- **Unit (Vitest)**: stores, helper functions, geometry. IPC mocked through
  `__setInvokeForTesting`. `tests/unit/setup.ts` configures default mock.
- **Component (Histoire)**: визуальная regression manual через Histoire UI.
- **E2E (Playwright)**: full UX flow against `npm run dev` server (mocked IPC).
- **A11y (axe-playwright)**: WCAG AA + ГОСТ Р 52872-2019 на all main pages.
- **Performance**: budgets check on theme switch, wizard step navigation, cold start.

CI runs все three (unit + e2e + a11y) на каждый PR; perf budget check fails build
if any operation exceeds budget defined в `PERFORMANCE_BUDGETS.md`.
