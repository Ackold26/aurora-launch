<!-- Toaster — non-blocking notifications. -->

<script lang="ts">
  import { fly } from 'svelte/transition';
  import { quintOut } from 'svelte/easing';

  import { toasts, dismissToast } from '$lib/stores/toast';
</script>

<div class="toaster" role="region" aria-label="Notifications" aria-live="polite">
  {#each $toasts as toast (toast.id)}
    <div
      class="toast toast-{toast.level}"
      role="status"
      transition:fly={{ y: 20, duration: 220, easing: quintOut }}
    >
      <div class="content">
        <strong class="title">{toast.title}</strong>
        {#if toast.body}<p class="body">{toast.body}</p>{/if}
      </div>
      <button
        type="button"
        class="dismiss"
        onclick={() => dismissToast(toast.id)}
        aria-label="Dismiss"
      >×</button>
    </div>
  {/each}
</div>

<style>
  .toaster {
    position: fixed;
    bottom: var(--spacing-6);
    right: var(--spacing-6);
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
    z-index: 1000;
    pointer-events: none;
    max-width: 360px;
  }

  .toast {
    pointer-events: auto;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-left: 3px solid var(--accent);
    border-radius: var(--border-radius-lg);
    padding: var(--spacing-3) var(--spacing-4);
    box-shadow: var(--shadow-md);
    display: flex;
    align-items: flex-start;
    gap: var(--spacing-3);
    color: var(--text-primary);
  }

  .toast-success {
    border-left-color: var(--color-success);
  }
  .toast-warning {
    border-left-color: var(--color-warning);
  }
  .toast-danger {
    border-left-color: var(--color-danger);
  }

  .content {
    flex: 1;
  }

  .title {
    display: block;
    font-weight: 500;
  }

  .body {
    color: var(--text-secondary);
    font-size: var(--typography-fontSize-ui-sm);
    margin: var(--spacing-1) 0 0 0;
  }

  .dismiss {
    background: transparent;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 20px;
    line-height: 1;
    padding: 0;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
  }
  .dismiss:hover {
    background: color-mix(in srgb, var(--text-muted) 18%, transparent);
    color: var(--text-primary);
  }
</style>
