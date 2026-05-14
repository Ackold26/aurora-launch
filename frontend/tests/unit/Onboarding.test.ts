// Vitest tests для Onboarding components (Phase Premium P-01).

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/svelte';

import WelcomeAnimation from '../../src/lib/components/Onboarding/WelcomeAnimation.svelte';
import TutorialCarousel from '../../src/lib/components/Onboarding/TutorialCarousel.svelte';

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('WelcomeAnimation', () => {
  it('renders brand mark + tagline', () => {
    render(WelcomeAnimation, { instant: true });
    expect(screen.getByText('Aurora')).toBeTruthy();
    expect(screen.getByText('Launch Planner')).toBeTruthy();
  });

  it('calls oncomplete callback after timeout', async () => {
    vi.useFakeTimers();
    const onComplete = vi.fn();
    render(WelcomeAnimation, { instant: true, oncomplete: onComplete });
    // Advance timers — instant=true → 0ms timer
    vi.advanceTimersByTime(10);
    await waitFor(() => {
      expect(onComplete).toHaveBeenCalledOnce();
    });
    vi.useRealTimers();
  });

  it('does NOT call oncomplete twice on multiple ticks', async () => {
    vi.useFakeTimers();
    const onComplete = vi.fn();
    render(WelcomeAnimation, { instant: true, oncomplete: onComplete });
    vi.advanceTimersByTime(100);
    vi.advanceTimersByTime(200);
    vi.advanceTimersByTime(500);
    await waitFor(() => {
      expect(onComplete).toHaveBeenCalledOnce();
    });
    vi.useRealTimers();
  });
});

describe('TutorialCarousel', () => {
  it('renders first slide by default', () => {
    render(TutorialCarousel, {});
    expect(screen.getByText(/Прогноз запуска нового бренда/)).toBeTruthy();
    expect(screen.getByText('1 / 5')).toBeTruthy();
  });

  it('Next button advances slide', async () => {
    render(TutorialCarousel, {});
    const nextBtn = screen.getByRole('button', { name: /Следующий слайд/ });
    await fireEvent.click(nextBtn);
    expect(screen.getByText(/Загрузка данных/)).toBeTruthy();
    expect(screen.getByText('2 / 5')).toBeTruthy();
  });

  it('Back button regresses slide', async () => {
    render(TutorialCarousel, {});
    const nextBtn = screen.getByRole('button', { name: /Следующий слайд/ });
    await fireEvent.click(nextBtn);
    await fireEvent.click(nextBtn);
    const backBtn = screen.getByRole('button', { name: /Предыдущий слайд/ });
    await fireEvent.click(backBtn);
    expect(screen.getByText('2 / 5')).toBeTruthy();
  });

  it('Back button disabled on first slide', () => {
    render(TutorialCarousel, {});
    const backBtn = screen.getByRole('button', { name: /Предыдущий слайд/ });
    expect((backBtn as HTMLButtonElement).disabled).toBe(true);
  });

  it('shows CTAs on last slide instead of Next', async () => {
    render(TutorialCarousel, {});
    const nextBtn = screen.getByRole('button', { name: /Следующий слайд/ });
    // Advance к last slide (5 of 5)
    for (let i = 0; i < 4; i++) {
      await fireEvent.click(nextBtn);
    }
    expect(screen.getByText('5 / 5')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Открыть пример' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Начать с нуля' })).toBeTruthy();
  });

  it('clicking Skip fires onskip callback', async () => {
    const onSkip = vi.fn();
    render(TutorialCarousel, { onskip: onSkip });
    const skipBtn = screen.getByRole('button', { name: /Пропустить/ });
    await fireEvent.click(skipBtn);
    expect(onSkip).toHaveBeenCalledOnce();
  });

  it('clicking sample CTA on last slide fires onsample callback', async () => {
    const onSample = vi.fn();
    render(TutorialCarousel, { onsample: onSample });
    const nextBtn = screen.getByRole('button', { name: /Следующий слайд/ });
    for (let i = 0; i < 4; i++) await fireEvent.click(nextBtn);
    await fireEvent.click(screen.getByRole('button', { name: 'Открыть пример' }));
    expect(onSample).toHaveBeenCalledOnce();
  });

  it('clicking blank CTA on last slide fires onblank callback', async () => {
    const onBlank = vi.fn();
    render(TutorialCarousel, { onblank: onBlank });
    const nextBtn = screen.getByRole('button', { name: /Следующий слайд/ });
    for (let i = 0; i < 4; i++) await fireEvent.click(nextBtn);
    await fireEvent.click(screen.getByRole('button', { name: 'Начать с нуля' }));
    expect(onBlank).toHaveBeenCalledOnce();
  });

  it('dot click jumps to that slide', async () => {
    render(TutorialCarousel, {});
    const dots = screen.getAllByRole('tab');
    expect(dots).toHaveLength(5);
    await fireEvent.click(dots[3]!);
    expect(screen.getByText('4 / 5')).toBeTruthy();
  });

  it('first dot has aria-selected=true initially', () => {
    render(TutorialCarousel, {});
    const dots = screen.getAllByRole('tab');
    expect(dots[0]!.getAttribute('aria-selected')).toBe('true');
    expect(dots[1]!.getAttribute('aria-selected')).toBe('false');
  });

  it('ArrowRight keyboard navigates next', async () => {
    render(TutorialCarousel, {});
    await fireEvent.keyDown(window, { key: 'ArrowRight' });
    expect(screen.getByText('2 / 5')).toBeTruthy();
  });

  it('ArrowLeft keyboard navigates previous', async () => {
    render(TutorialCarousel, {});
    await fireEvent.keyDown(window, { key: 'ArrowRight' });
    await fireEvent.keyDown(window, { key: 'ArrowRight' });
    await fireEvent.keyDown(window, { key: 'ArrowLeft' });
    expect(screen.getByText('2 / 5')).toBeTruthy();
  });

  it('Escape keyboard fires onskip', async () => {
    const onSkip = vi.fn();
    render(TutorialCarousel, { onskip: onSkip });
    await fireEvent.keyDown(window, { key: 'Escape' });
    expect(onSkip).toHaveBeenCalledOnce();
  });

  it('custom slides prop overrides defaults', () => {
    const custom = [
      { title: 'Custom 1', body: 'Body 1' },
      { title: 'Custom 2', body: 'Body 2' },
    ];
    render(TutorialCarousel, { slides: custom });
    expect(screen.getByText('Custom 1')).toBeTruthy();
    expect(screen.getByText('1 / 2')).toBeTruthy();
  });
});
