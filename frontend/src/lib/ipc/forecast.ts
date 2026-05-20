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

// ─── Sprint 2 D1': trust score read from project state ──────────────────────

export type TrustDimensionSource = 'project_state' | 'default' | 'override';

export type TrustDimensionKey =
  | 'proxy_similarity_score'
  | 'methodology_certified'
  | 'model_convergence_passed'
  | 'data_sufficiency'
  | 'uncertainty_pct_inverse';

export interface ProjectTrustScoreResult extends TrustScoreResult {
  project_id: string;
  /** false когда the project has no saved version yet — all dims default. */
  has_saved_version: boolean;
  /** Per-dimension source tag (project_state / default / override). */
  sources: Record<TrustDimensionKey, TrustDimensionSource>;
  /** Human-readable extraction notes per dimension (Expert info chip). */
  source_notes: Record<TrustDimensionKey, string>;
}

/** Compute trust score by reading project state from ProjectDB (Sprint 2 D1').
 *
 * Server-side wrapper extracts the five dimensions internally — frontend no
 * longer needs to hardcode model_convergence_passed=1 and data_sufficiency=1.0
 * the way client-side computeTrustScore currently does. The returned `sources`
 * field shows which dims came from real saved data vs defaults vs overrides.
 *
 * @param project_id Required.
 * @param overrides Optional per-dimension direct values (rare, mostly for tests).
 */
export async function computeTrustScoreForProject(args: {
  project_id: string;
  overrides?: Partial<Record<TrustDimensionKey, number>>;
}): Promise<ProjectTrustScoreResult> {
  return invoke<ProjectTrustScoreResult>('compute_trust_score_for_project', {
    params: args,
  });
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

/** Compose canonical forecast.json bytes для bundle write (этап 1.3д). */
export async function composeForecastJson(
  params: ComposeForecastJsonParams
): Promise<ComposeForecastJsonResult> {
  // Rust команда compose_forecast_json объявляет `params: serde_json::Value`
  // → Tauri требует `{ params: {...} }` wrapper (тот же паттерн что explain_forecast).
  return invoke<ComposeForecastJsonResult>('compose_forecast_json', { params });
}

// ─── ROADMAP §4.4 — Budget Optimizer IPC ────────────────────────────────────

export interface ChannelCap {
  min?: number;
  max: number;
}

export interface BudgetSearchRequest {
  total_budget: number;
  channel_caps: Record<string, ChannelCap>;
  horizon_periods: number;
  granularity?: 'monthly' | 'weekly';
  n_iterations?: number;
  seed?: number;
}

export interface BestSpendPlan {
  channel_split: Record<string, number[]>;
  expected_total_sales: number;
  ci_lower: number;
  ci_upper: number;
  methodology_signature: string;
  n_iterations_used: number;
}

export interface SpendPlanAlternative extends BestSpendPlan {
  rank: number;
}

export interface OptimizeBudgetResult {
  optimize_handle: string;
}

/** Spawn a budget optimization task (ROADMAP §4.4). Returns a handle immediately;
 * listen for `sidecar://optimize_budget_completed` or `sidecar://optimize_budget_failed`
 * events to receive the result. */
export async function optimizeBudget(params: {
  proxy_data: Record<string, unknown>;
  anchors_data: Record<string, unknown>;
  request: BudgetSearchRequest;
  timeout_seconds?: number;
}): Promise<OptimizeBudgetResult> {
  return invoke<OptimizeBudgetResult>('optimize_budget', params);
}

/** Request cancellation of a running budget optimisation job. */
export async function cancelOptimizeBudget(optimizeHandle: string): Promise<void> {
  return invoke<void>('cancel_optimize_budget', { optimizeHandle });
}

// ─── Sprint 2 D5: MCMC OOM pre-flight ────────────────────────────────────────

export type McmcBudgetStatus = 'ok' | 'low_ram' | 'critical';
export type McmcSuggestedFallback = 'bayesian' | 'ols' | null;

export interface CheckMcmcBudgetParams {
  /** Override the 4 GB default minimum. */
  min_required_bytes?: number;
}

export interface CheckMcmcBudgetResult {
  status: McmcBudgetStatus;
  available_bytes: number;
  total_bytes: number;
  used_pct: number;
  /** Plain Russian customer-facing recommendation. */
  recommendation: string;
  /** Engine to suggest as fallback when budget is short; null when OK. */
  suggested_fallback: McmcSuggestedFallback;
}

/** Pre-flight RAM budget check before MCMC sampling (Sprint 2 D5).
 *
 * Frontend invokes BEFORE triggering Bayesian training/forecast so the wizard
 * can surface a budget warning + OLS downgrade prompt instead of crashing
 * with MemoryError mid-sample. Safe to call repeatedly — pure psutil snapshot,
 * no side effects.
 */
export async function checkMcmcBudget(
  params: CheckMcmcBudgetParams = {}
): Promise<CheckMcmcBudgetResult> {
  return invoke<CheckMcmcBudgetResult>('check_mcmc_budget', { params });
}

// ─── Sprint 2 D4': MCMC iteration progress events ────────────────────────────

export type McmcPhase = 'adaptation' | 'sampling' | 'diagnostics' | 'done';

export interface McmcProgressEvent {
  /** Correlation id linking ticks to a training/forecast job. */
  handle: string;
  /** Progress 0..100. Backend clamps out-of-range values. */
  pct: number;
  /** Human-readable status text. */
  message: string;
  /** Phase label for progress indicator. */
  phase: McmcPhase;
}

/** Subscribe to MCMC iteration progress events emitted by training pipelines.
 *
 * Backend (aurora_engines.train_model) accepts a ``progress_callback``; Aurora
 * Launch sidecar wires that to ``sidecar://mcmc_progress`` events via the
 * ``build_mcmc_progress_callback`` factory. Frontend wait UX subscribes here
 * to drive the progress bar + tip rotation timer.
 *
 * Note: as of Sprint 2 there is no IPC handler that triggers training (no
 * customer-facing wizard training step yet). The listener wiring is ready
 * so the UI flows light up immediately когда training UI lands — tracked
 * как Sprint Buffer #20.
 */
export function onMcmcProgress(
  callback: (event: McmcProgressEvent) => void
): Promise<UnlistenFn> {
  return listen<McmcProgressEvent>('sidecar://mcmc_progress', (e) => callback(e.payload));
}

// ─── Optimize Budget event listener helpers ───────────────────────────────────

export interface OptimizeBudgetCompletedEvent {
  optimize_handle: string;
  best: BestSpendPlan;
  alternatives: SpendPlanAlternative[];
}

export interface OptimizeBudgetFailedEvent {
  optimize_handle: string;
  error: string;
  kind: string;
}

/** Subscribe to the optimize_budget completion event. Returns an unlisten function. */
export function onOptimizeBudgetCompleted(
  callback: (event: OptimizeBudgetCompletedEvent) => void
): Promise<import('@tauri-apps/api/event').UnlistenFn> {
  return listen<OptimizeBudgetCompletedEvent>(
    'sidecar://optimize_budget_completed',
    (e) => callback(e.payload)
  );
}

/** Subscribe to the optimize_budget failure event. Returns an unlisten function. */
export function onOptimizeBudgetFailed(
  callback: (event: OptimizeBudgetFailedEvent) => void
): Promise<import('@tauri-apps/api/event').UnlistenFn> {
  return listen<OptimizeBudgetFailedEvent>(
    'sidecar://optimize_budget_failed',
    (e) => callback(e.payload)
  );
}
