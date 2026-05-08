// Aurora Launch — i18n setup. ru-RU first-class, en-US best-effort secondary.
//
// Uses svelte-i18n с ICU MessageFormat для plurals (1 неделя / 2 недели /
// 5 недель), numbers (1 234,56 ₽), dates (8 мая 2026 г.).

import { addMessages, init, locale, getLocaleFromNavigator } from 'svelte-i18n';

import ru from './locales/ru.json';
import en from './locales/en.json';

const SUPPORTED = ['ru', 'en'] as const;
export type SupportedLocale = (typeof SUPPORTED)[number];
const STORAGE_KEY = 'aurora.locale';

addMessages('ru', ru);
addMessages('en', en);

function pickInitialLocale(): SupportedLocale {
  if (typeof localStorage !== 'undefined') {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && SUPPORTED.includes(stored as SupportedLocale)) {
      return stored as SupportedLocale;
    }
  }
  const nav = getLocaleFromNavigator();
  if (nav?.toLowerCase().startsWith('ru')) return 'ru';
  if (nav?.toLowerCase().startsWith('en')) return 'en';
  return 'ru'; // Aurora primary market
}

export function initI18n(): void {
  init({
    fallbackLocale: 'ru',
    initialLocale: pickInitialLocale()
  });
}

export function setLocale(loc: SupportedLocale): void {
  locale.set(loc);
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(STORAGE_KEY, loc);
  }
}

export const SUPPORTED_LOCALES: readonly SupportedLocale[] = SUPPORTED;
