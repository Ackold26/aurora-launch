// License JWT verification — мirrors aurora-platform-core JWT contract.
//
// Aurora Launch + Studio + Econometrica all sign-attest customer license JWTs
// using a single Ed25519 keypair (issuer = "aurora-platform-core"). Cloud
// signing service verifies the JWT before issuing a methodology certificate
// signature — gate ensures only paid licenses can produce signed bundles.

import { jwtVerify, importSPKI } from 'jose';

import { errorResponse } from './schema';

const ISSUER = 'aurora-platform-core';
const SIGNING_AUDIENCE = 'aurora-cloud-signer';

export interface LicenseClaims {
  iss: string;
  sub: string; // user_id
  aud: string | string[];
  exp: number;
  iat: number;
  nbf?: number;
  /** Aurora-specific claims */
  license_id: string;
  seat_id: string;
  machine_id: string;
  tier: string;
  enabled_features: string[];
}

let cachedKey: CryptoKey | undefined;

async function getVerifyKey(): Promise<CryptoKey> {
  if (cachedKey) return cachedKey;
  const pem = process.env.AURORA_LICENSE_VERIFY_KEY_PEM;
  if (!pem) {
    throw new Error('AURORA_LICENSE_VERIFY_KEY_PEM env var not set');
  }
  cachedKey = await importSPKI(pem, 'EdDSA');
  return cachedKey;
}

export class LicenseVerifyError extends Error {
  constructor(
    public kind: string,
    message: string
  ) {
    super(message);
  }
}

/**
 * Verify a license JWT.
 *
 * @param token raw JWT string
 * @param requiredFeature feature flag the licensee must hold
 * @returns parsed claims (use claims.seat_id for audit trail attribution)
 * @throws LicenseVerifyError on malformed / expired / wrong-audience / missing feature
 */
export async function verifyLicenseJwt(
  token: string,
  requiredFeature: string
): Promise<LicenseClaims> {
  const key = await getVerifyKey();
  let result;
  try {
    result = await jwtVerify(token, key, {
      issuer: ISSUER,
      audience: SIGNING_AUDIENCE,
      algorithms: ['EdDSA']
    });
  } catch (e) {
    throw new LicenseVerifyError(
      'license_invalid',
      e instanceof Error ? e.message : String(e)
    );
  }

  const claims = result.payload as unknown as LicenseClaims;

  if (!claims.seat_id || typeof claims.seat_id !== 'string') {
    throw new LicenseVerifyError('license_invalid', 'missing seat_id claim');
  }
  if (!claims.tier || !Array.isArray(claims.enabled_features)) {
    throw new LicenseVerifyError('license_invalid', 'missing tier/enabled_features');
  }
  if (!claims.enabled_features.includes(requiredFeature)) {
    throw new LicenseVerifyError(
      'feature_required',
      `tier ${claims.tier} lacks required feature ${requiredFeature}`
    );
  }
  return claims;
}

/**
 * Wrap a handler so it auto-verifies license JWT from `Authorization: Bearer <jwt>`.
 * Returns a structured 401/403 response on failure; 401 = malformed/missing auth,
 * 403 = valid auth but insufficient feature.
 */
export async function requireLicense(
  request: Request,
  requiredFeature: string
): Promise<{ claims: LicenseClaims } | Response> {
  const authHeader = request.headers.get('authorization') ?? '';
  if (!authHeader.startsWith('Bearer ')) {
    return errorResponse('auth_required', 'Authorization: Bearer <jwt> required', 401);
  }
  const token = authHeader.slice('Bearer '.length).trim();
  if (!token) {
    return errorResponse('auth_required', 'empty bearer token', 401);
  }
  try {
    const claims = await verifyLicenseJwt(token, requiredFeature);
    return { claims };
  } catch (e) {
    if (e instanceof LicenseVerifyError) {
      const status = e.kind === 'feature_required' ? 403 : 401;
      return errorResponse(e.kind, e.message, status);
    }
    return errorResponse('auth_invalid', String(e), 401);
  }
}
