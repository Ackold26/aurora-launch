// Aurora Launch — typed IPC client wrapping `@tauri-apps/api/core` invoke().
//
// All Tauri commands в src-tauri/src/commands/* exposed here as typed
// functions. Errors come back as `AuroraError { kind, message }`.
//
// Pattern:
//   import { ipc } from '$ipc/client';
//   const handle = await ipc.openBundle('/path/to/file.aurora');
//
// Mocked в Vitest tests via `setupMockIpc()` helper — see tests/unit/ipc.mock.ts.

import { invoke as tauriInvoke } from '@tauri-apps/api/core';
import type { BundleManifest, SimilarityDimensionScores, WizardSession } from '$types/aurora-schemas';

export interface AuroraError {
  kind: string;
  message: string;
}

export interface BundleHandleSummary {
  handle_id: string;
  source_format: string;
  size_bytes: number;
  revision: number;
  manifest: BundleManifest;
  /** Block 4 Phase 5: filesystem path used by verify_bundle_signature. */
  path: string;
}

export interface BundleEntryPayload {
  entry: string;
  bytes_base64: string;
  size_bytes: number;
  sha256_hex: string;
}

export interface ProxyVsRecipient {
  proxy_category_l1: string;
  proxy_category_l2: string;
  proxy_category_l3: string;
  proxy_pricing_tier: string;
  proxy_brand_size: string;
  proxy_distribution: string;
  proxy_media_maturity: string;
  proxy_lifecycle: string;
  recipient_category_l1: string;
  recipient_category_l2: string;
  recipient_category_l3: string;
  recipient_pricing_tier: string;
  recipient_brand_size: string;
  recipient_distribution: string;
  recipient_media_maturity: string;
  recipient_lifecycle: string;
}

export interface ForecastStartInput {
  project_id: string;
  horizon_weeks: number;
  seed: number;
}

export interface ForecastHandleSummary {
  handle_id: string;
  project_id: string;
  started_at: string;
}

export interface ForecastStatus {
  handle_id: string;
  state: 'running' | 'cancelling' | 'cancelled' | 'completed';
  progress_pct: number;
  elapsed_ms: number;
  eta_ms: number | null;
}

export interface VerificationResult {
  valid: boolean;
  signature_provenance: 'cloud_kms' | 'local_dev' | 'sample' | 'unsigned';
  signed_by: string | null;
  signed_at: string | null;
  key_fingerprint: string | null;
  composite_hash: string | null;
  manifest_revision: number | null;
  trust_badge: 'production' | 'dev' | 'sample' | 'warning';
  failure_reason: string | null;
}

export interface VerifyBundleInput {
  bundle_path: string;
  trust_local_dev: boolean;
}

// Sprint 3 D6 — reproducibility verification
export interface ReproducibilityFileMismatch {
  entry: string;
  expected_sha256: string;
  computed_sha256: string;
}

export interface ReproducibilityResult {
  status: 'verified' | 'diverged' | 'error';
  files_checked: number;
  mismatches: ReproducibilityFileMismatch[];
  reason: string | null;
}

export interface LicenseStatus {
  state: 'active' | 'grace' | 'expired' | 'invalid' | 'no_license' | 'degraded';
  tier: string | null;
  enabled_features: string[];
  detail: string;
  is_offline_grace: boolean;
  valid_until: string | null;
}

export interface BuildInfo {
  version: string;
  build_profile: string;
  is_dev_build: boolean;
  rust_version: string;
  cargo_pkg_name: string;
}

// ─── Validation / file-reader types (file reader port 2026-05-18) ─────────────

export type ColumnRole = 'kpi' | 'media' | 'control' | 'date' | 'unused' | 'unknown';

export interface ColumnAssignment {
  name: string;
  role: ColumnRole;
  confidence: number;
  /** Populated by backend; may be empty string when restored from session. */
  kind: string;
  /** True when role was auto-detected (not user-overridden). */
  auto_detected?: boolean;
}

