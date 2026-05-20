<!--
  ChartWithDrillDown — Sprint 3 A18 two-tier transparency UX for charts.

  Wraps any chart component with a labeled section + "Как считается?" button
  that opens DrillDownModal with the formula behind the chart.

  Touch devices: info button always visible.
  Pointer devices: button slightly faded until hover (consistent with NumberWithDrillDown).
  NO tooltip on chart — charts are large, direct modal-on-click is the only path.

  Graceful degradation: unknown formulaKey → button hidden, chart renders normally.
  INV-14: no motion artefacts in this component (no animations to reduce).
-->

<script lang="ts">
  import type { Snippet } from 'svelte';
  import { _ } from 'svelte-i18n';
  import { getFormula, firstSentence } from '$lib/utils/formulas';
  import type { FormulaEntry } from '$lib/utils/formulas';
  import DrillDownModal from './DrillDownModal.svelte';

  // ── Instance ID (module-level counter, SSR-safe) ─────────────────────────

  let _instanceCounter = 0;
  function nextInstanceId(): string {
    _instanceCounter += 1;
    return `cdd${_instanceCounter}`;
  }

  // ── Props ─────────────────────────────────────────────────────────────────

  interface Props {
    /** Formula key to look up in registry. */
    formulaKey: string;
    /** Title shown above chart + passed as contextValue to DrillDownModal. */
    chartTitle: string;
    /** Children snippet — actual chart component rendered inside the card. */
    children: Snippet;
    /**
     * Optional override for the subtitle line shown below the title.
     * If absent, formula.explanation (first sentence) is used.
     * If formulaKey unknown, no subtitle is rendered.
     */
    subtitleOverride?: string;
  }

  let { formulaKey, chartTitle, children, subtitleOverride }: Props = $props();

  // ── Formula lookup — $derived so Svelte tracks the prop access properly ──

  const formula: FormulaEntry | null = $derived(getFormula(formulaKey));

  // ── Subtitle: override → first sentence of explanation → nothing ─────────

  const subtitle: string = $derived.by(() => {
    if (subtitleOverride !== undefined) return subtitleOverride;
    if (!formula) return '';
    return firstSentence(formula.explanation);
  });

  // ── Per-instance ID for aria-labelledby ──────────────────────────────────

  const instanceId: string = nextInstanceId();
  const titleId: string = `chart-title-${instanceId}`;

  // ── Modal state ───────────────────────────────────────────────────────────

  let modalOpen: boolean = $state(false);

  function openModal(): void {
    modalOpen = true;
  }

  function closeModal(): void {
    modalOpen = false;
  }
</script>

<section class="chart-drill" aria-labelledby={titleId}>
  <header class="chart-drill-header">
    <div class="chart-drill-header-left">
      <h3 id={titleId} class="chart-drill-title">{chartTitle}</h3>
      {#if subtitle}
        <p class="chart-drill-subtitle">{subtitle}</p>
      {/if}
    </div>

    {#if formula}
      <button
        type="button"
        class="chart-drill-info"
        aria-label={$_('transparency.chart_drill.info_aria', {
          default: 'Подробнее о методике: {chartTitle}',
          values: { chartTitle },
        })}
        onclick={openModal}
      >
        <!--
          Inline info SVG — 14×14 viewBox, no external dep.
          Circular "i" — universally understood affordance.
        -->
        <svg
          class="chart-drill-info-icon"
          aria-hidden="true"
          focusable="false"
          width="14"
          height="14"
          viewBox="0 0 14 14"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <circle cx="7" cy="7" r="6.25" stroke="currentColor" stroke-width="1.5"/>
          <rect x="6.25" y="6" width="1.5" height="4.5" rx="0.75" fill="currentColor"/>
          <circle cx="7" cy="4" r="0.875" fill="currentColor"/>
        </svg>

        <span class="chart-drill-info-label">
          {$_('transparency.chart_drill.info_label', { default: 'Как считается?' })}
        </span>
      </button>
    {/if}
  </header>

  <div class="chart-drill-body">
    {@render children()}
  </div>
</section>

{#if formula}
  <DrillDownModal
    open={modalOpen}
    {formula}
    contextValue={chartTitle}
    onClose={closeModal}
  />
{/if}

<style>
  /* ── Section wrapper ──────────────────────────────────────────────────── */
  .chart-drill {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-3, 0.75rem);
  }

  /* ── Header row ───────────────────────────────────────────────────────── */
  .chart-drill-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: var(--spacing-3, 0.75rem);
    flex-wrap: wrap;
  }

  .chart-drill-header-left {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1, 0.25rem);
    min-width: 0; /* allow text truncation in constrained containers */
  }

  /* ── Title (h3) ───────────────────────────────────────────────────────── */
  .chart-drill-title {
    margin: 0;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary, #111);
    line-height: 1.3;
  }

  /* ── Subtitle (first sentence of formula explanation) ────────────────── */
  .chart-drill-subtitle {
    margin: 0;
    font-size: 0.8125rem;
    color: var(--text-secondary, #555);
    line-height: 1.4;
  }

  /* ── Info button ──────────────────────────────────────────────────────── */
  .chart-drill-info {
    display: inline-flex;
    align-items: center;
    gap: var(--spacing-1, 0.25rem);
    padding: 2px var(--spacing-2, 0.5rem);
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--accent, #2e5bff);
    background: transparent;
    border: 1px solid color-mix(in srgb, var(--accent, #2e5bff) 35%, transparent);
    border-radius: 4px;
    cursor: pointer;
    white-space: nowrap;
    flex-shrink: 0;
    align-self: flex-start;
    /* Default: always visible (touch-safe) */
    opacity: 1;
    transition: opacity 120ms ease, background 120ms ease, border-color 120ms ease;
  }

  .chart-drill-info:hover {
    background: color-mix(in srgb, var(--accent, #2e5bff) 8%, transparent);
    border-color: color-mix(in srgb, var(--accent, #2e5bff) 60%, transparent);
  }

  .chart-drill-info:focus-visible {
    outline: 2px solid var(--accent, #2e5bff);
    outline-offset: 2px;
  }

  /* A6 (Sprint 4 Batch 4): stricter than `pointer: fine` alone — hybrid devices
     like iPad с trackpad report fine pointer без hover capability, leading к
     info button hiding на touch. `hover: hover` filters к true mouse-driven
     interactions only. */
  @media (hover: hover) and (pointer: fine) {
    /* Pointer device — slightly fade when container not hovered */
    .chart-drill-info {
      opacity: 0.55;
    }

    .chart-drill:hover .chart-drill-info,
    .chart-drill:focus-within .chart-drill-info {
      opacity: 1;
    }
  }

  /* ── Info icon ────────────────────────────────────────────────────────── */
  .chart-drill-info-icon {
    flex-shrink: 0;
    /* optical vertical alignment */
    position: relative;
    top: 0.5px;
  }

  /* ── Chart body ───────────────────────────────────────────────────────── */
  .chart-drill-body {
    /* Let the chart component control its own dimensions.
       Wrapper is transparent — no border, no background imposed here.
       Consumers (ForecastCone, BudgetSplitChart, etc.) own their sizing. */
    min-width: 0;
  }

  /* ── INV-14: reduce motion ────────────────────────────────────────────── */
  @media (prefers-reduced-motion: reduce) {
    .chart-drill-info {
      transition: none;
    }
  }
</style>
