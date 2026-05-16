<!--
  DataSourcesCard — Settings card for managing per-project watched folders.

  Allows the user to:
    - Select a project from the list (project dropdown)
    - View existing data source folders (DSM / Mediascope / Manual)
    - Add a folder via Tauri directory picker
    - Remove a folder from the list
    - All changes auto-save via ipc.setDataSources()

  Props:
    projectUuid?  — pre-selected project UUID (optional; shows dropdown to pick one)

  A11y:
    - Card heading + project selector linked via aria-labelledby
    - Source list uses <ul>/<li> semantics
    - Dismiss buttons have aria-label="Убрать папку {path}"
    - aria-live="polite" on save indicator
    - Empty state announced via aria-live region

  INV-14: no JS-driven animations; CSS transitions only + reduced-motion guard.
-->

<script lang="ts">
  import { onMount, untrack } from 'svelte';
  import { _ } from 'svelte-i18n';
  import { ipc } from '$ipc/client';
  import type { DataSourceConfig } from '$ipc/client';
  import { listProjects } from '$ipc/projects';
  import type { ProjectSummary } from '$ipc/projects';

  // ── Props ──────────────────────────────────────────────────────────────────

  interface Props {
    /** Pre-selected project UUID. If not provided, user must choose via dropdown. */
    projectUuid?: string | null;
  }

  let { projectUuid = null }: Props = $props();

  // ── Internal state ─────────────────────────────────────────────────────────

  let projects = $state<ProjectSummary[]>([]);
  // untrack: capturing initial prop value is intentional (no reactive tracking needed here)
  let selectedProjectUuid = $state<string | null>(untrack(() => projectUuid));
  let sources = $state<DataSourceConfig[]>([]);
  let loading = $state(false);
  let errorMsg = $state<string | null>(null);
  let saveState = $state<'idle' | 'saving' | 'saved'>('idle');
  let saveTimer: ReturnType<typeof setTimeout> | null = null;

  // For add-dialog state
  let addKind = $state<DataSourceConfig['source_kind']>('dsm_xlsx_folder');
  let adding = $state(false);

  // ── Computed ───────────────────────────────────────────────────────────────

  const kindLabel = $derived.by(() => ({
    dsm_xlsx_folder: $_('settings.datasources.kind.dsm'),
    mediascope_xlsx_folder: $_('settings.datasources.kind.mediascope'),
    manual: $_('settings.datasources.kind.manual'),
  }));

  // ── Lifecycle ──────────────────────────────────────────────────────────────

  onMount(async () => {
    await loadProjects();
    if (selectedProjectUuid) {
      await loadSources(selectedProjectUuid);
    }
  });

  async function loadProjects() {
    try {
      projects = await listProjects();
      // If no project pre-selected but there is only one, auto-select it
      if (!selectedProjectUuid && projects.length === 1) {
        const first = projects[0];
        if (first) {
          selectedProjectUuid = first.project_uuid;
          await loadSources(first.project_uuid);
        }
      }
    } catch (e) {
      errorMsg = e instanceof Error ? e.message : String(e);
    }
  }

  async function loadSources(uuid: string) {
    loading = true;
    errorMsg = null;
    try {
      const result = await ipc.getDataSources(uuid);
      sources = result.sources;
    } catch (e) {
      errorMsg = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  async function saveSources(uuid: string, newSources: DataSourceConfig[]) {
    saveState = 'saving';
    if (saveTimer !== null) clearTimeout(saveTimer);
    try {
      await ipc.setDataSources(uuid, newSources);
      saveState = 'saved';
      saveTimer = setTimeout(() => {
        saveState = 'idle';
      }, 2500);
    } catch {
      saveState = 'idle';
    }
  }

  // ── Event handlers ─────────────────────────────────────────────────────────

  async function onProjectChange(e: Event) {
    const val = (e.target as HTMLSelectElement).value;
    selectedProjectUuid = val || null;
    sources = [];
    saveState = 'idle';
    if (selectedProjectUuid) {
      await loadSources(selectedProjectUuid);
    }
  }

  async function removeSource(index: number) {
    if (!selectedProjectUuid) return;
    const next = sources.filter((_, i) => i !== index);
    sources = next;
    await saveSources(selectedProjectUuid, next);
  }

  async function addFolder() {
    if (!selectedProjectUuid || adding) return;
    adding = true;
    try {
      const { open } = await import('@tauri-apps/plugin-dialog');
      const chosen = await open({ directory: true, title: $_('settings.datasources.dialog_title') });
      if (typeof chosen === 'string' && chosen) {
        const newSource: DataSourceConfig = {
          source_kind: addKind,
          path: chosen,
          last_checked_at: null,
          last_modified_seen: null,
        };
        const next = [...sources, newSource];
        sources = next;
        await saveSources(selectedProjectUuid, next);
      }
    } catch {
      // User cancelled or dialog failed — silently ignore
    } finally {
      adding = false;
    }
  }

  async function retryLoad() {
    errorMsg = null;
    if (selectedProjectUuid) {
      await loadSources(selectedProjectUuid);
    } else {
      await loadProjects();
    }
  }

  function formatCheckedAt(ts: string | null | undefined): string {
    if (!ts) return $_('settings.datasources.never_checked');
    try {
      const d = new Date(ts);
      return $_('settings.datasources.checked_at', { values: { time: d.toLocaleString('ru-RU') } });
    } catch {
      return ts;
    }
  }
</script>

<article class="ds-card" aria-labelledby="ds-heading">
  <!-- Header row -->
  <div class="ds-header">
    <div class="ds-titles">
      <h3 id="ds-heading" class="ds-title">{$_('settings.datasources.title')}</h3>
      <p class="ds-subtitle">{$_('settings.datasources.subtitle')}</p>
    </div>
    <!-- Save state indicator -->
    {#if selectedProjectUuid && saveState !== 'idle'}
      <span
        class="save-indicator"
        data-state={saveState}
        aria-live="polite"
        role="status"
        aria-label={saveState === 'saving'
          ? $_('settings.datasources.saving')
          : $_('settings.datasources.saved')}
      >
        <span class="save-dot" aria-hidden="true"></span>
        <span class="save-label">
          {saveState === 'saving'
            ? $_('settings.datasources.saving')
            : $_('settings.datasources.saved')}
        </span>
      </span>
    {/if}
  </div>

  <!-- Project selector -->
  <div class="ds-project-row">
    <label for="ds-project-select" class="ds-project-label">
      {$_('settings.datasources.project_label')}
    </label>
    <select
      id="ds-project-select"
      class="ds-select"
      value={selectedProjectUuid ?? ''}
      onchange={onProjectChange}
      aria-labelledby="ds-heading"
    >
      <option value="">{$_('settings.datasources.select_project')}</option>
      {#each projects as project (project.project_uuid)}
        <option value={project.project_uuid}>{project.name}</option>
      {/each}
    </select>
  </div>

  <!-- Error state -->
  {#if errorMsg}
    <div class="ds-error" role="alert">
      <span>{$_('settings.datasources.error')}</span>
      <button class="ds-retry-btn" onclick={retryLoad} type="button">
        {$_('settings.datasources.retry')}
      </button>
    </div>
  {:else if !selectedProjectUuid}
    <!-- No project selected -->
    <p class="ds-hint" aria-live="polite">{$_('settings.datasources.no_project')}</p>
  {:else if loading}
    <!-- Loading skeleton -->
    <div class="ds-loading" aria-live="polite" aria-label="Загрузка…">
      <div class="ds-skeleton"></div>
      <div class="ds-skeleton ds-skeleton--short"></div>
    </div>
  {:else if sources.length === 0}
    <!-- Empty state -->
    <p class="ds-empty" aria-live="polite">{$_('settings.datasources.empty')}</p>
  {:else}
    <!-- Source list -->
    <ul class="ds-list" aria-label={$_('settings.datasources.title')}>
      {#each sources as source, i (source.path ?? `${source.source_kind}-${i}`)}
        <li class="ds-row">
          <span class="ds-kind-badge ds-kind-badge--{source.source_kind}">
            {kindLabel[source.source_kind]}
          </span>
          <span class="ds-path" title={source.path ?? ''}>{source.path ?? '—'}</span>
          <span class="ds-checked">{formatCheckedAt(source.last_checked_at)}</span>
          <button
            class="ds-remove-btn"
            type="button"
            aria-label={$_('settings.datasources.remove', { values: { path: source.path ?? '' } })}
            onclick={() => removeSource(i)}
          >
            ×
          </button>
        </li>
      {/each}
    </ul>
  {/if}

  <!-- Add folder row (shown when project is selected and not in error) -->
  {#if selectedProjectUuid && !errorMsg}
    <div class="ds-add-row">
      <label for="ds-kind-select" class="ds-add-label">
        {$_('settings.datasources.kind_label')}
      </label>
      <select id="ds-kind-select" class="ds-select ds-kind-select" bind:value={addKind}>
        <option value="dsm_xlsx_folder">{$_('settings.datasources.kind_dsm')}</option>
        <option value="mediascope_xlsx_folder">{$_('settings.datasources.kind_mediascope')}</option>
        <option value="manual">{$_('settings.datasources.kind_manual')}</option>
      </select>
      <button
        class="ds-add-btn"
        type="button"
        disabled={adding}
        onclick={addFolder}
      >
        {adding ? '…' : $_('settings.datasources.add')}
      </button>
    </div>
  {/if}
</article>

<style>
  .ds-card {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-3);
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-lg);
    padding: var(--spacing-4);
    box-shadow: var(--shadow-sm);
  }

  .ds-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--spacing-3);
  }

  .ds-titles {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1);
  }

  .ds-title {
    font-size: var(--typography-fontSize-ui-h3);
    color: var(--text-primary);
    font-weight: 500;
    margin: 0;
  }

  .ds-subtitle {
    color: var(--text-secondary);
    font-size: var(--typography-fontSize-ui-sm);
    margin: 0;
    max-width: 480px;
  }

  /* Save indicator */
  .save-indicator {
    display: inline-flex;
    align-items: center;
    gap: var(--spacing-1, 0.25rem);
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
    flex-shrink: 0;
  }

  .save-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
    transition: background-color var(--motion-default, 200ms) ease;
  }

  [data-state='saving'] .save-dot { background: var(--color-warning, #f59e0b); }
  [data-state='saving'] .save-label { color: var(--color-warning, #f59e0b); }
  [data-state='saved'] .save-dot { background: var(--color-success, #10b981); }
  [data-state='saved'] .save-label { color: var(--color-success, #10b981); }

  @media (prefers-reduced-motion: no-preference) {
    [data-state='saving'] .save-dot {
      animation: ds-pulse 1s ease-in-out infinite;
    }
  }

  @keyframes ds-pulse {
    0%   { opacity: 1; transform: scale(1); }
    50%  { opacity: 0.45; transform: scale(0.8); }
    100% { opacity: 1; transform: scale(1); }
  }

  /* Project selector */
  .ds-project-row {
    display: flex;
    align-items: center;
    gap: var(--spacing-2);
    flex-wrap: wrap;
  }

  .ds-project-label,
  .ds-add-label {
    color: var(--text-secondary);
    font-size: var(--typography-fontSize-ui-sm);
    white-space: nowrap;
  }

  .ds-select {
    background: var(--bg-main);
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-md);
    color: var(--text-primary);
    font-family: var(--font-sans);
    font-size: var(--typography-fontSize-ui-sm);
    padding: var(--spacing-1) var(--spacing-2);
    cursor: pointer;
  }

  .ds-select:focus {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }

  /* Error */
  .ds-error {
    display: flex;
    align-items: center;
    gap: var(--spacing-2);
    padding: var(--spacing-2) var(--spacing-3);
    background: color-mix(in srgb, var(--color-danger, #ef4444) 10%, var(--bg-main));
    border: 1px solid color-mix(in srgb, var(--color-danger, #ef4444) 30%, transparent);
    border-radius: var(--border-radius-md);
    color: var(--text-secondary);
    font-size: var(--typography-fontSize-ui-sm);
  }

  .ds-retry-btn {
    background: transparent;
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-md);
    color: var(--accent);
    cursor: pointer;
    font-size: var(--typography-fontSize-ui-sm);
    padding: 2px var(--spacing-2);
  }

  .ds-retry-btn:hover {
    background: color-mix(in srgb, var(--accent) 10%, transparent);
  }

  /* Hint / empty */
  .ds-hint,
  .ds-empty {
    color: var(--text-muted);
    font-size: var(--typography-fontSize-ui-sm);
    margin: 0;
    max-width: 480px;
  }

  /* Loading skeletons */
  .ds-loading {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
  }

  .ds-skeleton {
    height: 36px;
    background: color-mix(in srgb, var(--text-muted) 12%, var(--bg-main));
    border-radius: var(--border-radius-md);
    animation: ds-shimmer 1.5s ease-in-out infinite;
  }

  .ds-skeleton--short {
    width: 60%;
  }

  @media (prefers-reduced-motion: reduce) {
    .ds-skeleton { animation: none; }
  }

  @keyframes ds-shimmer {
    0%   { opacity: 1; }
    50%  { opacity: 0.5; }
    100% { opacity: 1; }
  }

  /* Source list */
  .ds-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
  }

  .ds-row {
    display: grid;
    grid-template-columns: auto 1fr auto auto;
    align-items: center;
    gap: var(--spacing-2);
    padding: var(--spacing-2) var(--spacing-3);
    background: var(--bg-main);
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-md);
    transition: border-color var(--motion-fast, 150ms) ease;
  }

  .ds-row:hover {
    border-color: color-mix(in srgb, var(--accent) 35%, var(--border-subtle));
  }

  /* Kind badges */
  .ds-kind-badge {
    font-size: var(--typography-fontSize-ui-xs, 0.72rem);
    font-weight: 600;
    padding: 2px 6px;
    border-radius: var(--border-radius-sm, 4px);
    white-space: nowrap;
  }

  .ds-kind-badge--dsm_xlsx_folder {
    background: color-mix(in srgb, var(--color-info, #3b82f6) 15%, transparent);
    color: color-mix(in srgb, var(--color-info, #3b82f6) 90%, var(--text-primary));
  }

  .ds-kind-badge--mediascope_xlsx_folder {
    background: color-mix(in srgb, var(--color-success, #10b981) 15%, transparent);
    color: color-mix(in srgb, var(--color-success, #10b981) 90%, var(--text-primary));
  }

  .ds-kind-badge--manual {
    background: color-mix(in srgb, var(--text-muted, #7a7a90) 15%, transparent);
    color: var(--text-secondary);
  }

  .ds-path {
    font-size: var(--typography-fontSize-ui-sm);
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
  }

  .ds-checked {
    font-size: var(--typography-fontSize-ui-xs, 0.72rem);
    color: var(--text-muted);
    white-space: nowrap;
  }

  .ds-remove-btn {
    background: transparent;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 1.1rem;
    line-height: 1;
    padding: 2px 4px;
    border-radius: var(--border-radius-sm, 4px);
    transition: color var(--motion-fast, 150ms), background var(--motion-fast, 150ms);
  }

  .ds-remove-btn:hover {
    color: var(--color-danger, #ef4444);
    background: color-mix(in srgb, var(--color-danger, #ef4444) 10%, transparent);
  }

  .ds-remove-btn:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }

  /* Add row */
  .ds-add-row {
    display: flex;
    align-items: center;
    gap: var(--spacing-2);
    flex-wrap: wrap;
    padding-top: var(--spacing-2);
    border-top: 1px solid var(--border-subtle);
  }

  .ds-kind-select {
    flex: 0 0 auto;
  }

  .ds-add-btn {
    background: transparent;
    border: 1px solid var(--accent);
    border-radius: var(--border-radius-md);
    color: var(--accent);
    cursor: pointer;
    font-family: var(--font-sans);
    font-size: var(--typography-fontSize-ui-sm);
    padding: var(--spacing-1) var(--spacing-3);
    transition: background var(--motion-fast, 150ms), color var(--motion-fast, 150ms);
  }

  .ds-add-btn:hover:not(:disabled) {
    background: var(--accent);
    color: white;
  }

  .ds-add-btn:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .ds-add-btn:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }
</style>
