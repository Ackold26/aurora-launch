//! License IPC. Block 2 contract — exposes Python-side LaunchLicenseValidator
//! state to UI; Block 4 wires real Python sidecar. For now stubs reflect the
//! BUILD_PROFILE gate from Block 1D B1 fix.
//!
//! Crucial invariant: the `is_dev_build` boolean reflects the **compile-time**
//! `AURORA_BUILD_PROFILE` const, NOT a runtime env var. Frontend can rely on
//! this to hide dev-only UI affordances в production builds.

use serde::{Deserialize, Serialize};

use crate::errors::AuroraResult;

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct LicenseStatusPayload {
    pub state: String, // active | grace | expired | invalid | no_license | degraded
    pub tier: Option<String>,
    pub enabled_features: Vec<String>,
    pub detail: String,
    pub is_offline_grace: bool,
    pub valid_until: Option<String>,
}

#[tauri::command]
pub async fn current_license_status() -> AuroraResult<LicenseStatusPayload> {
    // Block 2 stub: returns degraded by default; Block 4 invokes Python
    // LaunchLicenseValidator.from_env().current_status() через sidecar.
    let is_dev = crate::BUILD_PROFILE == "dev";
    if is_dev {
        Ok(LicenseStatusPayload {
            state: "active".into(),
            tier: Some("dev_bypass".into()),
            enabled_features: vec![
                "launch_proxy_single".into(),
                "launch_proxy_multi".into(),
                "report_pdf_methodology_certificate".into(),
                "report_white_label".into(),
            ],
            detail: "DEV BUILD — license bypass active (AURORA_BUILD_PROFILE=dev)".into(),
            is_offline_grace: false,
            valid_until: None,
        })
    } else {
        Ok(LicenseStatusPayload {
            state: "no_license".into(),
            tier: None,
            enabled_features: vec![],
            detail: "Block 4 wires real LicenseSDK via Python sidecar".into(),
            is_offline_grace: false,
            valid_until: None,
        })
    }
}

#[tauri::command]
pub async fn has_feature(feature: String) -> AuroraResult<bool> {
    let status = current_license_status().await?;
    let active_or_grace = matches!(status.state.as_str(), "active" | "grace");
    Ok(active_or_grace && status.enabled_features.contains(&feature))
}

#[derive(Serialize, Deserialize, Debug)]
pub struct RequireFeatureError {
    pub feature: String,
    pub current_state: String,
    pub message: String,
}

#[tauri::command]
pub async fn require_feature(feature: String) -> AuroraResult<()> {
    let granted = has_feature(feature.clone()).await?;
    if granted {
        Ok(())
    } else {
        let status = current_license_status().await?;
        Err(crate::errors::AuroraError::LicenseFeatureRequired {
            feature,
            current_state: status.state,
        })
    }
}

#[tauri::command]
pub async fn is_dev_build() -> AuroraResult<bool> {
    Ok(crate::BUILD_PROFILE == "dev")
}
