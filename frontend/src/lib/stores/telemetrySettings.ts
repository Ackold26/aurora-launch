/**
 * Telemetry redaction-tier store (Phase 2.D.2 HE-6).
 *
 * Persists the customer's chosen redaction tier via Rust IPC
 * (`get_redaction_tier` / `set_redaction_tier`). Falls back to 'basic'
 * if the IPC call fails (backwards-compat: no DB row = basic tier).
 *
 * Usage:
 *   import { redactionTier, initRedactionTier, setRedactionTier } from '$lib/stores/telemetrySettings';
 *   $redactionTier  // 'basic' | 'strict' | 'paranoid'
 */

import { writable } from 'svelte/store';
import type { RedactionTier } from '$lib/services/tiered_redact';
import { ipc } from '$ipc/client';

// ─── Store ────────────────────────────────────────────────────────────────────

/** Current redaction tier — reactive Svelte store. Default 'basic'. */
export const redactionTier = writable<RedactionTier>('basic');

/** True while a tier-change IPC call is in-flight. */
export const redactionTierLoading = writable(false);

/**
 * Count of events that will be re-redacted when the tier upgrades.
 * -1 means not yet fetched. 0 means no pending events.
 */
export const pendingRedactionCount = writable<number>(-1);

// ─── Init ─────────────────────────────────────────────────────────────────────

/** Load the persisted tier from Rust. Call once on Settings page mount. */
export async function initRedactionTier(): Promise<void> {
  try {
    const tier = await ipc.getRedactionTier();
    redactionTier.set(tier as RedactionTier);
  } catch (e) {
    console.debug('[telemetrySettings] getRedactionTier failed, defaulting to basic', e);
    redactionTier.set('basic');
  }
}

// ─── Mutation ─────────────────────────────────────────────────────────────────

/**
 * Persist a new redaction tier.
 * If tier is more strict than current (upgrade), returns count of pending events.
 */
export async function setRedactionTier(tier: RedactionTier): Promise<void> {
  redactionTierLoading.set(true);
  try {
    const result = await ipc.setRedactionTier(tier);
    redactionTier.set(tier);
    if (result && typeof result.pending_count === 'number') {
      pendingRedactionCount.set(result.pending_count);
    }
  } catch (e) {
    console.error('[telemetrySettings] setRedactionTier failed', e);
  } finally {
    redactionTierLoading.set(false);
  }
}
