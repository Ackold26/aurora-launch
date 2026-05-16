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

  Mock в Vitest: vi.mock('@tauri-apps/plugin-updater') — см. UpdateAvailableBanner.test.ts.
-->

<script lang="ts">
  import { onMount } from 'svelte';
  import { _ } from 'svelte-i18n';
  import { relaunch } from '@tauri-apps/plugin-process';
  import { fadeIn } from '$lib/services/motion';

  /** Информация об обнаруженном update (подмножество plugin Update type). */
  interface UpdateInfo {
    version: string;
    body: string | null;
  }

  // Props: позволяем тестам передать update object напрямую, минуя реальный check().
  interface Props {
    /** Только для тестов: форсированный update object, пропускает реальный check(). */
    forceUpdate?: UpdateInfo | null;
  }

  let { forceUpdate = undefined }: Props = $props();

  // Используем generic $state<Type>(value) — паттерн принятый в проекте (wizard/+page.svelte).
  // Annotation-style `let x: T = $state(v)` конфликтует с type narrowing в svelte-check.
  let bannerState = $state<'idle' | 'available' | 'downloading' | 'ready' | 'error'>('idle');
  let updateInfo = $state<UpdateInfo | null>(null);
  let downloadProgress = $state<number>(0);
  let errorMessage = $state<string | null>(null);
  let dismissedThisSession = $state<boolean>(false);

  // Внутренняя ссылка на update object из plugin (для downloadAndInstall).
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let _updateHandle: any = null;

  const visible: boolean = $derived(
    !dismissedThisSession &&
      (bannerState === 'available' ||
        bannerState === 'downloading' ||
        bannerState === 'ready' ||
        bannerState === 'error'),
  );

  onMount(() => {
    if (forceUpdate !== undefined) {
      // Тестовый путь: форсируем состояние через prop.
      if (forceUpdate !== null) {
        updateInfo = forceUpdate;
        bannerState = 'available';
      }
      return;
    }

    // Продакшн путь: fire-and-forget best-effort check.
    void checkForUpdate();
  });

  async function checkForUpdate() {
    try {
      // Динамический импорт позволяет vi.mock('@tauri-apps/plugin-updater')
      // перехватить вызов в тестах без side effects при module load.
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
      // update === null или update.available === false → bannerState остаётся 'idle' (banner hidden)
    } catch (e) {
      // Сетевой сбой, подпись не прошла — логируем тихо, не блокируем UI.
      console.warn('[updater] check failed:', e);
      errorMessage = e instanceof Error ? e.message : String(e);
      bannerState = 'error';
    }
  }

  async function installUpdate() {
    if (!_updateHandle || bannerState === 'downloading') return;
    bannerState = 'downloading';
    downloadProgress = 0;

    try {
      await _updateHandle.downloadAndInstall(
        (progress: {
          event: string;
          data?: { chunkLength?: number; contentLength?: number | null };
        }) => {
          if (progress.event === 'Progress') {
            const chunkLen = progress.data?.chunkLength ?? 0;
            const totalLen = progress.data?.contentLength ?? 0;
            if (totalLen > 0) {
              downloadProgress = Math.min(
                100,
                Math.round((chunkLen / totalLen) * 100),
              );
            } else {
              // Неизвестный размер — индикатор пульсирует (-1 = indeterminate).
              downloadProgress = -1;
            }
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

{#if visible}
  <div
    class="update-banner update-banner--{bannerState}"
    role="status"
    aria-live="polite"
    aria-label={$_('updater.banner.aria_label')}
    transition:fadeIn
  >
    <div class="update-banner__content">
      {#if bannerState === 'available'}
        <span class="update-banner__icon" aria-hidden="true">◆</span>
        <span class="update-banner__message">
          {$_('updater.banner.available', {
            values: { version: updateInfo?.version ?? '' },
          })}
          {#if updateInfo?.body}
            <span class="update-banner__notes">{updateInfo.body}</span>
          {/if}
        </span>
        <div class="update-banner__actions">
          <button
            type="button"
            class="update-banner__btn update-banner__btn--primary"
            onclick={installUpdate}
          >
            {$_('updater.banner.install_now')}
          </button>
          <button
            type="button"
            class="update-banner__btn update-banner__btn--ghost"
            onclick={dismiss}
            aria-label={$_('updater.banner.dismiss_aria')}
          >
            {$_('updater.banner.later')}
          </button>
        </div>
      {:else if bannerState === 'downloading'}
        <span class="update-banner__icon" aria-hidden="true">⬇</span>
        <span class="update-banner__message">
          {$_('updater.banner.downloading')}
        </span>
        <div
          class="update-banner__progress-wrap"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={downloadProgress >= 0 ? downloadProgress : undefined}
        >
          <div
            class="update-banner__progress-bar"
            class:update-banner__progress-bar--indeterminate={downloadProgress < 0}
            style:width="{downloadProgress >= 0 ? downloadProgress : 100}%"
          ></div>
        </div>
      {:else if bannerState === 'ready'}
        <span class="update-banner__icon" aria-hidden="true">✓</span>
        <span class="update-banner__message">
          {$_('updater.banner.ready')}
        </span>
        <div class="update-banner__actions">
          <button
            type="button"
            class="update-banner__btn update-banner__btn--primary"
            onclick={doRelaunch}
          >
            {$_('updater.banner.relaunch')}
          </button>
          <button
            type="button"
            class="update-banner__btn update-banner__btn--ghost"
            onclick={dismiss}
            aria-label={$_('updater.banner.dismiss_aria')}
          >
            {$_('updater.banner.later')}
          </button>
        </div>
      {:else if bannerState === 'error'}
        <span class="update-banner__icon" aria-hidden="true">!</span>
        <span class="update-banner__message update-banner__message--error">
          {$_('updater.banner.error')}
        </span>
        <button
          type="button"
          class="update-banner__btn update-banner__btn--ghost update-banner__dismiss"
          onclick={dismiss}
          aria-label={$_('updater.banner.dismiss_aria')}
        >
          ×
        </button>
      {/if}
    </div>
  </div>
{/if}

<style>
  .update-banner {
    width: 100%;
    padding: var(--spacing-2, 0.5rem) var(--spacing-6, 1.5rem);
    background: color-mix(in srgb, var(--accent, #6366f1) 12%, var(--bg-surface, #fff));
    border-bottom: 1px solid color-mix(in srgb, var(--accent, #6366f1) 30%, transparent);
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    z-index: 900;
  }

  .update-banner--error {
    background: color-mix(in srgb, var(--color-warning, #ed6c02) 8%, var(--bg-surface, #fff));
    border-bottom-color: color-mix(
      in srgb,
      var(--color-warning, #ed6c02) 30%,
      transparent
    );
  }

  .update-banner__content {
    display: flex;
    align-items: center;
    gap: var(--spacing-3, 0.75rem);
    flex-wrap: wrap;
    max-width: 1200px;
    margin: 0 auto;
  }

  .update-banner__icon {
    color: var(--accent, #6366f1);
    font-size: 1rem;
    flex-shrink: 0;
  }

  .update-banner--error .update-banner__icon {
    color: var(--color-warning, #ed6c02);
  }

  .update-banner__message {
    flex: 1;
    color: var(--text-primary, #111);
    display: flex;
    align-items: center;
    gap: var(--spacing-2, 0.5rem);
    flex-wrap: wrap;
  }

  .update-banner__message--error {
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

  .update-banner__actions {
    display: flex;
    gap: var(--spacing-2, 0.5rem);
    flex-shrink: 0;
  }

  .update-banner__btn {
    padding: 4px 12px;
    border-radius: 4px;
    border: 1px solid transparent;
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    font-weight: 500;
    cursor: pointer;
    transition: opacity 120ms ease, background-color 120ms ease;
    line-height: 1.5;
  }

  .update-banner__btn--primary {
    background: var(--accent, #6366f1);
    border-color: var(--accent, #6366f1);
    color: #fff;
  }

  .update-banner__btn--primary:hover {
    opacity: 0.9;
  }

  .update-banner__btn--ghost {
    background: transparent;
    border-color: var(--border-subtle, #d1d5db);
    color: var(--text-secondary, #555);
  }

  .update-banner__btn--ghost:hover {
    background: var(--surface-hover, #f9fafb);
    color: var(--text-primary, #111);
  }

  .update-banner__dismiss {
    margin-left: auto;
    padding: 2px 8px;
    font-size: 1rem;
    line-height: 1;
  }

  /* Progress bar */
  .update-banner__progress-wrap {
    flex: 1;
    min-width: 120px;
    max-width: 240px;
    height: 6px;
    background: var(--border-subtle, #e5e7eb);
    border-radius: 3px;
    overflow: hidden;
  }

  .update-banner__progress-bar {
    height: 100%;
    background: var(--accent, #6366f1);
    border-radius: 3px;
    transition: width 200ms ease;
  }

  @keyframes indeterminate {
    0% {
      transform: translateX(-100%);
    }
    100% {
      transform: translateX(200%);
    }
  }

  .update-banner__progress-bar--indeterminate {
    width: 40% !important;
    animation: indeterminate 1.2s ease infinite;
  }

  /* INV-14: prefers-reduced-motion — stop indeterminate animation */
  @media (prefers-reduced-motion: reduce) {
    .update-banner__progress-bar--indeterminate {
      animation: none;
      width: 100% !important;
      opacity: 0.5;
    }

    .update-banner__btn,
    .update-banner__progress-bar {
      transition: none;
    }
  }
</style>
