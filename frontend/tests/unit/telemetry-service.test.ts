// Tests for src/lib/services/telemetry.ts (P-16).
//
// Covers:
//   1. opt-in false  → no IPC call
//   2. opt-in true   → IPC called with correct event_type
//   3. opt-in pending → events buffered, flushed after opt-in resolves true
//   4. opt-in pending → discard buffer if opt-in resolves false
//   5. PII fields stripped before send
//   6. Per-event schema — project_create carries granularity
//   7. Per-event schema — forecast_start carries horizon_weeks
//   8. Per-event schema — error_occurred carries stack_fingerprint + error_category
//   9. Async error during opt-in fetch → no crash, stays buffered
//  10. fingerprintStack + categoriseError helpers
//  11. Multiple events buffered while unknown, all flushed on opt-in true
//  12. Buffer cap at 64 — excess events dropped

import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { TelemetryEvent } from '../../src/lib/ipc/client';
import {
  track,
  initTelemetryInternal,
  notifyOptInChange,
  fingerprintStack,
  categoriseError,
  __setTelemetryIpcForTesting,
  __resetTelemetryStateForTesting,
} from '../../src/lib/services/telemetry';

// ─── Test helpers ─────────────────────────────────────────────────────────────

function makeIpcMocks(optIn: boolean | 'throw') {
  // Explicit generic ensures mock.calls[n][0] is typed as TelemetryEvent, not never.
  const logEvent = vi.fn<(event: TelemetryEvent) => Promise<number>>(async () => 1);
  const getTelemetryOptIn = vi.fn(async () => {
    if (optIn === 'throw') throw new Error('IPC unavailable');
    return optIn;
  });
  __setTelemetryIpcForTesting({ logEvent, getTelemetryOptIn });
  return { logEvent, getTelemetryOptIn };
}

beforeEach(() => {
  __resetTelemetryStateForTesting();
  vi.clearAllMocks();
});

// ─── 1. opt-in false → no IPC call ───────────────────────────────────────────

describe('track() when opt-in = false', () => {
  it('does not call logEvent when opt-in is false', async () => {
    const { logEvent } = makeIpcMocks(false);
    await initTelemetryInternal();

    track('app_open', { build_profile: 'dev' });

    // fire-and-forget — allow microtasks to settle
    await Promise.resolve();
    expect(logEvent).not.toHaveBeenCalled();
  });
});

// ─── 2. opt-in true → IPC called with correct event_type ─────────────────────

describe('track() when opt-in = true', () => {
  it('calls logEvent with correct event_type', async () => {
    const { logEvent } = makeIpcMocks(true);
    await initTelemetryInternal();

    track('app_open', { build_profile: 'release' });
    await Promise.resolve();

    expect(logEvent).toHaveBeenCalledOnce();
    const callArg = logEvent.mock.calls[0]?.[0];
    expect(callArg?.event_type).toBe('app_open');
  });

  it('logEvent payload matches the tracked payload', async () => {
    const { logEvent } = makeIpcMocks(true);
    await initTelemetryInternal();

    track('project_create', { granularity: 'weekly' });
    await Promise.resolve();

    const callArg = logEvent.mock.calls[0]?.[0];
    expect(callArg?.payload).toMatchObject({ granularity: 'weekly' });
  });
});

// ─── 3. opt-in pending → buffer, flush on true ────────────────────────────────

describe('buffering while opt-in is unknown', () => {
  it('buffers events before init, flushes on opt-in=true', async () => {
    const { logEvent } = makeIpcMocks(true);

    // Track BEFORE init — should buffer
    track('forecast_start', { horizon_weeks: 26 });
    track('project_create', { granularity: 'monthly' });

    expect(logEvent).not.toHaveBeenCalled();

    await initTelemetryInternal();
    // flush is async; allow microtasks
    await new Promise((r) => setTimeout(r, 0));

    expect(logEvent).toHaveBeenCalledTimes(2);
    const types = logEvent.mock.calls.map((c) => c[0]?.event_type);
    expect(types).toContain('forecast_start');
    expect(types).toContain('project_create');
  });
});

// ─── 4. opt-in pending → discard on false ─────────────────────────────────────

describe('buffer discard when opt-in resolves false', () => {
  it('discards buffered events when opt-in=false resolved', async () => {
    const { logEvent } = makeIpcMocks(false);

    track('app_open', { build_profile: 'dev' });
    track('settings_changed', { setting_key: 'theme' });

    await initTelemetryInternal();
    await new Promise((r) => setTimeout(r, 0));

    expect(logEvent).not.toHaveBeenCalled();
  });
});

// ─── 5. PII fields stripped before send ──────────────────────────────────────

describe('PII scrubbing', () => {
  it('strips brand_name, project_name, project_uuid, customer_email from payload', async () => {
    const { logEvent } = makeIpcMocks(true);
    await initTelemetryInternal();

    // Artificially cast to bypass TS type — test runtime scrubber
    track('settings_changed', {
      setting_key: 'theme',
      // @ts-expect-error intentional PII injection for scrubber test
      brand_name: 'Кагоцел',
      project_name: 'Secret Project',
      project_uuid: 'uuid-secret',
      customer_email: 'test@example.com',
    });
    await Promise.resolve();

    const callArg = logEvent.mock.calls[0]?.[0];
    expect(callArg?.payload).not.toHaveProperty('brand_name');
    expect(callArg?.payload).not.toHaveProperty('project_name');
    expect(callArg?.payload).not.toHaveProperty('project_uuid');
    expect(callArg?.payload).not.toHaveProperty('customer_email');
    // Non-PII field preserved
    expect(callArg?.payload).toHaveProperty('setting_key', 'theme');
  });
});

