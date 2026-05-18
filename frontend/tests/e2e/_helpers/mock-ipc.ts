/**
 * mock-ipc.ts — Reusable Playwright IPC mock helper для Aurora Launch.
 *
 * Strategy: inject via page.addInitScript() BEFORE page.goto() to intercept
 * window.__TAURI_INTERNALS__.invoke — the internal hook that @tauri-apps/api/core
 * calls for every IPC command.
 *
 * We also mock:
 *   - __TAURI_INTERNALS__.transformCallback — used by @tauri-apps/api/event.listen()
 *   - __TAURI_INTERNALS__.unregisterCallback — called on unlisten()
 *   - __TAURI_EVENT_PLUGIN_INTERNALS__.unregisterListener — called on _unlisten()
 *
 * This covers ALL Tauri IPC paths used by the wizard without needing a real
 * Tauri runtime. The SvelteKit dev server (Vite) serves the frontend, and the
 * mock makes IPC calls resolve immediately.
 *
 * Handler serialisation: functions cannot cross the Playwright serialisation
 * boundary. We stringify each handler and reconstruct it in-browser via
 * new Function(). IIFE form `(args) => result` is passed as-is.
 */

import type { Page } from '@playwright/test';

export type IpcHandler = (args?: Record<string, unknown>) => unknown;

// ─── Default happy-path mocks ─────────────────────────────────────────────────

export const defaultWizardHappyPathMocks: Record<string, IpcHandler> = {
  // ── Wizard session ──────────────────────────────────────────────────────────
  wizard_session_load: () => ({ session: null }),
  wizard_session_save: () => ({ saved: true, saved_at: new Date().toISOString() }),
  wizard_session_clear: () => ({ cleared: true }),

  // ── Sample bundles (Step 2 ProxyPickerCard) ─────────────────────────────────
  list_sample_bundles: () => ({
    bundles: [
      {
        id: 'kagotsel_venarus',
        path: '/mock/kagotsel.aurora',
        label: 'Кагоцел (грипп/ОРВИ)',
        exists: true,
      },
      {
        id: 'venarus_baseline',
        path: '/mock/venarus.aurora',
        label: 'Венарус (хроническая)',
        exists: true,
      },
      {
        id: 'multi_proxy',
        path: '/mock/multi.aurora',
        label: 'Мульти-прокси (3 бренда)',
        exists: true,
      },
    ],
  }),

  // ── Step 0: analyze imported file (file reader port 2026-05-18) ────────────
  analyze_data_file: () => ({
    status: 'ok',
    file_name: 'sample_wide_table.xlsx',
    size_kb: 142.6,
    shape: [156, 4],
    headers: ['date', 'sales_packs', 'tv_grp', 'competitor_share'],
    rows: [
      ['2024-01-07', 142000, 850.2, 0.12],
      ['2024-01-14', 138500, 790.5, 0.13],
      ['2024-01-21', 145200, 910.1, 0.11],
      ['2024-01-28', 139800, 820.3, 0.14],
      ['2024-02-04', 151000, 880.7, 0.10],
    ],
    dtypes: {
      date: 'datetime64[ns]',
      sales_packs: 'int64',
      tv_grp: 'float64',
      competitor_share: 'float64',
    },
    columns: [
      { name: 'date',              role: 'date',    confidence: 0.97, kind: 'date',               auto_detected: true },
      { name: 'sales_packs',       role: 'kpi',     confidence: 0.85, kind: 'target_count',        auto_detected: true },
      { name: 'tv_grp',            role: 'media',   confidence: 0.85, kind: 'physical',            auto_detected: true },
      { name: 'competitor_share',  role: 'control', confidence: 0.90, kind: 'signed_competitor',   auto_detected: true },
    ],
  }),

  // ── Step 0: validate wide table (file reader port 2026-05-18) ───────────────
  validate_wide_table: () => ({
    status: 'ok',
    verdict: 'ГОТОВ К МОДЕЛИРОВАНИЮ',
    file: { name: 'sample_wide_table.xlsx', rows: 156, cols: 4, size_kb: 142.6 },
    columns: [],
    detected: {
      date: 'date',
      kpi: ['sales_packs'],
      media: ['tv_grp'],
      control: ['competitor_share'],
      n_predictors: 2,
      ratio: 78.0,
      date_frequency: 'weekly',
    },
    available_kpi_types: ['sales_packs', 'leads'],
    issues: [],
    warnings: [],
    high_correlations: [],
    full_correlation_matrix: { labels: [], matrix: [] },
  }),

  // ── Step 3: similarity computation ─────────────────────────────────────────
  compute_similarity_dimensions: () => ({
    category_l1_match: 1.0,
    category_l2_match: 1.0,
    category_l3_match: 1.0,
    pricing_tier_match: 1.0,
    brand_size_match: 1.0,
    distribution_match: 1.0,
    media_maturity_match: 0.0,
    lifecycle_match: 0.0,
    weights_used: {},
  }),
  aggregate_score: () => 0.75,

  // ── Step 5: forecast ────────────────────────────────────────────────────────
  // event-based progress is tested separately; synchronous IPC side mocked here.
  start_forecast: (args) => {
    const projectId =
      (args as { input?: { project_id?: string } } | undefined)?.input?.project_id ?? 'p1';
    return {
      handle_id: 'mock-forecast-001',
      project_id: String(projectId),
      started_at: new Date().toISOString(),
    };
  },
  cancel_forecast: () => undefined,
  get_forecast_status: () => ({
    handle_id: 'mock-forecast-001',
    state: 'completed',
    progress_pct: 100,
    elapsed_ms: 2000,
    eta_ms: null,
  }),

  // ── Step 6: cert + save ─────────────────────────────────────────────────────
  save_bundle: () => ({ revision: 1, manifest: {}, composite_hash: 'mock-hash' }),
  compose_forecast_json: () => ({
    forecast_json_base64: 'eyJtb2NrIjoidHJ1ZSJ9',
    byte_size: 17,
  }),

  // ── Plugin event system — plugin:event|listen returns a numeric handler id.
  // transformCallback is called first (in core.js) and registers the JS callback
  // in __TAURI_INTERNALS__.callbacks; listen() just needs a resolved id.
  'plugin:event|listen': () => 9999,
  'plugin:event|unlisten': () => undefined,

  // ── Misc ─────────────────────────────────────────────────────────────────────
  log_event: () => 1,
  get_build_info: () => ({
    version: '0.1.0',
    build_profile: 'dev',
    is_dev_build: true,
    rust_version: '1.75',
    cargo_pkg_name: 'aurora-launch-gui',
  }),
  get_refresh_consent: () => null,
  has_feature: () => true,
  current_license_status: () => ({
    state: 'active',
    tier: 'pro',
    enabled_features: ['*'],
    detail: 'mock',
    is_offline_grace: false,
    valid_until: null,
  }),
  get_handshake_status: () => null,
  is_dev_build: () => true,
};

