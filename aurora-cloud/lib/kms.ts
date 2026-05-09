// Yandex.Cloud KMS asymmetric signature integration.
//
// Block 3 BLOCKER-2 fix arrives here: real cloud KMS public key replaces
// the `EMBED_AT_RELEASE_TIME` placeholder. F1 deploy provisions an Ed25519
// keypair в KMS, exports the public part к `AURORA_CLOUD_PUBLIC_KEY_PEM`
// (baked into Aurora Launch release builds), keeps the private part inside
// KMS (never exposed).
//
// API: https://cloud.yandex.com/en/docs/kms/api-ref/AsymmetricSignatureCrypto/sign

import { errorResponse } from './schema';

const KMS_ENDPOINT = 'https://kms.api.cloud.yandex.net/kms/v1/asymmetricSignatureKeys';

export interface KmsSignResult {
  signature_hex: string;
  public_key_hex: string;
  key_id: string;
}

export class KmsError extends Error {
  constructor(
    public kind: string,
    message: string
  ) {
    super(message);
  }
}

/** Request a fresh IAM token from Yandex Cloud metadata service.
 *
 * On Vercel Edge runtime we can't use the metadata service — instead we
 * accept a long-lived service-account JWT pre-signed at deploy time, exchange
 * it for an IAM token at function cold-start. Token cached for ~1 hour.
 */

let cachedIamToken: { token: string; expiresAt: number } | undefined;

async function getIamToken(): Promise<string> {
  const now = Date.now();
  if (cachedIamToken && cachedIamToken.expiresAt > now + 60_000) {
    return cachedIamToken.token;
  }
  const saJwt = process.env.AURORA_KMS_SA_JWT;
  if (!saJwt) {
    throw new KmsError('kms_misconfigured', 'AURORA_KMS_SA_JWT env var not set');
  }
  const resp = await fetch('https://iam.api.cloud.yandex.net/iam/v1/tokens', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ jwt: saJwt })
  });
  if (!resp.ok) {
    throw new KmsError('kms_iam_failed', `IAM token exchange failed: ${resp.status}`);
  }
  const data = (await resp.json()) as { iamToken: string; expiresAt: string };
  // Yandex returns RFC 3339 expiresAt; our cache uses ms-since-epoch.
  const expiresAt = Date.parse(data.expiresAt) || now + 3_600_000;
  cachedIamToken = { token: data.iamToken, expiresAt };
  return data.iamToken;
}

/**
 * Sign a 32-byte hash via Yandex.Cloud KMS Ed25519 key.
 *
 * @param hashHex hex-encoded 32-byte hash to sign
 * @returns signature + public key + key id для audit chain
 */
export async function kmsSign(hashHex: string): Promise<KmsSignResult> {
  const keyId = process.env.AURORA_KMS_KEY_ID;
  if (!keyId) {
    throw new KmsError('kms_misconfigured', 'AURORA_KMS_KEY_ID env var not set');
  }

  const iamToken = await getIamToken();

  // Yandex KMS expects message as base64-encoded raw bytes (NOT hash; signing
  // service hashes internally to SHA-512 для Ed25519 — but Aurora pre-hashed
  // composite. We pass message=composite as raw 32 bytes; Ed25519 inside KMS
  // re-hashes — net result is signing хеш(хеш) which is fine cryptographically
  // и matches how Aurora Launch verifier expects via composite_bundle_hash_mirror
  // в Block 3.

  const messageBytes = hexToBytes(hashHex);
  const messageBase64 = bytesToBase64(messageBytes);

  const signResp = await fetch(`${KMS_ENDPOINT}/${keyId}:sign`, {
    method: 'POST',
    headers: {
      authorization: `Bearer ${iamToken}`,
      'content-type': 'application/json'
    },
    body: JSON.stringify({
      keyId,
      message: messageBase64
    })
  });

  if (!signResp.ok) {
    const text = await signResp.text();
    throw new KmsError(
      'kms_sign_failed',
      `KMS sign returned ${signResp.status}: ${text.slice(0, 200)}`
    );
  }

  const signData = (await signResp.json()) as { signature: string; keyId: string };
  const signatureBytes = base64ToBytes(signData.signature);
  if (signatureBytes.length !== 64) {
    throw new KmsError(
      'kms_invalid_response',
      `KMS returned ${signatureBytes.length}-byte signature (expected 64)`
    );
  }

  const publicKeyHex = process.env.AURORA_CLOUD_PUBLIC_KEY_HEX ?? '';
  if (!publicKeyHex || publicKeyHex.length !== 64) {
    throw new KmsError(
      'kms_misconfigured',
      'AURORA_CLOUD_PUBLIC_KEY_HEX env var must be 64-char hex'
    );
  }

  return {
    signature_hex: bytesToHex(signatureBytes),
    public_key_hex: publicKeyHex,
    key_id: signData.keyId
  };
}

// ─── Hex / base64 helpers (no Node Buffer в Edge runtime) ────────────────────

export function hexToBytes(hex: string): Uint8Array {
  if (hex.length % 2 !== 0) throw new Error('hex string odd length');
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) {
    const h = hex.slice(i * 2, i * 2 + 2);
    const v = parseInt(h, 16);
    if (Number.isNaN(v)) throw new Error(`invalid hex chars at ${i}`);
    out[i] = v;
  }
  return out;
}

export function bytesToHex(bytes: Uint8Array): string {
  let s = '';
  for (const b of bytes) s += b.toString(16).padStart(2, '0');
  return s;
}

export function bytesToBase64(bytes: Uint8Array): string {
  let s = '';
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s);
}

export function base64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

export function kmsErrorResponse(e: unknown): Response {
  if (e instanceof KmsError) {
    return errorResponse(e.kind, e.message, e.kind === 'kms_misconfigured' ? 503 : 502);
  }
  return errorResponse('kms_unknown', String(e), 502);
}
