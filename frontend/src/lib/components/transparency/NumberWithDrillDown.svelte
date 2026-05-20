<!--
  NumberWithDrillDown — Sprint 3 A18 two-tier transparency UX.

  Tier 1 — Hover tooltip (pointer device only, CSS-only for ≤100ms latency).
  Tier 2 — Click/tap → DrillDownModal (formula, KaTeX, provenance).

  Touch devices: info button is ALWAYS visible (no hover dependency).
  Pointer devices: info button fades in on hover; tooltip appears on hover.

  INV-14: prefers-reduced-motion respected — tooltip transition: none.
  Graceful degradation: unknown formulaKey → value-only span, no affordance.
-->

<script lang="ts">
  import { _ } from 'svelte-i18n';
  import { getFormula, firstSentence } from '$lib/utils/formulas';
  import type { FormulaEntry } from '$lib/utils/formulas';
  import DrillDownModal from './DrillDownModal.svelte';

  // ── Props ─────────────────────────────────────────────────────────────────

  interface Props {
    /**
     * Formula key to look up in registry.
     * If unknown, component renders value-only (no drill-down affordance).
     */
    formulaKey: string;
    /** Displayed value (e.g. "3.7%", "1 234 ₽", "0.94"). */
    value: string;
    /** Optional CSS class for the wrapper. */
    class?: string;
  }

  let { formulaKey, value, class: extraClass = '' }: Props = $props();

  // ── Formula lookup — $derived so Svelte tracks the prop access properly ──

  const formula: FormulaEntry | null = $derived(getFormula(formulaKey));

  // ── Tooltip text: first sentence of explanation ──────────────────────────

  const tooltipText: string = $derived.by(() => {
    if (!formula) return '';
    return firstSentence(formula.explanation);
  });

  // ── Modal state ───────────────────────────────────────────────────────────

  let modalOpen: boolean = $state(false);

  function openModal(): void {
    modalOpen = true;
  }

  function closeModal(): void {
    modalOpen = false;
  }

  // ── Keyboard handler for the value span (role=button) ────────────────────

  function handleValueKeydown(e: KeyboardEvent): void {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      openModal();
    }
  }
</script>

