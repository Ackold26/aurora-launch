<!--
  ColumnMappingTable — Step 1 wizard UI for mapping XLSX/CSV source columns
  to Aurora canonical fields (BTA-6).

  Props:
    sourceColumns   — readonly list of source column names from the file
    suggestedMapping — sidecar adapter hints (priority over heuristic)
    previewRows     — first rows of data for value preview
    mapping         — $bindable Map<source, canonical | null>

  On mount (when mapping is empty) auto-fills via autoMapColumns heuristic.
  Parent mutates mapping via bind:mapping={...}.

  A11y: each select has aria-label «Сопоставить колонку <source>».
  INV-14: no animations (pure table).
-->

<script lang="ts">
  import {
    autoMapColumns,
    groupedCanonicalFields,
    CANONICAL_FIELDS,
  } from '$lib/utils/auto_map_columns';

  interface Props {
    sourceColumns: readonly string[];
    /** Sidecar suggested mapping от adapter — приоритет над heuristic */
    suggestedMapping?: Record<string, string>;
    /** Preview rows из sidecar (для verifyование значений) */
    previewRows?: Array<Record<string, unknown>>;
    /** Bindable: текущий mapping. Parent sets initial → child mutates. */
    mapping: Map<string, string | null>;
  }

  let {
    sourceColumns,
    suggestedMapping = {},
    previewRows = [],
    mapping = $bindable(),
  }: Props = $props();

  // Grouped options for <optgroup> rendering — computed once.
  const grouped = groupedCanonicalFields();

  // Group display labels in Russian.
  const GROUP_LABELS: Record<string, string> = {
    identity: 'Идентификация',
    period:   'Период',
    sales:    'Продажи',
    media:    'Медиа',
    category: 'Категория',
  };

  // Auto-fill mapping at mount if empty.
  $effect(() => {
    if (mapping.size === 0 && sourceColumns.length > 0) {
      mapping = autoMapColumns(sourceColumns, suggestedMapping);
    }
  });

  // Count of mapped (non-null) columns.
  let mappedCount = $derived(
    [...mapping.values()].filter((v) => v !== null).length,
  );

  // Preview value for a source column from first preview row.
  function previewValue(src: string): string {
    const firstRow = previewRows[0];
    if (!firstRow) return '';
    const val = firstRow[src];
    if (val === undefined || val === null) return '';
    return String(val);
  }

  // Handle select change — must reassign Map to trigger Svelte 5 reactivity.
  function handleChange(src: string, newValue: string) {
    const next = new Map(mapping);
    next.set(src, newValue === '' ? null : newValue);
    mapping = next;
  }
</script>

<div class="mapping-wrapper">
  <table class="mapping-table" aria-label="Сопоставление колонок файла с полями Aurora">
    <thead>
      <tr>
        <th scope="col">Колонка в файле</th>
        <th scope="col">Aurora-поле</th>
      </tr>
    </thead>
    <tbody>
      {#each sourceColumns as src (src)}
        {@const currentVal = mapping.get(src) ?? null}
        <tr class={currentVal !== null ? 'row-mapped' : 'row-unmapped'}>
          <td class="cell-source">
            <span class="source-name">{src}</span>
            {#if previewValue(src)}
              <small class="preview">{previewValue(src)}</small>
            {/if}
          </td>
          <td class="cell-select">
            <select
              aria-label={`Сопоставить колонку ${src}`}
              value={currentVal ?? ''}
              onchange={(e) => handleChange(src, (e.currentTarget as HTMLSelectElement).value)}
            >
              <option value="">— не сопоставлено —</option>
              {#each Object.keys(grouped) as group (group)}
                {@const groupFields = grouped[group] ?? []}
                {#if groupFields.length > 0}
                  <optgroup label={GROUP_LABELS[group] ?? group}>
                    {#each groupFields as field (field.id)}
                      <option value={field.id}>{field.label_ru}</option>
                    {/each}
                  </optgroup>
                {/if}
              {/each}
            </select>
          </td>
        </tr>
      {/each}
    </tbody>
  </table>

  <p class="mapping-counter" aria-live="polite">
    Сопоставлено <strong>{mappedCount}</strong> из <strong>{sourceColumns.length}</strong> колонок
  </p>
</div>

<style>
  .mapping-wrapper {
    width: 100%;
  }

  .mapping-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--typography-fontSize-ui-body, 1rem);
  }

  .mapping-table th,
  .mapping-table td {
    padding: 12px;
    border-bottom: 1px solid var(--border-subtle, var(--color-ui-bg-border, #2a2d37));
    text-align: left;
  }

  .mapping-table th {
    font-weight: var(--typography-fontWeight-medium, 500);
    color: var(--text-secondary, var(--color-ui-text-secondary, #A8A8B8));
    background: var(--bg-surface, var(--color-ui-bg-surface, #1a1d27));
  }

  .cell-source {
    vertical-align: top;
  }

  .source-name {
    display: block;
    color: var(--text-primary, var(--color-ui-text-primary, #EAEAF0));
    font-weight: var(--typography-fontWeight-medium, 500);
  }

  .preview {
    display: block;
    font-size: 0.85em;
    color: var(--text-muted, var(--color-ui-text-muted, #7A7A90));
    margin-top: 4px;
  }

  .cell-select {
    width: 55%;
  }

  select {
    width: 100%;
    padding: 8px;
    border: 1px solid var(--border-subtle, var(--color-ui-bg-border, #2a2d37));
    border-radius: var(--border-radius-sm, 2px);
    background: var(--bg-surface, var(--color-ui-bg-surface, #1a1d27));
    color: var(--text-primary, var(--color-ui-text-primary, #EAEAF0));
    font-size: inherit;
    font-family: inherit;
    cursor: pointer;
  }

  select:focus {
    outline: 2px solid var(--accent, var(--color-ui-accent-primary, #2E5BFF));
    outline-offset: 1px;
  }

  /* Mapped row — subtle green background */
  .row-mapped {
    background: var(--color-success-soft, color-mix(in srgb, var(--color-success, var(--color-semantic-success, #10B981)) 12%, transparent));
  }

  /* Unmapped row — subtle warning background */
  .row-unmapped {
    background: var(--color-warning-soft, color-mix(in srgb, var(--color-warning, var(--color-semantic-warning, #F59E0B)) 10%, transparent));
  }

  .mapping-counter {
    margin-top: 12px;
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    color: var(--text-secondary, var(--color-ui-text-secondary, #A8A8B8));
  }
</style>
