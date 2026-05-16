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

  import { onMount, onDestroy } from 'svelte';
  import { listen, type UnlistenFn } from '@tauri-apps/api/event';
  import { ipc, type HandshakeResult } from '$ipc/client';

  let result = $state<HandshakeResult | null>(null);
  let unlisten: UnlistenFn | null = null;

  onMount(async () => {
    // Сначала event listener — handshake может прилететь именно сейчас.
    unlisten = await listen<HandshakeResult>(
      'sidecar://handshake_complete',
      ({ payload }) => {
        result = payload;
      },
    );

    // Затем pull текущего state — handshake мог завершиться до того как мы
    // успели подписаться. IPC возвращает null если ещё не выполнен.
    try {
      const status = await ipc.getHandshakeStatus();
      if (status !== null) {
        result = status;
      }
    } catch (e) {
      // Не критично — handshake позже всё равно прилетит через event.
      console.warn('[HandshakeModal] get_handshake_status failed:', e);
    }
  });

  onDestroy(() => {
    if (unlisten) unlisten();
  });

  function reload() {
    window.location.reload();
  }

  // Показываем только когда есть результат И он incompatible.
  // result === null (handshake ещё не дошёл) — не показываем (UI работает
  // как обычно, дожидаясь handshake; если sidecar медленный это нормально).
  const incompatible = $derived(result !== null && !result.compatible);
</script>

{#if incompatible && result}
  <div
    class="handshake-modal-backdrop"
    role="dialog"
    aria-modal="true"
    aria-labelledby="handshake-modal-title"
  >
    <div class="handshake-modal">
      <h2 id="handshake-modal-title">Несовместимая версия Aurora Launch</h2>
      <p class="reason">
        {result.reason ?? 'Sidecar (Python) не подходит к текущему shell (Rust).'}
      </p>
      {#if result.advice}
        <p class="advice">{result.advice}</p>
      {/if}
      <p class="warning">
        Продолжать работу <strong>небезопасно</strong> — данные проектов могут
        быть повреждены.
      </p>
      <div class="actions">
        <button class="primary" type="button" onclick={reload}>
          Перезапустить приложение
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .handshake-modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
  }

  .handshake-modal {
    background: var(--surface-base, #fff);
    color: var(--text-primary, #111);
    border-radius: 8px;
    padding: var(--spacing-6, 24px);
    max-width: 520px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
  }

  h2 {
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

  .warning {
    margin: 0 0 var(--spacing-4, 16px);
    padding: var(--spacing-2, 8px) var(--spacing-3, 12px);
    background: var(--state-warning-soft, #fff7e0);
    border-left: 3px solid var(--state-warning-base, #ed6c02);
    border-radius: 4px;
  }

  .actions {
    display: flex;
    justify-content: flex-end;
  }

  .actions button.primary {
    background: var(--accent-primary, #6366f1);
    color: #fff;
    border: none;
    padding: var(--spacing-3, 12px) var(--spacing-5, 20px);
    border-radius: 6px;
    font-size: var(--typography-fontSize-ui-md, 14px);
    cursor: pointer;
  }

  .actions button.primary:hover {
    opacity: 0.9;
  }
</style>
