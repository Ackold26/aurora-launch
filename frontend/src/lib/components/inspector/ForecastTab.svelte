<script lang="ts">
  import { _ } from 'svelte-i18n';
  import Card from '$lib/components/Card.svelte';
  import Skeleton from '$lib/components/Skeleton.svelte';
  import ForecastCone from '$lib/components/ForecastCone.svelte';
  import ModeBadge from '$lib/components/ModeBadge.svelte';
  import TrustScore from '$lib/components/TrustScore.svelte';
  import ReproduceModal from '$lib/components/inspector/ReproduceModal.svelte';
  import { activeBundle } from '$lib/stores/bundle';
  import { generateReproduceScript, explainForecast, computeTrustScore } from '$lib/ipc/forecast';
  import type { Explanation, TrustScoreResult } from '$lib/ipc/forecast';
  import { detectReproduceMode } from '$lib/utils/reproduce-mode';
  import type { ForecastData } from '$lib/components/inspector/types';

  interface Props {
    forecastData: ForecastData | null;
    loading: boolean;
    similarityScore: number | null;
    verificationValid: boolean | null;
  }

  let { forecastData, loading, similarityScore, verificationValid }: Props = $props();

  // M-09 Reproduce-in-Python state
  let reproduceModalOpen = $state(false);
  let reproduceScript = $state<string>('');
  let reproduceFilename = $state<string>('reproduce.py');
  let reproduceLoading = $state(false);
  let reproduceIsPreview = $state<boolean>(false);

  // M-03 AI explanation state
  let explanation = $state<Explanation | null>(null);
  let explanationLoading = $state(false);
  let explanationError = $state<string | null>(null);

  // PA-A03 / QW3: trust score state
  let trustResult = $state<TrustScoreResult | null>(null);
  let trustError = $state<string | null>(null);
  let trustIsRealCompute = $state<boolean>(false);

  // Load explanation when forecastData becomes available
  $effect(() => {
    if (forecastData && !explanation && !explanationLoading && !explanationError) {
      void loadExplanation();
    }
  });

  // Compute trust score when forecastData + similarityScore available
  $effect(() => {
    if (forecastData && similarityScore !== null && !trustResult && !trustError) {
      void computeTrustForBundle();
    }
  });

  async function loadExplanation() {
    if (!forecastData || !forecastData.engineMode || explanationLoading) return;
    explanationLoading = true;
    explanationError = null;
    try {
      const pointMean = forecastData.points.reduce((s, p) => s + p.point, 0) / forecastData.points.length;
      const ciLowMean = forecastData.points.reduce((s, p) => s + p.ciLower, 0) / forecastData.points.length;
      const ciHighMean = forecastData.points.reduce((s, p) => s + p.ciUpper, 0) / forecastData.points.length;
      explanation = await explainForecast({
        point_forecast_mean: pointMean,
        ci_lower_mean: ciLowMean,
        ci_upper_mean: ciHighMean,
        horizon_periods: forecastData.horizonWeeks,
        granularity: forecastData.granularity ?? 'monthly',
        engine_mode: forecastData.engineMode,
        methodology_signature: forecastData.methodologySignature ?? '',
        n_recipient: forecastData.nRecipient ?? 0,
        trust_score: trustResult?.score ?? null,
        warnings: forecastData.warnings ?? [],
        currency: 'RUB',
        locale: 'ru',
      });
    } catch (e) {
      explanationError = e instanceof Error ? e.message : String(e);
    } finally {
      explanationLoading = false;
    }
  }

  async function computeTrustForBundle() {
    if (!forecastData || similarityScore === null) return;
    try {
      const similarityPct = Math.round(similarityScore * 100);
      const widths = forecastData.points.map(p => (p.ciUpper - p.ciLower) / Math.max(p.point, 1));
      const meanWidth = widths.reduce((a, b) => a + b, 0) / widths.length;
      const uncertaintyInverse = Math.max(0, Math.min(1, 1 - meanWidth));
      const methodologyCertified = (verificationValid === true) ? 1 : 0.5;

      trustResult = await computeTrustScore({
        proxy_similarity_score: similarityPct,
        methodology_certified: methodologyCertified as 0 | 1 | 0.5,
        model_convergence_passed: 1,
        data_sufficiency: 1.0,
        uncertainty_pct_inverse: uncertaintyInverse,
      });
      trustIsRealCompute = true;
    } catch (e) {
      trustError = e instanceof Error ? e.message : String(e);
      trustResult = {
        score: similarityScore !== null ? Math.round(similarityScore * 100) : 0,
        tier: 'Предварительная оценка',
        diagnostics: [
          { label: 'Источник', value: 'только similarity score', status: 'info' },
          { label: 'Внимание', value: 'Полная диагностика появится после Bayesian fit', status: 'warn' },
        ],
      };
      trustIsRealCompute = false;
    }
  }

  async function openReproduceModal() {
    if (!$activeBundle || !forecastData) return;
    reproduceLoading = true;
    reproduceModalOpen = true;

    const modeResult = detectReproduceMode({
      anchors: forecastData.anchors,
      spendPlan: forecastData.spendPlan,
    });
    const hasReal = modeResult.isReal;
    reproduceIsPreview = !hasReal;

    try {
      const result = await generateReproduceScript({
        bundle_path: $activeBundle.path ?? './project.aurora',
        anchors: hasReal
          ? (forecastData.anchors as Record<string, unknown>)
          : {
              market_size: 1_000_000.0,
              market_size_cv: 0.1,
              planned_share_trajectory: Array(forecastData.horizonWeeks).fill(0.05),
              distribution_trajectory: Array(forecastData.horizonWeeks).fill(0.8),
              pricing_index: 1.0,
              elasticity: 0.0,
              seasonality: null,
            },
        spend_plan: hasReal
          ? (forecastData.spendPlan as Record<string, number[]>)
          : {},
        horizon_periods: forecastData.horizonWeeks,
        granularity: forecastData.granularity ?? 'monthly',
        coverage_target: 0.95,
        n_recipient: forecastData.nRecipient ?? 0,
      });

      if (!hasReal) {
        const previewWarning = [
          '# ⚠️ ПРЕВЬЮ-РЕЖИМ M-09 (Aurora Launch v0.1.0)',
          '# anchors + spend_plan в этом скрипте — ЗАГЛУШКИ из UI, не реальные',
          '# параметры исходного прогноза. Запуск даст forecast, не идентичный',
          '# тому что показан в Inspector. Bundle создан до v0.1.1 — используйте',
          '# скрипт как шаблон, подставляя свои anchors/spend вручную.',
          '#\n',
        ].join('\n');
        reproduceScript = previewWarning + result.script;
      } else {
        reproduceScript = result.script;
      }
      reproduceFilename = result.suggested_filename;
    } catch (e) {
      reproduceScript = `# Ошибка генерации скрипта:\n# ${e instanceof Error ? e.message : String(e)}\n`;
    } finally {
      reproduceLoading = false;
    }
  }
