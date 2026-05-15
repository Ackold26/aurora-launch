// Vitest tests для PatternSuggestionCard (Phase Magic M-06).

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';
import PatternSuggestionCard from '../../src/lib/components/PatternSuggestionCard.svelte';
import type { PatternMatch } from '../../src/lib/services/pattern-matcher';
import type { ProjectSummary } from '../../src/lib/ipc/projects';

vi.mock('$app/navigation', () => ({
  goto: vi.fn(),
}));

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function mkMatch(overrides: Partial<ProjectSummary> = {}, score = 80): PatternMatch {
  return {
    project: {
      project_uuid: overrides.project_uuid ?? 'p-1',
      name: overrides.name ?? 'Кагоцел Июнь 2025',
      created_at: overrides.created_at ?? new Date(Date.now() - 30 * 86400000).toISOString(),
      last_modified: overrides.last_modified ?? new Date(Date.now() - 15 * 86400000).toISOString(),
      granularity: overrides.granularity ?? 'monthly',
      version_count: overrides.version_count ?? 3,
      current_version_id: overrides.current_version_id ?? 1,
    },
    score,
    reasons: ['категория pharma_otc', 'свежий (15 дн. назад)', '3 версии'],
  };
}

describe('PatternSuggestionCard', () => {
  it('renders nothing когда forceMatches=[]', () => {
    const { container } = render(PatternSuggestionCard, { forceMatches: [] });
    expect(container.querySelector('.pattern-suggestion')).toBeNull();
  });

  it('renders header с приглашением', () => {
    render(PatternSuggestionCard, { forceMatches: [mkMatch()] });
    expect(screen.getByText(/Похоже на ваш предыдущий запуск/)).toBeTruthy();
  });

  it('singular phrasing для 1 match', () => {
    render(PatternSuggestionCard, { forceMatches: [mkMatch()] });
    expect(screen.getByText(/один похожий проект/)).toBeTruthy();
  });

  it('plural phrasing для 2+ matches', () => {
    render(PatternSuggestionCard, {
      forceMatches: [mkMatch({ project_uuid: 'a', name: 'A' }), mkMatch({ project_uuid: 'b', name: 'B' })],
    });
    expect(screen.getByText(/2 похожих проекта/)).toBeTruthy();
  });

  it('renders match name + reasons', () => {
    render(PatternSuggestionCard, { forceMatches: [mkMatch()] });
    expect(screen.getByText('Кагоцел Июнь 2025')).toBeTruthy();
    expect(screen.getByText(/категория pharma_otc.*свежий.*3 версии/)).toBeTruthy();
  });

  it('clicking match fires goto с правильным URL', async () => {
    const { goto } = await import('$app/navigation');
    render(PatternSuggestionCard, {
      forceMatches: [mkMatch({ project_uuid: 'xyz', name: 'TestProj' })],
    });
    const card = screen.getByText('TestProj').closest('button');
    await fireEvent.click(card!);
    expect(goto).toHaveBeenCalledWith('/project/xyz/history');
  });

  it('dismiss button hides component', async () => {
    render(PatternSuggestionCard, { forceMatches: [mkMatch()] });
    const dismiss = screen.getByLabelText('Скрыть подсказку');
    await fireEvent.click(dismiss);
    expect(screen.queryByText(/Похоже на ваш предыдущий/)).toBeNull();
  });

  it('renders multiple matches as list items', () => {
    render(PatternSuggestionCard, {
      forceMatches: [
        mkMatch({ project_uuid: '1', name: 'P1' }),
        mkMatch({ project_uuid: '2', name: 'P2' }),
        mkMatch({ project_uuid: '3', name: 'P3' }),
      ],
    });
    expect(screen.getByText('P1')).toBeTruthy();
    expect(screen.getByText('P2')).toBeTruthy();
    expect(screen.getByText('P3')).toBeTruthy();
  });

  it('section has aria-label', () => {
    const { container } = render(PatternSuggestionCard, {
      forceMatches: [mkMatch()],
    });
    const section = container.querySelector('section');
    expect(section?.getAttribute('aria-label')).toBe('Похожие предыдущие запуски');
  });

  it('version_count=1 renders «1 версия» singular', () => {
    render(PatternSuggestionCard, {
      forceMatches: [mkMatch({ version_count: 1 })],
    });
    expect(screen.getByText(/1 версия$/)).toBeTruthy();
  });
});
