import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/svelte';

import DashboardOverviewCard from '../../src/lib/components/welcome/DashboardOverviewCard.svelte';
import {
  __setProjectsInvokeForTesting,
} from '../../src/lib/ipc/projects';
import type { InvokeFn } from '../../src/lib/ipc/client';

afterEach(() => {
  cleanup();
  // Reset projects.ts invoke override to a sentinel that throws if called
  __setProjectsInvokeForTesting((async (cmd: string) => {
    throw new Error(`Unexpected post-test invoke: ${cmd}`);
  }) as InvokeFn);
});

describe('DashboardOverviewCard', () => {
  it('renders pre-loaded stats without fetching via IPC', () => {
    const stats = {
      total_proxies: 3,
      total_analyses: 7,
      next_consulting_deadline: null,
    };
    render(DashboardOverviewCard, { stats });
    expect(screen.getByText('3')).toBeTruthy();
    expect(screen.getByText('7')).toBeTruthy();
  });

  it('exposes <section> с implicit role="region" + localized aria-label', () => {
    render(DashboardOverviewCard, {
      stats: { total_proxies: 0, total_analyses: 0, next_consulting_deadline: null },
    });
    // <section> with aria-label has implicit role="region" — Svelte a11y rule
    // a11y_no_redundant_roles forbids explicit role declaration.
    const region = screen.getByRole('region');
    expect(region).toBeTruthy();
    expect(region.tagName.toLowerCase()).toBe('section');
    expect(region.getAttribute('aria-label')).toBeTruthy();
  });

  it('shows "Не запланирован" placeholder when deadline is null', () => {
    render(DashboardOverviewCard, {
      stats: { total_proxies: 1, total_analyses: 2, next_consulting_deadline: null },
    });
    expect(screen.getByText(/не запланирован/i)).toBeTruthy();
  });

  it('renders "Сегодня" branch when deadline date is today', () => {
    const today = new Date();
    today.setHours(23, 59, 0, 0);
    render(DashboardOverviewCard, {
      stats: {
        total_proxies: 1,
        total_analyses: 1,
        next_consulting_deadline: { due_at: today.toISOString(), client_name: 'Acme' },
      },
    });
    expect(screen.getByText(/сегодня/i)).toBeTruthy();
    expect(screen.getByText('Acme')).toBeTruthy();
  });

  it('renders "Просрочено" branch when deadline is in the past', () => {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    render(DashboardOverviewCard, {
      stats: {
        total_proxies: 0,
        total_analyses: 0,
        next_consulting_deadline: { due_at: yesterday.toISOString(), client_name: 'X' },
      },
    });
    expect(screen.getByText(/просрочено/i)).toBeTruthy();
  });

  it('shows error state when listProjects throws', async () => {
    __setProjectsInvokeForTesting((async () => {
      throw new Error('IPC down');
    }) as InvokeFn);
    render(DashboardOverviewCard);
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeTruthy();
    });
    expect(screen.getByText(/ipc down/i)).toBeTruthy();
  });

  it('computes total_analyses as sum of version_count via IPC fetch', async () => {
    __setProjectsInvokeForTesting((async (cmd: string) => {
      if (cmd === 'list_projects') {
        return [
          {
            project_uuid: '1',
            name: 'A',
            created_at: '2026-01-01',
            last_modified: '2026-01-01',
            granularity: 'monthly' as const,
            version_count: 3,
            current_version_id: 1,
          },
          {
            project_uuid: '2',
            name: 'B',
            created_at: '2026-01-01',
            last_modified: '2026-01-01',
            granularity: 'monthly' as const,
            version_count: 5,
            current_version_id: 1,
          },
        ];
      }
      throw new Error(`Unexpected invoke: ${cmd}`);
    }) as InvokeFn);
    render(DashboardOverviewCard);
    await waitFor(() => {
      expect(screen.getByText('8')).toBeTruthy(); // 3 + 5 analyses
    });
    expect(screen.getByText('2')).toBeTruthy(); // 2 projects = total_proxies
  });
});
