<!--
  UpdateAvailableBanner — Этап 2.9 ROADMAP_POST_V0_1_0.

  Показывается не-блокирующим баннером вверху layout'а когда tauri-plugin-updater
  обнаруживает новую версию. Монтируется в +layout.svelte.

  Жизненный цикл:
    'idle'        → начальное состояние (не показывается)
    'available'   → update найден, показываем banner с кнопками
    'downloading' → downloadAndInstall запущен, прогресс-бар
    'ready'       → установка завершена, нужен рестарт
    'error'       → сетевой / подпись-верификация error (показывается мелко)

  INV-14: prefers-reduced-motion уважается через fadeIn transition (duration=0 при reduced).
  Refactored on NotificationBanner (BTA-3 Phase 1.A): backdrop/positioning/ARIA delegated.

  Mock в Vitest: vi.mock('@tauri-apps/plugin-updater') — см. UpdateAvailableBanner.test.ts.
-->

<script lang="ts">
  import { onMount } from 'svelte';
  import { _ } from 'svelte-i18n';
  import { relaunch } from '@tauri-apps/plugin-process';
  import NotificationBanner from './NotificationBanner.svelte';

  /** Информация об обнаруженном update (подмножество plugin Update type). */
  interface UpdateInfo {
    version: string;
    body: string | null;
  }

  interface Props {
    /** Только для тестов: форсированный update object, пропускает реальный check(). */
    forceUpdate?: UpdateInfo | null;
  }

  let { forceUpdate = undefined }: Props = $props();

  let bannerState = $state<'idle' | 'available' | 'downloading' | 'ready' | 'error'>('idle');
  let updateInfo = $state<UpdateInfo | null>(null);
  let downloadProgress = $state<number>(0);
  let errorMessage = $state<string | null>(null);
  let dismissedThisSession = $state<boolean>(false);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let _updateHandle: any = null;

  const visible: boolean = $derived(
    !dismissedThisSession &&
      (bannerState === 'available' ||
        bannerState === 'downloading' ||
        bannerState === 'ready' ||
        bannerState === 'error'),
  );

  // level: error-state gets 'warning' tone; all other states use 'info'.
  const level = $derived(bannerState === 'error' ? 'warning' : 'info') as 'info' | 'warning';

  onMount(() => {
    if (forceUpdate !== undefined) {
      if (forceUpdate !== null) {
        updateInfo = forceUpdate;
        bannerState = 'available';
      }
      return;
    }

    void checkForUpdate();

    // Audit A-3 (этап 2.10): periodic re-check каждые 4 часа.
    const RECHECK_INTERVAL_MS = 4 * 60 * 60 * 1000;
    const intervalId = window.setInterval(() => {
      if (bannerState === 'idle' || bannerState === 'error') {
        dismissedThisSession = false;
        void checkForUpdate();
      }
    }, RECHECK_INTERVAL_MS);
    return () => window.clearInterval(intervalId);
  });

  async function checkForUpdate() {
    try {
      const { check } = await import('@tauri-apps/plugin-updater');
      const update = await check();

      if (update?.available) {
        _updateHandle = update;
        updateInfo = {
          version: update.version,
          body: update.body ?? null,
        };
        bannerState = 'available';
      }
    } catch (e) {
      console.warn('[updater] check failed:', e);
      errorMessage = e instanceof Error ? e.message : String(e);
      bannerState = 'error';
    }
  }

  async function installUpdate() {
    if (!_updateHandle || bannerState === 'downloading') return;
    bannerState = 'downloading';
    downloadProgress = 0;
    let downloadedBytes = 0;
    let totalBytes = 0;

    try {
      await _updateHandle.downloadAndInstall(
        (progress: {
          event: string;
          data?: { chunkLength?: number; contentLength?: number | null };
        }) => {
          if (progress.event === 'Started') {
            totalBytes = progress.data?.contentLength ?? 0;
            downloadedBytes = 0;
          } else if (progress.event === 'Progress') {
            downloadedBytes += progress.data?.chunkLength ?? 0;
            if (totalBytes === 0) {
              totalBytes = progress.data?.contentLength ?? 0;
            }
            if (totalBytes > 0) {
              downloadProgress = Math.min(
                100,
                Math.round((downloadedBytes / totalBytes) * 100),
              );
            } else {
              downloadProgress = -1;
            }
          } else if (progress.event === 'Finished') {
            downloadProgress = 100;
          }
        },
      );
      bannerState = 'ready';
    } catch (e) {
      console.error('[updater] downloadAndInstall failed:', e);
      errorMessage = e instanceof Error ? e.message : String(e);
      bannerState = 'error';
    }
  }

  function dismiss() {
    dismissedThisSession = true;
  }

  async function doRelaunch() {
    try {
      await relaunch();
    } catch (e) {
      console.error('[updater] relaunch failed:', e);
    }
  }
