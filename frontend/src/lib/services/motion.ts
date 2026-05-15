/**
 * motion.ts — Reusable Svelte 5 transition helpers.
 *
 * All helpers respect prefers-reduced-motion (INV-14):
 *   - When reduced: duration → 0, no CSS transform/opacity change.
 *   - When normal:  uses canonical --motion-duration-* and --motion-easing-* tokens.
 *
 * Usage:
 *   import { fadeIn, slideUp, scaleIn } from '$lib/services/motion';
 *
 *   <div transition:fadeIn>…</div>
 *   <div in:slideUp={{ delay: 80 }}>…</div>
 *   <button in:scaleIn>…</button>
 *
 * No external deps — uses Svelte built-in transition contract:
 *   { delay, duration, easing, css } as per svelte/transition interface.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Parameters accepted by all transition helpers. */
export interface MotionParams {
  /** Delay before transition starts, ms. Ignored under reduced motion. */
  delay?: number;
  /** Override duration, ms. Ignored under reduced motion (always 0). */
  duration?: number;
}

/**
 * Svelte transition return shape.
 * Matches the object returned by built-in helpers like `fade`, `fly`, etc.
 */
export interface TransitionResult {
  delay: number;
  duration: number;
  easing: (t: number) => number;
  css: (t: number, u: number) => string;
}

// ---------------------------------------------------------------------------
// Reduced motion detection
// ---------------------------------------------------------------------------

/**
 * Returns true if the OS/browser reports prefers-reduced-motion: reduce.
 * Checked at call time (not cached) so hot preference changes take effect
 * on the next transition invocation without page reload.
 *
 * Safe in SSR contexts (no window): returns false (default to motion on).
 */
export function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

// ---------------------------------------------------------------------------
// Easing functions — mirrors CSS cubic-bezier tokens (MOTION.md §3)
// ---------------------------------------------------------------------------

/** Standard easing: cubic-bezier(0.25, 0.1, 0.25, 1) — default hover/focus. */
export function easingStandard(t: number): number {
  // Approximated via cubic hermite interpolation of the bezier.
  // For Svelte transitions, easing(t) maps [0,1] → [0,1].
  return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
}

/** Enter easing: cubic-bezier(0, 0, 0.2, 1) — decelerate on entry. */
export function easingEnter(t: number): number {
  // Approximation: aggressive early acceleration, soft landing.
  return 1 - Math.pow(1 - t, 3);
}

/** Exit easing: cubic-bezier(0.4, 0, 1, 1) — accelerate on exit. */
export function easingExit(t: number): number {
  return t * t * t;
}

/** Spring-soft easing: cubic-bezier(0.34, 1.56, 0.64, 1) — slight overshoot. */
export function easingSpring(t: number): number {
  // Elastic-style approximation with overshoot at t ≈ 0.7.
  const c4 = (2 * Math.PI) / 3;
  if (t === 0) return 0;
  if (t === 1) return 1;
  return Math.pow(2, -8 * t) * Math.sin((t * 10 - 0.75) * c4) + 1;
}

/** Linear easing — progress bars, looping animations. */
export function easingLinear(t: number): number {
  return t;
}

// ---------------------------------------------------------------------------
// No-op transition (reduced motion)
// ---------------------------------------------------------------------------

/** Instant no-op transition returned under prefers-reduced-motion. */
function noopTransition(): TransitionResult {
  return {
    delay: 0,
    duration: 0,
    easing: easingLinear,
    css: () => '',
  };
}

// ---------------------------------------------------------------------------
// Transition: fadeIn
// ---------------------------------------------------------------------------

/**
 * fadeIn — opacity 0 → 1.
 * Easing: --motion-easing-enter (decelerate).
 * Duration default: --motion-duration-moderate (240ms).
 *
 * @param _node  DOM node (unused — CSS-only transition)
 * @param params Optional delay and duration overrides
 */
export function fadeIn(_node: Element, params?: MotionParams): TransitionResult {
  if (prefersReducedMotion()) return noopTransition();

  const duration = params?.duration ?? 240;
  const delay = params?.delay ?? 0;

  return {
    delay,
    duration,
    easing: easingEnter,
    css: (t: number) => `opacity: ${t}`,
  };
}

// ---------------------------------------------------------------------------
// Transition: slideUp
// ---------------------------------------------------------------------------

/**
 * slideUp — element slides up from +16px offset while fading in.
 * Easing: --motion-easing-spring-soft (slight overshoot).
 * Duration default: --motion-duration-moderate (240ms).
 *
 * @param _node  DOM node (unused — CSS-only transition)
 * @param params Optional delay and duration overrides
 */
export function slideUp(_node: Element, params?: MotionParams): TransitionResult {
  if (prefersReducedMotion()) return noopTransition();

  const duration = params?.duration ?? 240;
  const delay = params?.delay ?? 0;

  return {
    delay,
    duration,
    easing: easingSpring,
    css: (t: number) => {
      const offsetY = (1 - t) * 16;
      return `transform: translateY(${offsetY}px); opacity: ${t}`;
    },
  };
}

// ---------------------------------------------------------------------------
// Transition: scaleIn
// ---------------------------------------------------------------------------

/**
 * scaleIn — element scales from 0.92 → 1 while fading in.
 * For emphasis: selected state, CTA buttons, modal entry.
 * Easing: --motion-easing-spring-soft (slight overshoot).
 * Duration default: --motion-duration-normal (160ms).
 *
 * @param _node  DOM node (unused — CSS-only transition)
 * @param params Optional delay and duration overrides
 */
export function scaleIn(_node: Element, params?: MotionParams): TransitionResult {
  if (prefersReducedMotion()) return noopTransition();

  const duration = params?.duration ?? 160;
  const delay = params?.delay ?? 0;

  return {
    delay,
    duration,
    easing: easingSpring,
    css: (t: number) => {
      const scale = 0.92 + t * 0.08;
      return `transform: scale(${scale}); opacity: ${t}`;
    },
  };
}
