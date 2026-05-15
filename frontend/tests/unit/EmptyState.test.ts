// Vitest tests for EmptyState.svelte (Phase Premium P-07).

import { describe, expect, it, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';

import EmptyState from '../../src/lib/components/EmptyState.svelte';

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('EmptyState', () => {
  it('renders title and body text', () => {
    render(EmptyState, {
      title: 'Здесь будет ваша история',
      body: 'Каждый сохранённый прогноз появится в этой ленте.',
    });
    expect(screen.getByText('Здесь будет ваша история')).toBeTruthy();
    expect(screen.getByText('Каждый сохранённый прогноз появится в этой ленте.')).toBeTruthy();
  });

  it('renders emoji icon when icon prop is a string', () => {
    render(EmptyState, { title: 'Пусто', body: 'Ничего нет.', icon: '📋' });
    expect(screen.getByText('📋')).toBeTruthy();
  });

  it('does not render icon span when icon prop is omitted', () => {
    render(EmptyState, { title: 'Пусто', body: 'Текст' });
    // No element with emoji text
    expect(screen.queryByText('📋')).toBeNull();
  });

  it('calls primaryAction.onClick when primary button clicked', async () => {
    const onClick = vi.fn();
    render(EmptyState, {
      title: 'Пусто',
      body: 'Текст',
      primaryAction: { label: 'Создать прогноз', onClick },
    });
    const btn = screen.getByRole('button', { name: 'Создать прогноз' });
    await fireEvent.click(btn);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('calls secondaryAction.onClick when secondary button clicked', async () => {
    const primary = vi.fn();
    const secondary = vi.fn();
    render(EmptyState, {
      title: 'Пусто',
      body: 'Текст',
      primaryAction: { label: 'Главное действие', onClick: primary },
      secondaryAction: { label: 'Второстепенное', onClick: secondary },
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Второстепенное' }));
    expect(secondary).toHaveBeenCalledTimes(1);
    expect(primary).not.toHaveBeenCalled();
  });

  it('renders no buttons when no actions provided', () => {
    render(EmptyState, { title: 'Пусто', body: 'Текст' });
    expect(screen.queryAllByRole('button')).toHaveLength(0);
  });

  it('renders only primary button when secondaryAction omitted', () => {
    render(EmptyState, {
      title: 'Пусто',
      body: 'Текст',
      primaryAction: { label: 'Главное', onClick: vi.fn() },
    });
    expect(screen.getAllByRole('button')).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'Главное' })).toBeTruthy();
  });

  it('has aria-live="polite" for screen reader announcement', () => {
    const { container } = render(EmptyState, { title: 'Пусто', body: 'Текст' });
    const section = container.querySelector('[role="status"]');
    expect(section).toBeTruthy();
    expect(section?.getAttribute('aria-live')).toBe('polite');
  });

  it('adds compact class when compact=true', () => {
    const { container } = render(EmptyState, {
      title: 'Пусто',
      body: 'Текст',
      compact: true,
    });
    const section = container.querySelector('.empty-state');
    expect(section?.classList.contains('compact')).toBe(true);
  });

  it('does not add compact class by default', () => {
    const { container } = render(EmptyState, { title: 'Пусто', body: 'Текст' });
    const section = container.querySelector('.empty-state');
    expect(section?.classList.contains('compact')).toBe(false);
  });

  it('aria-label on section matches title prop', () => {
    const { container } = render(EmptyState, {
      title: 'Журнал пока пуст',
      body: 'Данные появятся здесь.',
    });
    const section = container.querySelector('[role="status"]');
    expect(section?.getAttribute('aria-label')).toBe('Журнал пока пуст');
  });
});
