<script lang="ts">
  import Skeleton from '$lib/components/Skeleton.svelte';
  import { pushToast } from '$lib/stores/toast';

  interface Props {
    open: boolean;
    script: string;
    filename: string;
    loading: boolean;
    isPreview: boolean;
    onclose: () => void;
  }

  let { open, script, filename, loading, isPreview, onclose }: Props = $props();

  // H-5 (audit 4.5 / Phase 1.A): focus modal close button on open
  let closeButtonEl = $state<HTMLButtonElement | undefined>(undefined);
  $effect(() => {
    if (open && closeButtonEl) {
      requestAnimationFrame(() => closeButtonEl?.focus());
    }
  });

  async function copyScript() {
    try {
      await navigator.clipboard.writeText(script);
      pushToast({
        level: 'success',
        title: 'Скопировано',
        body: `${script.length} символов в буфере обмена`,
      });
    } catch (e) {
      pushToast({
        level: 'danger',
        title: 'Не удалось скопировать',
        body: e instanceof Error ? e.message : String(e),
      });
    }
  }
</script>

{#if open}
  <!-- 4.3 a11y: backdrop dismiss через event.target check -->
  <div
    class="reproduce-modal-backdrop"
    role="dialog"
    aria-modal="true"
    aria-labelledby="reproduce-modal-title"
    onclick={(e) => { if (e.target === e.currentTarget) onclose(); }}
    onkeydown={(e) => { if (e.key === 'Escape') onclose(); }}
    tabindex="-1"
  >
    <div class="reproduce-modal-content">
      <header class="reproduce-modal-header">
        <h2 id="reproduce-modal-title">🐍 Воспроизвести прогноз в Python</h2>
        <button
          type="button"
          class="reproduce-modal-close"
          bind:this={closeButtonEl}
          onclick={onclose}
          aria-label="Закрыть"
        >
          ✕
        </button>
      </header>
      <p class="reproduce-modal-intro">
        Сохраните этот скрипт как <code>{filename}</code> + .aurora bundle.
        Запустите <code>python {filename}</code>.
        {#if isPreview}
          <strong class="reproduce-preview-badge">⚠️ Превью v0.1.0:</strong>
          параметры запуска и план медиа пока приближённые — скорректируйте их вручную. Точное воспроизведение появится в следующем обновлении.
        {:else}
          Прогноз будет идентичным до бита.
        {/if}
      </p>
      <div class="reproduce-actions">
        <button
          type="button"
          class="reproduce-action-btn primary"
          onclick={copyScript}
          disabled={loading || !script}
        >
          📋 Скопировать в буфер
        </button>
        <a
          class="reproduce-action-btn secondary"
          href={`data:text/x-python;charset=utf-8,${encodeURIComponent(script)}`}
          download={filename}
          role="button"
        >
          💾 Скачать .py
        </a>
      </div>
      {#if loading}
        <Skeleton width="100%" height="320px" rounded />
      {:else}
        <!-- 4.3 a11y: tabindex=0 на <pre> INTENTIONAL для keyboard scroll
             через стрелки (для customer'ов с keyboard-only navigation).
             svelte-check считает <pre> non-interactive, но WCAG позволяет
             tabindex=0 для scrollable content (RegEx 2.1.1). -->
        <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
        <pre
          class="reproduce-code"
          tabindex="0"
          role="region"
          aria-label="Сгенерированный Python-скрипт"
        ><code>{script}</code></pre>
      {/if}
    </div>
  </div>
{/if}

<style>
  .reproduce-modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: var(--spacing-4, 1rem);
  }
  .reproduce-modal-content {
    background: var(--bg-surface, white);
    border-radius: 8px;
    max-width: 920px;
    width: 100%;
    max-height: 90vh;
    overflow-y: auto;
    padding: var(--spacing-6, 1.5rem);
    display: flex;
    flex-direction: column;
    gap: var(--spacing-3, 0.75rem);
  }
  .reproduce-modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .reproduce-modal-header h2 {
    margin: 0;
    font-family: var(--font-display, var(--font-sans, sans-serif));
    font-size: 1.5rem;
  }
  .reproduce-modal-close {
    background: transparent;
    border: none;
    font-size: 1.5rem;
    cursor: pointer;
    color: var(--text-muted, #6b7280);
    padding: 0;
    width: 32px;
    height: 32px;
  }
  .reproduce-modal-close:hover {
    color: var(--text-primary, #111827);
  }
  .reproduce-modal-intro {
    color: var(--text-secondary, #4A4D57);
    line-height: 1.5;
  }
  .reproduce-preview-badge {
    color: var(--color-warning, #B45309);
    margin-right: 0.25rem;
  }
  .reproduce-actions {
    display: flex;
    gap: var(--spacing-2, 0.5rem);
  }
  .reproduce-action-btn {
    padding: 6px 14px;
    border-radius: 6px;
    cursor: pointer;
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    border: 1px solid transparent;
  }
  .reproduce-action-btn.primary {
    background: var(--accent, #2563eb);
    color: white;
    border-color: var(--accent, #2563eb);
  }
  .reproduce-action-btn.secondary {
    background: transparent;
    color: var(--text-primary, #111827);
    border-color: var(--border-default, #d1d5db);
  }
  .reproduce-code {
    background: var(--bg-elevated, #F0F2F7);
    border: 1px solid var(--border-subtle, #e5e7eb);
    border-radius: 6px;
    padding: var(--spacing-3, 0.75rem);
    font-family: var(--font-mono, monospace);
    font-size: 0.85rem;
    line-height: 1.5;
    overflow-x: auto;
    margin: 0;
    max-height: 60vh;
    color: var(--text-primary, #111827);
  }
</style>
