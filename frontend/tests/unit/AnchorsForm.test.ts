// Vitest tests for AnchorsForm.svelte (Phase 1.C.5, SO-1 simplification).

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';
import AnchorsForm from '../../src/lib/components/AnchorsForm.svelte';

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// ──────────────────────────────────────────────────────────────────────────────
// Default draft for convenience
// ──────────────────────────────────────────────────────────────────────────────
function defaultDraft() {
  return {
    pattern: 'sustain' as const,
    intensity: 5,
    awareness_target_pct: null,
    custom_trajectory: null,
    notes: null,
  };
}

describe('AnchorsForm — rendering', () => {
  it('renders heading and subtitle', () => {
    render(AnchorsForm, { draft: defaultDraft() });
    expect(screen.getByText(/Шаг 4 — Опорные точки прогноза/)).toBeTruthy();
    expect(screen.getByText(/Расскажите Aurora/)).toBeTruthy();
    // Subtitle contains "Устойчивый рост" in a <strong> inside the subtitle <p>
    const subtitle = screen.getByText(/Расскажите Aurora/);
    expect(subtitle.textContent).toContain('Устойчивый рост');
  });

  it('renders 4 pattern cards', () => {
    render(AnchorsForm, { draft: defaultDraft() });
    // Labels from TRAJECTORY_PATTERNS — use getAllByText since
    // "Устойчивый рост" appears in both subtitle and pattern card label
    expect(screen.getByText('Нарастание')).toBeTruthy();
    expect(screen.getAllByText('Устойчивый рост').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Снижение')).toBeTruthy();
    expect(screen.getByText('Свой график')).toBeTruthy();
  });

  it('renders pattern descriptions', () => {
    render(AnchorsForm, { draft: defaultDraft() });
    expect(screen.getByText('Awareness постепенно растёт')).toBeTruthy();
    expect(screen.getByText('Awareness стабильно поддерживается')).toBeTruthy();
  });

  it('renders SVG preview for non-custom pattern (sustain)', () => {
    const { container } = render(AnchorsForm, { draft: defaultDraft() });
    const svg = container.querySelector('svg');
    expect(svg).toBeTruthy();
  });

  it('SVG has accessible title element', () => {
    const { container } = render(AnchorsForm, { draft: defaultDraft() });
    const title = container.querySelector('svg title');
    expect(title?.textContent).toBe('Предпросмотр траектории awareness');
  });

  it('intensity range input has aria-label', () => {
    render(AnchorsForm, { draft: defaultDraft() });
    const slider = screen.getByRole('slider');
    expect(slider.getAttribute('aria-label')).toBeTruthy();
  });

  it('renders awareness target input with placeholder', () => {
    render(AnchorsForm, { draft: defaultDraft() });
    const input = screen.getByPlaceholderText('Например, 35.5');
    expect(input).toBeTruthy();
  });

  it('renders notes textarea', () => {
    render(AnchorsForm, { draft: defaultDraft() });
    expect(screen.getByLabelText('Дополнительные комментарии к прогнозу')).toBeTruthy();
  });
});

describe('AnchorsForm — pattern selection', () => {
  it('selected pattern card has aria-pressed=true', () => {
    const { container } = render(AnchorsForm, {
      draft: { ...defaultDraft(), pattern: 'rampup' },
    });
    const cards = container.querySelectorAll('.pattern-card');
    // First card = rampup
    const rampupCard = Array.from(cards).find(
      (c) => c.textContent?.includes('Нарастание'),
    );
    expect(rampupCard?.getAttribute('aria-pressed')).toBe('true');
  });

  it('other pattern cards have aria-pressed=false', () => {
    const { container } = render(AnchorsForm, {
      draft: { ...defaultDraft(), pattern: 'sustain' },
    });
    const cards = container.querySelectorAll('.pattern-card');
    const rampupCard = Array.from(cards).find(
      (c) => c.textContent?.includes('Нарастание'),
    );
    expect(rampupCard?.getAttribute('aria-pressed')).toBe('false');
  });

  it('clicking rampup card updates aria-pressed to true', async () => {
    const { container } = render(AnchorsForm, { draft: defaultDraft() });
    const cards = container.querySelectorAll('.pattern-card');
    const rampupCard = Array.from(cards).find(
      (c) => c.textContent?.includes('Нарастание'),
    ) as HTMLButtonElement;
    expect(rampupCard).toBeTruthy();
    await fireEvent.click(rampupCard);
    expect(rampupCard.getAttribute('aria-pressed')).toBe('true');
  });

  it('switching from non-custom to sustain hides custom inputs', () => {
    const { container } = render(AnchorsForm, {
      draft: { ...defaultDraft(), pattern: 'sustain' },
    });
    expect(container.querySelector('.custom-fieldset')).toBeNull();
  });
});

describe('AnchorsForm — custom mode', () => {
  it('selecting custom hides SVG preview', () => {
    const { container } = render(AnchorsForm, {
      draft: { ...defaultDraft(), pattern: 'custom', custom_trajectory: Array(12).fill(0) },
    });
    expect(container.querySelector('svg')).toBeNull();
  });

  it('custom mode shows number inputs for each period', () => {
    const horizonPeriods = 12;
    const { container } = render(AnchorsForm, {
      props: {
        draft: {
          ...defaultDraft(),
          pattern: 'custom',
          custom_trajectory: Array(horizonPeriods).fill(0),
        },
        horizon_periods: horizonPeriods,
      },
    });
    const customInputs = container.querySelectorAll('.custom-input');
    expect(customInputs).toHaveLength(horizonPeriods);
  });

  it('custom inputs are labelled by period number', () => {
    render(AnchorsForm, {
      props: {
        draft: {
          ...defaultDraft(),
          pattern: 'custom',
          custom_trajectory: Array(4).fill(0),
        },
        horizon_periods: 4,
      },
    });
    // aria-label="Период 1" through "Период 4"
    expect(screen.getByLabelText('Период 1')).toBeTruthy();
    expect(screen.getByLabelText('Период 4')).toBeTruthy();
  });

  it('switching back from custom to rampup re-renders SVG', async () => {
    const { container } = render(AnchorsForm, {
      draft: { ...defaultDraft(), pattern: 'custom', custom_trajectory: Array(12).fill(0) },
    });
    // Confirm no SVG yet
    expect(container.querySelector('svg')).toBeNull();

    // Click rampup card
    const cards = container.querySelectorAll('.pattern-card');
    const rampupCard = Array.from(cards).find(
      (c) => c.textContent?.includes('Нарастание'),
    ) as HTMLButtonElement;
    await fireEvent.click(rampupCard);

    expect(container.querySelector('svg')).toBeTruthy();
  });
});

describe('AnchorsForm — intensity slider', () => {
  it('shows current intensity label e.g. "5/10"', () => {
    render(AnchorsForm, { draft: defaultDraft() });
    expect(screen.getByText(/5\/10/)).toBeTruthy();
  });

  it('intensity slider is hidden in custom mode', () => {
    render(AnchorsForm, {
      draft: { ...defaultDraft(), pattern: 'custom', custom_trajectory: Array(12).fill(0) },
    });
    expect(screen.queryByRole('slider')).toBeNull();
  });
});

describe('AnchorsForm — validation', () => {
  it('no validation banner when draft is valid', () => {
    const { container } = render(AnchorsForm, { draft: defaultDraft() });
    expect(container.querySelector('.validation-banner')).toBeNull();
  });

  it('shows warning when custom_trajectory length mismatches horizon_periods', () => {
    const { container } = render(AnchorsForm, {
      props: {
        draft: {
          pattern: 'custom' as const,
          intensity: 5,
          awareness_target_pct: null,
          custom_trajectory: [0.5, 0.5], // only 2 values, horizon=12
          notes: null,
        },
        horizon_periods: 12,
      },
    });
    expect(container.querySelector('.validation-banner')).toBeTruthy();
    expect(screen.getByText(/нужно 12 значений/)).toBeTruthy();
  });
});

describe('AnchorsForm — a11y', () => {
  it('section has aria-label', () => {
    const { container } = render(AnchorsForm, { draft: defaultDraft() });
    const section = container.querySelector('section');
    expect(section?.getAttribute('aria-label')).toBe('Шаг 4 — Опорные точки прогноза');
  });

  it('validation banner has role=alert', () => {
    const { container } = render(AnchorsForm, {
      props: {
        draft: {
          pattern: 'custom' as const,
          intensity: 5,
          awareness_target_pct: null,
          custom_trajectory: [0.1],
          notes: null,
        },
        horizon_periods: 12,
      },
    });
    const banner = container.querySelector('.validation-banner');
    expect(banner?.getAttribute('role')).toBe('alert');
  });

  it('awareness target input has aria-label', () => {
    render(AnchorsForm, { draft: defaultDraft() });
    expect(screen.getByLabelText('Целевой уровень awareness в процентах')).toBeTruthy();
  });
});
