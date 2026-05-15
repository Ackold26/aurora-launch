# Aurora Launch — Motion Design Specification

**Version:** 1.0  
**Date:** 2026-05-15  
**Scope:** All animated UI elements in Aurora Launch Planner frontend.  
**SSOT for motion tokens:** `tokens.css` → `--motion-duration-*` and `--motion-easing-*`  
**Implementation service:** `src/lib/services/motion.ts`

---

## 1. Principles

### 1.1 Purposeful
Every animation must communicate meaning — state change, spatial relationship, cause and effect. Decorative motion that adds no informational value is prohibited.

### 1.2 Responsive
Animations must not delay user interaction. Transitions respond within one frame to input events. Entry animations do not gate interactivity.

### 1.3 Consistent
Identical semantic events always use identical durations and easing curves. Use the canonical tokens; do not inline ad-hoc values (e.g. `transition: 200ms ease` without a token variable).

### 1.4 Informative
Motion signals hierarchy and relationship:
- **Enter** (spring-soft easing): element arrives from an ambient position, signals new content.
- **Exit** (exit easing): element leaves toward a neutral direction, signals removal.
- **Hover feedback** (standard easing, fast duration): confirms interactive affordance.
- **Selection / emphasis** (scale, spring-soft): communicates "this is chosen."

### 1.5 Accessible
**INV-14 mandatory:** When `prefers-reduced-motion: reduce` is active, all durations collapse to `0ms`. No transforms are applied. Visual state changes remain (colour, border) — only temporal animation is suppressed. The `motion.ts` service enforces this automatically via `window.matchMedia`.

### 1.6 Performant
Only CSS properties that do not trigger layout reflow are animated: `transform`, `opacity`, `box-shadow` (composite only), `filter`. Never animate `width`, `height`, `top`, `left`, `margin`, or `padding` in transitions.

---

## 2. Duration Scale

| Token | Value | Usage |
|---|---|---|
| `--motion-duration-instant` | `0ms` | No-op placeholder; used programmatically when motion is disabled |
| `--motion-duration-fast` | `80ms` | Micro-feedback: dot/checkbox toggle, button press ripple |
| `--motion-duration-normal` | `160ms` | Standard hover states, focus ring appearance |
| `--motion-duration-moderate` | `240ms` | Card enter/exit, drawer open, tooltip appear |
| `--motion-duration-slow` | `360ms` | Page-level transitions, slide carousel cross-fade |
| `--motion-duration-leisurely` | `480ms` | Emphasis animations, first-load hero entrance |

**Migration from legacy tokens (Block 2D):**

| Legacy token | Canonical replacement | Notes |
|---|---|---|
| `--motion-fast` | alias → `--motion-duration-normal` (160ms) | Was 150ms; harmonised to scale |
| `--motion-default` | alias → `--motion-duration-moderate` (240ms) | Was 200ms; harmonised |
| `--motion-smooth` | alias → `--motion-duration-slow` (360ms) | Was 320ms; harmonised |

Legacy aliases are preserved in `tokens.css` pointing to canonical values. No component needs immediate refactoring; aliases will be removed in a future cleanup pass after all usages are updated.

---

## 3. Easing Curves

| Token | Curve | Usage |
|---|---|---|
| `--motion-easing-standard` | `cubic-bezier(0.25, 0.1, 0.25, 1)` aka `ease` | Default for most hover/focus transitions |
| `--motion-easing-enter` | `cubic-bezier(0, 0, 0.2, 1)` | Decelerate on entry — element arrives softly |
| `--motion-easing-exit` | `cubic-bezier(0.4, 0, 1, 1)` | Accelerate on exit — element leaves quickly |
| `--motion-easing-spring-soft` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | Slight overshoot for spatial/selection emphasis |
| `--motion-easing-linear` | `linear` | Looping animations, progress bars |

**Migration from legacy easing tokens:**

| Legacy token | Canonical replacement |
|---|---|
| `--easing-spring` | alias → `--motion-easing-spring-soft` |
| `--easing-smooth` | alias → `--motion-easing-standard` |
| `--easing-emphasized` | alias → `--motion-easing-enter` |

Legacy easing aliases preserved for backward compatibility.

---

## 4. Component Application Guidelines

### Slide / Carousel transitions
- Duration: `--motion-duration-slow` (360ms)
- Easing: `--motion-easing-enter` for incoming slide, `--motion-easing-exit` for outgoing
- Reduced motion: static swap, no transform/opacity animation

### Card hover (scenario cards, history rows)
- Transform: `translateY(-2px)` or `scale(1.01)`
- Duration: `--motion-duration-normal` (160ms)
- Easing: `--motion-easing-spring-soft` for transform; `--motion-easing-standard` for colour/shadow

### Scale emphasis (selected state, CTA)
- Duration: `--motion-duration-fast` (80ms) → `--motion-duration-normal` (160ms) spring back
- Easing: `--motion-easing-spring-soft`

### Fade / opacity transitions
- Duration: `--motion-duration-moderate` (240ms)
- Easing: `--motion-easing-enter`

---

## 5. Reduced Motion (INV-14)

The CSS layer handles static zero-out via media query in `tokens.css`:

```css
@media (prefers-reduced-motion: reduce) {
  :root {
    --motion-duration-fast: 0ms;
    --motion-duration-normal: 0ms;
    --motion-duration-moderate: 0ms;
    --motion-duration-slow: 0ms;
    --motion-duration-leisurely: 0ms;
    /* legacy aliases also zeroed */
    --motion-fast: 0ms;
    --motion-default: 0ms;
    --motion-smooth: 0ms;
  }
}
```

The `motion.ts` service reads `window.matchMedia('(prefers-reduced-motion: reduce)')` at call time. When reduced, all JS-driven transitions return `duration: 0` and no CSS transform strings — ensuring Svelte `transition:` directives also short-circuit.

---

## 6. Implementation Reference

```ts
import { fadeIn, slideUp, scaleIn } from '$lib/services/motion';

// In Svelte template:
<div transition:fadeIn>…</div>
<div in:slideUp={{ delay: 80 }}>…</div>
<button in:scaleIn>…</button>
```

All three helpers short-circuit to `duration: 0` under reduced motion automatically.

---

## 7. Revision History

| Date | Author | Change |
|---|---|---|
| 2026-05-15 | Маша (Claude) | Initial specification v1.0, tokens aligned with Material Design motion model |
