<!--
  Button — premium primary/secondary/ghost.
  Adapted from 03_Hybrid_Design_System/01-product-ui.tsx Aether Mesh.
  Sacred lime CTA invariant (only one per screen).
-->

<script lang="ts">
  interface Props {
    variant?: 'primary' | 'secondary' | 'ghost' | 'sigil' | 'danger';
    size?: 'sm' | 'md' | 'lg';
    disabled?: boolean;
    loading?: boolean;
    type?: 'button' | 'submit' | 'reset';
    onclick?: (e: MouseEvent) => void;
    children?: import('svelte').Snippet;
    iconStart?: import('svelte').Snippet;
    iconEnd?: import('svelte').Snippet;
    'aria-label'?: string;
  }

  let {
    variant = 'primary',
    size = 'md',
    disabled = false,
    loading = false,
    type = 'button',
    onclick,
    children,
    iconStart,
    iconEnd,
    'aria-label': ariaLabel
  }: Props = $props();
</script>

<button
  {type}
  class="btn btn-{variant} btn-{size}"
  class:loading
  disabled={disabled || loading}
  aria-busy={loading}
  aria-label={ariaLabel}
  onclick={(e) => onclick?.(e)}
>
  {#if iconStart}
    <span class="icon icon-start">{@render iconStart()}</span>
  {/if}
  <span class="label">
    {#if children}{@render children()}{/if}
  </span>
  {#if iconEnd}
    <span class="icon icon-end">{@render iconEnd()}</span>
  {/if}
  {#if loading}
    <span class="spinner" aria-hidden="true"></span>
  {/if}
</button>

<style>
  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--spacing-2);
    border: 1px solid transparent;
    border-radius: var(--border-radius-lg);
    font-family: var(--font-sans);
    font-weight: 500;
    line-height: 1;
    cursor: pointer;
    transition:
      transform var(--motion-fast) var(--easing-spring),
      background var(--motion-fast) var(--easing-smooth),
      border-color var(--motion-fast) var(--easing-smooth),
      box-shadow var(--motion-fast) var(--easing-smooth);
    user-select: none;
    position: relative;
    white-space: nowrap;
  }

  .btn:disabled {
    opacity: 0.55;
    cursor: not-allowed;
    transform: none !important;
  }

  .btn:not(:disabled):active {
    transform: translateY(1px);
  }

  .btn-sm {
    height: 32px;
    padding: 0 var(--spacing-3);
    font-size: var(--typography-fontSize-ui-sm);
  }
  .btn-md {
    height: 40px;
    padding: 0 var(--spacing-4);
    font-size: var(--typography-fontSize-ui-body);
  }
  .btn-lg {
    height: 48px;
    padding: 0 var(--spacing-6);
    font-size: var(--typography-fontSize-ui-body);
  }

  .btn-primary {
    background: var(--accent);
    color: #fff;
    border-color: var(--accent);
  }
  .btn-primary:not(:disabled):hover {
    background: color-mix(in srgb, var(--accent) 88%, white);
    box-shadow: var(--shadow-glow);
    transform: translateY(-1px);
  }

  .btn-secondary {
    background: var(--bg-surface);
    color: var(--text-primary);
    border-color: var(--border-subtle);
  }
  .btn-secondary:not(:disabled):hover {
    border-color: var(--accent);
    color: var(--accent);
  }

  .btn-ghost {
    background: transparent;
    color: var(--text-secondary);
    border-color: transparent;
  }
  .btn-ghost:not(:disabled):hover {
    color: var(--text-primary);
    background: color-mix(in srgb, var(--bg-surface) 70%, transparent);
  }

  /* Sacred lime — only one per screen, primary CTA. */
  .btn-sigil {
    background: var(--accent-sigil);
    color: #0a0a0a;
    border-color: var(--accent-sigil);
    font-weight: 600;
  }
  .btn-sigil:not(:disabled):hover {
    box-shadow: 0 0 24px color-mix(in srgb, var(--accent-sigil) 50%, transparent);
    transform: translateY(-1px);
  }

  .btn-danger {
    background: var(--color-danger);
    color: #fff;
    border-color: var(--color-danger);
  }
  .btn-danger:not(:disabled):hover {
    background: color-mix(in srgb, var(--color-danger) 88%, white);
  }

  .icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .spinner {
    width: 14px;
    height: 14px;
    margin-left: var(--spacing-2);
    border: 2px solid currentColor;
    border-right-color: transparent;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }

  .loading .label {
    opacity: 0.7;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
