// Vitest tests for AuditTab.svelte — Sprint 3 D6 reproducibility verification UI.
//
// Protects invariants:
//   INV-48 — test-first attack scenario coverage for reproducibility verification.
//   Sprint 3 D6 — verify_reproducibility IPC integration: phase state machine,
//                 badge tone, mismatch list, error handling, ARIA live region.
//
// IPC is mocked via setup.ts's __auroraIpcMock global (wraps __setInvokeForTesting).
// Pattern mirrors UpdateAvailableBanner.test.ts.

import { describe, expect, it, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';
import type { ReproducibilityResult } from '../../src/lib/ipc/client';

import AuditTab from '../../src/lib/components/inspector/AuditTab.svelte';

beforeEach(() => cleanup());

/** Flush microtasks — for IPC await + $derived state updates. */
async function flushAsync() {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

// ---------------------------------------------------------------------------
// IPC mock helpers
// ---------------------------------------------------------------------------

function getIpcMock() {
  return (globalThis as unknown as { __auroraIpcMock: ReturnType<typeof vi.fn> })
    .__auroraIpcMock;
}

function mockSuccess(overrides: Partial<ReproducibilityResult> = {}) {
  const result: ReproducibilityResult = {
    status: 'verified',
    files_checked: 5,
    mismatches: [],
    reason: null,
    composite_hash: null,
    ...overrides,
  };
  getIpcMock().mockImplementation(async (cmd: string) => {
    if (cmd === 'verify_reproducibility') return result;
    throw new Error(`Unmocked: ${cmd}`);
  });
  return result;
}

function mockError(message = 'SHA-256 mismatch detected') {
  getIpcMock().mockImplementation(async (cmd: string) => {
    if (cmd === 'verify_reproducibility') throw new Error(message);
    throw new Error(`Unmocked: ${cmd}`);
  });
}

// ---------------------------------------------------------------------------
// Initial state
// ---------------------------------------------------------------------------

describe('AuditTab — начальное состояние (idle)', () => {
  it('рендерит кнопку "Проверить воспроизводимость" в начальном состоянии', () => {
    render(AuditTab, { bundlePath: '/path/to/bundle.aurora' });
    expect(screen.getByText(/Проверить воспроизводимость/)).toBeTruthy();
  });

  it('НЕ отображает .audit-result в начальном состоянии', () => {
    const { container } = render(AuditTab, { bundlePath: '/path/to/bundle.aurora' });
    expect(container.querySelector('.audit-result')).toBeNull();
  });

  it('НЕ отображает .audit-error в начальном состоянии', () => {
    const { container } = render(AuditTab, { bundlePath: '/path/to/bundle.aurora' });
    expect(container.querySelector('.audit-error')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Button enabled/disabled state
// ---------------------------------------------------------------------------

describe('AuditTab — состояние кнопки', () => {
  it('кнопка активна когда bundlePath непустой', () => {
    render(AuditTab, { bundlePath: '/valid/path.aurora' });
    const btn = screen.getByText(/Проверить воспроизводимость/).closest('button');
    expect(btn).not.toBeNull();
    expect((btn as HTMLButtonElement).disabled).toBe(false);
  });

  it('кнопка заблокирована (disabled) когда bundlePath пустой', () => {
    render(AuditTab, { bundlePath: '' });
    const btn = screen
      .getByText(/Проверить воспроизводимость/)
      .closest('button') as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Running phase
// ---------------------------------------------------------------------------

describe('AuditTab — фаза running', () => {
  it('клик на кнопку переводит в running — показывает "Проверяется…"', async () => {
    // Use a promise that never resolves so we can catch the running state
    let resolveIpc!: (v: ReproducibilityResult) => void;
    getIpcMock().mockImplementation(
      async (cmd: string) =>
        new Promise<ReproducibilityResult>((resolve) => {
          if (cmd === 'verify_reproducibility') resolveIpc = resolve;
          else throw new Error(`Unmocked: ${cmd}`);
        }),
    );

    render(AuditTab, { bundlePath: '/path/to/bundle.aurora' });
    const btn = screen.getByText(/Проверить воспроизводимость/).closest('button')!;
    await fireEvent.click(btn);
    await flushAsync();

    expect(screen.getByText(/Проверяется…/)).toBeTruthy();

    // Cleanup — resolve the promise so the component can settle
    resolveIpc({ status: 'verified', files_checked: 0, mismatches: [], reason: null, composite_hash: null });
    await flushAsync();
  });

  it('кнопка disabled во время running', async () => {
    let resolveIpc!: (v: ReproducibilityResult) => void;
    getIpcMock().mockImplementation(
      async (cmd: string) =>
        new Promise<ReproducibilityResult>((resolve) => {
          if (cmd === 'verify_reproducibility') resolveIpc = resolve;
          else throw new Error(`Unmocked: ${cmd}`);
        }),
    );

    render(AuditTab, { bundlePath: '/path/to/bundle.aurora' });
    const btn = screen.getByText(/Проверить воспроизводимость/).closest('button') as HTMLButtonElement;
    await fireEvent.click(btn);
    await flushAsync();

    // During running the button text changes; find by "Проверяется…"
    const runningBtn = screen.getByText(/Проверяется…/).closest('button') as HTMLButtonElement;
    expect(runningBtn.disabled).toBe(true);

    resolveIpc({ status: 'verified', files_checked: 0, mismatches: [], reason: null, composite_hash: null });
    await flushAsync();
  });

  it('вызывает IPC с командой verify_reproducibility и аргументом bundlePath', async () => {
    mockSuccess();
    const ipcMock = getIpcMock();

    render(AuditTab, { bundlePath: '/path/to/bundle.aurora' });
    await fireEvent.click(screen.getByText(/Проверить воспроизводимость/).closest('button')!);
    await flushAsync();

    expect(ipcMock).toHaveBeenCalledWith(
      'verify_reproducibility',
      { bundlePath: '/path/to/bundle.aurora' },
    );
  });
});

// ---------------------------------------------------------------------------
// Success state — status: 'verified'
// ---------------------------------------------------------------------------

describe('AuditTab — успешная верификация (verified)', () => {
  it('после успеха отображает .audit-result', async () => {
    mockSuccess();
    const { container } = render(AuditTab, { bundlePath: '/path/to/bundle.aurora' });
    await fireEvent.click(screen.getByText(/Проверить воспроизводимость/).closest('button')!);
    await flushAsync();

    expect(container.querySelector('.audit-result')).not.toBeNull();
  });

  it('badge имеет data-tone="success" для status=verified', async () => {
    mockSuccess();
    const { container } = render(AuditTab, { bundlePath: '/path/to/bundle.aurora' });
    await fireEvent.click(screen.getByText(/Проверить воспроизводимость/).closest('button')!);
    await flushAsync();

    const badge = container.querySelector('.audit-result-badge');
    expect(badge).not.toBeNull();
    expect(badge!.getAttribute('data-tone')).toBe('success');
  });

  it('badge text = "Воспроизводимо" для status=verified', async () => {
    mockSuccess();
    const { container } = render(AuditTab, { bundlePath: '/path/to/bundle.aurora' });
    await fireEvent.click(screen.getByText(/Проверить воспроизводимость/).closest('button')!);
    await flushAsync();

    // Use container query to target the badge specifically — the description paragraph
    // also contains the word «Воспроизводимо», so screen.getByText would find multiple elements.
    const badge = container.querySelector('.audit-result-badge');
    expect(badge).not.toBeNull();
    expect(badge!.textContent).toContain('Воспроизводимо');
  });

  it('отображает количество проверенных файлов (files_checked)', async () => {
    mockSuccess({ files_checked: 7 });
    const { container } = render(AuditTab, { bundlePath: '/path/to/bundle.aurora' });
    await fireEvent.click(screen.getByText(/Проверить воспроизводимость/).closest('button')!);
    await flushAsync();

    expect(container.querySelector('.audit-result-summary')!.textContent).toContain('7');
  });

  it('НЕ рендерит .audit-mismatch-details когда mismatches пустой', async () => {
    mockSuccess({ mismatches: [] });
    const { container } = render(AuditTab, { bundlePath: '/path/to/bundle.aurora' });
    await fireEvent.click(screen.getByText(/Проверить воспроизводимость/).closest('button')!);
    await flushAsync();

    expect(container.querySelector('.audit-mismatch-details')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Diverged state
// ---------------------------------------------------------------------------

describe('AuditTab — расхождение хешей (diverged)', () => {
  it('badge имеет data-tone="danger" для status=diverged', async () => {
    mockSuccess({
      status: 'diverged',
      mismatches: [
        { entry: 'model/weights.npz', expected_sha256: 'aaa', computed_sha256: 'bbb' },
      ],
    });

    const { container } = render(AuditTab, { bundlePath: '/path/to/bundle.aurora' });
    await fireEvent.click(screen.getByText(/Проверить воспроизводимость/).closest('button')!);
    await flushAsync();

    const badge = container.querySelector('.audit-result-badge');
    expect(badge!.getAttribute('data-tone')).toBe('danger');
  });

  it('badge text = "Расхождение" для status=diverged', async () => {
    mockSuccess({ status: 'diverged', mismatches: [] });
    render(AuditTab, { bundlePath: '/path/to/bundle.aurora' });
    await fireEvent.click(screen.getByText(/Проверить воспроизводимость/).closest('button')!);
    await flushAsync();

    expect(screen.getByText(/Расхождение/)).toBeTruthy();
  });

  it('рендерит .audit-mismatch-details когда mismatches.length > 0', async () => {
    mockSuccess({
      status: 'diverged',
      files_checked: 3,
      mismatches: [
        { entry: 'model/weights.npz', expected_sha256: 'abc123', computed_sha256: 'def456' },
      ],
    });

    const { container } = render(AuditTab, { bundlePath: '/path/to/bundle.aurora' });
    await fireEvent.click(screen.getByText(/Проверить воспроизводимость/).closest('button')!);
    await flushAsync();

    expect(container.querySelector('.audit-mismatch-details')).not.toBeNull();
  });

  it('рендерит entry и оба хеша для каждого mismatch', async () => {
    const mismatch = {
      entry: 'model/weights.npz',
      expected_sha256: 'abc123deadbeef',
      computed_sha256: 'def456cafebabe',
    };
    mockSuccess({ status: 'diverged', mismatches: [mismatch] });

    const { container } = render(AuditTab, { bundlePath: '/path/to/bundle.aurora' });
    await fireEvent.click(screen.getByText(/Проверить воспроизводимость/).closest('button')!);
    await flushAsync();

    const details = container.querySelector('.audit-mismatch-details')!;
    expect(details.textContent).toContain(mismatch.entry);
    expect(details.textContent).toContain(mismatch.expected_sha256);
    expect(details.textContent).toContain(mismatch.computed_sha256);
  });
});

// ---------------------------------------------------------------------------
// Error state (status: 'error' with reason)
// ---------------------------------------------------------------------------

describe('AuditTab — статус error с reason', () => {
  it('badge имеет data-tone="warning" для status=error', async () => {
    mockSuccess({ status: 'error', reason: 'Невалидный ZIP-архив', mismatches: [] });

    const { container } = render(AuditTab, { bundlePath: '/path/to/bundle.aurora' });
    await fireEvent.click(screen.getByText(/Проверить воспроизводимость/).closest('button')!);
    await flushAsync();

    const badge = container.querySelector('.audit-result-badge');
    expect(badge!.getAttribute('data-tone')).toBe('warning');
  });

  it('рендерит reason text когда result.reason присутствует', async () => {
    const reason = 'Невалидный ZIP-архив';
    mockSuccess({ status: 'error', reason, mismatches: [] });

    const { container } = render(AuditTab, { bundlePath: '/path/to/bundle.aurora' });
    await fireEvent.click(screen.getByText(/Проверить воспроизводимость/).closest('button')!);
    await flushAsync();

    expect(container.querySelector('.audit-result-reason')!.textContent).toContain(reason);
  });
});

// ---------------------------------------------------------------------------
// IPC error (throws exception)
// ---------------------------------------------------------------------------

describe('AuditTab — ошибка IPC (выброс исключения)', () => {
  it('рендерит .audit-error с role=alert при ошибке IPC', async () => {
    mockError('Connection refused');
    const { container } = render(AuditTab, { bundlePath: '/path/to/bundle.aurora' });
    await fireEvent.click(screen.getByText(/Проверить воспроизводимость/).closest('button')!);
    await flushAsync();

    const errorEl = container.querySelector('.audit-error');
    expect(errorEl).not.toBeNull();
    expect(errorEl!.getAttribute('role')).toBe('alert');
  });

  it('errorMessage отображается в .audit-error', async () => {
    mockError('Connection refused');
    const { container } = render(AuditTab, { bundlePath: '/path/to/bundle.aurora' });
    await fireEvent.click(screen.getByText(/Проверить воспроизводимость/).closest('button')!);
    await flushAsync();

    expect(container.querySelector('.audit-error')!.textContent).toContain('Connection refused');
  });

  it('НЕ отображает .audit-result при ошибке IPC', async () => {
    mockError('Timeout');
    const { container } = render(AuditTab, { bundlePath: '/path/to/bundle.aurora' });
    await fireEvent.click(screen.getByText(/Проверить воспроизводимость/).closest('button')!);
    await flushAsync();

    expect(container.querySelector('.audit-result')).toBeNull();
  });

  it('кнопка доступна снова после ошибки (phase=error, не running)', async () => {
    mockError('Something went wrong');
    render(AuditTab, { bundlePath: '/path/to/bundle.aurora' });
    const btn = screen.getByText(/Проверить воспроизводимость/).closest('button') as HTMLButtonElement;
    await fireEvent.click(btn);
    await flushAsync();

    // After error, button text reverts to run label and should not be disabled
    const btnAfter = screen
      .getByText(/Проверить воспроизводимость/)
      .closest('button') as HTMLButtonElement;
    expect(btnAfter.disabled).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// ARIA live region
// ---------------------------------------------------------------------------

describe('AuditTab — ARIA live region', () => {
  it('.audit-result имеет aria-live="polite"', async () => {
    mockSuccess();
    const { container } = render(AuditTab, { bundlePath: '/path/to/bundle.aurora' });
    await fireEvent.click(screen.getByText(/Проверить воспроизводимость/).closest('button')!);
    await flushAsync();

    const result = container.querySelector('.audit-result');
    expect(result!.getAttribute('aria-live')).toBe('polite');
  });
});
