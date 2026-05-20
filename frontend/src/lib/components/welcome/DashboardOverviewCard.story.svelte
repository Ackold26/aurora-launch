<script>
  import { Hst } from '@histoire/plugin-svelte';
  import DashboardOverviewCard from './DashboardOverviewCard.svelte';

  // Hist stories pass `stats` prop to bypass IPC fetch (Histoire runs без Tauri).
  const populated = {
    total_proxies: 4,
    total_analyses: 17,
    next_consulting_deadline: null,
  };

  const upcomingDeadline = {
    total_proxies: 2,
    total_analyses: 6,
    next_consulting_deadline: {
      due_at: new Date(Date.now() + 2 * 86400 * 1000).toISOString(),
      client_name: 'Acme FMCG',
    },
  };

  const overdueDeadline = {
    total_proxies: 1,
    total_analyses: 3,
    next_consulting_deadline: {
      due_at: new Date(Date.now() - 86400 * 1000).toISOString(),
      client_name: 'Globex Pharma',
    },
  };
</script>

<Hst.Story title="welcome/DashboardOverviewCard" group="flows">
  <Hst.Variant title="Populated — empty deadline">
    <DashboardOverviewCard stats={populated} />
  </Hst.Variant>

  <Hst.Variant title="Upcoming consulting deadline (soon)">
    <DashboardOverviewCard stats={upcomingDeadline} />
  </Hst.Variant>

  <Hst.Variant title="Overdue consulting deadline">
    <DashboardOverviewCard stats={overdueDeadline} />
  </Hst.Variant>

  <Hst.Variant title="Zero projects (newly cleared)">
    <DashboardOverviewCard
      stats={{ total_proxies: 0, total_analyses: 0, next_consulting_deadline: null }}
    />
  </Hst.Variant>
</Hst.Story>
