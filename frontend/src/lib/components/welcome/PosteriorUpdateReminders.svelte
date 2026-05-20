<!--
  PosteriorUpdateReminders — Sprint 1 UX Foundation, posterior staleness reminders.

  Pulls projects где actuals data старше threshold_weeks via Tauri command
  `list_pending_posterior_updates` (wraps Sprint 0 sidecar method
  `list_projects_with_new_actuals`).

  Note: backend is Sprint 0 stub (always [] until schema migration adds
  `last_actuals_update_at` column). Component gracefully renders empty
  state as "all forecasts up to date".

  Each reminder: project name + weeks_since_update + open CTA. Urgency
  border-left coloring (fresh < 4w, stale 4-7w, critical >= 8w).
-->

<script lang="ts">
  import { onMount } from 'svelte';
  import { _ } from 'svelte-i18n';
  import { ipc, type PendingPosteriorUpdateItem } from '$lib/ipc/client';

  interface Props {
    /** Optional pre-loaded items (для tests / SSR). */
    items?: PendingPosteriorUpdateItem[];
    /** Threshold weeks для consider stale. Defaults to 4. */
    thresholdWeeks?: number;
  }

  let { items: itemsProp, thresholdWeeks = 4 }: Props = $props();

  let fetchedItems: PendingPosteriorUpdateItem[] = $state([]);
  let fetchLoading: boolean = $state(true);
  let error: string | null = $state(null);

  let items = $derived<PendingPosteriorUpdateItem[]>(itemsProp ?? fetchedItems);
  let loading = $derived<boolean>(itemsProp === undefined && fetchLoading);

  onMount(async () => {
    if (itemsProp !== undefined) {
      fetchLoading = false;
      return;
    }
    try {
      fetchedItems = await ipc.listPendingPosteriorUpdates(thresholdWeeks);
    } catch (e) {
      error = String(e);
    } finally {
      fetchLoading = false;
    }
  });

  type Urgency = 'fresh' | 'stale' | 'critical';

  function urgency(weeksSinceUpdate: number): Urgency {
    if (weeksSinceUpdate >= 8) return 'critical';
    if (weeksSinceUpdate >= 4) return 'stale';
    return 'fresh';
  }
</script>

<section
  class="posterior-reminders"
  aria-label={$_('dashboard.posterior.aria_label')}
