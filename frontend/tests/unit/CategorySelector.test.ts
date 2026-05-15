// Vitest tests для CategorySelector (Phase Magic — category-aware onboarding).

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';

import CategorySelector from '../../src/lib/components/Onboarding/CategorySelector.svelte';

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  // Clean localStorage между тестами
  try {
    window.localStorage.removeItem('aurora.category');
  } catch {
    /* ignore */
  }
});

describe('CategorySelector', () => {
  it('renders header с приглашением', () => {
    render(CategorySelector, { onselect: vi.fn() });
    expect(screen.getByText('Какая у вас категория?')).toBeTruthy();
    expect(
      screen.getByText(/Aurora настроит примеры/),
    ).toBeTruthy();
  });

  it('renders 4 category options', () => {
    render(CategorySelector, { onselect: vi.fn() });
    expect(screen.getByText('Фарма OTC')).toBeTruthy();
    expect(screen.getByText('FMCG')).toBeTruthy();
    expect(screen.getByText('B2B')).toBeTruthy();
    expect(screen.getByText('Другое')).toBeTruthy();
  });

  it('shows category-specific examples', () => {
    render(CategorySelector, { onselect: vi.fn() });
    expect(screen.getByText('Кагоцел, Венарус, Терафлю')).toBeTruthy();
    expect(screen.getByText(/Косметика, бытовая химия/)).toBeTruthy();
    expect(screen.getByText(/SaaS, услуги/)).toBeTruthy();
  });

  it('clicking pharma option fires onselect с pharma_otc id', async () => {
    const onSelect = vi.fn();
    render(CategorySelector, { onselect: onSelect });
    const card = screen.getByText('Фарма OTC').closest('button');
    expect(card).toBeTruthy();
    await fireEvent.click(card!);
    expect(onSelect).toHaveBeenCalledWith('pharma_otc');
  });

  it('clicking fmcg option fires onselect с fmcg id', async () => {
    const onSelect = vi.fn();
    render(CategorySelector, { onselect: onSelect });
    const card = screen.getByText('FMCG').closest('button');
    await fireEvent.click(card!);
    expect(onSelect).toHaveBeenCalledWith('fmcg');
  });

  it('selection persists к localStorage', async () => {
    const onSelect = vi.fn();
    render(CategorySelector, { onselect: onSelect });
    const card = screen.getByText('B2B').closest('button');
    await fireEvent.click(card!);
    expect(window.localStorage.getItem('aurora.category')).toBe('b2b');
  });

  it('skip button visible когда onskip provided', () => {
    render(CategorySelector, { onselect: vi.fn(), onskip: vi.fn() });
    expect(screen.getByText(/Пропустить/)).toBeTruthy();
  });

  it('skip button absent когда onskip omitted', () => {
    render(CategorySelector, { onselect: vi.fn() });
    expect(screen.queryByText(/Пропустить/)).toBeNull();
  });

  it('clicking skip fires onskip callback', async () => {
    const onSkip = vi.fn();
    render(CategorySelector, { onselect: vi.fn(), onskip: onSkip });
    const skipBtn = screen.getByText(/Пропустить/);
    await fireEvent.click(skipBtn);
    expect(onSkip).toHaveBeenCalledOnce();
  });

  it('skip does NOT save к localStorage', async () => {
    const onSkip = vi.fn();
    render(CategorySelector, { onselect: vi.fn(), onskip: onSkip });
    await fireEvent.click(screen.getByText(/Пропустить/));
    expect(window.localStorage.getItem('aurora.category')).toBeNull();
  });

  it('section has correct aria-label', () => {
    const { container } = render(CategorySelector, { onselect: vi.fn() });
    const section = container.querySelector('section');
    expect(section?.getAttribute('aria-label')).toBe('Выбор категории бренда');
  });
});
