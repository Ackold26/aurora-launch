<!--
  Badge — verdict chip, license tier, trust badge.
  Adapted from 02-client-deliverable.tsx + 03-bridge-signature.tsx.
-->

<script lang="ts">
  interface Props {
    variant?:
      | 'default'
      | 'success'
      | 'warning'
      | 'danger'
      | 'info'
      | 'sigil'
      | 'verdict-high'
      | 'verdict-medium'
      | 'verdict-low'
      | 'verdict-insufficient';
    size?: 'sm' | 'md';
    children?: import('svelte').Snippet;
  }

  let { variant = 'default', size = 'md', children }: Props = $props();
</script>

<span class="badge badge-{variant} badge-{size}" role="status">
  {#if children}{@render children()}{/if}
</span>

<style>
  .badge {
    display: inline-flex;
    align-items: center;
    gap: var(--spacing-1);
    padding: 0 var(--spacing-2);
    border: 1px solid transparent;
    border-radius: 999px;
    font-family: var(--font-sans);
    font-weight: 500;
    letter-spacing: 0.01em;
    line-height: 1;
    white-space: nowrap;
  }

  .badge-sm {
    height: 20px;
    font-size: var(--typography-fontSize-ui-xs);
  }
  .badge-md {
    height: 24px;
    font-size: var(--typography-fontSize-ui-sm);
  }

  .badge-default {
    background: color-mix(in srgb, var(--text-secondary) 10%, transparent);
    color: var(--text-secondary);
    border-color: var(--border-subtle);
  }

  .badge-success,
  .badge-verdict-high {
    background: color-mix(in srgb, var(--color-success) 14%, transparent);
    color: var(--color-success);
    border-color: color-mix(in srgb, var(--color-success) 40%, transparent);
  }

  .badge-warning,
  .badge-verdict-medium {
    background: color-mix(in srgb, var(--color-warning) 14%, transparent);
    color: var(--color-warning);
    border-color: color-mix(in srgb, var(--color-warning) 40%, transparent);
  }

  .badge-danger,
  .badge-verdict-insufficient {
    background: color-mix(in srgb, var(--color-danger) 14%, transparent);
    color: var(--color-danger);
    border-color: color-mix(in srgb, var(--color-danger) 40%, transparent);
  }

  .badge-info,
  .badge-verdict-low {
    background: color-mix(in srgb, var(--color-info) 14%, transparent);
    color: var(--color-info);
    border-color: color-mix(in srgb, var(--color-info) 40%, transparent);
  }

  .badge-sigil {
    background: color-mix(in srgb, var(--accent-sigil) 18%, transparent);
    color: var(--accent-sigil);
    border-color: color-mix(in srgb, var(--accent-sigil) 60%, transparent);
  }
</style>
