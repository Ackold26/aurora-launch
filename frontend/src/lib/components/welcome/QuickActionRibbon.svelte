<!--
  QuickActionRibbon — Sprint 1 UX Foundation, top-of-workspace action bar.

  4 main CTAs after first project creation. The «Новый прогноз» CTA uses
  sacred lime sigil (single primary on Workspace screen per Button.svelte
  invariant). Other 3 = ghost variant.

  Actions:
    - New project (sigil) → goto('/wizard')
    - Refresh forecasts (ghost) → refresh callback prop (parent handles)
    - Open inspector (ghost) → goto('/inspector')
    - Settings (ghost) → goto('/settings')
-->

<script lang="ts">
  import { _ } from 'svelte-i18n';
  import { goto } from '$app/navigation';

  interface Props {
    /** Optional refresh handler. When undefined, the refresh CTA is hidden
     *  so the ribbon doesn't promise a non-functional action. */
    onRefresh?: () => void | Promise<void>;
    /** Optional override для inspector destination. Defaults to /inspector. */
    inspectorHref?: string;
  }

  let { onRefresh, inspectorHref = '/inspector' }: Props = $props();

  let refreshing: boolean = $state(false);

  async function handleRefresh(): Promise<void> {
    if (!onRefresh || refreshing) return;
    refreshing = true;
    try {
      await onRefresh();
    } finally {
      refreshing = false;
    }
  }

  function handleNewProject(): void {
    void goto('/wizard');
  }

  function handleInspector(): void {
    void goto(inspectorHref);
  }

  function handleSettings(): void {
    void goto('/settings');
  }
</script>

<section
  class="quick-actions"
  aria-label={$_('dashboard.quick.aria_label')}
>
  <div class="quick-grid">
    <button
      type="button"
      class="action action--sigil"
      onclick={handleNewProject}
    >
      <span class="action-icon" aria-hidden="true">+</span>
      <span class="action-body">
        <span class="action-title">{$_('dashboard.quick.new_project.title')}</span>
        <span class="action-hint">{$_('dashboard.quick.new_project.hint')}</span>
      </span>
    </button>

    {#if onRefresh}
      <button
        type="button"
        class="action action--ghost"
        onclick={handleRefresh}
        disabled={refreshing}
        aria-busy={refreshing}
      >
        <span class="action-icon" class:action-icon--spinning={refreshing} aria-hidden="true">↻</span>
        <span class="action-body">
          <span class="action-title">
            {refreshing
              ? $_('dashboard.quick.refresh.running')
              : $_('dashboard.quick.refresh.title')}
          </span>
          <span class="action-hint">{$_('dashboard.quick.refresh.hint')}</span>
        </span>
      </button>
    {/if}

    <button
      type="button"
      class="action action--ghost"
      onclick={handleInspector}
    >
      <span class="action-icon" aria-hidden="true">◇</span>
      <span class="action-body">
        <span class="action-title">{$_('dashboard.quick.inspector.title')}</span>
        <span class="action-hint">{$_('dashboard.quick.inspector.hint')}</span>
      </span>
    </button>

    <button
      type="button"
      class="action action--ghost"
      onclick={handleSettings}
    >
      <span class="action-icon" aria-hidden="true">⚙</span>
      <span class="action-body">
        <span class="action-title">{$_('dashboard.quick.settings.title')}</span>
        <span class="action-hint">{$_('dashboard.quick.settings.hint')}</span>
      </span>
    </button>
  </div>
</section>

<style>
  .quick-actions {
    display: block;
  }

  .quick-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: var(--spacing-3);
  }

  /* ── Action button — shared base ────────────────────────────────────────── */

  .action {
    display: flex;
    align-items: center;
    gap: var(--spacing-3);
    padding: var(--spacing-4);
    border-radius: var(--border-radius-md);
    border: 1px solid transparent;
    font-family: var(--font-sans);
    text-align: left;
    cursor: pointer;
    transition:
      transform var(--motion-default) var(--easing-spring),
      border-color var(--motion-default) var(--easing-smooth),
      background var(--motion-default) var(--easing-smooth),
      box-shadow var(--motion-default) var(--easing-smooth);
  }

  .action:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .action:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .action:not(:disabled):active {
    transform: translateY(1px);
  }

  /* ── Primary sigil (sacred lime — only one per screen) ──────────────────── */

  .action--sigil {
    background: var(--accent-sigil);
    color: var(--color-brand-deep-100, #0a1628);
    border-color: var(--accent-sigil);
  }

  .action--sigil .action-title {
    font-weight: var(--typography-fontWeight-bold);
  }

  .action--sigil:not(:disabled):hover {
    transform: translateY(-1px);
    box-shadow: 0 0 24px color-mix(in srgb, var(--accent-sigil) 45%, transparent);
  }

  /* ── Ghost variant (secondary actions) ──────────────────────────────────── */

  .action--ghost {
    background: var(--bg-surface);
    color: var(--text-primary);
    border-color: var(--border-subtle);
  }

  .action--ghost:not(:disabled):hover {
    border-color: var(--accent);
    background: color-mix(in srgb, var(--accent) 8%, var(--bg-surface));
  }

  /* ── Icon + body slots ──────────────────────────────────────────────────── */

  .action-icon {
    font-size: var(--typography-fontSize-ui-h2);
    line-height: 1;
    flex-shrink: 0;
  }

  .action-icon--spinning {
    animation: action-spin 1s linear infinite;
  }

  @keyframes action-spin {
    to { transform: rotate(360deg); }
  }

  .action-body {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1);
    min-width: 0;
  }

  .action-title {
    font-size: var(--typography-fontSize-ui-body);
    font-weight: var(--typography-fontWeight-medium);
    line-height: var(--typography-lineHeight-snug);
  }

  .action-hint {
    color: color-mix(in srgb, currentColor 65%, transparent);
    font-size: var(--typography-fontSize-ui-xs);
    line-height: var(--typography-lineHeight-normal);
  }

  /* ── INV-14 reduced motion ──────────────────────────────────────────────── */

  @media (prefers-reduced-motion: reduce) {
    .action {
      transition: none;
    }
    .action-icon--spinning {
      animation: none;
    }
  }
</style>
