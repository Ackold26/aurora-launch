<!--
  NotificationBanner — BTA-3 (Phase 1.A): shared base for all notification
  banner / modal surfaces in Aurora Launch.

  Consolidates duplicated boilerplate from:
    HandshakeIncompatibleModal → level='error'   (z-index 9999, alertdialog, focus-trap)
    UpdateAvailableBanner      → level='info'    (z-index 900, status, no trap)
    RefreshAvailableBanner     → level='prompt'/'info' (z-index 1000/900)

  INV-14: prefers-reduced-motion respected via fadeIn from $lib/services/motion.
  All ARIA is level-driven; consumers pass children/actions snippets for content.
-->

<script lang="ts">
  import type { Snippet } from 'svelte';
  import { fadeIn } from '$lib/services/motion';

  // ── z-index constants ────────────────────────────────────────────────────
  const Z_BLOCKING_MODAL = 9999;
  const Z_PROMPT_MODAL = 1000;
  const Z_TOP_BANNER = 900;

  // ── Props ────────────────────────────────────────────────────────────────
  interface Props {
    /** Visibility — controlled by parent. */
    open: boolean;
    /**
     * level determines UX tone + ARIA semantics + z-index:
     *   'error'   — blocking modal (z-index 9999, role=alertdialog, focus trap, no dismiss)
     *   'warning' — non-blocking banner with emphasis (z-index 900, role=status, dismiss)
     *   'info'    — info banner (z-index 900, role=status, dismiss)
     *   'prompt'  — opt-in dialog (z-index 1000, role=dialog, focus trap, dismiss)
     */
    level: 'error' | 'warning' | 'info' | 'prompt';
    /** Optional aria-labelledby target id for accessible title. */
    titleId?: string;
    /** Children snippet — primary content (title, body). */
    children?: Snippet;
    /** Actions snippet — buttons row (Install / Dismiss / etc). */
    actions?: Snippet;
    /**
     * Called on dismiss (Escape key or dismiss-button click).
     * When undefined: no dismiss button is rendered (force mode for 'error').
     */
    onDismiss?: () => void;
    /** Auto-focus CSS selector inside banner on mount. Defaults to first focusable. */
    autoFocusSelector?: string;
  }

  let {
    open,
    level,
    titleId,
    children,
    actions,
    onDismiss,
    autoFocusSelector,
  }: Props = $props();

  // ── Derived ARIA / layout properties ────────────────────────────────────

  const isModal = $derived(level === 'error' || level === 'prompt');
  const isBanner = $derived(level === 'warning' || level === 'info');
  const hasTrap = $derived(isModal);

  const ariaRole = $derived(
    level === 'error' ? 'alertdialog' : level === 'prompt' ? 'dialog' : 'status',
  );

  const ariaLive = $derived(
    level === 'error' ? 'assertive' : 'polite',
  );

  const zIndex = $derived(
    level === 'error'
      ? Z_BLOCKING_MODAL
      : level === 'prompt'
        ? Z_PROMPT_MODAL
        : Z_TOP_BANNER,
  );

  // ── Focus trap ───────────────────────────────────────────────────────────

  let bannerEl: HTMLElement | undefined = $state();

  /** Return all keyboard-focusable children of el. */
  function focusable(el: HTMLElement): HTMLElement[] {
    return Array.from(
      el.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ),
    );
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape' && onDismiss) {
      event.preventDefault();
      onDismiss();
      return;
    }

    if (event.key === 'Tab' && hasTrap && bannerEl) {
      const items = focusable(bannerEl);
      if (items.length === 0) {
        event.preventDefault();
        return;
      }
      const first: HTMLElement = items[0]!;
      const last: HTMLElement = items[items.length - 1]!;
      if (event.shiftKey) {
        if (document.activeElement === first) {
          event.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    }
  }

  // ── Auto-focus on open ───────────────────────────────────────────────────

  $effect(() => {
    if (open && bannerEl) {
      // Defer one tick so the DOM is fully rendered before focusing.
      requestAnimationFrame(() => {
        if (!bannerEl) return;
        if (autoFocusSelector) {
          const target = bannerEl.querySelector<HTMLElement>(autoFocusSelector);
          if (target) { target.focus(); return; }
        }
        // Fall back to first focusable item.
        const items = focusable(bannerEl);
        const firstItem = items[0];
        if (firstItem) firstItem.focus();
      });
    }
  });
</script>

{#if open}
  {#if isModal}
    <!-- Modal overlay (error / prompt) -->
    <div
      class="nb-backdrop nb-backdrop--{level}"
      style:z-index={zIndex}
      role="presentation"
      transition:fadeIn
    >
      <div
        class="nb-modal nb-modal--{level}"
        role={ariaRole}
        aria-modal={isModal ? 'true' : undefined}
        aria-labelledby={titleId}
        aria-live={ariaLive}
        bind:this={bannerEl}
        onkeydown={handleKeydown}
        tabindex="-1"
      >
        {@render children?.()}
        {#if actions}
          <div class="nb-actions">
            {@render actions()}
          </div>
        {/if}
        {#if onDismiss}
          <button
            class="nb-dismiss nb-dismiss--modal"
            type="button"
            onclick={onDismiss}
            aria-label="Закрыть"
          >×</button>
        {/if}
      </div>
    </div>
  {:else}
    <!-- Inline top banner (warning / info) -->
    <div
      class="nb-banner nb-banner--{level}"
      style:z-index={zIndex}
      role={ariaRole}
      aria-live={ariaLive}
      aria-labelledby={titleId}
      bind:this={bannerEl}
      onkeydown={handleKeydown}
      transition:fadeIn
    >
      <div class="nb-banner__content">
        {@render children?.()}
        {#if actions}
          <div class="nb-actions nb-actions--inline">
            {@render actions()}
          </div>
        {/if}
        {#if onDismiss}
          <button
            class="nb-dismiss nb-dismiss--banner"
            type="button"
            onclick={onDismiss}
            aria-label="Закрыть"
          >×</button>
        {/if}
      </div>
    </div>
  {/if}
{/if}

<style>
  /* ── Backdrop (modal levels) ──────────────────────────────────────────── */
  .nb-backdrop {
    position: fixed;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.55);
  }

  .nb-backdrop--error {
    background: rgba(0, 0, 0, 0.7);
  }

  .nb-backdrop--prompt {
    background: rgba(0, 0, 0, 0.4);
  }

  /* ── Modal card ───────────────────────────────────────────────────────── */
  .nb-modal {
    position: relative;
    background: var(--surface-base, #fff);
    color: var(--text-primary, #111);
    border-radius: 8px;
    padding: var(--spacing-6, 24px);
    max-width: 540px;
    width: calc(100vw - 2rem);
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
    outline: none;
  }

  .nb-modal--error {
    border-top: 3px solid var(--state-danger-base, #c62828);
  }

  .nb-modal--prompt {
    border-top: 3px solid var(--color-ui-accent-primary, #2E5BFF);
  }

  /* ── Banner strip (info / warning) ───────────────────────────────────── */
  .nb-banner {
    position: sticky;
    top: 0;
    width: 100%;
    padding: var(--spacing-2, 0.5rem) var(--spacing-6, 1.5rem);
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    border-bottom: 1px solid transparent;
  }

  .nb-banner--info {
    background: color-mix(in srgb, var(--color-ui-accent-primary, #2E5BFF) 12%, var(--bg-surface, #fff));
    border-bottom-color: color-mix(in srgb, var(--color-ui-accent-primary, #2E5BFF) 30%, transparent);
  }

  .nb-banner--warning {
    background: color-mix(in srgb, var(--state-warning-base, #ed6c02) 8%, var(--bg-surface, #fff));
    border-bottom-color: color-mix(in srgb, var(--state-warning-base, #ed6c02) 30%, transparent);
  }

  .nb-banner__content {
    display: flex;
    align-items: center;
    gap: var(--spacing-3, 0.75rem);
    flex-wrap: wrap;
    max-width: 1200px;
    margin: 0 auto;
  }

  /* ── Actions row ──────────────────────────────────────────────────────── */
  .nb-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--spacing-2, 0.5rem);
    margin-top: var(--spacing-4, 1rem);
  }

  .nb-actions--inline {
    margin-top: 0;
    flex-shrink: 0;
  }

  /* ── Dismiss button ───────────────────────────────────────────────────── */
  .nb-dismiss {
    background: transparent;
    border: none;
    cursor: pointer;
    color: var(--text-muted, #9ca3af);
    line-height: 1;
    padding: 2px 6px;
    border-radius: 4px;
  }

  .nb-dismiss:hover {
    color: var(--text-primary, #111);
    background: var(--surface-hover, #f3f4f6);
  }

  .nb-dismiss--modal {
    position: absolute;
    top: var(--spacing-3, 12px);
    right: var(--spacing-3, 12px);
    font-size: 1.25rem;
  }

  .nb-dismiss--banner {
    margin-left: auto;
    font-size: 1rem;
  }

  /* ── Shared button tokens for actions snippets ───────────────────────── */
  /* Buttons rendered inside .nb-actions are children's DOM but inside this
   * component's wrapper element, so :global(.nb-actions .nb-btn) works. */
  :global(.nb-actions .nb-btn) {
    padding: 4px 12px;
    border-radius: 4px;
    border: 1px solid transparent;
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    font-weight: 500;
    cursor: pointer;
    transition: opacity 120ms ease, background-color 120ms ease;
    line-height: 1.5;
  }

  :global(.nb-actions .nb-btn:disabled) {
    opacity: 0.55;
    cursor: not-allowed;
  }

  :global(.nb-actions .nb-btn--primary) {
    background: var(--color-ui-accent-primary, #2E5BFF);
    border-color: var(--color-ui-accent-primary, #2E5BFF);
    color: #fff;
  }

  :global(.nb-actions .nb-btn--primary:hover:not(:disabled)) {
    opacity: 0.9;
  }

  :global(.nb-actions .nb-btn--ghost) {
    background: transparent;
    border-color: var(--border-subtle, #d1d5db);
    color: var(--text-secondary, #555);
  }

  :global(.nb-actions .nb-btn--ghost:hover) {
    background: var(--surface-hover, #f9fafb);
    color: var(--text-primary, #111);
  }

  :global(.nb-actions .nb-btn--muted) {
    background: transparent;
    border-color: transparent;
    color: var(--text-muted, #9ca3af);
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
  }

  :global(.nb-actions .nb-btn--muted:hover) {
    color: var(--text-secondary, #555);
    text-decoration: underline;
  }

  /* ── INV-14: prefers-reduced-motion ──────────────────────────────────── */
  @media (prefers-reduced-motion: reduce) {
    .nb-banner,
    .nb-modal,
    .nb-backdrop {
      transition: none;
      animation: none;
    }

    :global(.nb-actions .nb-btn) {
      transition: none;
    }
  }
</style>