export interface AnalyzeDataFileInput {
  path: string;
  n_rows?: number;
}

export interface AnalyzeDataFileResult {
  status: 'ok' | 'error';
  message?: string;
  file_name?: string;
  size_kb?: number;
  shape?: [number, number];
  headers?: string[];
  rows?: Array<Array<string | number | null>>;
  dtypes?: Record<string, string>;
  columns?: ColumnAssignment[];
}

export interface ValidateWideTableInput {
  path: string;
  role_overrides?: Record<string, ColumnRole>;
}

export interface WideTableValidationResult {
  status: 'ok' | 'warning' | 'error';
  verdict?: string;
  message?: string;
  file?: { name: string; rows: number; cols: number; size_kb: number };
  columns?: Array<
    ColumnAssignment & {
      dtype?: string;
      stats?: Record<string, number>;
      histogram?: { counts: number[]; edges: number[] };
      adstock_type?: string;
      date_stats?: Record<string, unknown>;
    }
  >;
  detected?: {
    date: string | null;
    kpi: string[];
    media: string[];
    control: string[];
    n_predictors: number;
    ratio: number;
    date_frequency: string;
  };
  available_kpi_types?: string[];
  issues?: Array<{ type: string; message: string; severity: string }>;
  warnings?: Array<{ type: string; message: string; severity: string }>;
  high_correlations?: Array<{ col1: string; col2: string; correlation: number; risk: string }>;
  full_correlation_matrix?: { labels: string[]; matrix: number[][] };
}

export interface ForecastProgressEvent {
  forecast_handle: string;
  week_index: number;
  point_forecast: number;
  ci_lower: number;
  ci_upper: number;
  progress_pct: number;
  elapsed_ms: number;
}

export interface ForecastCompletedEvent {
  forecast_handle: string;
  /** Legacy emission path. Orchestrated path заполняет также horizon_periods. */
  horizon_weeks: number;
  horizon_periods?: number;
  elapsed_ms: number;
  /** 1.3d: orchestrated path emits full summary (см. methods.py:1409). */
  forecast?: {
    horizon_periods: number;
    granularity: 'monthly' | 'weekly';
    methodology_signature: string;
    engine_mode: 'pure_transfer' | 'transfer_with_bias_check' | 'ols_with_proxy_priors' | 'bayesian_with_proxy_priors';
    warnings: string[];
    points: Array<{ point_forecast: number; ci_lower: number; ci_upper: number }>;
  };
}

export interface ForecastFailedEvent {
  forecast_handle: string;
  error: string;
  kind: string;
}

export interface TelemetryEvent {
  event_type: string;
  timestamp: string;
  payload: Record<string, unknown>;
}

export interface StoredTelemetryEvent extends TelemetryEvent {
  id: number;
  uploaded_at: string | null;
}

export interface AuditEntry {
  id: number;
  timestamp: string;
  actor: string;
  operation: string;
  target: string | null;
  outcome: string;
  details: Record<string, unknown>;
}

export interface AuditQuery {
  limit?: number;
  since?: string;
  operation_filter?: string;
}

// Sprint 1 — UX Foundation: posterior staleness reminders.
// Backend stub: list_projects_with_new_actuals returns [] until schema migration
// adds last_actuals_update_at column (Sprint 2+).
export interface PendingPosteriorUpdateItem {
  project_uuid: string;
  name: string;
  last_actuals_update_at: string | null;
  weeks_since_update: number;
}

export interface FeedbackInput {
  text: string;
  screenshot_path?: string;
  log_path?: string;
}

export interface FeedbackEntry {
  id: number;
  timestamp: string;
  text: string;
  screenshot_path: string | null;
  log_path: string | null;
  uploaded_at: string | null;
}

// ─── Auto-Refresh types (ROADMAP §3.5) ───────────────────────────────────────

export interface DataSourceConfig {
  source_kind: 'dsm_xlsx_folder' | 'mediascope_xlsx_folder' | 'manual';
  path?: string | null;
  last_checked_at?: string | null;
  last_modified_seen?: string | null;
}

