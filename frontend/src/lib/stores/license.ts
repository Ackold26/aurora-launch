// License store — central source for has_feature gates во всём UI.
// Phase 2.A: подключён к real sidecar get_license_status (раньше Rust stub).
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

/**
 * UX-4: empathetic human-readable message для каждого license state.
 * НЕ «No license. Features blocked» — а warm tone объясняющий что customer
 * может сделать. Используется в Settings → License panel и paywall modals.
 */
export function licenseUserMessage(status: LicenseStatus): string {
  switch (status.state) {
    case 'active':
      if (status.tier === 'dev_bypass') {
        return 'Разработческая сборка — все функции доступны без лицензии.';
      }
      return `Лицензия активна${status.tier ? ` (${status.tier})` : ''}. Все возможности тарифа открыты.`;
    case 'grace':
      return 'Связь с сервером Aurora временно недоступна. Работаете в офлайн-режиме — функции продолжают работать до 7 дней.';
    case 'expired':
      return 'Срок действия вашей лицензии истёк. Все данные сохранены — продлите подписку в личном кабинете, чтобы продолжить работу.';
    case 'invalid':
      return 'Не удалось проверить лицензию. Возможно, файл лицензии повреждён — обратитесь в поддержку Aurora.';
    case 'no_license':
      return 'Лицензия не найдена. Введите ключ активации в Настройках или запросите пробный период на auroraai.pro.';
    case 'degraded':
      return 'Локальная служба проверки лицензии недоступна. Перезапустите приложение или обратитесь в поддержку, если ошибка повторяется.';
    default:
      return status.detail || 'Состояние лицензии неизвестно.';
  }
}

/**
 * UX-4: проверка нужно ли показывать warning banner. True если state
 * требует внимания customer'a (expired / invalid / no_license / degraded).
 * Grace — НЕ warning (UX: customer должен спокойно работать в offline).
 */
export const needsAttention = derived(licenseStatus, ($s) =>
  ['expired', 'invalid', 'no_license', 'degraded'].includes($s.state)
);

/** Constants mirroring `aurora_launch.engines.license_validator` */
export const FEATURE_LAUNCH_PROXY_SINGLE = 'launch_proxy_single';
export const FEATURE_LAUNCH_PROXY_MULTI = 'launch_proxy_multi';
export const FEATURE_METHODOLOGY_CERT = 'report_pdf_methodology_certificate';
export const FEATURE_WHITE_LABEL = 'report_white_label';
export const FEATURE_TELEMETRY_EXPORT = 'telemetry_export';
