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
  import { _ } from 'svelte-i18n';
  import {
    getProject,
    compareVersions,
    compareForecastVersions,
    type ProjectDetail,
    type VersionSummary,
    type VersionDiff,
    type ForecastDiff,
  } from '$ipc/projects';
  import ForecastHistorySkeleton from '$lib/components/skeletons/ForecastHistorySkeleton.svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import { formatTimeAgo } from '$lib/utils/time';
  import { goto } from '$app/navigation';

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
  let forecastDiff = $state<ForecastDiff | null>(null);
  let compareError = $state<string | null>(null);
  let comparing = $state(false);

  // M-05 Anticipation UX: hover-triggered preload cache.
  // Key format: "min-max" (always lower version_id first). Value: cached
  // Promise — awaited when user actually clicks Compare → instant result
  // because IPC already finished during hover.
  type CachedPair = {
    file: Promise<VersionDiff>;
    semantic: Promise<ForecastDiff | null>;
  };
  const _diffCache = new Map<string, CachedPair>();

  function _cacheKey(a: number, b: number): string {
    return a < b ? `${a}-${b}` : `${b}-${a}`;
  }

  function _kickOffPreload(a: number, b: number): void {
    if (a === b) return;
    const key = _cacheKey(a, b);
    if (_diffCache.has(key)) return; // already preloaded
    const [low, high] = a < b ? [a, b] : [b, a];
    _diffCache.set(key, {
      file: compareVersions(low, high),
      // .catch keeps promise resolved even if semantic IPC fails
      semantic: compareForecastVersions(low, high).catch(() => null),
    });
  }

  function handleRowMouseEnter(versionId: number): void {
    // Only preload pairing когда exactly 1 version selected and hovered != selected
    if (selected.size !== 1) return;
    const firstSelected = selected.values().next().value;
    if (firstSelected === undefined || firstSelected === versionId) return;
    _kickOffPreload(firstSelected, versionId);
  }

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
    forecastDiff = null;
    compareError = null;
    _diffCache.clear();  // M-05: invalidate preload cache
  }

  async function runCompare(): Promise<void> {
    if (selected.size !== 2) return;
    const [a, b] = Array.from(selected);
    if (a === undefined || b === undefined) return;
    comparing = true;
    compareError = null;
    diff = null;
    forecastDiff = null;
    try {
      // Order by version_id ASC so diff semantic = "what changed from a → b"
      const [low, high] = a < b ? [a, b] : [b, a];
      // M-05: try cache first (populated by hover preload)
      const key = _cacheKey(low, high);
      const cached = _diffCache.get(key);
      let fileDiffPromise: Promise<VersionDiff>;
      let semanticDiffPromise: Promise<ForecastDiff | null>;
      if (cached) {
        // Hover preload already kicked these off — await cached promises
        fileDiffPromise = cached.file;
        semanticDiffPromise = cached.semantic;
      } else {
        // No preload (user clicked very fast OR hovered different rows)
        fileDiffPromise = compareVersions(low, high);
        semanticDiffPromise = compareForecastVersions(low, high).catch(() => null);
      }
      const [fileDiff, semanticDiff] = await Promise.all([
        fileDiffPromise,
        semanticDiffPromise,
      ]);
      diff = fileDiff;
      forecastDiff = semanticDiff;
    } catch (e) {
      compareError = e instanceof Error ? e.message : String(e);
    } finally {
      comparing = false;
    }
  }

  function formatPct(v: number | undefined): string {
    if (v === undefined || !Number.isFinite(v)) return '—';
    const sign = v > 0 ? '+' : '';
    return `${sign}${v.toFixed(1)}%`;
  }

  function formatCompact(v: number | undefined): string {
    if (v === undefined || !Number.isFinite(v)) return '—';
    const abs = Math.abs(v);
    if (abs >= 1_000_000) return `${(v / 1_000_000).toFixed(1).replace(/\.0$/, '')} млн`;
    if (abs >= 1_000) return `${(v / 1_000).toFixed(0)} тыс`;
    return v.toFixed(0);
  }

  function timeAgo(iso: string): string {
    return formatTimeAgo(iso, 'ru');
  }

  function shortHash(hash: string | null): string {
    if (!hash) return '—';
    return hash.length > 12 ? `${hash.slice(0, 8)}…${hash.slice(-4)}` : hash;
  }
</script>

