// Aurora Launch — Projects reactive store (Svelte 5 runes).
//
// Wraps ProjectDB IPC calls with $state reactive primitives.
// No legacy writable/derived — runes-only per INV-25 dual-mode UX pattern.
//
// Usage:
//   import { projectsStore } from '$lib/stores/projects.svelte';
//   projectsStore.refresh();           // load/reload project list
//   projectsStore.projects             // reactive ProjectSummary[]
//   projectsStore.loading              // boolean
//   projectsStore.error                // string | null

import {
  listProjects,
  createProject,
  deleteProject,
  getProject,
  loadSampleBundle as ipcLoadSampleBundle,
} from '$ipc/projects';
import type { ProjectSummary, ProjectDetail, SampleScenario, Granularity } from '$ipc/projects';

class ProjectsStore {
  projects = $state<ProjectSummary[]>([]);
  currentProject = $state<ProjectDetail | null>(null);
  loading = $state<boolean>(false);
  error = $state<string | null>(null);

  /** Reload the full project list from local DB. */
  async refresh(): Promise<void> {
    this.loading = true;
    this.error = null;
    try {
      this.projects = await listProjects();
    } catch (e) {
      this.error = e instanceof Error ? e.message : String(e);
    } finally {
      this.loading = false;
    }
  }

  /** Create a new project, then refresh the list. Returns the new project_uuid. */
  async create(name: string, granularity: Granularity = 'monthly'): Promise<string> {
    const result = await createProject(name, { granularity });
    await this.refresh();
    return result.project_uuid;
  }

  /**
   * Delete a project and refresh the list.
   * Clears currentProject if it matches the deleted uuid.
   */
  async remove(projectUuid: string): Promise<void> {
    await deleteProject(projectUuid);
    if (this.currentProject?.project_uuid === projectUuid) {
      this.currentProject = null;
    }
    await this.refresh();
  }

  /** Load project detail (includes full version history) into currentProject. */
  async open(projectUuid: string): Promise<void> {
    this.loading = true;
    this.error = null;
    try {
      this.currentProject = await getProject(projectUuid);
    } catch (e) {
      this.error = e instanceof Error ? e.message : String(e);
    } finally {
      this.loading = false;
    }
  }

  /**
   * Load a built-in sample bundle as a versioned project.
   * Returns the project_uuid of the created project.
   */
  async loadSample(scenario: SampleScenario): Promise<string> {
    this.loading = true;
    this.error = null;
    try {
      const result = await ipcLoadSampleBundle(scenario);
      await this.refresh();
      return result.project_uuid;
    } catch (e) {
      this.error = e instanceof Error ? e.message : String(e);
      throw e;
    } finally {
      this.loading = false;
    }
  }
}

export const projectsStore = new ProjectsStore();