// ─── setupMockIpc ─────────────────────────────────────────────────────────────

/**
 * Inject mock IPC into the page BEFORE page.goto().
 *
 * MUST be called before navigation — addInitScript injects into every new
 * document but only takes effect if called before goto().
 *
 * @param page      Playwright Page object.
 * @param custom    Optional per-test overrides merged over defaults.
 */
export async function setupMockIpc(
  page: Page,
  custom: Record<string, IpcHandler> = {},
): Promise<void> {
  const merged = { ...defaultWizardHappyPathMocks, ...custom };

  // Serialise handlers: each fn becomes its toString() source. We reconstruct
  // it in-browser via new Function, wrapping in an IIFE to get the return value.
  const serialised: Record<string, string> = {};
  for (const [name, fn] of Object.entries(merged)) {
    serialised[name] = fn.toString();
  }

  await page.addInitScript((handlers: Record<string, string>) => {
    // ── Reconstruct handlers from string sources ────────────────────────────
    const restored: Record<string, (args: unknown) => unknown> = {};
    for (const [name, src] of Object.entries(handlers)) {
      try {
        // eslint-disable-next-line no-new-func
        restored[name] = new Function('args', `return (${src})(args)`) as (
          args: unknown,
        ) => unknown;
      } catch {
        console.error('[mock-ipc] Failed to restore handler for:', name);
      }
    }

    // ── Callback registry (needed by transformCallback in core.js) ──────────
    let _callbackId = 0;
    const _callbacks: Record<number, (msg: unknown) => void> = {};

    // ── Full __TAURI_INTERNALS__ mock ───────────────────────────────────────
    (
      globalThis as unknown as {
        __TAURI_INTERNALS__: {
          invoke: (cmd: string, args?: unknown, opts?: unknown) => Promise<unknown>;
          transformCallback: (cb: (msg: unknown) => void, once?: boolean) => number;
          unregisterCallback: (id: number) => void;
        };
      }
    ).__TAURI_INTERNALS__ = {
      invoke(cmd: string, args?: unknown) {
        const handler = restored[cmd];
        if (!handler) {
          // Warn instead of reject — unknown commands are non-critical in tests
          // (layout/lifecycle calls we haven't mocked).
          console.warn('[mock-ipc] no handler for IPC command:', cmd);
          return Promise.resolve(null);
        }
        try {
          return Promise.resolve(handler(args));
        } catch (e) {
          return Promise.reject(e);
        }
      },
      transformCallback(cb: (msg: unknown) => void, once = false) {
        const id = ++_callbackId;
        if (once) {
          _callbacks[id] = (msg) => {
            delete _callbacks[id];
            cb(msg);
          };
        } else {
          _callbacks[id] = cb;
        }
        return id;
      },
      unregisterCallback(id: number) {
        delete _callbacks[id];
      },
    };

    // ── __TAURI_EVENT_PLUGIN_INTERNALS__ — called by _unlisten() ────────────
    (
      globalThis as unknown as {
        __TAURI_EVENT_PLUGIN_INTERNALS__: {
          unregisterListener: (event: string, id: number) => void;
        };
      }
    ).__TAURI_EVENT_PLUGIN_INTERNALS__ = {
      unregisterListener(_event: string, _id: number) {
        // no-op in mock
      },
    };
  }, serialised);
}
