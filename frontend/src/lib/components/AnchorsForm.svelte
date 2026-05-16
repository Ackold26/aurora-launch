<!--
  AnchorsForm — Wizard Step 4 (Phase 1.C.5, SO-1 simplification).

  Replaces the legacy 12-slider approach with a pattern picker
  (Nарастание / Устойчивый рост / Снижение / Свой график) plus an
  intensity 1-10 slider.  80 % of use cases are covered by predefined
  patterns; Custom mode reveals the raw per-period sliders.

  Bindable `draft` prop follows WizardAnchorsDraft schema from
  src/aurora_launch/schemas/wizard_session.py.

  Per INV-14: prefers-reduced-motion respected (no hover transform).
-->

<script lang="ts">
  import {
    TRAJECTORY_PATTERNS,
    generateTrajectory,
    validIntensity,
    type TrajectoryPattern,
  } from '$lib/utils/trajectory_patterns';

  // ──────────────────────────────────────────────────────────────────────────
  // Types
  // ──────────────────────────────────────────────────────────────────────────

  interface AnchorsDraft {
    pattern: TrajectoryPattern;
    intensity: number;
    awareness_target_pct: number | null;
    custom_trajectory: number[] | null;
    notes: string | null;
  }

  interface Props {
    /**
     * Bindable: current anchors draft.  Parent passes initial value;
     * child reassigns the whole object on each mutation to trigger
     * Svelte reactivity (`draft = {...draft, field: newValue}`).
     */
    draft?: AnchorsDraft | null;
    /**
     * Horizon length in periods (weeks or months) — controls SVG preview
     * density and custom_trajectory slot count.
     */
    horizon_periods?: number;
  }

  let { draft = $bindable(), horizon_periods = 12 }: Props = $props();

  // ──────────────────────────────────────────────────────────────────────────
  // Derived
  // ──────────────────────────────────────────────────────────────────────────

  /** Ensure draft is always a valid object for template reads. */
  const safeDraft = $derived<AnchorsDraft>(
    draft ?? {
      pattern: 'sustain',
      intensity: 5,
      awareness_target_pct: null,
      custom_trajectory: null,
      notes: null,
    },
  );

  /** SVG preview data points. Null when pattern === 'custom'. */
  const trajectoryPoints = $derived<number[] | null>(
    generateTrajectory(safeDraft.pattern, safeDraft.intensity, horizon_periods),
  );

  /** SVG dimensions. */
  const SVG_W = 280;
  const SVG_H = 80;
  const PAD_X = 24;
  const PAD_Y = 8;

  /** Convert normalised values → SVG polyline points string. */
  const polylinePoints = $derived(
    trajectoryPoints && trajectoryPoints.length > 0
      ? (() => {
          const pts = trajectoryPoints;
          const w = SVG_W - PAD_X * 2;
          const h = SVG_H - PAD_Y * 2;
          return pts
            .map((v, i) => {
              const x = PAD_X + (i / Math.max(1, pts.length - 1)) * w;
              const y = PAD_Y + (1 - v) * h; // invert Y: 1.0 → top
              return `${x.toFixed(1)},${y.toFixed(1)}`;
            })
            .join(' ');
        })()
      : '',
  );

  /** Validation errors shown in the banner. */
  const validationErrors = $derived(
    (() => {
      const errs: string[] = [];
      if (!validIntensity(safeDraft.intensity)) {
        errs.push('Сила должна быть целым числом от 1 до 10.');
      }
      if (
        safeDraft.pattern === 'custom' &&
        safeDraft.custom_trajectory !== null &&
        safeDraft.custom_trajectory.length !== horizon_periods
      ) {
        errs.push(
          `Свой график: нужно ${horizon_periods} значений (указано ${safeDraft.custom_trajectory?.length ?? 0}).`,
        );
      }
      return errs;
    })(),
  );

  // ──────────────────────────────────────────────────────────────────────────
  // Mutators — always reassign the entire object to trigger reactivity
  // ──────────────────────────────────────────────────────────────────────────

  function setPattern(p: TrajectoryPattern): void {
    const next: AnchorsDraft = { ...safeDraft, pattern: p };
    // Ensure custom_trajectory slot is initialised when switching to custom.
    if (p === 'custom' && next.custom_trajectory === null) {
      next.custom_trajectory = Array(horizon_periods).fill(0);
    }
    draft = next;
  }

  function setIntensity(raw: string): void {
    const n = parseInt(raw, 10);
    draft = { ...safeDraft, intensity: Number.isNaN(n) ? safeDraft.intensity : n };
  }

  function setAwarenessTarget(raw: string): void {
    const n = parseFloat(raw);
    draft = { ...safeDraft, awareness_target_pct: raw === '' || Number.isNaN(n) ? null : n };
  }

  function setCustomValue(index: number, raw: string): void {
    const n = parseFloat(raw);
    const traj = safeDraft.custom_trajectory
      ? [...safeDraft.custom_trajectory]
      : Array(horizon_periods).fill(0);
    traj[index] = Number.isNaN(n) ? 0 : Math.max(0, Math.min(1, n));
    draft = { ...safeDraft, custom_trajectory: traj };
  }

  function setNotes(raw: string): void {
    draft = { ...safeDraft, notes: raw === '' ? null : raw };
  }
