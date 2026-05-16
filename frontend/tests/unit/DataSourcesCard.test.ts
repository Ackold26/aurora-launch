// Vitest tests for DataSourcesCard.svelte (Phase 3 — watched folder management).
//
// IPC mocked via:
//   - __setInvokeForTesting (client.ts: get_data_sources / set_data_sources)
//   - __setProjectsInvokeForTesting (projects.ts: list_projects)
// @tauri-apps/plugin-dialog mocked via vi.mock hoisting.

import { describe, expect, it, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/svelte';

import { __setInvokeForTesting, type InvokeFn } from '../../src/lib/ipc/client';
import { __setProjectsInvokeForTesting } from '../../src/lib/ipc/projects';
import type { DataSourceConfig } from '../../src/lib/ipc/client';

// ── Module-level mock for Tauri dialog plugin ──────────────────────────────
// Must appear BEFORE the component import so vi.mock hoisting works.
const openDialogMock = vi.fn();
vi.mock('@tauri-apps/plugin-dialog', () => ({
  open: (...args: unknown[]) => openDialogMock(...args),
}));

import DataSourcesCard from '../../src/lib/components/DataSourcesCard.svelte';

// ── Constants ──────────────────────────────────────────────────────────────

const PROJECT_UUID = 'proj-test-001';
const PROJECT_UUID_2 = 'proj-test-002';
const PROJECT_NAME = 'Тестовый проект';

const PROJECT_LIST_SINGLE = [
  {
    project_uuid: PROJECT_UUID,
    name: PROJECT_NAME,
    created_at: '2026-01-01T00:00:00Z',
    last_modified: '2026-01-02T00:00:00Z',
    granularity: 'monthly',
    version_count: 3,
    current_version_id: 3,
  },
];

// Two projects — prevents auto-selection when no projectUuid prop given
const PROJECT_LIST_TWO = [
  ...PROJECT_LIST_SINGLE,
  {
    project_uuid: PROJECT_UUID_2,
    name: 'Второй проект',
    created_at: '2026-02-01T00:00:00Z',
    last_modified: '2026-02-02T00:00:00Z',
    granularity: 'monthly',
    version_count: 1,
    current_version_id: 1,
  },
];

const SOURCE_DSM: DataSourceConfig = {
  source_kind: 'dsm_xlsx_folder',
  path: 'C:\\Data\\DSM',
  last_checked_at: '2026-05-16T08:00:00Z',
  last_modified_seen: null,
};

const SOURCE_MEDIASCOPE: DataSourceConfig = {
  source_kind: 'mediascope_xlsx_folder',
  path: 'C:\\Data\\Mediascope',
  last_checked_at: null,
  last_modified_seen: null,
};

// ── IPC mock helpers ───────────────────────────────────────────────────────

/**
 * Set up IPC invoke mocks. Always call before render.
 * setSpy receives (cmd, args) for set_data_sources calls — used for assertion.
 */
function setupMocks(
  sources: DataSourceConfig[] = [],
  options: {
    projects?: typeof PROJECT_LIST_SINGLE;
    sourcesError?: boolean;
    projectsError?: boolean;
  } = {},
): ReturnType<typeof vi.fn> {
  const projectList = options.projects ?? PROJECT_LIST_SINGLE;

  const projectsInvoke = vi.fn(async (cmd: string) => {
    if (cmd === 'list_projects') {
      if (options.projectsError) throw new Error('DB unavailable');
      return projectList;
    }
    throw new Error(`Unmocked projects IPC: ${cmd}`);
  });
  __setProjectsInvokeForTesting(
    projectsInvoke as Parameters<typeof __setProjectsInvokeForTesting>[0],
  );

  const setSpy = vi.fn().mockResolvedValue({ saved: true, count: 0 });

  const clientInvoke = vi.fn(async (cmd: string, args?: Record<string, unknown>) => {
    if (cmd === 'get_data_sources') {
      if (options.sourcesError) throw new Error('sources unavailable');
      return { sources };
    }
    if (cmd === 'set_data_sources') {
      return setSpy(cmd, args);
    }
    throw new Error(`Unmocked IPC: ${cmd}`);
  });
  __setInvokeForTesting(clientInvoke as InvokeFn);

  return setSpy;
}

beforeEach(() => {
  cleanup();
  openDialogMock.mockReset();
});

afterEach(() => {
  cleanup();
});

// ── Tests ──────────────────────────────────────────────────────────────────

describe('DataSourcesCard — empty state', () => {
  it('1. shows empty-state hint when project has no sources', async () => {
    setupMocks([]);
    render(DataSourcesCard, { projectUuid: PROJECT_UUID });

    await waitFor(
      () => expect(screen.getByText(/Папки не настроены|No folders configured/i)).toBeDefined(),
      { timeout: 2000 },
    );
  });

  it('1b. shows project selector when no project is pre-selected (two projects, no auto-select)', async () => {
    setupMocks([], { projects: PROJECT_LIST_TWO });
    render(DataSourcesCard, {});

    // Wait for projects to load — the no-project hint <p> should appear
    await waitFor(
      () => {
        // The hint paragraph (not the option element) contains "Выберите проект..."
        const hint = screen.queryByText(/Выберите проект, чтобы управлять/i);
        expect(hint).not.toBeNull();
      },
      { timeout: 2000 },
    );

    // The project selector combobox exists
    const selects = screen.getAllByRole('combobox');
    expect(selects.length).toBeGreaterThan(0);
  });
});

describe('DataSourcesCard — IPC fetch at mount', () => {
  it('2. fetches getDataSources with the projectUuid prop at mount', async () => {
    let capturedUuid: string | undefined;

    const projectsInvoke = vi.fn(async (cmd: string) => {
      if (cmd === 'list_projects') return PROJECT_LIST_SINGLE;
      throw new Error(cmd);
    });
    __setProjectsInvokeForTesting(
      projectsInvoke as Parameters<typeof __setProjectsInvokeForTesting>[0],
    );

    const clientInvoke = vi.fn(async (cmd: string, args?: Record<string, unknown>) => {
      if (cmd === 'get_data_sources') {
        capturedUuid = String(args?.project_uuid ?? '');
        return { sources: [] };
      }
      throw new Error(cmd);
    });
    __setInvokeForTesting(clientInvoke as InvokeFn);

    render(DataSourcesCard, { projectUuid: PROJECT_UUID });

    await waitFor(() => expect(capturedUuid).toBe(PROJECT_UUID), { timeout: 2000 });
  });
});

describe('DataSourcesCard — source rendering', () => {
  it('3. renders one row per source in the list', async () => {
    setupMocks([SOURCE_DSM, SOURCE_MEDIASCOPE]);
    render(DataSourcesCard, { projectUuid: PROJECT_UUID });

    await waitFor(
      () => expect(screen.getAllByRole('listitem').length).toBe(2),
      { timeout: 2000 },
    );
  });

  it('4. renders correct kind badge labels for DSM and Mediascope', async () => {
    setupMocks([SOURCE_DSM, SOURCE_MEDIASCOPE]);
    render(DataSourcesCard, { projectUuid: PROJECT_UUID });

    await waitFor(
      () => {
        expect(screen.getByText(/DSM-выгрузка|DSM export/i)).toBeDefined();
        expect(screen.getByText(/Mediascope-выгрузка|Mediascope export/i)).toBeDefined();
      },
      { timeout: 2000 },
    );
  });

  it('4b. renders Manual kind badge when source_kind is manual', async () => {
    const manualSource: DataSourceConfig = {
      source_kind: 'manual',
      path: 'C:\\Data\\Manual',
      last_checked_at: null,
      last_modified_seen: null,
    };
    setupMocks([manualSource]);
    render(DataSourcesCard, { projectUuid: PROJECT_UUID });

    await waitFor(
      () => expect(screen.getByText(/Ручной импорт|Manual import/i)).toBeDefined(),
      { timeout: 2000 },
    );
  });
});

describe('DataSourcesCard — add folder', () => {
  it('5. add button triggers dialog + IPC save with extended list', async () => {
    const setSpy = setupMocks([]);
    render(DataSourcesCard, { projectUuid: PROJECT_UUID });
    openDialogMock.mockResolvedValueOnce('C:\\NewFolder');

    // Wait for add button to appear
    await waitFor(
      () => screen.getByRole('button', { name: /Добавить папку|Add folder/i }),
      { timeout: 2000 },
    );
    const addBtn = screen.getByRole('button', { name: /Добавить папку|Add folder/i });
    await fireEvent.click(addBtn);

    await waitFor(
      () => expect(openDialogMock).toHaveBeenCalledWith(
        expect.objectContaining({ directory: true }),
      ),
      { timeout: 2000 },
    );
    await waitFor(
      () => expect(setSpy).toHaveBeenCalledWith(
        'set_data_sources',
        expect.objectContaining({
          project_uuid: PROJECT_UUID,
          sources: expect.arrayContaining([
            expect.objectContaining({ path: 'C:\\NewFolder' }),
          ]),
        }),
      ),
      { timeout: 2000 },
    );
  });

  it('5b. cancelled dialog (null) does not call set_data_sources', async () => {
    const setSpy = setupMocks([]);
    render(DataSourcesCard, { projectUuid: PROJECT_UUID });
    openDialogMock.mockResolvedValueOnce(null);

    await waitFor(
      () => screen.getByRole('button', { name: /Добавить папку|Add folder/i }),
      { timeout: 2000 },
    );
    const addBtn = screen.getByRole('button', { name: /Добавить папку|Add folder/i });
    await fireEvent.click(addBtn);

    // Give a moment for any async processing
    await new Promise((r) => setTimeout(r, 50));

    expect(setSpy).not.toHaveBeenCalled();
  });
});

describe('DataSourcesCard — remove folder', () => {
  it('6. remove button calls IPC save without the removed item', async () => {
    const setSpy = setupMocks([SOURCE_DSM, SOURCE_MEDIASCOPE]);
    render(DataSourcesCard, { projectUuid: PROJECT_UUID });

    // Wait for dismiss buttons to appear
    await waitFor(
      () => screen.getAllByRole('button', { name: /Убрать папку|Remove folder/i }),
      { timeout: 2000 },
    );
    const dismissBtns = screen.getAllByRole('button', { name: /Убрать папку|Remove folder/i });
    const firstBtn = dismissBtns[0];
    if (!firstBtn) throw new Error('No dismiss button found');
    await fireEvent.click(firstBtn);

    await waitFor(
      () => expect(setSpy).toHaveBeenCalledWith(
        'set_data_sources',
        expect.objectContaining({
          project_uuid: PROJECT_UUID,
          sources: expect.not.arrayContaining([
            expect.objectContaining({ path: SOURCE_DSM.path }),
          ]),
        }),
      ),
      { timeout: 2000 },
    );
  });
});

describe('DataSourcesCard — save indicator', () => {
  it('7. save indicator shows "saving" during in-flight IPC save', async () => {
    let resolveSet!: (v: unknown) => void;
    const setPromise = new Promise((res) => { resolveSet = res; });

    const projectsInvoke = vi.fn(async (cmd: string) => {
      if (cmd === 'list_projects') return PROJECT_LIST_SINGLE;
      throw new Error(cmd);
    });
    __setProjectsInvokeForTesting(
      projectsInvoke as Parameters<typeof __setProjectsInvokeForTesting>[0],
    );

    const clientInvoke = vi.fn(async (cmd: string) => {
      if (cmd === 'get_data_sources') return { sources: [] };
      if (cmd === 'set_data_sources')
        return setPromise.then(() => ({ saved: true, count: 0 }));
      throw new Error(cmd);
    });
    __setInvokeForTesting(clientInvoke as InvokeFn);

    render(DataSourcesCard, { projectUuid: PROJECT_UUID });
    openDialogMock.mockResolvedValueOnce('C:\\Folder');

    // Wait for add button
    await waitFor(
      () => screen.getByRole('button', { name: /Добавить папку|Add folder/i }),
      { timeout: 2000 },
    );

    const addBtn = screen.getByRole('button', { name: /Добавить папку|Add folder/i });
    await fireEvent.click(addBtn);

    // While save is pending, indicator shows "Сохраняется"
    await waitFor(
      () => expect(screen.getByText(/Сохраняется|Saving/i)).toBeDefined(),
      { timeout: 2000 },
    );

    // Resolve the save
    resolveSet(undefined);

    // After save resolves, shows "Сохранено"
    await waitFor(
      () => expect(screen.getByText(/Сохранено|Saved/i)).toBeDefined(),
      { timeout: 2000 },
    );
  });
});

describe('DataSourcesCard — empty save', () => {
  it('8. saving after removing last source sends [] to IPC', async () => {
    const setSpy = setupMocks([SOURCE_DSM]);
    render(DataSourcesCard, { projectUuid: PROJECT_UUID });

    // Wait for dismiss button
    await waitFor(
      () => screen.getByRole('button', { name: /Убрать папку|Remove folder/i }),
      { timeout: 2000 },
    );
    const dismissBtn = screen.getByRole('button', { name: /Убрать папку|Remove folder/i });
    await fireEvent.click(dismissBtn);

    await waitFor(
      () => expect(setSpy).toHaveBeenCalledWith(
        'set_data_sources',
        expect.objectContaining({
          project_uuid: PROJECT_UUID,
          sources: [],
        }),
      ),
      { timeout: 2000 },
    );
  });
});

describe('DataSourcesCard — error state', () => {
  it('9. IPC error on getDataSources shows error alert with retry button', async () => {
    setupMocks([], { sourcesError: true });
    render(DataSourcesCard, { projectUuid: PROJECT_UUID });

    await waitFor(
      () => {
        expect(screen.getByRole('alert')).toBeDefined();
        expect(screen.getByRole('button', { name: /Повторить|Retry/i })).toBeDefined();
      },
      { timeout: 2000 },
    );
  });

  it('9b. clicking retry reloads sources and clears error', async () => {
    let callCount = 0;

    const projectsInvoke = vi.fn(async (cmd: string) => {
      if (cmd === 'list_projects') return PROJECT_LIST_SINGLE;
      throw new Error(cmd);
    });
    __setProjectsInvokeForTesting(
      projectsInvoke as Parameters<typeof __setProjectsInvokeForTesting>[0],
    );

    const clientInvoke = vi.fn(async (cmd: string) => {
      if (cmd === 'get_data_sources') {
        callCount++;
        if (callCount === 1) throw new Error('first fail');
        return { sources: [SOURCE_DSM] };
      }
      throw new Error(cmd);
    });
    __setInvokeForTesting(clientInvoke as InvokeFn);

    render(DataSourcesCard, { projectUuid: PROJECT_UUID });

    // Wait for error state
    await waitFor(
      () => screen.getByRole('button', { name: /Повторить|Retry/i }),
      { timeout: 2000 },
    );

    const retryBtn = screen.getByRole('button', { name: /Повторить|Retry/i });
    await fireEvent.click(retryBtn);

    // After retry success, error gone and source visible
    await waitFor(
      () => {
        expect(screen.queryByRole('alert')).toBeNull();
        expect(screen.getAllByRole('listitem').length).toBe(1);
      },
      { timeout: 2000 },
    );
  });
});

describe('DataSourcesCard — a11y', () => {
  it('10. dismiss buttons have aria-label containing the folder path', async () => {
    setupMocks([SOURCE_DSM]);
    render(DataSourcesCard, { projectUuid: PROJECT_UUID });

    await waitFor(
      () => screen.getByRole('button', { name: /Убрать папку C:\\Data\\DSM|Remove folder C:\\Data\\DSM/i }),
      { timeout: 2000 },
    );

    const btn = screen.getByRole('button', {
      name: /Убрать папку C:\\Data\\DSM|Remove folder C:\\Data\\DSM/i,
    });
    expect(btn).toBeDefined();
  });

  it('10b. project selector is accessible with role=combobox', async () => {
    setupMocks([], { projects: PROJECT_LIST_TWO });
    render(DataSourcesCard, {});

    await waitFor(
      () => {
        const selects = screen.getAllByRole('combobox');
        // At minimum the project dropdown
        expect(selects.length).toBeGreaterThanOrEqual(1);
      },
      { timeout: 2000 },
    );
  });
});