</script>

<div role="tabpanel" id="tab-forecast" hidden={false}>
  <Card title={$_('inspector.tab.forecast')}>
    {#snippet children()}
      {#if loading}
        <Skeleton width="100%" height="240px" rounded />
      {:else if forecastData}
        {#if forecastData.engineMode}
          <div class="mode-badge-mount">
            <ModeBadge
              mode={forecastData.engineMode}
              warnings={forecastData.warnings ?? []}
              showFullDetails={false}
            />
          </div>
        {/if}
        <ForecastCone
          points={forecastData.points}
          horizonWeeks={forecastData.horizonWeeks}
          width={620}
          height={300}
          title="Forecast cone (saved)"
        />
        {#if explanationLoading}
          <div class="explanation-loading">
            <Skeleton width="100%" height="120px" rounded />
          </div>
        {:else if explanation}
          <article class="forecast-explanation" aria-label="Объяснение прогноза" data-confidence={explanation.confidence}>
            <header class="explanation-header">
              <h3>
                <span aria-hidden="true">💡</span>
                Что значит этот прогноз
              </h3>
              <abbr title="Local engine: текстовое объяснение генерируется на этой машине, без отправки данных в сеть. Cloud (Claude API) — opt-in upgrade в Phase 2.5.">
                <span class="explanation-engine-tag">{explanation.engine_used}</span>
              </abbr>
            </header>
            <p class="explanation-para explanation-what">{explanation.what}</p>
            <p class="explanation-para explanation-why">{explanation.why}</p>
            <p class="explanation-para explanation-risks">{explanation.risks}</p>
          </article>
        {:else if explanationError}
          <p class="explanation-error" role="alert">
            Не удалось подготовить объяснение прогноза: {explanationError}
          </p>
        {/if}
        <div class="reproduce-cta">
          <button type="button" class="reproduce-btn" onclick={openReproduceModal} title="Воспроизвести прогноз в Python">
            <span aria-hidden="true">🐍</span> Воспроизвести в Python
          </button>
          <small class="reproduce-hint">Скрипт + сохранённый .aurora bundle = идентичный прогноз на любой машине с pip install aurora-launch.</small>
        </div>
        {#if trustResult}
          <div class="trust-mount">
            {#if !trustIsRealCompute}
              <div class="trust-preview-badge" role="note">
                <span class="badge-icon" aria-hidden="true">📊</span>
                <span class="badge-text">
                  Предварительная оценка — рассчитано только из similarity.
                  Полная диагностика появится после Bayesian fit.
                </span>
              </div>
            {/if}
            <TrustScore
              score={trustResult.score}
              verdict={trustResult.tier}
              diagnostics={trustResult.diagnostics}
              expertMode={!trustIsRealCompute}
            />
          </div>
        {/if}
      {:else}
        <p class="muted">No forecast entry в bundle (workflow not yet completed).</p>
      {/if}
    {/snippet}
  </Card>
</div>

<ReproduceModal
  open={reproduceModalOpen}
  script={reproduceScript}
  filename={reproduceFilename}
  loading={reproduceLoading}
  isPreview={reproduceIsPreview}
  onclose={() => (reproduceModalOpen = false)}
/>

<style>
  .mode-badge-mount { margin-bottom: var(--spacing-3, 0.75rem); }
  .forecast-explanation {
    margin-top: var(--spacing-4, 1rem);
    padding: var(--spacing-4, 1rem);
    background: color-mix(in srgb, var(--bg-elevated, #F0F2F7) 80%, transparent);
    border-left: 4px solid var(--accent, #2563eb);
    border-radius: 4px;
  }
  .forecast-explanation[data-confidence='low'] { border-left-color: var(--color-warning, #B45309); }
  .forecast-explanation[data-confidence='high'] { border-left-color: var(--color-success, #047857); }
  .explanation-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--spacing-3, 0.75rem);
  }
  .explanation-header h3 {
    margin: 0;
    font-family: var(--font-display, var(--font-sans, sans-serif));
    font-size: 1.125rem;
    display: inline-flex;
    align-items: center;
    gap: var(--spacing-2, 0.5rem);
  }
  .explanation-engine-tag {
    font-family: var(--font-mono, monospace);
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
    color: var(--text-muted, #6b7280);
    padding: 2px 8px;
    background: var(--bg-surface, white);
    border: 1px solid var(--border-default, #d1d5db);
    border-radius: 999px;
  }
  .explanation-para {
    margin: 0 0 var(--spacing-2, 0.5rem) 0;
    line-height: 1.6;
    color: var(--text-primary, #111827);
  }
  .explanation-para:last-child { margin-bottom: 0; }
  .explanation-risks {
    color: var(--text-secondary, #4A4D57);
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    border-top: 1px dashed var(--border-subtle, #e5e7eb);
    padding-top: var(--spacing-2, 0.5rem);
    margin-top: var(--spacing-3, 0.75rem);
  }
  .explanation-loading { margin-top: var(--spacing-4, 1rem); }
  .explanation-error { color: var(--color-danger, #B91C1C); margin-top: var(--spacing-3, 0.75rem); }
  .reproduce-cta {
    margin-top: var(--spacing-4, 1rem);
    padding: var(--spacing-3, 0.75rem);
    background: color-mix(in srgb, var(--accent, #2563eb) 6%, transparent);
    border-left: 3px solid var(--accent, #2563eb);
    border-radius: 4px;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2, 0.5rem);
  }
  .reproduce-btn {
    align-self: flex-start;
    padding: 8px 16px;
    border-radius: 6px;
    border: 1px solid var(--accent, #2563eb);
    background: var(--accent, #2563eb);
    color: white;
    cursor: pointer;
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    font-weight: 500;
    transition: background-color 120ms ease;
  }
  .reproduce-btn:hover { background: var(--color-primary-hover, #1d4ed8); }
  .reproduce-hint { color: var(--text-muted, #6b7280); font-size: var(--typography-fontSize-ui-xs, 0.75rem); line-height: 1.4; }
  .trust-mount { margin-top: var(--spacing-4, 1rem); }
  .trust-preview-badge {
    display: flex;
    align-items: center;
    gap: var(--spacing-2, 0.5rem);
    padding: var(--spacing-2, 0.5rem) var(--spacing-3, 0.75rem);
    background: color-mix(in srgb, var(--color-warning, #B45309) 8%, transparent);
    border-left: 3px solid var(--color-warning, #B45309);
    border-radius: 4px;
    margin-bottom: var(--spacing-2, 0.5rem);
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    color: var(--text-secondary, #4A4D57);
  }
  .badge-icon { flex-shrink: 0; font-size: 1.2em; }
  .badge-text { line-height: 1.4; }
  .muted { color: var(--text-muted); font-style: italic; }
</style>
