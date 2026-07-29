// Vitest tests for ForecastTab.svelte — exec-launch-trust (2026-07-29),
// расширено audit findings fix (2026-07-29, fix/audit-findings-72).
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
//
// 🔴 Приёмка audit findings (2026-07-29): причина оговорки раньше читалась из
// engineMode (заказанный режим), а не из фактически исполненного пути —
// methodologySignature. Ниже добавлены сценарии на fallback-выходы
// (байесовский расчёт не состоялся → перенос) и на регрессию по данным
// клиента (ols_with_proxy_priors_v1 — это НЕ перенос). HONEST_TRANSFER_NOTE
// сужен до общего префикса всех пяти утверждённых текстов, т.к. конкретная
// причина теперь варьируется по сценарию.

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

// 🔴 audit findings (2026-07-29): общий префикс утверждённых клиентских текстов —
// присутствует во всех пяти вариантах оговорки (перенос / байес-аналитика /
// байес-fallback / регрессия / метод неизвестен), поэтому годится как базовая
// проверка "оговорка вообще показана" независимо от конкретной причины.
const HONEST_TRANSFER_NOTE = 'Диагностика сходимости не выполнялась';

function baseForecastData(
  engineMode: ForecastData['engineMode'],
  methodologySignature = 'test-signature',
): ForecastData {
  return {
    points: [
      { weekIndex: 0, point: 1000, ciLower: 900, ciUpper: 1100 },
      { weekIndex: 1, point: 1050, ciLower: 940, ciUpper: 1160 },
    ],
    horizonWeeks: 2,
    engineMode,
    methodologySignature,
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

  it('bayesian_with_proxy_priors: сэмплирования там тоже нет → оговорка показана, но с другой причиной', async () => {
    // 🔴 Приёмка 2026-07-29. Прежний контракт этого теста был обратным: в
    // байесовском режиме оговорка не показывалась вовсе. Проверка по коду
    // движка показала, что режим bayesian_with_proxy_priors ведёт в
    // АНАЛИТИЧЕСКИЙ байес (`engines/bayesian_with_priors.py:183` —
    // `r_hat=1.0, # analytical Gaussian → perfect convergence by construction`),
    // MCMC-цепей нет ни здесь, ни в режимах переноса. Значит подставленная
    // единица одинаково недоказана во всех режимах бандла, и молчание в
    // байесовской ветке было бы тем же нарушением INV-50, только реже
    // заметным. Оговорка обязана стоять всегда — меняется её причина.
    mockForecastIpc();
    render(ForecastTab, {
      forecastData: baseForecastData('bayesian_with_proxy_priors'),
      loading: false,
      similarityScore: 0.82,
      verificationValid: true,
    });
    await flushAsync();

    expect(screen.getByText(new RegExp(HONEST_TRANSFER_NOTE))).toBeTruthy();
    expect(screen.getByText(/получено аналитически, без сэмплирования/)).toBeTruthy();
    // И причина переноса в этом режиме звучать НЕ должна — иначе оговорка
    // объясняет клиенту не то, что произошло.
    expect(screen.queryByText(/прогноз построен методом переноса/)).toBeNull();
  });

  // 🔴 Новые сценарии — audit findings (2026-07-29, fix/audit-findings-72).
  // Разведка нашла: причина оговорки бралась из engineMode (заказанного режима),
  // а не из methodologySignature (фактически исполненного пути). У байесовского
  // и OLS-режимов есть fallback-выходы в dispatch_table.py, где engineMode
  // остаётся прежним, а сигнатура называет то, что случилось на самом деле.

  it('байесовский fallback (engineMode остался bayesian, но сигнатура — fallback): оговорка про несостоявшийся байесовский расчёт, НЕ про аналитический апостериор', async () => {
    mockForecastIpc();
    render(ForecastTab, {
      // engine_config.mode всё ещё 'bayesian_with_proxy_priors' (заказан байес),
      // но dispatch_table.py:483 вернул fallback-сигнатуру — recipient_y/
      // historical_spend не хватило, апостериор не строился, реально
      // выполнился чистый перенос.
      forecastData: baseForecastData('bayesian_with_proxy_priors', 'bayesian_with_proxy_priors_fallback_v1'),
      loading: false,
      similarityScore: 0.82,
      verificationValid: true,
    });
    await flushAsync();

    expect(screen.getByText(new RegExp(HONEST_TRANSFER_NOTE))).toBeTruthy();
    expect(screen.getByText(/байесовский расчёт не состоялся, прогноз построен методом переноса/)).toBeTruthy();
    // Аналитический апостериор в этом случае НЕ строился — текст не должен
    // утверждать обратное (это ровно тот дефект, что нашёл аудит).
    expect(screen.queryByText(/получено аналитически/)).toBeNull();
  });

  it('регрессия по данным клиента (ols_with_proxy_priors_v1, реальный фит): текст про МНК с опорными значениями, а НЕ про перенос', async () => {
    mockForecastIpc();
    render(ForecastTab, {
      // dispatch_table.py:407 — реальный ridge-фит на recipient_y, это НЕ перенос,
      // хотя engineMode называется так же, как и fallback-вариант того же режима.
      forecastData: baseForecastData('ols_with_proxy_priors', 'ols_with_proxy_priors_v1'),
      loading: false,
      similarityScore: 0.82,
      verificationValid: true,
    });
    await flushAsync();

    expect(screen.getByText(new RegExp(HONEST_TRANSFER_NOTE))).toBeTruthy();
    expect(screen.getByText(/оценена по вашим данным методом наименьших квадратов с опорными значениями/)).toBeTruthy();
    // "Перенос" в этом случае — неверное название метода (регрессия реально
    // подгонялась по данным получателя, это не пассивное масштабирование).
    expect(screen.queryByText(/прогноз построен методом переноса/)).toBeNull();
  });

  it('сигнатуры нет и режим неизвестен: оговорка не называет никакой метод', async () => {
    mockForecastIpc();
    render(ForecastTab, {
      // methodologySignature отсутствует (напр. legacy-бандл, нормализованный
      // forecast_bundle.py::_normalize_legacy_to_v1 c methodology_signature=""),
      // engineMode тоже undefined — определить метод нечем.
      forecastData: baseForecastData(undefined, ''),
      loading: false,
      similarityScore: 0.82,
      verificationValid: true,
    });
    await flushAsync();

    expect(screen.getByText(new RegExp(HONEST_TRANSFER_NOTE))).toBeTruthy();
    expect(screen.getByText(/метод расчёта в сохранённом прогнозе не указан/)).toBeTruthy();
    // Ни одна конкретная причина не должна называться — метод неизвестен.
    expect(screen.queryByText(/прогноз построен методом переноса/)).toBeNull();
    expect(screen.queryByText(/получено аналитически/)).toBeNull();
    expect(screen.queryByText(/наименьших квадратов/)).toBeNull();
  });
});
