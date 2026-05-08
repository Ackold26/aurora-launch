//! Aurora Launch Tauri backend — IPC commands library.
//!
//! All IPC commands return `Result<T, AuroraError>` where `AuroraError` is
//! a structured error type that the frontend deserializes. No `unwrap()` /
//! `panic!()` in command handlers — those would crash the webview without
//! a clean diagnostic.
//!
//! Commands are organised into modules per feature area:
//! - `bundle` — open / save / inspect `.aurora` bundles (handle-based, lazy)
//! - `similarity` — compute similarity dimensions (sub-100ms warm)
//! - `forecast` — kick off forecast generation, stream progress
//! - `methodology_cert` — verify Ed25519 signatures (Block 2C)
//! - `license` — current license status, feature gate checks
//! - `telemetry` — local SQLite buffer для opt-in upload
//! - `feedback` — capture screenshot + log для in-app feedback channel
//! - `audit_log` — emit audit events visible в History panel

use std::sync::Mutex;

mod commands;
mod errors;
mod state;

use errors::AuroraError;
use state::AppState;

/// Aurora Launch build profile, embedded at compile time via build.rs.
/// `"production"` (default for releases) или `"dev"`. License bypass code
/// path is ELIMINATED at compile time when this == "production".
pub const BUILD_PROFILE: &str = env!("AURORA_BUILD_PROFILE");

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    env_logger::init();
    log::info!(
        "aurora_launch starting — build_profile={}, version={}",
        BUILD_PROFILE,
        env!("CARGO_PKG_VERSION")
    );

    tauri::Builder::default()
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_os::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(AppState::default())
        .invoke_handler(tauri::generate_handler![
            // bundle commands
            commands::bundle::open_bundle,
            commands::bundle::close_bundle,
            commands::bundle::list_bundle_entries,
            commands::bundle::read_bundle_entry,
            commands::bundle::get_manifest,
            commands::bundle::save_bundle,
            // similarity commands
            commands::similarity::compute_similarity_dimensions,
            commands::similarity::aggregate_score,
            // forecast commands
            commands::forecast::start_forecast,
            commands::forecast::cancel_forecast,
            commands::forecast::get_forecast_status,
            // methodology_cert commands (Block 2C)
            commands::methodology_cert::verify_bundle_signature,
            commands::methodology_cert::generate_local_dev_signature,
            // license commands
            commands::license::current_license_status,
            commands::license::has_feature,
            commands::license::require_feature,
            commands::license::is_dev_build,
            // telemetry commands (Block 2F — local-only buffer)
            commands::telemetry::log_event,
            commands::telemetry::list_events,
            commands::telemetry::get_telemetry_opt_in,
            commands::telemetry::set_telemetry_opt_in,
            // feedback commands (Block 2F — Cmd+Shift+F)
            commands::feedback::capture_feedback,
            commands::feedback::list_pending_feedback,
            // audit log (Block 2F — UI consumer)
            commands::audit_log::list_audit_entries,
            // build info
            commands::build_info::get_build_info,
        ])
        .setup(|app| {
            // Initialize local SQLite for telemetry + audit log
            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                if let Err(e) = state::init_local_storage(&app_handle).await {
                    log::error!("Failed to initialize local storage: {e}");
                }
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running aurora-launch");
}