</script>

<NotificationBanner
  open={visible}
  {level}
  onDismiss={dismiss}
>
  {#snippet children()}
    {#if bannerState === 'available'}
      <span class="icon" aria-hidden="true">◆</span>
      <span class="message">
        {$_('updater.banner.available', {
          values: { version: updateInfo?.version ?? '' },
        })}
        {#if updateInfo?.body}
          <span class="update-banner__notes">{updateInfo.body}</span>
        {/if}
      </span>
    {:else if bannerState === 'downloading'}
      <span class="icon" aria-hidden="true">⬇</span>
      <span class="message">{$_('updater.banner.downloading')}</span>
      <div
        class="progress-wrap"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={downloadProgress >= 0 ? downloadProgress : undefined}
      >
        <div
          class="progress-bar"
          class:progress-bar--indeterminate={downloadProgress < 0}
          style:width="{downloadProgress >= 0 ? downloadProgress : 100}%"
        ></div>
      </div>
    {:else if bannerState === 'ready'}
      <span class="icon" aria-hidden="true">✓</span>
      <span class="message">{$_('updater.banner.ready')}</span>
    {:else if bannerState === 'error'}
      <span class="icon icon--error" aria-hidden="true">!</span>
      <span class="message message--error">{$_('updater.banner.error')}</span>
    {/if}
  {/snippet}

  {#snippet actions()}
    {#if bannerState === 'available'}
      <button
        type="button"
        class="nb-btn nb-btn--primary"
        onclick={installUpdate}
      >
        {$_('updater.banner.install_now')}
      </button>
      <button
        type="button"
        class="nb-btn nb-btn--ghost"
        onclick={dismiss}
        aria-label={$_('updater.banner.dismiss_aria')}
      >
        {$_('updater.banner.later')}
      </button>
    {:else if bannerState === 'ready'}
      <button
        type="button"
        class="nb-btn nb-btn--primary"
        onclick={doRelaunch}
      >
        {$_('updater.banner.relaunch')}
      </button>
      <button
        type="button"
        class="nb-btn nb-btn--ghost"
        onclick={dismiss}
        aria-label={$_('updater.banner.dismiss_aria')}
      >
        {$_('updater.banner.later')}
      </button>
    {/if}
  {/snippet}
</NotificationBanner>

<style>
  .icon {
    color: var(--color-ui-accent-primary, #6366f1);
    font-size: 1rem;
    flex-shrink: 0;
  }

  .icon--error {
    color: var(--state-warning-base, #ed6c02);
  }

  .message {
    flex: 1;
    color: var(--text-primary, #111);
    display: flex;
    align-items: center;
    gap: var(--spacing-2, 0.5rem);
    flex-wrap: wrap;
  }

  .message--error {
    color: var(--text-secondary, #555);
  }

  .update-banner__notes {
    color: var(--text-muted, #6b7280);
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
    font-style: italic;
    max-width: 320px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* Button styles delegated to NotificationBanner shared :global(.nb-btn) rules. */

  /* Progress bar */
  .progress-wrap {
    flex: 1;
    min-width: 120px;
    max-width: 240px;
    height: 6px;
    background: var(--border-subtle, #e5e7eb);
    border-radius: 3px;
    overflow: hidden;
  }

  .progress-bar {
    height: 100%;
    background: var(--color-ui-accent-primary, #6366f1);
    border-radius: 3px;
    transition: width 200ms ease;
  }

  @keyframes indeterminate {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(200%); }
  }

  .progress-bar--indeterminate {
    width: 40% !important;
    animation: indeterminate 1.2s ease infinite;
  }

  /* INV-14: prefers-reduced-motion */
  @media (prefers-reduced-motion: reduce) {
    .progress-bar--indeterminate {
      animation: none;
      width: 100% !important;
      opacity: 0.5;
    }

    .progress-bar {
      transition: none;
    }
  }
</style>
