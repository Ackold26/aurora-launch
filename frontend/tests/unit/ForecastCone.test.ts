// Vitest tests for ForecastCone.svelte — a11y + data table toggle (M-10).

import { describe, expect, it, beforeEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';

import ForecastCone from '../../src/lib/components/ForecastCone.svelte';

beforeEach(() => cleanup());

// ---------------------------------------------------------------------------
// Shared fixtures
// ---------------------------------------------------------------------------

function makePoints(count: number) {
  return Array.from({ length: count }, (_, i) => ({
    weekIndex: i,
    point: 50 + i * 2,
    ciLower: 40 + i * 2,
    ciUpper: 60 + i * 2,
  }));
}

function defaultProps(overrides: Record<string, unknown> = {}) {
  return {
    points: makePoints(4),
    horizonWeeks: 4,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

describe('ForecastCone — empty state', () => {
  it('renders accessible empty message when points is empty', () => {
    render(ForecastCone, defaultProps({ points: [] }));
    const msg = screen.getByRole('status');
    expect(msg.textContent).toContain('Нет данных прогноза');
  });

  it('does not render SVG when points is empty', () => {
    const { container } = render(ForecastCone, defaultProps({ points: [] }));
    expect(container.querySelector('svg')).toBeNull();
  });

  it('does not render toggle button when points is empty', () => {
    render(ForecastCone, defaultProps({ points: [] }));
    expect(screen.queryByRole('button')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// SVG accessibility metadata
// ---------------------------------------------------------------------------

describe('ForecastCone — SVG a11y attributes', () => {
  it('SVG has role="img"', () => {
    const { container } = render(ForecastCone, defaultProps());
    const svg = container.querySelector('svg');
    expect(svg?.getAttribute('role')).toBe('img');
  });

  it('SVG has <title> element with descriptive text', () => {
    const { container } = render(ForecastCone, defaultProps());
    const titleEl = container.querySelector('svg title');
    expect(titleEl).toBeTruthy();
    expect((titleEl?.textContent ?? '').length).toBeGreaterThan(10);
  });

  it('<title> text contains horizon weeks', () => {
    const { container } = render(ForecastCone, defaultProps({ horizonWeeks: 26 }));
    const titleEl = container.querySelector('svg title');
    expect(titleEl?.textContent).toContain('26');
  });

  it('SVG has <desc> element with long description', () => {
    const { container } = render(ForecastCone, defaultProps());
    const descEl = container.querySelector('svg desc');
    expect(descEl).toBeTruthy();
    expect((descEl?.textContent ?? '').length).toBeGreaterThan(20);
  });

  it('<desc> mentions CI and axes', () => {
    const { container } = render(ForecastCone, defaultProps());
    const descEl = container.querySelector('svg desc');
    const text = descEl?.textContent ?? '';
    expect(text).toContain('awareness');
    expect(text).toContain('90%');
  });

  it('SVG aria-labelledby references <title> id', () => {
    const { container } = render(ForecastCone, defaultProps());
    const svg = container.querySelector('svg');
    const labelledBy = svg?.getAttribute('aria-labelledby') ?? '';
    expect(labelledBy).toBeTruthy();
    const titleEl = container.querySelector(`#${labelledBy}`);
    expect(titleEl?.tagName.toLowerCase()).toBe('title');
  });

  it('SVG aria-describedby references <desc> id', () => {
    const { container } = render(ForecastCone, defaultProps());
    const svg = container.querySelector('svg');
    const describedBy = svg?.getAttribute('aria-describedby') ?? '';
    expect(describedBy).toBeTruthy();
    const descEl = container.querySelector(`#${describedBy}`);
    expect(descEl?.tagName.toLowerCase()).toBe('desc');
  });

  it('custom title prop is reflected in <title> text', () => {
    const { container } = render(ForecastCone, defaultProps({ title: 'Мой кастомный заголовок' }));
    const titleEl = container.querySelector('svg title');
    expect(titleEl?.textContent).toContain('Мой кастомный заголовок');
  });
});

// ---------------------------------------------------------------------------
// Toggle button
// ---------------------------------------------------------------------------

describe('ForecastCone — toggle button', () => {
  it('toggle button is rendered when points non-empty', () => {
    render(ForecastCone, defaultProps());
    const btn = screen.getByRole('button');
    expect(btn).toBeTruthy();
    expect(btn.textContent).toContain('Показать данные таблицей');
  });

  it('toggle button initial aria-expanded is false', () => {
    render(ForecastCone, defaultProps());
    const btn = screen.getByRole('button');
    expect(btn.getAttribute('aria-expanded')).toBe('false');
  });

  it('clicking toggle button sets aria-expanded to true', async () => {
    render(ForecastCone, defaultProps());
    const btn = screen.getByRole('button');
    await fireEvent.click(btn);
    expect(btn.getAttribute('aria-expanded')).toBe('true');
  });

  it('clicking toggle twice collapses table again (aria-expanded false)', async () => {
    render(ForecastCone, defaultProps());
    const btn = screen.getByRole('button');
    await fireEvent.click(btn);
    await fireEvent.click(btn);
    expect(btn.getAttribute('aria-expanded')).toBe('false');
  });

  it('aria-controls on button references a valid DOM id', async () => {
    const { container } = render(ForecastCone, defaultProps());
    const btn = screen.getByRole('button');
    const controlsId = btn.getAttribute('aria-controls') ?? '';
    expect(controlsId).toBeTruthy();
    // Reveal table so the element exists in DOM
    await fireEvent.click(btn);
    const controlled = container.querySelector(`#${controlsId}`);
    expect(controlled).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// Data table content
// ---------------------------------------------------------------------------

describe('ForecastCone — data table', () => {
  async function openTable(points = makePoints(3)) {
    const result = render(ForecastCone, defaultProps({ points, horizonWeeks: points.length }));
    const btn = screen.getByRole('button');
    await fireEvent.click(btn);
    return result;
  }

  it('table is not rendered initially (collapsed)', () => {
    const { container } = render(ForecastCone, defaultProps());
    expect(container.querySelector('table')).toBeNull();
  });

  it('clicking toggle reveals table element', async () => {
    const { container } = await openTable();
    expect(container.querySelector('table')).toBeTruthy();
  });

  it('table contains N rows matching N points', async () => {
    const points = makePoints(5);
    const { container } = await openTable(points);
    const rows = container.querySelectorAll('tbody tr');
    expect(rows.length).toBe(5);
  });

  it('table caption present and sr-only', async () => {
    const { container } = await openTable();
    const caption = container.querySelector('table caption');
    expect(caption).toBeTruthy();
    expect(caption?.classList.contains('sr-only')).toBe(true);
    expect(caption?.textContent).toContain('awareness');
  });

  it('column headers have scope="col"', async () => {
    const { container } = await openTable();
    const colHeaders = container.querySelectorAll('thead th[scope="col"]');
    expect(colHeaders.length).toBe(4);
  });

  it('row headers have scope="row"', async () => {
    const { container } = await openTable(makePoints(3));
    const rowHeaders = container.querySelectorAll('tbody th[scope="row"]');
    expect(rowHeaders.length).toBe(3);
  });

  it('row header displays weekIndex + 1 (1-based)', async () => {
    const points = makePoints(2);
    const { container } = await openTable(points);
    const rowHeaders = container.querySelectorAll('tbody th[scope="row"]');
    expect(rowHeaders[0]?.textContent?.trim()).toBe('1');
    expect(rowHeaders[1]?.textContent?.trim()).toBe('2');
  });

  it('numbers formatted with ru-RU locale (comma decimal separator)', async () => {
    // Use a value that will have a decimal in ru-RU format
    const points = [
      { weekIndex: 0, point: 50.5, ciLower: 40.5, ciUpper: 60.5 },
    ];
    const { container } = await openTable(points);
    const cells = container.querySelectorAll('tbody td');
    // ru-RU uses comma as decimal: "50,5"
    expect(cells[0]?.textContent).toContain(',');
  });

  it('table data cells show point, ciLower, ciUpper for each row', async () => {
    const points = [
      { weekIndex: 0, point: 100, ciLower: 80, ciUpper: 120 },
    ];
    const { container } = await openTable(points);
    const cells = container.querySelectorAll('tbody td');
    // 3 data cells per row: point, ciLower, ciUpper
    expect(cells.length).toBe(3);
    // Values formatted as ru-RU integers (no decimal for whole numbers)
    expect(cells[0]?.textContent?.trim()).toBe('100');
    expect(cells[1]?.textContent?.trim()).toBe('80');
    expect(cells[2]?.textContent?.trim()).toBe('120');
  });
});
