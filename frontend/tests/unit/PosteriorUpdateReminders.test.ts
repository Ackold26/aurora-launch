import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/svelte';

import PosteriorUpdateReminders from '../../src/lib/components/welcome/PosteriorUpdateReminders.svelte';
import {
  __setInvokeForTesting,
  type InvokeFn,
  type PendingPosteriorUpdateItem,
} from '../../src/lib/ipc/client';

afterEach(() => {
  cleanup();
  __setInvokeForTesting((async (cmd: string) => {
    throw new Error(`Unexpected post-test invoke: ${cmd}`);
  }) as InvokeFn);
});

describe('PosteriorUpdateReminders', () => {
  const sampleItems: PendingPosteriorUpdateItem[] = [
    {
      project_uuid: 'uuid-fresh',
      name: 'Свежий проект',
      last_actuals_update_at: '2026-04-15T10:00:00Z',
      weeks_since_update: 2,
    },
    {
      project_uuid: 'uuid-stale',
      name: 'Устаревающий проект',
      last_actuals_update_at: '2026-03-01T10:00:00Z',
      weeks_since_update: 6,
    },
    {
      project_uuid: 'uuid-critical',
      name: 'Критический проект',
      last_actuals_update_at: '2026-01-01T10:00:00Z',
      weeks_since_update: 12,
    },
  ];

  it('renders pre-loaded items prop без IPC fetch', () => {
    render(PosteriorUpdateReminders, { items: sampleItems });
    expect(screen.getByText('Свежий проект')).toBeTruthy();
    expect(screen.getByText('Устаревающий проект')).toBeTruthy();
    expect(screen.getByText('Критический проект')).toBeTruthy();
  });

  it('renders empty state когда items === []', () => {
    render(PosteriorUpdateReminders, { items: [] });
    // Empty state uses class .reminders-empty
    expect(document.querySelector('.reminders-empty')).toBeTruthy();
  });

  it('shows loading skeleton aria-busy при отсутствии itemsProp', () => {
    // Use never-resolving promise to keep loading state
    __setInvokeForTesting((() => new Promise(() => {})) as InvokeFn);
    render(PosteriorUpdateReminders);
    const busy = document.querySelector('[aria-busy="true"]');
    expect(busy).toBeTruthy();
    expect(document.querySelector('.skeleton-row')).toBeTruthy();
  });

  it('shows error state с alert role когда IPC throws', async () => {
    __setInvokeForTesting((async () => {
      throw new Error('Backend down');
    }) as InvokeFn);
    render(PosteriorUpdateReminders);
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeTruthy();
    });
    expect(screen.getByText(/backend down/i)).toBeTruthy();
  });

  it('применяет urgency CSS class по weeks_since_update порогам', () => {
    render(PosteriorUpdateReminders, { items: sampleItems });
    expect(document.querySelector('.reminder--fresh')).toBeTruthy();    // 2 weeks
    expect(document.querySelector('.reminder--stale')).toBeTruthy();    // 6 weeks
    expect(document.querySelector('.reminder--critical')).toBeTruthy(); // 12 weeks
  });

  it('renders CTA как <a> с href /inspector?project={uuid}', () => {
    render(PosteriorUpdateReminders, { items: [sampleItems[0]!] });
    const link = document.querySelector('a.reminder-cta') as HTMLAnchorElement | null;
    expect(link).toBeTruthy();
    expect(link?.getAttribute('href')).toBe('/inspector?project=uuid-fresh');
    expect(link?.getAttribute('aria-label')).toBeTruthy();
  });

  it('shows "Актуалы ещё не загружены" branch когда last_actuals_update_at === null', () => {
    const items: PendingPosteriorUpdateItem[] = [
      {
        project_uuid: 'uuid-never',
        name: 'Новый проект',
        last_actuals_update_at: null,
        weeks_since_update: 999,
      },
    ];
    render(PosteriorUpdateReminders, { items });
    // Match RU translation для never_updated key
    expect(screen.getByText(/ещё не загружен/i)).toBeTruthy();
  });

  it('fetches items via IPC когда itemsProp undefined', async () => {
    __setInvokeForTesting((async (cmd: string) => {
      if (cmd === 'list_pending_posterior_updates') {
        return sampleItems;
      }
      throw new Error(`Unexpected cmd: ${cmd}`);
    }) as InvokeFn);
    render(PosteriorUpdateReminders);
    await waitFor(() => {
      expect(screen.getByText('Свежий проект')).toBeTruthy();
    });
    expect(screen.getByText('Устаревающий проект')).toBeTruthy();
  });

  it('exposes <section> с localized aria-label', () => {
    render(PosteriorUpdateReminders, { items: sampleItems });
    const region = screen.getByRole('region');
    expect(region.tagName.toLowerCase()).toBe('section');
    expect(region.getAttribute('aria-label')).toBeTruthy();
  });
});
