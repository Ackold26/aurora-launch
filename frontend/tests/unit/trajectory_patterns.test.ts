// Vitest tests for trajectory_patterns utility (Phase 1.C.5, SO-1).

import { describe, expect, it } from 'vitest';
import {
  generateTrajectory,
  validIntensity,
  TRAJECTORY_PATTERNS,
} from '../../src/lib/utils/trajectory_patterns';

describe('TRAJECTORY_PATTERNS', () => {
  it('exports exactly 4 descriptors', () => {
    expect(TRAJECTORY_PATTERNS).toHaveLength(4);
  });

  it('contains rampup/sustain/decline/custom ids', () => {
    const ids = TRAJECTORY_PATTERNS.map((p) => p.id);
    expect(ids).toContain('rampup');
    expect(ids).toContain('sustain');
    expect(ids).toContain('decline');
    expect(ids).toContain('custom');
  });
});

describe('generateTrajectory — rampup', () => {
  it('starts low and ends high (monotonic growth trend)', () => {
    const pts = generateTrajectory('rampup', 7, 12)!;
    const first = pts.at(0)!;
    const last = pts.at(-1)!;
    expect(first).toBeLessThan(last);
  });

  it('is monotonically non-decreasing', () => {
    const pts = generateTrajectory('rampup', 8, 12)!;
    for (let i = 1; i < pts.length; i++) {
      expect(pts[i]!).toBeGreaterThanOrEqual(pts[i - 1]! - 1e-9);
    }
  });

  it('first value is close to 0.1 (base floor)', () => {
    const pts = generateTrajectory('rampup', 5, 12)!;
    expect(pts.at(0)!).toBeCloseTo(0.1, 1);
  });
});

describe('generateTrajectory — sustain', () => {
  it('stays near the target (intensity/10) throughout', () => {
    const intensity = 6;
    const target = intensity / 10; // 0.6
    const pts = generateTrajectory('sustain', intensity, 12)!;
    for (const v of pts) {
      expect(v).toBeGreaterThanOrEqual(target - 0.1 - 1e-9);
      expect(v).toBeLessThanOrEqual(target + 0.1 + 1e-9);
    }
  });
});

describe('generateTrajectory — decline', () => {
  it('starts at peak and finishes lower', () => {
    const pts = generateTrajectory('decline', 8, 12)!;
    expect(pts.at(0)!).toBeGreaterThan(pts.at(-1)!);
  });

  it('is monotonically non-increasing', () => {
    const pts = generateTrajectory('decline', 7, 12)!;
    for (let i = 1; i < pts.length; i++) {
      expect(pts[i]!).toBeLessThanOrEqual(pts[i - 1]! + 1e-9);
    }
  });
});

describe('generateTrajectory — custom', () => {
  it('returns null for custom pattern', () => {
    expect(generateTrajectory('custom', 5, 12)).toBeNull();
  });
});

describe('generateTrajectory — intensity scaling', () => {
  it('intensity 1 produces low target values', () => {
    const pts = generateTrajectory('sustain', 1, 12)!;
    // target = 0.1; all values should be near 0.1
    for (const v of pts) {
      expect(v).toBeLessThan(0.25);
    }
  });

  it('intensity 10 produces high target values', () => {
    const pts = generateTrajectory('sustain', 10, 12)!;
    // target = 1.0; most values should be near 1
    const avg = pts.reduce((a, b) => a + b, 0) / pts.length;
    expect(avg).toBeGreaterThan(0.85);
  });
});

describe('generateTrajectory — horizon_periods', () => {
  it('horizon_periods=4 → exactly 4 points', () => {
    expect(generateTrajectory('rampup', 5, 4)).toHaveLength(4);
  });

  it('horizon_periods=52 → exactly 52 points (no perf cliff)', () => {
    expect(generateTrajectory('sustain', 7, 52)).toHaveLength(52);
  });
});

describe('generateTrajectory — value clamping', () => {
  it('all values are clamped to [0.05, 1.0]', () => {
    for (const pattern of ['rampup', 'sustain', 'decline'] as const) {
      for (const intensity of [1, 5, 10]) {
        const pts = generateTrajectory(pattern, intensity, 12)!;
        for (const v of pts) {
          expect(v).toBeGreaterThanOrEqual(0.05 - 1e-9);
          expect(v).toBeLessThanOrEqual(1.0 + 1e-9);
        }
      }
    }
  });
});

describe('validIntensity', () => {
  it('accepts all integers 1..10', () => {
    for (let i = 1; i <= 10; i++) {
      expect(validIntensity(i)).toBe(true);
    }
  });

  it('rejects 0 (below range)', () => {
    expect(validIntensity(0)).toBe(false);
  });

  it('rejects 11 (above range)', () => {
    expect(validIntensity(11)).toBe(false);
  });

  it('rejects float 1.5', () => {
    expect(validIntensity(1.5)).toBe(false);
  });

  it('rejects string "5"', () => {
    expect(validIntensity('5' as unknown as number)).toBe(false);
  });

  it('rejects NaN', () => {
    expect(validIntensity(NaN)).toBe(false);
  });

  it('rejects negative numbers', () => {
    expect(validIntensity(-1)).toBe(false);
  });
});
