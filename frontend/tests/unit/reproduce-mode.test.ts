// Unit tests for M-09 reproduce-mode detection utility.
// Covers the three classification cases: real payload, legacy payload,
// and partial payload (anchors present but spend_plan empty/absent).
//
// detectReproduceMode() is a pure function — no jsdom / Svelte mount needed.

import { describe, it, expect } from 'vitest';
import { detectReproduceMode } from '../../src/lib/utils/reproduce-mode';

describe('detectReproduceMode', () => {
  // ─── Real payload (v0.1.1+ bundles) ─────────────────────────────────────────

  it('isReal=true when anchors + non-empty spend_plan both present', () => {
    const result = detectReproduceMode({
      anchors: {
        market_size: 1_500_000,
        market_size_cv: 0.12,
        planned_share_trajectory: [0.04, 0.05, 0.06],
        distribution_trajectory: [0.8, 0.85, 0.9],
        pricing_index: 1.0,
        elasticity: -0.3,
        seasonality: null,
      },
      spendPlan: {
        tv: [1_000_000, 900_000, 1_100_000],
        digital: [500_000, 600_000, 700_000],
      },
    });
    expect(result.isReal).toBe(true);
  });

  it('isReal=true with minimal valid anchors (single key) + single-key spend_plan', () => {
    const result = detectReproduceMode({
      anchors: { market_size: 500_000 },
      spendPlan: { tv: [100_000] },
    });
    expect(result.isReal).toBe(true);
  });

  // ─── Legacy payload (pre-v0.1.1 bundles) ─────────────────────────────────────

  it('isReal=false when anchors is null (legacy bundle)', () => {
    const result = detectReproduceMode({
      anchors: null,
      spendPlan: { tv: [100_000] },
    });
    expect(result.isReal).toBe(false);
  });

  it('isReal=false when anchors is undefined (field missing in JSON)', () => {
    const result = detectReproduceMode({
      anchors: undefined,
      spendPlan: { tv: [100_000] },
    });
    expect(result.isReal).toBe(false);
  });

  it('isReal=false when both anchors and spend_plan are null', () => {
    const result = detectReproduceMode({
      anchors: null,
      spendPlan: null,
    });
    expect(result.isReal).toBe(false);
  });

  it('isReal=false when both anchors and spend_plan are undefined (empty object from legacy)', () => {
    const result = detectReproduceMode({});
    expect(result.isReal).toBe(false);
  });

  // ─── Partial payload (safe conservative fallback) ────────────────────────────

  it('isReal=false when anchors present but spend_plan is null', () => {
    const result = detectReproduceMode({
      anchors: { market_size: 1_000_000 },
      spendPlan: null,
    });
    expect(result.isReal).toBe(false);
  });

  it('isReal=false when anchors present but spend_plan is undefined', () => {
    const result = detectReproduceMode({
      anchors: { market_size: 1_000_000 },
      spendPlan: undefined,
    });
    expect(result.isReal).toBe(false);
  });

  it('isReal=false when anchors present but spend_plan is empty object', () => {
    const result = detectReproduceMode({
      anchors: { market_size: 1_000_000, market_size_cv: 0.1 },
      spendPlan: {},
    });
    expect(result.isReal).toBe(false);
  });

  // ─── reason field sanity ─────────────────────────────────────────────────────

  it('real result contains non-empty reason string', () => {
    const result = detectReproduceMode({
      anchors: { market_size: 1_000_000 },
      spendPlan: { tv: [100_000] },
    });
    expect(typeof result.reason).toBe('string');
    expect(result.reason.length).toBeGreaterThan(0);
  });

  it('legacy result contains non-empty reason string', () => {
    const result = detectReproduceMode({ anchors: null, spendPlan: null });
    expect(typeof result.reason).toBe('string');
    expect(result.reason.length).toBeGreaterThan(0);
  });
});
