import { describe, expect, it } from 'vitest';

import { determineVerdict, VERDICT_THRESHOLDS } from '../../src/lib/utils/verdict';

describe('determineVerdict (frontend mirror, Block 3 HIGH-10 SSOT)', () => {
  it('thresholds match Python similarity_calculator constants', () => {
    expect(VERDICT_THRESHOLDS.High).toBe(0.85);
    expect(VERDICT_THRESHOLDS.Medium).toBe(0.65);
    expect(VERDICT_THRESHOLDS.Low).toBe(0.5);
  });

  it('boundaries match SIMILARITY_FRAMEWORK §6', () => {
    expect(determineVerdict(0.85)).toBe('High');
    expect(determineVerdict(0.65)).toBe('Medium');
    expect(determineVerdict(0.5)).toBe('Low');
    expect(determineVerdict(0.49)).toBe('Insufficient');
  });

  it('rejects non-finite scores (mirror Python audit-extended fix)', () => {
    expect(() => determineVerdict(NaN)).toThrow();
    expect(() => determineVerdict(Infinity)).toThrow();
    expect(() => determineVerdict(-Infinity)).toThrow();
  });
});