>
  <header class="reminders-header">
    <h2 class="reminders-title">{$_('dashboard.posterior.title')}</h2>
    <p class="reminders-subtitle">{$_('dashboard.posterior.subtitle')}</p>
  </header>

  {#if loading}
    <ul class="reminders-list" aria-busy="true" aria-live="polite">
      <li class="skeleton-row"></li>
      <li class="skeleton-row"></li>
    </ul>
  {:else if error}
    <div class="reminders-error" role="alert">
      <span class="error-icon" aria-hidden="true">⚠</span>
      <div class="error-body">
        <p class="error-title">{$_('dashboard.posterior.load_error')}</p>
        <small class="error-detail">{error}</small>
      </div>
    </div>
  {:else if items.length === 0}
    <div class="reminders-empty">
      <span class="empty-icon" aria-hidden="true">✓</span>
      <div class="empty-body">
        <p class="empty-title">{$_('dashboard.posterior.empty_title')}</p>
        <p class="empty-detail">{$_('dashboard.posterior.empty_body')}</p>
      </div>
    </div>
  {:else}
    <ul class="reminders-list">
      {#each items as item (item.project_uuid)}
        {@const urg = urgency(item.weeks_since_update)}
        <li class="reminder reminder--{urg}">
          <div class="reminder-info">
            <p class="reminder-name">{item.name}</p>
            <p class="reminder-age">
              {#if item.last_actuals_update_at}
                {$_('dashboard.posterior.weeks_since', {
                  values: { weeks: item.weeks_since_update }
                })}
              {:else}
                {$_('dashboard.posterior.never_updated')}
              {/if}
            </p>
          </div>
          <a
            class="reminder-cta"
            href="/inspector?project={item.project_uuid}"
            aria-label={$_('dashboard.posterior.open_aria', {
              values: { name: item.name }
            })}
          >
            {$_('dashboard.posterior.open_button')}
          </a>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .posterior-reminders {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-4);
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-lg);
    padding: var(--spacing-6);
    box-shadow: var(--shadow-sm);
  }

  .reminders-header {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1);
  }

  .reminders-title {
    margin: 0;
    font-family: var(--font-display);
    font-size: var(--typography-fontSize-ui-h2);
    font-weight: var(--typography-fontWeight-medium);
    color: var(--text-primary);
    line-height: var(--typography-lineHeight-snug);
  }

  .reminders-subtitle {
    margin: 0;
    color: var(--text-secondary);
    font-size: var(--typography-fontSize-ui-sm);
    line-height: var(--typography-lineHeight-normal);
  }

  .reminders-list {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
    list-style: none;
    padding: 0;
    margin: 0;
  }

  .reminder {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--spacing-4);
    padding: var(--spacing-3) var(--spacing-4);
    background: color-mix(in srgb, var(--bg-main) 70%, var(--bg-surface));
    border: 1px solid var(--border-subtle);
    border-left-width: 3px;
    border-radius: var(--border-radius-md);
    transition: border-color var(--motion-default) var(--easing-smooth);
  }

  .reminder--fresh    { border-left-color: var(--color-info); }
  .reminder--stale    { border-left-color: var(--color-warning); }
  .reminder--critical { border-left-color: var(--color-danger); }

  .reminder:hover {
    border-color: color-mix(in srgb, var(--accent) 35%, var(--border-subtle));
  }

  .reminder-info {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1);
    min-width: 0;
    flex: 1;
  }

  .reminder-name {
    margin: 0;
    color: var(--text-primary);
    font-size: var(--typography-fontSize-ui-body);
    font-weight: var(--typography-fontWeight-medium);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .reminder-age {
    margin: 0;
    color: var(--text-muted);
    font-size: var(--typography-fontSize-ui-xs);
  }

  .reminder-cta {
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: var(--spacing-2) var(--spacing-4);
    background: transparent;
    color: var(--accent);
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-md);
    font-family: var(--font-sans);
    font-size: var(--typography-fontSize-ui-sm);
    font-weight: var(--typography-fontWeight-medium);
    text-decoration: none;
    transition:
      border-color var(--motion-default) var(--easing-smooth),
      background var(--motion-default) var(--easing-smooth);
  }

  .reminder-cta:hover {
    border-color: var(--accent);
    background: color-mix(in srgb, var(--accent) 8%, transparent);
  }

  .reminder-cta:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .skeleton-row {
    display: block;
    height: 56px;
    background: linear-gradient(
      90deg,
      var(--border-subtle) 0%,
      color-mix(in srgb, var(--border-subtle) 50%, var(--bg-surface)) 50%,
      var(--border-subtle) 100%
    );
    background-size: 200% 100%;
    border-radius: var(--border-radius-md);
    animation: skeleton-shimmer 1.4s var(--easing-smooth) infinite;
  }

  @keyframes skeleton-shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  .reminders-error {
    display: flex;
    gap: var(--spacing-3);
    align-items: flex-start;
    padding: var(--spacing-4);
    background: color-mix(in srgb, var(--color-danger) 8%, var(--bg-surface));
    border: 1px solid color-mix(in srgb, var(--color-danger) 30%, transparent);
    border-radius: var(--border-radius-md);
  }

  .error-icon {
    color: var(--color-danger);
    font-size: var(--typography-fontSize-ui-h3);
    line-height: 1;
  }

  .error-body {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1);
  }

  .error-title {
    margin: 0;
    color: var(--text-primary);
    font-size: var(--typography-fontSize-ui-body);
    font-weight: var(--typography-fontWeight-medium);
  }

  .error-detail {
    color: var(--text-muted);
    font-size: var(--typography-fontSize-ui-xs);
  }

  .reminders-empty {
    display: flex;
    gap: var(--spacing-3);
    align-items: flex-start;
    padding: var(--spacing-4);
    background: color-mix(in srgb, var(--color-success) 6%, var(--bg-surface));
    border: 1px solid color-mix(in srgb, var(--color-success) 25%, transparent);
    border-radius: var(--border-radius-md);
  }

  .empty-icon {
    color: var(--color-success);
    font-size: var(--typography-fontSize-ui-h3);
    line-height: 1;
  }

  .empty-title {
    margin: 0;
    color: var(--text-primary);
    font-size: var(--typography-fontSize-ui-body);
    font-weight: var(--typography-fontWeight-medium);
  }

  .empty-detail {
    margin: var(--spacing-1) 0 0 0;
    color: var(--text-secondary);
    font-size: var(--typography-fontSize-ui-sm);
    line-height: var(--typography-lineHeight-normal);
  }

  @media (prefers-reduced-motion: reduce) {
    .reminder {
      transition: none;
    }
    .reminder-cta {
      transition: none;
    }
    .skeleton-row {
      animation: none;
    }
  }
</style>
