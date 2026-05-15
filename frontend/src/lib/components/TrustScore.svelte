<!--
  TrustScore — Forecast confidence single-number widget (Phase Π.3.3).

  Closes audit P-09 (Observability default = trust score 0-100, not MCMC
  diagnostics). Per INV-25 dual-mode UX: Manager mode default shows score
  + verdict; Expert mode (opt-in) разворачивает R̂ / ESS / divergent
  transitions / drift parameters.

  Calculation rules (per Plan v3.0 §A.5):

    score = round(weighted_average(
      proxy_similarity_score * 30,
      methodology_certified * 20,
      model_convergence_passed * 20,
      data_sufficiency * 20,
      uncertainty_pct_inverse * 10
    ))

  Score ranges:
    90-100 → "Очень высокий"  (vivid green)
    75-89  → "Высокий"          (green)
    60-74  → "Средний"           (amber)
    40-59  → "Низкий"             (orange)
    0-39   → "Не подтверждён"     (red)
-->

<script lang="ts">
  import { _ } from 'svelte-i18n';

  interface DiagnosticDetail {
    label: string;
    value: string;
    status: 'good' | 'warn' | 'bad' | 'info';
  }

  interface Props {
    score: number;
    verdict?: string;
    diagnostics?: DiagnosticDetail[];
    expertMode?: boolean;
  }

  let {
    score,
    verdict,
    diagnostics = [],
    expertMode = false,
  }: Props = $props();

  // Score-to-tier mapping (INV-25 Manager mode)
  const tier = $derived.by(() => {
    if (score >= 90) return { label: $_('trustScore.tier.very_high'), color: 'success', tone: 'vivid' };
    if (score >= 75) return { label: $_('trustScore.tier.high'), color: 'success', tone: 'standard' };
    if (score >= 60) return { label: $_('trustScore.tier.medium'), color: 'warning', tone: 'standard' };
    if (score >= 40) return { label: $_('trustScore.tier.low'), color: 'warning', tone: 'standard' };
    return { label: $_('trustScore.tier.unconfirmed'), color: 'danger', tone: 'standard' };
  });

  const finalVerdict = $derived(verdict ?? tier.label);
  const scoreClamped = $derived(Math.min(100, Math.max(0, Math.round(score))));

  let expanded = $state(false);
  function toggleExpanded() {
    expanded = !expanded;
  }
</script>

