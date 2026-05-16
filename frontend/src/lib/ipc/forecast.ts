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
  /** Legacy emission path использует horizon_weeks; orchestrated — horizon_weeks тоже. */
  horizon_weeks?: number;
  horizon_periods?: number;
  elapsed_ms: number;
  /** Orchestrated path: full summary с points + engine_mode + methodology_signature + warnings + granularity. */
  forecast?: {
    horizon_periods: number;
    granularity: 'monthly' | 'weekly';
    methodology_signature: string;
    engine_mode: 'pure_transfer' | 'transfer_with_bias_check' | 'ols_with_proxy_priors' | 'bayesian_with_proxy_priors';
    warnings: string[];
    points: Array<{ point_forecast: number; ci_lower: number; ci_upper: number }>;
  };
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

// ─── Phase Magic M-09: Reproduce-in-Python script generator ──────────────────

export interface ReproduceScriptParams {
  bundle_path: string;
  anchors: Record<string, unknown>;
  spend_plan: Record<string, number[]>;
  horizon_periods: number;
  granularity?: 'monthly' | 'weekly';
  coverage_target?: number;
  n_recipient?: number;
  seed?: number;
}

export interface ReproduceScriptResult {
  script: string;
  suggested_filename: string;
}

/** Generate Python script reproducing the forecast bit-exact (M-09). */
export async function generateReproduceScript(
  params: ReproduceScriptParams
): Promise<ReproduceScriptResult> {
  return invoke<ReproduceScriptResult>('generate_reproduce_script', params as unknown as Record<string, unknown>);
}

// ─── Phase Magic M-03: AI explanations (local-first) ────────────────────────

export interface ExplainerInputs {
  point_forecast_mean: number;
  ci_lower_mean: number;
  ci_upper_mean: number;
  horizon_periods: number;
  granularity: 'monthly' | 'weekly';
  engine_mode:
    | 'pure_transfer'
    | 'transfer_with_bias_check'
    | 'ols_with_proxy_priors'
    | 'bayesian_with_proxy_priors';
  methodology_signature: string;
  n_recipient: number;
  trust_score?: number | null;
  warnings?: string[];
  currency?: string;
  locale?: 'ru' | 'en';
}

export interface Explanation {
  what: string;
  why: string;
  risks: string;
  engine_used: 'local' | 'cloud';
  confidence: 'high' | 'medium' | 'low';
}

/** Generate 3-paragraph forecast narrative (M-03 local engine). */
export async function explainForecast(
  inputs: ExplainerInputs
): Promise<Explanation> {
  // B-3 fix: Rust команда explain_forecast объявляет `params: serde_json::Value`
  // → Tauri ожидает `{ params: {...} }` wrapper. Без wrapper deserialize error.
  return invoke<Explanation>('explain_forecast', { params: inputs });
}

// ─── Этап 1.3d: compose forecast.json для bundle write ──────────────────────

export interface ComposeForecastJsonParams {
  horizon_weeks: number;
  weekly_points: Array<{ week_index: number; point: number; ci_lower: number; ci_upper: number }>;
  engine_mode?: 'pure_transfer' | 'transfer_with_bias_check' | 'ols_with_proxy_priors' | 'bayesian_with_proxy_priors';
  granularity?: 'monthly' | 'weekly';
  methodology_signature?: string;
  n_recipient?: number;
  warnings?: string[];
  anchors?: Record<string, unknown> | null;
  spend_plan?: Record<string, number[]> | null;
  coverage_target?: number;
  seed?: number;
  produced_at?: string;
}

export interface ComposeForecastJsonResult {
  forecast_json_base64: string;
  schema_version: string;
  byte_size: number;
}

/** Compose canonical forecast.json bytes для bundle write (этап 1.3d). */
export async function composeForecastJson(
  params: ComposeForecastJsonParams
): Promise<ComposeForecastJsonResult> {
  // Rust команда compose_forecast_json объявляет `params: serde_json::Value`
  // → Tauri требует `{ params: {...} }` wrapper (тот же паттерн что explain_forecast).
  return invoke<ComposeForecastJsonResult>('compose_forecast_json', { params });
}
