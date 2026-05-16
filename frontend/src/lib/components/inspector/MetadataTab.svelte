<script lang="ts">
  import { _ } from 'svelte-i18n';
  import { manifestSummary } from '$lib/stores/bundle';
  import Card from '$lib/components/Card.svelte';
</script>

<div role="tabpanel" id="tab-metadata" hidden={false}>
  <Card title={$_('inspector.tab.metadata')}>
    {#snippet children()}
      <!-- M-08: tooltips на cryptographic / provenance metadata fields. -->
      <dl class="meta-grid">
        <dt>
          <abbr title="UUID v4 идентификатор проекта (генерируется при создании, неизменяемый, используется во всех версиях)">
            Project ID
          </abbr>
        </dt>
        <dd class="mono">{$manifestSummary?.project_id ?? '—'}</dd>
        <dt>
          <abbr title="Monotonic counter — растёт на 1 при каждом save. Защищает от optimistic-concurrency конфликтов при параллельных правках.">
            Revision
          </abbr>
        </dt>
        <dd class="mono">{$manifestSummary?.revision ?? '—'}</dd>
        <dt>
          <abbr title="Версия приложения Aurora Launch использованная при создании. Verify-tool сравнивает с локальной версией.">
            Aurora Launch version
          </abbr>
        </dt>
        <dd>{$manifestSummary?.aurora_app_version ?? '—'}</dd>
        <dt>Created</dt>
        <dd>{$manifestSummary?.created_at ?? '—'}</dd>
        <dt>Last modified</dt>
        <dd>{$manifestSummary?.last_modified ?? '—'}</dd>
        <dt>Files</dt>
        <dd>{Object.keys($manifestSummary?.files ?? {}).length}</dd>
        <dt>
          <abbr title="SHA-256 hash на каждый файл в bundle. Любая модификация => несовпадение hash => failed verification.">
            Integrity check
          </abbr>
        </dt>
        <dd>{$manifestSummary?.integrity_check ?? '—'}</dd>
        <dt>Compression</dt>
        <dd>{$manifestSummary?.compression ?? '—'}</dd>
      </dl>
    {/snippet}
  </Card>
</div>

<style>
  .meta-grid {
    display: grid;
    grid-template-columns: 200px 1fr;
    gap: var(--spacing-2) var(--spacing-4);
    margin: 0;
  }

  dt {
    color: var(--text-muted);
  }

  dd {
    margin: 0;
    color: var(--text-primary);
  }

  .mono {
    font-family: var(--font-mono);
    font-size: 0.9em;
  }
</style>
