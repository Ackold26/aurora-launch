<script lang="ts">
  import { Hst } from '@histoire/plugin-svelte';
  import RecentActivityTimeline from './RecentActivityTimeline.svelte';
  import type { AuditEntry } from '$lib/ipc/client';

  const now = Date.now();
  const minutes = (n: number) => new Date(now - n * 60 * 1000).toISOString();
  const hours = (n: number) => new Date(now - n * 3600 * 1000).toISOString();
  const days = (n: number) => new Date(now - n * 86400 * 1000).toISOString();

  const empty: AuditEntry[] = [];

  const populated: AuditEntry[] = [
    {
      id: 7,
      timestamp: minutes(2),
      actor: 'user',
      operation: 'verify_bundle_signature',
      target: 'kagotsel_venarus.aurora',
      outcome: 'success',
      details: {},
    },
    {
      id: 6,
      timestamp: minutes(15),
      actor: 'user',
      operation: 'save_bundle',
      target: 'FMCG Beverage Q2',
      outcome: 'success',
      details: {},
    },
    {
      id: 5,
      timestamp: hours(3),
      actor: 'user',
      operation: 'start_forecast',
      target: 'FMCG Beverage Q2 — Forecast #4',
      outcome: 'success',
      details: {},
    },
    {
      id: 4,
      timestamp: hours(8),
      actor: 'user',
      operation: 'cancel_forecast',
      target: null,
      outcome: 'warning',
      details: {},
    },
    {
      id: 3,
      timestamp: days(2),
      actor: 'user',
      operation: 'import_bundle',
      target: 'Pharma OTC Launch.aurora',
      outcome: 'error',
      details: { reason: 'signature_invalid' },
    },
    {
      id: 2,
      timestamp: days(5),
      actor: 'user',
      operation: 'create_project',
      target: 'Snack Category Pilot',
      outcome: 'success',
      details: {},
    },
  ];
</script>

<Hst.Story title="welcome/RecentActivityTimeline" group="flows">
  <Hst.Variant title="Empty — no activity yet">
    <RecentActivityTimeline entries={empty} />
  </Hst.Variant>

  <Hst.Variant title="Populated — mixed outcomes">
    <RecentActivityTimeline entries={populated} />
  </Hst.Variant>

  <Hst.Variant title="Limit 3 — most recent only">
    <RecentActivityTimeline entries={populated} limit={3} />
  </Hst.Variant>
</Hst.Story>
