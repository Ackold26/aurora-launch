// Unit tests for src/lib/stores/projects.svelte.ts
//
// Tests the Svelte 5 runes-based ProjectsStore class.
// IPC module is vi.mock'd so store logic is tested in isolation.

import { describe, it, expect, vi, beforeEach } from 'vitest';

// ─── Mock the IPC module ───────────────────────────────────────────────────────
// Must be hoisted above imports that pull in the store (vi.mock is hoisted
// at build time, but the factory runs before the module under test loads).

vi.mock('../../src/lib/ipc/projects', () => ({
  listProjects: vi.fn(),
  createProject: vi.fn(),
  deleteProject: vi.fn(),
  getProject: vi.fn(),
  loadSampleBundle: vi.fn(),
}));

// Import after mock registration.
import {
  listProjects,
  createProject,
  deleteProject,
  getProject,
  loadSampleBundle,
} from '../../src/lib/ipc/projects';
import type { ProjectSummary, ProjectDetail } from '../../src/lib/ipc/projects';

// Import the store class directly to get a fresh instance per test.
// We re-import the singleton for integration-style tests.
import { projectsStore } from '../../src/lib/stores/projects.svelte';

// Cast mocks for easy setup
const mockListProjects = vi.mocked(listProjects);
const mockCreateProject = vi.mocked(createProject);
const mockDeleteProject = vi.mocked(deleteProject);
const mockGetProject = vi.mocked(getProject);
const mockLoadSampleBundle = vi.mocked(loadSampleBundle);

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeProjectSummary(overrides: Partial<ProjectSummary> = {}): ProjectSummary {
  return {
    project_uuid: 'uuid-1',
    name: 'Test Project',
    created_at: '2026-01-01T00:00:00Z',
    last_modified: '2026-01-02T00:00:00Z',
    granularity: 'monthly',
    version_count: 1,
    current_version_id: 1,
    ...overrides,
  };
}

function makeProjectDetail(uuid = 'uuid-1'): ProjectDetail {
  return {
    project_uuid: uuid,
    name: 'Test Project',
    metadata: {},
    versions: [],
  };
}

// ─── Reset state between tests ────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks();
  // Reset store state
  projectsStore.projects = [];
  projectsStore.currentProject = null;
  projectsStore.loading = false;
  projectsStore.error = null;
});

// ─── refresh() ───────────────────────────────────────────────────────────────

describe('projectsStore.refresh()', () => {
  it('populates projects on success', async () => {
    const summaries = [makeProjectSummary(), makeProjectSummary({ project_uuid: 'uuid-2' })];
    mockListProjects.mockResolvedValueOnce(summaries);

    await projectsStore.refresh();

    expect(projectsStore.projects).toHaveLength(2);
    expect(projectsStore.projects[0]?.project_uuid).toBe('uuid-1');
    expect(projectsStore.loading).toBe(false);
    expect(projectsStore.error).toBeNull();
  });

  it('sets loading=true during fetch, false after', async () => {
    let capturedLoading: boolean | undefined;
    mockListProjects.mockImplementationOnce(async () => {
      capturedLoading = projectsStore.loading;
      return [];
    });

    await projectsStore.refresh();

    expect(capturedLoading).toBe(true);
    expect(projectsStore.loading).toBe(false);
  });

  it('sets error on IPC failure', async () => {
    mockListProjects.mockRejectedValueOnce(new Error('DB locked'));

    await projectsStore.refresh();

    expect(projectsStore.error).toBe('DB locked');
    expect(projectsStore.loading).toBe(false);
    // projects unchanged (empty from reset)
    expect(projectsStore.projects).toHaveLength(0);
  });

  it('resets error to null at start of a new refresh call', async () => {
    projectsStore.error = 'stale error';
    mockListProjects.mockResolvedValueOnce([]);

    await projectsStore.refresh();

    expect(projectsStore.error).toBeNull();
  });
});

// ─── create() ────────────────────────────────────────────────────────────────

describe('projectsStore.create()', () => {
  it('calls createProject then refresh, returns project_uuid', async () => {
    mockCreateProject.mockResolvedValueOnce({
      project_uuid: 'uuid-new',
      name: 'New',
      created_at: '2026-01-01T00:00:00Z',
    });
    mockListProjects.mockResolvedValueOnce([makeProjectSummary({ project_uuid: 'uuid-new' })]);

    const uuid = await projectsStore.create('New');

    expect(mockCreateProject).toHaveBeenCalledOnce();
    expect(mockListProjects).toHaveBeenCalledOnce();
    expect(uuid).toBe('uuid-new');
    expect(projectsStore.projects).toHaveLength(1);
  });

  it('defaults granularity to monthly', async () => {
    mockCreateProject.mockResolvedValueOnce({
      project_uuid: 'uuid-m',
      name: 'M',
      created_at: '2026-01-01T00:00:00Z',
    });
    mockListProjects.mockResolvedValueOnce([]);

    await projectsStore.create('M');

    expect(mockCreateProject).toHaveBeenCalledWith('M', { granularity: 'monthly' });
  });

  it('passes explicit granularity through to IPC', async () => {
    mockCreateProject.mockResolvedValueOnce({
      project_uuid: 'uuid-w',
      name: 'W',
      created_at: '2026-01-01T00:00:00Z',
    });
    mockListProjects.mockResolvedValueOnce([]);

    await projectsStore.create('W', 'weekly');

    expect(mockCreateProject).toHaveBeenCalledWith('W', { granularity: 'weekly' });
  });
});

