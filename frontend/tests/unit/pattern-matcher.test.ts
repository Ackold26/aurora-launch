// Vitest tests для pattern-matcher service (Phase Magic M-06).

import { describe, expect, it, beforeEach } from 'vitest';
import {
  findSimilarPastLaunches,
  formatRecency,
  getStoredCategory,
} from '../../src/lib/services/pattern-matcher';
import type { ProjectSummary } from '../../src/lib/ipc/projects';

const DAY_MS = 1000 * 60 * 60 * 24;

function isoDaysAgo(days: number): string {
  return new Date(Date.now() - days * DAY_MS).toISOString();
}

function mkProject(overrides: Partial<ProjectSummary> = {}): ProjectSummary {
  return {
    project_uuid: overrides.project_uuid ?? 'p-' + Math.random().toString(36).slice(2, 8),
    name: overrides.name ?? 'Sample',
    created_at: overrides.created_at ?? isoDaysAgo(90),
    last_modified: overrides.last_modified ?? isoDaysAgo(30),
    granularity: overrides.granularity ?? 'monthly',
    version_count: overrides.version_count ?? 1,
    current_version_id: overrides.current_version_id ?? 1,
  };
}

beforeEach(() => {
  try {
    window.localStorage.clear();
  } catch {
    /* ignore */
  }
});

describe('getStoredCategory', () => {
  it('returns null когда category не set', () => {
    expect(getStoredCategory()).toBeNull();
  });

  it('returns stored category', () => {
    window.localStorage.setItem('aurora.category', 'pharma_otc');
    expect(getStoredCategory()).toBe('pharma_otc');
  });
});

describe('findSimilarPastLaunches', () => {
  it('returns empty без category', () => {
    const projects = [mkProject({ name: 'A' })];
    expect(findSimilarPastLaunches(projects)).toEqual([]);
  });

  it('returns empty с category но без projects', () => {
    window.localStorage.setItem('aurora.category', 'fmcg');
    expect(findSimilarPastLaunches([])).toEqual([]);
  });

  it('returns base match (score=50) когда category set + 1 stale project', () => {
    const proj = mkProject({ last_modified: isoDaysAgo(180), version_count: 1 });
    const result = findSimilarPastLaunches([proj], 'pharma_otc');
    expect(result).toHaveLength(1);
    expect(result[0]!.score).toBe(50);
    expect(result[0]!.reasons).toContain('категория pharma_otc');
  });

  it('adds +30 recency bonus (≤90 days)', () => {
    const proj = mkProject({ last_modified: isoDaysAgo(15), version_count: 1 });
    const result = findSimilarPastLaunches([proj], 'fmcg');
    expect(result[0]!.score).toBe(80);
    expect(result[0]!.reasons.some((r) => r.includes('свежий'))).toBe(true);
  });

  it('adds +20 maturity bonus (≥3 versions)', () => {
    const proj = mkProject({ last_modified: isoDaysAgo(180), version_count: 5 });
    const result = findSimilarPastLaunches([proj], 'b2b');
    expect(result[0]!.score).toBe(70);
    expect(result[0]!.reasons.some((r) => r.includes('5 версии'))).toBe(true);
  });

  it('max score (100) когда все факторы совпадают', () => {
    const proj = mkProject({ last_modified: isoDaysAgo(10), version_count: 4 });
    const result = findSimilarPastLaunches([proj], 'pharma_otc');
    expect(result[0]!.score).toBe(100);
  });

  it('ranks by score DESC, ties broken by recency', () => {
    const projects = [
      mkProject({ name: 'old', last_modified: isoDaysAgo(180), version_count: 1 }),
      mkProject({ name: 'fresh-low', last_modified: isoDaysAgo(20), version_count: 1 }),
      mkProject({ name: 'fresh-mature', last_modified: isoDaysAgo(25), version_count: 5 }),
    ];
    const result = findSimilarPastLaunches(projects, 'fmcg');
    expect(result.map((m) => m.project.name)).toEqual(['fresh-mature', 'fresh-low', 'old']);
  });

  it('limits к top-3', () => {
    const projects = Array.from({ length: 7 }, (_, i) =>
      mkProject({ name: `p${i}`, last_modified: isoDaysAgo(10 + i) }),
    );
    const result = findSimilarPastLaunches(projects, 'fmcg');
    expect(result).toHaveLength(3);
  });

  it('reads category from localStorage when not explicit', () => {
    window.localStorage.setItem('aurora.category', 'b2b');
    const proj = mkProject({ last_modified: isoDaysAgo(5), version_count: 3 });
    const result = findSimilarPastLaunches([proj]);
    expect(result).toHaveLength(1);
    expect(result[0]!.reasons.some((r) => r.includes('b2b'))).toBe(true);
  });
});

describe('formatRecency', () => {
  it('returns «сегодня» for < 1 day', () => {
    expect(formatRecency(new Date().toISOString())).toBe('сегодня');
  });

  it('returns N days for < 7', () => {
    expect(formatRecency(isoDaysAgo(3))).toBe('3 дн. назад');
  });

  it('returns weeks for 7-29 days', () => {
    expect(formatRecency(isoDaysAgo(14))).toBe('2 нед. назад');
  });

  it('returns months for 30-364 days', () => {
    expect(formatRecency(isoDaysAgo(90))).toBe('3 мес. назад');
  });

  it('returns years for ≥365 days', () => {
    expect(formatRecency(isoDaysAgo(500))).toBe('1 г. назад');
  });

  it('handles invalid ISO gracefully', () => {
    expect(formatRecency('garbage')).toBe('недавно');
  });
});
