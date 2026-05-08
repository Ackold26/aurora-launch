//! Build info IPC — exposes compile-time constants to frontend.
//!
//! Used by:
//! - Settings → About panel (display version, build profile, build date)
//! - License validator UI (warning banner if dev build)
//! - Audit footer (performance metrics row includes build version)

use serde::{Deserialize, Serialize};

use crate::errors::AuroraResult;

#[derive(Serialize, Deserialize, Debug)]
pub struct BuildInfo {
    pub version: String,
    pub build_profile: String,
    pub is_dev_build: bool,
    pub rust_version: String,
    pub cargo_pkg_name: String,
}

#[tauri::command]
pub async fn get_build_info() -> AuroraResult<BuildInfo> {
    Ok(BuildInfo {
        version: env!("CARGO_PKG_VERSION").into(),
        build_profile: crate::BUILD_PROFILE.into(),
        is_dev_build: crate::BUILD_PROFILE == "dev",
        rust_version: option_env!("RUSTC_VERSION")
            .unwrap_or("unknown")
            .into(),
        cargo_pkg_name: env!("CARGO_PKG_NAME").into(),
    })
}
