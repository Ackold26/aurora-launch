// Vitest tests for ForecastTab.svelte — exec-launch-trust (2026-07-29).
//
// Guards INV-50 (честность метрик): в режиме переноса (pure_transfer /
// transfer_with_bias_check / ols_with_proxy_priors) MCMC-сэмплинг не
// запускается, значит R̂/ESS физически не вычисляются. computeTrustForBundle()
// шлёт model_convergence_passed=1 как консервативный дефолт (см. комментарий
// в компоненте + backend trust_score_project.extract_model_convergence), но
// интерфейс обязан прямо сказать, что диагностика не выполнялась — а не
// молчать, оставляя клиента с одним только зелёным числом/tier.
//
// Красный прогон этого теста доказывается вручную (см. отчёт
// D:\Docs\Aurora_Ai\Projects\exec_launch_trust_report.md): временно убрать
// {:else if mcmcDiagnosticsNotApplicable} ветку в ForecastTab.svelte.

import { describe, expect, it, beforeEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';

import ForecastTab from '../../src/lib/components/inspector/ForecastTab.svelte';
import { __setForecastInvokeForTesting } from '../../src/lib/ipc/forecast';
import type { ForecastData } from '../../src/lib/components/inspector/types';
import type { TrustScoreResult } from '../../src/lib/ipc/forecast';

beforeEach(() => cleanup());

/** Flush microtasks — for IPC await + $effect/$derived state updates. */
async function flushAsync() {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

const HONEST_TRANSFER_NOTE = 'Диагностика сходимости не выполнялась';

function baseForecastData(engineMode: ForecastData['engineMode']): ForecastData {
  return {
    points: [
      { weekIndex: 0, point: 1000, ciLower: 900, ciUpper: 1100 },
      { weekIndex: 1, point: 1050, ciLower: 940, ciUpper: 1160 },
    ],
    horizonWeeks: 2,
    engineMode,
    methodologySignature: 'test-signature',
    warnings: [],
    nRecipient: 500,
    granularity: 'weekly',
    anchors: null,
    spendPlan: null,
  };
}

/** Trust score IPC response shaped like the real compute_trust_score handler —
 * includes the "Сошлось (R̂ < 1.05, ESS > 400)" diagnostic that
 * _convergence_diagnostic (trust_score.py) produces for model_convergence_passed=1,
 * so the test exercises the actual honesty gap, not a synthetic stand-in. */
function mockTrustScoreResult(): TrustScoreResult {
  return {
    score: 82,
    tier: 'Высокий',
    diagnostics: [
      { label: 'Similarity подобие', value: '82.0%  →  24.6 pt', status: 'good' },
      { label: 'Сертификат методологии', value: 'Подтверждён  →  20.0 pt', status: 'good' },
      { label: 'Сходимость модели', value: 'Сошлось (R̂ < 1.05, ESS > 400)  →  20.0 pt', status: 'good' },
      { label: 'Достаточность данных', value: '100.0% от минимума  →  20.0 pt', status: 'good' },
      { label: 'Точность прогноза (ширина ДИ)', value: 'Инверсия 80.0%  →  8.0 pt', status: 'good' },
    ],
  };
}

function mockForecastIpc() {
  __setForecastInvokeForTesting(async (cmd: string) => {
    if (cmd === 'compute_trust_score') return mockTrustScoreResult();
    if (cmd === 'explain_forecast') {
      return { what: '', why: '', risks: '', engine_used: 'local', confidence: 'high' };
    }
    throw new Error(`Unmocked forecast IPC in test: ${cmd}`);
  });
}

describe('ForecastTab — честность диагностики сходимости (INV-50)', () => {
  it('pure_transfer: показывает прямую оговорку "диагностика не выполнялась", а не молчаливое зелёное значение', async () => {
    mockForecastIpc();
    render(ForecastTab, {
      forecastData: baseForecastData('pure_transfer'),
      loading: false,
      similarityScore: 0.82,
      verificationValid: true,
    });
    await flushAsync();

    expect(screen.getByText(new RegExp(HONEST_TRANSFER_NOTE))).toBeTruthy();
  });

  it('ols_with_proxy_priors: тоже не запускает MCMC → та же честная оговорка', async () => {
    mockForecastIpc();
    render(ForecastTab, {
      forecastData: baseForecastData('ols_with_proxy_priors'),
      loading: false,
      similarityScore: 0.82,
      verificationValid: true,
    });
    await flushAsync();

    expect(screen.getByText(new RegExp(HONEST_TRANSFER_NOTE))).toBeTruthy();
  });

  it('engineMode не определён (undefined): консервативно тоже считается "MCMC не подтверждён" → оговорка показана', async () => {
    mockForecastIpc();
    render(ForecastTab, {
      forecastData: baseForecastData(undefined),
      loading: false,
      similarityScore: 0.82,
      verificationValid: true,
    });
    await flushAsync();

    expect(screen.getByText(new RegExp(HONEST_TRANSFER_NOTE))).toBeTruthy();
  });

  it('bayesian_with_proxy_priors: MCMC применим для этого режима → оговорка НЕ показывается', async () => {
    mockForecastIpc();
    render(ForecastTab, {
      forecastData: baseForecastData('bayesian_with_proxy_priors'),
      loading: false,
      similarityScore: 0.82,
      verificationValid: true,
    });
    await flushAsync();

    expect(screen.queryByText(new RegExp(HONEST_TRANSFER_NOTE))).toBeNull();
  });
});
