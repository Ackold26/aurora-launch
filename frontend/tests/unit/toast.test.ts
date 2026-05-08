import { describe, expect, it, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';

import { toasts, pushToast, dismissToast } from '../../src/lib/stores/toast';

describe('toast store', () => {
  beforeEach(() => {
    toasts.set([]);
    vi.useFakeTimers();
  });

  it('pushToast adds toast', () => {
    pushToast({ level: 'info', title: 'Hello' });
    expect(get(toasts)).toHaveLength(1);
    expect(get(toasts)[0].title).toBe('Hello');
  });

  it('auto-dismisses after ttlMs', () => {
    pushToast({ level: 'info', title: 'Goes', ttlMs: 1000 });
    expect(get(toasts)).toHaveLength(1);
    vi.advanceTimersByTime(1500);
    expect(get(toasts)).toHaveLength(0);
  });

  it('manual dismissToast removes by id', () => {
    const id = pushToast({ level: 'info', title: 'A', ttlMs: 0 });
    expect(get(toasts)).toHaveLength(1);
    dismissToast(id);
    expect(get(toasts)).toHaveLength(0);
  });

  it('does not auto-dismiss when ttlMs=0', () => {
    pushToast({ level: 'info', title: 'Sticky', ttlMs: 0 });
    vi.advanceTimersByTime(60_000);
    expect(get(toasts)).toHaveLength(1);
  });
});
