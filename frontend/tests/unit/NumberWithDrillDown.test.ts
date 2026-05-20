// Vitest tests for NumberWithDrillDown.svelte — Sprint 3 A18 two-tier transparency UX.
//
// Protects invariants:
//   INV-48 — test-first attack scenario coverage.
//   Sprint 3 A18 — value span (role=button) + info button affordance, graceful
//                  degradation for unknown formulaKey, keyboard activation,
//                  tooltip text = first sentence of explanation.

import { describe, expect, it, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';

// Mock KaTeX to prevent CSS errors in jsdom (DrillDownModal imports katex)
vi.mock('katex', () => ({
  default: {
    render: vi.fn((latex: string, container: HTMLElement) => {
      container.innerHTML = '<span class="katex">' + latex + '</span>';
    }),
  },
}));
vi.mock('katex/dist/katex.min.css', () => ({}));

import NumberWithDrillDown from '../../src/lib/components/transparency/NumberWithDrillDown.svelte';
import { getFormula } from '../../src/lib/utils/formulas';

beforeEach(() => cleanup());

// ---------------------------------------------------------------------------
// Shared fixtures — real formulas from registry
// ---------------------------------------------------------------------------

const KNOWN_KEY = 'trust_score_8d';
const UNKNOWN_KEY = 'formula_that_does_not_exist_xyz';
const formula = getFormula(KNOWN_KEY)!;

/** Expected first sentence of formula explanation (same logic as component). */
function firstSentence(text: string): string {
  const dot = text.indexOf('.');
  return dot !== -1 ? text.slice(0, dot + 1) : text;
}

/** Flush microtasks — for $effect (KaTeX inside DrillDownModal). */
async function flushAsync() {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

// ---------------------------------------------------------------------------
// Graceful degradation — unknown formulaKey
// ---------------------------------------------------------------------------

describe('NumberWithDrillDown — деградация при неизвестном ключе', () => {
  it('рендерит только <span> с value когда formulaKey неизвестен', () => {
    const { container } = render(NumberWithDrillDown, {
      formulaKey: UNKNOWN_KEY,
      value: '99,9%',
    });

    // Should be a plain span containing value text
    expect(container.textContent).toContain('99,9%');
  });

  it('НЕ рендерит .number-drill-info кнопку при неизвестном ключе', () => {
    const { container } = render(NumberWithDrillDown, {
      formulaKey: UNKNOWN_KEY,
      value: '99,9%',
    });

    expect(container.querySelector('.number-drill-info')).toBeNull();
  });

  it('НЕ рендерит .number-drill-value span при неизвестном ключе', () => {
    const { container } = render(NumberWithDrillDown, {
      formulaKey: UNKNOWN_KEY,
      value: '99,9%',
    });

    expect(container.querySelector('.number-drill-value')).toBeNull();
  });

  it('НЕ рендерит DrillDownModal при неизвестном ключе', () => {
    render(NumberWithDrillDown, {
      formulaKey: UNKNOWN_KEY,
      value: '99,9%',
    });

    expect(screen.queryByRole('dialog')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Known formulaKey — renders value + info button
// ---------------------------------------------------------------------------

describe('NumberWithDrillDown — известный formulaKey', () => {
  it('рендерит .number-drill-value (role=button) со значением', () => {
    const { container } = render(NumberWithDrillDown, {
      formulaKey: KNOWN_KEY,
      value: '0.87',
    });

    const valueSpan = container.querySelector('.number-drill-value');
    expect(valueSpan).not.toBeNull();
    expect(valueSpan!.getAttribute('role')).toBe('button');
    expect(valueSpan!.textContent).toBe('0.87');
  });

  it('рендерит .number-drill-info кнопку', () => {
    const { container } = render(NumberWithDrillDown, {
      formulaKey: KNOWN_KEY,
      value: '0.87',
    });

    const infoBtn = container.querySelector('.number-drill-info');
    expect(infoBtn).not.toBeNull();
  });

  it('value span имеет корректный aria-label с interpolated value', () => {
    const { container } = render(NumberWithDrillDown, {
      formulaKey: KNOWN_KEY,
      value: '0.87',
    });

    const valueSpan = container.querySelector('.number-drill-value');
    const ariaLabel = valueSpan!.getAttribute('aria-label') ?? '';
    expect(ariaLabel).toContain('0.87');
  });

  it('info button имеет aria-label с formula.title', () => {
    const { container } = render(NumberWithDrillDown, {
      formulaKey: KNOWN_KEY,
      value: '0.87',
    });

    const infoBtn = container.querySelector('.number-drill-info');
    const ariaLabel = infoBtn!.getAttribute('aria-label') ?? '';
    expect(ariaLabel).toContain(formula.title);
  });
});

// ---------------------------------------------------------------------------
// Modal opening — click interactions
// ---------------------------------------------------------------------------

describe('NumberWithDrillDown — открытие модалки кликом', () => {
  it('клик по .number-drill-value открывает DrillDownModal (role=dialog)', async () => {
    const { container } = render(NumberWithDrillDown, {
      formulaKey: KNOWN_KEY,
      value: '0.87',
    });

    const valueSpan = container.querySelector('.number-drill-value')!;
    await fireEvent.click(valueSpan);
    await flushAsync();

    expect(screen.queryByRole('dialog')).not.toBeNull();
  });

  it('клик по .number-drill-info открывает DrillDownModal', async () => {
    const { container } = render(NumberWithDrillDown, {
      formulaKey: KNOWN_KEY,
      value: '0.87',
    });

    const infoBtn = container.querySelector('.number-drill-info')!;
    await fireEvent.click(infoBtn);
    await flushAsync();

    expect(screen.queryByRole('dialog')).not.toBeNull();
  });

  it('DrillDownModal содержит formula.title после открытия', async () => {
    const { container } = render(NumberWithDrillDown, {
      formulaKey: KNOWN_KEY,
      value: '0.87',
    });

    await fireEvent.click(container.querySelector('.number-drill-value')!);
    await flushAsync();

    expect(screen.queryByText(formula.title, { exact: false })).not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Modal opening — keyboard interactions
// ---------------------------------------------------------------------------

describe('NumberWithDrillDown — открытие модалки клавиатурой', () => {
  it('Enter на value span открывает модалку', async () => {
    const { container } = render(NumberWithDrillDown, {
      formulaKey: KNOWN_KEY,
      value: '0.87',
    });

    const valueSpan = container.querySelector('.number-drill-value')!;
    await fireEvent.keyDown(valueSpan, { key: 'Enter' });
    await flushAsync();

    expect(screen.queryByRole('dialog')).not.toBeNull();
  });

  it('Space на value span открывает модалку', async () => {
    const { container } = render(NumberWithDrillDown, {
      formulaKey: KNOWN_KEY,
      value: '0.87',
    });

    const valueSpan = container.querySelector('.number-drill-value')!;
    await fireEvent.keyDown(valueSpan, { key: ' ' });
    await flushAsync();

    expect(screen.queryByRole('dialog')).not.toBeNull();
  });

  it('другие клавиши (например "a") НЕ открывают модалку', async () => {
    const { container } = render(NumberWithDrillDown, {
      formulaKey: KNOWN_KEY,
      value: '0.87',
    });

    const valueSpan = container.querySelector('.number-drill-value')!;
    await fireEvent.keyDown(valueSpan, { key: 'a' });
    await flushAsync();

    expect(screen.queryByRole('dialog')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Tooltip text
// ---------------------------------------------------------------------------

describe('NumberWithDrillDown — tooltip text', () => {
  it('data-tooltip на .number-drill равен первому предложению explanation', () => {
    const { container } = render(NumberWithDrillDown, {
      formulaKey: KNOWN_KEY,
      value: '0.87',
    });

    const wrapper = container.querySelector('.number-drill');
    expect(wrapper).not.toBeNull();

    const tooltip = wrapper!.getAttribute('data-tooltip');
    const expected = firstSentence(formula.explanation);
    expect(tooltip).toBe(expected);
  });

  it('firstSentence регрессия — обрезает по первой точке включительно', () => {
    // Regression test for `dot = explanation.indexOf('.')` + slice(0, dot+1) logic
    const text = 'Первое предложение. Второе предложение.';
    expect(firstSentence(text)).toBe('Первое предложение.');
  });

  it('firstSentence регрессия — возвращает полный текст если точки нет', () => {
    const text = 'Нет точки здесь';
    expect(firstSentence(text)).toBe('Нет точки здесь');
  });

  it('tooltip для similarity_jensen_shannon содержит только первое предложение', () => {
    const key = 'similarity_jensen_shannon';
    const f = getFormula(key)!;
    const { container } = render(NumberWithDrillDown, { formulaKey: key, value: '92%' });

    const wrapper = container.querySelector('.number-drill');
    const tooltip = wrapper!.getAttribute('data-tooltip');
    expect(tooltip).toBe(firstSentence(f.explanation));
    // Must NOT include the second sentence
    const secondDotPos = f.explanation.indexOf('.', f.explanation.indexOf('.') + 1);
    if (secondDotPos !== -1) {
      expect(tooltip!.length).toBeLessThan(f.explanation.length);
    }
  });
});