<article class="trust-score" data-tier={tier.color}>
  <header class="trust-header">
    <div class="trust-label">{$_("trustScore.label")}</div>
    {#if expertMode}
      <button
        type="button"
        class="trust-expand-toggle"
        onclick={toggleExpanded}
        aria-expanded={expanded}
        aria-controls="trust-diagnostics"
      >
        {expanded ? $_("trustScore.collapse") : $_("trustScore.expand")}
      </button>
    {/if}
  </header>

  <div class="trust-body">
    <div class="trust-score-circle" data-tier={tier.color}>
      <span class="trust-score-number" aria-label={$_("trustScore.aria_score", { values: { score: scoreClamped } })}>
        {scoreClamped}
      </span>
    </div>
    <div class="trust-verdict-block">
      <div class="trust-verdict-label">{$_("trustScore.verdict_label")}</div>
      <div class="trust-verdict-value" data-tier={tier.color}>{finalVerdict}</div>
    </div>
  </div>

  {#if expertMode && expanded && diagnostics.length > 0}
    <section id="trust-diagnostics" class="trust-diagnostics" aria-label={$_("trustScore.diagnostics_label")}>
      <h4 class="trust-diagnostics-title">{$_("trustScore.diagnostics_title")}</h4>
      <dl class="trust-diagnostics-list">
        {#each diagnostics as d (d.label)}
          <div class="trust-diagnostic-row" data-status={d.status}>
            <dt>{d.label}</dt>
            <dd>{d.value}</dd>
          </div>
        {/each}
      </dl>
    </section>
  {/if}
</article>

<style>
  .trust-score {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-3);
    padding: var(--spacing-4);
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-lg);
    box-shadow: var(--shadow-sm);
  }

  .trust-score[data-tier='success'] {
    border-left: 4px solid var(--color-success);
  }
  .trust-score[data-tier='warning'] {
    border-left: 4px solid var(--color-warning);
  }
  .trust-score[data-tier='danger'] {
    border-left: 4px solid var(--color-danger);
  }

  .trust-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--spacing-3);
  }

  .trust-label {
    font-size: var(--typography-fontSize-ui-sm);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-secondary);
  }

  .trust-expand-toggle {
    background: transparent;
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-md);
    padding: var(--spacing-1) var(--spacing-2);
    font-size: var(--typography-fontSize-ui-xs);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--motion-fast) var(--easing-smooth);
  }
  .trust-expand-toggle:hover {
    border-color: var(--accent);
    color: var(--text-primary);
  }

  .trust-body {
    display: flex;
    align-items: center;
    gap: var(--spacing-4);
  }

  .trust-score-circle {
    flex-shrink: 0;
    width: 96px;
    height: 96px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg-elevated);
    border: 3px solid var(--border-subtle);
  }
  .trust-score-circle[data-tier='success'] {
    background: color-mix(in srgb, var(--color-success) 12%, var(--bg-elevated));
    border-color: var(--color-success);
  }
  .trust-score-circle[data-tier='warning'] {
    background: color-mix(in srgb, var(--color-warning) 12%, var(--bg-elevated));
    border-color: var(--color-warning);
  }
  .trust-score-circle[data-tier='danger'] {
    background: color-mix(in srgb, var(--color-danger) 12%, var(--bg-elevated));
    border-color: var(--color-danger);
  }

  .trust-score-number {
    font-size: 2.5rem;
    font-weight: 600;
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
  }

  .trust-verdict-block {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1);
  }

  .trust-verdict-label {
    font-size: var(--typography-fontSize-ui-xs);
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .trust-verdict-value {
    font-size: var(--typography-fontSize-ui-h2);
    font-weight: 500;
    color: var(--text-primary);
  }
  .trust-verdict-value[data-tier='success'] {
    color: var(--color-success);
  }
  .trust-verdict-value[data-tier='warning'] {
    color: var(--color-warning);
  }
  .trust-verdict-value[data-tier='danger'] {
    color: var(--color-danger);
  }

  .trust-diagnostics {
    border-top: 1px solid var(--border-subtle);
    padding-top: var(--spacing-3);
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
  }

  .trust-diagnostics-title {
    font-size: var(--typography-fontSize-ui-sm);
    font-weight: 500;
    color: var(--text-secondary);
    margin: 0;
  }

  .trust-diagnostics-list {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1);
    margin: 0;
  }

  .trust-diagnostic-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--spacing-2);
    padding: var(--spacing-1) var(--spacing-2);
    border-radius: var(--border-radius-sm);
    background: var(--bg-elevated);
  }

  .trust-diagnostic-row[data-status='good'] {
    border-left: 2px solid var(--color-success);
  }
  .trust-diagnostic-row[data-status='warn'] {
    border-left: 2px solid var(--color-warning);
  }
  .trust-diagnostic-row[data-status='bad'] {
    border-left: 2px solid var(--color-danger);
  }
  .trust-diagnostic-row[data-status='info'] {
    border-left: 2px solid var(--color-info);
  }

  .trust-diagnostic-row dt {
    font-size: var(--typography-fontSize-ui-sm);
    color: var(--text-secondary);
    margin: 0;
  }

  .trust-diagnostic-row dd {
    font-size: var(--typography-fontSize-ui-sm);
    color: var(--text-primary);
    margin: 0;
    font-variant-numeric: tabular-nums;
  }

  /* Reduced motion respect — INV-14 */
  @media (prefers-reduced-motion: reduce) {
    .trust-expand-toggle {
      transition: none;
    }
  }
</style>