// ─── 6. Per-event schema — project_create ─────────────────────────────────────

describe('event schema: project_create', () => {
  it('carries granularity field', async () => {
    const { logEvent } = makeIpcMocks(true);
    await initTelemetryInternal();

    track('project_create', { granularity: 'weekly' });
    await Promise.resolve();

    const callArg = logEvent.mock.calls[0]?.[0];
    expect(callArg?.event_type).toBe('project_create');
    expect(callArg?.payload?.granularity).toBe('weekly');
  });
});

// ─── 7. Per-event schema — forecast_start ─────────────────────────────────────

describe('event schema: forecast_start', () => {
  it('carries horizon_weeks field', async () => {
    const { logEvent } = makeIpcMocks(true);
    await initTelemetryInternal();

    track('forecast_start', { horizon_weeks: 52 });
    await Promise.resolve();

    const callArg = logEvent.mock.calls[0]?.[0];
    expect(callArg?.event_type).toBe('forecast_start');
    expect(callArg?.payload?.horizon_weeks).toBe(52);
  });
});

// ─── 8. Per-event schema — error_occurred ─────────────────────────────────────

describe('event schema: error_occurred', () => {
  it('carries error_category and stack_fingerprint (8 hex chars)', async () => {
    const { logEvent } = makeIpcMocks(true);
    await initTelemetryInternal();

    track('error_occurred', {
      error_category: 'ipc_error',
      stack_fingerprint: fingerprintStack('Error: IPC failed\n  at invoke (client.ts:12)'),
    });
    await Promise.resolve();

    const callArg = logEvent.mock.calls[0]?.[0];
    expect(callArg?.payload?.error_category).toBe('ipc_error');
    const fp = callArg?.payload?.stack_fingerprint as string;
    expect(fp).toMatch(/^[0-9a-f]{8}$/);
  });
});

// ─── 9. Async error during opt-in fetch → no crash ────────────────────────────

describe('opt-in fetch failure', () => {
  it('does not crash and remains in buffered state when IPC throws', async () => {
    makeIpcMocks('throw');

    // Should not throw
    await expect(initTelemetryInternal()).resolves.toBeUndefined();

    // Subsequent track calls should still buffer (state remains unknown)
    expect(() => track('app_open', { build_profile: 'dev' })).not.toThrow();
  });
});

// ─── 10. fingerprintStack + categoriseError helpers ───────────────────────────

describe('fingerprintStack', () => {
  it('returns 8-char hex string', () => {
    const fp = fingerprintStack('Error: something\n  at foo.ts:1');
    expect(fp).toMatch(/^[0-9a-f]{8}$/);
  });

  it('returns 00000000 for undefined stack', () => {
    expect(fingerprintStack(undefined)).toBe('00000000');
  });

  it('deterministic — same input → same fingerprint', () => {
    const stack = 'Error: test\n  at bar.ts:5';
    expect(fingerprintStack(stack)).toBe(fingerprintStack(stack));
  });
});

describe('categoriseError', () => {
  it('TypeError → type_error', () => {
    expect(categoriseError(new TypeError('bad type'))).toBe('type_error');
  });

  it('IPC error message → ipc_error', () => {
    expect(categoriseError(new Error('IPC invoke failed'))).toBe('ipc_error');
  });

  it('non-Error → unknown_error', () => {
    expect(categoriseError('string error')).toBe('unknown_error');
  });

  it('generic Error → runtime_error', () => {
    expect(categoriseError(new Error('something went wrong'))).toBe('runtime_error');
  });
});

// ─── 11. Multiple events buffered, all flushed ────────────────────────────────

describe('buffer flush completeness', () => {
  it('all N buffered events are flushed in order when opt-in resolves true', async () => {
    const { logEvent } = makeIpcMocks(true);

    const events: Array<{ type: string; payload: object }> = [
      { type: 'app_open', payload: { build_profile: 'dev' } },
      { type: 'project_create', payload: { granularity: 'monthly' as const } },
      { type: 'forecast_start', payload: { horizon_weeks: 26 } },
    ];

    // @ts-expect-error mixed event types for buffer test
    events.forEach((ev) => track(ev.type, ev.payload));

    await initTelemetryInternal();
    await new Promise((r) => setTimeout(r, 0));

    expect(logEvent).toHaveBeenCalledTimes(3);
    const flushedTypes = logEvent.mock.calls.map((c) => c[0]?.event_type);
    expect(flushedTypes).toEqual(['app_open', 'project_create', 'forecast_start']);
  });
});

// ─── 12. Buffer cap at 64 ─────────────────────────────────────────────────────

describe('buffer overflow protection', () => {
  it('drops events beyond the 64-entry cap', async () => {
    const { logEvent } = makeIpcMocks(true);

    // Push 70 events while unknown
    for (let i = 0; i < 70; i++) {
      track('settings_changed', { setting_key: `key_${i}` });
    }

    await initTelemetryInternal();
    await new Promise((r) => setTimeout(r, 0));

    // Only 64 flushed — last 6 dropped
    expect(logEvent).toHaveBeenCalledTimes(64);
  });
});
