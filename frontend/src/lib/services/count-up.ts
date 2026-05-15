/**
 * Phase Magic M-10: count-up animation utility.
 *
 * Smoothly animates a numeric value от start к end over duration_ms.
 * Used in confidence narrative diff panel + trust score reveals.
 *
 * Respects prefers-reduced-motion (INV-14): jumps immediately к end value.
 *
 * Usage:
 *   const stop = countUp(0, 20, 600, (v) => myDisplayValue = v);
 *   // ... later if needed: stop();
 */

export type CountUpCallback = (current: number) => void;
export type StopFn = () => void;

/**
 * Animate a value from start к end, calling cb on each frame.
 *
 * @param start Starting value
 * @param end Target value
 * @param durationMs Animation duration (ignored if prefers-reduced-motion)
 * @param cb Called с current interpolated value on each animation frame
 * @returns Stop function — cancels animation early
 */
export function countUp(
  start: number,
  end: number,
  durationMs: number,
  cb: CountUpCallback,
): StopFn {
  // Reduced motion: jump straight к end, single sync callback
  if (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  ) {
    cb(end);
    return () => {};
  }

  // No animation timing API в SSR — sync to end value
  if (typeof requestAnimationFrame !== 'function') {
    cb(end);
    return () => {};
  }

  let rafId: number | null = null;
  let cancelled = false;
  const t0 = performance.now();
  const delta = end - start;

  function tick(now: number) {
    if (cancelled) return;
    const elapsed = now - t0;
    const progress = Math.min(1, Math.max(0, elapsed / durationMs));
    // easeOutCubic — fast start, gentle settle
    const eased = 1 - Math.pow(1 - progress, 3);
    const current = start + delta * eased;
    cb(current);
    if (progress < 1) {
      rafId = requestAnimationFrame(tick);
    }
  }

  rafId = requestAnimationFrame(tick);

  return () => {
    cancelled = true;
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
    }
  };
}
