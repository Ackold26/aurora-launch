// Aurora Launch — M-09 Reproduce-in-Python mode detection.
//
// Pure utility: determines whether a forecast bundle contains real anchors +
// spend_plan (v0.1.1+ bundles) or only legacy data (preview fallback).
// Extracted from +page.svelte so unit-testable without jsdom / Svelte mount.
//
// Commit fbd1c93 added anchors + spend_plan to forecast.json schema (v1).
// Inspector reads them in loadForecast() and passes here to decide mode.

export interface ReproduceModeInputs {
  anchors?: Record<string, unknown> | null | undefined;
  spendPlan?: Record<string, number[]> | null | undefined;
}

export interface ReproduceModeResult {
  /** true → real bundle data available; false → legacy / partial → preview mode */
  isReal: boolean;
  /** Human-readable reason for debugging (not shown to end-user) */
  reason: string;
}

/**
 * Determine whether a forecast bundle has sufficient real anchors + spend_plan
 * for bit-exact M-09 reproduction (isReal=true) or should fall back to
 * preview mode with stub values (isReal=false).
 *
 * Rules (all three must hold for isReal=true):
 *   1. anchors is a non-null object
 *   2. spendPlan is a non-null object
 *   3. spendPlan has at least one key (non-empty)
 *
 * Partial payload (anchors present, spend_plan empty/absent) is conservative
 * → preview=true. Spend without anchors is not a valid combination (legacy
 * bundles won't have either; v1 bundles export both together).
 */
export function detectReproduceMode(inputs: ReproduceModeInputs): ReproduceModeResult {
  const { anchors, spendPlan } = inputs;

  if (anchors === null || anchors === undefined) {
    return { isReal: false, reason: 'anchors absent (legacy bundle)' };
  }

  if (spendPlan === null || spendPlan === undefined) {
    return { isReal: false, reason: 'spend_plan absent (legacy bundle)' };
  }

  if (Object.keys(spendPlan).length === 0) {
    return { isReal: false, reason: 'spend_plan present but empty — partial data, preview safe' };
  }

  return { isReal: true, reason: 'anchors + spend_plan present with keys — real reproduce' };
}
