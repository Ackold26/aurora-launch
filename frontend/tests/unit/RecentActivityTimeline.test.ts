// Vitest tests for RecentActivityTimeline.svelte (Sprint 1 UX Foundation).
//
// IPC mocked via __setInvokeForTesting (client.ts: list_audit_entries).
// Note: navigation goto() called from empty-state CTA is stubbed via vi.mock
// so jsdom doesn't bail on real route resolution.

import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/svelte';

// goto stub — vi.mock hoisting requires definition BEFORE component import.
vi.mock('$app/navigation', () => ({
  goto: vi.fn(async () => {}),
}));

import RecentActivityTimeline from '../../src/lib/components/welcome/RecentActivityTimeline.svelte';
import {
  __setInvokeForTesting,
  type AuditEntry,
  type InvokeFn,
} from '../../src/lib/ipc/client';

afterEach(() => {
  cleanup();
  // Reset client.ts invoke override to a sentinel that throws if called.
  __setInvokeForTesting((async (cmd: string) => {
    throw new Error(`Unexpected post-test invoke: ${cmd}`);
  }) as InvokeFn);
});

// ── Fixtures ────────────────────────────────────────────────────────────────

function makeEntry(
  id: number,
  operation: string,
  timestamp: string,
  outcome = 'success',
  target: string | null = null,
): AuditEntry {
  return {
    id,
    timestamp,
    actor: 'user',
    operation,
    target,
    outcome,
    details: {},
  };
}

const NOW_MS = Date.now();
const isoFromOffset = (offsetMs: number) =>
  new Date(NOW_MS - offsetMs).toISOString();

// ── Tests ───────────────────────────────────────────────────────────────────

