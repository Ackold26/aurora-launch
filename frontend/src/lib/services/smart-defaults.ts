/**
 * Phase Magic M-04: smart defaults service.
 *
 * Auto-detects user-environment hints to pre-fill anchor form defaults.
 * Goal: reduce friction в first wizard step from blank fields → "Aurora
 * already знает мой регион, валюту, локаль."
 *
 * Audit ROI 6×: small effort, high first-impression payoff.
 *
 * Per INV-25 dual-mode: detection results are SUGGESTIONS — Manager mode
 * shows pre-filled values, Expert mode shows detection chain ("определено
 * из navigator.language").
 *
 * Sources:
 *   - Intl.DateTimeFormat().resolvedOptions().timeZone  (e.g. "Europe/Moscow")
 *   - navigator.language                                  (e.g. "ru-RU")
 *   - currency: derived from locale via Intl.NumberFormat probe
 *   - calendar style: weekly vs monthly hint based on browser locale
 */

export interface SmartDefaults {
  /** IANA timezone identifier, e.g. "Europe/Moscow" */
  timezone: string;
  /** BCP-47 locale tag, e.g. "ru-RU" */
  locale: string;
  /** Language code derived from locale, e.g. "ru" */
  language: string;
  /** Default currency ISO 4217 code, e.g. "RUB" — derived от locale */
  currency: 'RUB' | 'USD' | 'EUR' | 'GBP' | 'CNY' | 'JPY' | 'KZT' | 'units';
  /** Calendar granularity hint based on locale region */
  granularity: 'monthly' | 'weekly';
  /** Detection source (для Expert mode transparency) */
  source: {
    timezone: 'Intl.DateTimeFormat' | 'fallback';
    locale: 'navigator.language' | 'fallback';
    currency: 'locale-derived' | 'fallback';
    granularity: 'locale-derived' | 'fallback';
  };
}

const _LOCALE_TO_CURRENCY: Record<string, SmartDefaults['currency']> = {
  ru: 'RUB',
  'ru-RU': 'RUB',
  'ru-BY': 'RUB',
  uk: 'RUB', // Conservative — Ukrainian customer may use UAH but RUB safe baseline
  en: 'USD',
  'en-US': 'USD',
  'en-GB': 'GBP',
  'en-CA': 'USD',
  de: 'EUR',
  'de-DE': 'EUR',
  fr: 'EUR',
  'fr-FR': 'EUR',
  es: 'EUR',
  'es-ES': 'EUR',
  it: 'EUR',
  'it-IT': 'EUR',
  zh: 'CNY',
  'zh-CN': 'CNY',
  ja: 'JPY',
  'ja-JP': 'JPY',
  kk: 'KZT',
  'kk-KZ': 'KZT',
};

const _LOCALE_TO_GRANULARITY: Record<string, SmartDefaults['granularity']> = {
  // Russia + CIS: monthly common in pharma/FMCG
  ru: 'monthly',
  'ru-RU': 'monthly',
  kk: 'monthly',
  // US/UK FMCG: weekly tracking common (e.g., Nielsen weekly panel)
  en: 'weekly',
  'en-US': 'weekly',
  'en-GB': 'weekly',
  // Other markets: monthly default
  de: 'monthly',
  fr: 'monthly',
  zh: 'monthly',
  ja: 'monthly',
};

export function detectSmartDefaults(): SmartDefaults {
  const source: SmartDefaults['source'] = {
    timezone: 'fallback',
    locale: 'fallback',
    currency: 'fallback',
    granularity: 'fallback',
  };

  // Timezone via Intl.DateTimeFormat — supported in all evergreen browsers
  let timezone = 'Europe/Moscow';
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (tz && tz.length > 0) {
      timezone = tz;
      source.timezone = 'Intl.DateTimeFormat';
    }
  } catch (e) {
    // Audit M-4 (этап 1.7): не silent — log fallback в DevTools.
    // jsdom может не имплементировать Intl → Moscow fallback as Aurora primary market.
    console.warn('[smart-defaults] Intl.DateTimeFormat unavailable, defaulting к Europe/Moscow:', e);
  }

  // Locale via navigator.language
  let locale = 'ru-RU';
  try {
    const navLang = typeof navigator !== 'undefined' ? navigator.language : '';
    if (navLang && navLang.length > 0) {
      locale = navLang;
      source.locale = 'navigator.language';
    }
  } catch (e) {
    // Audit M-4 (этап 1.7): не silent.
    console.warn('[smart-defaults] navigator.language unavailable, defaulting к ru-RU:', e);
  }

  const language = locale.split('-')[0] ?? 'ru';

  // Currency: prefer exact locale match, then language-only, then fallback
  let currency: SmartDefaults['currency'] = 'RUB';
  if (locale in _LOCALE_TO_CURRENCY) {
    currency = _LOCALE_TO_CURRENCY[locale]!;
    source.currency = 'locale-derived';
  } else if (language in _LOCALE_TO_CURRENCY) {
    currency = _LOCALE_TO_CURRENCY[language]!;
    source.currency = 'locale-derived';
  }

  // Granularity hint
  let granularity: SmartDefaults['granularity'] = 'monthly';
  if (locale in _LOCALE_TO_GRANULARITY) {
    granularity = _LOCALE_TO_GRANULARITY[locale]!;
    source.granularity = 'locale-derived';
  } else if (language in _LOCALE_TO_GRANULARITY) {
    granularity = _LOCALE_TO_GRANULARITY[language]!;
    source.granularity = 'locale-derived';
  }

  return {
    timezone,
    locale,
    language,
    currency,
    granularity,
    source,
  };
}

/**
 * Format a smart default value for display in Expert mode disclosure.
 * Example: "Europe/Moscow (определено из Intl.DateTimeFormat)"
 */
export function describeDetection(
  field: keyof SmartDefaults['source'],
  defaults: SmartDefaults
): string {
  const value =
    field === 'timezone'
      ? defaults.timezone
      : field === 'locale'
      ? defaults.locale
      : field === 'currency'
      ? defaults.currency
      : defaults.granularity;
  const src = defaults.source[field];
  if (src === 'fallback') {
    return `${value} (значение по умолчанию)`;
  }
  return `${value} (определено из ${src})`;
}
