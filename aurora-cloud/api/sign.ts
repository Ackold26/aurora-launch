// /api/sign — methodology cert signing service (Final F1).
//
// POST /api/sign
// Authorization: Bearer <license_jwt>
// Body: { composite_hash_hex, license_jwt, client_meta? }
//
// Verifies license JWT (must include `report_pdf_methodology_certificate`
// feature flag). Calls Yandex.Cloud KMS to sign the composite hash. Returns
// Ed25519 signature + public key for chain-of-trust display.
//
// Block 3 BLOCKER-2 fix arrives here: production cloud KMS public key
// flows к Aurora Launch release builds via env, replaces placeholder.

import { kmsErrorResponse, kmsSign } from '../lib/kms';
import { LicenseVerifyError, requireLicense } from '../lib/license';
import {
  errorResponse,
  isValidSignRequest,
  jsonResponse,
  type SignRequest,
  type SignResponse
} from '../lib/schema';

export const config = { runtime: 'edge' };

const FEATURE = 'report_pdf_methodology_certificate';

export default async function handler(request: Request): Promise<Response> {
  if (request.method !== 'POST') {
    return errorResponse('method_not_allowed', 'POST only', 405);
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch (e) {
    return errorResponse('invalid_json', String(e), 400);
  }

  if (!isValidSignRequest(body)) {
    return errorResponse(
      'invalid_input',
      'composite_hash_hex (64-char hex) and license_jwt required',
      400
    );
  }
  const req = body as SignRequest;

  // Defense-in-depth: license JWT must appear in BOTH body AND Authorization
  // header (matched). Prevents a forwarded request с body JWT but missing
  // Authorization header (some proxies strip).
  const authHeader = request.headers.get('authorization') ?? '';
  const headerToken = authHeader.startsWith('Bearer ')
    ? authHeader.slice(7).trim()
    : '';
  if (headerToken !== req.license_jwt) {
    return errorResponse(
      'auth_required',
      'license_jwt must be passed in BOTH Authorization header AND body, matched',
      401
    );
  }

  const auth = await requireLicense(request, FEATURE);
  if (auth instanceof Response) return auth;
  const { claims } = auth;

  // Compute key fingerprint from public key hex для chain-of-trust display
  // (BLAKE3-16 first 16 hex chars). For Edge runtime we use noble/hashes.
  let keyFingerprint = '';
  try {
    const { blake3 } = await import('@noble/hashes/blake3');
    const { hexToBytes, bytesToHex } = await import('../lib/kms');
    const pubKeyBytes = hexToBytes(process.env.AURORA_CLOUD_PUBLIC_KEY_HEX ?? '');
    const fp = blake3(pubKeyBytes);
    keyFingerprint = bytesToHex(fp).slice(0, 16);
  } catch {
    keyFingerprint = '0000000000000000';
  }

  let result;
  try {
    result = await kmsSign(req.composite_hash_hex);
  } catch (e) {
    return kmsErrorResponse(e);
  }

  // Audit log (Vercel KV — best-effort, не block response on KV failure).
  try {
    const { kv } = await import('@vercel/kv');
    await kv.lpush('aurora:sign:audit', {
      seat_id: claims.seat_id,
      license_id: claims.license_id,
      composite_hash: req.composite_hash_hex,
      signed_at: new Date().toISOString(),
      client_meta: req.client_meta ?? {}
    });
    await kv.ltrim('aurora:sign:audit', 0, 9999); // keep last 10k entries
  } catch (e) {
    console.error('[sign] audit KV write failed (non-fatal):', e);
  }

  const response: SignResponse = {
    signature_hex: result.signature_hex,
    public_key_hex: result.public_key_hex,
    signed_at: new Date().toISOString(),
    key_fingerprint: keyFingerprint
  };

  return jsonResponse(response);
}
