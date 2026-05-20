// Vitest tests for DrillDownModal.svelte — Sprint 3 D2 transparency drill-down.
//
// Protects invariants:
//   INV-48 — attack scenario (test-first) coverage for new Sprint 3 components.
//   Sprint 3 A18 — two-tier transparency UX: KaTeX formula display, text fallback,
//                  provenance citations, inputs definition list.
//
// KaTeX is mocked at module level (before component import) to prevent
// CSS/DOM issues under jsdom. The mock injects a real .katex-class span so
// tests can verify KaTeX was invoked.

import { describe, expect, it, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';

// --- KaTeX module mock (must precede component import) ---
vi.mock('katex', () => ({
  default: {
    render: vi.fn((latex: string, container: HTMLElement) => {
      container.innerHTML = '<span class="katex">' + latex + '</span>';
    }),
  },
}));

// Also mock the katex CSS import to prevent jsdom crashes
vi.mock('katex/dist/katex.min.css', () => ({}));

import katex from 'katex';
import DrillDownModal from '../../src/lib/components/transparency/DrillDownModal.svelte';
import { getFormula } from '../../src/lib/utils/formulas';

beforeEach(() => cleanup());

// ---------------------------------------------------------------------------
// Shared fixtures — use REAL registry formulas (no mock formulas module)
//
// trust_score_8d           — has 3 inputs + NO provenance URL → <cite> path
// similarity_jensen_shannon — has 4 inputs + provenance URL → <a> link path
// conformal_prediction_interval — has 3 inputs + provenance URL (secondary URL formula)
// ---------------------------------------------------------------------------

// trust_score_8d: inputs.length=3, provenance.url=undefined → cite-fallback test
const formulaNoUrl = getFormula('trust_score_8d')!;

// similarity_jensen_shannon: inputs.length=4, provenance.url set → anchor test
const formulaWithUrl = getFormula('similarity_jensen_shannon')!;

// conformal_prediction_interval: inputs.length=3, has provenance URL
const formulaThreeInputs = getFormula('conformal_prediction_interval')!;

function defaultProps(overrides: Record<string, unknown> = {}) {
  return {
    open: true,
    onClose: vi.fn(),
    formula: formulaNoUrl,
    ...overrides,
  };
}

/** Flush microtasks — needed for $effect (KaTeX render) which runs after render. */
async function flushAsync() {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

// ---------------------------------------------------------------------------
// Group 1 — Rendering when open=true + formula present
// ---------------------------------------------------------------------------

describe('DrillDownModal — rendering open=true + formula present', () => {
  it('title text equals formula.title', async () => {
    const { container } = render(DrillDownModal, defaultProps());
    await flushAsync();

    const title = container.querySelector('#drill-title');
    expect(title).not.toBeNull();
    expect(title!.textContent).toContain(formulaNoUrl.title);
  });

  it('explanation paragraph text equals formula.explanation', async () => {
    const { container } = render(DrillDownModal, defaultProps());
    await flushAsync();

    const explanation = container.querySelector('#drill-explanation');
    expect(explanation).not.toBeNull();
    expect(explanation!.textContent).toBe(formulaNoUrl.explanation);
  });

  it('inputs DL renders one dt/dd pair per formula.inputs entry', async () => {
    // formulaNoUrl (trust_score_8d) has 3 inputs
    const { container } = render(DrillDownModal, defaultProps({ formula: formulaNoUrl }));
    await flushAsync();

    const dl = container.querySelector('.dd-inputs');
    expect(dl).not.toBeNull();
    const dts = dl!.querySelectorAll('dt');
    const dds = dl!.querySelectorAll('dd');
    expect(dts.length).toBe(formulaNoUrl.inputs.length);
    expect(dds.length).toBe(formulaNoUrl.inputs.length);
  });

  it('each symbol code renders in <dt><code class="dd-symbol">', async () => {
    const { container } = render(DrillDownModal, defaultProps({ formula: formulaNoUrl }));
    await flushAsync();

    const dl = container.querySelector('.dd-inputs')!;
    const codes = dl.querySelectorAll('dt code.dd-symbol');
    expect(codes.length).toBe(formulaNoUrl.inputs.length);
    const symbols = Array.from(codes).map((c) => c.textContent);
    for (const input of formulaNoUrl.inputs) {
      expect(symbols).toContain(input.symbol);
    }
  });

  it('output paragraph contains formula.output', async () => {
    const { container } = render(DrillDownModal, defaultProps());
    await flushAsync();

    const output = container.querySelector('.dd-output');
    expect(output).not.toBeNull();
    expect(output!.textContent).toBe(formulaNoUrl.output);
  });

  it('provenance footer renders formula.provenance.citation', async () => {
    const { container } = render(DrillDownModal, defaultProps({ formula: formulaNoUrl }));
    await flushAsync();

    const footer = container.querySelector('.dd-provenance');
    expect(footer).not.toBeNull();
    expect(footer!.textContent).toContain(formulaNoUrl.provenance.citation);
  });

  it('when provenance.url present → renders <a> with target="_blank" + rel="noopener noreferrer"', async () => {
    const { container } = render(
      DrillDownModal,
      defaultProps({ formula: formulaWithUrl }),
    );
    await flushAsync();

    const link = container.querySelector('.dd-provenance a');
    expect(link).not.toBeNull();
    expect(link!.getAttribute('href')).toBe(formulaWithUrl.provenance.url);
    expect(link!.getAttribute('target')).toBe('_blank');
    expect(link!.getAttribute('rel')).toBe('noopener noreferrer');
  });

  it('when provenance.url absent → renders plain <cite>, NO anchor element', async () => {
    // formulaNoUrl (trust_score_8d) has no URL
    const { container } = render(DrillDownModal, defaultProps({ formula: formulaNoUrl }));
    await flushAsync();

    const footer = container.querySelector('.dd-provenance');
    expect(footer!.querySelector('a')).toBeNull();
    const cite = footer!.querySelector('cite');
    expect(cite).not.toBeNull();
    expect(cite!.textContent).toContain(formulaNoUrl.provenance.citation);
  });

  it('contextValue prop renders inside .drill-context-badge span when provided', async () => {
    const { container } = render(DrillDownModal, defaultProps({ contextValue: '42%' }));
    await flushAsync();

    const badge = container.querySelector('.drill-context-badge');
    expect(badge).not.toBeNull();
    expect(badge!.textContent).toBe('42%');
  });

  it('contextValue badge hidden when prop omitted', async () => {
    const { container } = render(DrillDownModal, defaultProps({ contextValue: undefined }));
    await flushAsync();

    expect(container.querySelector('.drill-context-badge')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Group 2 — KaTeX rendering
// ---------------------------------------------------------------------------

describe('DrillDownModal — KaTeX rendering', () => {
  it('mathContainer receives katex output after $effect runs (container.innerHTML contains .katex span)', async () => {
    vi.mocked(katex.render).mockImplementation((latex, container) => {
      container.innerHTML = '<span class="katex">' + latex + '</span>';
    });

    const { container } = render(DrillDownModal, defaultProps());
    await flushAsync();

    const mathContainer = container.querySelector('.dd-math');
    expect(mathContainer).not.toBeNull();
    expect(mathContainer!.querySelector('.katex')).not.toBeNull();
  });

  it('katex.render called with formula.latex and displayMode: true', async () => {
    vi.mocked(katex.render).mockClear();
    vi.mocked(katex.render).mockImplementation((latex, container) => {
      container.innerHTML = '<span class="katex">' + latex + '</span>';
    });

    render(DrillDownModal, defaultProps({ formula: formulaNoUrl }));
    await flushAsync();

    expect(vi.mocked(katex.render)).toHaveBeenCalledWith(
      formulaNoUrl.latex,
      expect.any(HTMLElement),
      expect.objectContaining({ displayMode: true }),
    );
  });

  it('aria-label on .dd-math equals formula.text_fallback', async () => {
    const { container } = render(DrillDownModal, defaultProps({ formula: formulaNoUrl }));
    await flushAsync();

    const math = container.querySelector('.dd-math');
    expect(math).not.toBeNull();
    expect(math!.getAttribute('aria-label')).toBe(formulaNoUrl.text_fallback);
  });

  it('aria-describedby on .dd-math points to "drill-explanation" id', async () => {
    const { container } = render(DrillDownModal, defaultProps());
    await flushAsync();

    const math = container.querySelector('.dd-math');
    expect(math!.getAttribute('aria-describedby')).toBe('drill-explanation');
  });

  it('text fallback path: when katex.render throws, mathContainer.textContent equals formula.text_fallback', async () => {
    vi.mocked(katex.render).mockImplementationOnce(() => {
      throw new Error('fail');
    });

    const { container } = render(DrillDownModal, defaultProps());
    await flushAsync();

    const mathContainer = container.querySelector('.dd-math');
    expect(mathContainer).not.toBeNull();
    expect(mathContainer!.textContent).toBe(formulaNoUrl.text_fallback);
  });
});

// ---------------------------------------------------------------------------
// Group 3 — Modal behaviour + accessibility
// ---------------------------------------------------------------------------

describe('DrillDownModal — modal behaviour + accessibility', () => {
  it('when open=false → no formula content rendered (NotificationBanner hides via open prop)', async () => {
    vi.mocked(katex.render).mockClear();

    const { container } = render(DrillDownModal, defaultProps({ open: false }));
    await flushAsync();

    // NotificationBanner only renders content inside {#if open}
    expect(container.querySelector('#drill-title')).toBeNull();
    expect(container.querySelector('.dd-math')).toBeNull();
    expect(container.querySelector('.dd-explanation')).toBeNull();
    expect(vi.mocked(katex.render)).not.toHaveBeenCalled();
  });

  it('fallback "Нет данных для отображения формулы" renders when formula=null + open=true', async () => {
    render(DrillDownModal, defaultProps({ formula: null }));
    await flushAsync();

    expect(screen.getByText(/Нет данных для отображения формулы/)).toBeTruthy();
  });

  it('onClose callback invoked when close button (nb-btn--ghost) clicked', async () => {
    const onClose = vi.fn();
    render(DrillDownModal, defaultProps({ onClose }));
    await flushAsync();

    // "Закрыть" button is the actions snippet ghost button
    const closeBtn = screen.getByText('Закрыть');
    await fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('dialog has role=dialog (delegated to NotificationBanner level=prompt)', async () => {
    render(DrillDownModal, defaultProps());
    await flushAsync();

    const dialog = screen.queryByRole('dialog');
    expect(dialog).not.toBeNull();
  });

  it('dialog has aria-labelledby="drill-title"', async () => {
    render(DrillDownModal, defaultProps());
    await flushAsync();

    const dialog = screen.queryByRole('dialog');
    expect(dialog!.getAttribute('aria-labelledby')).toBe('drill-title');
  });

  it('dismiss × button in NotificationBanner also invokes onClose', async () => {
    const onClose = vi.fn();
    render(DrillDownModal, defaultProps({ onClose }));
    await flushAsync();

    // NotificationBanner renders an aria-label="Закрыть" × dismiss button
    const dismissBtns = screen.getAllByLabelText('Закрыть');
    expect(dismissBtns.length).toBeGreaterThanOrEqual(1);
    await fireEvent.click(dismissBtns[0]!);
    expect(onClose).toHaveBeenCalled();
  });

  // PENDING Batch 4: touch-device drill-down UX — swipe-down gesture on modal
  // should trigger onClose (two-tier transparency drill-down from Sprint 3 A18).
  // Blocked on Playwright/mobile gesture test infrastructure.
  it.skip('swipe-down gesture on .dd-math triggers onClose (touch UX)', async () => {
    // PENDING Batch 4: implement touch gesture simulation via pointer events
    // once touch-device test harness is established (Sprint 4 scope).
    const onClose = vi.fn();
    render(DrillDownModal, defaultProps({ onClose }));
    await flushAsync();
    // TODO: simulate touchstart + touchmove + touchend in downward direction
    expect(onClose).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Additional coverage — inputs with formulaWithUrl (4 inputs, has URL)
// ---------------------------------------------------------------------------

describe('DrillDownModal — similarity_jensen_shannon (4 inputs, URL)', () => {
  it('renders 4 dt/dd pairs for similarity_jensen_shannon', async () => {
    const { container } = render(
      DrillDownModal,
      defaultProps({ formula: formulaWithUrl }),
    );
    await flushAsync();

    const dl = container.querySelector('.dd-inputs')!;
    expect(dl.querySelectorAll('dt').length).toBe(4);
    expect(dl.querySelectorAll('dd').length).toBe(4);
  });

  it('each dd contains the corresponding input description', async () => {
    const { container } = render(
      DrillDownModal,
      defaultProps({ formula: formulaWithUrl }),
    );
    await flushAsync();

    const dl = container.querySelector('.dd-inputs')!;
    const dds = dl.querySelectorAll('dd');
    const descriptions = Array.from(dds).map((d) => d.textContent);
    for (const input of formulaWithUrl.inputs) {
      expect(descriptions.some((d) => d?.includes(input.description))).toBe(true);
    }
  });

  it('provenance link citation text matches formulaWithUrl.provenance.citation', async () => {
    const { container } = render(
      DrillDownModal,
      defaultProps({ formula: formulaWithUrl }),
    );
    await flushAsync();

    const footer = container.querySelector('.dd-provenance');
    expect(footer!.textContent).toContain(formulaWithUrl.provenance.citation);
  });
});
