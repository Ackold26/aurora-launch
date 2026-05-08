// Toast store — non-blocking notifications.
import { writable } from 'svelte/store';

export interface Toast {
  id: number;
  level: 'info' | 'success' | 'warning' | 'danger';
  title: string;
  body?: string;
  ttlMs?: number;
}

let nextId = 1;

export const toasts = writable<Toast[]>([]);

export function pushToast(t: Omit<Toast, 'id'>): number {
  const id = nextId++;
  const toast: Toast = { id, ttlMs: 4500, ...t };
  toasts.update((list) => [...list, toast]);
  if (toast.ttlMs && toast.ttlMs > 0) {
    setTimeout(() => dismissToast(id), toast.ttlMs);
  }
  return id;
}

export function dismissToast(id: number): void {
  toasts.update((list) => list.filter((t) => t.id !== id));
}
