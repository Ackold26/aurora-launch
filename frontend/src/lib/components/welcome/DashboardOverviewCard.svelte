<!--
  DashboardOverviewCard — Sprint 1 UX Foundation, top-row workspace summary.

  Replaces 3-Card welcome with three metric tiles:
    - Total proxy brands (computed from listProjects)
    - Total analyses (sum project.version_count)
    - Next consulting deadline (placeholder — biller integration TODO)
-->

<script lang="ts">
  import { onMount } from 'svelte';
  import { _ } from 'svelte-i18n';
  import { listProjects, type ProjectSummary } from '$lib/ipc/projects';

  interface ConsultingDeadline {
    due_at: string;
    client_name: string;
  }

  interface DashboardStats {
    total_proxies: number;
    total_analyses: number;
    next_consulting_deadline: ConsultingDeadline | null;
  }

  interface Props {
    /** Optional pre-loaded stats (for SSR / tests). When undefined the component
     *  fetches via listProjects() onMount. */
    stats?: DashboardStats;
  }

  let { stats: statsProp }: Props = $props();

  let fetchedStats: DashboardStats | null = $state(null);
  let fetchLoading: boolean = $state(true);
  let error: string | null = $state(null);

  let stats = $derived<DashboardStats | null>(statsProp ?? fetchedStats);
  let loading = $derived<boolean>(statsProp === undefined && fetchLoading);

  onMount(async () => {
    if (statsProp !== undefined) {
      fetchLoading = false;
      return;
    }
    try {
      const projects = await listProjects();
      fetchedStats = computeStats(projects);
    } catch (e) {
      error = String(e);
    } finally {
      fetchLoading = false;
    }
  });

  function computeStats(projects: ProjectSummary[]): DashboardStats {
    return {
      total_proxies: projects.length,
      total_analyses: projects.reduce((sum, p) => sum + p.version_count, 0),
      next_consulting_deadline: null,
    };
  }

  function daysUntil(isoDate: string): number {
    // Compare calendar days, not exact ms difference — same date at 23:59
    // and same date at 00:01 must both report 0 days ("Today"), not 1.
    const target = new Date(isoDate);
    const now = new Date();
    const targetDay = new Date(
      target.getFullYear(),
      target.getMonth(),
      target.getDate(),
    ).getTime();
    const nowDay = new Date(
      now.getFullYear(),
      now.getMonth(),
      now.getDate(),
    ).getTime();
    return Math.round((targetDay - nowDay) / (1000 * 60 * 60 * 24));
  }

  type Urgency = 'none' | 'far' | 'soon' | 'overdue';

  function deadlineUrgency(deadline: ConsultingDeadline | null): Urgency {
    if (!deadline) return 'none';
    const d = daysUntil(deadline.due_at);
    if (d < 0) return 'overdue';
    if (d <= 3) return 'soon';
    return 'far';
  }

  function formatDeadline(deadline: ConsultingDeadline | null): string {
    if (!deadline) return $_('dashboard.overview.no_deadline');
    const d = daysUntil(deadline.due_at);
    if (d < 0) return $_('dashboard.overview.deadline_overdue');
    if (d === 0) return $_('dashboard.overview.deadline_today');
    if (d === 1) return $_('dashboard.overview.deadline_tomorrow');
    return $_('dashboard.overview.deadline_days', { values: { days: d } });
  }
</script>

<section
  class="dashboard-overview"
  aria-label={$_('dashboard.overview.aria_label')}
