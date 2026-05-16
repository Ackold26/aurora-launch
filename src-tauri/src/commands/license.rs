//! License IPC. Phase 2.A — Rust shell wraps Python sidecar
//! get_license_status handler. SSOT для license state — Python
//! LaunchLicenseValidator (engines/license_validator.py), который читает
//! aurora_common.license.LicenseSDK (JWT + offline grace per ADR-002).
//!
//! C-3 closure: до Phase 2.A `current_license_status` был hardcoded stub —
//! production builds возвращали `no_license` всегда, dev возвращали bypass.
//! Customer не мог купить лицензию (proof не работал). Теперь Rust invoke
//! sidecar по реальному IPC; Python validate'ит лицензию через
//! aurora_common.license.LicenseSDK.
//!
//! HE-3 защита: Python-side LaunchLicenseValidator.from_env() refuses
//! BYPASS env если AURORA_BUILD_PROFILE != 'dev'. build.rs embed'ит
//! AURORA_BUILD_PROFILE при compile time — env var на runtime игнорируется.
//!
//! `is_dev_build` остаётся compile-time check — frontend использует для
//! show/hide dev-only affordances (test buttons, debug menus).

use std::sync::Arc;

use serde::{Deserialize, Serialize};
use tauri::State;

use crate::errors::AuroraResult;
use crate::sidecar::SidecarManager;

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct LicenseStatusPayload {
    pub state: String, // active | grace | expired | invalid | no_license | degraded
    pub tier: Option<String>,
    pub enabled_features: Vec<String>,
    pub detail: String,
    pub is_offline_grace: bool,
    pub valid_until: Option<String>,
}

/// Fallback payload когда sidecar недоступен (binary missing, terminated).
/// Fail-closed — UX-4 empathetic copy для customer чтобы понимал ситуацию.
fn sidecar_unavailable_payload() -> LicenseStatusPayload {
    LicenseStatusPayload {
        state: "degraded".into(),
        tier: None,
        enabled_features: vec![],
        detail: "Подключение к локальной службе Aurora недоступно. \
                 Перезапустите приложение или обратитесь в поддержку."
            .into(),
        is_offline_grace: false,
        valid_until: None,
    }
}

#[tauri::command]
pub async fn current_license_status(
    sidecar: State<'_, Arc<SidecarManager>>,
) -> AuroraResult<LicenseStatusPayload> {
    match sidecar
        .invoke::<LicenseStatusPayload>("get_license_status", serde_json::json!({}))
        .await
    {
        Ok(payload) => Ok(payload),
        Err(_) => Ok(sidecar_unavailable_payload()),
    }
}

#[tauri::command]
pub async fn has_feature(
    sidecar: State<'_, Arc<SidecarManager>>,
    feature: String,
) -> AuroraResult<bool> {
    // Дешевле: спросить sidecar напрямую — он уже умеет короткий
    // has_license_feature handler (avoid duplicating logic в Rust).
    #[derive(Deserialize)]
    struct HasFeatureResponse {
        granted: bool,
        #[allow(dead_code)]
        state: String,
    }

    match sidecar
        .invoke::<HasFeatureResponse>(
            "has_license_feature",
            serde_json::json!({ "feature": feature }),
        )
        .await
    {
        Ok(resp) => Ok(resp.granted),
        Err(_) => Ok(false), // fail-closed
    }
}

#[derive(Serialize, Deserialize, Debug)]
pub struct RequireFeatureError {
    pub feature: String,
    pub current_state: String,
    pub message: String,
}

#[tauri::command]
pub async fn require_feature(
    sidecar: State<'_, Arc<SidecarManager>>,
    feature: String,
) -> AuroraResult<()> {
    let granted = has_feature(sidecar.clone(), feature.clone()).await?;
    if granted {
        Ok(())
    } else {
        let status = current_license_status(sidecar).await?;
        Err(crate::errors::AuroraError::LicenseFeatureRequired {
            feature,
            current_state: status.state,
        })
    }
}

#[tauri::command]
pub async fn is_dev_build() -> AuroraResult<bool> {
    // Compile-time check — embedded build.rs через cargo:rustc-env. Cannot
    // be flipped at runtime (production install всегда возвращает false).
    Ok(crate::BUILD_PROFILE == "dev")
}
