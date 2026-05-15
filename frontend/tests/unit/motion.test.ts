/**
 * Unit tests for src/lib/services/motion.ts
 *
 * Tests:
 *   1. fadeIn  — returns correct duration and CSS opacity keyframe
 *   2. slideUp — returns correct duration and CSS transform+opacity keyframe
 *   3. scaleIn — returns correct duration and CSS scale+opacity keyframe
 *   4. prefers-reduced-motion mock → all helpers return duration: 0
 *   5. Custom delay param propagates to result.delay
 *   6. Custom duration param propagates to result.duration
 */

import { describe, expect, it, vi, afterEach } from 'vitest';

import {
  fadeIn,
  slideUp,
  scaleIn,
  prefersReducedMotion,
  easingEnter,
  easingSpring,
} from '../../src/lib/services/motion';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Stub element — transition helpers accept Element but don't use it. */
const STUB_NODE = {} as Element;

/**
 * Mock window.matchMedia to return a specific prefers-reduced-motion value.
 * Returns a restore function to undo the mock.
 */
function mockReducedMotion(reduced: boolean): () => void {
  const original = window.matchMedia;
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query === '(prefers-reduced-motion: reduce)' ? reduced : false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
  return () => {
    window.matchMedia = original;
  };
}

// ---------------------------------------------------------------------------
// Teardown
// ---------------------------------------------------------------------------

afterEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('prefersReducedMotion()', () => {
  it('returns false when prefers-reduced-motion is not set', () => {
    const restore = mockReducedMotion(false);
    expect(prefersReducedMotion()).toBe(false);
    restore();
  });

  it('returns true when prefers-reduced-motion: reduce is active', () => {
    const restore = mockReducedMotion(true);
    expect(prefersReducedMotion()).toBe(true);
    restore();
  });
});

describe('fadeIn()', () => {
  it('returns result with default duration 240ms', () => {
    const restore = mockReducedMotion(false);
    const result = fadeIn(STUB_NODE);
    expect(result.duration).toBe(240);
    restore();
  });

  it('CSS function at t=1 produces full opacity', () => {
    const restore = mockReducedMotion(false);
    const result = fadeIn(STUB_NODE);
    expect(result.css(1, 0)).toBe('opacity: 1');
    restore();
  });

  it('CSS function at t=0 produces zero opacity', () => {
    const restore = mockReducedMotion(false);
    const result = fadeIn(STUB_NODE);
    expect(result.css(0, 1)).toBe('opacity: 0');
    restore();
  });

  it('uses easingEnter (returns same output at t=0.5)', () => {
    const restore = mockReducedMotion(false);
    const result = fadeIn(STUB_NODE);
    // easingEnter(0.5) ≈ 0.875; verify the easing fn is functionally compatible
    const expected = easingEnter(0.5);
    expect(result.easing(0.5)).toBeCloseTo(expected, 6);
    restore();
  });
});

describe('slideUp()', () => {
  it('returns result with default duration 240ms', () => {
    const restore = mockReducedMotion(false);
    const result = slideUp(STUB_NODE);
    expect(result.duration).toBe(240);
    restore();
  });

  it('CSS at t=1 produces no translateY offset and full opacity', () => {
    const restore = mockReducedMotion(false);
    const result = slideUp(STUB_NODE);
    const css = result.css(1, 0);
    // At t=1: offsetY = 0, opacity = 1
    expect(css).toContain('translateY(0px)');
    expect(css).toContain('opacity: 1');
    restore();
  });

  it('CSS at t=0 produces 16px translateY offset and zero opacity', () => {
    const restore = mockReducedMotion(false);
    const result = slideUp(STUB_NODE);
    const css = result.css(0, 1);
    expect(css).toContain('translateY(16px)');
    expect(css).toContain('opacity: 0');
    restore();
  });

  it('uses spring easing (same as easingSpring at t=0.5)', () => {
    const restore = mockReducedMotion(false);
    const result = slideUp(STUB_NODE);
    expect(result.easing(0.5)).toBeCloseTo(easingSpring(0.5), 6);
    restore();
  });
});

