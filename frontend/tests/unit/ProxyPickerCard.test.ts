// Vitest tests for ProxyPickerCard.svelte (Phase 1.C.3 — Step 2 wizard proxy picker).
//
// IPC mocked via globalThis.__auroraIpcMock (set by setup.ts __setInvokeForTesting).
// @tauri-apps/plugin-dialog is vi.mock'd per-test so openDialog never touches Tauri.

import { describe, expect, it, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';
import ProxyPickerCard from '../../src/lib/components/ProxyPickerCard.svelte';

// ── Module-level mock for Tauri dialog plugin ──────────────────────────────
//
// Must appear BEFORE the import of ProxyPickerCard so vi.mock hoisting works.
// Each test overrides the `open` fn via `openMock` where needed.
const openMock = vi.fn();
vi.mock('@tauri-apps/plugin-dialog', () => ({
  open: (...args: unknown[]) => openMock(...args),
}));

// ── Helpers ────────────────────────────────────────────────────────────────

type IpcMock = { mockResolvedValueOnce: (v: unknown) => void; mockRejectedValueOnce: (e: unknown) => void };
function ipcMock(): IpcMock {
  return (globalThis as unknown as { __auroraIpcMock: IpcMock }).__auroraIpcMock;
}

/** Flush onMount async chain (3 microtask turns covers Promise chains). */
async function flush() {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

const SAMPLE_BUNDLES = [
  { id: 'kagotsel_venarus', path: '/data/kagotsel.aurora', label: 'Кагоцел (грипп/ОРВИ)', exists: true },
  { id: 'venarus_baseline', path: '/data/venarus.aurora', label: 'Венарус (хроническая)', exists: true },
  { id: 'multi_proxy',      path: '/data/multi.aurora',   label: 'Мульти-прокси (3 бренда)', exists: true },
];

/** Set up IPC mock to return a successful listSampleBundles response. */
function mockBundles(
  overrides?: Partial<(typeof SAMPLE_BUNDLES)[number]>[],
) {
  const bundles = overrides
    ? SAMPLE_BUNDLES.map((b, i) => ({ ...b, ...(overrides[i] ?? {}) }))
    : SAMPLE_BUNDLES;
  ipcMock().mockResolvedValueOnce({ bundles });
}

beforeEach(() => {
  cleanup();
  openMock.mockReset();
});

// ── Rendering tests ────────────────────────────────────────────────────────

describe('ProxyPickerCard — rendering', () => {
  it('renders heading «Шаг 2 — Выберите прокси-бренд»', async () => {
    mockBundles();
    render(ProxyPickerCard, { selectedPath: null, selectedLabel: null });
    await flush();
    expect(screen.getByText('Шаг 2 — Выберите прокси-бренд')).toBeTruthy();
  });

  it('shows loading state initially', () => {
    // Never resolved — stays in loading state during sync render.
    ipcMock().mockResolvedValueOnce(
      new Promise(() => {}), // never resolves in this test
    );
    render(ProxyPickerCard, { selectedPath: null, selectedLabel: null });
    expect(screen.getByText(/Загружаем примеры/)).toBeTruthy();
  });

  it('fetches sample bundles at mount via ipc.listSampleBundles', async () => {
    mockBundles();
    render(ProxyPickerCard, { selectedPath: null, selectedLabel: null });
    await flush();
    // All three cards present → ipc was called and response processed.
    expect(screen.getByText('Кагоцел (грипп/ОРВИ)')).toBeTruthy();
    expect(screen.getByText('Венарус (хроническая)')).toBeTruthy();
    expect(screen.getByText('Мульти-прокси (3 бренда)')).toBeTruthy();
  });

  it('renders one card per sample bundle (all existing)', async () => {
    mockBundles();
    const { container } = render(ProxyPickerCard, { selectedPath: null, selectedLabel: null });
    await flush();
    const cards = container.querySelectorAll('.bundle-card');
    expect(cards).toHaveLength(3);
  });

  it('shows disabled state for bundle with exists=false', async () => {
    mockBundles([
      {},
      { exists: false, label: 'Венарус (хроническая)' },
      {},
    ]);
    const { container } = render(ProxyPickerCard, { selectedPath: null, selectedLabel: null });
    await flush();
    const disabledCards = container.querySelectorAll('.card-disabled');
    expect(disabledCards).toHaveLength(1);
    // The button itself should be HTML-disabled.
    const disabledBtn = container.querySelector('button.card-disabled') as HTMLButtonElement | null;
    expect(disabledBtn).not.toBeNull();
    expect(disabledBtn!.disabled).toBe(true);
  });

  it('upload button is present', async () => {
    mockBundles();
    render(ProxyPickerCard, { selectedPath: null, selectedLabel: null });
    await flush();
    const btn = screen.getByText(/Загрузить свой \.aurora файл/);
    expect(btn).toBeTruthy();
  });
});

// ── IPC error fallback ─────────────────────────────────────────────────────

describe('ProxyPickerCard — ipc error fallback', () => {
  it('shows error message when ipc.listSampleBundles rejects', async () => {
    ipcMock().mockRejectedValueOnce(new Error('sidecar offline'));
    render(ProxyPickerCard, { selectedPath: null, selectedLabel: null });
    await flush();
    // Should show role=alert with error text.
    const alert = screen.getByRole('alert');
    expect(alert).toBeTruthy();
    expect(alert.textContent).toContain('sidecar offline');
  });
});

// ── Selection tests ────────────────────────────────────────────────────────

describe('ProxyPickerCard — selection', () => {
  it('clicking a sample card sets selectedPath and selectedLabel', async () => {
    mockBundles();
    let path: string | null = null;
    let label: string | null = null;

    const { container } = render(ProxyPickerCard, {
      get selectedPath() { return path; },
      set selectedPath(v) { path = v; },
      get selectedLabel() { return label; },
      set selectedLabel(v) { label = v; },
    });
    await flush();

    const firstCard = container.querySelector('.bundle-card') as HTMLButtonElement;
    await fireEvent.click(firstCard);
    await flush();

    expect(path).toBe('/data/kagotsel.aurora');
    expect(label).toBe('Кагоцел (грипп/ОРВИ)');
  });

  it('clicking already-selected card does not deselect (radio semantics)', async () => {
    mockBundles();
    let path: string | null = '/data/kagotsel.aurora';
    let label: string | null = 'Кагоцел (грипп/ОРВИ)';

    const { container } = render(ProxyPickerCard, {
      get selectedPath() { return path; },
      set selectedPath(v) { path = v; },
      get selectedLabel() { return label; },
      set selectedLabel(v) { label = v; },
    });
    await flush();

    const firstCard = container.querySelector('.bundle-card') as HTMLButtonElement;
    await fireEvent.click(firstCard);
    await flush();

    // Still selected — not toggled off.
    expect(path).toBe('/data/kagotsel.aurora');
  });

  it('shows «Выбран: …» indicator when selectedLabel is pre-set', async () => {
    // Tests that the indicator renders when selectedLabel is non-null.
    // Bindable re-render in jsdom is tested via the underlying prop visibility;
    // here we verify the indicator markup exists when the prop is pre-set.
    mockBundles();
    render(ProxyPickerCard, {
      selectedPath: '/data/kagotsel.aurora',
      selectedLabel: 'Кагоцел (грипп/ОРВИ)',
    });
    await flush();

    expect(screen.getByText(/Выбран:/)).toBeTruthy();
    // Use the .selected-indicator paragraph specifically to avoid matching card labels.
    const indicator = screen.getByText(/Выбран:/);
    expect(indicator.textContent).toContain('Кагоцел');
  });

  it('indicator is absent when selectedLabel is null', async () => {
    mockBundles();
    render(ProxyPickerCard, { selectedPath: null, selectedLabel: null });
    await flush();
    expect(screen.queryByText(/Выбран:/)).toBeNull();
  });
});

// ── A11y tests ─────────────────────────────────────────────────────────────

describe('ProxyPickerCard — a11y', () => {
  it('radiogroup role on cards container', async () => {
    mockBundles();
    render(ProxyPickerCard, { selectedPath: null, selectedLabel: null });
    await flush();
    const group = screen.getByRole('radiogroup');
    expect(group).toBeTruthy();
  });

  it('radiogroup has aria-label «Выбор прокси-бренда»', async () => {
    mockBundles();
    render(ProxyPickerCard, { selectedPath: null, selectedLabel: null });
    await flush();
    const group = screen.getByRole('radiogroup', { name: 'Выбор прокси-бренда' });
    expect(group).toBeTruthy();
  });

  it('aria-pressed=false on unselected card', async () => {
    mockBundles();
    const { container } = render(ProxyPickerCard, {
      selectedPath: null,
      selectedLabel: null,
    });
    await flush();
    const firstCard = container.querySelector('.bundle-card') as HTMLButtonElement;
    expect(firstCard.getAttribute('aria-pressed')).toBe('false');
  });

  it('aria-pressed=true when selectedPath matches card path (pre-set)', async () => {
    // Render with the first bundle pre-selected to verify aria-pressed=true renders.
    mockBundles();
    const { container } = render(ProxyPickerCard, {
      selectedPath: '/data/kagotsel.aurora',
      selectedLabel: 'Кагоцел (грипп/ОРВИ)',
    });
    await flush();

    const cards = container.querySelectorAll('.bundle-card') as NodeListOf<HTMLButtonElement>;
    expect(cards[0]?.getAttribute('aria-pressed')).toBe('true');
    expect(cards[1]?.getAttribute('aria-pressed')).toBe('false');
    expect(cards[2]?.getAttribute('aria-pressed')).toBe('false');
  });
});

// ── Upload tests ───────────────────────────────────────────────────────────

describe('ProxyPickerCard — upload button', () => {
  it('clicking upload button opens Tauri dialog', async () => {
    mockBundles();
    openMock.mockResolvedValueOnce(null); // user cancelled
    render(ProxyPickerCard, { selectedPath: null, selectedLabel: null });
    await flush();

    const uploadBtn = screen.getByText(/Загрузить свой \.aurora файл/);
    await fireEvent.click(uploadBtn);
    await flush();

    expect(openMock).toHaveBeenCalledOnce();
    expect(openMock).toHaveBeenCalledWith(
      expect.objectContaining({
        multiple: false,
        filters: expect.arrayContaining([
          expect.objectContaining({ extensions: expect.arrayContaining(['aurora']) }),
        ]),
      }),
    );
  });

  it('selecting a custom file sets selectedPath + label with basename', async () => {
    mockBundles();
    openMock.mockResolvedValueOnce('C:\\Users\\user\\downloads\\my-brand.aurora');

    let path: string | null = null;
    let label: string | null = null;

    render(ProxyPickerCard, {
      get selectedPath() { return path; },
      set selectedPath(v) { path = v; },
      get selectedLabel() { return label; },
      set selectedLabel(v) { label = v; },
    });
    await flush();

    const uploadBtn = screen.getByText(/Загрузить свой \.aurora файл/);
    await fireEvent.click(uploadBtn);
    await flush();

    expect(path).toBe('C:\\Users\\user\\downloads\\my-brand.aurora');
    expect(label).toBe('Свой файл: my-brand.aurora');
  });

  it('cancelling dialog (null returned) does not change selected', async () => {
    mockBundles();
    openMock.mockResolvedValueOnce(null);

    let path: string | null = null;
    let label: string | null = null;

    render(ProxyPickerCard, {
      get selectedPath() { return path; },
      set selectedPath(v) { path = v; },
      get selectedLabel() { return label; },
      set selectedLabel(v) { label = v; },
    });
    await flush();

    const uploadBtn = screen.getByText(/Загрузить свой \.aurora файл/);
    await fireEvent.click(uploadBtn);
    await flush();

    expect(path).toBeNull();
    expect(label).toBeNull();
  });
});
