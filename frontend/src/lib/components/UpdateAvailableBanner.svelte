<!--
  UpdateAvailableBanner — Этап 2.9 ROADMAP_POST_V0_1_0.

  Показывается не-блокирующим баннером вверху layout'а когда найдена новая
  версия. Монтируется в +layout.svelte.

  Fleet-unify migration (2026-06-14): переведён с `tauri-plugin-updater`
  (minisign) на флотовый checksum-updater — данные идут через Rust IPC-команды
  (`check_update` / `download_update` / `apply_update`) + событие
  `update-progress`. Целостность = SHA256-checksum (verify в Rust). Подписи
  плагина больше нет.

  Жизненный цикл:
    'idle'        → начальное состояние (не показывается)
    'available'   → update найден, показываем banner с кнопками
    'downloading' → download_update запущен, прогресс-бар (update-progress)
    'installing'  → checksum verified, apply_update запускает инсталлятор;
                    приложение закроется (NSIS перезапишет файлы)
    'error'       → сетевой / checksum / install error (показывается мелко)

  INV-14: prefers-reduced-motion уважается через NotificationBanner + CSS ниже.
  Refactored on NotificationBanner (BTA-3 Phase 1.A): backdrop/positioning/ARIA delegated.

  Mock в Vitest: vi.mock('@tauri-apps/api/core') invoke + '@tauri-apps/api/event' listen.
-->

<script lang="ts">
  import { onMount } from 'svelte';
  import { _ } from 'svelte-i18n';
  import { invoke } from '@tauri-apps/api/core';
  import { listen } from '@tauri-apps/api/event';
  import NotificationBanner from './NotificationBanner.svelte';

  /** Серверный VersionInfo (commands/updater.rs::VersionInfo). */
  interface VersionInfo {
    version: string;
    download_url: string;
    release_notes?: string;
    mandatory?: boolean;
    checksum?: string;
    min_version?: string;
  }

  /** Информация об обнаруженном update для отображения + установки. */
  interface UpdateInfo {
    version: string;
    body: string | null;
    url?: string;
    checksum?: string;
  }

  interface Props {
    /** Только для тестов: форсированный update object, пропускает реальный check(). */
    forceUpdate?: UpdateInfo | null;
  }

  let { forceUpdate = undefined }: Props = $props();

  let bannerState = $state<'idle' | 'available' | 'downloading' | 'installing' | 'error'>('idle');
  let updateInfo = $state<UpdateInfo | null>(null);
  let downloadProgress = $state<number>(0);
  let errorMessage = $state<string | null>(null);
  let dismissedThisSession = $state<boolean>(false);

  const visible: boolean = $derived(
    !dismissedThisSession &&
      (bannerState === 'available' ||
        bannerState === 'downloading' ||
        bannerState === 'installing' ||
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
      const info = await invoke<VersionInfo | null>('check_update');
      if (info) {
        updateInfo = {
          version: info.version,
          body: info.release_notes ?? null,
          url: info.download_url,
          checksum: info.checksum ?? '',
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
    if (!updateInfo || bannerState === 'downloading' || bannerState === 'installing') return;
    if (!updateInfo.url) {
      errorMessage = 'No download URL';
      bannerState = 'error';
      return;
    }

    bannerState = 'downloading';
    downloadProgress = 0;
    errorMessage = null;

    const unlisten = await listen<{ percent: number; downloaded?: number; total?: number }>(
      'update-progress',
      (event) => {
        const pct = event.payload?.percent;
        if (typeof pct === 'number') downloadProgress = Math.min(100, Math.max(0, pct));
      },
    );

    try {
      // download_update downloads then verifies the SHA256 checksum (throws on mismatch).
      const installerPath = await invoke<string>('download_update', {
        url: updateInfo.url,
        checksum: updateInfo.checksum ?? '',
      });
      unlisten();
      downloadProgress = 100;
      bannerState = 'installing';
      // apply_update launches the installer (elevated) and exits the process on
      // success. If it returns, it errored (e.g. UAC denied) — surfaced below.
      await invoke('apply_update', { installerPath });
    } catch (e) {
      unlisten();
      console.error('[updater] install failed:', e);
      errorMessage = e instanceof Error ? e.message : String(e);
      bannerState = 'error';
    }
  }

  function dismiss() {
    dismissedThisSession = true;
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
    {:else if bannerState === 'installing'}
      <span class="icon" aria-hidden="true">⬇</span>
      <span class="message">{$_('updater.banner.installing')}</span>
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
    {:else if bannerState === 'error'}
      <button
        type="button"
        class="nb-btn nb-btn--ghost"
        onclick={installUpdate}
      >
        {$_('updater.banner.install_now')}
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
