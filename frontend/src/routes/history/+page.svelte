<!-- History — audit log + telemetry events + pending feedback (Block 2F). -->

<script lang="ts">
  import { onMount } from 'svelte';
  import { _ } from 'svelte-i18n';
  import { ipc } from '$ipc/client';
  import type { AuditEntry, FeedbackEntry, StoredTelemetryEvent } from '$ipc/client';
  import Card from '$lib/components/Card.svelte';
  import Skeleton from '$lib/components/Skeleton.svelte';
  import Badge from '$lib/components/Badge.svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import { goto } from '$app/navigation';

  let entries = $state<AuditEntry[]>([]);
  let telemetry = $state<StoredTelemetryEvent[]>([]);
  let pending = $state<FeedbackEntry[]>([]);
  let loading = $state(true);

  onMount(async () => {
    try {
      const [a, t, p] = await Promise.all([
        ipc.listAuditEntries({ limit: 100 }).catch(() => []),
        ipc.listEvents(50).catch(() => []),
        ipc.listPendingFeedback().catch(() => [])
      ]);
      entries = a;
      telemetry = t;
      pending = p;
    } finally {
      loading = false;
    }
  });

  function fmt(ts: string) {
    return new Date(ts).toLocaleString();
  }
</script>

<section class="history">
  <h1>{$_('nav.history')}</h1>

  <Card title="Audit log">
    {#snippet children()}
      {#if loading}
        <Skeleton width="100%" height="120px" rounded />
      {:else if entries.length === 0}
        <EmptyState
          icon="📂"
          title="Журнал пока пуст"
          body="История действий в приложении появится здесь — открытие проектов, сохранения, экспорт. Это хранится локально и никуда не отправляется."
          primaryAction={{ label: 'К списку проектов', onClick: () => goto('/') }}
        />
      {:else}
        <ol class="timeline">
          {#each entries as e (e.id)}
            <li>
              <time>{fmt(e.timestamp)}</time>
              <span class="op">{e.operation}</span>
              {#if e.target}<span class="target">{e.target}</span>{/if}
              <Badge
                size="sm"
                variant={e.outcome === 'success' ? 'success' : e.outcome === 'failure' ? 'danger' : 'default'}
              >
                {#snippet children()}{e.outcome}{/snippet}
              </Badge>
            </li>
          {/each}
        </ol>
      {/if}
    {/snippet}
  </Card>

  <Card title="Telemetry events (local-only buffer)">
    {#snippet children()}
      {#if loading}
        <Skeleton width="100%" height="80px" rounded />
      {:else if telemetry.length === 0}
        <EmptyState
          compact
          icon="📊"
          title="Метрик пока нет"
          body="Чтобы начать собирать — включите телеметрию в Настройках."
          primaryAction={{ label: 'Открыть Настройки', onClick: () => goto('/settings') }}
        />
      {:else}
        <ul class="events">
          {#each telemetry as ev (ev.id)}
            <li>
              <time>{fmt(ev.timestamp)}</time>
              <span class="event-type">{ev.event_type}</span>
              {#if ev.uploaded_at}
                <Badge size="sm" variant="success">
                  {#snippet children()}uploaded{/snippet}
                </Badge>
              {:else}
                <Badge size="sm" variant="default">
                  {#snippet children()}local{/snippet}
                </Badge>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
    {/snippet}
  </Card>

  {#if pending.length > 0}
    <Card title="Pending feedback (Cmd+Shift+F)" accent="info">
      {#snippet children()}
        <ul class="feedback-list">
          {#each pending as fb (fb.id)}
            <li>
              <time>{fmt(fb.timestamp)}</time>
              <p>{fb.text}</p>
            </li>
          {/each}
        </ul>
      {/snippet}
    </Card>
  {/if}
</section>

<style>
  .history {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-4);
    max-width: 960px;
    margin: 0 auto;
  }

  .timeline {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
  }

  .timeline li {
    display: flex;
    align-items: center;
    gap: var(--spacing-3);
    padding: var(--spacing-2) 0;
    border-bottom: 1px solid var(--border-subtle);
    font-size: var(--typography-fontSize-ui-sm);
  }

  time {
    color: var(--text-muted);
    font-family: var(--font-mono);
    font-size: var(--typography-fontSize-ui-xs);
    min-width: 160px;
  }

  .op {
    color: var(--text-primary);
    font-weight: 500;
  }

  .target {
    color: var(--text-secondary);
    font-family: var(--font-mono);
    font-size: 0.85em;
  }

  .events,
  .feedback-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
  }

  .events li {
    display: flex;
    gap: var(--spacing-3);
    align-items: center;
  }

  .event-type {
    font-family: var(--font-mono);
    color: var(--text-secondary);
  }

  .feedback-list li {
    border-left: 3px solid var(--color-info);
    padding-left: var(--spacing-3);
  }

  .feedback-list p {
    margin: var(--spacing-1) 0 0 0;
    color: var(--text-primary);
  }

  .muted {
    color: var(--text-muted);
  }
</style>
