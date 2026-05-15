// Vitest tests для daily-insights service (Phase Magic M-07).

import { describe, expect, it, beforeEach, vi } from 'vitest';
import {
  computeDailyInsight,
  shouldShowInsight,
  markInsightShown,
} from '../../src/lib/services/daily-insights';
import type { ProjectSummary } from '../../src/lib/ipc/projects';

const DAY_MS = 1000 * 60 * 60 * 24;

function isoDaysAgo(days: number): string {
  return new Date(Date.now() - days * DAY_MS).toISOString();
}

function mkProject(overrides: Partial<ProjectSummary> = {}): ProjectSummary {
  return {
    project_uuid: overrides.project_uuid ?? 'p-' + Math.random().toString(36).slice(2, 8),
    name: overrides.name ?? 'Sample',
    created_at: overrides.created_at ?? isoDaysAgo(40),
    last_modified: overrides.last_modified ?? isoDaysAgo(1),
    granularity: overrides.granularity ?? 'monthly',
    version_count: overrides.version_count ?? 1,
    current_version_id: overrides.current_version_id ?? 1,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  try {
    window.localStorage.clear();
  } catch {
    /* ignore */
  }
});

describe('computeDailyInsight', () => {
  it('returns null когда нет projects + не онбординг', () => {
    const result = computeDailyInsight([]);
    expect(result).toBeNull();
  });

  it('returns onboarding nudge когда onboarded + 0 projects', () => {
    window.localStorage.setItem('aurora.onboarded', '1');
    const result = computeDailyInsight([]);
    expect(result).toBeTruthy();
    expect(result!.id).toBe('onboarding_nudge');
    expect(result!.severity).toBe('info');
    expect(result!.ctaHref).toBe('/onboarding');
  });

  it('returns null для свежих projects (< 14 days)', () => {
    const projects = [mkProject({ last_modified: isoDaysAgo(3) })];
    const result = computeDailyInsight(projects);
    expect(result).toBeNull();
  });

  it('returns stale insight для проекта 14-30 days old', () => {
    const proj = mkProject({ name: 'Кагоцел', last_modified: isoDaysAgo(20) });
    const result = computeDailyInsight([proj]);
    expect(result).toBeTruthy();
    expect(result!.id).toBe('stale_forecast');
    expect(result!.severity).toBe('info');
    expect(result!.title).toContain('Кагоцел');
    expect(result!.projectUuid).toBe(proj.project_uuid);
  });

  it('returns very_stale warning для проекта > 30 days', () => {
    const proj = mkProject({ name: 'Венарус', last_modified: isoDaysAgo(45) });
    const result = computeDailyInsight([proj]);
    expect(result).toBeTruthy();
    expect(result!.id).toBe('very_stale_forecast');
    expect(result!.severity).toBe('warning');
    expect(result!.title).toContain('Венарус');
    expect(result!.title).toContain('45');
  });

  it('prefers very-stale over stale когда оба присутствуют', () => {
    const stale = mkProject({ name: 'A', last_modified: isoDaysAgo(20) });
    const veryStale = mkProject({ name: 'B', last_modified: isoDaysAgo(60) });
    const result = computeDailyInsight([stale, veryStale]);
    expect(result!.id).toBe('very_stale_forecast');
    expect(result!.title).toContain('B');
  });

  it('returns cross-sell insight когда ≥5 projects, все свежие', () => {
    const projects = Array.from({ length: 6 }, (_, i) =>
      mkProject({ name: `P${i}`, last_modified: isoDaysAgo(2) }),
    );
    const result = computeDailyInsight(projects);
    expect(result).toBeTruthy();
    expect(result!.id).toBe('power_user_cross_sell');
    expect(result!.severity).toBe('success');
    expect(result!.title).toContain('6');
  });

  it('не возвращает cross-sell когда есть stale (приоритет stale)', () => {
    const fresh = Array.from({ length: 5 }, () =>
      mkProject({ last_modified: isoDaysAgo(2) }),
    );
    const stale = mkProject({ last_modified: isoDaysAgo(25) });
    const result = computeDailyInsight([stale, ...fresh]);
    expect(result!.id).toBe('stale_forecast');
  });
});

describe('shouldShowInsight + markInsightShown', () => {
  it('returns true когда никогда не показывали', () => {
    expect(shouldShowInsight()).toBe(true);
  });

  it('returns false после markInsightShown сегодня', () => {
    markInsightShown();
    expect(shouldShowInsight()).toBe(false);
  });

  it('returns true если последний показ был вчера', () => {
    const yesterday = new Date(Date.now() - DAY_MS);
    const y = yesterday.getFullYear();
    const m = String(yesterday.getMonth() + 1).padStart(2, '0');
    const d = String(yesterday.getDate()).padStart(2, '0');
    window.localStorage.setItem('aurora.last-insight-shown', `${y}-${m}-${d}`);
    expect(shouldShowInsight()).toBe(true);
  });

  it('markInsightShown survives missing localStorage gracefully', () => {
    // Simulate restricted environment
    const original = window.localStorage;
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      get() {
        throw new Error('Storage disabled');
      },
    });
    expect(() => markInsightShown()).not.toThrow();
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: original,
    });
  });
});
