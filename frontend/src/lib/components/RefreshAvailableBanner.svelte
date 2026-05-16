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
  Refactored on NotificationBanner (BTA-3 Phase 1.A): backdrop/ARIA/motion delegated.
-->

<script lang="ts">
  import { onMount } from 'svelte';
  import { _ } from 'svelte-i18n';
  import { ipc } from '$ipc/client';
  import type { RefreshConsentSetting, RefreshTrigger, DataSourceConfig } from '$ipc/client';
  import NotificationBanner from './NotificationBanner.svelte';

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

  // opt-in state = more prominent (prompt-level); available = info banner
  const level = $derived(bannerState === 'opt-in' ? 'info' : 'info') as 'info';

  // ─── Mount ────────────────────────────────────────────────────────────────

  onMount(() => {
    void init();
  });

  async function init() {
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

    if (consent === null) {
      bannerState = 'opt-in';
      return;
    }

    if (!consent.enabled) {
      return;
    }

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
      for (const trigger of triggers) {
        try {
          await ipc.dismissRefreshTrigger(trigger.project_uuid);
        } catch (_e) {
          // best-effort
        }
      }
      bannerState = 'dismissed';
      window.dispatchEvent(
        new CustomEvent('aurora:refresh-forecast', { detail: { triggers } }),
      );
    } finally {
      refreshing = false;
    }
  }

  async function handleLater() {
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

  function handleDismiss() {
    if (bannerState === 'opt-in') {
      void handleOptOut();
    } else {
      void handleLater();
    }
  }
</script>

<NotificationBanner
  open={visible}
  {level}
  onDismiss={handleDismiss}
>
  {#snippet children()}
    {#if bannerState === 'opt-in'}
      <span class="icon" aria-hidden="true">◆</span>
      <div class="body">
        <span class="title">{$_('refresh.optin.title')}</span>
        <span class="detail">{$_('refresh.optin.detail')}</span>
      </div>
    {:else if bannerState === 'available'}
      <span class="icon icon--refresh" aria-hidden="true">↻</span>
      <span class="message">
        {$_('refresh.banner.available', { values: { count: triggerProjectCount() } })}
      </span>
    {/if}
  {/snippet}

  {#snippet actions()}
    {#if bannerState === 'opt-in'}
      <button
        type="button"
        class="nb-btn nb-btn--primary"
        onclick={handleOptIn}
      >
        {$_('refresh.optin.accept')}
      </button>
      <button
        type="button"
        class="nb-btn nb-btn--ghost"
        onclick={handleOptOut}
      >
        {$_('refresh.optin.decline')}
      </button>
    {:else if bannerState === 'available'}
      <button
        type="button"
        class="nb-btn nb-btn--primary"
        onclick={handleRefreshNow}
        disabled={refreshing}
      >
        {refreshing ? $_('refresh.banner.refreshing') : $_('refresh.banner.refresh_now')}
      </button>
      <button
        type="button"
        class="nb-btn nb-btn--ghost"
        onclick={handleLater}
      >
        {$_('refresh.banner.later')}
      </button>
      <button
        type="button"
        class="nb-btn nb-btn--muted"
        onclick={handleNeverAsk}
      >
        {$_('refresh.banner.never')}
      </button>
    {/if}
  {/snippet}
</NotificationBanner>

<style>
  .icon {
    color: var(--color-ui-accent-primary, #6366f1);
    font-size: 1.1rem;
    flex-shrink: 0;
  }

  .icon--refresh {
    color: var(--color-info, #1d4ed8);
  }

  .body {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1, 0.25rem);
  }

  .title {
    color: var(--text-primary, #111);
    font-weight: 500;
  }

  .detail {
    /* WCAG AA 4.5:1 fix (A11Y-W01): --text-muted (#7A7D87 on white) is ~3.6:1
       at xs font-size. Use --text-secondary (#4A4D57) which is ~7.6:1. */
    color: var(--text-secondary, #4a4d57);
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
    max-width: 560px;
  }

  .message {
    flex: 1;
    color: var(--text-primary, #111);
  }

  /* Button styles delegated to NotificationBanner shared :global(.nb-btn) rules. */
</style>
