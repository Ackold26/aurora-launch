// Vitest tests for ForecastHistory.svelte (Phase Premium P-02).

import { describe, expect, it, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/svelte';

vi.mock('../../src/lib/ipc/projects', () => ({
  getProject: vi.fn(),
  compareVersions: vi.fn(),
}));

import { getProject, compareVersions } from '../../src/lib/ipc/projects';
import type { ProjectDetail, VersionSummary, VersionDiff } from '../../src/lib/ipc/projects';
import ForecastHistory from '../../src/lib/components/ForecastHistory.svelte';

const mockGetProject = vi.mocked(getProject);
const mockCompareVersions = vi.mocked(compareVersions);

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
