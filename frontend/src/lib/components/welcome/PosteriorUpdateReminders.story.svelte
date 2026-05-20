<script lang="ts">
  import { Hst } from '@histoire/plugin-svelte';
  import PosteriorUpdateReminders from './PosteriorUpdateReminders.svelte';
  import type { PendingPosteriorUpdateItem } from '$lib/ipc/client';

  const empty: PendingPosteriorUpdateItem[] = [];

  const mixedUrgency: PendingPosteriorUpdateItem[] = [
    {
      project_uuid: 'fresh',
      name: 'FMCG Beverage Q2',
      last_actuals_update_at: '2026-05-05T10:00:00Z',
      weeks_since_update: 2,
    },
    {
      project_uuid: 'stale',
      name: 'Pharma OTC Launch',
      last_actuals_update_at: '2026-04-01T10:00:00Z',
      weeks_since_update: 6,
    },
    {
      project_uuid: 'critical',
      name: 'Snack Category Pilot',
      last_actuals_update_at: '2026-02-15T10:00:00Z',
      weeks_since_update: 12,
    },
  ];

  const neverUpdated: PendingPosteriorUpdateItem[] = [
    {
      project_uuid: 'new',
      name: 'New project (no actuals)',
      last_actuals_update_at: null,
      weeks_since_update: 999,
    },
  ];
</script>

<Hst.Story title="welcome/PosteriorUpdateReminders" group="flows">
  <Hst.Variant title="Empty — all forecasts up to date">
    <PosteriorUpdateReminders items={empty} />
  </Hst.Variant>

  <Hst.Variant title="Mixed urgency (fresh + stale + critical)">
    <PosteriorUpdateReminders items={mixedUrgency} />
  </Hst.Variant>

  <Hst.Variant title="Never-updated project">
    <PosteriorUpdateReminders items={neverUpdated} />
  </Hst.Variant>
</Hst.Story>
