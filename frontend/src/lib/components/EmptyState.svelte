<!--
  EmptyState — Reusable empty state panel with illustration, caring copy, and action buttons.

  Phase Premium P-07: every list/form that can be empty shows this component
  instead of raw "nothing here" text.

  Props:
    icon          — emoji string or Svelte snippet for SVG illustration
    title         — forward-looking headline ("Здесь будет…")
    body          — explains why it's empty + what will happen
    primaryAction  — { label, onClick } main CTA
    secondaryAction — { label, onClick } optional secondary action
    compact        — reduced padding / smaller font for inline contexts

  ARIA: <section role="status" aria-live="polite"> so screen readers announce
        appearance of empty state without requiring user focus.

  INV-14: all transitions respect prefers-reduced-motion via CSS media query.
-->

<script lang="ts">
  import { fadeIn } from '$lib/services/motion';

  interface Action {
    label: string;
    onClick: () => void;
  }

  interface Props {
    icon?: string;
    title: string;
    body: string;
    primaryAction?: Action;
    secondaryAction?: Action;
    compact?: boolean;
    children?: import('svelte').Snippet;
  }

  let {
    icon,
    title,
    body,
    primaryAction,
    secondaryAction,
    compact = false,
    children,
  }: Props = $props();
</script>

<!-- PA-A01 fix: motion service wired — fadeIn used here (was zero usage) -->
<section
  in:fadeIn={{ duration: 220 }}
  class="empty-state"
  class:compact
  role="status"
  aria-live="polite"
  aria-label={title}
>
  {#if icon}
    <span class="empty-icon" aria-hidden="true">{icon}</span>
  {/if}

  {#if children}
    <div class="empty-illustration" aria-hidden="true">
      {@render children()}
    </div>
  {/if}

  <h3 class="empty-title">{title}</h3>
  <p class="empty-body">{body}</p>

  {#if primaryAction || secondaryAction}
    <div class="empty-actions">
      {#if primaryAction}
        <button
          type="button"
          class="btn btn-primary"
          onclick={primaryAction.onClick}
        >
          {primaryAction.label}
        </button>
      {/if}
      {#if secondaryAction}
        <button
          type="button"
          class="btn btn-secondary"
          onclick={secondaryAction.onClick}
        >
          {secondaryAction.label}
        </button>
      {/if}
    </div>
  {/if}
</section>

<style>
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: var(--spacing-3, 0.75rem);
    padding: var(--spacing-8, 2rem) var(--spacing-6, 1.5rem);
    background: var(--surface-subtle, color-mix(in srgb, var(--bg-surface, #fafafa) 60%, transparent));
    border-radius: var(--border-radius-lg, 12px);
    border: 1px dashed var(--border-subtle, #e5e7eb);
  }

  .empty-state.compact {
    padding: var(--spacing-4, 1rem) var(--spacing-4, 1rem);
    gap: var(--spacing-2, 0.5rem);
  }

  .empty-icon {
    font-size: 2.5rem;
    line-height: 1;
    /* Subtle entrance animation — respects prefers-reduced-motion */
    animation: icon-in 300ms var(--easing-smooth, ease-out) both;
  }

  .empty-state.compact .empty-icon {
    font-size: 1.75rem;
  }

  .empty-illustration {
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted, #9ca3af);
  }

  .empty-title {
    margin: 0;
    font-family: var(--font-display, var(--font-sans, sans-serif));
    font-size: var(--typography-fontSize-display-xs, 1.125rem);
    font-weight: 600;
    color: var(--text-primary, #111827);
    line-height: 1.3;
  }

  .empty-state.compact .empty-title {
    font-size: var(--typography-fontSize-ui-body, 0.9375rem);
  }

  .empty-body {
    margin: 0;
    color: var(--text-secondary, #6b7280);
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    line-height: 1.6;
    max-width: 38ch;
  }

  .empty-state.compact .empty-body {
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
    max-width: 46ch;
  }

  .empty-actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--spacing-2, 0.5rem);
    justify-content: center;
    margin-top: var(--spacing-1, 0.25rem);
  }

  /* Inline button styles — avoid importing Button.svelte to keep component self-contained */
  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--spacing-2, 0.5rem);
    border: 1px solid transparent;
    border-radius: var(--border-radius-lg, 8px);
    font-family: var(--font-sans, sans-serif);
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    font-weight: 500;
    line-height: 1;
    height: 36px;
    padding: 0 var(--spacing-4, 1rem);
    cursor: pointer;
    user-select: none;
    transition:
      transform var(--motion-fast, 120ms) var(--easing-spring, ease),
      background var(--motion-fast, 120ms) var(--easing-smooth, ease),
      border-color var(--motion-fast, 120ms) var(--easing-smooth, ease),
      box-shadow var(--motion-fast, 120ms) var(--easing-smooth, ease);
  }

  .btn-primary {
    background: var(--accent, #2563eb);
    color: #fff;
    border-color: var(--accent, #2563eb);
  }

  .btn-primary:hover {
    background: color-mix(in srgb, var(--accent, #2563eb) 88%, white);
    transform: translateY(-1px);
    box-shadow: var(--shadow-glow, 0 4px 14px color-mix(in srgb, var(--accent, #2563eb) 30%, transparent));
  }

  .btn-primary:active {
    transform: translateY(1px);
  }

  .btn-secondary {
    background: var(--bg-surface, white);
    color: var(--text-primary, #111827);
    border-color: var(--border-subtle, #e5e7eb);
  }

  .btn-secondary:hover {
    border-color: var(--accent, #2563eb);
    color: var(--accent, #2563eb);
  }

  /* INV-14: kill all motion when reduced-motion requested */
  @media (prefers-reduced-motion: reduce) {
    .btn {
      transition: none;
    }
    .empty-icon {
      animation: none;
    }
  }

  @keyframes icon-in {
    from {
      opacity: 0;
      transform: scale(0.8);
    }
    to {
      opacity: 1;
      transform: scale(1);
    }
  }
</style>
