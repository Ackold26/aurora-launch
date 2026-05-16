<!--
  Card — surface container с premium elevation.
  Adapted from 03_Hybrid_Design_System Aether Mesh card pattern.
-->

<script lang="ts">
  interface Props {
    title?: string;
    subtitle?: string;
    accent?: 'default' | 'success' | 'warning' | 'danger' | 'info';
    interactive?: boolean;
    /**
     * Heading level for the card title (default: 3).
     * Set to 2 when a page-level <h1> is present and the card is the
     * first content heading — avoids axe heading-order violation (A11Y-W03).
     */
    headingLevel?: 2 | 3 | 4;
    onclick?: (e: MouseEvent) => void;
    children?: import('svelte').Snippet;
    actions?: import('svelte').Snippet;
  }

  let {
    title,
    subtitle,
    accent = 'default',
    interactive = false,
    headingLevel = 3,
    onclick,
    children,
    actions
  }: Props = $props();
</script>

<!-- Audit H-07 (этап 4.5): svelte-check не понимает что `<button>` и
     `<article>` имеют implicit role. svelte-ignore directive безопаснее
     чем добавлять redundant role attribute. -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<svelte:element
  this={interactive ? 'button' : 'article'}
  class="card card-{accent}"
  class:interactive
  type={interactive ? 'button' : undefined}
  onclick={interactive ? (e: MouseEvent) => onclick?.(e) : undefined}
>
  {#if title || subtitle || actions}
    <header class="card-header">
      <div class="card-titles">
        {#if title}<svelte:element this={`h${headingLevel}`} class="card-title">{title}</svelte:element>{/if}
        {#if subtitle}<p class="card-subtitle">{subtitle}</p>{/if}
      </div>
      {#if actions}
        <div class="card-actions">{@render actions()}</div>
      {/if}
    </header>
  {/if}
  <div class="card-body">
    {#if children}{@render children()}{/if}
  </div>
</svelte:element>

<style>
  .card {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-3);
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-lg);
    padding: var(--spacing-4);
    box-shadow: var(--shadow-sm);
    transition:
      transform var(--motion-default) var(--easing-spring),
      box-shadow var(--motion-default) var(--easing-smooth),
      border-color var(--motion-default) var(--easing-smooth);
    text-align: left;
    color: inherit;
    font-family: inherit;
    width: 100%;
  }

  button.card {
    cursor: pointer;
  }

  .card.interactive:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
    border-color: color-mix(in srgb, var(--accent) 35%, var(--border-subtle));
  }

  .card.interactive:active {
    transform: translateY(0);
  }

  .card-success {
    border-left: 3px solid var(--color-success);
  }
  .card-warning {
    border-left: 3px solid var(--color-warning);
  }
  .card-danger {
    border-left: 3px solid var(--color-danger);
  }
  .card-info {
    border-left: 3px solid var(--color-info);
  }

  .card-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--spacing-3);
  }

  .card-titles {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1);
  }

  .card-title {
    font-size: var(--typography-fontSize-ui-h3);
    color: var(--text-primary);
    font-weight: 500;
  }

  .card-subtitle {
    color: var(--text-secondary);
    font-size: var(--typography-fontSize-ui-sm);
    margin: 0;
  }

  .card-body {
    color: var(--text-primary);
  }

  .card-actions {
    display: flex;
    gap: var(--spacing-2);
    flex-shrink: 0;
  }
</style>
