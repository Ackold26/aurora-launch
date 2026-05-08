// Active bundle store — tracks open bundle handle (D7 handle-based pattern).
import { writable, derived, get } from 'svelte/store';

import { ipc } from '$ipc/client';
import type { BundleHandleSummary } from '$ipc/client';

export const activeBundle = writable<BundleHandleSummary | null>(null);

export const isDirty = writable<boolean>(false);
export const lastSavedAt = writable<string | null>(null);

export const manifestSummary = derived(activeBundle, ($b) => $b?.manifest ?? null);
export const bundleRevision = derived(activeBundle, ($b) => $b?.revision ?? null);

export async function openBundleAt(path: string): Promise<BundleHandleSummary> {
  const handle = await ipc.openBundle(path);
  activeBundle.set(handle);
  isDirty.set(false);
  return handle;
}

export async function closeActiveBundle(): Promise<void> {
  const $b = get(activeBundle);
  if (!$b) return;
  await ipc.closeBundle($b.handle_id);
  activeBundle.set(null);
  isDirty.set(false);
  lastSavedAt.set(null);
}

export async function readEntry(entry: string): Promise<Uint8Array | null> {
  const $b = get(activeBundle);
  if (!$b) return null;
  const payload = await ipc.readBundleEntry($b.handle_id, entry);
  return base64ToUint8Array(payload.bytes_base64);
}

export async function readEntryJson<T = unknown>(entry: string): Promise<T | null> {
  const bytes = await readEntry(entry);
  if (!bytes) return null;
  const text = new TextDecoder('utf-8').decode(bytes);
  return JSON.parse(text) as T;
}

function base64ToUint8Array(b64: string): Uint8Array {
  const binary = typeof atob === 'function' ? atob(b64) : Buffer.from(b64, 'base64').toString('binary');
  const len = binary.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}