describe('scaleIn()', () => {
  it('returns result with default duration 160ms', () => {
    const restore = mockReducedMotion(false);
    const result = scaleIn(STUB_NODE);
    expect(result.duration).toBe(160);
    restore();
  });

  it('CSS at t=1 produces scale(1) and full opacity', () => {
    const restore = mockReducedMotion(false);
    const result = scaleIn(STUB_NODE);
    const css = result.css(1, 0);
    expect(css).toContain('scale(1)');
    expect(css).toContain('opacity: 1');
    restore();
  });

  it('CSS at t=0 produces scale(0.92) and zero opacity', () => {
    const restore = mockReducedMotion(false);
    const result = scaleIn(STUB_NODE);
    const css = result.css(0, 1);
    expect(css).toContain('scale(0.92)');
    expect(css).toContain('opacity: 0');
    restore();
  });
});

describe('prefers-reduced-motion: all helpers return duration 0', () => {
  it('fadeIn returns duration: 0 when reduced motion active', () => {
    const restore = mockReducedMotion(true);
    const result = fadeIn(STUB_NODE);
    expect(result.duration).toBe(0);
    restore();
  });

  it('slideUp returns duration: 0 when reduced motion active', () => {
    const restore = mockReducedMotion(true);
    const result = slideUp(STUB_NODE);
    expect(result.duration).toBe(0);
    restore();
  });

  it('scaleIn returns duration: 0 when reduced motion active', () => {
    const restore = mockReducedMotion(true);
    const result = scaleIn(STUB_NODE);
    expect(result.duration).toBe(0);
    restore();
  });

  it('fadeIn reduced-motion: CSS returns empty string (no visual change)', () => {
    const restore = mockReducedMotion(true);
    const result = fadeIn(STUB_NODE);
    expect(result.css(0.5, 0.5)).toBe('');
    restore();
  });

  it('slideUp reduced-motion: CSS returns empty string', () => {
    const restore = mockReducedMotion(true);
    const result = slideUp(STUB_NODE);
    expect(result.css(0.5, 0.5)).toBe('');
    restore();
  });

  it('scaleIn reduced-motion: CSS returns empty string', () => {
    const restore = mockReducedMotion(true);
    const result = scaleIn(STUB_NODE);
    expect(result.css(0.5, 0.5)).toBe('');
    restore();
  });
});

describe('custom params propagation', () => {
  it('custom delay param propagates to result.delay', () => {
    const restore = mockReducedMotion(false);
    const result = fadeIn(STUB_NODE, { delay: 120 });
    expect(result.delay).toBe(120);
    restore();
  });

  it('custom duration param propagates to result.duration', () => {
    const restore = mockReducedMotion(false);
    const result = fadeIn(STUB_NODE, { duration: 500 });
    expect(result.duration).toBe(500);
    restore();
  });

  it('slideUp custom duration propagates', () => {
    const restore = mockReducedMotion(false);
    const result = slideUp(STUB_NODE, { duration: 300, delay: 50 });
    expect(result.duration).toBe(300);
    expect(result.delay).toBe(50);
    restore();
  });

  it('scaleIn custom duration propagates', () => {
    const restore = mockReducedMotion(false);
    const result = scaleIn(STUB_NODE, { duration: 80 });
    expect(result.duration).toBe(80);
    restore();
  });

  it('reduced motion ignores custom duration — always 0', () => {
    const restore = mockReducedMotion(true);
    const result = fadeIn(STUB_NODE, { duration: 999 });
    expect(result.duration).toBe(0);
    restore();
  });

  it('reduced motion ignores custom delay — always 0', () => {
    const restore = mockReducedMotion(true);
    const result = slideUp(STUB_NODE, { delay: 200 });
    expect(result.delay).toBe(0);
    restore();
  });
});
