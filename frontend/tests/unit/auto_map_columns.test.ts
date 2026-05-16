// Vitest tests for auto_map_columns utility (BTA-6).

import { describe, expect, it } from 'vitest';
import {
  autoMapColumns,
  groupedCanonicalFields,
  CANONICAL_FIELDS,
} from '../../src/lib/utils/auto_map_columns';

describe('autoMapColumns', () => {
  it('exact RUS match: «Бренд» → brand_name', () => {
    const result = autoMapColumns(['Бренд']);
    expect(result.get('Бренд')).toBe('brand_name');
  });

  it('exact ENG match: «Brand» → brand_name', () => {
    const result = autoMapColumns(['Brand']);
    expect(result.get('Brand')).toBe('brand_name');
  });

  it('case insensitive: «БРЕНД» → brand_name', () => {
    const result = autoMapColumns(['БРЕНД']);
    expect(result.get('БРЕНД')).toBe('brand_name');
  });

  it('normalised whitespace: « Бренд » → brand_name', () => {
    const result = autoMapColumns([' Бренд ']);
    expect(result.get(' Бренд ')).toBe('brand_name');
  });

  it('sidecar suggested имеет приоритет над heuristic', () => {
    // 'Бренд' normalises to brand_name via synonym table,
    // but sidecar suggests period_date — sidecar wins.
    const result = autoMapColumns(['Бренд'], { 'Бренд': 'period_date' });
    expect(result.get('Бренд')).toBe('period_date');
  });

  it('unknown column → null', () => {
    const result = autoMapColumns(['Неизвестная_колонка_xyz']);
    expect(result.get('Неизвестная_колонка_xyz')).toBeNull();
  });

  it('multi-word: «доля рынка» → market_share_pct', () => {
    const result = autoMapColumns(['доля рынка']);
    expect(result.get('доля рынка')).toBe('market_share_pct');
  });

  it('legacy typo: «Channek» → channel_name', () => {
    const result = autoMapColumns(['Channek']);
    expect(result.get('Channek')).toBe('channel_name');
  });

  it('preserves source case in Map keys', () => {
    // Key in result must be the original string, not normalised.
    const result = autoMapColumns(['Бренд']);
    expect(result.has('Бренд')).toBe(true);
    expect(result.has('бренд')).toBe(false);
  });

  it('«Дата» → period_date', () => {
    const result = autoMapColumns(['Дата']);
    expect(result.get('Дата')).toBe('period_date');
  });

  it('«spend» → spend_thousand_rub', () => {
    const result = autoMapColumns(['spend']);
    expect(result.get('spend')).toBe('spend_thousand_rub');
  });

  it('«АТХ» → atc_code', () => {
    const result = autoMapColumns(['АТХ']);
    expect(result.get('АТХ')).toBe('atc_code');
  });

  it('multiple columns — all mapped in one call', () => {
    const result = autoMapColumns(['Бренд', 'Дата', 'Неизвестно']);
    expect(result.get('Бренд')).toBe('brand_name');
    expect(result.get('Дата')).toBe('period_date');
    expect(result.get('Неизвестно')).toBeNull();
    expect(result.size).toBe(3);
  });

  it('empty sourceColumns → empty Map', () => {
    const result = autoMapColumns([]);
    expect(result.size).toBe(0);
  });
});

describe('groupedCanonicalFields', () => {
  it('returns exactly 5 groups', () => {
    const groups = groupedCanonicalFields();
    expect(Object.keys(groups)).toHaveLength(5);
    expect(Object.keys(groups)).toEqual(
      expect.arrayContaining(['identity', 'period', 'sales', 'media', 'category']),
    );
  });

  it('identity group contains brand_name', () => {
    const groups = groupedCanonicalFields();
    const ids = (groups['identity'] ?? []).map((f) => f.id);
    expect(ids).toContain('brand_name');
  });

  it('period group contains period_date', () => {
    const groups = groupedCanonicalFields();
    const ids = (groups['period'] ?? []).map((f) => f.id);
    expect(ids).toContain('period_date');
  });

  it('category group contains atc_code', () => {
    const groups = groupedCanonicalFields();
    const ids = (groups['category'] ?? []).map((f) => f.id);
    expect(ids).toContain('atc_code');
  });
});

describe('CANONICAL_FIELDS', () => {
  it('contains brand_name', () => {
    const ids = CANONICAL_FIELDS.map((f) => f.id);
    expect(ids).toContain('brand_name');
  });

  it('contains period_date', () => {
    const ids = CANONICAL_FIELDS.map((f) => f.id);
    expect(ids).toContain('period_date');
  });

  it('contains atc_code', () => {
    const ids = CANONICAL_FIELDS.map((f) => f.id);
    expect(ids).toContain('atc_code');
  });

  it('every field has non-empty id, label_ru and valid group', () => {
    const validGroups = new Set(['identity', 'period', 'sales', 'media', 'category']);
    for (const f of CANONICAL_FIELDS) {
      expect(f.id.length).toBeGreaterThan(0);
      expect(f.label_ru.length).toBeGreaterThan(0);
      expect(validGroups.has(f.group)).toBe(true);
    }
  });
});
