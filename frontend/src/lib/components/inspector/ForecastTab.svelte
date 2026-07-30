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
  import ChartWithDrillDown from '$lib/components/transparency/ChartWithDrillDown.svelte';
  import NumberWithDrillDown from '$lib/components/transparency/NumberWithDrillDown.svelte';

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

  // exec-launch-trust (2026-07-29, INV-50): computeTrustForBundle() ниже шлёт
  // model_convergence_passed=1 как консервативный дефолт (тот же, что уже
  // документирован в backend-обёртке trust_score_project.extract_model_convergence
  // для detected proxy-transfer без MCMC) — числовой вклад в score НЕ трогаем,
  // это отдельное, уже принятое продуктовое решение. Но клиент не должен видеть
  // зелёный итог без оговорки: R̂/ESS в этом окне не вычислялись — интерфейс
  // обязан сказать об этом прямо.
  //
  // 🔴 Приёмка audit findings 2026-07-29 (fix/audit-findings-72): причина оговорки
  // раньше читалась из engineMode — ЗАКАЗАННОГО режима движка (`engine_config.mode`),
  // а не из фактически исполненного пути. У байесовского и OLS-режимов есть
  // fallback-выходы в чистый перенос (`dispatch_table.py:274-304, 318-326, 351-360`
  // для OLS; `:463-483, 490-499, 526-535` для Bayesian) — тогда engineMode остаётся
  // прежним, а апостериор/регрессия по данным клиента не строятся вовсе. Фактический
  // путь несёт `methodologySignature` — каждый handler в dispatch_table.py возвращает
  // свою сигнатуру (`pure_transfer_v1`, `transfer_with_bias_check_v1`,
  // `ols_with_proxy_priors_v1` / `..._fallback_v1`, `bayesian_with_proxy_priors_v1` /
  // `..._fallback_v1`). Приоритет: сигнатура → engineMode (только когда сигнатуры нет,
  // напр. legacy-бандл до появления поля) → «метод не указан» (когда нет ни того, ни
  // другого). Клиентский текст не должен называть внутренние имена режимов/сигнатур.
  //
  // 🔴 Внешний аудит 2026-07-30 (High, регресс): предыдущая правка сузила общий
  // префикс до одной только сходимости, и «и достаточности данных» пропало из всех
  // пяти текстов. Подставлены ОБЕ величины (`model_convergence_passed: 1` и
  // `data_sufficiency: 1.0` в computeTrustForBundle ниже), и обе видны клиенту
  // зелёными строками панели TrustScore. INV-50 «нет числа — нет подписи»: каждая
  // подставленная величина обязана быть названа в оговорке. Префикс ниже — SSOT
  // для всех вариантов, менять его можно только вместе со сторожем в
  // frontend/tests/unit/ForecastTab.test.ts (он ассертит обе величины по фикстуре).
  const CLIENT_STUBBED_DIAGNOSTICS_PREFIX =
    'Диагностика сходимости и достаточности данных не выполнялась';
  const CLIENT_TRANSFER_TEXT =
    `${CLIENT_STUBBED_DIAGNOSTICS_PREFIX} – прогноз построен методом переноса, без сэмплирования.`;
  const CLIENT_BAYESIAN_ANALYTICAL_TEXT =
    `${CLIENT_STUBBED_DIAGNOSTICS_PREFIX} – апостериорное распределение получено аналитически, без сэмплирования.`;
  const CLIENT_BAYESIAN_FALLBACK_TEXT =
    `${CLIENT_STUBBED_DIAGNOSTICS_PREFIX} – байесовский расчёт не состоялся, прогноз построен методом переноса.`;
  const CLIENT_REGRESSION_TEXT =
    `${CLIENT_STUBBED_DIAGNOSTICS_PREFIX} – модель оценена по вашим данным методом наименьших квадратов с опорными значениями, без сэмплирования.`;
  // 🔴 Внешний аудит 2026-07-30 (High): устаревший путь расчёта
  // (`methods_forecast.py`, ветка legacy prior-predictive) раньше вообще не
  // сообщал о себе — сводки в `forecast_completed` не было, мастер подставлял
  // `pure_transfer`, и клиенту говорилось «методом переноса, без сэмплирования».
  // Ложны оба утверждения: переноса не было, выборка была (50 draws из априорных
  // допущений). Теперь этот путь испускает сигнатуру `legacy_prior_predictive_v1`,
  // и ей соответствует свой честный текст.
  const CLIENT_LEGACY_PRIOR_PREDICTIVE_TEXT =
    `${CLIENT_STUBBED_DIAGNOSTICS_PREFIX} – прогноз получен выборкой из априорных допущений, модель по вашим данным не строилась.`;
  const CLIENT_UNKNOWN_METHOD_TEXT =
    `${CLIENT_STUBBED_DIAGNOSTICS_PREFIX} – метод расчёта в сохранённом прогнозе не указан.`;

  /** Текст оговорки по фактической сигнатуре методологии (см. dispatch_table.py).
   * Возвращает null, если сигнатура не распознана — вызывающий код тогда обязан
   * обратиться к engineMode как к запасному источнику. Проверка fallback-вариантов
   * ДОЛЖНА идти раньше базового префикса — иначе `..._fallback_v1` матчится как
   * успешный путь (fallback-строка сама начинается с базового имени режима). */
  function textForSignature(sig: string): string | null {
    if (sig.startsWith('bayesian_with_proxy_priors_fallback')) return CLIENT_BAYESIAN_FALLBACK_TEXT;
    if (sig.startsWith('bayesian_with_proxy_priors')) return CLIENT_BAYESIAN_ANALYTICAL_TEXT;
    if (sig.startsWith('ols_with_proxy_priors_fallback')) return CLIENT_TRANSFER_TEXT;
    if (sig.startsWith('ols_with_proxy_priors')) return CLIENT_REGRESSION_TEXT;
    if (sig.startsWith('transfer_with_bias_check')) return CLIENT_TRANSFER_TEXT;
    if (sig.startsWith('pure_transfer')) return CLIENT_TRANSFER_TEXT;
    if (sig.startsWith('legacy_prior_predictive')) return CLIENT_LEGACY_PRIOR_PREDICTIVE_TEXT;
    return null;
  }

  /** Текст оговорки по ЗАКАЗАННОМУ режиму движка — запасной источник, только
   * когда фактическая сигнатура недоступна (напр. legacy-бандл без поля
   * methodology_signature). engineMode не различает реальный фит и fallback —
   * это единственное известное ограничение этого запасного пути. */
  function textForEngineMode(mode: ForecastData['engineMode']): string | null {
    switch (mode) {
      case 'pure_transfer':
      case 'transfer_with_bias_check':
        return CLIENT_TRANSFER_TEXT;
      case 'ols_with_proxy_priors':
        return CLIENT_REGRESSION_TEXT;
      case 'bayesian_with_proxy_priors':
        return CLIENT_BAYESIAN_ANALYTICAL_TEXT;
      default:
        return null;
    }
  }

  const trustDisclaimerText = $derived.by((): string => {
    const sig = forecastData?.methodologySignature;
    const bySignature = sig ? textForSignature(sig) : null;
    if (bySignature) return bySignature;
    return textForEngineMode(forecastData?.engineMode) ?? CLIENT_UNKNOWN_METHOD_TEXT;
  });

  // Derived summary stats for NumberWithDrillDown wrappers — Sprint 3 D4
  const pointMeanDisplay = $derived.by((): string => {
    if (!forecastData || forecastData.points.length === 0) return '—';
    const mean = forecastData.points.reduce((s, p) => s + p.point, 0) / forecastData.points.length;
    return mean.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
  });

  const ciLowerMeanDisplay = $derived.by((): string => {
    if (!forecastData || forecastData.points.length === 0) return '—';
    const mean = forecastData.points.reduce((s, p) => s + p.ciLower, 0) / forecastData.points.length;
    return mean.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
  });

  const ciUpperMeanDisplay = $derived.by((): string => {
    if (!forecastData || forecastData.points.length === 0) return '—';
    const mean = forecastData.points.reduce((s, p) => s + p.ciUpper, 0) / forecastData.points.length;
    return mean.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
  });

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
        // 🔴 Внешний аудит 2026-07-29 (High): ОБА этих значения подставлены, а не измерены —
        // вместе они дают 40 pt из 100 и диагностики «Сошлось» и «100.0% от минимума».
        // Первая правка блока говорила только о сходимости; достаточность данных так же не
        // проверялась (nRecipient есть в данных и не используется), поэтому оговорка ниже
        // называет обе. Числовой вклад не трогаем — это отдельное, ранее принятое решение.
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
        <ChartWithDrillDown
          formulaKey="conformal_prediction_interval"
          chartTitle={$_('inspector.forecast.chart_title', { default: 'Прогноз с доверительным интервалом' })}
        >
          {#snippet children()}
            <ForecastCone
              points={forecastData.points}
              horizonWeeks={forecastData.horizonWeeks}
              width={620}
              height={300}
              title="Forecast cone (saved)"
            />
          {/snippet}
        </ChartWithDrillDown>
        <dl class="forecast-summary-stats">
          <div class="forecast-stat">
            <dt>{$_('inspector.forecast.stat_point_mean', { default: 'Средний прогноз' })}</dt>
            <dd>
              <NumberWithDrillDown
                formulaKey="forecast_baseline_projection"
                value={pointMeanDisplay}
              />
            </dd>
          </div>
          <div class="forecast-stat">
            <dt>{$_('inspector.forecast.stat_ci_lower', { default: 'CI нижняя граница (ср.)' })}</dt>
            <dd>
              <NumberWithDrillDown
                formulaKey="conformal_prediction_interval"
                value={ciLowerMeanDisplay}
              />
            </dd>
          </div>
          <div class="forecast-stat">
            <dt>{$_('inspector.forecast.stat_ci_upper', { default: 'CI верхняя граница (ср.)' })}</dt>
            <dd>
              <NumberWithDrillDown
                formulaKey="conformal_prediction_interval"
                value={ciUpperMeanDisplay}
              />
            </dd>
          </div>
        </dl>
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
            {:else}
              <div class="trust-preview-badge" role="note">
                <span class="badge-icon" aria-hidden="true">📊</span>
                <span class="badge-text">{trustDisclaimerText}</span>
              </div>
            {/if}
            <TrustScore
              score={trustResult.score}
              verdict={trustResult.tier}
              diagnostics={trustResult.diagnostics}
              showAdvancedDiagnostics={!trustIsRealCompute}
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
  .forecast-summary-stats {
    display: flex;
    gap: var(--spacing-4, 1rem);
    flex-wrap: wrap;
    margin: var(--spacing-3, 0.75rem) 0 0 0;
    padding: var(--spacing-3, 0.75rem);
    background: color-mix(in srgb, var(--bg-elevated, #F0F2F7) 60%, transparent);
    border-radius: 6px;
  }
  .forecast-stat {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .forecast-stat dt {
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
    color: var(--text-muted, #6b7280);
    font-weight: 400;
  }
  .forecast-stat dd {
    margin: 0;
    font-family: var(--font-mono, monospace);
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    font-weight: 600;
    color: var(--text-primary, #111827);
  }
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
