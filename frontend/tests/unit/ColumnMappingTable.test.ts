// Vitest tests for ColumnMappingTable.svelte (BTA-6).

import { describe, expect, it, beforeEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';
import ColumnMappingTable from '../../src/lib/components/ColumnMappingTable.svelte';

beforeEach(() => cleanup());

/** Flush $effect / onMount microtasks. */
async function flush() {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

const SOURCE_COLS = ['Бренд', 'Дата', 'Неизвестная_колонка'] as const;

describe('ColumnMappingTable — rendering', () => {
  it('renders table header «Колонка в файле»', async () => {
    const mapping = new Map<string, string | null>();
    render(ColumnMappingTable, {
      sourceColumns: SOURCE_COLS,
      mapping,
    });
    await flush();
    expect(screen.getByText('Колонка в файле')).toBeTruthy();
  });

  it('renders table header «Aurora-поле»', async () => {
    const mapping = new Map<string, string | null>();
    render(ColumnMappingTable, {
      sourceColumns: SOURCE_COLS,
      mapping,
    });
    await flush();
    expect(screen.getByText('Aurora-поле')).toBeTruthy();
  });

  it('renders one <tr> per source column (+ header row)', async () => {
    const mapping = new Map<string, string | null>();
    const { container } = render(ColumnMappingTable, {
      sourceColumns: SOURCE_COLS,
      mapping,
    });
    await flush();
    // thead has 1 tr, tbody has SOURCE_COLS.length tr
    const bodyRows = container.querySelectorAll('tbody tr');
    expect(bodyRows).toHaveLength(SOURCE_COLS.length);
  });

  it('renders source column name in each row', async () => {
    const mapping = new Map<string, string | null>();
    render(ColumnMappingTable, {
      sourceColumns: ['МойБренд', 'МояДата'],
      mapping,
    });
    await flush();
    expect(screen.getByText('МойБренд')).toBeTruthy();
    expect(screen.getByText('МояДата')).toBeTruthy();
  });

  it('each select has correct aria-label', async () => {
    const mapping = new Map<string, string | null>();
    const { container } = render(ColumnMappingTable, {
      sourceColumns: ['Бренд', 'Дата'],
      mapping,
    });
    await flush();
    const selects = container.querySelectorAll('select');
    const labels = [...selects].map((s) => s.getAttribute('aria-label'));
    expect(labels).toContain('Сопоставить колонку Бренд');
    expect(labels).toContain('Сопоставить колонку Дата');
  });
});

describe('ColumnMappingTable — auto-fill', () => {
  it('auto-fills mapping at mount when mapping is empty', async () => {
    const mapping = new Map<string, string | null>();
    const { container } = render(ColumnMappingTable, {
      sourceColumns: ['Бренд'],
      mapping,
    });
    await flush();
    // After auto-fill, the select for «Бренд» should show brand_name.
    const select = container.querySelector('select[aria-label="Сопоставить колонку Бренд"]') as HTMLSelectElement | null;
    expect(select).not.toBeNull();
    expect(select!.value).toBe('brand_name');
  });

  it('does not overwrite existing mapping on mount', async () => {
    // Pre-fill with a custom value — should NOT be overwritten.
    const mapping = new Map<string, string | null>([['Бренд', 'region']]);
    const { container } = render(ColumnMappingTable, {
      sourceColumns: ['Бренд'],
      mapping,
    });
    await flush();
    const select = container.querySelector('select[aria-label="Сопоставить колонку Бренд"]') as HTMLSelectElement | null;
    expect(select!.value).toBe('region');
  });
});

describe('ColumnMappingTable — counter', () => {
  it('shows «Сопоставлено X из Y» counter', async () => {
    // Pre-fill so we have a known state.
    const mapping = new Map<string, string | null>([
      ['Бренд', 'brand_name'],
      ['Дата', null],
    ]);
    render(ColumnMappingTable, {
      sourceColumns: ['Бренд', 'Дата'],
      mapping,
    });
    await flush();
    expect(screen.getByText(/Сопоставлено/)).toBeTruthy();
    expect(screen.getByText('1')).toBeTruthy(); // mappedCount
    expect(screen.getByText('2')).toBeTruthy(); // total
  });

  it('counter shows 0 when no columns mapped', async () => {
    const mapping = new Map<string, string | null>([
      ['Неизвестно', null],
    ]);
    render(ColumnMappingTable, {
      sourceColumns: ['Неизвестно'],
      mapping,
    });
    await flush();
    // mappedCount = 0, total = 1
    expect(screen.getByText('0')).toBeTruthy();
    expect(screen.getByText('1')).toBeTruthy();
  });
});

describe('ColumnMappingTable — preview value', () => {
  it('shows preview value from previewRows[0] under source name', async () => {
    const mapping = new Map<string, string | null>();
    render(ColumnMappingTable, {
      sourceColumns: ['Бренд'],
      mapping,
      previewRows: [{ 'Бренд': 'Кагоцел' }],
    });
    await flush();
    expect(screen.getByText('Кагоцел')).toBeTruthy();
  });

  it('no preview shown when previewRows empty', async () => {
    const mapping = new Map<string, string | null>();
    const { container } = render(ColumnMappingTable, {
      sourceColumns: ['Бренд'],
      mapping,
      previewRows: [],
    });
    await flush();
    const previews = container.querySelectorAll('.preview');
    expect(previews).toHaveLength(0);
  });
});

describe('ColumnMappingTable — select interaction', () => {
  it('select has «— не сопоставлено —» as empty option', async () => {
    const mapping = new Map<string, string | null>([['Бренд', null]]);
    const { container } = render(ColumnMappingTable, {
      sourceColumns: ['Бренд'],
      mapping,
    });
    await flush();
    const select = container.querySelector('select') as HTMLSelectElement;
    const options = [...select.options].map((o) => o.text);
    expect(options).toContain('— не сопоставлено —');
  });

  it('select options contain Aurora canonical field labels', async () => {
    const mapping = new Map<string, string | null>([['Бренд', null]]);
    const { container } = render(ColumnMappingTable, {
      sourceColumns: ['Бренд'],
      mapping,
    });
    await flush();
    const select = container.querySelector('select') as HTMLSelectElement;
    const options = [...select.options].map((o) => o.text);
    expect(options).toContain('Бренд');   // label_ru for brand_name
    expect(options).toContain('Период / Дата'); // period_date
  });

  it('changing select updates select value in DOM', async () => {
    const mapping = new Map<string, string | null>([['МояКолонка', null]]);
    const { container } = render(ColumnMappingTable, {
      sourceColumns: ['МояКолонка'],
      mapping,
    });
    await flush();
    const select = container.querySelector('select') as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: 'region' } });
    await flush();
    expect(select.value).toBe('region');
  });
});
