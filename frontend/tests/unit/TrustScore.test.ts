import { describe, expect, it, beforeEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';

import TrustScore from '../../src/lib/components/TrustScore.svelte';

beforeEach(() => cleanup());

// Helper to build default minimal props
function defaultProps(overrides: Record<string, unknown> = {}) {
  return { score: 87, ...overrides };
}

describe('TrustScore', () => {
  // ---------- score display ----------

  it('renders the score number 87', () => {
    render(TrustScore, defaultProps());
    expect(screen.getByText('87')).toBeTruthy();
  });

  // ---------- tier mapping ----------

  it('score 95 → "Очень высокий"', () => {
    render(TrustScore, defaultProps({ score: 95 }));
    expect(screen.getByText('Очень высокий')).toBeTruthy();
  });

  it('score 80 → "Высокий"', () => {
    render(TrustScore, defaultProps({ score: 80 }));
    expect(screen.getByText('Высокий')).toBeTruthy();
  });

  it('score 65 → "Средний"', () => {
    render(TrustScore, defaultProps({ score: 65 }));
    expect(screen.getByText('Средний')).toBeTruthy();
  });

  it('score 50 → "Низкий"', () => {
    render(TrustScore, defaultProps({ score: 50 }));
    expect(screen.getByText('Низкий')).toBeTruthy();
  });

  it('score 30 → "Пока не рассчитан"', () => {
    render(TrustScore, defaultProps({ score: 30 }));
    expect(screen.getByText('Пока не рассчитан')).toBeTruthy();
  });

  // ---------- clamping ----------

  it('negative score -10 clamps to 0', () => {
    render(TrustScore, defaultProps({ score: -10 }));
    expect(screen.getByText('0')).toBeTruthy();
  });

  it('score 150 clamps to 100', () => {
    render(TrustScore, defaultProps({ score: 150 }));
    expect(screen.getByText('100')).toBeTruthy();
  });

  it('score 87.6 rounds to 88', () => {
    render(TrustScore, defaultProps({ score: 87.6 }));
    expect(screen.getByText('88')).toBeTruthy();
  });

  // ---------- expert mode ----------

  it('expertMode=false → expand/collapse toggle button hidden', () => {
    render(TrustScore, defaultProps({ expertMode: false }));
    // Sprint 6 audit pass V1: explain link visible regardless of mode (ungated).
    // Expand toggle remains expertMode-gated. Match toggle specifically.
    expect(screen.queryByRole('button', { name: /Подробнее|Свернуть/ })).toBeNull();
  });

  it('expertMode=true → toggle button visible', () => {
    render(TrustScore, defaultProps({ expertMode: true }));
    // Sprint 6 D5 #22: ≥2 buttons in expert mode — explain link + expand toggle.
    // Match expand toggle specifically by its label.
    expect(screen.getByRole('button', { name: /Подробнее|Свернуть/ })).toBeTruthy();
  });

  it('expertMode=false → diagnostics section absent', () => {
    render(TrustScore, defaultProps({
      expertMode: false,
      diagnostics: [{ label: 'R̂', value: '1.00', status: 'good' }]
    }));
    expect(screen.queryByLabelText('Подробная диагностика')).toBeNull();
  });

  it('toggle expanded → diagnostics visible when expertMode=true and diagnostics provided', async () => {
    render(TrustScore, defaultProps({
      expertMode: true,
      diagnostics: [{ label: 'R̂', value: '1.00', status: 'good' }]
    }));
    // Sprint 6 D5 #22: select expand toggle (not explain link).
    const btn = screen.getByRole('button', { name: /Подробнее|Свернуть/ });
    await fireEvent.click(btn);
    expect(screen.getByLabelText('Подробная диагностика')).toBeTruthy();
    expect(screen.getByText('R̂')).toBeTruthy();
  });

  // ---------- Sprint 6 D5 #22 — explain link drill-down ----------
  //
  // Sprint 6 audit pass V1 decision: explain link visible regardless of
  // expertMode — educational link ≠ diagnostic clutter. Production integration
  // (ForecastTab.svelte:296) uses `expertMode={!trustIsRealCompute}` semantic
  // что would hide button для real-compute pilot users — undesirable.

  it('explain link "Что значат эти 8 измерений?" visible in expertMode=true', () => {
    render(TrustScore, defaultProps({ expertMode: true }));
    expect(screen.getByRole('button', { name: /8 измерений/ })).toBeTruthy();
  });

  it('explain link visible in expertMode=false (educational, ungated)', () => {
    render(TrustScore, defaultProps({ expertMode: false }));
    expect(screen.getByRole('button', { name: /8 измерений/ })).toBeTruthy();
  });

  it('click explain link → DrillDownModal opens с trust_score_8d formula', async () => {
    render(TrustScore, defaultProps({ expertMode: true }));
    const btn = screen.getByRole('button', { name: /8 измерений/ });
    await fireEvent.click(btn);
    // Modal title from formulas.ts: "Trust Score (8 измерений)"
    expect(screen.getByText(/Trust Score \(8 измерений\)/)).toBeTruthy();
  });

  // ---------- aria ----------

  it('ARIA label "Уровень доверия: 87 из 100" present', () => {
    render(TrustScore, defaultProps({ score: 87 }));
    expect(screen.getByLabelText('Уровень доверия: 87 из 100')).toBeTruthy();
  });

  // ---------- verdict override ----------

  it('custom verdict prop overrides tier label', () => {
    render(TrustScore, defaultProps({ score: 80, verdict: 'Отличный прогноз' }));
    expect(screen.getByText('Отличный прогноз')).toBeTruthy();
    expect(screen.queryByText('Высокий')).toBeNull();
  });
});
