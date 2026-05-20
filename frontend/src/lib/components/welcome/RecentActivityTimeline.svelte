<!--
  RecentActivityTimeline — Sprint 1 UX Foundation, recent activity feed.

  Pulls last 8 audit entries via ipc.listAuditEntries (newest-first by id DESC).
  Reused from the audit log infrastructure to surface user-visible workflow
  activity (project create / save / forecast / signature verification etc.).

  States: loading skeletons → entries OR empty CTA → error retry.
-->

<script lang="ts">
  import { onMount } from 'svelte';
  import { _ } from 'svelte-i18n';
  import { goto } from '$app/navigation';
  import { ipc, type AuditEntry } from '$lib/ipc/client';

  interface Props {
    /** Optional pre-loaded entries (for tests / SSR). When undefined the
     *  component fetches via ipc.listAuditEntries({ limit }) onMount. */
    entries?: AuditEntry[];
    /** Max entries to show. Defaults to 8. */
    limit?: number;
  }

  let { entries: entriesProp, limit = 8 }: Props = $props();

  let fetchedEntries: AuditEntry[] | null = $state(null);
  let fetchLoading: boolean = $state(true);
  let error: string | null = $state(null);

  // Combined source — prop wins (DashboardOverviewCard pattern).
  let entries = $derived<AuditEntry[] | null>(entriesProp ?? fetchedEntries);
  let loading = $derived<boolean>(entriesProp === undefined && fetchLoading);

  // Visible slice — apply limit to whichever source is active.
  let visibleEntries = $derived<AuditEntry[]>(
    (entries ?? []).slice(0, limit),
  );

  async function fetchEntries(): Promise<void> {
    fetchLoading = true;
    error = null;
    try {
      const result = await ipc.listAuditEntries({ limit });
      fetchedEntries = result;
    } catch (e) {
      error = String(e);
    } finally {
      fetchLoading = false;
    }
  }

  onMount(() => {
    if (entriesProp !== undefined) {
      fetchLoading = false;
      return;
    }
    void fetchEntries();
  });

  // ── Time formatting ────────────────────────────────────────────────────────

  function formatRelativeTime(timestamp: string): string {
    const ts = new Date(timestamp).getTime();
    if (Number.isNaN(ts)) return timestamp;
    const deltaSec = (Date.now() - ts) / 1000;

    if (deltaSec < 60) return $_('dashboard.activity.just_now');
    if (deltaSec < 3600) {
      return $_('dashboard.activity.minutes_ago', {
        values: { count: Math.floor(deltaSec / 60) },
      });
    }
    if (deltaSec < 86400) {
      return $_('dashboard.activity.hours_ago', {
        values: { count: Math.floor(deltaSec / 3600) },
      });
    }
    if (deltaSec < 604800) {
      return $_('dashboard.activity.days_ago', {
        values: { count: Math.floor(deltaSec / 86400) },
      });
    }
    return new Date(timestamp).toLocaleDateString();
  }

  // ── Operation label mapping ───────────────────────────────────────────────

  const KNOWN_OPS = new Set([
    'create_project',
    'save_bundle',
    'import_bundle',
    'verify_bundle_signature',
    'start_forecast',
    'cancel_forecast',
    'delete_project',
  ]);

  function formatOperation(op: string): string {
    if (KNOWN_OPS.has(op)) {
      return $_(`dashboard.activity.operation.${op}`);
    }
    return $_('dashboard.activity.operation.unknown');
  }

  // ── Outcome → CSS class ───────────────────────────────────────────────────

  type OutcomeKind = 'success' | 'warning' | 'error' | 'neutral';

  function outcomeKind(outcome: string): OutcomeKind {
    const o = outcome.toLowerCase();
    if (o === 'success') return 'success';
    if (o === 'warning' || o === 'partial') return 'warning';
    if (o === 'error' || o === 'failed') return 'error';
    return 'neutral';
  }

  function handleRetry(): void {
    void fetchEntries();
  }

  function handleEmptyCta(): void {
    void goto('/wizard');
  }
</script>

<section
  class="activity-timeline"
  aria-label={$_('dashboard.activity.aria_label')}
