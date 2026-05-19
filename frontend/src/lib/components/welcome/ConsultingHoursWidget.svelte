<!--
  ConsultingHoursWidget — Sprint 1 UX Foundation, premium gauge для часов
  консалтинга. Visualizes used vs total с urgency-driven coloring.

  Pure display — no IPC. Caller supplies used / total props (e.g. fetched
  from biller integration на parent level).

  Edge cases:
    - total === 0 → unlimited mode (∞, gradient shimmer)
    - used > total → fill capped at 100%, actual numbers shown
    - negative inputs → clamped to 0 (defensive)
-->

<script lang="ts">
  import { _ } from 'svelte-i18n';

  interface Props {
    used: number;
    total: number;
    /** Optional override for the gauge title. Defaults to localized "Часы консалтинга". */
    label?: string;
  }

  let { used, total, label }: Props = $props();

  type Urgency = 'success' | 'warning' | 'danger';

  let safeUsed = $derived(Math.max(0, used));
  let safeTotal = $derived(Math.max(0, total));
  let isUnlimited = $derived(safeTotal === 0);
  let percent = $derived(
    isUnlimited ? 0 : Math.min(100, (safeUsed / safeTotal) * 100)
  );
  let urgency = $derived<Urgency>(
    isUnlimited
      ? 'success'
      : percent >= 90
        ? 'danger'
        : percent >= 70
          ? 'warning'
          : 'success'
  );
  let remaining = $derived(Math.max(0, safeTotal - safeUsed));
  let titleLabel = $derived(label ?? $_('dashboard.hours.title'));
</script>

<section
  class="consulting-hours"
  role="meter"
  aria-valuenow={safeUsed}
  aria-valuemin="0"
  aria-valuemax={isUnlimited ? safeUsed : safeTotal}
  aria-label={$_('dashboard.hours.used_total_aria', {
    values: { used: safeUsed, total: isUnlimited ? '∞' : safeTotal }
  })}
>
  <header class="hours-header">
    <h3 class="hours-title">{titleLabel}</h3>
    {#if !isUnlimited}
      <span class="hours-percent hours-percent--{urgency}" aria-hidden="true">
        {Math.round(percent)}%
      </span>
    {/if}
  </header>

  <div class="hours-numeric" aria-hidden="true">
    <span class="hours-used hours-used--{urgency}">{safeUsed}</span>
    <span class="hours-divider">/</span>
    <span class="hours-total">{isUnlimited ? '∞' : safeTotal}</span>
  </div>

  <div class="hours-track" aria-hidden="true">
    <div
      class="hours-fill hours-fill--{urgency}"
      class:hours-fill--unlimited={isUnlimited}
      style:width="{isUnlimited ? 100 : percent}%"
    ></div>
  </div>

  <footer class="hours-footer">
    {#if isUnlimited}
      <span class="hours-status hours-status--success">
        {$_('dashboard.hours.unlimited')}
      </span>
    {:else}
      <span class="hours-status hours-status--{urgency}">
        {$_('dashboard.hours.remaining', { values: { hours: remaining } })}
      </span>
    {/if}
  </footer>
</section>

<style>
  .consulting-hours {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-3);
    padding: var(--spacing-4);
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-lg);
    box-shadow: var(--shadow-sm);
  }

  .hours-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: var(--spacing-2);
  }

  .hours-title {
    margin: 0;
    font-family: var(--font-display);
    font-size: var(--typography-fontSize-ui-h3);
    font-weight: var(--typography-fontWeight-medium);
    color: var(--text-primary);
    line-height: var(--typography-lineHeight-snug);
  }

  .hours-percent {
    font-family: var(--font-mono);
    font-size: var(--typography-fontSize-ui-sm);
    font-weight: var(--typography-fontWeight-medium);
    font-variant-numeric: tabular-nums;
  }

  .hours-percent--success { color: var(--color-success); }
  .hours-percent--warning { color: var(--color-warning); }
  .hours-percent--danger  { color: var(--color-danger);  }

  .hours-numeric {
    display: flex;
    align-items: baseline;
    gap: var(--spacing-1);
    font-family: var(--font-display);
    line-height: var(--typography-lineHeight-tight);
    font-variant-numeric: tabular-nums;
  }

  .hours-used {
    font-size: var(--typography-fontSize-display-lg);
    font-weight: var(--typography-fontWeight-bold);
  }

  .hours-used--success { color: var(--color-success); }
  .hours-used--warning { color: var(--color-warning); }
  .hours-used--danger  { color: var(--color-danger);  }

  .hours-divider {
    color: var(--text-muted);
    font-size: var(--typography-fontSize-ui-h2);
    font-weight: var(--typography-fontWeight-light);
  }

  .hours-total {
    color: var(--text-secondary);
    font-size: var(--typography-fontSize-ui-h2);
    font-weight: var(--typography-fontWeight-medium);
  }

  .hours-track {
    height: 8px;
    background: var(--border-subtle);
    border-radius: var(--border-radius-sm);
    overflow: hidden;
    position: relative;
  }

  .hours-fill {
    height: 100%;
    border-radius: inherit;
    transition:
      width var(--motion-default) var(--easing-smooth),
      background-color var(--motion-default) var(--easing-smooth);
  }

  .hours-fill--success { background: var(--color-success); }
  .hours-fill--warning { background: var(--color-warning); }
  .hours-fill--danger  { background: var(--color-danger);  }

  .hours-fill--unlimited {
    background: linear-gradient(
      90deg,
      var(--color-success) 0%,
      var(--accent) 50%,
      var(--color-success) 100%
    );
    background-size: 200% 100%;
    animation: unlimited-shimmer 3s var(--easing-smooth) infinite;
  }

  @keyframes unlimited-shimmer {
    0%   { background-position: 0 0; }
    100% { background-position: 200% 0; }
  }

  .hours-footer {
    display: flex;
    justify-content: flex-end;
  }

  .hours-status {
    font-size: var(--typography-fontSize-ui-xs);
    color: var(--text-muted);
  }

  .hours-status--success { color: var(--color-success); }
  .hours-status--warning { color: var(--color-warning); }
  .hours-status--danger  { color: var(--color-danger);  }

  @media (prefers-reduced-motion: reduce) {
    .hours-fill,
    .hours-fill--unlimited {
      transition: none;
      animation: none;
    }
  }
</style>
