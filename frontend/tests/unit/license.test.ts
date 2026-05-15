import { describe, expect, it, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';

import {
  licenseStatus,
  refreshLicense,
  hasFeatureSync,
  isUsable,
  isDevBypass
} from '../../src/lib/stores/license';

describe('license store', () => {
  beforeEach(() => {
    licenseStatus.set({
      state: 'no_license',
      tier: null,
      enabled_features: [],
      detail: '',
      is_offline_grace: false,
      valid_until: null
    });
    const mock = (globalThis as unknown as { __auroraIpcMock: ReturnType<typeof vi.fn> }).__auroraIpcMock;
    mock.mockReset();
  });

  it('refreshLicense calls current_license_status and updates store', async () => {
    const mock = (globalThis as unknown as { __auroraIpcMock: ReturnType<typeof vi.fn> }).__auroraIpcMock;
    mock.mockImplementationOnce(async () => ({
      state: 'active',
      tier: 'pro',
      enabled_features: ['launch_proxy_single', 'launch_proxy_multi'],
      detail: 'OK',
      is_offline_grace: false,
      valid_until: null
    }));
    const status = await refreshLicense();
    expect(status.state).toBe('active');
    expect(get(licenseStatus).tier).toBe('pro');
    expect(get(isUsable)).toBe(true);
    expect(get(isDevBypass)).toBe(false);
  });

  it('hasFeatureSync respects state and features', () => {
    licenseStatus.set({
      state: 'active',
      tier: 'pro',
      enabled_features: ['launch_proxy_single'],
      detail: '',
      is_offline_grace: false,
      valid_until: null
    });
    expect(hasFeatureSync('launch_proxy_single')).toBe(true);
    expect(hasFeatureSync('launch_proxy_multi')).toBe(false);
  });

  it('hasFeatureSync false when state is no_license', () => {
    licenseStatus.set({
      state: 'no_license',
      tier: null,
      enabled_features: ['launch_proxy_single'],
      detail: '',
      is_offline_grace: false,
      valid_until: null
    });
    expect(hasFeatureSync('launch_proxy_single')).toBe(false);
  });

  it('isDevBypass derived from tier', () => {
    licenseStatus.set({
      state: 'active',
      tier: 'dev_bypass',
      enabled_features: [],
      detail: '',
      is_offline_grace: false,
      valid_until: null
    });
    expect(get(isDevBypass)).toBe(true);
  });
});
