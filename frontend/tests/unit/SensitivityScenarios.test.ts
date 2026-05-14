import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';

import SensitivityScenarios from '../../src/lib/components/SensitivityScenarios.svelte';

beforeEach(() => cleanup());

// Canonical 3-card dataset matching the spec.
const THREE_SCENARIOS = [
  {
    name: 'pessimistic' as const,
    title: 'Пессимистичный',
    description: 'Худший правдоподобный сценарий',
    pointForecastFormatted: '1 200 000',
    ciLowerFormatted: '900 000',
    ciUpperFormatted: '1 500 000',
    deltaPctVsBase: -18.5,
  },
  {
    name: 'base' as const,
    title: 'Базовый',
    description: 'Текущие параметры',
    pointForecastFormatted: '1 470 000',
    ciLowerFormatted: '1 100 000',
    ciUpperFormatted: '1 840 000',
    deltaPctVsBase: 0,
  },
  {
    name: 'optimistic' as const,
    title: 'Оптимистичный',
    description: 'Лучший правдоподобный сценарий',
    pointForecastFormatted: '1 750 000',
    ciLowerFormatted: '1 350 000',
    ciUpperFormatted: '2 150 000',
    deltaPctVsBase: 19.0,
  },
];

function defaultProps(overrides: Record<string, unknown> = {}) {
  return {
    scenarios: THREE_SCENARIOS,
    selected: 'base' as const,
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
    const expertBtn = screen.getByText(/Expert mode/i);
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
});