{#if !formula}
  <!--
    Graceful degradation — no drill-down affordance for unknown keys.
    Renders as an unadorned span; no empty info button, no broken tooltip.
  -->
  <span class={extraClass || undefined}>{value}</span>
{:else}
  <!--
    Wrapper span carries [data-tooltip] for CSS-only tooltip.
    NOT a button — number is informational; the inner value span
    gets role=button for keyboard activation.
  -->
  <span
    class="number-drill {extraClass}"
    data-tooltip={tooltipText}
  >
    <span
      class="number-drill-value"
      role="button"
      tabindex="0"
      aria-label={$_('transparency.number_drill.value_aria', {
        default: '{value} — нажмите для деталей',
        values: { value },
      })}
      onclick={openModal}
      onkeydown={handleValueKeydown}
    >{value}</span>

    <button
      type="button"
      class="number-drill-info"
      aria-label={$_('transparency.number_drill.info_aria', {
        default: 'Подробнее о формуле: {title}',
        values: { title: formula.title },
      })}
      onclick={openModal}
    >i</button>
  </span>

  <DrillDownModal
    open={modalOpen}
    {formula}
    contextValue={value}
    onClose={closeModal}
  />
{/if}

<style>
  /* ── Wrapper ──────────────────────────────────────────────────────────── */
  .number-drill {
    display: inline-flex;
    align-items: baseline;
    gap: 2px;
    position: relative;
    /* focus-within outline shows when value span or info btn is focused */
    border-radius: 3px;
  }

  .number-drill:focus-within {
    outline: 2px solid var(--accent, #2e5bff);
    outline-offset: 2px;
  }

  /* ── Value span (role=button) ─────────────────────────────────────────── */
  .number-drill-value {
    cursor: pointer;
    /* Subtle underline hint for interactivity */
    text-decoration: underline;
    text-decoration-style: dotted;
    text-decoration-color: color-mix(in srgb, currentColor 40%, transparent);
    text-underline-offset: 2px;
  }

  .number-drill-value:focus-visible {
    outline: none; /* parent .number-drill:focus-within handles outline */
  }

  /* ── Info button ──────────────────────────────────────────────────────── */
  /*
    A1 (Sprint 4 Batch 4 — WCAG 2.5.8 Target Size Minimum, Level AA):
      Minimum interactive target = 24×24 CSS pixels. Visual button stays
      16×16 but a ::before pseudo-element extends the click/tap hit area
      to 24×24 (16 + 4*2 inset). Visual design unchanged для sighted
      users — accessibility upgraded для motor-impaired / touch users.
  */
  .number-drill-info {
    position: relative; /* anchor for ::before hit-area expansion */
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1rem;
    height: 1rem;
    font-size: 0.625rem;
    font-style: italic;
    font-weight: 700;
    line-height: 1;
    border-radius: 50%;
    border: 1px solid color-mix(in srgb, var(--accent, #2e5bff) 60%, transparent);
    color: var(--accent, #2e5bff);
    background: transparent;
    cursor: pointer;
    padding: 0;
    flex-shrink: 0;
    /* Default: always visible (touch-safe) */
    opacity: 1;
    transition: opacity 120ms ease, color 120ms ease;
    vertical-align: middle;
    margin-bottom: 0.1em; /* optical alignment with text baseline */
  }

  /* A1: invisible hit-area expansion. ::before captures clicks/taps выходящие
     beyond the visible 16×16 button (4px on each side → 24×24 hit area). */
  .number-drill-info::before {
    content: '';
    position: absolute;
    inset: -4px;
    /* No background — invisible. Pointer events propagate through к button. */
  }

  .number-drill-info:focus-visible {
    outline: none; /* parent :focus-within handles outline */
  }

  .number-drill-info:hover {
    background: color-mix(in srgb, var(--accent, #2e5bff) 10%, transparent);
  }

  /* A6 (Sprint 4 Batch 4): @media (hover: hover) and (pointer: fine) — stricter
     than `pointer: fine` alone. Hybrid devices (iPad с trackpad, Surface)
     report `pointer: fine` но `hover: none` — the previous query incorrectly
     applied hover-fade на these surfaces, hiding the info button когда trackpad
     user touched the screen. Combined media query targets ТОЛЬКО true mouse
     interactions. */
  @media (hover: hover) and (pointer: fine) {
    /* Pointer device — fade info button when not hovering */
    .number-drill-info {
      opacity: 0.4;
    }

    .number-drill:hover .number-drill-info,
    .number-drill:focus-within .number-drill-info {
      opacity: 1;
    }
  }

  /* ── CSS-only tooltip ─────────────────────────────────────────────────── */
  /*
    Uses [data-tooltip]::after — no JS, no requestAnimationFrame.
    Latency is paint-synchronous; satisfies ≤100ms requirement.
    Only activates on pointer:fine (no conflict with touch tap-zoom on iOS).
  */

  .number-drill[data-tooltip]::after {
    content: attr(data-tooltip);
    position: absolute;
    bottom: calc(100% + 6px);
    left: 50%;
    transform: translateX(-50%);
    background: var(--text-primary, #111);
    color: var(--surface-base, #fff);
    padding: 6px 10px;
    border-radius: 4px;
    white-space: normal;
    min-width: 200px;
    max-width: 320px;
    font-size: 0.75rem;
    line-height: 1.4;
    pointer-events: none;
    opacity: 0;
    transition: opacity 100ms ease;
    z-index: 100;
    /* Prevent tooltip from appearing on touch devices */
    /* (pointer:fine guard below handles actual activation) */
  }

  /* A6: hover-only activation для tooltip — see info button @media above. */
  @media (hover: hover) and (pointer: fine) {
    .number-drill[data-tooltip]:hover::after,
    .number-drill[data-tooltip]:focus-within::after {
      opacity: 1;
    }
  }

  /* ── INV-14: reduce motion ────────────────────────────────────────────── */
  @media (prefers-reduced-motion: reduce) {
    .number-drill[data-tooltip]::after {
      transition: none;
    }

    .number-drill-info {
      transition: none;
    }
  }
</style>
