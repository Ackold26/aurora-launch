<!--
  DataPreviewTable — Step 0 wizard UI for previewing wide-table data and
  assigning column roles (KPI / media / control / date / unused / unknown).

  Props:
    headers         — column names (readonly)
    rows            — first N rows of data (readonly, array-of-arrays)
    dtypes          — pandas dtype per column name
    roleAssignments — $bindable Map<colName, ColumnAssignment>

  On role select change: Map is reassigned (new Map) to trigger Svelte 5
  reactivity, auto_detected is set to false for user overrides.

  A11y: each select has aria-label from i18n key wizard.import.role.dropdown_aria.
  INV-14: no animations — pure static table.
-->

<script lang="ts">
  import { _ } from 'svelte-i18n';
  import type { ColumnAssignment, ColumnRole } from '$ipc/client';

  interface Props {
    headers: readonly string[];
    rows: ReadonlyArray<ReadonlyArray<string | number | null>>;
    dtypes: Readonly<Record<string, string>>;
    /** Bindable: current role assignments. Key = column name. */
    roleAssignments: Map<string, ColumnAssignment>;
    /** Total rows in file (from shape[0]), may differ from rows.length */
    totalRows?: number | undefined;
    /** File size in KB */
    sizeKb?: number | null | undefined;
  }

  let {
    headers,
    rows,
    dtypes,
    roleAssignments = $bindable(),
    totalRows = undefined,
    sizeKb = null,
  }: Props = $props();

  // Role color dot — maps role to a CSS color value.
  // Use design tokens where available, fallback to hex per design doc.
  const ROLE_COLORS: Record<ColumnRole | 'unknown', string> = {
    kpi:     '#22c55e',  // green — var(--color-success) is close but hex is explicit per spec
    media:   '#3b82f6',  // blue
    control: '#a855f7',  // purple
    date:    '#f59e0b',  // orange
    unused:  '#9ca3af',  // gray
    unknown: '#4b5563',  // dark gray
  };

  const ROLE_OPTIONS: ColumnRole[] = ['kpi', 'media', 'control', 'date', 'unused'];

  // Derived summary values
  const colCount = $derived(headers.length);
  const rowCount = $derived(totalRows ?? rows.length);
  const sizeDisplay = $derived(sizeKb != null ? Math.round(sizeKb * 10) / 10 : null);

  /** Handle role select change — reassign Map for Svelte 5 reactivity. */
  function handleRoleChange(name: string, newRole: string) {
    const current = roleAssignments.get(name);
    if (!current) return;
    const next = new Map(roleAssignments);
    next.set(name, {
      ...current,
      role: newRole as ColumnRole,
      auto_detected: false,
      confidence: 1.0,
    });
    roleAssignments = next;
  }
</script>

