<!--
  /optimize — Подбор оптимального бюджета.
  Standalone route: wizard-like screen для grid + Dirichlet random search.
  Не модифицирует wizard/inspector/settings — изолированная фича.
-->

<script lang="ts">
  import { onDestroy } from 'svelte';
  import { _ } from 'svelte-i18n';
  import {
    optimizeBudget,
    cancelOptimizeBudget,
    onOptimizeBudgetCompleted,
    onOptimizeBudgetFailed,
    type BestSpendPlan,
    type SpendPlanAlternative,
  } from '$ipc/forecast';
  import { pushToast } from '$lib/stores/toast';
  import Card from '$lib/components/Card.svelte';
  import BudgetSplitChart from '$lib/components/BudgetSplitChart.svelte';

  // ─── Form state ───────────────────────────────────────────────────────────

  let totalBudget = $state<number | null>(null);
  let horizonPeriods = $state(12);
  let granularity = $state<'monthly' | 'weekly'>('monthly');
  let channels = $state<Array<{ name: string; min?: number; max: number }>>([
    { name: 'ТВ', max: 0 },
    { name: 'Digital', max: 0 },
    { name: 'OOH', max: 0 },
  ]);
  let nIterations = $state(100);

  // ─── Async / result state ─────────────────────────────────────────────────

  let optimizeHandle = $state<string | null>(null);
  let running = $state(false);
  let elapsedSec = $state(0);
  let result = $state<BestSpendPlan | null>(null);
  let alternatives = $state<SpendPlanAlternative[]>([]);

  // ─── Derived ─────────────────────────────────────────────────────────────

  const canStart = $derived(
    totalBudget !== null &&
      totalBudget > 0 &&
      channels.length > 0 &&
      channels.every((c) => c.max > 0) &&
      Math.max(...channels.map((c) => c.min ?? 0)) <= Math.min(...channels.map((c) => c.max))
  );

  // Sum of best plan totals per channel (across periods)
  const resultTotalSum = $derived(
    result
      ? Object.values(result.channel_split).reduce(
          (acc, periods) => acc + periods.reduce((s, v) => s + v, 0),
          0
        )
      : 0
  );

  // ─── Elapsed timer ────────────────────────────────────────────────────────

  let elapsedInterval: ReturnType<typeof setInterval> | null = null;

  function startElapsed() {
    elapsedSec = 0;
    elapsedInterval = setInterval(() => {
      elapsedSec += 1;
    }, 1000);
  }

  function stopElapsed() {
    if (elapsedInterval !== null) {
      clearInterval(elapsedInterval);
      elapsedInterval = null;
    }
  }

  // ─── Event listeners ─────────────────────────────────────────────────────

  let unlistenCompleted: (() => void) | null = null;
  let unlistenFailed: (() => void) | null = null;

  async function attachListeners(handle: string) {
    // Detach any previous listeners first
    detachListeners();

    unlistenCompleted = await onOptimizeBudgetCompleted((payload) => {
      if (payload.optimize_handle !== handle) return;
      result = payload.best;
      alternatives = payload.alternatives ?? [];
      running = false;
      stopElapsed();
    });

    unlistenFailed = await onOptimizeBudgetFailed((payload) => {
      if (payload.optimize_handle !== handle) return;
      running = false;
      stopElapsed();
      const isBusy = payload.kind === 'SidecarBusyError';
      pushToast({
        level: 'warning',
        title: isBusy ? $_('optimize.error.busy') : $_('optimize.error.generic'),
        ...(isBusy ? {} : { body: payload.error }),
        ttlMs: isBusy ? 8000 : 6000,
      });
    });
  }

  function detachListeners() {
    unlistenCompleted?.();
    unlistenCompleted = null;
    unlistenFailed?.();
    unlistenFailed = null;
  }

  onDestroy(() => {
    detachListeners();
    stopElapsed();
  });

  // ─── Actions ─────────────────────────────────────────────────────────────

  async function handleStart() {
    if (!canStart || running) return;

    result = null;
    alternatives = [];
    running = true;
    startElapsed();

    try {
      const channelCaps: Record<string, { min?: number; max: number }> = {};
      for (const ch of channels) {
        channelCaps[ch.name] = { max: ch.max, ...(ch.min !== undefined ? { min: ch.min } : {}) };
      }

      const res = await optimizeBudget({
        proxy_data: {},
        anchors_data: {},
        request: {
          total_budget: totalBudget!,
          channel_caps: channelCaps,
          horizon_periods: horizonPeriods,
          granularity,
          n_iterations: nIterations,
        },
      });

      optimizeHandle = res.optimize_handle;
      await attachListeners(res.optimize_handle);
    } catch (err: unknown) {
      running = false;
      stopElapsed();
      const msg = err instanceof Error ? err.message : String(err);
      const isBusy = msg.includes('SidecarBusy') || msg.includes('Busy');
      pushToast({
        level: 'warning',
        title: isBusy ? $_('optimize.error.busy') : $_('optimize.error.generic'),
        ...(isBusy ? {} : { body: msg }),
        ttlMs: isBusy ? 8000 : 6000,
      });
    }
  }

  async function handleCancel() {
    if (!optimizeHandle) return;
    try {
      await cancelOptimizeBudget(optimizeHandle);
    } catch {
      // Best-effort cancel — ignore errors
    }
    running = false;
    stopElapsed();
    detachListeners();
  }

  function addChannel() {
    channels = [...channels, { name: '', max: 0 }];
  }

  function removeChannel(index: number) {
    channels = channels.filter((_, i) => i !== index);
  }

  // ─── Formatting ───────────────────────────────────────────────────────────

  function formatRub(value: number): string {
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'RUB',
      maximumFractionDigits: 0,
    }).format(value);
  }