>
  <header class="overview-header">
    <h2 class="overview-title">{$_('dashboard.overview.title')}</h2>
    <p class="overview-subtitle">{$_('dashboard.overview.subtitle')}</p>
  </header>

  {#if loading}
    <div class="overview-tiles" aria-busy="true" aria-live="polite">
      <span class="skeleton-tile"></span>
      <span class="skeleton-tile"></span>
      <span class="skeleton-tile"></span>
    </div>
  {:else if error}
    <div class="overview-error" role="alert">
      <span class="error-icon" aria-hidden="true">⚠</span>
      <div class="error-body">
        <p class="error-title">{$_('dashboard.overview.load_error')}</p>
        <small class="error-detail">{error}</small>
      </div>
    </div>
  {:else if stats}
    <div class="overview-tiles">
      <article class="metric-tile">
        <span class="metric-label">{$_('dashboard.overview.proxies_label')}</span>
        <span class="metric-value">{stats.total_proxies}</span>
        <span class="metric-hint">{$_('dashboard.overview.proxies_hint')}</span>
      </article>

      <article class="metric-tile">
        <span class="metric-label">{$_('dashboard.overview.analyses_label')}</span>
        <span class="metric-value">{stats.total_analyses}</span>
        <span class="metric-hint">{$_('dashboard.overview.analyses_hint')}</span>
      </article>

      <article
        class="metric-tile metric-tile--text"
        class:urgency-soon={deadlineUrgency(stats.next_consulting_deadline) === 'soon'}
        class:urgency-overdue={deadlineUrgency(stats.next_consulting_deadline) === 'overdue'}
      >
        <span class="metric-label">{$_('dashboard.overview.deadline_label')}</span>
        <span class="metric-value metric-value--small">
          {formatDeadline(stats.next_consulting_deadline)}
        </span>
        {#if stats.next_consulting_deadline?.client_name}
          <span class="metric-hint">{stats.next_consulting_deadline.client_name}</span>
        {/if}
      </article>
    </div>
  {/if}
</section>

<style>
  .dashboard-overview {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-4);
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-lg);
    padding: var(--spacing-6);
    box-shadow: var(--shadow-sm);
  }

  .overview-header {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1);
  }

  .overview-title {
    margin: 0;
    font-family: var(--font-display);
    font-size: var(--typography-fontSize-ui-h2);
    font-weight: var(--typography-fontWeight-medium);
    color: var(--text-primary);
    line-height: var(--typography-lineHeight-snug);
  }

  .overview-subtitle {
    margin: 0;
    color: var(--text-secondary);
    font-size: var(--typography-fontSize-ui-sm);
    line-height: var(--typography-lineHeight-normal);
  }

  .overview-tiles {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: var(--spacing-4);
  }

  .metric-tile {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1);
    padding: var(--spacing-4);
    background: color-mix(in srgb, var(--bg-main) 70%, var(--bg-surface));
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-md);
    transition: border-color var(--motion-default) var(--easing-smooth);
  }

  .metric-tile:hover {
    border-color: color-mix(in srgb, var(--accent) 35%, var(--border-subtle));
  }

  .metric-tile.urgency-soon {
    border-left: 3px solid var(--color-warning);
  }

  .metric-tile.urgency-overdue {
    border-left: 3px solid var(--color-danger);
  }

  .metric-label {
    color: var(--text-muted);
    font-size: var(--typography-fontSize-ui-xs);
    font-weight: var(--typography-fontWeight-medium);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .metric-value {
    color: var(--text-primary);
    font-family: var(--font-display);
    font-size: var(--typography-fontSize-display-lg);
    font-weight: var(--typography-fontWeight-bold);
    line-height: var(--typography-lineHeight-tight);
    font-variant-numeric: tabular-nums;
  }

  .metric-value--small {
    font-size: var(--typography-fontSize-ui-h3);
    font-weight: var(--typography-fontWeight-medium);
  }

  .metric-hint {
    color: var(--text-muted);
    font-size: var(--typography-fontSize-ui-xs);
  }

  .skeleton-tile {
    display: block;
    height: 96px;
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

  .overview-error {
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

  @media (prefers-reduced-motion: reduce) {
    .metric-tile {
      transition: none;
    }
    .skeleton-tile {
      animation: none;
    }
  }
</style>
