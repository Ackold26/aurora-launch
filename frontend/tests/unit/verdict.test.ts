import { describe, expect, it } from 'vitest';

// Mirrors Python similarity_calculator.determine_verdict logic for UI computation.
function determineVerdict(score: number): 'High' | 'Medium' | 'Low' | 'Insufficient' {
  if (!Number.isFinite(score)) {
    throw new Error(`score must be finite, got ${score}`);
  }
  if (score >= 0.85) return 'High';
  if (score >= 0.65) return 'Medium';
  if (score >= 0.5) return 'Low';
  return 'Insufficient';
}

describe('determineVerdict (frontend mirror)', () => {
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
