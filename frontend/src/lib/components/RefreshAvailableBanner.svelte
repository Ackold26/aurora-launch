<!--
  RefreshAvailableBanner — ROADMAP §3.5: Automatic forecast refresh on new data.

  Lifecycle:
    'idle'      → initial; no triggers found, or consent not yet given
    'opt-in'    → first-run: user has never configured consent (null from sidecar)
    'available' → triggers found AND consent.enabled === true → shows banner
    'dismissed' → user clicked «Позже» (session-scoped; watcher dismissed)

  152-FZ / PDPL compliance:
    - No automatic action without prior explicit opt-in.
    - "Никогда не спрашивать" = set_refresh_consent({enabled: false}).
    - Watcher reads only LOCAL filesystem mtimes; no network calls.

  Props (test escape hatches):
    forceTriggers  — pre-built trigger list (bypasses real IPC check)
    forceConsent   — pre-built consent setting (bypasses real IPC fetch)
    projectUuid    — project UUID to check; defaults to first in list_projects
    sources        — data sources to watch

  Mounting: +layout.svelte (after UpdateAvailableBanner).
-->

<script lang="ts">
  import { onMount } from 'svelte';
  import { _ } from 'svelte-i18n';
  import { fly } from 'svelte/transition';
  import { ipc } from '$ipc/client';
  import type { RefreshConsentSetting, RefreshTrigger, DataSourceConfig } from '$ipc/client';
  import { fadeIn } from '$lib/services/motion';

  // ─── Props (test escape hatches) ──────────────────────────────────────────

  interface Props {
    /** Override consent fetch — useful in tests. */
    forceConsent?: RefreshConsentSetting | null | undefined;
    /** Override trigger detection — useful in tests. */
    forceTriggers?: RefreshTrigger[] | undefined;
    /** Project UUID to check updates for. In production, caller passes active project UUID. */
    projectUuid?: string;
    /** Data sources to watch. */
    sources?: DataSourceConfig[];
  }

  let {
    forceConsent = undefined,
    forceTriggers = undefined,
    projectUuid = '',
    sources = [],
  }: Props = $props();

  // ─── State ────────────────────────────────────────────────────────────────

  type BannerState = 'idle' | 'opt-in' | 'available' | 'dismissed';
  let bannerState = $state<BannerState>('idle');
  let triggers = $state<RefreshTrigger[]>([]);
  let consent = $state<RefreshConsentSetting | null>(null);
  let refreshing = $state(false);

  const visible: boolean = $derived(
    bannerState === 'opt-in' || bannerState === 'available',
  );

  // ─── Mount ────────────────────────────────────────────────────────────────

  onMount(() => {
    void init();
  });

  async function init() {
    // 1. Fetch consent (or use forced value for tests)
    if (forceConsent !== undefined) {
      consent = forceConsent;
    } else {
      try {
        consent = await ipc.getRefreshConsent();
      } catch (e) {
        console.warn('[refresh-banner] getRefreshConsent failed:', e);
        return;
      }
    }

    // 2. First-run: no consent configured → show opt-in dialog
    if (consent === null) {
      bannerState = 'opt-in';
      return;
    }

    // 3. Consent disabled → silent, no banner
    if (!consent.enabled) {
      return;
    }

    // 4. Consent enabled → check for triggers
    await checkTriggers();
  }

  async function checkTriggers() {
    if (forceTriggers !== undefined) {
      triggers = forceTriggers;
    } else if (projectUuid) {
      try {
        const result = await ipc.checkDataSourceUpdates(projectUuid, sources);
        triggers = result.triggers;
      } catch (e) {
        console.warn('[refresh-banner] checkDataSourceUpdates failed:', e);
        return;
      }
    }

    if (triggers.length > 0) {
      bannerState = 'available';
    }
  }

  // ─── Actions ──────────────────────────────────────────────────────────────

  async function handleOptIn() {
    try {
      const updated = await ipc.setRefreshConsent(true, 'weekly');
      consent = updated;
      bannerState = 'idle';
      // Now check for triggers immediately
      await checkTriggers();
    } catch (e) {
      console.warn('[refresh-banner] setRefreshConsent failed:', e);
    }
  }

  async function handleOptOut() {
    try {
      await ipc.setRefreshConsent(false, 'weekly');
      bannerState = 'idle';
    } catch (e) {
      console.warn('[refresh-banner] setRefreshConsent(false) failed:', e);
    }
  }

  async function handleRefreshNow() {
    if (refreshing) return;
    refreshing = true;
    try {
      // Mark all trigger sources as seen
      for (const trigger of triggers) {
        try {
          await ipc.dismissRefreshTrigger(trigger.project_uuid);
        } catch (_e) {
          // best-effort
        }
      }
      bannerState = 'dismissed';
      // Dispatch event so Inspector / project list can react
      window.dispatchEvent(
        new CustomEvent('aurora:refresh-forecast', { detail: { triggers } }),
      );
    } finally {
      refreshing = false;
    }
  }

  async function handleLater() {
    // Session-scoped dismiss — will show again on next app start
    if (projectUuid) {
      try {
        await ipc.dismissRefreshTrigger(projectUuid);
      } catch (_e) {
        // best-effort
      }
    }
    bannerState = 'dismissed';
  }

  async function handleNeverAsk() {
    // Permanent opt-out via consent setting
    try {
      await ipc.setRefreshConsent(false, consent?.frequency ?? 'weekly');
    } catch (e) {
      console.warn('[refresh-banner] neverAsk setRefreshConsent failed:', e);
    }
    bannerState = 'dismissed';
  }

  function triggerProjectCount(): number {
    const unique = new Set(triggers.map((t) => t.project_uuid));
    return unique.size;
  }
