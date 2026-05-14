<!--
  ForecastHistory — Linear timeline of project versions (Phase Premium P-02).

  Uses R-03 IPC: getProject (fetches full version list) + compareVersions
  (split-pane diff when 2 selected).

  Per INV-25 dual-mode UX:
    Manager mode (default): revision number, time-ago timestamp, label, decision note
    Expert mode (opt-in):   + composite_bundle_hash short fingerprint + file_count

  Compare flow:
    1. Click checkbox on a version row → adds к selection (max 2)
    2. Second selection enables "Сравнить" button
    3. Click "Сравнить" → fetches compare_versions → renders diff below timeline
    4. Click "Очистить выделение" → resets

  ARIA: <ol> for sequential history, role="listbox" with aria-multiselectable
        on the compare-mode set, aria-pressed on selection toggles.

  Reduced motion (INV-14): no animations on row enter — relies on existing
  Card hover transition which already respects prefers-reduced-motion.
-->

<script lang="ts">
  import { onMount } from 'svelte';
  import { SvelteSet } from 'svelte/reactivity';
  import {
    getProject,
    compareVersions,
    type ProjectDetail,
    type VersionSummary,
    type VersionDiff,
  } from '$ipc/projects';
  import ForecastHistorySkeleton from '$lib/components/skeletons/ForecastHistorySkeleton.svelte';
  import { formatTimeAgo } from '$lib/utils/time';

  interface Props {
    projectUuid: string;
    expertMode?: boolean;
    /** Optional preloaded detail — skips initial fetch (useful for tests / SSR). */
    initialDetail?: ProjectDetail;
  }

  let { projectUuid, expertMode = false, initialDetail }: Props = $props();

  let detail = $state<ProjectDetail | null>(initialDetail ?? null);
  let loading = $state(!initialDetail);
  let error = $state<string | null>(null);

  // Selection state — Set of version_id (max 2 entries).
  // SvelteSet for reactivity: regular Set mutations (.add/.delete) don't
  // trigger Svelte 5 reactivity; SvelteSet wraps Set with $state internally.
  const selected = new SvelteSet<number>();
  let selectionCount = $derived(selected.size);
  let canCompare = $derived(selectionCount === 2);

  let diff = $state<VersionDiff | null>(null);
  let compareError = $state<string | null>(null);
  let comparing = $state(false);

  // Sort versions descending by created_at (newest first) для timeline display
  const sortedVersions = $derived.by(() => {
    if (!detail) return [] as VersionSummary[];
    return [...detail.versions].sort((a, b) => {
      // Compare ISO strings lexicographically — works для well-formed timestamps
      if (a.created_at < b.created_at) return 1;
      if (a.created_at > b.created_at) return -1;
      return 0;
    });
  });

  onMount(async () => {
    if (initialDetail) return;
    try {
      detail = await getProject(projectUuid);
      error = null;
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  });

  function toggleSelection(versionId: number): void {
    if (selected.has(versionId)) {
      selected.delete(versionId);
    } else {
      if (selected.size >= 2) {
        // Replace oldest selection (simple FIFO for max-2 behaviour)
        const oldest = selected.values().next().value;
        if (oldest !== undefined) selected.delete(oldest);
      }
      selected.add(versionId);
    }
    // Clear stale diff on any selection change
    diff = null;
    compareError = null;
  }

  function clearSelection(): void {
    selected.clear();
    diff = null;
    compareError = null;
  }

  async function runCompare(): Promise<void> {
    if (selected.size !== 2) return;
    const [a, b] = Array.from(selected);
    if (a === undefined || b === undefined) return;
    comparing = true;
    compareError = null;
    diff = null;
    try {
      // Order by version_id ASC so diff semantic = "what changed from a → b"
      const [low, high] = a < b ? [a, b] : [b, a];
      diff = await compareVersions(low, high);
    } catch (e) {
      compareError = e instanceof Error ? e.message : String(e);
    } finally {
      comparing = false;
    }
  }

  function timeAgo(iso: string): string {
    return formatTimeAgo(iso, 'ru');
  }

  function shortHash(hash: string | null): string {
    if (!hash) return '—';
    return hash.length > 12 ? `${hash.slice(0, 8)}…${hash.slice(-4)}` : hash;
  }
</script>

<section class="forecast-history" aria-label="История прогнозов">
  <header class="history-header">
    <h2>История версий</h2>
    {#if !loading && detail && sortedVersions.length > 0}
      <div class="selection-bar" role="status" aria-live="polite">
        {#if selectionCount === 0}
          <span class="hint">Выделите 2 версии для сравнения</span>
        {:else if selectionCount === 1}
          <span class="hint">Выделена 1 — выберите вторую</span>
        {:else}
          <button
            type="button"
            class="btn btn-primary"
            onclick={runCompare}
            disabled={comparing || !canCompare}
          >
            {comparing ? 'Сравнение…' : 'Сравнить'}
          </button>
          <button
            type="button"
            class="btn btn-ghost"
            onclick={clearSelection}
            disabled={comparing}
          >
            Очистить
          </button>
        {/if}
      </div>
    {/if}
  </header>

  {#if loading}
    <ForecastHistorySkeleton />
  {:else if error}
    <p class="error-state" role="alert">Не удалось загрузить историю: {error}</p>
  {:else if sortedVersions.length === 0}
    <p class="empty-state">У проекта пока нет сохранённых версий.</p>
  {:else}
    <ol class="timeline" role="listbox" aria-multiselectable="true">
      {#each sortedVersions as v (v.version_id)}
        {@const isSelected = selected.has(v.version_id)}
        <li
          class="timeline-row"
          class:selected={isSelected}
          role="option"
          aria-selected={isSelected}
        >
          <button
            type="button"
            class="select-toggle"
            aria-pressed={isSelected}
            aria-label={`Версия ${v.revision} — ${isSelected ? 'снять выделение' : 'выделить'}`}
            onclick={() => toggleSelection(v.version_id)}
          >
            <span class="checkbox-glyph" aria-hidden="true">{isSelected ? '✓' : ' '}</span>
          </button>

          <div class="version-meta">
            <div class="version-head">
              <span class="revision">v{v.revision}</span>
              {#if v.label}
                <span class="label">{v.label}</span>
              {/if}
              <time class="when" datetime={v.created_at}>{timeAgo(v.created_at)}</time>
            </div>
            {#if v.decision_note}
              <p class="note">{v.decision_note}</p>
            {/if}
            {#if expertMode}
              <dl class="expert-details">
                <dt>Hash:</dt>
                <dd class="mono">{shortHash(v.composite_bundle_hash)}</dd>
                <dt>Файлов:</dt>
                <dd>{v.file_count}</dd>
                <dt>ID:</dt>
                <dd class="mono">{v.version_id}</dd>
              </dl>
            {/if}
          </div>
        </li>
      {/each}
    </ol>
  {/if}

  {#if compareError}
    <p class="error-state" role="alert">Ошибка сравнения: {compareError}</p>
  {/if}

  {#if diff}
    <section class="diff-pane" aria-label="Различия между версиями">
      <h3>Различия</h3>
      <div class="diff-summary">
        {#if diff.files_changed.length === 0 && diff.files_only_in_a.length === 0 && diff.files_only_in_b.length === 0}
          <p class="identical">Версии идентичны — содержимое не отличается.</p>
        {:else}
          <div class="diff-grid">
            <div class="diff-column" data-kind="changed">
              <h4>Изменены ({diff.files_changed.length})</h4>
              {#if diff.files_changed.length > 0}
                <ul>
                  {#each diff.files_changed as f}<li class="mono">{f}</li>{/each}
                </ul>
              {:else}
                <p class="muted">—</p>
              {/if}
            </div>
            <div class="diff-column" data-kind="only-a">
              <h4>Только в ранней ({diff.files_only_in_a.length})</h4>
              {#if diff.files_only_in_a.length > 0}
                <ul>
                  {#each diff.files_only_in_a as f}<li class="mono">{f}</li>{/each}
                </ul>
              {:else}
                <p class="muted">—</p>
              {/if}
            </div>
            <div class="diff-column" data-kind="only-b">
              <h4>Только в поздней ({diff.files_only_in_b.length})</h4>
              {#if diff.files_only_in_b.length > 0}
                <ul>
                  {#each diff.files_only_in_b as f}<li class="mono">{f}</li>{/each}
                </ul>
              {:else}
                <p class="muted">—</p>
              {/if}
            </div>
          </div>
          {#if expertMode}
            <p class="diff-unchanged-count">Без изменений: {diff.files_unchanged.length} файл(ов)</p>
          {/if}
        {/if}
      </div>
    </section>
  {/if}
</section>

<style>
  .forecast-history {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-4, 1rem);
  }

  .history-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--spacing-3, 0.75rem);
  }

  h2 {
    margin: 0;
    font-family: var(--font-display, var(--font-sans, sans-serif));
    font-size: var(--typography-fontSize-display-sm, 1.5rem);
    font-weight: 600;
  }

  .selection-bar {
    display: flex;
    align-items: center;
    gap: var(--spacing-2, 0.5rem);
  }

  .hint {
    color: var(--text-muted, #888);
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
  }

  .btn {
    padding: 0.5rem 1rem;
    border-radius: 6px;
    border: 1px solid transparent;
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    cursor: pointer;
    transition: background-color 120ms ease, border-color 120ms ease;
  }

  .btn-primary {
    background: var(--color-primary, #2563eb);
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    background: var(--color-primary-hover, #1d4ed8);
  }

  .btn-ghost {
    background: transparent;
    border-color: var(--border-default, #d1d5db);
    color: var(--text-primary, #111827);
  }

  .btn-ghost:hover:not(:disabled) {
    background: var(--surface-hover, #f9fafb);
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .timeline {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2, 0.5rem);
  }

  .timeline-row {
    display: flex;
    align-items: flex-start;
    gap: var(--spacing-3, 0.75rem);
    padding: var(--spacing-3, 0.75rem);
    border: 1px solid var(--border-subtle, #e5e7eb);
    border-radius: 8px;
    background: var(--surface-base, white);
    transition: border-color 120ms ease, background-color 120ms ease;
  }

  .timeline-row.selected {
    border-color: var(--color-primary, #2563eb);
    background: var(--surface-selected, #eff6ff);
  }

  .select-toggle {
    background: none;
    border: 1px solid var(--border-default, #d1d5db);
    border-radius: 4px;
    width: 22px;
    height: 22px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: var(--text-primary, #111827);
    flex-shrink: 0;
  }

  .select-toggle[aria-pressed='true'] {
    background: var(--color-primary, #2563eb);
    border-color: var(--color-primary, #2563eb);
    color: white;
  }

  .checkbox-glyph {
    line-height: 1;
    font-size: 0.95rem;
  }

  .version-meta {
    flex: 1;
    min-width: 0;
  }

  .version-head {
    display: flex;
    flex-wrap: wrap;
    gap: var(--spacing-2, 0.5rem);
    align-items: baseline;
  }

  .revision {
    font-family: var(--font-mono, monospace);
    font-weight: 600;
    color: var(--text-primary, #111827);
  }

  .label {
    color: var(--text-primary, #111827);
    font-weight: 500;
  }

  .when {
    color: var(--text-muted, #6b7280);
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
  }

  .note {
    margin: var(--spacing-1, 0.25rem) 0 0 0;
    color: var(--text-secondary, #374151);
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
  }

  .expert-details {
    display: grid;
    grid-template-columns: auto 1fr;
    column-gap: var(--spacing-2, 0.5rem);
    row-gap: 2px;
    margin: var(--spacing-2, 0.5rem) 0 0 0;
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
  }

  .expert-details dt {
    color: var(--text-muted, #6b7280);
  }

  .expert-details dd {
    margin: 0;
    color: var(--text-secondary, #374151);
  }

  .mono {
    font-family: var(--font-mono, monospace);
  }

  .empty-state,
  .error-state {
    color: var(--text-muted, #6b7280);
    padding: var(--spacing-4, 1rem);
    text-align: center;
  }

  .error-state {
    color: var(--color-danger, #dc2626);
  }

  .diff-pane {
    border-top: 2px solid var(--border-subtle, #e5e7eb);
    padding-top: var(--spacing-4, 1rem);
  }

  .diff-pane h3 {
    margin: 0 0 var(--spacing-3, 0.75rem) 0;
    font-family: var(--font-display, var(--font-sans, sans-serif));
    font-size: var(--typography-fontSize-display-xs, 1.125rem);
  }

  .identical {
    color: var(--text-muted, #6b7280);
    font-style: italic;
  }

  .diff-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: var(--spacing-3, 0.75rem);
  }

  .diff-column {
    background: var(--surface-base, white);
    border: 1px solid var(--border-subtle, #e5e7eb);
    border-radius: 6px;
    padding: var(--spacing-3, 0.75rem);
  }

  .diff-column h4 {
    margin: 0 0 var(--spacing-2, 0.5rem) 0;
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    font-weight: 600;
  }

  .diff-column[data-kind='changed'] h4 {
    color: var(--color-warning, #d97706);
  }

  .diff-column[data-kind='only-a'] h4 {
    color: var(--color-danger, #dc2626);
  }

  .diff-column[data-kind='only-b'] h4 {
    color: var(--color-success, #059669);
  }

  .diff-column ul {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-height: 200px;
    overflow-y: auto;
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
  }

  .muted {
    color: var(--text-muted, #9ca3af);
    margin: 0;
  }

  .diff-unchanged-count {
    margin: var(--spacing-3, 0.75rem) 0 0 0;
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
    color: var(--text-muted, #6b7280);
  }
</style>
