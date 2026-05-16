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

  // ── Step 0: parse imported file ─────────────────────────────────────────────
  parse_data_file: () => ({
    adapter_id: 'dsm_v2024',
    adapter_metadata: {},
    record_count: 156,
    records: [
      { brand_name: 'Кагоцел', period_date: '2024-01-01', sales_value_rub: 50000 },
    ],
    source_columns: ['Бренд', 'Дата', 'Продажи_рубли', 'АТХ_код'],
    suggested_mapping: {
      Бренд: 'brand_name',
      Дата: 'period_date',
      Продажи_рубли: 'sales_value_rub',
      АТХ_код: 'atc_code',
    },
    preview_rows: [
      { brand_name: 'Кагоцел', period_date: '2024-01-01', sales_value_rub: 50000 },
    ],
    available_canonical_fields: [
      { id: 'brand_name', label_ru: 'Бренд', group: 'identity' },
      { id: 'period_date', label_ru: 'Период / Дата', group: 'period' },
      { id: 'sales_value_rub', label_ru: 'Продажи (рубли)', group: 'sales' },
      { id: 'atc_code', label_ru: 'АТХ-код', group: 'category' },
    ],
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
