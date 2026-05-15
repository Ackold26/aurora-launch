// Vitest tests для DailyInsightBanner (Phase Magic M-07 banner).
// Use forceInsight prop к bypass projectsStore.refresh + suppress check.

import { describe, expect, it, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';
import DailyInsightBanner from '../../src/lib/components/DailyInsightBanner.svelte';
import type { DailyInsight } from '../../src/lib/services/daily-insights';

// Stub @sveltejs/kit's goto — keep external nav out of jsdom
vi.mock('$app/navigation', () => ({
  goto: vi.fn(),
}));

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  try {
    window.localStorage.clear();
  } catch {
    /* ignore */
  }
});

const sampleInsight: DailyInsight = {
  id: 'stale_forecast',
  severity: 'info',
  title: 'Прогноз «Кагоцел» создан 20 дней назад',
  body: 'Aurora накопила достаточно времени для свежей оценки.',
  cta: 'Открыть проект',
  ctaHref: '/project/abc/history',
  projectUuid: 'abc',
};

describe('DailyInsightBanner', () => {
  it('renders insight с forceInsight prop', () => {
    render(DailyInsightBanner, { forceInsight: sampleInsight });
    expect(screen.getByText(/Прогноз «Кагоцел»/)).toBeTruthy();
    expect(screen.getByText(/достаточно времени/)).toBeTruthy();
  });

  it('renders CTA button', () => {
    render(DailyInsightBanner, { forceInsight: sampleInsight });
    expect(screen.getByText('Открыть проект')).toBeTruthy();
  });

  it('renders dismiss button с aria-label', () => {
    render(DailyInsightBanner, { forceInsight: sampleInsight });
    const dismiss = screen.getByLabelText('Скрыть на сегодня');
    expect(dismiss).toBeTruthy();
  });

  it('dismiss hides banner', async () => {
    render(DailyInsightBanner, { forceInsight: sampleInsight });
    const dismiss = screen.getByLabelText('Скрыть на сегодня');
    await fireEvent.click(dismiss);
    expect(screen.queryByText(/Прогноз «Кагоцел»/)).toBeNull();
  });

  it('dismiss persists suppression к localStorage', async () => {
    render(DailyInsightBanner, { forceInsight: sampleInsight });
    await fireEvent.click(screen.getByLabelText('Скрыть на сегодня'));
    const stored = window.localStorage.getItem('aurora.last-insight-shown');
    expect(stored).toBeTruthy();
    expect(stored).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it('null forceInsight hides banner', () => {
    render(DailyInsightBanner, { forceInsight: null });
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('warning severity shows correct icon and class', () => {
    const warningInsight: DailyInsight = {
      ...sampleInsight,
      severity: 'warning',
      id: 'very_stale_forecast',
    };
    const { container } = render(DailyInsightBanner, { forceInsight: warningInsight });
    expect(container.querySelector('.severity-warning')).toBeTruthy();
    expect(screen.getByText('⚠️')).toBeTruthy();
  });

  it('success severity shows sparkle icon', () => {
    const successInsight: DailyInsight = {
      ...sampleInsight,
      severity: 'success',
      id: 'power_user_cross_sell',
    };
    render(DailyInsightBanner, { forceInsight: successInsight });
    expect(screen.getByText('✨')).toBeTruthy();
  });

  it('info severity shows lightbulb icon', () => {
    render(DailyInsightBanner, { forceInsight: sampleInsight });
    expect(screen.getByText('💡')).toBeTruthy();
  });

  it('CTA without href omits CTA button', () => {
    // exactOptionalPropertyTypes: use Omit to drop optional fields instead of
    // setting them to undefined (which is disallowed for optional properties).
    const { cta: _cta, ctaHref: _ctaHref, ...rest } = sampleInsight;
    const noCta: DailyInsight = rest;
    render(DailyInsightBanner, { forceInsight: noCta });
    expect(screen.queryByText('Открыть проект')).toBeNull();
  });

  it('clicking internal CTA fires goto + dismisses banner', async () => {
    const { goto } = await import('$app/navigation');
    render(DailyInsightBanner, { forceInsight: sampleInsight });
    const cta = screen.getByText('Открыть проект');
    await fireEvent.click(cta);
    expect(goto).toHaveBeenCalledWith('/project/abc/history');
    expect(screen.queryByText('Открыть проект')).toBeNull();
  });

  it('external CTA (https://) opens new window вместо goto', async () => {
    const original = window.open;
    window.open = vi.fn();
    const externalInsight: DailyInsight = {
      ...sampleInsight,
      ctaHref: 'https://auroraai.pro/brand-tracker',
      cta: 'Узнать больше',
    };
    render(DailyInsightBanner, { forceInsight: externalInsight });
    await fireEvent.click(screen.getByText('Узнать больше'));
    expect(window.open).toHaveBeenCalledWith(
      'https://auroraai.pro/brand-tracker',
      '_blank',
      'noopener,noreferrer',
    );
    window.open = original;
  });
});
