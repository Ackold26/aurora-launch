// Aurora Launch — Telemetry service (P-16).
//
// Wraps ipc.logEvent с opt-in check (152-ФЗ compliance: opt-in only).
// Default opt-in = false until user explicitly enables via Settings.
//
// Behaviour:
//   - opt-in false  → no-op, console.debug skip notice
//   - opt-in true   → forward to ipc.logEvent (fire-and-forget)
//   - opt-in unknown (initial load) → buffer up to 64 events,
//     flush once opt-in resolves to true; discard if false
//
// PII policy:
//   - Stripped fields: brand_name, project_name, project_uuid, customer_email
//   - Allowed: granularity, scenario_name, mode_name, error_category
//   - Stack traces: hashed to 8-char hex fingerprint (never raw text)
//
// All calls are fire-and-forget — never block UI.
// No new npm dependencies.

import { ipc } from '$ipc/client';

// ─── Event payload types ──────────────────────────────────────────────────────

export interface AppOpenPayload {
  build_profile: string;
}

export interface ProjectCreatePayload {
  granularity: 'monthly' | 'weekly';
}

export interface ForecastStartPayload {
  horizon_weeks: number;
}

export interface ForecastCompletePayload {
  horizon_periods: number;
  elapsed_ms: number;
}

export interface SensitivityOpenPayload {
  record?: never; // no fields needed; presence of event is the signal
}

export interface VersionSavePayload {
  revision: number;
}

export interface ErrorOccurredPayload {
  error_category: string;
  /** 8-char hex fingerprint of the stack trace. Never the raw stack. */
  stack_fingerprint: string;
}

export interface SupportDiagnosticsSentPayload {
  has_screenshot: boolean;
  has_log: boolean;
}

export interface ModeOverrideUsedPayload {
  mode_name: string;
}

export interface SettingsChangedPayload {
  setting_key: string;
}

// Discriminated union — enforces typed payload per event_type.
export type TelemetryPayloadMap = {
  app_open: AppOpenPayload;
  project_create: ProjectCreatePayload;
  forecast_start: ForecastStartPayload;
  forecast_complete: ForecastCompletePayload;
  sensitivity_open: SensitivityOpenPayload;
  version_save: VersionSavePayload;
  error_occurred: ErrorOccurredPayload;
  support_diagnostics_sent: SupportDiagnosticsSentPayload;
  mode_override_used: ModeOverrideUsedPayload;
  settings_changed: SettingsChangedPayload;
};

export type TelemetryEventType = keyof TelemetryPayloadMap;

// ─── PII scrubber ─────────────────────────────────────────────────────────────

const PII_FIELDS = new Set([
  'brand_name',
  'project_name',
  'project_uuid',
  'customer_email',
]);

/** Remove known PII fields from a payload object (shallow). */
function scrubPii(payload: Record<string, unknown>): Record<string, unknown> {
  const clean: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(payload)) {
    if (!PII_FIELDS.has(key)) {
      clean[key] = value;
    }
  }
  return clean;
}

// ─── Stack trace fingerprinting ───────────────────────────────────────────────

/**
 * Hash a string to an 8-char hex fingerprint using a simple djb2-style hash.
 * NOT cryptographically secure — used only for grouping, not security.
 */
function fingerprintString(s: string): string {
  let h = 5381;
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) + h) ^ s.charCodeAt(i);
    h = h >>> 0; // keep 32-bit unsigned
  }
  return h.toString(16).padStart(8, '0');
}

/** Truncate a raw stack trace to 1 KB then hash to 8-char fingerprint. */
export function fingerprintStack(stack: string | undefined): string {
  if (!stack) return '00000000';
  const truncated = stack.slice(0, 1024);
  return fingerprintString(truncated);
}

/** Categorise an error into a broad bucket (no PII). */
export function categoriseError(err: unknown): string {
  if (err instanceof TypeError) return 'type_error';
  if (err instanceof RangeError) return 'range_error';
  if (err instanceof SyntaxError) return 'syntax_error';
  if (err instanceof Error) {
    const msg = err.message.toLowerCase();
    if (msg.includes('ipc') || msg.includes('tauri') || msg.includes('invoke')) return 'ipc_error';
    if (msg.includes('network') || msg.includes('fetch')) return 'network_error';
    if (msg.includes('timeout')) return 'timeout_error';
    return 'runtime_error';
  }
  return 'unknown_error';
}

// ─── Internal opt-in state machine ───────────────────────────────────────────

type OptInState = 'unknown' | boolean;

let optInState: OptInState = 'unknown';

