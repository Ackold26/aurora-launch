<!--
  ProgressBarMCMC — премиум-компонент ожидания MCMC-расчёта (Sprint 2 D6).

  Показывает прогресс 0-100%, текущую фазу, оценку оставшегося времени
  и ротирующиеся методологические подсказки каждые 8 секунд.

  INV-14: prefers-reduced-motion — анимация прогресс-бара отключается.
  INV-27: data-mcmc-progress-mount="true" на корневом элементе для
          sessionStats hook.

  Props: { pct, phase, elapsedMs, message, oncancel, cancelDisabled?, showTips? }
  Wired into ForecastTab.svelte в D7'.
-->

<script lang="ts">
  import { METHODOLOGY_TIPS } from '$lib/data/methodology_tips';
  import type { McmcPhase } from '$lib/ipc/forecast';

  // ── Props ─────────────────────────────────────────────────────────────────

  interface Props {
    /** Прогресс 0..100. */
    pct: number;
    /** Текущая фаза вычисления. */
    phase: McmcPhase;
    /** Прошедшее время в мс — нужно для расчёта ETA. */
    elapsedMs: number;
    /** Статусная строка от бэкенда (например "Drawing samples"). */
    message: string;
    /** Обработчик отмены. Кнопка всегда отрисовывается. */
    oncancel: () => void;
    /** Отключить кнопку отмены (default: false). */
    cancelDisabled?: boolean;
    /** Показывать ли блок с подсказками (default: true). */
    showTips?: boolean;
  }

  let {
    pct,
    phase,
    elapsedMs,
    message,
    oncancel,
    cancelDisabled = false,
    showTips = true,
  }: Props = $props();

  // ── ETA ───────────────────────────────────────────────────────────────────

  /**
   * Оценка оставшегося времени в мс.
   * При pct < 5 данных недостаточно для надёжной оценки.
   */
  const etaMs = $derived(
    pct >= 5
      ? (elapsedMs * (100 - pct)) / Math.max(pct, 1)
      : null
  );

  /** Форматирует оценку оставшегося времени в читаемую строку. */
  const etaLabel = $derived(() => {
    if (pct < 5) return 'Расчёт времени…';
    if (etaMs === null) return 'Расчёт времени…';
    const totalSec = Math.round(etaMs / 1000);
    if (totalSec < 60) return `Осталось ~${totalSec} сек`;
    const min = Math.floor(totalSec / 60);
    const sec = totalSec % 60;
    if (sec === 0) return `Осталось ~${min} мин`;
    return `Осталось ~${min} мин ${sec} сек`;
  });

  // ── Phase label ───────────────────────────────────────────────────────────

  const PHASE_LABELS: Record<McmcPhase, string> = {
    adaptation: 'Адаптация',
    sampling: 'Сэмплирование',
    diagnostics: 'Диагностика',
    done: 'Готово',
  };

  const phaseLabel = $derived(PHASE_LABELS[phase] ?? phase);

  // ── Message truncation ────────────────────────────────────────────────────

  const MAX_MSG = 80;
  const displayMessage = $derived(
    message.length > MAX_MSG ? message.slice(0, MAX_MSG - 1) + '…' : message
  );

  // ── Tip rotation ──────────────────────────────────────────────────────────

  let tipIndex = $state(0);

  $effect(() => {
    // Не вращаем подсказки когда расчёт завершён или подсказки скрыты
    if (phase === 'done' || !showTips) return;

    const id = setInterval(() => {
      tipIndex = (tipIndex + 1) % METHODOLOGY_TIPS.length;
    }, 8000);

    return () => clearInterval(id);
  });

  const currentTip = $derived(METHODOLOGY_TIPS[tipIndex] ?? METHODOLOGY_TIPS[0]);

  // ── Progress bar width ────────────────────────────────────────────────────

  const barWidth = $derived(`${Math.max(0, Math.min(100, pct))}%`);
  const pctDisplay = $derived(Math.round(Math.max(0, Math.min(100, pct))));
</script>

<div
  class="mcmc-wait"
  data-mcmc-progress-mount="true"
  role="region"
  aria-label="Процесс вычисления"
