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
  import { _ } from 'svelte-i18n';
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
        title: $_('inspector.reproduce.toast.copy_success.title'),
        body: $_('inspector.reproduce.toast.copy_success.body', { values: { count: script.length } }),
      });
    } catch (e) {
      pushToast({
        level: 'danger',
        title: $_('inspector.reproduce.toast.copy_error.title'),
        body: e instanceof Error ? e.message : String(e),
      });
    }
  }
</script>

<!--
  autoFocusSelector targets close-X button — safe default during loading state
  when Copy button is disabled и Download <a> has empty data URI (would
  download empty file if Enter pressed on auto-focused link). Sprint 8 audit
  hotfix B1 — restores old v0.2.1 behavior где `closeButtonEl.focus()`.
-->
<NotificationBanner
  level="prompt"
  {open}
  onDismiss={onclose}
  titleId="reproduce-modal-title"
  autoFocusSelector=".nb-dismiss--modal"
>
  {#snippet children()}
    <h2 id="reproduce-modal-title" class="reproduce-modal-title">
      {$_('inspector.reproduce.title')}
    </h2>
    <p class="reproduce-modal-intro">
      {$_('inspector.reproduce.intro_save_prefix')}<code>{filename}</code>{$_('inspector.reproduce.intro_save_suffix')}
      {$_('inspector.reproduce.intro_run_prefix')}<code>python {filename}</code>{$_('inspector.reproduce.intro_run_suffix')}
      {#if isPreview}
        <strong class="reproduce-preview-badge">{$_('inspector.reproduce.preview_badge')}</strong>
        {$_('inspector.reproduce.preview_explanation')}
      {:else}
        {$_('inspector.reproduce.bit_equal')}
      {/if}
    </p>
    <div class="reproduce-actions">
      <button
        type="button"
        class="reproduce-action-btn primary"
        onclick={copyScript}
        disabled={loading || !script}
      >
        {$_('inspector.reproduce.copy_button')}
      </button>
      <a
        class="reproduce-action-btn secondary"
        href={`data:text/x-python;charset=utf-8,${encodeURIComponent(script)}`}
        download={filename}
        role="button"
      >
        {$_('inspector.reproduce.download_button')}
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
        aria-label={$_('inspector.reproduce.code_aria')}
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
