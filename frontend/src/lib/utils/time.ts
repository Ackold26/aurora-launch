// Aurora Launch — time formatting utilities.
//
// formatTimeAgo: deterministic relative-time string using Intl.RelativeTimeFormat.
// Replaces inline timeAgo() functions in ForecastHistory.svelte + SaveIndicator.svelte
// per P-12 i18n infrastructure task.
//
// Locale mapping: 'ru' → 'ru-RU', 'en' → 'en-US'. Accepts both BCP-47 tags.

/** Threshold table (seconds → unit). Order matters: first match wins. */
const THRESHOLDS: Array<{ unit: Intl.RelativeTimeFormatUnit; seconds: number }> = [
  { unit: 'second', seconds: 45 },
  { unit: 'minute', seconds: 45 * 60 },
  { unit: 'hour', seconds: 22 * 3600 },
  { unit: 'day', seconds: 6 * 86400 },
  { unit: 'week', seconds: 4 * 7 * 86400 },
  { unit: 'month', seconds: 11 * 30 * 86400 },
];

/**
 * Returns a short relative-time string for the given ISO timestamp.
 *
 * @param iso    ISO 8601 timestamp string (e.g. "2026-05-15T10:00:00Z")
 * @param locale BCP-47 locale tag. Defaults to 'ru'. Accepts 'ru', 'ru-RU', 'en', 'en-US'.
 * @returns      Localised string ("только что", "2 мин назад", "3 days ago", …)
 *               Returns the raw iso string if it cannot be parsed.
 */
export function formatTimeAgo(iso: string, locale: string = 'ru'): string {
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return iso;

  const elapsedSeconds = (Date.now() - t) / 1000;

  // "just now" bucket — within 45 seconds
  if (elapsedSeconds < 45) {
    // Use locale-appropriate string without Intl (avoids "0 seconds ago" awkwardness)
    const lang = locale.toLowerCase().startsWith('ru') ? 'ru' : 'en';
    return lang === 'ru' ? 'только что' : 'just now';
  }

  // Find the right unit
  let value = elapsedSeconds;
  let unit: Intl.RelativeTimeFormatUnit = 'year';
  for (const threshold of THRESHOLDS) {
    if (Math.abs(elapsedSeconds) < threshold.seconds) {
      unit = threshold.unit;
      const divisors: Record<string, number> = {
        second: 1,
        minute: 60,
        hour: 3600,
        day: 86400,
        week: 7 * 86400,
        month: 30 * 86400,
      };
      value = elapsedSeconds / (divisors[threshold.unit] ?? 1);
      break;
    }
  }
  if (unit === 'year') {
    value = elapsedSeconds / (365 * 86400);
  }

  // Round toward past (negative = past in RelativeTimeFormat)
  const rounded = -Math.round(Math.abs(value));

  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'always', style: 'short' });
  return rtf.format(rounded, unit);
}
