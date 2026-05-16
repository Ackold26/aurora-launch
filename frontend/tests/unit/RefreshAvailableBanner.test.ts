// ROADMAP §3.5 — тесты RefreshAvailableBanner.
//
// Покрытие:
//  1. Не показывает banner при consent.enabled=false
//  2. Не показывает banner при consent=null && forceConsent не задан
//  3. Показывает opt-in dialog при consent=null (первый запуск)
//  4. Показывает banner при triggers.length > 0 + consent.enabled=true
//  5. «Позже» вызывает dismissRefreshTrigger и скрывает баннер
//  6. «Никогда не спрашивать» вызывает setRefreshConsent(false) и скрывает
//  7. «Обновить сейчас» диспатчит aurora:refresh-forecast и скрывает баннер
//
// Мокаем ipc через __setInvokeForTesting. Компонент получает forceConsent /
// forceTriggers через props для детерминизма.

import { describe, expect, it, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/svelte';

import { __setInvokeForTesting, type InvokeFn } from '../../src/lib/ipc/client';
import type { RefreshConsentSetting, RefreshTrigger } from '../../src/lib/ipc/client';

beforeEach(() => cleanup());
afterEach(() => cleanup());

// Stub fadeIn transition (returns no-op spring)
vi.mock('$lib/services/motion', () => ({
  fadeIn: (_node: unknown, _opts?: unknown) => ({ duration: 0 }),
}));

import RefreshAvailableBanner from '../../src/lib/components/RefreshAvailableBanner.svelte';

/** Helper для type-safe мока invoke. */
function mockInvoke(
  handler: (cmd: string, args?: Record<string, unknown>) => Promise<unknown>,
): void {
  __setInvokeForTesting(handler as InvokeFn);
}

/** Flush several microtask ticks to let onMount async chain settle. */
async function flushAsync() {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

const CONSENT_ENABLED: RefreshConsentSetting = {
  enabled: true,
  frequency: 'weekly',
  last_prompted_at: '2026-01-01T00:00:00+00:00',
};

const CONSENT_DISABLED: RefreshConsentSetting = {
  enabled: false,
  frequency: 'weekly',
  last_prompted_at: null,
};

const TRIGGER: RefreshTrigger = {
  project_uuid: 'proj-abc',
  reason: 'new_data',
  detected_at: '2026-05-16T10:00:00+00:00',
  source: 'dsm_xlsx_folder:/data/dsm',
};

describe('RefreshAvailableBanner', () => {
  it('1. does NOT show banner when consent.enabled=false', async () => {
    mockInvoke(async (cmd: string) => {
      if (cmd === 'get_refresh_consent') return CONSENT_DISABLED;
      return null;
    });

    render(RefreshAvailableBanner, {
      forceConsent: CONSENT_DISABLED,
      forceTriggers: [TRIGGER],
    });
    await flushAsync();

    // Banner should not appear because consent is disabled
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('2. does NOT show banner when forceConsent explicitly disabled', async () => {
    render(RefreshAvailableBanner, {
      forceConsent: CONSENT_DISABLED,
    });
    await flushAsync();

    expect(screen.queryByRole('status')).toBeNull();
  });

  it('3. shows opt-in dialog when consent is null (first-run)', async () => {
    mockInvoke(async () => null);

    render(RefreshAvailableBanner, {
      forceConsent: null,
    });
    await flushAsync();

    const banner = screen.getByRole('status');
    expect(banner).toBeDefined();
    // Opt-in buttons should be present
    expect(screen.getByText(/Включить|Enable/i)).toBeDefined();
    expect(screen.getByText(/Нет, спасибо|No thanks/i)).toBeDefined();
  });

  it('4. shows refresh banner when triggers exist + consent enabled', async () => {
    render(RefreshAvailableBanner, {
      forceConsent: CONSENT_ENABLED,
      forceTriggers: [TRIGGER],
    });
    await flushAsync();

    const banner = screen.getByRole('status');
    expect(banner).toBeDefined();
    // Should show "Refresh now" button
    expect(screen.getByText(/Обновить сейчас|Refresh now/i)).toBeDefined();
    // Should show "Later" button
    expect(screen.getByText(/Позже|Later/i)).toBeDefined();
    // Should show "Never ask" button
    expect(screen.getByText(/Никогда не спрашивать|Never ask again/i)).toBeDefined();
  });

  it('5. «Позже» calls dismissRefreshTrigger and hides banner', async () => {
    const dismissCalled: string[] = [];
    mockInvoke(async (cmd: string, args?: Record<string, unknown>) => {
      if (cmd === 'dismiss_refresh_trigger') {
        dismissCalled.push(String(args?.project_uuid ?? ''));
        return { dismissed: true };
      }
      return null;
    });

    render(RefreshAvailableBanner, {
      forceConsent: CONSENT_ENABLED,
      forceTriggers: [TRIGGER],
      projectUuid: 'proj-abc',
    });
    await flushAsync();

    const laterBtn = screen.getByText(/Позже|Later/i);
    await fireEvent.click(laterBtn);
    await flushAsync();

    expect(dismissCalled).toContain('proj-abc');
    // Banner should be gone
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('6. «Никогда» calls setRefreshConsent(false) and hides banner', async () => {
    const consentCalls: Array<{ enabled: boolean }> = [];
    mockInvoke(async (cmd: string, args?: Record<string, unknown>) => {
      if (cmd === 'set_refresh_consent') {
        consentCalls.push({ enabled: Boolean(args?.enabled) });
        return { enabled: false, frequency: 'weekly', last_prompted_at: null };
      }
      return null;
    });

    render(RefreshAvailableBanner, {
      forceConsent: CONSENT_ENABLED,
      forceTriggers: [TRIGGER],
    });
    await flushAsync();

    const neverBtn = screen.getByText(/Никогда не спрашивать|Never ask again/i);
    await fireEvent.click(neverBtn);
    await flushAsync();

    expect(consentCalls.some((c) => c.enabled === false)).toBe(true);
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('7. «Обновить сейчас» dispatches aurora:refresh-forecast event', async () => {
    const receivedEvents: CustomEvent[] = [];
    const handler = (e: Event) => receivedEvents.push(e as CustomEvent);
    window.addEventListener('aurora:refresh-forecast', handler);

    mockInvoke(async (cmd: string) => {
      if (cmd === 'dismiss_refresh_trigger') return { dismissed: true };
      return null;
    });

    render(RefreshAvailableBanner, {
      forceConsent: CONSENT_ENABLED,
      forceTriggers: [TRIGGER],
      projectUuid: 'proj-abc',
    });
    await flushAsync();

    const refreshBtn = screen.getByText(/Обновить сейчас|Refresh now/i);
    await fireEvent.click(refreshBtn);
    await flushAsync();

    window.removeEventListener('aurora:refresh-forecast', handler);

    expect(receivedEvents.length).toBe(1);
    // eslint-disable-next-line @typescript-eslint/no-unsafe-member-access
    expect((receivedEvents[0] as CustomEvent<{ triggers: unknown[] }>).detail.triggers).toHaveLength(1);
    expect(screen.queryByRole('status')).toBeNull();
  });
});


describe('M-06: opt-in prompt rate limiting (localStorage snooze)', () => {
  const SNOOZE_KEY = 'aurora.refresh.opt_in.snooze_until';

  beforeEach(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(SNOOZE_KEY);
    }
    cleanup();
  });

  it('opt-in banner НЕ показывается если snooze_until > now', () => {
    // Set snooze в будущее (через 1 час)
    window.localStorage.setItem(
      SNOOZE_KEY,
      String(Date.now() + 60 * 60 * 1000),
    );

    render(RefreshAvailableBanner, {
      props: { forceConsent: null }, // consent=null = first-run state
    });

    // banner НЕ rendered (silent skip)
    expect(screen.queryByText(/Автоматическое обновление прогнозов/i)).toBeNull();
  });

  it('opt-in banner показывается если snooze_until истёк', () => {
    // Snooze в прошлом
    window.localStorage.setItem(
      SNOOZE_KEY,
      String(Date.now() - 60 * 60 * 1000),
    );

    render(RefreshAvailableBanner, {
      props: { forceConsent: null },
    });

    // Banner показывается (cooldown expired)
    expect(screen.queryByText(/Автоматическое обновление прогнозов/i)).not.toBeNull();
  });

  it('opt-in banner показывается если snooze key отсутствует (first ever)', () => {
    render(RefreshAvailableBanner, {
      props: { forceConsent: null },
    });

    expect(screen.queryByText(/Автоматическое обновление прогнозов/i)).not.toBeNull();
  });

  it('malformed snooze value — fail-open (показывается banner)', () => {
    window.localStorage.setItem(SNOOZE_KEY, 'NaN-or-junk');

    render(RefreshAvailableBanner, {
      props: { forceConsent: null },
    });

    expect(screen.queryByText(/Автоматическое обновление прогнозов/i)).not.toBeNull();
  });
});
