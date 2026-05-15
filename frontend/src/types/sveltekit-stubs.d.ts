/**
 * Augment @histoire/plugin-svelte to export Hst as a concrete value.
 *
 * The histoire Svelte plugin resolves <Hst.Story> / <Hst.Variant> at runtime
 * via a Vite virtual module. svelte-check sees only the type declaration where
 * Hst is an interface (not a value), causing "type cannot be used as value"
 * errors. This ambient override re-declares Hst as a const so story files
 * type-check correctly.
 */
declare module '@histoire/plugin-svelte' {
  import type { ComponentType, SvelteComponent } from 'svelte';

  interface HstComponents {
    Story: ComponentType<SvelteComponent & { title?: string; group?: string }>;
    Variant: ComponentType<SvelteComponent & { title?: string }>;
    [key: string]: ComponentType<SvelteComponent>;
  }

  export const Hst: HstComponents;
  export function defineSetupSvelte(handler: (api: { app: unknown }) => Promise<void> | void): typeof handler;
}

/**
 * Type stubs for SvelteKit virtual modules used in this Tauri app.
 *
 * This project uses Vite (not SvelteKit server), so the $app/* modules are
 * provided as runtime shims (see vite.config.ts aliases). These declarations
 * let svelte-check resolve types without requiring the full @sveltejs/kit
 * package, which would pull in unnecessary server-side dependencies.
 */

declare module '$app/navigation' {
  /**
   * Navigate to a new URL programmatically.
   * In this Tauri app the runtime shim delegates to window.location.
   */
  // Audit M-3 (этап 1.7): добавлены state + invalidateAll из SvelteKit 2.x API
  // чтобы код использующий эти опции получал корректный type-check.
  export function goto(
    url: string,
    opts?: {
      replaceState?: boolean;
      noScroll?: boolean;
      keepFocus?: boolean;
      state?: Record<string, unknown>;
      invalidateAll?: boolean;
    }
  ): Promise<void>;

  export function preloadData(url: string): Promise<void>;
  export function preloadCode(url: string): Promise<void>;
  export function invalidate(url: string | URL | ((url: URL) => boolean)): Promise<void>;
  export function invalidateAll(): Promise<void>;
  export function afterNavigate(fn: (nav: { from: URL | null; to: URL }) => void): void;
  export function beforeNavigate(fn: (nav: { from: URL; to: URL | null; cancel: () => void }) => void): void;
}

declare module '$app/state' {
  import type { Readable } from 'svelte/store';

  interface PageState {
    /** Current page URL */
    url: URL;
    /** Route params extracted from the URL pattern */
    params: Record<string, string>;
    /** Page data returned by load functions */
    data: Record<string, unknown>;
    /** Page status code */
    status: number;
    /** Page error, if any */
    error: App.Error | null;
    /** Current route object */
    route: { id: string | null };
  }

  /** Reactive page state object (SvelteKit compatibility shim). */
  export const page: PageState;
}

declare module '$app/environment' {
  export const browser: boolean;
  export const dev: boolean;
  export const building: boolean;
  export const version: string;
}

declare module '$app/stores' {
  import type { Readable } from 'svelte/store';

  interface Page {
    url: URL;
    params: Record<string, string>;
    data: Record<string, unknown>;
    status: number;
    error: App.Error | null;
    route: { id: string | null };
  }

  export const page: Readable<Page>;
  export const navigating: Readable<{ from: URL | null; to: URL } | null>;
  export const updated: Readable<boolean> & { check(): Promise<boolean> };
}