</script>

<div class="optimize-page">
  <!-- ── Heading ──────────────────────────────────────────────────────────── -->
  <section aria-label={$_('optimize.heading')} class="page-header">
    <h1 class="page-title">{$_('optimize.heading')}</h1>
    <p class="page-subtitle">{$_('optimize.subtitle')}</p>
  </section>

  <!-- ── Input section ────────────────────────────────────────────────────── -->
  <section aria-label="Параметры оптимизации" class="input-section">
    <Card title="Параметры" headingLevel={2}>
      {#snippet children()}
        <div class="form-grid">
          <!-- Total budget -->
          <div class="field">
            <label for="total-budget">{$_('optimize.input.total_budget')}</label>
            <input
              id="total-budget"
              type="number"
              min="1"
              step="1000"
              bind:value={totalBudget}
              placeholder="Например: 10 000 000"
              required
              class="field-input"
            />
          </div>

          <!-- Horizon -->
          <div class="field">
            <label for="horizon-periods">{$_('optimize.input.horizon')}</label>
            <input
              id="horizon-periods"
              type="number"
              min="1"
              max="52"
              bind:value={horizonPeriods}
              class="field-input field-input--narrow"
            />
          </div>

          <!-- Granularity -->
          <fieldset class="field field--full">
            <legend>{$_('optimize.input.granularity')}</legend>
            <div class="radio-group">
              <label class="radio-label">
                <input
                  type="radio"
                  name="granularity"
                  value="monthly"
                  bind:group={granularity}
                />
                {$_('optimize.input.granularity.monthly')}
              </label>
              <label class="radio-label">
                <input
                  type="radio"
                  name="granularity"
                  value="weekly"
                  bind:group={granularity}
                />
                {$_('optimize.input.granularity.weekly')}
              </label>
            </div>
          </fieldset>

          <!-- Channels -->
          <div class="field field--full">
            <span class="field-label">{$_('optimize.input.channels')}</span>
            <div class="channels-list" role="list">
              {#each channels as ch, i}
                <div class="channel-row" role="listitem">
                  <label class="sr-only" for="ch-name-{i}">{$_('optimize.input.channel.name')} {i + 1}</label>
                  <input
                    id="ch-name-{i}"
                    type="text"
                    placeholder={$_('optimize.input.channel.name')}
                    bind:value={ch.name}
                    class="field-input ch-name"
                    required
                  />
                  <label class="sr-only" for="ch-max-{i}">{$_('optimize.input.channel.max')}</label>
                  <input
                    id="ch-max-{i}"
                    type="number"
                    min="0"
                    step="100000"
                    placeholder={$_('optimize.input.channel.max')}
                    bind:value={ch.max}
                    class="field-input ch-budget"
                    required
                  />
                  <label class="sr-only" for="ch-min-{i}">{$_('optimize.input.channel.min')}</label>
                  <input
                    id="ch-min-{i}"
                    type="number"
                    min="0"
                    step="100000"
                    placeholder={$_('optimize.input.channel.min')}
                    bind:value={ch.min}
                    class="field-input ch-budget"
                  />
                  <button
                    type="button"
                    class="btn-icon btn-danger"
                    onclick={() => removeChannel(i)}
                    aria-label="{$_('optimize.input.channel.remove')} {ch.name || String(i + 1)}"
                  >✕</button>
                </div>
              {/each}
            </div>
            <button type="button" class="btn-ghost btn-add-ch" onclick={addChannel}>
              {$_('optimize.input.channel.add')}
            </button>
          </div>

          <!-- Advanced (collapsible) -->
          <details class="field field--full advanced-details">
            <summary class="advanced-summary">{$_('optimize.input.advanced')}</summary>
            <div class="advanced-body">
              <label for="n-iterations">{$_('optimize.input.n_iterations')}</label>
              <input
                id="n-iterations"
                type="number"
                min="10"
                max="2000"
                step="10"
                bind:value={nIterations}
                class="field-input field-input--narrow"
              />
            </div>
          </details>
        </div>

        <!-- Action button -->
        <div class="form-actions">
          <button
            type="button"
            class="btn-primary"
            onclick={handleStart}
            disabled={!canStart || running}
          >
            {$_('optimize.action.start')}
          </button>
        </div>
      {/snippet}
    </Card>
  </section>

  <!-- ── Progress section (only when running) ─────────────────────────────── -->
  {#if running}
    <section aria-label="Статус оптимизации" class="progress-section">
      <Card headingLevel={2}>
        {#snippet children()}
          <div class="running-row">
            <span class="spinner" aria-hidden="true"></span>
            <span>
              {$_('optimize.running.label')}
              <!-- aria-live for elapsed counter, not entire label (avoids verbosity) -->
              <span
                aria-live="polite"
                aria-atomic="true"
                class="elapsed-counter"
              >{elapsedSec}с</span>
            </span>
            <button
              type="button"
              class="btn-cancel"
              onclick={handleCancel}
            >
              {$_('optimize.action.cancel')}
            </button>
          </div>
        {/snippet}
      </Card>
    </section>
  {/if}

  <!-- ── Results section (only when completed) ────────────────────────────── -->
  {#if result}
    <section aria-label="Результаты оптимизации" class="results-section">
      <!-- Best plan card -->
      <Card title={$_('optimize.result.best')} accent="success" headingLevel={2}>
        {#snippet children()}
          <div class="result-body">
            <!-- Sum verification -->
            <p class="result-total">
              <strong>{$_('optimize.result.total')}</strong>
              {formatRub(resultTotalSum)}
            </p>

            <!-- Channel split chart -->
            <div class="chart-wrapper" aria-label="Распределение бюджета по каналам">
              <BudgetSplitChart channels={result!.channel_split} width={560} height={180} />
            </div>

            <!-- KPI grid -->
            <dl class="kpi-grid">
              <div class="kpi-item">
                <dt>{$_('optimize.result.kpi.sales')}</dt>
                <dd>{formatRub(result!.expected_total_sales)}</dd>
              </div>
              <div class="kpi-item">
                <dt>{$_('optimize.result.kpi.ci')}</dt>
                <dd>{formatRub(result!.ci_lower)} – {formatRub(result!.ci_upper)}</dd>
              </div>
            </dl>
          </div>
        {/snippet}
      </Card>

      <!-- Alternatives (collapsible) -->
      {#if alternatives.length > 0}
        <details class="alternatives-details">
          <summary class="alternatives-summary">
            {$_('optimize.result.alternatives')} ({alternatives.length})
          </summary>
          <div class="alternatives-list">
            {#each alternatives as alt}
              <Card headingLevel={3}>
                {#snippet children()}
                  <p class="alt-rank">
                    {$_('optimize.result.alt.rank', { values: { rank: alt.rank } })}
                  </p>
                  <dl class="kpi-grid">
                    <div class="kpi-item">
                      <dt>{$_('optimize.result.kpi.sales')}</dt>
                      <dd>{formatRub(alt.expected_total_sales)}</dd>
                    </div>
                    <div class="kpi-item">
                      <dt>{$_('optimize.result.kpi.ci')}</dt>
                      <dd>{formatRub(alt.ci_lower)} – {formatRub(alt.ci_upper)}</dd>
                    </div>
                  </dl>
                  <BudgetSplitChart channels={alt.channel_split} width={500} height={140} />
                {/snippet}
              </Card>
            {/each}
          </div>
        </details>
      {/if}
    </section>
  {/if}
</div>

<style>
  .optimize-page {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-6);
    max-width: 760px;
  }

  /* ── Page header ───────────────────────────────────────────────────────── */
  .page-header {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
  }

  .page-title {
    font-size: var(--typography-fontSize-ui-h2, 1.5rem);
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }

  .page-subtitle {
    color: var(--text-secondary);
    font-size: var(--typography-fontSize-ui-body, 0.9375rem);
    line-height: 1.6;
    margin: 0;
  }

  /* ── Form ──────────────────────────────────────────────────────────────── */
  .form-grid {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-4);
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1);
  }

  .field-label {
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    color: var(--text-secondary);
    font-weight: 500;
  }

  .field label,
  .field legend {
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    color: var(--text-secondary);
    font-weight: 500;
    margin: 0;
    padding: 0;
    border: none;
  }

  .field-input {
    background: var(--bg-main);
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-md, 6px);
    padding: var(--spacing-2) var(--spacing-3);
    color: var(--text-primary);
    font-family: var(--font-sans);
    font-size: var(--typography-fontSize-ui-body, 0.9375rem);
    transition: border-color 120ms ease;
    width: 100%;
    box-sizing: border-box;
  }

  .field-input:focus {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
    border-color: var(--accent);
  }

  .field-input--narrow {
    width: 120px;
  }

  .field--full {
    width: 100%;
  }

  /* ── Radio group ───────────────────────────────────────────────────────── */
  .radio-group {
    display: flex;
    gap: var(--spacing-4);
    flex-wrap: wrap;
    margin-top: var(--spacing-1);
  }

  .radio-label {
    display: flex;
    align-items: center;
    gap: var(--spacing-2);
    cursor: pointer;
    font-size: var(--typography-fontSize-ui-body, 0.9375rem);
    color: var(--text-primary);
  }

  /* ── Channels list ─────────────────────────────────────────────────────── */
  .channels-list {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
    margin-top: var(--spacing-2);
  }

  .channel-row {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr auto;
    gap: var(--spacing-2);
    align-items: center;
  }

  .ch-name {
    min-width: 0;
  }

  .ch-budget {
    min-width: 0;
  }

  .btn-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    padding: 0;
    border-radius: var(--border-radius-md, 6px);
    border: 1px solid transparent;
    cursor: pointer;
    font-size: 14px;
    transition: background-color 120ms ease;
    flex-shrink: 0;
  }

  .btn-danger {
    background: transparent;
    border-color: var(--color-danger);
    color: var(--color-danger);
  }

  .btn-danger:hover {
    background: color-mix(in srgb, var(--color-danger) 12%, transparent);
  }

  .btn-ghost {
    background: transparent;
    border: 1px dashed var(--border-subtle);
    color: var(--text-secondary);
    border-radius: var(--border-radius-md, 6px);
    padding: var(--spacing-2) var(--spacing-3);
    cursor: pointer;
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    font-family: var(--font-sans);
    transition: color 120ms ease, border-color 120ms ease;
  }

  .btn-ghost:hover {
    color: var(--text-primary);
    border-color: var(--accent);
  }

  .btn-add-ch {
    margin-top: var(--spacing-2);
    align-self: flex-start;
  }

  /* ── Advanced details ──────────────────────────────────────────────────── */
  .advanced-details {
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-md, 6px);
    padding: var(--spacing-2) var(--spacing-3);
  }

  .advanced-summary {
    cursor: pointer;
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    color: var(--text-secondary);
    user-select: none;
    padding: var(--spacing-1) 0;
  }

  .advanced-body {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
    margin-top: var(--spacing-3);
  }

  .advanced-body label {
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    color: var(--text-secondary);
  }

  /* ── Form actions ──────────────────────────────────────────────────────── */
  .form-actions {
    display: flex;
    justify-content: flex-end;
    padding-top: var(--spacing-2);
    border-top: 1px solid var(--border-subtle);
    margin-top: var(--spacing-2);
  }

  .btn-primary {
    padding: var(--spacing-2) var(--spacing-6);
    background: var(--accent);
    border: none;
    border-radius: var(--border-radius-md, 6px);
    color: white;
    font-family: var(--font-sans);
    font-size: var(--typography-fontSize-ui-body, 0.9375rem);
    font-weight: 500;
    cursor: pointer;
    transition: opacity 120ms ease;
  }

  .btn-primary:hover:not(:disabled) {
    opacity: 0.88;
  }

  .btn-primary:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  /* ── Progress section ──────────────────────────────────────────────────── */
  .running-row {
    display: flex;
    align-items: center;
    gap: var(--spacing-3);
  }

  .spinner {
    display: inline-block;
    width: 18px;
    height: 18px;
    border: 2px solid var(--border-subtle);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    flex-shrink: 0;
  }

  @media (prefers-reduced-motion: reduce) {
    .spinner {
      animation: none;
      border-top-color: var(--accent);
    }
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .elapsed-counter {
    font-variant-numeric: tabular-nums;
    color: var(--text-muted);
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
  }

  .btn-cancel {
    margin-left: auto;
    padding: var(--spacing-1) var(--spacing-4);
    background: transparent;
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-md, 6px);
    color: var(--text-secondary);
    font-family: var(--font-sans);
    cursor: pointer;
    transition: color 120ms ease, border-color 120ms ease;
  }

  .btn-cancel:hover {
    color: var(--text-primary);
    border-color: var(--color-danger);
    color: var(--color-danger);
  }

  /* ── Results section ───────────────────────────────────────────────────── */
  .results-section {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-4);
  }

  .result-body {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-4);
  }

  .result-total {
    font-size: var(--typography-fontSize-ui-body, 0.9375rem);
    color: var(--text-primary);
    margin: 0;
  }

  .chart-wrapper {
    overflow-x: auto;
  }

  /* KPI grid */
  .kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: var(--spacing-3);
    margin: 0;
  }

  .kpi-item {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1);
    padding: var(--spacing-3);
    background: var(--bg-main);
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-md, 6px);
  }

  .kpi-item dt {
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .kpi-item dd {
    font-size: var(--typography-fontSize-ui-body, 0.9375rem);
    color: var(--text-primary);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    margin: 0;
  }

  /* ── Alternatives ──────────────────────────────────────────────────────── */
  .alternatives-details {
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-lg);
    overflow: hidden;
  }

  .alternatives-summary {
    cursor: pointer;
    padding: var(--spacing-3) var(--spacing-4);
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    color: var(--text-secondary);
    background: var(--bg-surface);
    user-select: none;
    border-bottom: 1px solid var(--border-subtle);
  }

  .alternatives-list {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-3);
    padding: var(--spacing-4);
  }

  .alt-rank {
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    color: var(--text-muted);
    margin: 0 0 var(--spacing-2);
  }

  /* Screen-reader only utility */
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border-width: 0;
  }
</style>
