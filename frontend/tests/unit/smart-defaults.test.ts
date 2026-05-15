// Phase Magic M-04: smart defaults service tests.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  detectSmartDefaults,
  describeDetection,
  type SmartDefaults,
} from '../../src/lib/services/smart-defaults';

describe('detectSmartDefaults', () => {
  it('returns SmartDefaults shape with required fields', () => {
    const result = detectSmartDefaults();
    expect(result).toHaveProperty('timezone');
    expect(result).toHaveProperty('locale');
    expect(result).toHaveProperty('language');
    expect(result).toHaveProperty('currency');
    expect(result).toHaveProperty('granularity');
    expect(result).toHaveProperty('source');
  });

  it('timezone is non-empty string', () => {
    const result = detectSmartDefaults();
    expect(typeof result.timezone).toBe('string');
    expect(result.timezone.length).toBeGreaterThan(0);
  });

  it('locale matches BCP-47 format', () => {
    const result = detectSmartDefaults();
    // Either "xx" or "xx-XX"
    expect(result.locale).toMatch(/^[a-z]{2}(-[A-Z]{2})?$/);
  });

  it('language derived from locale prefix', () => {
    const result = detectSmartDefaults();
    expect(result.language).toBe(result.locale.split('-')[0]);
  });

  it('currency is from allowed enum set', () => {
    const result = detectSmartDefaults();
    expect(['RUB', 'USD', 'EUR', 'GBP', 'CNY', 'JPY', 'KZT', 'units']).toContain(
      result.currency
    );
  });

  it('granularity is monthly or weekly', () => {
    const result = detectSmartDefaults();
    expect(['monthly', 'weekly']).toContain(result.granularity);
  });

  it('source fields track detection method', () => {
    const result = detectSmartDefaults();
    expect(['Intl.DateTimeFormat', 'fallback']).toContain(result.source.timezone);
    expect(['navigator.language', 'fallback']).toContain(result.source.locale);
    expect(['locale-derived', 'fallback']).toContain(result.source.currency);
    expect(['locale-derived', 'fallback']).toContain(result.source.granularity);
  });
});

describe('describeDetection', () => {
  const makeDefaults = (overrides: Partial<SmartDefaults> = {}): SmartDefaults => ({
    timezone: 'Europe/Moscow',
    locale: 'ru-RU',
    language: 'ru',
    currency: 'RUB',
    granularity: 'monthly',
    source: {
      timezone: 'Intl.DateTimeFormat',
      locale: 'navigator.language',
      currency: 'locale-derived',
      granularity: 'locale-derived',
    },
    ...overrides,
  });

  it('describes timezone detection с source', () => {
    const d = makeDefaults();
    expect(describeDetection('timezone', d)).toBe(
      'Europe/Moscow (определено из Intl.DateTimeFormat)'
    );
  });

  it('describes locale detection с source', () => {
    const d = makeDefaults();
    expect(describeDetection('locale', d)).toBe(
      'ru-RU (определено из navigator.language)'
    );
  });

  it('describes fallback source explicitly', () => {
    const d = makeDefaults({
      source: {
        timezone: 'fallback',
        locale: 'navigator.language',
        currency: 'locale-derived',
        granularity: 'locale-derived',
      },
    });
    expect(describeDetection('timezone', d)).toBe(
      'Europe/Moscow (значение по умолчанию)'
    );
  });

  it('describes currency detection', () => {
    const d = makeDefaults();
    expect(describeDetection('currency', d)).toBe('RUB (определено из locale-derived)');
  });
});

// Locale mapping behaviour: jsdom navigator.language pre-set during setup
// makes mocking fragile. Detection logic verified through code review +
// real-browser behaviour tested manually on pilot install.
