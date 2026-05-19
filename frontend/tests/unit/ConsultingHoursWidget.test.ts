import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';

import ConsultingHoursWidget from '../../src/lib/components/welcome/ConsultingHoursWidget.svelte';

beforeEach(() => cleanup());

describe('ConsultingHoursWidget', () => {
  it('renders 10/40 в success state (25%)', () => {
    render(ConsultingHoursWidget, { used: 10, total: 40 });
    expect(screen.getByText('10')).toBeTruthy();
    expect(screen.getByText('40')).toBeTruthy();
    expect(screen.getByText('25%')).toBeTruthy();
    expect(document.querySelector('.hours-used--success')).toBeTruthy();
  });

  it('renders warning state at 80%', () => {
    render(ConsultingHoursWidget, { used: 32, total: 40 });
    expect(screen.getByText('80%')).toBeTruthy();
    expect(document.querySelector('.hours-used--warning')).toBeTruthy();
    expect(document.querySelector('.hours-fill--warning')).toBeTruthy();
  });

  it('renders danger state at 95%', () => {
    render(ConsultingHoursWidget, { used: 38, total: 40 });
    expect(screen.getByText('95%')).toBeTruthy();
    expect(document.querySelector('.hours-used--danger')).toBeTruthy();
    expect(document.querySelector('.hours-fill--danger')).toBeTruthy();
  });

  it('shows ∞ + "Безлимит" branch when total === 0', () => {
    render(ConsultingHoursWidget, { used: 5, total: 0 });
    expect(screen.getByText('∞')).toBeTruthy();
    // No percent shown в unlimited mode
    expect(screen.queryByText(/%/)).toBeNull();
    expect(screen.getByText(/безлимит/i)).toBeTruthy();
    expect(document.querySelector('.hours-fill--unlimited')).toBeTruthy();
  });

  it('caps visual fill at 100% когда used > total but shows actual numbers', () => {
    render(ConsultingHoursWidget, { used: 45, total: 40 });
    expect(screen.getByText('45')).toBeTruthy();
    expect(screen.getByText('40')).toBeTruthy();
    const fill = document.querySelector('.hours-fill') as HTMLElement | null;
    expect(fill).toBeTruthy();
    expect(fill?.style.width).toBe('100%');
  });

  it('clamps negative inputs к 0 defensively (treats as unlimited)', () => {
    render(ConsultingHoursWidget, { used: -5, total: -10 });
    expect(screen.getByText('0')).toBeTruthy(); // clamped used
    // total clamped to 0 → unlimited mode kicks in
    expect(screen.getByText(/безлимит/i)).toBeTruthy();
  });

  it('exposes role="meter" с aria-valuenow/min/max + aria-label', () => {
    render(ConsultingHoursWidget, { used: 24, total: 40 });
    const meter = screen.getByRole('meter');
    expect(meter.getAttribute('aria-valuenow')).toBe('24');
    expect(meter.getAttribute('aria-valuemin')).toBe('0');
    expect(meter.getAttribute('aria-valuemax')).toBe('40');
    expect(meter.getAttribute('aria-label')).toBeTruthy();
  });

  it('accepts label prop override', () => {
    render(ConsultingHoursWidget, { used: 1, total: 10, label: 'Custom Header' });
    expect(screen.getByText('Custom Header')).toBeTruthy();
  });
});