<section class="forecast-history" aria-label={$_("forecastHistory.section_label")}>
  <header class="history-header">
    <h2>{$_("history.title")}</h2>
    {#if !loading && detail && sortedVersions.length > 0}
      <div class="selection-bar" role="status" aria-live="polite">
        {#if selectionCount === 0}
          <span class="hint">{$_("history.select_hint_0")}</span>
        {:else if selectionCount === 1}
          <span class="hint">{$_("history.select_hint_1")}</span>
        {:else}
          <button
            type="button"
            class="btn btn-primary"
            onclick={runCompare}
            disabled={comparing || !canCompare}
          >
            {comparing ? $_("history.comparing") : $_("history.compare_btn")}
          </button>
          <button
            type="button"
            class="btn btn-ghost"
            onclick={clearSelection}
            disabled={comparing}
          >
            {$_("history.clear_selection")}
          </button>
        {/if}
      </div>
    {/if}
  </header>

  {#if loading}
    <ForecastHistorySkeleton />
  {:else if error}
    <p class="error-state" role="alert">{$_("history.load_error", { values: { reason: error } })}</p>
  {:else if sortedVersions.length === 0}
    <EmptyState
      icon="📋"
      title={$_("forecastHistory.empty_title")}
      body={$_("forecastHistory.empty_body")}
      primaryAction={{ label: $_("forecastHistory.empty_cta_primary"), onClick: () => goto('/wizard') }}
      secondaryAction={{ label: $_("forecastHistory.empty_cta_secondary"), onClick: () => goto('/') }}
    />
  {:else}
    <ol class="timeline" role="listbox" aria-multiselectable="true">
      {#each sortedVersions as v (v.version_id)}
        {@const isSelected = selected.has(v.version_id)}
        <li
          class="timeline-row"
          class:selected={isSelected}
          role="option"
          aria-selected={isSelected}
          onmouseenter={() => handleRowMouseEnter(v.version_id)}
        >
          <button
            type="button"
            class="select-toggle"
            aria-pressed={isSelected}
            aria-label={$_("history.version_select_label", { values: { revision: v.revision, action: isSelected ? $_("history.action_deselect") : $_("history.action_select") } })}
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
                <dt>{$_("history.expert.hash_label")}</dt>
                <dd class="mono">{shortHash(v.composite_bundle_hash)}</dd>
                <dt>{$_("history.expert.files_label")}</dt>
                <dd>{v.file_count}</dd>
                <dt>{$_("history.expert.id_label")}</dt>
                <dd class="mono">{v.version_id}</dd>
              </dl>
            {/if}
          </div>
        </li>
      {/each}
    </ol>
  {/if}

  {#if compareError}
    <p class="error-state" role="alert">{$_("history.compare_error", { values: { reason: compareError } })}</p>
  {/if}

  {#if forecastDiff && forecastDiff.available}
    <section class="semantic-diff-pane" aria-label="Семантический diff прогноза">
      <h3>📊 Что изменилось в прогнозе</h3>
      <dl class="semantic-diff-grid">
        <div class="semantic-diff-row">
          <dt>Прогноз (средний)</dt>
          <dd>
            <span class="value-before">{formatCompact(forecastDiff.point_a)}</span>
            <span class="arrow">→</span>
            <span class="value-after">{formatCompact(forecastDiff.point_b)}</span>
            <span
              class="delta-badge"
              data-direction={forecastDiff.point_delta_pct! >= 0 ? 'up' : 'down'}
            >{formatPct(forecastDiff.point_delta_pct)}</span>
          </dd>
        </div>
        <div class="semantic-diff-row">
          <dt>Ширина CI</dt>
          <dd>
            <span class="value-before">{formatCompact(forecastDiff.ci_width_a)}</span>
            <span class="arrow">→</span>
            <span class="value-after">{formatCompact(forecastDiff.ci_width_b)}</span>
            <span
              class="delta-badge"
              data-direction={forecastDiff.ci_width_delta_pct! <= 0 ? 'good' : 'bad'}
              title="Чем уже CI, тем увереннее прогноз"
            >{formatPct(forecastDiff.ci_width_delta_pct)}</span>
          </dd>
        </div>
        {#if forecastDiff.engine_mode_a !== forecastDiff.engine_mode_b}
          <div class="semantic-diff-row">
            <dt>Режим engine</dt>
            <dd>
              <code>{forecastDiff.engine_mode_a ?? '—'}</code>
              <span class="arrow">→</span>
              <code>{forecastDiff.engine_mode_b ?? '—'}</code>
            </dd>
          </div>
        {/if}
      </dl>
    </section>
  {/if}

  {#if diff}
    <section class="diff-pane" aria-label={$_("forecastHistory.diff_region_label")}>
      <h3>{$_("history.diff.title")}</h3>
      <div class="diff-summary">
        {#if diff.files_changed.length === 0 && diff.files_only_in_a.length === 0 && diff.files_only_in_b.length === 0}
          <p class="identical">{$_("history.diff.identical")}</p>
        {:else}
          <div class="diff-grid">
            <div class="diff-column" data-kind="changed">
              <h4>{$_("history.diff.changed", { values: { count: diff.files_changed.length } })}</h4>
              {#if diff.files_changed.length > 0}
                <ul>
                  {#each diff.files_changed as f}<li class="mono">{f}</li>{/each}
                </ul>
              {:else}
                <p class="muted">—</p>
              {/if}
            </div>
            <div class="diff-column" data-kind="only-a">
              <h4>{$_("history.diff.only_earlier", { values: { count: diff.files_only_in_a.length } })}</h4>
              {#if diff.files_only_in_a.length > 0}
                <ul>
                  {#each diff.files_only_in_a as f}<li class="mono">{f}</li>{/each}
                </ul>
              {:else}
                <p class="muted">—</p>
              {/if}
            </div>
            <div class="diff-column" data-kind="only-b">
              <h4>{$_("history.diff.only_later", { values: { count: diff.files_only_in_b.length } })}</h4>
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
            <p class="diff-unchanged-count">{$_("history.diff.unchanged_count", { values: { count: diff.files_unchanged.length } })}</p>
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
    transition:
      background-color var(--motion-duration-normal, 160ms) var(--motion-easing-standard, ease),
      border-color     var(--motion-duration-normal, 160ms) var(--motion-easing-standard, ease);
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
    transition:
      border-color     var(--motion-duration-normal, 160ms) var(--motion-easing-standard, ease),
      background-color var(--motion-duration-normal, 160ms) var(--motion-easing-standard, ease);
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

  .error-state {
    color: var(--color-danger, #dc2626);
    padding: var(--spacing-4, 1rem);
    text-align: center;
  }

  /* Phase 2 smart diff semantic panel */
  .semantic-diff-pane {
    padding: var(--spacing-3, 0.75rem) var(--spacing-4, 1rem);
    background: color-mix(in srgb, var(--accent, #2563eb) 5%, transparent);
    border-left: 3px solid var(--accent, #2563eb);
    border-radius: 4px;
    margin-bottom: var(--spacing-3, 0.75rem);
  }
  .semantic-diff-pane h3 {
    margin: 0 0 var(--spacing-3, 0.75rem) 0;
    font-size: 1rem;
  }
  .semantic-diff-grid {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2, 0.5rem);
    margin: 0;
  }
  .semantic-diff-row {
    display: flex;
    align-items: center;
    gap: var(--spacing-3, 0.75rem);
  }
  .semantic-diff-row dt {
    flex: 0 0 140px;
    color: var(--text-secondary, #4A4D57);
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
  }
  .semantic-diff-row dd {
    flex: 1;
    margin: 0;
    display: flex;
    align-items: center;
    gap: var(--spacing-2, 0.5rem);
  }
  .value-before {
    color: var(--text-muted, #6b7280);
    font-family: var(--font-mono, monospace);
  }
  .value-after {
    color: var(--text-primary, #111827);
    font-weight: 500;
    font-family: var(--font-mono, monospace);
  }
  .arrow {
    color: var(--text-muted, #9ca3af);
    font-weight: bold;
  }
  .delta-badge {
    padding: 2px 8px;
    border-radius: 999px;
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
    font-weight: 500;
    font-family: var(--font-mono, monospace);
  }
  .delta-badge[data-direction='up'] {
    background: color-mix(in srgb, var(--color-success, #047857) 15%, transparent);
    color: var(--color-success, #047857);
  }
  .delta-badge[data-direction='down'] {
    background: color-mix(in srgb, var(--color-danger, #B91C1C) 15%, transparent);
    color: var(--color-danger, #B91C1C);
  }
  .delta-badge[data-direction='good'] {
    background: color-mix(in srgb, var(--color-success, #047857) 15%, transparent);
    color: var(--color-success, #047857);
  }
  .delta-badge[data-direction='bad'] {
    background: color-mix(in srgb, var(--color-warning, #B45309) 15%, transparent);
    color: var(--color-warning, #B45309);
  }
  .semantic-diff-row code {
    font-size: 0.85rem;
    background: var(--bg-surface, white);
    padding: 2px 6px;
    border-radius: 3px;
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
