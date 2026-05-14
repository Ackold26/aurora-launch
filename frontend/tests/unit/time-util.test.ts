// Vitest tests for frontend/src/lib/utils/time.ts
// P-12 i18n infrastructure — formatTimeAgo helper.

import { describe, expect, it, beforeEach, vi, afterEach } from 'vitest';
import { formatTimeAgo } from '../../src/lib/utils/time';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function nowMinus(seconds: number): string {
  return new Date(Date.now() - seconds * 1000).toISOString();
}

// ---------------------------------------------------------------------------
// Invalid input
// ---------------------------------------------------------------------------

describe('formatTimeAgo — invalid input', () => {
  it('returns raw string if iso is not parseable', () => {
    const raw = 'not-a-date';
    expect(formatTimeAgo(raw)).toBe(raw);
  });
});

// ---------------------------------------------------------------------------
// Russian locale (default)
// ---------------------------------------------------------------------------

describe('formatTimeAgo — ru (default)', () => {
  it('returns "только что" for timestamps within 44 seconds', () => {
    expect(formatTimeAgo(nowMinus(0))).toBe('только что');
    expect(formatTimeAgo(nowMinus(44))).toBe('только что');
  });

  it('returns minute-range string for ~2 minutes ago', () => {
    const result = formatTimeAgo(nowMinus(2 * 60));
    expect(result).toMatch(/2/);
    // Intl may produce "мин." or "мин" depending on locale data version
    expect(result).toMatch(/мин/);
  });

  it('returns hour-range string for ~3 hours ago', () => {
    const result = formatTimeAgo(nowMinus(3 * 3600), 'ru');
    expect(result).toMatch(/3/);
    // Intl produces "ч." or "ч"
    expect(result).toMatch(/ч/);
  });

  it('returns day-range string for ~2 days ago', () => {
    const result = formatTimeAgo(nowMinus(2 * 86400), 'ru');
    expect(result).toMatch(/2/);
    // Intl produces "дн." or "нед." depending on threshold alignment
    expect(result).toMatch(/дн|нед/);
  });

  it('returns week-range string for ~2 weeks ago', () => {
    const result = formatTimeAgo(nowMinus(14 * 86400), 'ru');
    expect(result).toMatch(/2/);
  });
});

// ---------------------------------------------------------------------------
// English locale
// ---------------------------------------------------------------------------

describe('formatTimeAgo — en', () => {
  it('returns "just now" for timestamps within 44 seconds', () => {
    expect(formatTimeAgo(nowMinus(10), 'en')).toBe('just now');
    expect(formatTimeAgo(nowMinus(44), 'en')).toBe('just now');
  });

  it('returns minute-range string for ~2 minutes ago', () => {
    const result = formatTimeAgo(nowMinus(2 * 60), 'en');
    expect(result).toMatch(/2/);
    // Intl short: "min." or "min"
    expect(result).toMatch(/min/i);
  });

  it('returns hour-range string for ~3 hours ago', () => {
    const result = formatTimeAgo(nowMinus(3 * 3600), 'en-US');
    expect(result).toMatch(/3/);
    // Intl short: "hr." or "hr"
    expect(result).toMatch(/hr/i);
  });

  it('returns day-range string for ~2 days ago', () => {
    const result = formatTimeAgo(nowMinus(2 * 86400), 'en');
    expect(result).toMatch(/2/);
    expect(result).toMatch(/day/i);
  });
});

// ---------------------------------------------------------------------------
// BCP-47 tag variants
// ---------------------------------------------------------------------------

describe('formatTimeAgo — locale tag variants', () => {
  it('ru-RU tag works identically to "ru"', () => {
    const ts = nowMinus(2 * 60);
    const a = formatTimeAgo(ts, 'ru');
    const b = formatTimeAgo(ts, 'ru-RU');
    expect(a).toBe(b);
  });

  it('en-US tag works identically to "en"', () => {
    const ts = nowMinus(2 * 60);
    const a = formatTimeAgo(ts, 'en');
    const b = formatTimeAgo(ts, 'en-US');
    expect(a).toBe(b);
  });
});
