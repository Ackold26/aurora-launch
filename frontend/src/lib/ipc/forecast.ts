// Aurora Launch — Forecast IPC typed shim.
//
// Typed wrappers for forecast commands already wired through the sidecar.
// Event listeners use a swappable `listen` reference so Vitest tests can
// inject a mock without importing @tauri-apps/api/event in jsdom.
//
// Re-exports types that overlap with client.ts to keep callers from importing
// two modules. The authoritative type declarations live here for forecast-
// specific callers; client.ts types are kept for backward compat.

import { type InvokeFn } from './client';
import { invoke as tauriInvoke } from '@tauri-apps/api/core';
import { listen as tauriListen, type UnlistenFn } from '@tauri-apps/api/event';

// ─── Swappable references for testing ────────────────────────────────────────

let invoke: InvokeFn = tauriInvoke as InvokeFn;
type ListenFn = <T>(event: string, handler: (e: { payload: T }) => void) => Promise<UnlistenFn>;
let listen: ListenFn = tauriListen as ListenFn;

/** For Vitest tests — overrides invoke for this module. */
export function __setForecastInvokeForTesting(fn: InvokeFn): void {
  invoke = fn;
}

/** For Vitest tests — overrides listen for this module. */
export function __setForecastListenForTesting(fn: ListenFn): void {
  listen = fn;
}

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ForecastHandleSummary {
  handle_id: string;
  project_id: string;
  started_at: string;
}

export interface ForecastStatus {
  handle_id: string;
  state: 'running' | 'cancelling' | 'cancelled' | 'completed' | 'failed';
  progress_pct: number;
  elapsed_ms: number;
  eta_ms: number | null;
}

export interface ForecastProgressEvent {
  forecast_handle: string;
  /** Period index (week or month depending on project granularity). */
  period_index: number;
  point_forecast: number;
  ci_lower: number;
  ci_upper: number;
  progress_pct: number;
  elapsed_ms: number;
}

export interface ForecastCompletedEvent {
  forecast_handle: string;
  horizon_periods: number;
  elapsed_ms: number;
  forecast_data?: unknown;
}

export interface ForecastFailedEvent {
  forecast_handle: string;
  error: string;
  kind: string;
}

// ─── Service functions ────────────────────────────────────────────────────────

/** Spawn a forecast run. Returns a handle identifying the async job. */
export async function startForecast(input: {
  project_id: string;
  horizon_weeks: number;
  seed: number;
}): Promise<ForecastHandleSummary> {
  return invoke<ForecastHandleSummary>('start_forecast', { input });
}

/** Request cancellation of a running forecast. Resolves when the cancel is acknowledged. */
export async function cancelForecast(handleId: string): Promise<void> {
  return invoke<void>('cancel_forecast', { handleId });
}

/** Poll the current state of a forecast job. */
export async function getForecastStatus(handleId: string): Promise<ForecastStatus> {
  return invoke<ForecastStatus>('get_forecast_status', { handleId });
}

// ─── Event listeners ─────────────────────────────────────────────────────────

/** Subscribe to per-period progress ticks. Returns an unlisten function. */
export function onForecastProgress(
  callback: (event: ForecastProgressEvent) => void
): Promise<UnlistenFn> {
  return listen<ForecastProgressEvent>('sidecar://forecast_progress', (e) => callback(e.payload));
}

/** Subscribe to the completion event. Returns an unlisten function. */
export function onForecastCompleted(
  callback: (event: ForecastCompletedEvent) => void
): Promise<UnlistenFn> {
  return listen<ForecastCompletedEvent>('sidecar://forecast_completed', (e) =>
    callback(e.payload)
  );
}

/** Subscribe to the failure event. Returns an unlisten function. */
export function onForecastFailed(
  callback: (event: ForecastFailedEvent) => void
): Promise<UnlistenFn> {
  return listen<ForecastFailedEvent>('sidecar://forecast_failed', (e) => callback(e.payload));
}

// ─── PA-A03: Trust score IPC ─────────────────────────────────────────────────

export interface TrustScoreInputs {
  proxy_similarity_score: number;  // 0..100
  methodology_certified: 0 | 1 | 0.5;  // 0/1/partial
  model_convergence_passed: 0 | 1 | 0.5;
  data_sufficiency: number;  // 0..1
  uncertainty_pct_inverse: number;  // 0..1 (1 - normalised_ci_width)
}

export interface TrustScoreDiagnostic {
  label: string;
  value: string;
  status: 'good' | 'warn' | 'bad' | 'info';
  weight?: number;
}

export interface TrustScoreResult {
  score: number;  // 0..100 integer
  tier: string;  // Russian tier label
  diagnostics: TrustScoreDiagnostic[];
}

/** Compute trust score via Python sidecar (P-03 + PA-A03). */
export async function computeTrustScore(
  inputs: TrustScoreInputs
): Promise<TrustScoreResult> {
  return invoke<TrustScoreResult>('compute_trust_score', { params: inputs });
}
