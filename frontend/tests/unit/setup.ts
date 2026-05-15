// Vitest setup — mock @tauri-apps/api/core invoke; global testing-library DOM.
import { vi } from 'vitest';

import { __setInvokeForTesting } from '../../src/lib/ipc/client';

// Initialise i18n with Russian locale so $_ works in component tests.
// Force 'ru' directly — jsdom navigator.language is 'en', which would
// otherwise pick English and break Russian-text assertions.
import { addMessages, init } from 'svelte-i18n';
import ruMessages from '../../src/lib/i18n/locales/ru.json';
import enMessages from '../../src/lib/i18n/locales/en.json';
addMessages('ru', ruMessages as Record<string, string>);
addMessages('en', enMessages as Record<string, string>);
init({ fallbackLocale: 'ru', initialLocale: 'ru' });

// Default mock invoke — tests override per-spec via .mockImplementation.
const defaultInvoke = vi.fn(async (cmd: string, args: unknown) => {
  console.warn(`Unmocked IPC call: ${cmd}`, args);
  throw new Error(`IPC '${cmd}' not mocked`);
});

__setInvokeForTesting(defaultInvoke as <T>(cmd: string, args?: Record<string, unknown>) => Promise<T>);

// Provide a global so per-test overrides work consistently.
(globalThis as unknown as { __auroraIpcMock: typeof defaultInvoke }).__auroraIpcMock =
  defaultInvoke;

// Reset between tests
import { afterEach } from 'vitest';
afterEach(() => {
  defaultInvoke.mockReset();
});
