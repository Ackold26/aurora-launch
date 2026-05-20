<!--
  DrillDownModal — Sprint 3 transparency layer.

  Thin wrapper over <NotificationBanner level="prompt"> — all focus-trap,
  ESC, ARIA role="dialog", backdrop, and INV-14 reduced-motion are delegated
  to the base component.  This component only owns the drill-down content
  layout: formula (KaTeX), explanation, inputs table, output, provenance.
-->

<script lang="ts">
  import { _ } from 'svelte-i18n';
  import katex from 'katex';
  import 'katex/dist/katex.min.css';
  import NotificationBanner from '$lib/components/NotificationBanner.svelte';
  import { getFormula } from '$lib/utils/formulas';
  import type { FormulaEntry } from '$lib/utils/formulas';

  // ── Props ────────────────────────────────────────────────────────────────

  interface Props {
    /** Visibility — controlled by parent. */
    open: boolean;
    /** Close callback. */
    onClose: () => void;
    /** Direct formula entry. Wins over `formulaKey` if BOTH provided. Passing
     *  `formula={null}` explicitly is treated as deliberate null override
     *  (renders fallback "Нет данных"), even if `formulaKey` is valid —
     *  pass `formula={undefined}` (or omit) to enable formulaKey lookup. */
    formula?: FormulaEntry | null;
    /** Lookup-by-key alternative — internally resolves через getFormula().
     *  Used только когда `formula` prop is `undefined` (not `null`). */
    formulaKey?: string;
    /** Optional context-specific numeric value to display ("3.7%" for example). */
    contextValue?: string;
  }

  let { open, onClose, formula: formulaProp, formulaKey, contextValue }: Props = $props();

  // Resolve final formula — prop wins, else lookup by key.
  const formula: FormulaEntry | null = $derived(
    formulaProp !== undefined ? formulaProp : (formulaKey ? getFormula(formulaKey) : null)
  );

  // ── KaTeX rendering ──────────────────────────────────────────────────────

  let mathContainer: HTMLElement | undefined = $state();

  $effect(() => {
    if (!open || !formula || !mathContainer) return;
    try {
      katex.render(formula.latex, mathContainer, {
        throwOnError: false,
        displayMode: true,
        output: 'html', // 'html' explicit — НЕ emits MathML duplicate.
        strict: false, // allow cyrillic in \text{}
      });
      // Sprint 4 Batch 7 A3-C1 follow-up: previous Batch 4 attempted к hide
      // MathML elements (`.katex-mathml`, `annotation`) via aria-hidden but
      // `output: 'html'` config above prevents MathML emission entirely —
      // селектор matches zero elements. The aria-label на .dd-math (set к
      // `formula.text_fallback`) provides the canonical accessible name; AT
      // reads только текст fallback, no double-announce из MathML.
    } catch (e) {
      console.warn('[drill-down] KaTeX render failed, using text fallback:', e);
      mathContainer.textContent = formula.text_fallback;
    }
  });
</script>

<NotificationBanner
  level="prompt"
  {open}
  onDismiss={onClose}
  titleId="drill-title"
