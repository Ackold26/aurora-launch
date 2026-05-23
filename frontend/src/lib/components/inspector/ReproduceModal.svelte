<!--
  ReproduceModal — Sprint 3 M-09 (Inspector → "Воспроизвести в Python").

  Sprint 8 D2 (#21): refactored на NotificationBanner level="prompt" — focus-trap,
  ESC, ARIA role="dialog", backdrop, auto-focus, focus restoration на opener
  delegated к base component (same pattern as DrillDownModal). Removed ~50 LOC
  duplicated focus/backdrop/keydown plumbing.

  Owns только domain content: title, intro/preview text, copy/download actions,
  generated Python script display.

  Note: hardcoded RU microcopy (title, intro template, buttons, toasts) deferred
  к Sprint Buffer #48 (i18n extraction, separate scope from refactor).
-->

<script lang="ts">
  import Skeleton from '$lib/components/Skeleton.svelte';
  import NotificationBanner from '$lib/components/NotificationBanner.svelte';
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

<NotificationBanner
  level="prompt"
  {open}
  onDismiss={onclose}
  titleId="reproduce-modal-title"
>
  {#snippet children()}
    <h2 id="reproduce-modal-title" class="reproduce-modal-title">
      🐍 Воспроизвести прогноз в Python
    </h2>
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
  {/snippet}
</NotificationBanner>

<style>
  /* Sprint 8 D2 (#21): backdrop/modal/header/close styles removed — provided by
     NotificationBanner level="prompt". Only domain content styles remain. */

  .reproduce-modal-title {
    margin: 0 0 var(--spacing-3, 0.75rem);
    font-family: var(--font-display, var(--font-sans, sans-serif));
    font-size: 1.5rem;
  }
  .reproduce-modal-intro {
    color: var(--text-secondary, #4A4D57);
    line-height: 1.5;
    margin: 0 0 var(--spacing-3, 0.75rem);
  }
  .reproduce-preview-badge {
    color: var(--color-warning, #B45309);
    margin-right: 0.25rem;
  }
  .reproduce-actions {
    display: flex;
    gap: var(--spacing-2, 0.5rem);
    margin-bottom: var(--spacing-3, 0.75rem);
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