describe('RecentActivityTimeline', () => {
  it('renders entries prop directly без IPC fetch', () => {
    const entries = [
      makeEntry(3, 'create_project', isoFromOffset(2 * 60 * 1000), 'success', 'Acme Beverages'),
      makeEntry(2, 'save_bundle', isoFromOffset(10 * 60 * 1000), 'success', 'forecast.aurora'),
      makeEntry(1, 'start_forecast', isoFromOffset(30 * 60 * 1000), 'success'),
    ];
    render(RecentActivityTimeline, { entries });
    // Two items have visible targets (item 1 has no target).
    expect(screen.getByText('Acme Beverages')).toBeTruthy();
    expect(screen.getByText('forecast.aurora')).toBeTruthy();
    // <section> with aria-label exposes implicit role="region".
    const region = screen.getByRole('region');
    expect(region.tagName.toLowerCase()).toBe('section');
  });

  it('empty state shown когда entries === []', () => {
    render(RecentActivityTimeline, { entries: [] });
    // Empty state has a CTA button (К списку проектов).
    const cta = screen.getByRole('button');
    expect(cta).toBeTruthy();
    // No list items rendered (the empty container is a div, not <ul>).
    expect(screen.queryAllByRole('listitem')).toHaveLength(0);
  });

  it('empty state shown когда IPC fetch returns []', async () => {
    __setInvokeForTesting((async (cmd: string) => {
      if (cmd === 'list_audit_entries') return [] as AuditEntry[];
      throw new Error(`Unexpected invoke: ${cmd}`);
    }) as InvokeFn);
    render(RecentActivityTimeline);
    await waitFor(() => {
      expect(screen.getByRole('button')).toBeTruthy();
    });
    expect(screen.queryAllByRole('listitem')).toHaveLength(0);
  });

  it('skeleton aria-busy shown during loading (never-resolving fetch)', () => {
    // Never-resolving promise — fetchLoading stays true forever.
    __setInvokeForTesting((() => new Promise(() => {})) as InvokeFn);
    render(RecentActivityTimeline);
    const list = document.querySelector('[aria-busy="true"]');
    expect(list).toBeTruthy();
    // 4 skeleton placeholders per spec.
    expect(document.querySelectorAll('.skeleton-row').length).toBe(4);
  });

  it('error state с role="alert" когда fetch throws', async () => {
    __setInvokeForTesting((async () => {
      throw new Error('IPC down');
    }) as InvokeFn);
    render(RecentActivityTimeline);
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeTruthy();
    });
    expect(screen.getByText(/ipc down/i)).toBeTruthy();
    // Retry button exists.
    expect(screen.getByRole('button')).toBeTruthy();
  });

  it('limit=3 → only 3 items rendered (override default 8)', () => {
    const entries = Array.from({ length: 8 }, (_, i) =>
      makeEntry(i + 1, 'create_project', isoFromOffset((i + 1) * 60 * 1000)),
    ).reverse(); // newest first
    render(RecentActivityTimeline, { entries, limit: 3 });
    const items = screen.getAllByRole('listitem');
    expect(items).toHaveLength(3);
  });

  it('relative time formatting renders a <time> with datetime attr for each entry', () => {
    // Note: i18n keys для dashboard.activity.* добавляются Opus thread'ом
    // в отдельном batch step. До этого svelte-i18n возвращает raw key для
    // missing entries. Поэтому проверяем структуру <time datetime>, а не
    // localized текст (он будет «dashboard.activity.minutes_ago» как fallback).
    const recentIso = isoFromOffset(30 * 1000);
    const fiveIso = isoFromOffset(5 * 60 * 1000);
    const entries = [
      makeEntry(2, 'create_project', recentIso, 'success', 'Recent'),
      makeEntry(1, 'save_bundle', fiveIso, 'success', 'FiveMin'),
    ];
    render(RecentActivityTimeline, { entries });

    const recentRow = screen.getByText('Recent').closest('.activity-item');
    const fiveRow = screen.getByText('FiveMin').closest('.activity-item');
    expect(recentRow).toBeTruthy();
    expect(fiveRow).toBeTruthy();

    const recentTimeEl = recentRow?.querySelector('time');
    const fiveTimeEl = fiveRow?.querySelector('time');
    expect(recentTimeEl).toBeTruthy();
    expect(fiveTimeEl).toBeTruthy();
    // <time datetime="…ISO timestamp…"> — provides semantic timestamp for AT.
    expect(recentTimeEl?.getAttribute('datetime')).toBe(recentIso);
    expect(fiveTimeEl?.getAttribute('datetime')).toBe(fiveIso);
    // Time text non-empty (either localized phrase or raw key fallback).
    expect((recentTimeEl?.textContent ?? '').length).toBeGreaterThan(0);
    expect((fiveTimeEl?.textContent ?? '').length).toBeGreaterThan(0);
    // Two distinct branches → two distinct strings (just_now key vs minutes_ago key).
    expect(recentTimeEl?.textContent).not.toBe(fiveTimeEl?.textContent);
  });

  it('items rendered в order provided by parent (newest first)', () => {
    // Backend orders by id DESC; pass in newest-first order, verify
    // DOM preserves that order.
    const entries = [
      makeEntry(99, 'create_project', isoFromOffset(60 * 1000), 'success', 'NewestProject'),
      makeEntry(50, 'save_bundle', isoFromOffset(2 * 3600 * 1000), 'success', 'MiddleProject'),
      makeEntry(1, 'start_forecast', isoFromOffset(48 * 3600 * 1000), 'success', 'OldestProject'),
    ];
    render(RecentActivityTimeline, { entries });
    const items = screen.getAllByRole('listitem');
    expect(items).toHaveLength(3);
    // Targets appear in same order as entries array.
    expect(items[0]?.textContent ?? '').toContain('NewestProject');
    expect(items[1]?.textContent ?? '').toContain('MiddleProject');
    expect(items[2]?.textContent ?? '').toContain('OldestProject');
  });

  it('aria-label на section is set (localized)', () => {
    render(RecentActivityTimeline, { entries: [] });
    const region = screen.getByRole('region');
    const label = region.getAttribute('aria-label');
    expect(label).toBeTruthy();
    // Either localized Russian or raw key fallback — both are non-empty.
    expect((label ?? '').length).toBeGreaterThan(0);
  });

  it('outcome → color CSS class applied to dot', () => {
    const entries = [
      makeEntry(3, 'create_project', isoFromOffset(60 * 1000), 'success', 'A'),
      makeEntry(2, 'save_bundle', isoFromOffset(120 * 1000), 'error', 'B'),
      makeEntry(1, 'start_forecast', isoFromOffset(180 * 1000), 'warning', 'C'),
    ];
    render(RecentActivityTimeline, { entries });
    expect(document.querySelector('.activity-dot--success')).toBeTruthy();
    expect(document.querySelector('.activity-dot--error')).toBeTruthy();
    expect(document.querySelector('.activity-dot--warning')).toBeTruthy();
  });
});