>
  {#snippet children()}
    {#if formula}
      <h2 id="drill-title" class="dd-title">
        {formula.title}
        {#if contextValue}
          <span class="drill-context-badge">{contextValue}</span>
        {/if}
      </h2>

      <div
        class="dd-math"
        role="img"
        aria-label={formula.text_fallback}
        aria-describedby="drill-explanation"
        bind:this={mathContainer}
      ></div>

      <p id="drill-explanation" class="dd-explanation">{formula.explanation}</p>

      {#if formula.inputs.length > 0}
        <h3 class="dd-section-heading">
          {$_('transparency.drill_down.inputs_heading', { default: 'Входные значения' })}
        </h3>
        <dl class="dd-inputs">
          {#each formula.inputs as input (input.symbol)}
            <dt><code class="dd-symbol">{input.symbol}</code></dt>
            <dd class="dd-desc">{input.description}</dd>
          {/each}
        </dl>
      {/if}

      <h3 class="dd-section-heading">
        {$_('transparency.drill_down.output_heading', { default: 'Результат' })}
      </h3>
      <p class="dd-output">{formula.output}</p>

      <footer class="dd-provenance">
        <span class="dd-provenance__label">
          {$_('transparency.drill_down.provenance_heading', { default: 'Источник' })}:
        </span>
        {#if formula.provenance.url}
          <a
            href={formula.provenance.url}
            target="_blank"
            rel="noopener noreferrer"
            class="dd-provenance__link"
            aria-label="{formula.provenance.citation} — {$_('transparency.drill_down.external_link_aria', { default: 'Открыть источник (откроется в новой вкладке)' })}"
          >
            <cite>{formula.provenance.citation}</cite>
            <svg class="dd-ext-icon" aria-hidden="true" focusable="false" width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M7 1h4v4M11 1 5.5 6.5M4 2H2a1 1 0 0 0-1 1v7a1 1 0 0 0 1 1h7a1 1 0 0 0 1-1V8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </a>
        {:else}
          <cite class="dd-provenance__cite">{formula.provenance.citation}</cite>
        {/if}
      </footer>
    {:else}
      <!-- Fallback when formula is null but open=true -->
      <h2 id="drill-title" class="dd-title">—</h2>
      <p class="dd-explanation">Нет данных для отображения формулы.</p>
    {/if}
  {/snippet}

  {#snippet actions()}
    <button
      type="button"
      class="nb-btn nb-btn--ghost"
      onclick={onClose}
    >
      {$_('transparency.drill_down.close_button', { default: 'Закрыть' })}
    </button>
  {/snippet}
</NotificationBanner>

<style>
  /* ── Title row ────────────────────────────────────────────────────────── */
  .dd-title {
    font-size: 1.25rem;
    font-weight: 600;
    margin: 0 0 var(--spacing-2, 0.5rem);
    color: var(--text-primary, #111);
    line-height: 1.3;
    /* Leave right-side room for the NotificationBanner × dismiss button */
    padding-right: var(--spacing-8, 2rem);
  }

  /* ── Context value badge ──────────────────────────────────────────────── */
  .drill-context-badge {
    display: inline-block;
    margin-left: var(--spacing-2, 0.5rem);
    padding: 1px 8px;
    border-radius: 12px;
    font-size: 0.8125rem;
    font-weight: 500;
    background: color-mix(in srgb, var(--accent, #2e5bff) 14%, transparent);
    color: var(--accent, #2e5bff);
    vertical-align: middle;
    line-height: 1.6;
  }

  /* ── Math display container ───────────────────────────────────────────── */
  .dd-math {
    background: var(--bg-elevated, #f8fafc);
    padding: var(--spacing-4, 1rem);
    border-radius: 6px;
    margin: var(--spacing-3, 0.75rem) 0;
    overflow-x: auto;
    min-height: 2.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  /* KaTeX injects its own elements; allow them to inherit overflow scroll */
  .dd-math :global(.katex-display) {
    margin: 0;
    overflow-x: auto;
    overflow-y: hidden;
  }

  /* ── Explanation paragraph ────────────────────────────────────────────── */
  .dd-explanation {
    margin: 0 0 var(--spacing-3, 0.75rem);
    color: var(--text-primary, #111);
    line-height: 1.55;
    font-size: 0.9375rem;
  }

  /* ── Section headings (h3) ────────────────────────────────────────────── */
  .dd-section-heading {
    font-size: 1rem;
    font-weight: 600;
    margin: var(--spacing-4, 1rem) 0 var(--spacing-1, 0.25rem);
    color: var(--text-secondary, #555);
  }

  /* ── Inputs definition list ───────────────────────────────────────────── */
  .dd-inputs {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: var(--spacing-2, 0.5rem) var(--spacing-3, 0.75rem);
    margin: 0 0 var(--spacing-2, 0.5rem);
  }

  .dd-symbol {
    font-family: var(--font-mono, monospace);
    font-size: 0.875rem;
    background: color-mix(in srgb, var(--accent, #2e5bff) 8%, transparent);
    color: var(--accent, #2e5bff);
    padding: 1px 6px;
    border-radius: 3px;
    white-space: nowrap;
  }

  .dd-desc {
    margin: 0;
    color: var(--text-primary, #111);
    font-size: 0.9375rem;
    line-height: 1.4;
    align-self: center;
  }

  /* ── Output ───────────────────────────────────────────────────────────── */
  .dd-output {
    margin: 0 0 var(--spacing-2, 0.5rem);
    color: var(--text-primary, #111);
    font-size: 0.9375rem;
    line-height: 1.55;
  }

  /* ── Provenance footer ────────────────────────────────────────────────── */
  .dd-provenance {
    border-top: 1px solid var(--border-subtle, #d1d5db);
    padding-top: var(--spacing-3, 0.75rem);
    margin-top: var(--spacing-4, 1rem);
    font-size: 0.875rem;
    color: var(--text-muted, #9ca3af);
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.25rem;
  }

  .dd-provenance__label {
    flex-shrink: 0;
    font-weight: 500;
  }

  .dd-provenance__link {
    color: var(--text-muted, #9ca3af);
    text-decoration: underline;
    text-underline-offset: 2px;
    display: inline-flex;
    align-items: baseline;
    gap: 3px;
  }

  .dd-provenance__link:hover {
    color: var(--text-secondary, #555);
  }

  .dd-provenance__cite {
    font-style: normal;
  }

  .dd-ext-icon {
    flex-shrink: 0;
    vertical-align: middle;
    position: relative;
    top: -1px;
  }
</style>