>
  <!-- Phase badge -->
  <div class="phase-row">
    <span class="phase-badge" data-phase={phase} aria-label={`Фаза: ${phaseLabel}`}>
      {phaseLabel}
    </span>
    <span class="eta-label" aria-live="polite">
      {etaLabel()}
    </span>
  </div>

  <!-- Progress bar -->
  <div
    class="track-wrap"
    role="progressbar"
    aria-valuenow={pctDisplay}
    aria-valuemin={0}
    aria-valuemax={100}
    aria-label={`Прогресс: ${pctDisplay}%`}
  >
    <div class="track">
      <div class="bar" style:width={barWidth}></div>
    </div>
    <span class="pct-label" aria-hidden="true">{pctDisplay}%</span>
  </div>

  <!-- Status message -->
  {#if displayMessage}
    <p class="status-message" aria-live="polite">{displayMessage}</p>
  {/if}

  <!-- Methodology tip -->
  {#if showTips}
    <div class="tip-area" aria-label="Методологическая подсказка" aria-live="polite">
      <span class="tip-icon" aria-hidden="true">💡</span>
      <p class="tip-text">{currentTip}</p>
    </div>
  {/if}

  <!-- Cancel button — always rendered, disabled only when cancelDisabled=true -->
  <div class="actions-row">
    <button
      type="button"
      class="cancel-btn"
      onclick={oncancel}
      disabled={cancelDisabled}
      aria-disabled={cancelDisabled}
    >
      Отменить
    </button>
  </div>
</div>

<style>
  .mcmc-wait {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-3, 0.75rem);
    padding: var(--spacing-4, 1rem);
    background: var(--bg-elevated, #f0f2f7);
    border-radius: var(--border-radius-lg, 8px);
    border: 1px solid var(--border-subtle, #e5e7eb);
    width: 100%;
    box-sizing: border-box;
  }

  /* ── Phase row ───────────────────────────────────────────────────────────── */
  .phase-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--spacing-2, 0.5rem);
    flex-wrap: wrap;
  }

  .phase-badge {
    display: inline-flex;
    align-items: center;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
    font-weight: 600;
    letter-spacing: 0.02em;
    background: color-mix(in srgb, var(--accent, #2563eb) 15%, transparent);
    color: var(--accent, #2563eb);
    border: 1px solid color-mix(in srgb, var(--accent, #2563eb) 30%, transparent);
  }

  .phase-badge[data-phase='done'] {
    background: color-mix(in srgb, var(--color-success, #047857) 15%, transparent);
    color: var(--color-success, #047857);
    border-color: color-mix(in srgb, var(--color-success, #047857) 30%, transparent);
  }

  .phase-badge[data-phase='diagnostics'] {
    background: color-mix(in srgb, var(--color-warning, #b45309) 12%, transparent);
    color: var(--color-warning, #b45309);
    border-color: color-mix(in srgb, var(--color-warning, #b45309) 30%, transparent);
  }

  .eta-label {
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    color: var(--text-muted, #6b7280);
    font-variant-numeric: tabular-nums;
  }

  /* ── Progress track ──────────────────────────────────────────────────────── */
  .track-wrap {
    display: flex;
    align-items: center;
    gap: var(--spacing-2, 0.5rem);
  }

  .track {
    flex: 1;
    height: 8px;
    background: var(--bg-surface, #fff);
    border: 1px solid var(--border-subtle, #e5e7eb);
    border-radius: 999px;
    overflow: hidden;
    position: relative;
  }

  .bar {
    height: 100%;
    background: linear-gradient(
      90deg,
      var(--accent, #2563eb),
      color-mix(in srgb, var(--accent, #2563eb) 70%, var(--accent-sigil, #7c3aed))
    );
    border-radius: 999px;
    transition: width 400ms var(--easing-emphasized, cubic-bezier(0.4, 0, 0.2, 1));
    will-change: width;
  }

  .pct-label {
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    font-weight: 600;
    color: var(--text-primary, #111827);
    font-variant-numeric: tabular-nums;
    min-width: 3.5ch;
    text-align: right;
  }

  /* ── Status message ──────────────────────────────────────────────────────── */
  .status-message {
    margin: 0;
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    color: var(--text-secondary, #4a4d57);
    line-height: 1.5;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* ── Tip area ────────────────────────────────────────────────────────────── */
  .tip-area {
    display: flex;
    align-items: flex-start;
    gap: var(--spacing-2, 0.5rem);
    padding: var(--spacing-3, 0.75rem);
    background: color-mix(in srgb, var(--accent, #2563eb) 5%, transparent);
    border-left: 3px solid color-mix(in srgb, var(--accent, #2563eb) 40%, transparent);
    border-radius: 4px;
  }

  .tip-icon {
    font-size: 1rem;
    flex-shrink: 0;
    line-height: 1.5;
  }

  .tip-text {
    margin: 0;
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    color: var(--text-secondary, #4a4d57);
    line-height: 1.6;
  }

  /* ── Actions row ─────────────────────────────────────────────────────────── */
  .actions-row {
    display: flex;
    justify-content: flex-end;
  }

  .cancel-btn {
    padding: 6px 16px;
    border-radius: 6px;
    border: 1px solid var(--border-subtle, #d1d5db);
    background: transparent;
    color: var(--text-secondary, #4a4d57);
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    font-weight: 500;
    cursor: pointer;
    transition: background-color 120ms ease, color 120ms ease;
  }

  .cancel-btn:hover:not(:disabled) {
    background: var(--bg-surface, #fff);
    color: var(--text-primary, #111827);
    border-color: var(--text-muted, #6b7280);
  }

  .cancel-btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  /* ── INV-14: prefers-reduced-motion ─────────────────────────────────────── */
  @media (prefers-reduced-motion: reduce) {
    .bar {
      transition: none;
    }

    .cancel-btn {
      transition: none;
    }
  }
</style>