export interface RefreshConsentSetting {
  enabled: boolean;
  frequency: 'daily' | 'weekly' | 'monthly';
  last_prompted_at: string | null;
}

export interface RefreshTrigger {
  project_uuid: string;
  reason: 'new_data' | 'manual' | 'scheduled';
  detected_at: string;
  source: string;
}

// Override hook for tests / Storybook (Vitest setup imports & swaps).
export type InvokeFn = <T>(cmd: string, args?: Record<string, unknown>) => Promise<T>;

let invoke: InvokeFn = tauriInvoke as InvokeFn;

export function __setInvokeForTesting(fn: InvokeFn): void {
  invoke = fn;
}

export const ipc = {
  // bundle
  openBundle: (path: string) => invoke<BundleHandleSummary>('open_bundle', { path }),
  closeBundle: (handleId: string) => invoke<void>('close_bundle', { handleId }),
  listBundleEntries: (handleId: string) =>
    invoke<string[]>('list_bundle_entries', { handleId }),
  readBundleEntry: (handleId: string, entry: string) =>
    invoke<BundleEntryPayload>('read_bundle_entry', { handleId, entry }),
  getManifest: (handleId: string) =>
    invoke<BundleManifest>('get_manifest', { handleId }),
  saveBundle: (handleId: string, targetPath: string) =>
    invoke<unknown>('save_bundle', { handleId, targetPath }),

  // similarity
  computeSimilarityDimensions: (pair: ProxyVsRecipient) =>
    invoke<SimilarityDimensionScores>('compute_similarity_dimensions', { pair }),
  aggregateScore: (input: {
    dimensions: SimilarityDimensionScores;
    weights: Record<string, number>;
  }) => invoke<number>('aggregate_score', { input }),

  // forecast
  startForecast: (input: ForecastStartInput) =>
    invoke<ForecastHandleSummary>('start_forecast', { input }),
  cancelForecast: (handleId: string) =>
    invoke<void>('cancel_forecast', { handleId }),
  getForecastStatus: (handleId: string) =>
    invoke<ForecastStatus>('get_forecast_status', { handleId }),

  // methodology cert (Block 2C)
  verifyBundleSignature: (input: VerifyBundleInput) =>
    invoke<VerificationResult>('verify_bundle_signature', { input }),
  generateLocalDevSignature: (bundlePath: string) =>
    invoke<{
      public_key_hex: string;
      signature_hex: string;
      composite_hash_hex: string;
    }>('generate_local_dev_signature', { bundlePath }),

  // Sprint 3 D6: bundle reproducibility verification
  verifyReproducibility: (bundlePath: string) =>
    invoke<ReproducibilityResult>('verify_reproducibility', { bundlePath }),

  // license
  currentLicenseStatus: () => invoke<LicenseStatus>('current_license_status'),
  hasFeature: (feature: string) => invoke<boolean>('has_feature', { feature }),
  requireFeature: (feature: string) =>
    invoke<void>('require_feature', { feature }),
  isDevBuild: () => invoke<boolean>('is_dev_build'),

  // telemetry (Block 2F local-only)
  logEvent: (event: TelemetryEvent) => invoke<number>('log_event', { event }),
  listEvents: (limit?: number) =>
    invoke<StoredTelemetryEvent[]>('list_events', { limit }),
  getTelemetryOptIn: () => invoke<boolean>('get_telemetry_opt_in'),
  setTelemetryOptIn: (enabled: boolean) =>
    invoke<void>('set_telemetry_opt_in', { enabled }),
  // Phase 2.D.2 HE-6: tiered redaction
  getRedactionTier: () => invoke<string>('get_redaction_tier'),
  setRedactionTier: (tier: string) =>
    invoke<{ pending_count: number }>('set_redaction_tier', { tier }),

  // feedback
  captureFeedback: (input: FeedbackInput) =>
    invoke<number>('capture_feedback', { input }),
  listPendingFeedback: () =>
    invoke<FeedbackEntry[]>('list_pending_feedback'),

  // audit log
  listAuditEntries: (query: AuditQuery = {}) =>
    invoke<AuditEntry[]>('list_audit_entries', { query }),

  // posterior updates (Sprint 1 UX Foundation; backend stub until Sprint 2 schema migration)
  listPendingPosteriorUpdates: (thresholdWeeks?: number) =>
    invoke<PendingPosteriorUpdateItem[]>('list_pending_posterior_updates', {
      threshold_weeks: thresholdWeeks,
    }),

  // build info
  getBuildInfo: () => invoke<BuildInfo>('get_build_info'),

  // validation (file reader port 2026-05-18)
  analyzeDataFile: (input: AnalyzeDataFileInput) =>
    invoke<AnalyzeDataFileResult>('analyze_data_file', { input }),
  validateWideTable: (input: ValidateWideTableInput) =>
    invoke<WideTableValidationResult>('validate_wide_table', { input }),

  // save_bundle (Block 4 Phase 2 — full sidecar wiring)
  saveBundleViaSidecar: (input: SaveBundleInput) =>
    invoke<{
      revision: number;
      manifest: BundleManifest;
      composite_hash: string;
    }>('save_bundle', input as unknown as Record<string, unknown>),

  // Этап 2.8: handshake-status (Rust↔Python compat)
  getHandshakeStatus: () =>
    invoke<HandshakeResult | null>('get_handshake_status'),

  // ROADMAP §3.5 — Auto-Refresh (Python sidecar methods via Rust passthrough)
  getRefreshConsent: () =>
    invoke<RefreshConsentSetting | null>('get_refresh_consent', {}),
  setRefreshConsent: (enabled: boolean, frequency: RefreshConsentSetting['frequency'] = 'weekly') =>
    invoke<RefreshConsentSetting>('set_refresh_consent', { enabled, frequency }),
  checkDataSourceUpdates: (projectUuid: string, sources: DataSourceConfig[]) =>
    invoke<{ triggers: RefreshTrigger[] }>('check_data_source_updates', {
      project_uuid: projectUuid,
      sources,
    }),
  dismissRefreshTrigger: (projectUuid: string) =>
    invoke<{ dismissed: boolean }>('dismiss_refresh_trigger', { project_uuid: projectUuid }),
  // Phase 3 — persisted data sources (folder watching per-project)
  getDataSources: (projectUuid: string) =>
    invoke<{ sources: DataSourceConfig[] }>('get_data_sources', { project_uuid: projectUuid }),
  setDataSources: (projectUuid: string, sources: DataSourceConfig[]) =>
    invoke<{ saved: boolean; count: number; warning?: string }>('set_data_sources', {
      project_uuid: projectUuid,
      sources,
    }),

  // Phase 1.C — Wizard session persistence (BTA-2 + UX-3 recovery)
  wizardSessionSave: (session: WizardSession) =>
    invoke<{ saved: boolean; saved_at?: string }>('wizard_session_save', {
      session: session as unknown as Record<string, unknown>,
    }),
  wizardSessionLoad: () =>
    invoke<{ session: WizardSession | null }>('wizard_session_load', {}),
  wizardSessionClear: () =>
    invoke<{ cleared: boolean }>('wizard_session_clear', {}),
  listSampleBundles: () =>
    invoke<{ bundles: Array<{ id: string; path: string; label: string; exists: boolean }> }>(
      'list_sample_bundles',
      {},
    ),
};

/** Этап 2.8: результат negotiate-handshake между Rust shell и Python sidecar. */
export interface HandshakeResult {
  compatible: boolean;
  reason?: string | null;
  advice?: string | null;
}

export interface SaveBundleInput {
  handleId: string;
  targetPath: string;
  extraFilesBase64?: Record<string, string>;
  expectedRevision?: number | null;
}
