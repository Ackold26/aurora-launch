import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';

import SensitivityScenarios from '../../src/lib/components/SensitivityScenarios.svelte';

beforeEach(() => cleanup());

// Canonical 3-card dataset matching the P-04 raw-numbers schema.
const THREE_SCENARIOS = [
  {
    name: 'pessimistic' as const,
    title: 'Пессимистичный',
    description: 'Худший правдоподобный сценарий',
    pointForecast: 1_200_000,
    ciLower: 900_000,
    ciUpper: 1_500_000,
    deltaPctVsBase: -18.5,
  },
  {
    name: 'base' as const,
    title: 'Базовый',
    description: 'Текущие параметры',
    pointForecast: 1_470_000,
    ciLower: 1_100_000,
    ciUpper: 1_840_000,
    deltaPctVsBase: 0,
  },
  {
    name: 'optimistic' as const,
    title: 'Оптимистичный',
    description: 'Лучший правдоподобный сценарий',
    pointForecast: 1_750_000,
    ciLower: 1_350_000,
    ciUpper: 2_150_000,
    deltaPctVsBase: 19.0,
  },
];

function defaultProps(overrides: Record<string, unknown> = {}) {
  return {
    scenarios: THREE_SCENARIOS,
    selected: 'base' as const,
    currency: 'units' as const, // simpler text matches без currency symbols
    ...overrides,
  };
}

