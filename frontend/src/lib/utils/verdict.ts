// Aurora Launch — verdict computation utilities.
//
// Block 3 HIGH-10 fix: SSOT для verdict thresholds. Previously inlined в
// wizard.svelte с hardcoded literals 0.85/0.65/0.50 — silent drift if Python
// `VERDICT_THRESHOLDS` changes. Now imported from one place; tests + wizard +
// inspector all use same constants.
//
// Python source: src/aurora_launch/engines/similarity_calculator.py:27-32
// (VERDICT_THRESHOLDS dict). Future codegen will sync these via export script;
// for now manual mirror with audit-doc reference.

export const VERDICT_THRESHOLDS = {
  High: 0.85,
  Medium: 0.65,
  Low: 0.5
} as const;

export type Verdict = 'High' | 'Medium' | 'Low' | 'Insufficient';

/**
 * Mirrors Python `similarity_calculator.determine_verdict`:
 * - non-finite scores raise (NaN/Inf indicates upstream bug)
 * - boundaries inclusive (≥ threshold → that verdict)
 *
 * Block 3 audit: this function MUST stay in sync с Python implementation.
 * Tests `tests/unit/verdict.test.ts` validate boundaries.
 */
export function determineVerdict(score: number): Verdict {
  if (!Number.isFinite(score)) {
    throw new Error(
      `determineVerdict: score must be finite, got ${score}. ` +
        'NaN/Inf indicates upstream computation error.'
    );
  }
  if (score >= VERDICT_THRESHOLDS.High) return 'High';
  if (score >= VERDICT_THRESHOLDS.Medium) return 'Medium';
  if (score >= VERDICT_THRESHOLDS.Low) return 'Low';
  return 'Insufficient';
}
