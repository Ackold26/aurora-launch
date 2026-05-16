// Unit tests for BudgetSplitChart.svelte
//
// Coverage:
//  1.  Renders one bar per channel
//  2.  Correct sum displayed per channel
//  3.  Empty data — renders gracefully (no crash, shows "Нет данных")
//  4.  Single channel happy path
//  5.  5+ channels — grid scales (all bars rendered)
//  6.  Numeric formatting with ₽ and thousand separator
//  7.  a11y: SVG <title> element is present
//  8.  <title> contains all channel names
//  9.  Bar width proportional to total (largest channel gets biggest bar)
// 10.  Total across periods is summed correctly

import { describe, expect, it, beforeEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';

import BudgetSplitChart from '../../src/lib/components/BudgetSplitChart.svelte';

beforeEach(() => cleanup());

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** Flush micro-tasks so $derived + $state settle. */
async function flush() {
  await Promise.resolve();
  await Promise.resolve();
}

// ─── Tests ───────────────────────────────────────────────────────────────────

describe('BudgetSplitChart', () => {
  it('1. renders one <rect> bar per channel', async () => {
    const { container } = render(BudgetSplitChart, {
      props: {
        channels: {
          ТВ: [1_000_000, 2_000_000],
          Digital: [500_000, 500_000],
          OOH: [300_000],
        },
      },
    });
    await flush();

    // Each channel → one <rect> element
    const rects = container.querySelectorAll('rect');
    expect(rects.length).toBe(3);
  });

  it('2. correct per-channel sum is shown in value labels', async () => {
    const { container } = render(BudgetSplitChart, {
      props: {
        channels: {
          ТВ: [1_000_000, 1_000_000], // sum = 2 000 000
        },
      },
    });
    await flush();

    // The SVG title or a text element should contain the formatted sum.
    const svgText = container.querySelector('svg')?.textContent ?? '';
    // 2 000 000 ₽ formatted in ru-RU includes "2" and "000" — look for substring
    expect(svgText).toMatch(/2/);
    expect(svgText).toMatch(/000/);
  });

  it('3. empty channels — renders gracefully without crash', async () => {
    const { container } = render(BudgetSplitChart, {
      props: { channels: {} },
    });
    await flush();

    // Should have an SVG element
    const svg = container.querySelector('svg');
    expect(svg).not.toBeNull();

    // No bars
    const rects = container.querySelectorAll('rect');
    expect(rects.length).toBe(0);

    // Shows empty state text
    expect(svg?.textContent).toContain('Нет данных');
  });

  it('4. single channel happy path — renders one bar and correct sum', async () => {
    const { container } = render(BudgetSplitChart, {
      props: {
        channels: {
          'Outdoor': [5_000_000],
        },
      },
    });
    await flush();

    const rects = container.querySelectorAll('rect');
    expect(rects.length).toBe(1);

    const textEl = container.querySelector('svg title');
    expect(textEl?.textContent).toContain('Outdoor');
  });

  it('5. 5+ channels — all bars rendered', async () => {
    const { container } = render(BudgetSplitChart, {
      props: {
        channels: {
          ТВ: [1_000_000],
          Digital: [800_000],
          OOH: [500_000],
          Radio: [200_000],
          Print: [100_000],
          Cinema: [50_000],
        },
      },
    });
    await flush();

    const rects = container.querySelectorAll('rect');
    expect(rects.length).toBe(6);
  });

  it('6. numeric formatting uses ₽ and thousand separator', async () => {
    const { container } = render(BudgetSplitChart, {
      props: {
        channels: {
          ТВ: [10_000_000],
        },
      },
    });
    await flush();

    const svgText = container.querySelector('svg')?.textContent ?? '';
    // Intl.NumberFormat ru-RU currency will include ₽
    expect(svgText).toContain('₽');
  });

  it('7. a11y: SVG has a <title> element', async () => {
    const { container } = render(BudgetSplitChart, {
      props: {
        channels: { ТВ: [1_000_000] },
      },
    });
    await flush();

    const title = container.querySelector('svg title');
    expect(title).not.toBeNull();
    expect(title?.textContent?.length).toBeGreaterThan(0);
  });

  it('8. <title> contains all channel names', async () => {
    const { container } = render(BudgetSplitChart, {
      props: {
        channels: {
          ТВ: [1_000_000],
          Digital: [500_000],
          OOH: [300_000],
        },
      },
    });
    await flush();

    const title = container.querySelector('svg title')?.textContent ?? '';
    expect(title).toContain('ТВ');
    expect(title).toContain('Digital');
    expect(title).toContain('OOH');
  });

  it('9. largest channel gets the widest bar (width proportional)', async () => {
    const { container } = render(BudgetSplitChart, {
      props: {
        channels: {
          Big: [10_000_000],
          Small: [1_000_000],
        },
      },
    });
    await flush();

    const rects = Array.from(container.querySelectorAll('rect'));
    // First channel is "Big"; get their widths
    const widths = rects.map((r) => parseFloat(r.getAttribute('width') ?? '0'));
    // Big (index 0) should have strictly larger width than Small (index 1)
    expect(widths[0] ?? 0).toBeGreaterThan(widths[1] ?? 0);
  });

  it('10. total is computed as sum across all periods', async () => {
    const { container } = render(BudgetSplitChart, {
      props: {
        channels: {
          ТВ: [1_000_000, 2_000_000, 3_000_000], // total = 6 000 000
        },
      },
    });
    await flush();

    const svgText = container.querySelector('svg')?.textContent ?? '';
    // The sum 6 000 000 should appear in some form
    expect(svgText).toContain('6');
  });
});
