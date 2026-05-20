import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/svelte';

// Mock SvelteKit navigation BEFORE component import.
vi.mock('$app/navigation', () => ({
  goto: vi.fn(),
}));

// Mock projects IPC: loadSampleBundle is the primary CTA action.
vi.mock('$lib/ipc/projects', () => ({
  loadSampleBundle: vi.fn(),
}));

// Mock toast store: pushToast emitted on error path.
vi.mock('$lib/stores/toast', () => ({
  pushToast: vi.fn(),
}));

import EmptyDashboard from '../../src/lib/components/welcome/EmptyDashboard.svelte';
import { goto } from '$app/navigation';
import { loadSampleBundle } from '$lib/ipc/projects';
import { pushToast } from '$lib/stores/toast';

const mockedGoto = vi.mocked(goto);
const mockedLoadSample = vi.mocked(loadSampleBundle);
const mockedPushToast = vi.mocked(pushToast);

beforeEach(() => {
  mockedGoto.mockReset();
  mockedLoadSample.mockReset();
  mockedPushToast.mockReset();
});

afterEach(() => cleanup());

describe('EmptyDashboard', () => {
  it('renders hero / sample card / highlights / hint sections', () => {
    render(EmptyDashboard);
    // Region landmark via section aria-label
    const region = screen.getByRole('region', { name: /первый запуск/i });
    expect(region).toBeTruthy();
    // Sample card title localized
    expect(screen.getByText(/откройте пример/i)).toBeTruthy();
    // Highlights section nested region
    const highlights = screen.getByRole('region', { name: /возможности aurora/i });
    expect(highlights).toBeTruthy();
  });

  it('renders 4 methodology highlights', () => {
    render(EmptyDashboard);
    // Each highlight has class .highlight
    const items = document.querySelectorAll('.highlight');
    expect(items.length).toBe(4);
  });

  it('clicking sample CTA calls loadSampleBundle + goto /inspector', async () => {
    mockedLoadSample.mockResolvedValueOnce({
      project_uuid: 'sample-uuid',
      version_id: 1,
      channels: ['tv'],
      n_periods: 12,
    });
    mockedGoto.mockResolvedValueOnce(undefined);
    render(EmptyDashboard);

    const cta = screen.getByRole('button', { name: /открыть пример/i });
    await fireEvent.click(cta);

    await waitFor(() => {
      expect(mockedLoadSample).toHaveBeenCalledWith('kagotsel_venarus');
    });
    expect(mockedGoto).toHaveBeenCalledWith('/inspector?project=sample-uuid');
  });

  it('shows loading state when sample CTA pressed (button disabled + spinner)', async () => {
    // Never-resolving promise to keep loading state
    mockedLoadSample.mockReturnValueOnce(new Promise(() => {}));
    render(EmptyDashboard);

    const cta = screen.getByRole('button', { name: /открыть пример/i });
    await fireEvent.click(cta);

    // Find the disabled button с aria-busy
    await waitFor(() => {
      const busy = document.querySelector('button[aria-busy="true"][disabled]');
      expect(busy).toBeTruthy();
    });
    expect(document.querySelector('.cta__spinner')).toBeTruthy();
  });

  it('pushToast called when loadSampleBundle rejects', async () => {
    mockedLoadSample.mockRejectedValueOnce(new Error('Sample missing'));
    render(EmptyDashboard);

    const cta = screen.getByRole('button', { name: /открыть пример/i });
    await fireEvent.click(cta);

    await waitFor(() => {
      expect(mockedPushToast).toHaveBeenCalledTimes(1);
    });
    const arg = mockedPushToast.mock.calls[0]?.[0];
    expect(arg?.level).toBe('danger');
    expect(arg?.body).toContain('Sample missing');
    // goto NOT called on error
    expect(mockedGoto).not.toHaveBeenCalled();
  });

  it('new launch CTA goes to /wizard', async () => {
    mockedGoto.mockResolvedValueOnce(undefined);
    render(EmptyDashboard);
    const cta = screen.getByRole('button', { name: /новый прогноз с нуля/i });
    await fireEvent.click(cta);
    expect(mockedGoto).toHaveBeenCalledWith('/wizard');
  });

  it('respects sampleScenario prop override', async () => {
    mockedLoadSample.mockResolvedValueOnce({
      project_uuid: 'venarus-uuid',
      version_id: 1,
      channels: [],
      n_periods: 12,
    });
    mockedGoto.mockResolvedValueOnce(undefined);

    render(EmptyDashboard, { sampleScenario: 'venarus_baseline' });
    const cta = screen.getByRole('button', { name: /открыть пример/i });
    await fireEvent.click(cta);

    await waitFor(() => {
      expect(mockedLoadSample).toHaveBeenCalledWith('venarus_baseline');
    });
  });

  it('sigil styling applied to sample CTA (sacred lime invariant)', () => {
    render(EmptyDashboard);
    const sigilCta = document.querySelector('.cta--sigil');
    expect(sigilCta).toBeTruthy();
    expect(sigilCta?.textContent?.toLowerCase()).toContain('пример');
  });
});
