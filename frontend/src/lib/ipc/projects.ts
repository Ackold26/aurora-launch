// Aurora Launch — ProjectDB + LaunchOrchestrator IPC shim.
//
// Wraps 8 new Tauri commands:
//   create_project / list_projects / get_project / delete_project
//   list_versions / compare_versions
//   import_aurora_bundle / load_sample_bundle
//
// Uses the same swappable invoke injected by __setInvokeForTesting in client.ts,
// so the global Vitest mock (tests/unit/setup.ts) covers these functions for free.

import { type InvokeFn } from './client';
import { invoke as tauriInvoke } from '@tauri-apps/api/core';

// Swappable reference — overridden in tests via __setProjectsInvokeForTesting.
let invoke: InvokeFn = tauriInvoke as InvokeFn;

/** For Vitest tests only — overrides the invoke function for this module. */
export function __setProjectsInvokeForTesting(fn: InvokeFn): void {
  invoke = fn;
}

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ProjectSummary {
  project_uuid: string;
  name: string;
  created_at: string;
  last_modified: string;
  granularity: 'monthly' | 'weekly';
  version_count: number;
  current_version_id: number | null;
}

export interface VersionSummary {
  version_id: number;
  revision: number;
  label: string | null;
  decision_note: string | null;
  created_at: string;
  composite_bundle_hash: string | null;
  file_count: number;
}

export interface ProjectDetail {
  project_uuid: string;
  name: string;
  metadata: Record<string, unknown>;
  versions: VersionSummary[];
}

export interface VersionDiff {
  files_only_in_a: string[];
  files_only_in_b: string[];
  files_changed: string[];
  files_unchanged: string[];
}

export interface ImportBundleResult {
  project_uuid: string;
  version_id: number;
}

export interface SampleBundleResult {
  project_uuid: string;
  version_id: number;
  channels: string[];
  n_periods: number;
}

export interface CreateProjectResult {
  project_uuid: string;
  name: string;
  created_at: string;
}

export type Granularity = 'monthly' | 'weekly';

export type SampleScenario = 'kagotsel_venarus' | 'venarus_baseline' | 'multi_proxy';

// ─── Service functions ────────────────────────────────────────────────────────

/** Create a new empty project. Defaults: granularity = 'monthly', metadata = {}. */
export async function createProject(
  name: string,
  options: { granularity?: Granularity; metadata?: Record<string, unknown> } = {}
): Promise<CreateProjectResult> {
  return invoke<CreateProjectResult>('create_project', {
    name,
    granularity: options.granularity ?? 'monthly',
    metadata: options.metadata ?? {},
  });
}

/** List all projects in the local DB, ordered by last_modified desc. */
export async function listProjects(): Promise<ProjectSummary[]> {
  return invoke<ProjectSummary[]>('list_projects');
}

/** Fetch full project detail including version history. */
export async function getProject(projectUuid: string): Promise<ProjectDetail> {
  return invoke<ProjectDetail>('get_project', { projectUuid });
}

/** Permanently delete a project and all its versions. */
export async function deleteProject(projectUuid: string): Promise<void> {
  return invoke<void>('delete_project', { projectUuid });
}

/** List versions for a project, ordered by revision asc. */
export async function listVersions(projectUuid: string): Promise<VersionSummary[]> {
  return invoke<VersionSummary[]>('list_versions', { projectUuid });
}

/** Diff two versions by version_id — returns file-level change sets. */
export async function compareVersions(
  versionIdA: number,
  versionIdB: number
): Promise<VersionDiff> {
  return invoke<VersionDiff>('compare_versions', { versionIdA, versionIdB });
}

/** Import an .aurora bundle from disk, creating/versioning a project. */
export async function importAuroraBundle(
  bundlePath: string,
  options: { projectName?: string; granularity?: Granularity } = {}
): Promise<ImportBundleResult> {
  return invoke<ImportBundleResult>('import_aurora_bundle', {
    bundlePath,
    projectName: options.projectName,
    granularity: options.granularity,
  });
}

/** Load a built-in sample dataset as a versioned project. */
export async function loadSampleBundle(scenario: SampleScenario): Promise<SampleBundleResult> {
  return invoke<SampleBundleResult>('load_sample_bundle', { scenario });
}
