<script lang="ts">
  // Этап 2.8 ROADMAP_POST_V0_1_0.md:
  //
  // Slot-blocking modal — показывается когда Rust shell несовместим с
  // Python sidecar (negotiate-handshake вернул compatible=false). До
  // pилого этого был только log::warn в Rust — UI ничего не знал и
  // продолжал работать с кривым sidecar.
  //
  // Подписывается на `sidecar://handshake_complete` event + проверяет
  // `get_handshake_status` IPC при mount (ловит случай если event улетел
  // раньше mount layout'a).
  //
  // Refactored on NotificationBanner (BTA-3 Phase 1.A): backdrop / focus-trap /
  // ARIA delegated to base component. level='error' — no dismiss, force restart.

  import { onMount, onDestroy } from 'svelte';
  import { _ } from 'svelte-i18n';
  import { listen, type UnlistenFn } from '@tauri-apps/api/event';
  import { ipc, type HandshakeResult } from '$ipc/client';
  import NotificationBanner from './NotificationBanner.svelte';

  let result = $state<HandshakeResult | null>(null);
  let unlisten: UnlistenFn | null = null;

  onMount(async () => {
    unlisten = await listen<HandshakeResult>(
      'sidecar://handshake_complete',
      ({ payload }) => {
        result = payload;
      },
    );

    try {
      const status = await ipc.getHandshakeStatus();
      if (status !== null) {
        result = status;
      }
    } catch (e) {
      console.warn('[HandshakeModal] get_handshake_status failed:', e);
    }
  });

  onDestroy(() => {
    if (unlisten) unlisten();
  });

  // Audit H-1 (этап 2.10): relaunch() убивает оба процесса и стартует заново.
  // window.location.reload() оставляет живой incompatible sidecar — fallback только.
  async function reload() {
    try {
      const { relaunch } = await import('@tauri-apps/plugin-process');
      await relaunch();
    } catch (e) {
      console.warn('[HandshakeModal] relaunch unavailable, fallback to reload:', e);
      window.location.reload();
    }
  }

  const incompatible = $derived(result !== null && !result.compatible);
</script>

<!-- level='error': blocking modal, focus-trap on, no onDismiss (force restart) -->
<NotificationBanner
  open={incompatible}
  level="error"
  titleId="handshake-modal-title"
  autoFocusSelector=".nb-btn--primary"
>
  {#snippet children()}
    <h2 id="handshake-modal-title" class="modal-title">{$_('handshake_modal.title')}</h2>
    <p class="reason">
      {result?.reason ?? $_('handshake_modal.default_reason')}
    </p>
    {#if result?.advice}
      <p class="advice">{result.advice}</p>
    {/if}
    <p class="warning-box">{$_('handshake_modal.warning')}</p>
  {/snippet}

  {#snippet actions()}
    <!-- H-7 (audit 4.5 / Phase 1.A): canonical accent token via nb-btn--primary. -->
    <button class="nb-btn nb-btn--primary" type="button" onclick={reload}>
      {$_('handshake_modal.button_restart')}
    </button>
  {/snippet}
</NotificationBanner>

<style>
  .modal-title {
    margin: 0 0 var(--spacing-3, 12px);
    color: var(--state-danger-base, #c62828);
  }

  .reason {
    margin: 0 0 var(--spacing-2, 8px);
    font-weight: 600;
  }

  .advice {
    margin: 0 0 var(--spacing-3, 12px);
    color: var(--text-muted, #555);
  }

  .warning-box {
    margin: 0 0 var(--spacing-4, 16px);
    padding: var(--spacing-2, 8px) var(--spacing-3, 12px);
    background: var(--state-warning-soft, #fff7e0);
    border-left: 3px solid var(--state-warning-base, #ed6c02);
    border-radius: 4px;
  }
</style>
