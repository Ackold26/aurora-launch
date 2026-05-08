import { describe, expect, it, beforeEach } from 'vitest';
import { get } from 'svelte/store';

import { themeMode, resolvedTheme, cycleTheme } from '../../src/lib/stores/theme';

describe('theme store', () => {
  beforeEach(() => {
    localStorage.clear();
    themeMode.set('dark');
  });

  it('persists mode to localStorage', () => {
    themeMode.set('light');
    expect(localStorage.getItem('aurora.theme')).toBe('light');
  });

  it('updates document data-theme attribute', () => {
    themeMode.set('high-contrast');
    expect(document.documentElement.dataset.theme).toBe('high-contrast');
  });

  it('cycleTheme advances в order', () => {
    themeMode.set('system');
    cycleTheme();
    expect(get(themeMode)).toBe('dark');
    cycleTheme();
    expect(get(themeMode)).toBe('light');
    cycleTheme();
    expect(get(themeMode)).toBe('high-contrast');
    cycleTheme();
    expect(get(themeMode)).toBe('system');
  });

  it('resolvedTheme matches mode when not system', () => {
    themeMode.set('dark');
    expect(get(resolvedTheme)).toBe('dark');
    themeMode.set('light');
    expect(get(resolvedTheme)).toBe('light');
  });
});
