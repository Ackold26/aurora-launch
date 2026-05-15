// Vitest setup — mock @tauri-apps/api/core invoke; global testing-library DOM.
import { vi } from 'vitest';

import { __setInvokeForTesting } from '../../src/lib/ipc/client';

// jsdom polyfills.
// 1) matchMedia: motion service prefersReducedMotion() relies on it. Mock к
//    return reduced=true so Svelte transitions short-circuit к no-op (avoids
//    element.animate() call which jsdom does not implement).
if (typeof window !== 'undefined' && typeof window.matchMedia !== 'function') {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: query.includes('prefers-reduced-motion: reduce'),
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}

// 2) Element.prototype.animate: Svelte 5 transitions invoke it for CSS
//    keyframes. jsdom lacks Web Animations API. Stub returns an Animation-
//    like object с finished/cancel methods so transitions complete без error.
if (typeof Element !== 'undefined' && typeof Element.prototype.animate !== 'function') {
  (Element.prototype as unknown as { animate: () => unknown }).animate = function () {
    return {
      cancel: () => {},
      finish: () => {},
      finished: Promise.resolve(),
      onfinish: null,
      pause: () => {},
      play: () => {},
      currentTime: 0,
      playState: 'finished',
    };
  };
}

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