/** Queue of events buffered while opt-in is unknown. Max 64 entries. */
const pendingQueue: Array<{ eventType: string; payload: Record<string, unknown>; ts: string }> = [];
const MAX_QUEUE = 64;

/** Flush the pending queue to IPC. Only called when opt-in becomes true. */
async function flushQueue(): Promise<void> {
  const events = pendingQueue.splice(0, pendingQueue.length);
  for (const ev of events) {
    await ipc
      .logEvent({ event_type: ev.eventType, timestamp: ev.ts, payload: ev.payload })
      .catch((e) => console.debug('[telemetry] flush error', e));
  }
}

// ─── Opt-in resolution ────────────────────────────────────────────────────────

/**
 * Initialise opt-in state from Rust backend. Called once on app startup.
 * Safe to call multiple times — subsequent calls are no-ops if state already resolved.
 */
export async function initTelemetry(): Promise<void> {
  if (optInState !== 'unknown') return;
  try {
    const enabled = await ipc.getTelemetryOptIn();
    optInState = enabled;
    if (enabled) {
      await flushQueue();
    } else {
      // Discard buffered events — user opted out.
      pendingQueue.length = 0;
    }
  } catch (e) {
    console.debug('[telemetry] opt-in fetch failed, defaulting to buffered', e);
    // Stay in 'unknown' — continue buffering. Not a crash.
  }
}

/**
 * Notify the telemetry service that the user changed opt-in preference.
 * Must be called after ipc.setTelemetryOptIn() succeeds.
 */
export function notifyOptInChange(enabled: boolean): void {
  optInState = enabled;
  if (enabled) {
    void flushQueue();
  } else {
    pendingQueue.length = 0;
  }
}

// ─── Overrideable IPC reference for testing ───────────────────────────────────

type LogEventFn = typeof ipc.logEvent;
type GetOptInFn = typeof ipc.getTelemetryOptIn;

let _logEvent: LogEventFn = ipc.logEvent.bind(ipc);
let _getOptIn: GetOptInFn = ipc.getTelemetryOptIn.bind(ipc);

/** For Vitest tests only. */
export function __setTelemetryIpcForTesting(overrides: {
  logEvent?: LogEventFn;
  getTelemetryOptIn?: GetOptInFn;
}): void {
  if (overrides.logEvent) _logEvent = overrides.logEvent;
  if (overrides.getTelemetryOptIn) _getOptIn = overrides.getTelemetryOptIn;
}

/** Reset internal state for tests. */
export function __resetTelemetryStateForTesting(): void {
  optInState = 'unknown';
  pendingQueue.length = 0;
  _logEvent = ipc.logEvent.bind(ipc);
  _getOptIn = ipc.getTelemetryOptIn.bind(ipc);
}

// Patch initTelemetry to use overrideable _getOptIn reference.
// We re-expose the core logic here so tests can inject mocks.
async function resolveOptIn(): Promise<void> {
  try {
    const enabled = await _getOptIn();
    optInState = enabled;
    if (enabled) {
      const events = pendingQueue.splice(0, pendingQueue.length);
      for (const ev of events) {
        await _logEvent({ event_type: ev.eventType, timestamp: ev.ts, payload: ev.payload })
          .catch((e) => console.debug('[telemetry] flush error', e));
      }
    } else {
      pendingQueue.length = 0;
    }
  } catch (e) {
    console.debug('[telemetry] opt-in fetch failed, defaulting to buffered', e);
  }
}

// ─── Core track function ──────────────────────────────────────────────────────

/**
 * Track a telemetry event.
 *
 * - Fire-and-forget: never throws, never blocks UI.
 * - Respects opt-in: no-op if disabled, buffers if unknown.
 * - Scrubs PII fields before sending.
 */
export function track<E extends TelemetryEventType>(
  eventType: E,
  payload: TelemetryPayloadMap[E]
): void {
  const timestamp = new Date().toISOString();
  const clean = scrubPii(payload as Record<string, unknown>);

  if (optInState === false) {
    console.debug(`[telemetry] skip (opt-out): ${eventType}`);
    return;
  }

  if (optInState === 'unknown') {
    if (pendingQueue.length < MAX_QUEUE) {
      pendingQueue.push({ eventType, payload: clean, ts: timestamp });
    }
    return;
  }

  // opt-in === true → send immediately, fire-and-forget
  void _logEvent({ event_type: eventType, timestamp, payload: clean }).catch((e) => {
    console.debug(`[telemetry] logEvent error for ${eventType}:`, e);
  });
}

// Re-export resolveOptIn as the testable version of initTelemetry.
export { resolveOptIn as initTelemetryInternal };
