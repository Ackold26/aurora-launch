import { describe, expect, it, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';

import { activeBundle, openBundleAt, closeActiveBundle, readEntryJson } from '../../src/lib/stores/bundle';

describe('bundle store', () => {
  beforeEach(() => {
    const mock = (globalThis as { __auroraIpcMock: ReturnType<typeof vi.fn> }).__auroraIpcMock;
    mock.mockReset();
    activeBundle.set(null);
  });

  it('openBundleAt sets activeBundle', async () => {
    const mock = (globalThis as { __auroraIpcMock: ReturnType<typeof vi.fn> }).__auroraIpcMock;
    mock.mockImplementationOnce(async () => ({
      handle_id: 'h1',
      source_format: 'zip',
      size_bytes: 1234,
      revision: 0,
      manifest: { project_id: 'p', revision: 0, files: {} }
    }));
    const handle = await openBundleAt('/tmp/foo.aurora');
    expect(handle.handle_id).toBe('h1');
    expect(get(activeBundle)?.handle_id).toBe('h1');
  });

  it('closeActiveBundle calls IPC and clears store', async () => {
    activeBundle.set({
      handle_id: 'h1',
      source_format: 'zip',
      size_bytes: 1234,
      revision: 0,
      manifest: {} as never
    });
    const mock = (globalThis as { __auroraIpcMock: ReturnType<typeof vi.fn> }).__auroraIpcMock;
    mock.mockImplementationOnce(async () => undefined);
    await closeActiveBundle();
    expect(get(activeBundle)).toBeNull();
    expect(mock).toHaveBeenCalledWith('close_bundle', { handleId: 'h1' });
  });

  it('readEntryJson returns null when no active bundle', async () => {
    activeBundle.set(null);
    const result = await readEntryJson('foo.json');
    expect(result).toBeNull();
  });

  it('readEntryJson decodes base64 and parses JSON', async () => {
    activeBundle.set({
      handle_id: 'h1',
      source_format: 'zip',
      size_bytes: 100,
      revision: 0,
      manifest: {} as never
    });
    const mock = (globalThis as { __auroraIpcMock: ReturnType<typeof vi.fn> }).__auroraIpcMock;
    const json = JSON.stringify({ k: 1 });
    const b64 = btoa(json);
    mock.mockImplementationOnce(async () => ({
      entry: 'data.json',
      bytes_base64: b64,
      size_bytes: json.length,
      sha256_hex: 'X'.repeat(64)
    }));
    const result = await readEntryJson<{ k: number }>('data.json');
    expect(result).toEqual({ k: 1 });
  });
});