describe('SensitivityScenarios', () => {
  // ---------- rendering ----------

  it('renders 3 scenario cards', () => {
    render(SensitivityScenarios, defaultProps());
    // All 3 scenario titles must appear
    expect(screen.getByText('Пессимистичный')).toBeTruthy();
    expect(screen.getByText('Базовый')).toBeTruthy();
    expect(screen.getByText('Оптимистичный')).toBeTruthy();
  });

  // ---------- selected state ----------

  it('selected="base" → base card has aria-pressed="true"', () => {
    render(SensitivityScenarios, defaultProps({ selected: 'base' }));
    // The base card button should have aria-pressed=true
    const buttons = screen.getAllByRole('button');
    // Expert mode button + 3 scenario buttons; scenario buttons have aria-pressed attr
    const scenarioButtons = buttons.filter(
      (b) => b.hasAttribute('aria-pressed')
    );
    const baseBtn = scenarioButtons.find((b) =>
      b.textContent?.includes('Базовый')
    );
    expect(baseBtn).toBeTruthy();
    expect(baseBtn!.getAttribute('aria-pressed')).toBe('true');
  });

  it('non-selected cards have aria-pressed="false"', () => {
    render(SensitivityScenarios, defaultProps({ selected: 'base' }));
    const buttons = screen.getAllByRole('button');
    const scenarioButtons = buttons.filter((b) => b.hasAttribute('aria-pressed'));
    const pessBtn = scenarioButtons.find((b) =>
      b.textContent?.includes('Пессимистичный')
    );
    expect(pessBtn!.getAttribute('aria-pressed')).toBe('false');
  });

  // ---------- callbacks ----------

  it('click pessimistic card → onSelectScenario called with "pessimistic"', async () => {
    const onSelect = vi.fn();
    render(SensitivityScenarios, defaultProps({ onSelectScenario: onSelect }));
    const buttons = screen.getAllByRole('button');
    const pessBtn = buttons.find(
      (b) => b.hasAttribute('aria-pressed') && b.textContent?.includes('Пессимистичный')
    );
    await fireEvent.click(pessBtn!);
    expect(onSelect).toHaveBeenCalledOnce();
    expect(onSelect).toHaveBeenCalledWith('pessimistic');
  });

  it('click "Expert mode" button → onSwitchToExpert called', async () => {
    const onSwitch = vi.fn();
    render(SensitivityScenarios, defaultProps({ onSwitchToExpert: onSwitch }));
    const expertBtn = screen.getByText(/Expert mode|Расширенные параметры/i);
    await fireEvent.click(expertBtn);
    expect(onSwitch).toHaveBeenCalledOnce();
  });

  // ---------- delta badge ----------

  it('pessimistic card shows negative delta badge', () => {
    render(SensitivityScenarios, defaultProps());
    // deltaPctVsBase = -18.5 → "-18.5% vs Base"
    expect(screen.getByText('-18.5% vs Base')).toBeTruthy();
  });

  it('optimistic card shows positive delta badge with + prefix', () => {
    render(SensitivityScenarios, defaultProps());
    // deltaPctVsBase = 19.0 → "+19.0% vs Base"
    expect(screen.getByText('+19.0% vs Base')).toBeTruthy();
  });

  it('pessimistic delta has data-direction="down"', () => {
    render(SensitivityScenarios, defaultProps());
    const delta = screen.getByText('-18.5% vs Base');
    expect(delta.getAttribute('data-direction')).toBe('down');
  });

  it('optimistic delta has data-direction="up"', () => {
    render(SensitivityScenarios, defaultProps());
    const delta = screen.getByText('+19.0% vs Base');
    expect(delta.getAttribute('data-direction')).toBe('up');
  });

  it('base card has no delta badge', () => {
    render(SensitivityScenarios, defaultProps());
    // deltaPctVsBase=0 but name="base" → no delta rendered at all
    // Verify by checking no "0.0% vs Base" text exists
    expect(screen.queryByText(/0\.0% vs Base/)).toBeNull();
  });

  // ---------- keyboard / accessibility ----------

  it('all 3 scenario cards are keyboard-navigable buttons', () => {
    render(SensitivityScenarios, defaultProps());
    const buttons = screen.getAllByRole('button');
    const scenarioButtons = buttons.filter((b) => b.hasAttribute('aria-pressed'));
    expect(scenarioButtons).toHaveLength(3);
    scenarioButtons.forEach((btn) => {
      expect(btn.tagName.toLowerCase()).toBe('button');
    });
  });

  // ---------- P-04 raw-numbers + formatting ----------

  it('renders raw point forecast number formatted as Russian locale', () => {
    render(SensitivityScenarios, defaultProps({ currency: 'units' }));
    // Russian locale: 1 200 000 (с non-breaking spaces or regular spaces)
    // Intl.NumberFormat ru-RU uses NBSP ( ). Test через текст что contains 1, 200, 000.
    const items = screen.getAllByText(/1\s?200\s?000/);
    expect(items.length).toBeGreaterThan(0);
  });

  it('currency="RUB" renders ₽ symbol', () => {
    render(SensitivityScenarios, defaultProps({ currency: 'RUB' }));
    // narrowSymbol gives ₽
    const text = document.body.textContent || '';
    expect(text).toMatch(/₽|RUB/);
  });

  it('currency="USD" renders $ symbol', () => {
    render(SensitivityScenarios, defaultProps({ currency: 'USD' }));
    const text = document.body.textContent || '';
    expect(text).toMatch(/\$|USD/);
  });

  it('currency="units" renders без currency symbol', () => {
    render(SensitivityScenarios, defaultProps({ currency: 'units' }));
    const text = document.body.textContent || '';
    expect(text).not.toMatch(/₽|\$|€/);
  });

  it('notation="compact" produces shorter representation', () => {
    render(SensitivityScenarios, defaultProps({ currency: 'units', notation: 'compact' }));
    // ru-RU compact для 1_200_000 → "1,2 млн"
    const text = document.body.textContent || '';
    expect(text).toMatch(/млн|M/);
  });

  it('handles non-finite values gracefully (NaN → "—")', () => {
    const scenarios = [
      {
        name: 'pessimistic' as const,
        title: 'Пессимистичный',
        description: 'Test',
        pointForecast: NaN,
        ciLower: NaN,
        ciUpper: NaN,
        deltaPctVsBase: 0,
      },
    ];
    render(SensitivityScenarios, { scenarios, currency: 'units' });
    // Дефис-длинный (—) returned для NaN
    const dashes = screen.getAllByText('—');
    expect(dashes.length).toBeGreaterThan(0);
  });
});
