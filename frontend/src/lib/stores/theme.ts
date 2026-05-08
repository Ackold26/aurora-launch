// Theme store — dark / light / high-contrast.
//
// Persistence: localStorage `aurora.theme`. Default = system preference.
// Switch budget: ≤150ms (PERFORMANCE_BUDGETS §1.3 Theme switch).

import { writable, get } from 'svelte/store';

export type ThemeMode = 'system' | 'dark' | 'light' | 'high-contrast';
export type ResolvedTheme = 'dark' | 'light' | 'high-contrast';

const STORAGE_KEY = 'aurora.theme';

function readStored(): ThemeMode {
  if (typeof localStorage === 'undefined') return 'system';
  const v = localStorage.getItem(STORAGE_KEY);
  if (v === 'dark' || v === 'light' || v === 'high-contrast' || v === 'system') {
    return v;
  }
  return 'system';
}

function resolveSystem(): ResolvedTheme {
  if (typeof window === 'undefined') return 'dark';
  if (window.matchMedia?.('(prefers-color-scheme: light)').matches) return 'light';
  return 'dark';
}

export const themeMode = writable<ThemeMode>(readStored());

export const resolvedTheme = writable<ResolvedTheme>(
  readStored() === 'system' ? resolveSystem() : (readStored() as ResolvedTheme)
);

themeMode.subscribe((mode) => {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(STORAGE_KEY, mode);
  }
  const resolved: ResolvedTheme = mode === 'system' ? resolveSystem() : mode;
  resolvedTheme.set(resolved);
  if (typeof document !== 'undefined') {
    document.documentElement.dataset.theme = resolved;
  }
});

if (typeof window !== 'undefined' && window.matchMedia) {
  window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', () => {
    if (get(themeMode) === 'system') {
      const resolved = resolveSystem();
      resolvedTheme.set(resolved);
      document.documentElement.dataset.theme = resolved;
    }
  });
}

export function cycleTheme(): void {
  const mode = get(themeMode);
  const order: ThemeMode[] = ['system', 'dark', 'light', 'high-contrast'];
  const idx = order.indexOf(mode);
  themeMode.set(order[(idx + 1) % order.length]);
}