<div class="preview-wrapper">
  <!-- Summary header -->
  <p class="preview-summary" aria-live="polite">
    {$_('wizard.import.preview.summary', {
      values: {
        cols: colCount,
        rows: rowCount,
        sizeKb: sizeDisplay ?? '?',
      },
    })}
  </p>

  <!-- Scrollable table container — role="region" makes it interactive
       so tabindex="0" is valid (WCAG 2.1.1 scrollable-region-focusable). -->
  <div class="table-scroll" role="region" tabindex="0" aria-label={$_('wizard.import.preview.title')}>
    <table class="preview-table">
      <thead>
        <!-- Row 1: column names -->
        <tr class="header-name-row">
          {#each headers as name (name)}
            <th scope="col" class="col-header">
              <span class="col-name" title={name}>{name}</span>
              {#if dtypes[name]}
                <span class="col-dtype">{dtypes[name]}</span>
              {/if}
            </th>
          {/each}
        </tr>

        <!-- Row 2: role selects (sticky) -->
        <tr class="header-role-row">
          {#each headers as name (name)}
            {@const assignment = roleAssignments.get(name)}
            {@const role = assignment?.role ?? 'unknown'}
            {@const isAuto = (assignment?.auto_detected ?? false) && (assignment?.confidence ?? 1) < 0.9}
            <th scope="col" class="col-role">
              <div class="role-cell">
                <span
                  class="role-dot"
                  style="background-color: {ROLE_COLORS[role as ColumnRole | 'unknown'] ?? ROLE_COLORS.unknown}"
                  aria-hidden="true"
                ></span>
                <select
                  aria-label={$_('wizard.import.role.dropdown_aria', { values: { name } })}
                  value={role}
                  onchange={(e) => handleRoleChange(name, (e.currentTarget as HTMLSelectElement).value)}
                >
                  {#each ROLE_OPTIONS as opt (opt)}
                    <option value={opt}>{$_(`wizard.import.role.${opt}`)}</option>
                  {/each}
                  {#if role === 'unknown'}
                    <option value="unknown">{$_('wizard.import.role.unknown')}</option>
                  {/if}
                </select>
                {#if isAuto}
                  <span class="auto-badge" aria-label="определено автоматически">
                    {$_('wizard.import.role.auto_badge')}
                  </span>
                {/if}
              </div>
            </th>
          {/each}
        </tr>
      </thead>

      <!-- Data rows: up to 20 (whatever was sent) -->
      <tbody>
        {#each rows as row, rowIdx (rowIdx)}
          <tr>
            {#each headers as name, colIdx (name)}
              <td class="data-cell">{String(row[colIdx] ?? '')}</td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>

  <!-- Hint below table -->
  <p class="preview-hint">{$_('wizard.import.preview.hint')}</p>
</div>

<style>
  .preview-wrapper {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-3, 12px);
    margin-top: var(--spacing-4, 16px);
  }

  .preview-summary {
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    color: var(--text-secondary, #a8a8b8);
    margin: 0;
    font-weight: var(--typography-fontWeight-medium, 500);
  }

  /* Scrollable container — INV-14: no animation, just overflow */
  .table-scroll {
    overflow-x: auto;
    border: 1px solid var(--border-subtle, #2a2d37);
    border-radius: var(--radius-sm, 4px);
  }

  .table-scroll:focus {
    outline: 2px solid var(--accent, #2e5bff);
    outline-offset: 1px;
  }

  .preview-table {
    border-collapse: collapse;
    min-width: 100%;
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    background: var(--bg-surface, #1a1d27);
  }

  /* Column name header row */
  .header-name-row th {
    padding: 8px 12px 4px;
    text-align: left;
    background: var(--bg-surface, #1a1d27);
    color: var(--text-primary, #eaeaf0);
    font-weight: var(--typography-fontWeight-medium, 500);
    border-bottom: 1px solid var(--border-subtle, #2a2d37);
    white-space: nowrap;
    min-width: 120px;
    max-width: 220px;
  }

  .col-name {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .col-dtype {
    display: block;
    font-size: 0.75em;
    color: var(--text-muted, #7a7a90);
    font-family: var(--font-mono, monospace);
    margin-top: 2px;
  }

  /* Role row — visually grouped with name row */
  .header-role-row th {
    padding: 4px 12px 8px;
    background: var(--bg-surface, #1a1d27);
    border-bottom: 2px solid var(--border-subtle, #2a2d37);
    vertical-align: top;
  }

  .role-cell {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: nowrap;
  }

  .role-dot {
    flex-shrink: 0;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    display: inline-block;
  }

  select {
    flex: 1;
    min-width: 100px;
    padding: 4px 6px;
    border: 1px solid var(--border-subtle, #2a2d37);
    border-radius: var(--radius-sm, 4px);
    background: var(--bg-main, #13151f);
    color: var(--text-primary, #eaeaf0);
    font-size: inherit;
    font-family: inherit;
    cursor: pointer;
  }

  select:focus {
    outline: 2px solid var(--accent, #2e5bff);
    outline-offset: 1px;
  }

  .auto-badge {
    flex-shrink: 0;
    display: inline-block;
    padding: 1px 5px;
    border-radius: 10px;
    background: var(--color-warning-soft, color-mix(in srgb, #f59e0b 15%, transparent));
    color: var(--text-secondary, #a8a8b8);
    font-size: 0.7em;
    font-weight: 500;
    white-space: nowrap;
    line-height: 1.4;
  }

  /* Data rows */
  .data-cell {
    padding: 6px 12px;
    border-bottom: 1px solid var(--border-subtle, #2a2d37);
    color: var(--text-primary, #eaeaf0);
    white-space: nowrap;
    max-width: 220px;
    overflow: hidden;
    text-overflow: ellipsis;
    font-family: var(--font-mono, monospace);
    font-size: 0.85em;
  }

  /* Zebra stripes for readability */
  tbody tr:nth-child(even) {
    background: var(--bg-main, #13151f);
  }

  tbody tr:nth-child(odd) {
    background: var(--bg-surface, #1a1d27);
  }

  tbody tr:hover {
    background: var(--surface-soft, rgba(255, 255, 255, 0.04));
  }

  .preview-hint {
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    color: var(--text-muted, #7a7a90);
    margin: 0;
    font-style: italic;
  }
</style>
