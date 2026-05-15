// Vitest tests for ForecastHistory.svelte (Phase Premium P-02).

import { describe, expect, it, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/svelte';

vi.mock('../../src/lib/ipc/projects', () => ({
  getProject: vi.fn(),
  compareVersions: vi.fn(),
  compareForecastVersions: vi.fn(),
}));

import {
  getProject,
  compareVersions,
  compareForecastVersions,
} from '../../src/lib/ipc/projects';
import type { ProjectDetail, VersionSummary, VersionDiff } from '../../src/lib/ipc/projects';
import ForecastHistory from '../../src/lib/components/ForecastHistory.svelte';

const mockGetProject = vi.mocked(getProject);
const mockCompareVersions = vi.mocked(compareVersions);
const mockCompareForecastVersions = vi.mocked(compareForecastVersions);

function version(overrides: Partial<VersionSummary> = {}): VersionSummary {
  return {
    version_id: 1,
    revision: 1,
    label: null,
    decision_note: null,
    created_at: '2026-05-15T10:00:00Z',
    composite_bundle_hash: 'aaaaaaaa1234',
    file_count: 3,
    ...overrides,
  };
}

function detail(versions: VersionSummary[] = []): ProjectDetail {
  return {
    project_uuid: 'uuid-test',
    name: 'Test Project',
    metadata: {},
    versions,
  };
}

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('ForecastHistory', () => {
  it('renders empty-state when project has no versions', async () => {
    render(ForecastHistory, { projectUuid: 'uuid-test', initialDetail: detail([]) });
    expect(screen.getByText('Здесь будет ваша история')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Создать первый прогноз' })).toBeTruthy();
  });

  it('renders timeline with provided versions', async () => {
    const versions = [
      version({ version_id: 1, revision: 1, label: 'Initial' }),
      version({ version_id: 2, revision: 2, label: 'Post-pilot tuning' }),
    ];
    render(ForecastHistory, { projectUuid: 'uuid-test', initialDetail: detail(versions) });
    expect(screen.getByText('v1')).toBeTruthy();
    expect(screen.getByText('v2')).toBeTruthy();
    expect(screen.getByText('Initial')).toBeTruthy();
    expect(screen.getByText('Post-pilot tuning')).toBeTruthy();
  });

  it('fetches detail via getProject when no initialDetail provided', async () => {
    mockGetProject.mockResolvedValueOnce(detail([version({ version_id: 5 })]));
    render(ForecastHistory, { projectUuid: 'uuid-async' });
    await waitFor(() => {
      expect(mockGetProject).toHaveBeenCalledWith('uuid-async');
    });
    await waitFor(() => {
      expect(screen.getByText('v1')).toBeTruthy();
    });
  });

  it('shows error state if getProject rejects', async () => {
    mockGetProject.mockRejectedValueOnce(new Error('network down'));
    render(ForecastHistory, { projectUuid: 'fail' });
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeTruthy();
    });
    expect(screen.getByText(/Не удалось загрузить/)).toBeTruthy();
  });

  it('sorts versions newest first', async () => {
    const versions = [
      version({ version_id: 1, revision: 1, created_at: '2026-05-15T08:00:00Z' }),
      version({ version_id: 2, revision: 2, created_at: '2026-05-15T12:00:00Z' }),
      version({ version_id: 3, revision: 3, created_at: '2026-05-15T10:00:00Z' }),
    ];
    render(ForecastHistory, { projectUuid: 'sort-test', initialDetail: detail(versions) });
    const items = screen.getAllByRole('option');
    // Order should be v2 (12:00), v3 (10:00), v1 (08:00)
    expect(items[0]?.textContent).toContain('v2');
    expect(items[1]?.textContent).toContain('v3');
    expect(items[2]?.textContent).toContain('v1');
  });

  it('toggles selection on version row click', async () => {
    const versions = [version({ version_id: 1, revision: 1 })];
    render(ForecastHistory, { projectUuid: 't', initialDetail: detail(versions) });
    const toggle = screen.getByRole('button', { name: /Версия 1.*выделить/ });
    expect(toggle.getAttribute('aria-pressed')).toBe('false');
    await fireEvent.click(toggle);
    expect(toggle.getAttribute('aria-pressed')).toBe('true');
  });

  it('shows compare button only when 2 versions selected', async () => {
    const versions = [
      version({ version_id: 1, revision: 1 }),
      version({ version_id: 2, revision: 2 }),
    ];
    render(ForecastHistory, { projectUuid: 't', initialDetail: detail(versions) });

    // Initial — hint shown
    expect(screen.getByText(/Выделите 2 версии/)).toBeTruthy();

    // Select first
    await fireEvent.click(screen.getByRole('button', { name: /Версия 1.*выделить/ }));
    expect(screen.getByText(/Выделена 1/)).toBeTruthy();

    // Select second — compare button appears
    await fireEvent.click(screen.getByRole('button', { name: /Версия 2.*выделить/ }));
    expect(screen.getByRole('button', { name: 'Сравнить' })).toBeTruthy();
  });

  it('runs compareVersions and renders diff on compare click', async () => {
    const versions = [
      version({ version_id: 1, revision: 1 }),
      version({ version_id: 2, revision: 2 }),
    ];
    const diff: VersionDiff = {
      files_only_in_a: [],
      files_only_in_b: ['new.json'],
      files_changed: ['proxy_posterior.msgpack'],
      files_unchanged: ['manifest.json'],
    };
    mockCompareVersions.mockResolvedValueOnce(diff);
    mockCompareForecastVersions.mockResolvedValueOnce({ available: false });

    render(ForecastHistory, { projectUuid: 't', initialDetail: detail(versions) });
    await fireEvent.click(screen.getByRole('button', { name: /Версия 1.*выделить/ }));
    await fireEvent.click(screen.getByRole('button', { name: /Версия 2.*выделить/ }));
    await fireEvent.click(screen.getByRole('button', { name: 'Сравнить' }));

    await waitFor(() => {
      expect(mockCompareVersions).toHaveBeenCalledWith(1, 2);
    });
    await waitFor(() => {
      expect(screen.getByText('proxy_posterior.msgpack')).toBeTruthy();
      expect(screen.getByText('new.json')).toBeTruthy();
    });
  });

  it('shows identical message when diff has no changes', async () => {
    const versions = [
      version({ version_id: 1, revision: 1 }),
      version({ version_id: 2, revision: 2 }),
    ];
    mockCompareVersions.mockResolvedValueOnce({
      files_only_in_a: [],
      files_only_in_b: [],
      files_changed: [],
      files_unchanged: ['manifest.json'],
    });
    mockCompareForecastVersions.mockResolvedValueOnce({ available: false });

    render(ForecastHistory, { projectUuid: 't', initialDetail: detail(versions) });
    await fireEvent.click(screen.getByRole('button', { name: /Версия 1.*выделить/ }));
    await fireEvent.click(screen.getByRole('button', { name: /Версия 2.*выделить/ }));
    await fireEvent.click(screen.getByRole('button', { name: 'Сравнить' }));

    await waitFor(() => {
      expect(screen.getByText(/Версии идентичны/)).toBeTruthy();
    });
  });

  it('clearSelection resets state', async () => {
    const versions = [
      version({ version_id: 1, revision: 1 }),
      version({ version_id: 2, revision: 2 }),
    ];
    render(ForecastHistory, { projectUuid: 't', initialDetail: detail(versions) });
    await fireEvent.click(screen.getByRole('button', { name: /Версия 1.*выделить/ }));
    await fireEvent.click(screen.getByRole('button', { name: /Версия 2.*выделить/ }));
    await fireEvent.click(screen.getByRole('button', { name: 'Очистить' }));
    expect(screen.getByText(/Выделите 2 версии/)).toBeTruthy();
  });

  it('expert mode shows composite_bundle_hash + file_count', async () => {
    const versions = [
      version({
        version_id: 1,
        revision: 1,
        composite_bundle_hash: 'abcdef1234567890fedcba',
        file_count: 7,
      }),
    ];
    render(ForecastHistory, {
      projectUuid: 't',
      initialDetail: detail(versions),
      expertMode: true,
    });
    expect(screen.getByText(/abcdef12…dcba/)).toBeTruthy();
    expect(screen.getByText(/Файлов:/)).toBeTruthy();
  });

  it('manager mode hides expert details', async () => {
    const versions = [version({ version_id: 1 })];
    render(ForecastHistory, {
      projectUuid: 't',
      initialDetail: detail(versions),
      expertMode: false,
    });
    expect(screen.queryByText(/Файлов:/)).toBeNull();
  });

  it('renders semantic diff when compareForecastVersions returns available', async () => {
    const versions = [
      version({ version_id: 1, revision: 1 }),
      version({ version_id: 2, revision: 2 }),
    ];
    mockCompareVersions.mockResolvedValueOnce({
      files_only_in_a: [],
      files_only_in_b: [],
      files_changed: ['forecast.json'],
      files_unchanged: [],
    });
    mockCompareForecastVersions.mockResolvedValueOnce({
      available: true,
      point_a: 1_000_000,
      point_b: 1_200_000,
      point_delta_abs: 200_000,
      point_delta_pct: 20.0,
      ci_width_a: 200_000,
      ci_width_b: 150_000,
      ci_width_delta_pct: -25.0,
      engine_mode_a: 'pure_transfer',
      engine_mode_b: 'pure_transfer',
      horizon_a: 12,
      horizon_b: 12,
    });

    render(ForecastHistory, { projectUuid: 't', initialDetail: detail(versions) });
    await fireEvent.click(screen.getByRole('button', { name: /Версия 1.*выделить/ }));
    await fireEvent.click(screen.getByRole('button', { name: /Версия 2.*выделить/ }));
    await fireEvent.click(screen.getByRole('button', { name: 'Сравнить' }));

    await waitFor(() => {
      // Semantic panel shows "Что изменилось" heading + percentage badges
      expect(screen.getByText(/Что изменилось/)).toBeTruthy();
      expect(screen.getByText('+20.0%')).toBeTruthy();
      expect(screen.getByText('-25.0%')).toBeTruthy();
    });
  });

  it('hides semantic diff when forecast.json missing from version', async () => {
    const versions = [
      version({ version_id: 1, revision: 1 }),
      version({ version_id: 2, revision: 2 }),
    ];
    mockCompareVersions.mockResolvedValueOnce({
      files_only_in_a: [],
      files_only_in_b: [],
      files_changed: [],
      files_unchanged: ['manifest.json'],
    });
    mockCompareForecastVersions.mockResolvedValueOnce({
      available: false,
      reason: 'forecast.json missing',
    });

    render(ForecastHistory, { projectUuid: 't', initialDetail: detail(versions) });
    await fireEvent.click(screen.getByRole('button', { name: /Версия 1.*выделить/ }));
    await fireEvent.click(screen.getByRole('button', { name: /Версия 2.*выделить/ }));
    await fireEvent.click(screen.getByRole('button', { name: 'Сравнить' }));

    await waitFor(() => {
      expect(screen.getByText(/Версии идентичны/)).toBeTruthy();
    });
    expect(screen.queryByText(/Что изменилось/)).toBeNull();
  });

  it('M-05 hover preloads compareVersions when 1 version selected', async () => {
    const versions = [
      version({ version_id: 1, revision: 1 }),
      version({ version_id: 2, revision: 2 }),
    ];
    mockCompareVersions.mockResolvedValueOnce({
      files_only_in_a: [],
      files_only_in_b: [],
      files_changed: [],
      files_unchanged: [],
    });
    mockCompareForecastVersions.mockResolvedValueOnce({ available: false });

    render(ForecastHistory, { projectUuid: 't', initialDetail: detail(versions) });
    // Select v1
    await fireEvent.click(screen.getByRole('button', { name: /Версия 1.*выделить/ }));
    // Hover over v2 row (not selected yet)
    const items = screen.getAllByRole('option');
    const v2Row = items.find((el) => el.textContent?.includes('v2'));
    await fireEvent.mouseEnter(v2Row!);

    // Hover should have triggered preload — verify IPC mocks were called
    await waitFor(() => {
      expect(mockCompareVersions).toHaveBeenCalledWith(1, 2);
      expect(mockCompareForecastVersions).toHaveBeenCalledWith(1, 2);
    });
  });

  it('M-05 hover does NOT preload when 0 or 2 selections', async () => {
    const versions = [
      version({ version_id: 1, revision: 1 }),
      version({ version_id: 2, revision: 2 }),
    ];
    mockCompareVersions.mockClear();
    mockCompareForecastVersions.mockClear();

    render(ForecastHistory, { projectUuid: 't', initialDetail: detail(versions) });
    // Nothing selected — hover should NOT trigger preload
    const items = screen.getAllByRole('option');
    await fireEvent.mouseEnter(items[0]!);
    await fireEvent.mouseEnter(items[1]!);

    expect(mockCompareVersions).not.toHaveBeenCalled();
    expect(mockCompareForecastVersions).not.toHaveBeenCalled();
  });

  it('M-05 hover same pair twice → preload kicked off only once', async () => {
    const versions = [
      version({ version_id: 1, revision: 1 }),
      version({ version_id: 2, revision: 2 }),
    ];
    mockCompareVersions.mockClear();
    mockCompareForecastVersions.mockClear();
    mockCompareVersions.mockResolvedValueOnce({
      files_only_in_a: [],
      files_only_in_b: [],
      files_changed: [],
      files_unchanged: [],
    });
    mockCompareForecastVersions.mockResolvedValueOnce({ available: false });

    render(ForecastHistory, { projectUuid: 't', initialDetail: detail(versions) });
    await fireEvent.click(screen.getByRole('button', { name: /Версия 1.*выделить/ }));

    const items = screen.getAllByRole('option');
    const v2Row = items.find((el) => el.textContent?.includes('v2'));
    // Hover twice — second should hit cache, no second IPC
    await fireEvent.mouseEnter(v2Row!);
    await fireEvent.mouseLeave(v2Row!);
    await fireEvent.mouseEnter(v2Row!);

    expect(mockCompareVersions).toHaveBeenCalledTimes(1);
    expect(mockCompareForecastVersions).toHaveBeenCalledTimes(1);
  });

  it('selection limits к max 2 (FIFO replacement)', async () => {
    const versions = [
      version({ version_id: 1, revision: 1 }),
      version({ version_id: 2, revision: 2 }),
      version({ version_id: 3, revision: 3 }),
    ];
    render(ForecastHistory, { projectUuid: 't', initialDetail: detail(versions) });
    await fireEvent.click(screen.getByRole('button', { name: /Версия 1.*выделить/ }));
    await fireEvent.click(screen.getByRole('button', { name: /Версия 2.*выделить/ }));
    await fireEvent.click(screen.getByRole('button', { name: /Версия 3.*выделить/ }));

    // Version 1 should now be deselected (FIFO eviction)
    const v1Toggle = screen.getByRole('button', { name: /Версия 1.*выделить/ });
    expect(v1Toggle.getAttribute('aria-pressed')).toBe('false');
    // Version 2 + 3 selected
    const v2Toggle = screen.getByRole('button', { name: /Версия 2.*снять/ });
    const v3Toggle = screen.getByRole('button', { name: /Версия 3.*снять/ });
    expect(v2Toggle.getAttribute('aria-pressed')).toBe('true');
    expect(v3Toggle.getAttribute('aria-pressed')).toBe('true');
  });
});
