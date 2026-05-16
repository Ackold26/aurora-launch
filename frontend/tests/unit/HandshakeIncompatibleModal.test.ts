// Этап 2.8 ROADMAP_POST_V0_1_0 — тесты HandshakeIncompatibleModal.
//
// Покрытие:
//  1. Не показывает modal до прихода handshake event'a (compatible undefined)
//  2. Не показывает modal при compatible=true (handshake OK)
//  3. Показывает modal при compatible=false с reason + advice
//  4. Если advice null — не рендерит advice paragraph
//  5. Reload button присутствует
//  6. ARIA: role=dialog + aria-modal + aria-labelledby
//
// Мокаем @tauri-apps/api/event.listen + переопределяем _invoke через
// __setInvokeForTesting (паттерн setup.ts).

import { describe, expect, it, beforeEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';

import { __setInvokeForTesting, type InvokeFn } from '../../src/lib/ipc/client';

beforeEach(() => cleanup());

// Mock listen из @tauri-apps/api/event — module-scope.
const listenMock = vi.fn((_event: string, _handler: unknown) =>
  Promise.resolve(() => {}),
);
vi.mock('@tauri-apps/api/event', () => ({
  listen: (event: string, handler: unknown) => listenMock(event, handler),
}));

import HandshakeIncompatibleModal from '../../src/lib/components/HandshakeIncompatibleModal.svelte';

/** Helper для type-safe мока invoke (generic InvokeFn). */
function mockInvoke(handler: (cmd: string, args?: Record<string, unknown>) => Promise<unknown>): void {
  __setInvokeForTesting(handler as InvokeFn);
}

/** Helper: ждём пока onMount async-цепочка отработает (2-3 microtasks). */
async function flushAsync() {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

describe('HandshakeIncompatibleModal', () => {
  beforeEach(() => {
    listenMock.mockClear();
    // Каждый тест выставит свой __setInvokeForTesting — reset не нужен.
  });

  it('does NOT render when handshake status is null (not yet completed)', async () => {
    mockInvoke(async (cmd: string) => {
      if (cmd === 'get_handshake_status') return null;
      throw new Error(`unexpected cmd ${cmd}`);
    });

    render(HandshakeIncompatibleModal);
    await flushAsync();

    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('does NOT render when handshake compatible=true', async () => {
    mockInvoke(async (cmd: string) => {
      if (cmd === 'get_handshake_status') {
        return { compatible: true, reason: null, advice: null };
      }
      throw new Error(`unexpected cmd ${cmd}`);
    });

    render(HandshakeIncompatibleModal);
    await flushAsync();

    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('renders modal with reason + advice when compatible=false', async () => {
    mockInvoke(async (cmd: string) => {
      if (cmd === 'get_handshake_status') {
        return {
          compatible: false,
          reason: 'Sidecar version 0.0.5 too old for shell 0.1.0',
          advice: 'Обновите Aurora Launch до v0.1.1',
        };
      }
      throw new Error(`unexpected cmd ${cmd}`);
    });

    render(HandshakeIncompatibleModal);

    const dialog = await screen.findByRole('dialog');
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    expect(dialog.getAttribute('aria-labelledby')).toBe('handshake-modal-title');
    expect(screen.getByText(/Sidecar version 0\.0\.5 too old/)).toBeTruthy();
    expect(screen.getByText('Обновите Aurora Launch до v0.1.1')).toBeTruthy();
  });

  it('renders without advice when advice is null', async () => {
    mockInvoke(async (cmd: string) => {
      if (cmd === 'get_handshake_status') {
        return { compatible: false, reason: 'Generic incompatibility', advice: null };
      }
      throw new Error(`unexpected cmd ${cmd}`);
    });

    render(HandshakeIncompatibleModal);

    expect(await screen.findByText(/Generic incompatibility/)).toBeTruthy();
    const dialog = screen.getByRole('dialog');
    expect(dialog.querySelectorAll('.advice').length).toBe(0);
  });

  it('renders default reason fallback when reason is null', async () => {
    mockInvoke(async (cmd: string) => {
      if (cmd === 'get_handshake_status') {
        return { compatible: false, reason: null, advice: null };
      }
      throw new Error(`unexpected cmd ${cmd}`);
    });

    render(HandshakeIncompatibleModal);

    expect(await screen.findByText(/не подходит к текущему shell/)).toBeTruthy();
  });

  it('shows reload action button', async () => {
    mockInvoke(async (cmd: string) => {
      if (cmd === 'get_handshake_status') {
        return { compatible: false, reason: 'whatever', advice: null };
      }
      throw new Error(`unexpected cmd ${cmd}`);
    });

    render(HandshakeIncompatibleModal);

    const button = await screen.findByRole('button', { name: /Перезапустить/ });
    expect(button).toBeTruthy();
  });

  it('subscribes to sidecar://handshake_complete event', async () => {
    mockInvoke(async () => null);

    render(HandshakeIncompatibleModal);
    await flushAsync();

    expect(listenMock).toHaveBeenCalledWith(
      'sidecar://handshake_complete',
      expect.any(Function),
    );
  });
});