</script>

{#if visible}
  <div
    class="refresh-banner refresh-banner--{bannerState}"
    role="status"
    aria-live="polite"
    aria-label={$_('refresh.banner.aria_label')}
    transition:fadeIn
  >
    <div class="refresh-banner__content">
      {#if bannerState === 'opt-in'}
        <!-- First-run opt-in dialog (152-FZ §9) -->
        <span class="refresh-banner__icon" aria-hidden="true">◆</span>
        <div class="refresh-banner__body">
          <span class="refresh-banner__title">{$_('refresh.optin.title')}</span>
          <span class="refresh-banner__detail">{$_('refresh.optin.detail')}</span>
        </div>
        <div class="refresh-banner__actions">
          <button
            type="button"
            class="refresh-banner__btn refresh-banner__btn--primary"
            onclick={handleOptIn}
          >
            {$_('refresh.optin.accept')}
          </button>
          <button
            type="button"
            class="refresh-banner__btn refresh-banner__btn--ghost"
            onclick={handleOptOut}
          >
            {$_('refresh.optin.decline')}
          </button>
        </div>
      {:else if bannerState === 'available'}
        <!-- New data detected banner -->
        <span class="refresh-banner__icon" aria-hidden="true">↻</span>
        <span class="refresh-banner__message">
          {$_('refresh.banner.available', { values: { count: triggerProjectCount() } })}
        </span>
        <div class="refresh-banner__actions">
          <button
            type="button"
            class="refresh-banner__btn refresh-banner__btn--primary"
            onclick={handleRefreshNow}
            disabled={refreshing}
          >
            {refreshing ? $_('refresh.banner.refreshing') : $_('refresh.banner.refresh_now')}
          </button>
          <button
            type="button"
            class="refresh-banner__btn refresh-banner__btn--ghost"
            onclick={handleLater}
          >
            {$_('refresh.banner.later')}
          </button>
          <button
            type="button"
            class="refresh-banner__btn refresh-banner__btn--muted"
            onclick={handleNeverAsk}
          >
            {$_('refresh.banner.never')}
          </button>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .refresh-banner {
    width: 100%;
    padding: var(--spacing-2, 0.5rem) var(--spacing-6, 1.5rem);
    background: color-mix(in srgb, var(--color-info, #1d4ed8) 10%, var(--bg-surface, #fff));
    border-bottom: 1px solid
      color-mix(in srgb, var(--color-info, #1d4ed8) 25%, transparent);
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    z-index: 890;
  }

  .refresh-banner--opt-in {
    background: color-mix(in srgb, var(--accent, #6366f1) 8%, var(--bg-surface, #fff));
    border-bottom-color: color-mix(in srgb, var(--accent, #6366f1) 20%, transparent);
  }

  .refresh-banner__content {
    display: flex;
    align-items: center;
    gap: var(--spacing-3, 0.75rem);
    flex-wrap: wrap;
    max-width: 1200px;
    margin: 0 auto;
  }

  .refresh-banner__icon {
    color: var(--color-info, #1d4ed8);
    font-size: 1.1rem;
    flex-shrink: 0;
  }

  .refresh-banner--opt-in .refresh-banner__icon {
    color: var(--accent, #6366f1);
  }

  .refresh-banner__body {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1, 0.25rem);
  }

  .refresh-banner__title {
    color: var(--text-primary, #111);
    font-weight: 500;
  }

  .refresh-banner__detail {
    color: var(--text-muted, #6b7280);
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
    max-width: 560px;
  }

  .refresh-banner__message {
    flex: 1;
    color: var(--text-primary, #111);
  }

  .refresh-banner__actions {
    display: flex;
    gap: var(--spacing-2, 0.5rem);
    flex-shrink: 0;
    flex-wrap: wrap;
  }

  .refresh-banner__btn {
    padding: 4px 12px;
    border-radius: 4px;
    border: 1px solid transparent;
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    font-weight: 500;
    cursor: pointer;
    transition: opacity 120ms ease, background-color 120ms ease;
    line-height: 1.5;
  }

  .refresh-banner__btn:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }

  .refresh-banner__btn--primary {
    background: var(--color-info, #1d4ed8);
    border-color: var(--color-info, #1d4ed8);
    color: #fff;
  }

  .refresh-banner__btn--primary:hover:not(:disabled) {
    opacity: 0.9;
  }

  .refresh-banner__btn--ghost {
    background: transparent;
    border-color: var(--border-subtle, #d1d5db);
    color: var(--text-secondary, #555);
  }

  .refresh-banner__btn--ghost:hover {
    background: var(--surface-hover, #f9fafb);
    color: var(--text-primary, #111);
  }

  .refresh-banner__btn--muted {
    background: transparent;
    border-color: transparent;
    color: var(--text-muted, #9ca3af);
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
  }

  .refresh-banner__btn--muted:hover {
    color: var(--text-secondary, #555);
    text-decoration: underline;
  }

  @media (prefers-reduced-motion: reduce) {
    .refresh-banner__btn {
      transition: none;
    }
  }
</style>
