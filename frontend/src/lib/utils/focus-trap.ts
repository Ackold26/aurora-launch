/**
 * Svelte 5 action for keyboard focus trap inside a modal/dialog.
 * Use: <div use:focusTrap>...</div>
 *
 * Behavior:
 *   - Tab from last focusable wraps to first
 *   - Shift+Tab from first wraps to last
 *   - No-op if container has no focusable children
 *
 * Q6 extraction from Sprint Buffer #34 — DRY consolidation
 * between NotificationBanner + CertExportModal.
 */
export function focusTrap(node: HTMLElement) {
  // Sprint 4 Batch 7 Q6-H1: `[role="button"]:not([aria-disabled="true"])`
  // replaces ineffective `:not([disabled])` filter — `disabled` attribute не
  // валиден на custom-role elements (e.g., `<span role="button">`);
  // `aria-disabled="true"` is the ARIA canonical signal для disabled
  // custom-role buttons. Keep `:not([disabled])` для legacy support где dev
  // actually set disabled attribute (no harm, just redundant).
  function focusable(): HTMLElement[] {
    return Array.from(
      node.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"]), [role="button"]:not([aria-disabled="true"]):not([disabled]), audio[controls], video[controls]',
      ),
    );
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key !== 'Tab') return;
    const items = focusable();
    if (items.length === 0) {
      e.preventDefault();
      return;
    }
    const first = items[0]!;
    const last = items[items.length - 1]!;
    if (e.shiftKey) {
      if (document.activeElement === first) {
        e.preventDefault();
        last.focus();
      }
    } else {
      if (document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }

  node.addEventListener('keydown', handleKeydown);

  return {
    destroy() {
      node.removeEventListener('keydown', handleKeydown);
    },
  };
}
