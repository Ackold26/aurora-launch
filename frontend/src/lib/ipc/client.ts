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
import type { BundleManifest, SimilarityDimensionScores } from '$types/aurora-schemas';

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

export interface ParseDataFileInput {
  path: string;
  adapter_id?: string;
  max_records?: number;
}

export interface ParseDataFileResult {
  adapter_id: string;
  adapter_metadata: Record<string, unknown>;
  record_count: number;
  records: Array<Record<string, unknown>>;
}

export interface AdapterInfo {
  adapter_id: string;
  adapter_version: string;
  schema_version: string;
  sample_files_glob: string[];
  canonical_record_mapping: Record<string, string>;
  detected_signatures: string[];
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
  horizon_weeks: number;
  elapsed_ms: number;
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

  // feedback
  captureFeedback: (input: FeedbackInput) =>
    invoke<number>('capture_feedback', { input }),
  listPendingFeedback: () =>
    invoke<FeedbackEntry[]>('list_pending_feedback'),

  // audit log
  listAuditEntries: (query: AuditQuery = {}) =>
    invoke<AuditEntry[]>('list_audit_entries', { query }),

  // build info
  getBuildInfo: () => invoke<BuildInfo>('get_build_info'),

  // adapters (Block 4 Phase 3)
  parseDataFile: (input: ParseDataFileInput) =>
    invoke<ParseDataFileResult>('parse_data_file', { input }),
  listAdapters: () => invoke<AdapterInfo[]>('list_adapters'),

  // save_bundle (Block 4 Phase 2 — full sidecar wiring)
  saveBundleViaSidecar: (input: SaveBundleInput) =>
    invoke<{
      revision: number;
      manifest: BundleManifest;
      composite_hash: string;
    }>('save_bundle', input as unknown as Record<string, unknown>)
};

export interface SaveBundleInput {
  handleId: string;
  targetPath: string;
  extraFilesBase64?: Record<string, string>;
  expectedRevision?: number | null;
}
