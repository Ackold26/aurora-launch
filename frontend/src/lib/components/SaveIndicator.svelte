<!--
  SaveIndicator — save state feedback widget (Phase Premium P-08).

  Three states:
    saved   — green dot + "Сохранено N мин назад" (or auto/manual variant)
    saving  — amber pulsing dot + "Сохраняется…"
    unsaved — gray dot + "Не сохранено"

  ARIA: aria-live="polite" so screen readers announce state changes.
  INV-14: pulse animation disabled if prefers-reduced-motion is set.
  Uses --color-success / --color-warning / --color-muted convenience aliases.

  TODO: wire to wizard save state in Phase Premium P-02 follow-up.
-->

<script lang="ts">
  interface Props {
    /** Current save state */
    state: 'saved' | 'saving' | 'unsaved';
    /** ISO timestamp of last successful save, or null */
    lastSavedAt: string | null;
    /** 'auto' = "Сохранено автоматически", 'manual' = "Сохранено вручную" */
    mode?: 'auto' | 'manual';
  }

  let { state, lastSavedAt, mode = 'auto' }: Props = $props();

  function timeAgo(iso: string | null): string {
    if (!iso) return '';
    const t = new Date(iso).getTime();
    if (!Number.isFinite(t)) return '';
    const secs = Math.max(0, Math.floor((Date.now() - t) / 1000));
    if (secs < 60) return 'только что';
    if (secs < 3600) return `${Math.floor(secs / 60)} мин назад`;
    if (secs < 86400) return `${Math.floor(secs / 3600)} ч назад`;
    return `${Math.floor(secs / 86400)} дн назад`;
  }

  const savedLabel = $derived(
    mode === 'auto' ? 'Сохранено автоматически' : 'Сохранено вручную'
  );

  const label = $derived.by(() => {
    if (state === 'saving') return 'Сохраняется…';
    if (state === 'unsaved') return 'Не сохранено';
    // saved
    const when = timeAgo(lastSavedAt);
    return when ? `${savedLabel} ${when}` : savedLabel;
  });
</script>

<span
  class="save-indicator"
  data-state={state}
  aria-live="polite"
  aria-label={label}
  title={label}
>
  <span class="dot" aria-hidden="true"></span>
  <span class="save-label">{label}</span>
</span>

<style>
  .save-indicator {
    display: inline-flex;
    align-items: center;
    gap: var(--spacing-1, 0.25rem);
    font-family: var(--font-sans, system-ui, sans-serif);
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
    color: var(--text-muted, #7a7a90);
    user-select: none;
  }

  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
    background: var(--color-muted, #7a7a90);
    transition: background-color var(--motion-default, 200ms) ease;
  }

  /* saved */
  [data-state='saved'] .dot {
    background: var(--color-success, #10b981);
  }
  [data-state='saved'] .save-label {
    color: var(--color-success, #10b981);
  }

  /* saving */
  [data-state='saving'] .dot {
    background: var(--color-warning, #f59e0b);
  }
  [data-state='saving'] .save-label {
    color: var(--color-warning, #f59e0b);
  }

  /* unsaved */
  [data-state='unsaved'] .dot {
    background: var(--text-muted, #7a7a90);
  }
  [data-state='unsaved'] .save-label {
    color: var(--text-muted, #7a7a90);
  }

  /* Pulse animation — only if user allows motion (INV-14) */
  @media (prefers-reduced-motion: no-preference) {
    [data-state='saving'] .dot {
      animation: dot-pulse 1s ease-in-out infinite;
    }
  }

  @keyframes dot-pulse {
    0%   { opacity: 1;    transform: scale(1); }
    50%  { opacity: 0.45; transform: scale(0.8); }
    100% { opacity: 1;    transform: scale(1); }
  }
</style>
