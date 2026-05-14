// Vitest tests for SaveIndicator.svelte (Phase Premium P-08).

import { describe, expect, it, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import SaveIndicator from '../../src/lib/components/SaveIndicator.svelte';

beforeEach(() => cleanup());

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function nowMinus(seconds: number): string {
  return new Date(Date.now() - seconds * 1000).toISOString();
}

function renderIndicator(props: {
  state: 'saved' | 'saving' | 'unsaved';
  lastSavedAt?: string | null;
  mode?: 'auto' | 'manual';
}) {
  return render(SaveIndicator, {
    state: props.state,
    lastSavedAt: props.lastSavedAt ?? null,
    mode: props.mode,
  });
}

// ---------------------------------------------------------------------------
// State labels
// ---------------------------------------------------------------------------

describe('SaveIndicator — state labels', () => {
  it('state=unsaved renders "Не сохранено"', () => {
    renderIndicator({ state: 'unsaved' });
    expect(screen.getByText('Не сохранено')).toBeTruthy();
  });

  it('state=saving renders "Сохраняется…"', () => {
    renderIndicator({ state: 'saving' });
    expect(screen.getByText('Сохраняется…')).toBeTruthy();
  });

  it('state=saved with null lastSavedAt renders auto label without time', () => {
    renderIndicator({ state: 'saved', lastSavedAt: null });
    expect(screen.getByText('Сохранено автоматически')).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// Time-ago formatting
// ---------------------------------------------------------------------------

describe('SaveIndicator — time-ago', () => {
  it('just-now (<60s) shows "только что"', () => {
    renderIndicator({ state: 'saved', lastSavedAt: nowMinus(30) });
    expect(screen.getByText(/только что/)).toBeTruthy();
  });

  it('2 minutes ago shows a minutes-range string', () => {
    renderIndicator({ state: 'saved', lastSavedAt: nowMinus(120) });
    // Intl.RelativeTimeFormat may produce "2 мин. назад" or "2 мин назад" depending on runtime
    expect(screen.getByText(/2.мин/)).toBeTruthy();
  });

  it('3 hours ago shows an hours-range string', () => {
    renderIndicator({ state: 'saved', lastSavedAt: nowMinus(3 * 3600) });
    expect(screen.getByText(/3.ч/)).toBeTruthy();
  });

  it('2 days ago shows a days-range string', () => {
    renderIndicator({ state: 'saved', lastSavedAt: nowMinus(2 * 86400) });
    expect(screen.getByText(/2.дн/)).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// mode prop — auto vs manual
// ---------------------------------------------------------------------------

describe('SaveIndicator — mode', () => {
  it('mode=auto (default) shows "Сохранено автоматически"', () => {
    renderIndicator({ state: 'saved', lastSavedAt: nowMinus(30) });
    expect(screen.getByText(/Сохранено автоматически/)).toBeTruthy();
  });

  it('mode=manual shows "Сохранено вручную"', () => {
    renderIndicator({ state: 'saved', lastSavedAt: nowMinus(30), mode: 'manual' });
    expect(screen.getByText(/Сохранено вручную/)).toBeTruthy();
  });

  it('mode=manual does NOT show "автоматически"', () => {
    renderIndicator({ state: 'saved', lastSavedAt: nowMinus(30), mode: 'manual' });
    expect(screen.queryByText(/автоматически/)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// ARIA
// ---------------------------------------------------------------------------

describe('SaveIndicator — ARIA', () => {
  it('aria-live="polite" attribute present', () => {
    renderIndicator({ state: 'unsaved' });
    const el = document.querySelector('[aria-live="polite"]');
    expect(el).not.toBeNull();
  });

  it('aria-label matches visible text for saved state', () => {
    renderIndicator({ state: 'saved', lastSavedAt: null });
    const el = document.querySelector('[aria-label]');
    expect(el?.getAttribute('aria-label')).toContain('Сохранено автоматически');
  });
});

// ---------------------------------------------------------------------------
// prefers-reduced-motion
// ---------------------------------------------------------------------------

describe('SaveIndicator — prefers-reduced-motion', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('data-state=saving is rendered regardless of motion preference', () => {
    // Mock matchMedia to indicate reduced motion
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query === '(prefers-reduced-motion: reduce)',
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });

    renderIndicator({ state: 'saving' });

    // Component renders saving state correctly even under reduced motion
    expect(screen.getByText('Сохраняется…')).toBeTruthy();

    // The dot element with data-state=saving exists — CSS handles animation suppression
    const indicator = document.querySelector('[data-state="saving"]');
    expect(indicator).not.toBeNull();
  });
});