</script>

<section class="anchors-form" aria-label="Шаг 4 — Опорные точки прогноза">
  <!-- ──────────────────────────────────────────────────────────────────────
       Header
  ──────────────────────────────────────────────────────────────────────── -->
  <header class="anchors-header">
    <h2 class="anchors-title">Шаг 4 — Опорные точки прогноза</h2>
    <p class="anchors-subtitle">
      Расскажите Aurora, как должен меняться awareness. Не уверены? Оставьте
      <strong>Устойчивый рост</strong> — это самый распространённый сценарий.
    </p>
  </header>

  <!-- ──────────────────────────────────────────────────────────────────────
       Pattern picker
  ──────────────────────────────────────────────────────────────────────── -->
  <fieldset class="pattern-fieldset">
    <legend class="pattern-legend">Паттерн awareness</legend>
    <div class="pattern-grid" role="group" aria-label="Паттерн awareness">
      {#each TRAJECTORY_PATTERNS as p (p.id)}
        {@const selected = safeDraft.pattern === p.id}
        <button
          type="button"
          class="pattern-card"
          class:pattern-card--selected={selected}
          aria-pressed={selected}
          onclick={() => setPattern(p.id)}
        >
          <span class="pattern-label">{p.label_ru}</span>
          <span class="pattern-desc">{p.description_ru}</span>
          <span class="pattern-use">{p.use_case_ru}</span>
        </button>
      {/each}
    </div>
  </fieldset>

  <!-- ──────────────────────────────────────────────────────────────────────
       Intensity slider (hidden in custom mode — irrelevant)
  ──────────────────────────────────────────────────────────────────────── -->
  {#if safeDraft.pattern !== 'custom'}
    <div class="intensity-row">
      <label class="intensity-label" for="anchors-intensity">
        Сила: <strong>{safeDraft.intensity}/10</strong>
      </label>
      <input
        id="anchors-intensity"
        type="range"
        min="1"
        max="10"
        step="1"
        value={safeDraft.intensity}
        class="intensity-slider"
        aria-label="Интенсивность паттерна от 1 до 10"
        aria-describedby="anchors-intensity-desc"
        oninput={(e) => setIntensity((e.target as HTMLInputElement).value)}
      />
      <span id="anchors-intensity-desc" class="intensity-hint">
        1 — минимальный эффект, 10 — максимальный
      </span>
    </div>
  {/if}

  <!-- ──────────────────────────────────────────────────────────────────────
       SVG trajectory preview
  ──────────────────────────────────────────────────────────────────────── -->
  {#if safeDraft.pattern !== 'custom'}
    <div class="preview-wrapper">
      <svg
        class="preview-svg"
        width={SVG_W}
        height={SVG_H}
        viewBox={`0 0 ${SVG_W} ${SVG_H}`}
        aria-label="Предпросмотр траектории awareness"
        role="img"
      >
        <title>Предпросмотр траектории awareness</title>
        <!-- Axis baseline -->
        <line
          x1={PAD_X}
          y1={SVG_H - PAD_Y}
          x2={SVG_W - PAD_X}
          y2={SVG_H - PAD_Y}
          class="axis-line"
        />
        <!-- Trajectory line -->
        {#if polylinePoints}
          <polyline
            points={polylinePoints}
            class="trajectory-line"
            fill="none"
          />
        {/if}
        <!-- Period labels -->
        <text x={PAD_X} y={SVG_H} class="axis-label" text-anchor="middle">1</text>
        <text x={SVG_W - PAD_X} y={SVG_H} class="axis-label" text-anchor="middle">
          {horizon_periods}
        </text>
      </svg>
    </div>
  {/if}

  <!-- ──────────────────────────────────────────────────────────────────────
       Custom trajectory inputs (pattern === 'custom' only)
  ──────────────────────────────────────────────────────────────────────── -->
  {#if safeDraft.pattern === 'custom'}
    <fieldset class="custom-fieldset">
      <legend class="custom-legend">
        Значения по периодам (от 0 до 1, где 1 = максимальный awareness)
      </legend>
      <div class="custom-grid">
        {#each Array(horizon_periods) as _, i}
          <label class="custom-cell">
            <span class="custom-period">{i + 1}</span>
            <input
              type="number"
              min="0"
              max="1"
              step="0.01"
              value={safeDraft.custom_trajectory?.[i] ?? 0}
              class="custom-input"
              aria-label={`Период ${i + 1}`}
              oninput={(e) => setCustomValue(i, (e.target as HTMLInputElement).value)}
            />
          </label>
        {/each}
      </div>
    </fieldset>
  {/if}

  <!-- ──────────────────────────────────────────────────────────────────────
       Awareness target % (optional)
  ──────────────────────────────────────────────────────────────────────── -->
  <div class="field-row">
    <label class="field-label" for="anchors-awareness">
      Целевой уровень awareness, % <span class="field-optional">(необязательно)</span>
    </label>
    <input
      id="anchors-awareness"
      type="number"
      min="0"
      max="100"
      step="0.1"
      value={safeDraft.awareness_target_pct ?? ''}
      placeholder="Например, 35.5"
      class="field-input"
      aria-label="Целевой уровень awareness в процентах"
      oninput={(e) => setAwarenessTarget((e.target as HTMLInputElement).value)}
    />
  </div>

  <!-- ──────────────────────────────────────────────────────────────────────
       Notes (optional)
  ──────────────────────────────────────────────────────────────────────── -->
  <div class="field-row">
    <label class="field-label" for="anchors-notes">
      Комментарии <span class="field-optional">(необязательно)</span>
    </label>
    <textarea
      id="anchors-notes"
      rows="3"
      value={safeDraft.notes ?? ''}
      placeholder="Особенности сезона, рыночная ситуация, ограничения..."
      class="field-textarea"
      aria-label="Дополнительные комментарии к прогнозу"
      oninput={(e) => setNotes((e.target as HTMLTextAreaElement).value)}
    ></textarea>
  </div>

  <!-- ──────────────────────────────────────────────────────────────────────
       Validation banner
  ──────────────────────────────────────────────────────────────────────── -->
  {#if validationErrors.length > 0}
    <div class="validation-banner" role="alert" aria-live="polite">
      {#each validationErrors as err}
        <p class="validation-error">{err}</p>
      {/each}
    </div>
  {/if}
</section>

<style>
  /* ── Layout ─────────────────────────────────────────────────────────────── */
  .anchors-form {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-4, 1rem);
    padding: var(--spacing-4, 1rem);
  }

  /* ── Header ─────────────────────────────────────────────────────────────── */
  .anchors-title {
    font-family: var(--font-display, var(--font-sans, sans-serif));
    font-size: var(--typography-fontSize-ui-h3, 1.25rem);
    font-weight: 600;
    color: var(--text-primary, #111827);
    margin: 0 0 var(--spacing-1, 0.25rem) 0;
  }

  .anchors-subtitle {
    color: var(--text-secondary, #374151);
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    margin: 0;
    line-height: var(--typography-lineHeight-normal, 1.5);
  }

  /* ── Pattern picker ─────────────────────────────────────────────────────── */
  .pattern-fieldset {
    border: none;
    padding: 0;
    margin: 0;
  }

  .pattern-legend {
    font-weight: 600;
    color: var(--text-primary, #111827);
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    margin-bottom: var(--spacing-2, 0.5rem);
  }

  .pattern-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: var(--spacing-2, 0.5rem);
  }

  .pattern-card {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1, 0.25rem);
    padding: var(--spacing-3, 0.75rem);
    background: var(--bg-surface, #1a1d27);
    border: 2px solid var(--border-subtle, #2a2d37);
    border-radius: var(--border-radius-lg, 8px);
    cursor: pointer;
    text-align: left;
    color: inherit;
    font-family: inherit;
    transition:
      border-color var(--motion-duration-fast, 80ms) var(--motion-easing-standard, ease),
      background var(--motion-duration-fast, 80ms) var(--motion-easing-standard, ease);
  }

  .pattern-card:hover {
    border-color: var(--accent, #2e5bff);
  }

  .pattern-card--selected {
    border-color: var(--accent, #2e5bff);
    background: var(--surface-selected, color-mix(in srgb, var(--accent, #2e5bff) 12%, var(--bg-surface, #1a1d27)));
  }

  .pattern-label {
    font-weight: 600;
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    color: var(--text-primary, #111827);
  }

  .pattern-desc {
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
    color: var(--text-secondary, #374151);
  }

  .pattern-use {
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
    color: var(--text-secondary, #4a4d57);
    font-style: italic;
  }

  /* ── Intensity slider ───────────────────────────────────────────────────── */
  .intensity-row {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1, 0.25rem);
  }

  .intensity-label {
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    color: var(--text-primary, #111827);
  }

  .intensity-slider {
    width: 100%;
    accent-color: var(--accent, #2e5bff);
    cursor: pointer;
  }

  .intensity-hint {
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
    color: var(--text-secondary, #4a4d57);
  }

  /* ── SVG preview ────────────────────────────────────────────────────────── */
  .preview-wrapper {
    border: 1px solid var(--border-subtle, #2a2d37);
    border-radius: var(--border-radius-sm, 2px);
    background: var(--color-bg-elevated, var(--bg-elevated, #222532));
    padding: var(--spacing-2, 0.5rem);
    display: inline-block;
  }

  .preview-svg {
    display: block;
  }

  .axis-line {
    stroke: var(--border-subtle, #2a2d37);
    stroke-width: 1;
  }

  .trajectory-line {
    stroke: var(--accent, #2e5bff);
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  .axis-label {
    fill: var(--text-secondary, #4a4d57);
    font-size: 10px;
    font-family: var(--font-mono, monospace);
  }

  /* ── Custom trajectory grid ─────────────────────────────────────────────── */
  .custom-fieldset {
    border: 1px solid var(--border-subtle, #2a2d37);
    border-radius: var(--border-radius-lg, 8px);
    padding: var(--spacing-3, 0.75rem);
    margin: 0;
  }

  .custom-legend {
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    color: var(--text-secondary, #374151);
    padding: 0 var(--spacing-1, 0.25rem);
  }

  .custom-grid {
    display: flex;
    flex-wrap: wrap;
    gap: var(--spacing-2, 0.5rem);
    margin-top: var(--spacing-2, 0.5rem);
  }

  .custom-cell {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--spacing-1, 0.25rem);
    width: 3.5rem;
  }

  .custom-period {
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
    color: var(--text-secondary, #4a4d57);
  }

  .custom-input {
    width: 100%;
    padding: var(--spacing-1, 0.25rem);
    border: 1px solid var(--border-subtle, #2a2d37);
    border-radius: var(--border-radius-sm, 2px);
    background: var(--bg-surface, #1a1d27);
    color: var(--text-primary, #111827);
    font-family: var(--font-mono, monospace);
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
    text-align: center;
  }

  /* ── Generic field rows ─────────────────────────────────────────────────── */
  .field-row {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1, 0.25rem);
  }

  .field-label {
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    font-weight: 500;
    color: var(--text-primary, #111827);
  }

  .field-optional {
    font-weight: 400;
    color: var(--text-secondary, #4a4d57);
  }

  .field-input {
    padding: var(--spacing-2, 0.5rem) var(--spacing-3, 0.75rem);
    border: 1px solid var(--border-subtle, #2a2d37);
    border-radius: var(--border-radius-md, 4px);
    background: var(--bg-surface, #1a1d27);
    color: var(--text-primary, #111827);
    font-family: inherit;
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    max-width: 16rem;
  }

  .field-input:focus {
    outline: 2px solid var(--accent, #2e5bff);
    outline-offset: 2px;
  }

  .field-textarea {
    padding: var(--spacing-2, 0.5rem) var(--spacing-3, 0.75rem);
    border: 1px solid var(--border-subtle, #2a2d37);
    border-radius: var(--border-radius-md, 4px);
    background: var(--bg-surface, #1a1d27);
    color: var(--text-primary, #111827);
    font-family: inherit;
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    resize: vertical;
  }

  .field-textarea:focus {
    outline: 2px solid var(--accent, #2e5bff);
    outline-offset: 2px;
  }

  /* ── Validation banner ──────────────────────────────────────────────────── */
  .validation-banner {
    padding: var(--spacing-2, 0.5rem) var(--spacing-3, 0.75rem);
    background: color-mix(in srgb, var(--color-danger, #EF4444) 12%, var(--bg-surface, #1a1d27));
    border: 1px solid var(--color-danger, #EF4444);
    border-radius: var(--border-radius-md, 4px);
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1, 0.25rem);
  }

  .validation-error {
    margin: 0;
    color: var(--color-danger, #EF4444);
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
  }

  /* ── Reduced motion ─────────────────────────────────────────────────────── */
  @media (prefers-reduced-motion: reduce) {
    .pattern-card {
      transition: none;
    }
  }
</style>