>
  <header class="activity-header">
    <h2 class="activity-title">{$_('dashboard.activity.title')}</h2>
    <p class="activity-subtitle">{$_('dashboard.activity.subtitle')}</p>
  </header>

  {#if loading}
    <ul class="activity-list" aria-busy="true" aria-live="polite">
      <li class="skeleton-row"></li>
      <li class="skeleton-row"></li>
      <li class="skeleton-row"></li>
      <li class="skeleton-row"></li>
    </ul>
  {:else if error}
    <div class="activity-error" role="alert">
      <span class="error-icon" aria-hidden="true">⚠</span>
      <div class="error-body">
        <p class="error-title">{$_('dashboard.activity.load_error')}</p>
        <small class="error-detail">{error}</small>
        <button
          type="button"
          class="retry-btn"
          onclick={handleRetry}
        >
          {$_('dashboard.activity.retry')}
        </button>
      </div>
    </div>
  {:else if visibleEntries.length === 0}
    <div class="activity-empty">
      <p class="empty-title">{$_('dashboard.activity.empty_title')}</p>
      <p class="empty-body">{$_('dashboard.activity.empty_body')}</p>
      <button
        type="button"
        class="empty-cta"
        onclick={handleEmptyCta}
      >
        {$_('dashboard.activity.empty_cta')}
      </button>
    </div>
  {:else}
    <ul class="activity-list">
      {#each visibleEntries as entry (entry.id)}
        <li class="activity-item">
          <span
            class="activity-dot activity-dot--{outcomeKind(entry.outcome)}"
            aria-hidden="true"
          ></span>
          <div class="activity-content">
            <div class="activity-row activity-row--top">
              <span class="activity-op">{formatOperation(entry.operation)}</span>
              <time class="activity-time" datetime={entry.timestamp}>
                {formatRelativeTime(entry.timestamp)}
              </time>
            </div>
            {#if entry.target}
              <span class="activity-target">{entry.target}</span>
            {/if}
          </div>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .activity-timeline {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-4);
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-lg);
    padding: var(--spacing-6);
    box-shadow: var(--shadow-sm);
  }

  .activity-header {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1);
  }

  .activity-title {
    margin: 0;
    font-family: var(--font-display);
    font-size: var(--typography-fontSize-ui-h2);
    font-weight: var(--typography-fontWeight-medium);
    color: var(--text-primary);
    line-height: var(--typography-lineHeight-snug);
  }

  .activity-subtitle {
    margin: 0;
    color: var(--text-secondary);
    font-size: var(--typography-fontSize-ui-sm);
    line-height: var(--typography-lineHeight-normal);
  }

  .activity-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
  }

  .activity-item {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: var(--spacing-3);
    align-items: flex-start;
    padding: var(--spacing-3) var(--spacing-4);
    background: color-mix(in srgb, var(--bg-main) 70%, var(--bg-surface));
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-md);
    transition: border-color var(--motion-default) var(--easing-smooth);
  }

  .activity-item:hover {
    border-color: color-mix(in srgb, var(--accent) 35%, var(--border-subtle));
  }

  .activity-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-top: 6px;
    flex-shrink: 0;
    background: var(--text-muted);
  }

  .activity-dot--success { background: var(--color-success); }
  .activity-dot--warning { background: var(--color-warning); }
  .activity-dot--error { background: var(--color-danger); }
  .activity-dot--neutral { background: var(--text-muted); }

  .activity-content {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1);
    min-width: 0;
  }

  .activity-row {
    display: flex;
    flex-wrap: wrap;
    gap: var(--spacing-2);
  }

  .activity-row--top {
    justify-content: space-between;
    align-items: baseline;
  }

  .activity-op {
    color: var(--text-primary);
    font-size: var(--typography-fontSize-ui-body);
    font-weight: var(--typography-fontWeight-medium);
  }

  .activity-time {
    color: var(--text-muted);
    font-size: var(--typography-fontSize-ui-xs);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  .activity-target {
    color: var(--text-secondary);
    font-size: var(--typography-fontSize-ui-sm);
    font-family: var(--font-mono);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* ── Skeleton loading ──────────────────────────────────────────────────── */

  .skeleton-row {
    list-style: none;
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

  /* ── Error state ───────────────────────────────────────────────────────── */

  .activity-error {
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
    gap: var(--spacing-2);
    flex: 1;
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

  .retry-btn {
    align-self: flex-start;
    background: transparent;
    border: 1px solid var(--color-danger);
    border-radius: var(--border-radius-md);
    color: var(--color-danger);
    cursor: pointer;
    font-family: var(--font-sans);
    font-size: var(--typography-fontSize-ui-sm);
    padding: var(--spacing-1) var(--spacing-3);
    transition:
      background-color var(--motion-default) var(--easing-smooth),
      color var(--motion-default) var(--easing-smooth);
  }

  .retry-btn:hover {
    background: var(--color-danger);
    color: var(--bg-surface);
  }

  .retry-btn:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  /* ── Empty state ───────────────────────────────────────────────────────── */

  .activity-empty {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
    align-items: flex-start;
    padding: var(--spacing-6);
    background: color-mix(in srgb, var(--bg-main) 70%, var(--bg-surface));
    border: 1px dashed var(--border-subtle);
    border-radius: var(--border-radius-md);
  }

  .empty-title {
    margin: 0;
    color: var(--text-primary);
    font-family: var(--font-display);
    font-size: var(--typography-fontSize-ui-h3);
    font-weight: var(--typography-fontWeight-medium);
  }

  .empty-body {
    margin: 0;
    color: var(--text-secondary);
    font-size: var(--typography-fontSize-ui-sm);
  }

  .empty-cta {
    margin-top: var(--spacing-2);
    background: var(--accent);
    border: 1px solid var(--accent);
    border-radius: var(--border-radius-md);
    color: var(--bg-surface);
    cursor: pointer;
    font-family: var(--font-sans);
    font-size: var(--typography-fontSize-ui-sm);
    font-weight: var(--typography-fontWeight-medium);
    padding: var(--spacing-2) var(--spacing-4);
    transition: opacity var(--motion-default) var(--easing-smooth);
  }

  .empty-cta:hover { opacity: 0.85; }

  .empty-cta:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  /* ── Reduced motion ────────────────────────────────────────────────────── */

  @media (prefers-reduced-motion: reduce) {
    .activity-item,
    .retry-btn,
    .empty-cta {
      transition: none;
    }
    .skeleton-row {
      animation: none;
    }
  }
</style>
