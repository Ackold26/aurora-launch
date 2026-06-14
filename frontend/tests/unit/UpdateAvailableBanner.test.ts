// Этап 2.9 ROADMAP_POST_V0_1_0 — тесты UpdateAvailableBanner.
//
// Покрытие:
//  1. Не показывается когда update отсутствует (forceUpdate=null)
//  2. Показывает banner с версией когда update available (forceUpdate={...})
//  3. Показывает release notes если body присутствует
//  4. Не показывает release notes если body отсутствует
//  5. Кнопка «Позже» скрывает banner (dismiss)
//  6. ARIA: role=status + aria-live=polite
//  7. Кнопка «Скачать и установить» присутствует в available-state
//  8. invoke('check_update') НЕ вызывается когда forceUpdate prop передан
//
// Fleet-unify migration (2026-06-14): компонент перешёл с
// @tauri-apps/plugin-updater (minisign) на IPC-команды checksum-updater'а.
// Мокаем @tauri-apps/api/core (invoke) + @tauri-apps/api/event (listen).
// Тесты с update используют forceUpdate prop → обходят invoke('check_update').

import { describe, expect, it, beforeEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/svelte';

// vi.hoisted: factory ниже исполняется до объявлений → переменные-моки нужно
// поднять, иначе TDZ ("Cannot access before initialization").
const { invokeMock, listenMock } = vi.hoisted(() => ({
  invokeMock: vi.fn(),
  listenMock: vi.fn(),
}));

vi.mock('@tauri-apps/api/core', () => ({ invoke: invokeMock }));
vi.mock('@tauri-apps/api/event', () => ({ listen: listenMock }));

beforeEach(() => {
  cleanup();
  invokeMock.mockReset();
  invokeMock.mockImplementation(async (cmd: string) => {
    if (cmd === 'check_update') return null; // по умолчанию апдейта нет
    if (cmd === 'download_update') return 'C:/tmp/aurora-update.exe';
    return undefined;
  });
  listenMock.mockReset();
  listenMock.mockImplementation(async () => () => {}); // listen → unlisten fn
});

import UpdateAvailableBanner from '../../src/lib/components/UpdateAvailableBanner.svelte';

/** Flush microtasks (onMount async chain). */
async function flushAsync() {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

describe('UpdateAvailableBanner', () => {
  it('does NOT render when forceUpdate is null (no update)', async () => {
    render(UpdateAvailableBanner, { props: { forceUpdate: null } });
    await flushAsync();

    // Banner should not be in DOM at all
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('renders banner when update is available via forceUpdate', async () => {
    render(UpdateAvailableBanner, {
      props: { forceUpdate: { version: '0.2.0', body: null } },
    });
    await flushAsync();

    const banner = screen.getByRole('status');
    expect(banner).toBeTruthy();
    expect(banner.textContent).toContain('0.2.0');
  });

  it('shows release notes when body is provided', async () => {
    render(UpdateAvailableBanner, {
      props: {
        forceUpdate: {
          version: '0.2.0',
          body: 'Улучшения прогноза + исправления',
        },
      },
    });
    await flushAsync();

    expect(screen.getByText(/Улучшения прогноза/)).toBeTruthy();
  });

  it('does NOT render release notes section when body is null', async () => {
    render(UpdateAvailableBanner, {
      props: { forceUpdate: { version: '0.2.0', body: null } },
    });
    await flushAsync();

    // .update-banner__notes should not be in DOM
    const banner = screen.getByRole('status');
    expect(banner.querySelector('.update-banner__notes')).toBeNull();
  });

  it('hides banner when "Later" button is clicked (dismiss)', async () => {
    render(UpdateAvailableBanner, {
      props: { forceUpdate: { version: '0.2.0', body: null } },
    });
    await flushAsync();

    // Banner visible
    expect(screen.getByRole('status')).toBeTruthy();

    const laterBtn = screen.getByText('Позже');
    fireEvent.click(laterBtn);
    await flushAsync();

    // Banner gone
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('banner has role=status and aria-live=polite', async () => {
    render(UpdateAvailableBanner, {
      props: { forceUpdate: { version: '0.2.0', body: null } },
    });
    await flushAsync();

    const banner = screen.getByRole('status');
    expect(banner.getAttribute('aria-live')).toBe('polite');
  });

  it('shows "Скачать и установить" action button when update available', async () => {
    render(UpdateAvailableBanner, {
      props: { forceUpdate: { version: '0.2.0', body: null } },
    });
    await flushAsync();

    const installBtn = screen.getByText('Скачать и установить');
    expect(installBtn).toBeTruthy();
  });

  it('does NOT call invoke(check_update) when forceUpdate prop is provided', async () => {
    render(UpdateAvailableBanner, {
      props: { forceUpdate: { version: '0.1.5', body: null } },
    });
    await flushAsync();

    // forceUpdate bypasses the real check — invoke('check_update') must not fire.
    const calledCommands = invokeMock.mock.calls.map((call) => call[0]);
    expect(calledCommands).not.toContain('check_update');
  });
});