// ─── remove() ────────────────────────────────────────────────────────────────

describe('projectsStore.remove()', () => {
  it('calls deleteProject then refresh', async () => {
    mockDeleteProject.mockResolvedValueOnce(undefined);
    mockListProjects.mockResolvedValueOnce([]);

    await projectsStore.remove('uuid-1');

    expect(mockDeleteProject).toHaveBeenCalledWith('uuid-1');
    expect(mockListProjects).toHaveBeenCalledOnce();
  });

  it('clears currentProject if it matches the removed uuid', async () => {
    projectsStore.currentProject = makeProjectDetail('uuid-1');
    mockDeleteProject.mockResolvedValueOnce(undefined);
    mockListProjects.mockResolvedValueOnce([]);

    await projectsStore.remove('uuid-1');

    expect(projectsStore.currentProject).toBeNull();
  });

  it('does NOT clear currentProject if uuid does not match', async () => {
    projectsStore.currentProject = makeProjectDetail('uuid-other');
    mockDeleteProject.mockResolvedValueOnce(undefined);
    mockListProjects.mockResolvedValueOnce([]);

    await projectsStore.remove('uuid-1');

    expect(projectsStore.currentProject).not.toBeNull();
    expect(projectsStore.currentProject?.project_uuid).toBe('uuid-other');
  });
});

// ─── open() ──────────────────────────────────────────────────────────────────

describe('projectsStore.open()', () => {
  it('fetches project detail and sets currentProject', async () => {
    const detail = makeProjectDetail('uuid-1');
    mockGetProject.mockResolvedValueOnce(detail);

    await projectsStore.open('uuid-1');

    expect(mockGetProject).toHaveBeenCalledWith('uuid-1');
    expect(projectsStore.currentProject?.project_uuid).toBe('uuid-1');
    expect(projectsStore.loading).toBe(false);
  });

  it('sets error on failure, does not change currentProject', async () => {
    projectsStore.currentProject = makeProjectDetail('uuid-prev');
    mockGetProject.mockRejectedValueOnce(new Error('not found'));

    await projectsStore.open('uuid-missing');

    expect(projectsStore.error).toBe('not found');
    expect(projectsStore.currentProject?.project_uuid).toBe('uuid-prev');
  });
});

// ─── loadSample() ────────────────────────────────────────────────────────────

describe('projectsStore.loadSample()', () => {
  it('calls loadSampleBundle then refresh, returns project_uuid', async () => {
    mockLoadSampleBundle.mockResolvedValueOnce({
      project_uuid: 'uuid-sample',
      version_id: 1,
      channels: ['TV', 'OOH'],
      n_periods: 24,
    });
    mockListProjects.mockResolvedValueOnce([
      makeProjectSummary({ project_uuid: 'uuid-sample', name: 'kagotsel_venarus' }),
    ]);

    const uuid = await projectsStore.loadSample('kagotsel_venarus');

    expect(mockLoadSampleBundle).toHaveBeenCalledWith('kagotsel_venarus');
    expect(mockListProjects).toHaveBeenCalledOnce();
    expect(uuid).toBe('uuid-sample');
    expect(projectsStore.projects).toHaveLength(1);
    expect(projectsStore.loading).toBe(false);
  });

  it('sets loading=true during sample load, false after', async () => {
    let capturedLoading: boolean | undefined;
    mockLoadSampleBundle.mockImplementationOnce(async () => {
      capturedLoading = projectsStore.loading;
      return { project_uuid: 'uuid-s', version_id: 1, channels: [], n_periods: 12 };
    });
    mockListProjects.mockResolvedValueOnce([]);

    await projectsStore.loadSample('venarus_baseline');

    expect(capturedLoading).toBe(true);
    expect(projectsStore.loading).toBe(false);
  });

  it('sets error and re-throws on failure', async () => {
    mockLoadSampleBundle.mockRejectedValueOnce(new Error('bundle missing'));

    await expect(projectsStore.loadSample('multi_proxy')).rejects.toThrow('bundle missing');
    expect(projectsStore.error).toBe('bundle missing');
    expect(projectsStore.loading).toBe(false);
  });
});
