<!--
  DailyInsightBanner — Phase Magic M-07 in-app daily insight surfacing.

  Mounts on home page; shows top-priority insight from daily-insights
  service if applicable AND not already shown today. Dismissable
  (locks suppression key 'aurora.last-insight-shown' к today's date).

  Per INV-14: prefers-reduced-motion respected (no slide-in animation).
-->

<script lang="ts">
  import { onMount, untrack } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    type DailyInsight,
    computeDailyInsight,
    shouldShowInsight,
    markInsightShown,
  } from '$lib/services/daily-insights';
  import { projectsStore } from '$lib/stores/projects.svelte';
  import { fadeIn } from '$lib/services/motion';

  interface Props {
    /** Override insight for testing (skips store + suppress checks). */
    forceInsight?: DailyInsight | null;
  }

  let { forceInsight }: Props = $props();

  // forceInsight — test escape hatch (NEVER set in production). Initial capture намерен.
  let insight = $state<DailyInsight | null>(untrack(() => forceInsight ?? null));
  let visible = $state<boolean>(untrack(() => forceInsight !== undefined));

  onMount(async () => {
    // forceInsight uses test-only path, skip side effects
    if (forceInsight !== undefined) return;

    if (!shouldShowInsight()) {
      visible = false;
      return;
    }

    // Ensure projects loaded
    if (projectsStore.projects.length === 0 && !projectsStore.loading) {
      // 1.5 fix: store.refresh() catches errors internally + tracks
      // error_occurred telemetry. Здесь логируем в DevTools — если refresh
      // упал, баннер просто не показывается, customer не знает почему;
      // pilot-диагностика теперь имеет след в console.
      await projectsStore.refresh();
      if (projectsStore.error) {
        console.warn(
          '[M-07 DailyInsight] projects.refresh failed, banner suppressed:',
          projectsStore.error,
        );
      }
    }

    const candidate = computeDailyInsight(projectsStore.projects);
    if (candidate) {
      insight = candidate;
      visible = true;
    }
  });

  function dismiss(): void {
    markInsightShown();
    visible = false;
  }

  function handleCta(): void {
    if (!insight?.ctaHref) return;
    markInsightShown();
    if (insight.ctaHref.startsWith('http')) {
      // External link — open в browser
      if (typeof window !== 'undefined') {
        window.open(insight.ctaHref, '_blank', 'noopener,noreferrer');
      }
    } else {
      goto(insight.ctaHref);
    }
    visible = false;
  }
</script>

{#if visible && insight}
  <aside
    class="daily-insight"
    class:severity-info={insight.severity === 'info'}
    class:severity-warning={insight.severity === 'warning'}
    class:severity-success={insight.severity === 'success'}
    role="status"
    aria-live="polite"
    in:fadeIn={{ duration: 220 }}
  >
    <div class="insight-icon" aria-hidden="true">
      {#if insight.severity === 'warning'}
        ⚠️
      {:else if insight.severity === 'success'}
        ✨
      {:else}
        💡
      {/if}
    </div>
    <div class="insight-body">
      <strong class="insight-title">{insight.title}</strong>
      <p class="insight-text">{insight.body}</p>
    </div>
    <div class="insight-actions">
      {#if insight.cta && insight.ctaHref}
        <button type="button" class="insight-cta" onclick={handleCta}>
          {insight.cta}
        </button>
      {/if}
      <button
        type="button"
        class="insight-dismiss"
        onclick={dismiss}
        aria-label="Скрыть на сегодня"
      >
        ×
      </button>
    </div>
  </aside>
{/if}

<style>
  .daily-insight {
    display: flex;
    align-items: flex-start;
    gap: var(--spacing-3, 0.75rem);
    padding: var(--spacing-3, 0.75rem) var(--spacing-4, 1rem);
    margin: 0 0 var(--spacing-4, 1rem) 0;
    border-radius: 8px;
    background: var(--bg-surface-elevated, #f9fafb);
    border-left: 4px solid var(--accent, #2563eb);
  }

  .severity-warning {
    border-left-color: var(--color-warning, #d97706);
    background: var(--bg-warning-subtle, #fef3c7);
  }

  .severity-success {
    border-left-color: var(--color-success, #059669);
    background: var(--bg-success-subtle, #ecfdf5);
  }

  .severity-info {
    border-left-color: var(--accent, #2563eb);
  }

  .insight-icon {
    flex-shrink: 0;
    font-size: 1.5rem;
    line-height: 1;
    padding-top: 2px;
  }

  .insight-body {
    flex: 1;
    min-width: 0;
  }

  .insight-title {
    display: block;
    font-weight: 600;
    color: var(--text-primary, #111827);
    margin-bottom: var(--spacing-1, 0.25rem);
  }

  .insight-text {
    margin: 0;
    color: var(--text-secondary, #374151);
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    line-height: 1.5;
  }

  .insight-actions {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: var(--spacing-2, 0.5rem);
  }

  .insight-cta {
    background: var(--accent, #2563eb);
    color: var(--text-on-accent, white);
    border: none;
    border-radius: 6px;
    padding: var(--spacing-1, 0.25rem) var(--spacing-3, 0.75rem);
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    cursor: pointer;
    font-family: inherit;
  }

  .insight-cta:hover {
    background: var(--accent-hover, #1d4ed8);
  }

  .insight-dismiss {
    background: transparent;
    border: none;
    color: var(--text-muted, #6b7280);
    cursor: pointer;
    font-size: 1.5rem;
    line-height: 1;
    padding: 0 var(--spacing-1, 0.25rem);
  }

  .insight-dismiss:hover {
    color: var(--text-primary, #111827);
  }

  @media (prefers-reduced-motion: reduce) {
    .insight-cta {
      transition: none;
    }
  }
</style>
