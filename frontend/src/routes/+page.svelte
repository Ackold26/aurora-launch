<!--
  Welcome / Workspace entry — Sprint 1 UX Foundation smart routing.

  Conditional shell:
    - loading → DashboardOverviewCard skeleton stub (component owns own state)
    - empty (no projects) → <EmptyDashboard /> first-run UX
    - populated → Workspace composition (Dashboard + Hours + Reminders +
      Activity + QuickActions)

  Replaces Sprint 0 3-Card welcome pattern. Import-from-disk flow now lives
  inside /wizard import step (Sprint Buffer #12 — reconsider placement).
-->

<script lang="ts">
  import { onMount } from 'svelte';
  import { listProjects, type ProjectSummary } from '$lib/ipc/projects';

  import DashboardOverviewCard from '$lib/components/welcome/DashboardOverviewCard.svelte';
  import ConsultingHoursWidget from '$lib/components/welcome/ConsultingHoursWidget.svelte';
  import PosteriorUpdateReminders from '$lib/components/welcome/PosteriorUpdateReminders.svelte';
  import RecentActivityTimeline from '$lib/components/welcome/RecentActivityTimeline.svelte';
  import QuickActionRibbon from '$lib/components/welcome/QuickActionRibbon.svelte';
  import EmptyDashboard from '$lib/components/welcome/EmptyDashboard.svelte';
  import DailyInsightBanner from '$lib/components/DailyInsightBanner.svelte';

  let projects = $state<ProjectSummary[] | null>(null);
  let loading = $state<boolean>(true);

  let isEmpty = $derived(projects !== null && projects.length === 0);
  let isPopulated = $derived(projects !== null && projects.length > 0);

  let overviewStats = $derived(
    projects === null
      ? undefined
      : {
          total_proxies: projects.length,
          total_analyses: projects.reduce(
            (sum: number, p: ProjectSummary) => sum + p.version_count,
            0,
          ),
          // Sprint Buffer: integrate biller next consulting deadline endpoint
          next_consulting_deadline: null,
        }
  );

  onMount(async () => {
    try {
      projects = await listProjects();
    } catch (e) {
      console.warn('listProjects failed, falling back to empty workspace', e);
      projects = [];
    } finally {
      loading = false;
    }
  });

  // Mock until biller integration ships (Sprint Buffer item).
  // total=0 → unlimited gauge (matches current launch tier).
  const MOCK_CONSULTING = { used: 0, total: 0 };
</script>

{#if loading}
  <section class="page-shell" aria-busy="true" aria-live="polite">
    <DashboardOverviewCard />
  </section>
{:else if isEmpty}
  <EmptyDashboard />
{:else if isPopulated && overviewStats}
  <section class="page-shell">
    <DailyInsightBanner />

    <DashboardOverviewCard stats={overviewStats} />

    <div class="workspace-grid">
      <ConsultingHoursWidget used={MOCK_CONSULTING.used} total={MOCK_CONSULTING.total} />
      <PosteriorUpdateReminders />
    </div>

    <RecentActivityTimeline />

    <QuickActionRibbon />
  </section>
{/if}

<style>
  .page-shell {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-6);
    max-width: var(--sizing-ui-containerMax);
    margin: 0 auto;
    padding: var(--spacing-4) 0 var(--spacing-8) 0;
  }

  .workspace-grid {
    display: grid;
    grid-template-columns: minmax(260px, 1fr) 2fr;
    gap: var(--spacing-4);
  }

  @media (max-width: 900px) {
    .workspace-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
