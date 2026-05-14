// Aurora Launch — Methodology Cert IPC typed shim (P-09).
//
// VerificationResult + VerifyBundleInput are canonical в $ipc/client.ts —
// re-exported here so consumers import from a single place without pulling
// the full client.
//
// Uses the same swappable invoke pattern as ipc/projects.ts so Vitest can
// mock this module independently of the global client mock.

import { invoke as tauriInvoke } from '@tauri-apps/api/core';
import type { InvokeFn } from './client';

export type { VerificationResult, VerifyBundleInput } from './client';

/** For Vitest tests only — overrides the invoke function for this module. */
let invoke: InvokeFn = tauriInvoke as InvokeFn;

export function __setMethodologyInvokeForTesting(fn: InvokeFn): void {
  invoke = fn;
}

export interface LocalDevSignatureResult {
  public_key_hex: string;
  signature_hex: string;
  composite_hash_hex: string;
}

/**
 * Verify Ed25519 methodology certificate for a bundle on disk.
 *
 * `trustLocalDev` should be `true` only in dev builds; pass `false` for
 * production to require cloud_kms or sample provenance.
 */
export async function verifyBundleSignature(
  bundlePath: string,
  trustLocalDev = false,
): Promise<import('./client').VerificationResult> {
  return invoke('verify_bundle_signature', {
    input: { bundle_path: bundlePath, trust_local_dev: trustLocalDev },
  });
}

/**
 * Generate (or load) a persistent local-dev Ed25519 signing key and sign the
 * bundle. Only callable in dev builds — returns the raw hex artefacts so the
 * UI can display them for inspection.
 */
export async function generateLocalDevSignature(
  bundlePath: string,
): Promise<LocalDevSignatureResult> {
  return invoke('generate_local_dev_signature', { bundlePath });
}
