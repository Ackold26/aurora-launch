// License store — central source for has_feature gates во всём UI.
import { writable, derived, get } from 'svelte/store';

import { ipc } from '$ipc/client';
import type { LicenseStatus } from '$ipc/client';

const NULL_STATUS: LicenseStatus = {
  state: 'no_license',
  tier: null,
  enabled_features: [],
  detail: 'License not yet loaded',
  is_offline_grace: false,
  valid_until: null
};

export const licenseStatus = writable<LicenseStatus>(NULL_STATUS);
export const licenseLoading = writable<boolean>(false);

export const isUsable = derived(licenseStatus, ($s) =>
  $s.state === 'active' || $s.state === 'grace'
);

export const isDevBypass = derived(licenseStatus, ($s) => $s.tier === 'dev_bypass');

export async function refreshLicense(): Promise<LicenseStatus> {
  licenseLoading.set(true);
  try {
    const status = await ipc.currentLicenseStatus();
    licenseStatus.set(status);
    return status;
  } finally {
    licenseLoading.set(false);
  }
}

export function hasFeatureSync(feature: string): boolean {
  const $status = get(licenseStatus);
  const usable = $status.state === 'active' || $status.state === 'grace';
  return usable && $status.enabled_features.includes(feature);
}

/** Constants mirroring `aurora_launch.engines.license_validator` */
export const FEATURE_LAUNCH_PROXY_SINGLE = 'launch_proxy_single';
export const FEATURE_LAUNCH_PROXY_MULTI = 'launch_proxy_multi';
export const FEATURE_METHODOLOGY_CERT = 'report_pdf_methodology_certificate';
export const FEATURE_WHITE_LABEL = 'report_white_label';
export const FEATURE_TELEMETRY_EXPORT = 'telemetry_export';
