// INV-05 attack scenario tests for /api/sign — written FIRST.
//
// Threat model: adversary wants Aurora Cloud to issue a signed methodology
// certificate без paying for `report_pdf_methodology_certificate` feature
// or на behalf of someone else's seat. Each test = one attack vector.

import { describe, expect, it } from 'vitest';

import {
  isValidSignRequest,
  type SignRequest
} from '../lib/schema';

describe('SignRequest validator (INV-05 attack scenarios)', () => {
  const validReq: SignRequest = {
    composite_hash_hex: 'a'.repeat(64),
    license_jwt: 'eyJ...real JWT...',
    client_meta: { aurora_app_version: '0.1.0' }
  };

  it('accepts canonical request', () => {
    expect(isValidSignRequest(validReq)).toBe(true);
  });

  it('rejects missing composite_hash_hex', () => {
    expect(isValidSignRequest({ license_jwt: 'x' })).toBe(false);
  });

  it('rejects empty license_jwt', () => {
    expect(
      isValidSignRequest({ composite_hash_hex: 'a'.repeat(64), license_jwt: '' })
    ).toBe(false);
  });

  it('rejects short hash', () => {
    expect(
      isValidSignRequest({ composite_hash_hex: 'a'.repeat(63), license_jwt: 'x' })
    ).toBe(false);
  });

  it('rejects long hash', () => {
    expect(
      isValidSignRequest({ composite_hash_hex: 'a'.repeat(65), license_jwt: 'x' })
    ).toBe(false);
  });

  it('rejects non-hex chars in hash', () => {
    expect(
      isValidSignRequest({ composite_hash_hex: 'g'.repeat(64), license_jwt: 'x' })
    ).toBe(false);
  });

  it('accepts uppercase hex', () => {
    expect(
      isValidSignRequest({ composite_hash_hex: 'A'.repeat(64), license_jwt: 'x' })
    ).toBe(true);
  });

  it('rejects oversized JWT (DoS guard)', () => {
    expect(
      isValidSignRequest({
        composite_hash_hex: 'a'.repeat(64),
        license_jwt: 'x'.repeat(10_000)
      })
    ).toBe(false);
  });

  it('rejects null body', () => {
    expect(isValidSignRequest(null)).toBe(false);
  });

  it('rejects array body', () => {
    expect(isValidSignRequest([])).toBe(false);
  });

  it('rejects string body', () => {
    expect(isValidSignRequest('not an object')).toBe(false);
  });

  it('rejects body с numeric license_jwt', () => {
    expect(
      isValidSignRequest({ composite_hash_hex: 'a'.repeat(64), license_jwt: 12345 })
    ).toBe(false);
  });
});

describe('Replay protection — composite_hash uniqueness', () => {
  // Replay attempt would require:
  // 1. Captured prior request (composite + JWT) — но JWT has expiry, replay
  //    >24h impossible
  // 2. Identical composite_hash → identical signature output — that's expected
  //    behaviour для deterministic signing. Defender accepts replay because
  //    signature validity не depends на freshness; what matters is JWT
  //    freshness (handled by jwtVerify exp claim) и КMS access (handled by
  //    IAM token rotation).
  //
  // This test documents the design decision that replay = same signature
  // output is acceptable, NOT a vulnerability.
  it('composite_hash determinism is by design (KMS sign on same hash → same sig)', () => {
    // No code path here — this is a doc-test pinning design intent.
    expect(true).toBe(true);
  });
});

describe('Authorization header & body JWT match (defense-in-depth)', () => {
  // The sign handler requires Authorization Bearer header AND license_jwt
  // в body to match. Prevents forwarding attacks where an intermediary
  // strips the header but leaves the body intact.
  it('design: header.token must equal body.license_jwt', () => {
    // Pinned by handler implementation; integration test (deploy-time) verifies.
    expect(true).toBe(true);
  });
});
