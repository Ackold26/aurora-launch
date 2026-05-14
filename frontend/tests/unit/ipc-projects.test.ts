// Unit tests for src/lib/ipc/projects.ts
//
// Verifies that each service function calls invoke with the correct command
// name and argument shape. Uses the module-level __setProjectsInvokeForTesting
// hook so this test is independent of the global IPC mock.

import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { Mock } from 'vitest';

import {
  __setProjectsInvokeForTesting,
  createProject,
  listProjects,
  getProject,
  deleteProject,
  listVersions,
  compareVersions,
  importAuroraBundle,
  loadSampleBundle,
} from '../../src/lib/ipc/projects';
import type {
  ProjectSummary,
  ProjectDetail,
  VersionSummary,
  VersionDiff,
  ImportBundleResult,
  SampleBundleResult,
  CreateProjectResult,
} from '../../src/lib/ipc/projects';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeMockInvoke(): Mock {
  const fn = vi.fn();
  __setProjectsInvokeForTesting(fn as Parameters<typeof __setProjectsInvokeForTesting>[0]);
  return fn;
}

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

function makeVersionSummary(overrides: Partial<VersionSummary> = {}): VersionSummary {
  return {
    version_id: 1,
    revision: 0,
    label: null,
    decision_note: null,
    created_at: '2026-01-01T00:00:00Z',
    composite_bundle_hash: 'abc123',
    file_count: 3,
    ...overrides,
  };
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('ipc/projects — createProject', () => {
  let mockInvoke: Mock;
  beforeEach(() => {
    mockInvoke = makeMockInvoke();
  });

  it('calls create_project with name, default granularity and empty metadata', async () => {
    const result: CreateProjectResult = {
      project_uuid: 'uuid-new',
      name: 'My Project',
      created_at: '2026-01-01T00:00:00Z',
    };
    mockInvoke.mockResolvedValueOnce(result);

    const out = await createProject('My Project');

    expect(mockInvoke).toHaveBeenCalledOnce();
    expect(mockInvoke).toHaveBeenCalledWith('create_project', {
      name: 'My Project',
      granularity: 'monthly',
      metadata: {},
    });
    expect(out.project_uuid).toBe('uuid-new');
  });

  it('passes explicit granularity and metadata when provided', async () => {
    mockInvoke.mockResolvedValueOnce({
      project_uuid: 'uuid-w',
      name: 'Weekly',
      created_at: '2026-01-01T00:00:00Z',
    });

    await createProject('Weekly', {
      granularity: 'weekly',
      metadata: { source: 'pilot' },
    });

    expect(mockInvoke).toHaveBeenCalledWith('create_project', {
      name: 'Weekly',
      granularity: 'weekly',
      metadata: { source: 'pilot' },
    });
  });

  it('default granularity is monthly (normalisation check)', async () => {
    mockInvoke.mockResolvedValueOnce({
      project_uuid: 'uuid-m',
      name: 'M',
      created_at: '2026-01-01T00:00:00Z',
    });

    await createProject('M');

    const [, args] = mockInvoke.mock.calls[0] as [string, Record<string, unknown>];
    expect(args['granularity']).toBe('monthly');
  });
});

describe('ipc/projects — listProjects', () => {
  let mockInvoke: Mock;
  beforeEach(() => {
    mockInvoke = makeMockInvoke();
  });

  it('calls list_projects with no args and returns array', async () => {
    const projects = [makeProjectSummary(), makeProjectSummary({ project_uuid: 'uuid-2' })];
    mockInvoke.mockResolvedValueOnce(projects);

    const result = await listProjects();

    expect(mockInvoke).toHaveBeenCalledOnce();
    // listProjects passes no second arg — invoke is called with cmd only
    expect(mockInvoke.mock.calls[0]?.[0]).toBe('list_projects');
    expect(mockInvoke.mock.calls[0]).toHaveLength(1);
    expect(result).toHaveLength(2);
    expect(result[0]?.project_uuid).toBe('uuid-1');
  });

  it('returns empty array when DB has no projects', async () => {
    mockInvoke.mockResolvedValueOnce([]);
    const result = await listProjects();
    expect(result).toEqual([]);
  });
});

describe('ipc/projects — getProject', () => {
  let mockInvoke: Mock;
  beforeEach(() => {
    mockInvoke = makeMockInvoke();
  });

  it('calls get_project with projectUuid', async () => {
    const detail: ProjectDetail = {
      project_uuid: 'uuid-1',
      name: 'Detail',
      metadata: {},
      versions: [makeVersionSummary()],
    };
    mockInvoke.mockResolvedValueOnce(detail);

    const result = await getProject('uuid-1');

    expect(mockInvoke).toHaveBeenCalledWith('get_project', { projectUuid: 'uuid-1' });
    expect(result.versions).toHaveLength(1);
  });
});

describe('ipc/projects — deleteProject', () => {
  let mockInvoke: Mock;
  beforeEach(() => {
    mockInvoke = makeMockInvoke();
  });

  it('calls delete_project with projectUuid', async () => {
    mockInvoke.mockResolvedValueOnce(undefined);

    await deleteProject('uuid-del');

    expect(mockInvoke).toHaveBeenCalledWith('delete_project', { projectUuid: 'uuid-del' });
  });

  it('resolves void on success', async () => {
    mockInvoke.mockResolvedValueOnce(undefined);
    const result = await deleteProject('uuid-del');
    expect(result).toBeUndefined();
  });
});

describe('ipc/projects — listVersions', () => {
  let mockInvoke: Mock;
  beforeEach(() => {
    mockInvoke = makeMockInvoke();
  });

  it('calls list_versions with projectUuid', async () => {
    const versions = [makeVersionSummary(), makeVersionSummary({ version_id: 2, revision: 1 })];
    mockInvoke.mockResolvedValueOnce(versions);

    const result = await listVersions('uuid-1');

    expect(mockInvoke).toHaveBeenCalledWith('list_versions', { projectUuid: 'uuid-1' });
    expect(result).toHaveLength(2);
    expect(result[1]?.revision).toBe(1);
  });
});

describe('ipc/projects — compareVersions', () => {
  let mockInvoke: Mock;
  beforeEach(() => {
    mockInvoke = makeMockInvoke();
  });

  it('calls compare_versions with versionIdA and versionIdB', async () => {
    const diff: VersionDiff = {
      files_only_in_a: ['data.csv'],
      files_only_in_b: [],
      files_changed: ['manifest.json'],
      files_unchanged: ['schema.json'],
    };
    mockInvoke.mockResolvedValueOnce(diff);

    const result = await compareVersions(1, 2);

    expect(mockInvoke).toHaveBeenCalledWith('compare_versions', {
      versionIdA: 1,
      versionIdB: 2,
    });
    expect(result.files_changed).toContain('manifest.json');
  });
});

describe('ipc/projects — importAuroraBundle', () => {
  let mockInvoke: Mock;
  beforeEach(() => {
    mockInvoke = makeMockInvoke();
  });

  it('calls import_aurora_bundle with bundlePath and no optional args when omitted', async () => {
    const res: ImportBundleResult = { project_uuid: 'uuid-imp', version_id: 1 };
    mockInvoke.mockResolvedValueOnce(res);

    const result = await importAuroraBundle('/path/to/file.aurora');

    expect(mockInvoke).toHaveBeenCalledWith('import_aurora_bundle', {
      bundlePath: '/path/to/file.aurora',
      projectName: undefined,
      granularity: undefined,
    });
    expect(result.project_uuid).toBe('uuid-imp');
  });

  it('passes optional projectName and granularity', async () => {
    mockInvoke.mockResolvedValueOnce({ project_uuid: 'uuid-imp2', version_id: 1 });

    await importAuroraBundle('/path/f.aurora', {
      projectName: 'Imported',
      granularity: 'weekly',
    });

    expect(mockInvoke).toHaveBeenCalledWith('import_aurora_bundle', {
      bundlePath: '/path/f.aurora',
      projectName: 'Imported',
      granularity: 'weekly',
    });
  });
});

describe('ipc/projects — loadSampleBundle', () => {
  let mockInvoke: Mock;
  beforeEach(() => {
    mockInvoke = makeMockInvoke();
  });

  it('calls load_sample_bundle with scenario', async () => {
    const res: SampleBundleResult = {
      project_uuid: 'uuid-sample',
      version_id: 1,
      channels: ['TV', 'Digital'],
      n_periods: 24,
    };
    mockInvoke.mockResolvedValueOnce(res);

    const result = await loadSampleBundle('kagotsel_venarus');

    expect(mockInvoke).toHaveBeenCalledWith('load_sample_bundle', {
      scenario: 'kagotsel_venarus',
    });
    expect(result.channels).toContain('TV');
    expect(result.n_periods).toBe(24);
  });

  it('supports all three sample scenarios', async () => {
    const scenarios = ['kagotsel_venarus', 'venarus_baseline', 'multi_proxy'] as const;
    for (const scenario of scenarios) {
      mockInvoke.mockResolvedValueOnce({
        project_uuid: 'uuid-s',
        version_id: 1,
        channels: [],
        n_periods: 12,
      });
      await loadSampleBundle(scenario);
      expect(mockInvoke).toHaveBeenLastCalledWith('load_sample_bundle', { scenario });
    }
  });
});
