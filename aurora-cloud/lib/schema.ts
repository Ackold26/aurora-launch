// Aurora Cloud — request/response schemas for Edge Functions.
// SSOT for cross-language wire format — Python sidecar producers + Rust IPC
// + Frontend consumers all match these shapes.

export interface SignRequest {
  /** Hex-encoded composite bundle hash (SHA-256, 64 chars) per Block 3
   *  composite_bundle_hash() / composite_bundle_hash_mirror(). */
  composite_hash_hex: string;
  /** License JWT issued by aurora-platform-core. Signing service verifies
   *  signature + expiry + audience before signing. */
  license_jwt: string;
  /** Optional client metadata for audit trail. */
  client_meta?: {
    aurora_app_version?: string;
    aurora_app?: string;
    bundle_revision?: number;
    project_id?: string;
  };
}

export interface SignResponse {
  /** Hex-encoded Ed25519 signature (64 bytes → 128 hex chars). */
  signature_hex: string;
  /** Hex-encoded public key (32 bytes → 64 hex chars). Frontend can store
   *  для local verify roundtrip (defense-in-depth). */
  public_key_hex: string;
  /** Server timestamp (RFC 3339 UTC) for signature provenance. */
  signed_at: string;
  /** Cloud KMS key fingerprint (BLAKE3-16 of public key) for chain-of-trust
   *  display в Methodology Cert UI. */
  key_fingerprint: string;
}

export interface ErrorResponse {
  kind: string;
  message: string;
  /** Optional details (validation errors, etc.) */
  details?: Record<string, unknown>;
}

export interface TelemetryEventBatch {
  /** Aurora license seat_id (from JWT) — server pulls from auth, NOT trusted from client. */
  events: Array<{
    event_type: string;
    timestamp: string;
    payload: Record<string, unknown>;
  }>;
}

export interface FeedbackSubmission {
  text: string;
  /** Base64 PNG screenshot — optional. */
  screenshot_base64?: string;
  /** Recent log slice (truncated to 32 KB server-side). */
  log_excerpt?: string;
  client_meta?: {
    aurora_app_version?: string;
    build_profile?: string;
    os?: string;
    locale?: string;
  };
}

export interface UpdaterManifestResponse {
  version: string;
  notes: string;
  pub_date: string;
  platforms: {
    [target_arch: string]: {
      signature: string;
      url: string;
    };
  };
}

// ─── Validators (Web standard, no schema lib) ────────────────────────────────

const HEX_64 = /^[0-9a-f]{64}$/i;

export function isValidSignRequest(body: unknown): body is SignRequest {
  if (typeof body !== 'object' || body === null) return false;
  const req = body as Partial<SignRequest>;
  if (typeof req.composite_hash_hex !== 'string') return false;
  if (!HEX_64.test(req.composite_hash_hex)) return false;
  if (typeof req.license_jwt !== 'string' || req.license_jwt.length === 0) return false;
  if (req.license_jwt.length > 8192) return false; // sanity
  return true;
}

export function isValidTelemetryBatch(body: unknown): body is TelemetryEventBatch {
  if (typeof body !== 'object' || body === null) return false;
  const req = body as Partial<TelemetryEventBatch>;
  if (!Array.isArray(req.events)) return false;
  if (req.events.length === 0 || req.events.length > 500) return false;
  for (const ev of req.events) {
    if (typeof ev !== 'object' || ev === null) return false;
    if (typeof ev.event_type !== 'string' || ev.event_type.length > 128) return false;
    if (typeof ev.timestamp !== 'string') return false;
  }
  return true;
}

export function isValidFeedback(body: unknown): body is FeedbackSubmission {
  if (typeof body !== 'object' || body === null) return false;
  const req = body as Partial<FeedbackSubmission>;
  if (typeof req.text !== 'string') return false;
  if (req.text.length === 0 || req.text.length > 8000) return false;
  if (req.screenshot_base64 !== undefined) {
    if (typeof req.screenshot_base64 !== 'string') return false;
    if (req.screenshot_base64.length > 5_000_000) return false; // ~5 MB cap
  }
  if (req.log_excerpt !== undefined) {
    if (typeof req.log_excerpt !== 'string') return false;
    if (req.log_excerpt.length > 32_768) return false;
  }
  return true;
}

export function jsonResponse(
  body: unknown,
  status = 200,
  extraHeaders: Record<string, string> = {}
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      ...extraHeaders
    }
  });
}

export function errorResponse(
  kind: string,
  message: string,
  status: number,
  details?: Record<string, unknown>
): Response {
  const body: ErrorResponse = details ? { kind, message, details } : { kind, message };
  return jsonResponse(body, status);
}
