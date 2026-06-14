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

use tauri::{Emitter, Manager};  // Manager: manage()/try_state(); Emitter: app.emit()

mod commands;
mod errors;
mod panic_handler;
mod paths;
mod sidecar;
mod state;

use errors::AuroraError;
use state::AppState;

/// Aurora Launch build profile, embedded at compile time via build.rs.
/// `"production"` (default for releases) или `"dev"`. License bypass code
/// path is ELIMINATED at compile time when this == "production".
pub const BUILD_PROFILE: &str = env!("AURORA_BUILD_PROFILE");

// ============== Auto-updater commands (fleet checksum updater) ==============
// Thin Tauri wrappers over `aurora_fleet::updater` (Core SSOT — cutover
// 2026-06-14, was the app-local `commands/updater.rs`). Host couplings are
// supplied as closures: download progress → `emit('update-progress')`; pre-exit
// → sidecar shutdown. The updater queries with product = CARGO_PKG_NAME
// (`aurora-launch`, fleet convention — matches the `app_versions` row + GH-Pages
// folder, NOT the short licensing product `launch`). The fixed prerelease-aware
// `is_newer` comes from the crate. Frontend contract unchanged:
//   invoke('check_update')                       -> VersionInfo | null
//   invoke('download_update', {url, checksum})   -> installer path (verifies checksum)
//   listen('update-progress', e => e.payload.percent)
//   invoke('apply_update', {installerPath})      -> launches installer, exits

/// Map a fleet updater error (`[UP-xxx] …`) to Launch's structured `UpdateFailed`
/// so the frontend banner keeps its `{ code, message }` contract.
fn map_update_err(e: aurora_fleet::FleetError) -> AuroraError {
    // Q3.1: the Core crate now parses the `[UP-xxx]` prefix once — use its
    // `code()` / `message()` instead of re-implementing the split here. Non-coded
    // variants (network/io surfaced via `?`) carry no code → fall back to UP-000.
    AuroraError::UpdateFailed {
        code: e.code().unwrap_or("UP-000").to_string(),
        message: e.message().to_string(),
    }
}

#[tauri::command]
async fn check_update() -> Result<Option<aurora_fleet::updater::VersionInfo>, AuroraError> {
    aurora_fleet::updater::check_for_updates(env!("CARGO_PKG_VERSION"), env!("CARGO_PKG_NAME"))
        .await
        .map_err(map_update_err)
}

#[tauri::command]
async fn download_update(
    url: String,
    checksum: String,
    app: tauri::AppHandle,
) -> Result<String, AuroraError> {
    let path = aurora_fleet::updater::download_update(&url, move |downloaded, total, percent| {
        let _ = app.emit(
            "update-progress",
            serde_json::json!({ "downloaded": downloaded, "total": total, "percent": percent }),
        );
    })
    .await
    .map_err(map_update_err)?;
    aurora_fleet::updater::verify_checksum(&path, &checksum).map_err(map_update_err)?;
    Ok(path.to_string_lossy().to_string())
}

#[tauri::command]
async fn apply_update(installer_path: String, app: tauri::AppHandle) -> Result<(), AuroraError> {
    // The crate's apply_update is sync and exits the process on success; run the
    // async sidecar shutdown inside the on_pre_exit hook (we are about to exit).
    let manager = app
        .try_state::<std::sync::Arc<sidecar::SidecarManager>>()
        .map(|s| std::sync::Arc::clone(s.inner()));
    aurora_fleet::updater::apply_update(std::path::Path::new(&installer_path), move || {
        if let Some(manager) = manager {
            tauri::async_runtime::block_on(manager.shutdown());
        }
    })
    .map_err(map_update_err)
}

/// Machine licensing id — hex SHA256 of the machine fingerprint. This is the
/// value an admin needs to issue a licence for this device; it matches the fleet
/// `licenses.fingerprint_hash` and the offline `license.json`
/// `machine_fingerprint_hash` binding (Phase B). Surfaced so the customer can
/// copy it from Settings when requesting a licence.
#[tauri::command]
fn get_machine_id() -> Result<String, AuroraError> {
    let fp = aurora_fleet::fingerprint::get_machine_fingerprint()
        .map_err(|e| AuroraError::Other(format!("fingerprint failed: {e}")))?;
    Ok(aurora_fleet::fingerprint::hash_fingerprint(&fp))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    env_logger::init();
    // Phase 0.3: install panic handler BEFORE anything else can crash.
    // Hook writes crash-{ts}.dump к %LOCALAPPDATA%/Aurora Launch/crashes/
    // when any thread panics. On next start, list_pending_crashes IPC
    // command surfaces these dumps for support submission.
    panic_handler::install_panic_hook(env!("CARGO_PKG_VERSION"), BUILD_PROFILE);

    // Phase Π.1.1: ensure all standard data subdirectories exist.
    if let Err(e) = paths::ensure_layout() {
        log::warn!("Failed to create standard data layout: {}", e);
    }

    log::info!(
        "aurora_launch starting — build_profile={}, version={}, user={}",
        BUILD_PROFILE,
        env!("CARGO_PKG_VERSION"),
        paths::current_username()
    );

    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_os::init());

    // Dev-only: MCP Bridge plugin для автоматизированных webview/IPC smoke
    // tests (visual-audit skill, driver_session @ 127.0.0.1:9229). Включается
    // только в debug сборке, в production не попадает. bind 127.0.0.1 (НЕ
    // дефолтный 0.0.0.0) — порт не открывается в сеть. base_port 9229 —
    // per-product (карта в visual-audit references; дефолт 9223 = Econometrica,
    // collision если оба dev сразу).
    #[cfg(debug_assertions)]
    let builder = builder.plugin(
        tauri_plugin_mcp_bridge::Builder::new()
            .bind_address("127.0.0.1")
            .base_port(9229)
            .build(),
    );

    builder
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
            // Phase 2 production Rust IPC bridges (audit deferred closure)
            commands::forecast::compute_trust_score,
            commands::forecast::generate_reproduce_script,
            commands::forecast::explain_forecast,
            commands::forecast::compare_forecast_versions,
            commands::forecast::compose_forecast_json,
            // Sprint 2 D5: MCMC OOM pre-flight memory budget
            commands::forecast::check_mcmc_budget,
            // Sprint 2 D1': trust score from project state
            commands::forecast::compute_trust_score_for_project,
            commands::handshake::get_handshake_status,
            // methodology_cert commands (Block 2C)
            commands::methodology_cert::verify_bundle_signature,
            commands::methodology_cert::generate_local_dev_signature,
            // Sprint 3 D6: bundle reproducibility verification
            commands::methodology_cert::verify_reproducibility,
            // license commands
            commands::license::current_license_status,
            commands::license::has_feature,
            commands::license::require_feature,
            commands::license::is_dev_build,
            commands::license::import_license,
            // telemetry commands (Block 2F — local-only buffer)
            commands::telemetry::log_event,
            commands::telemetry::list_events,
            commands::telemetry::get_telemetry_opt_in,
            commands::telemetry::set_telemetry_opt_in,
            // Phase 2.D.2 HE-6: tiered PII redaction
            commands::telemetry::get_redaction_tier,
            commands::telemetry::set_redaction_tier,
            // feedback commands (Block 2F — Cmd+Shift+F)
            commands::feedback::capture_feedback,
            commands::feedback::list_pending_feedback,
            // audit log (Block 2F — UI consumer)
            commands::audit_log::list_audit_entries,
            // build info
            commands::build_info::get_build_info,
            // auto-updater (fleet checksum updater — replaces tauri-plugin-updater)
            check_update,
            download_update,
            apply_update,
            // machine licensing id (Phase B — fingerprint for licence issuance)
            get_machine_id,
            // adapters (Block 4 Phase 3)
            commands::adapters::analyze_data_file,
            commands::adapters::validate_wide_table,
            // crash recovery (Phase 0.3)
            commands::crash_recovery::list_pending_crashes,
            commands::crash_recovery::get_crash_details,
            commands::crash_recovery::dismiss_crash,
            commands::crash_recovery::dismiss_all_crashes,
            // project management — ProjectDB + LaunchOrchestrator (R-03a)
            commands::projects::create_project,
            commands::projects::list_projects,
            commands::projects::list_pending_posterior_updates,
            commands::projects::get_project,
            commands::projects::delete_project,
            commands::projects::list_versions,
            commands::projects::compare_versions,
            commands::projects::import_aurora_bundle,
            commands::projects::load_sample_bundle,
        ])
        .setup(|app| {
            // Initialize local SQLite for telemetry + audit log
            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                if let Err(e) = state::init_local_storage(&app_handle).await {
                    log::error!("Failed to initialize local storage: {e}");
                }
            });

            // Block 4 Phase 1: spawn Python sidecar (long-running daemon).
            // Best-effort — if sidecar binary is missing (dev w/o PyInstaller),
            // app continues с degraded functionality (save/forecast/parse fail
            // gracefully via AuroraError::Other "sidecar not running").
            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                match sidecar::SidecarManager::spawn(&app_handle).await {
                    Ok(manager) => {
                        app_handle.manage(manager);
                        log::info!("Sidecar manager initialised");
                    }
                    Err(e) => {
                        log::warn!(
                            "Sidecar spawn failed (degraded mode — Phase 4 dependent flows \
                             will fail with sidecar_not_running): {e}"
                        );
                    }
                }
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running aurora-launch");
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Pins Launch's `[UP-xxx]` → `UpdateFailed { code, message }` glue after the
    /// Q3.1 switch to the crate's `code()` / `message()`. The crate tests the prefix
    /// parse itself; this guards Launch's OWN decisions — the frontend banner's
    /// `{ code, message }` contract and the `UP-000` fallback for non-coded errors.
    #[test]
    fn map_update_err_uses_crate_code_and_message() {
        // Coded updater error → code + prefix-stripped message.
        let mapped = map_update_err(aurora_fleet::FleetError::Update(
            "[UP-003] integrity check failed".into(),
        ));
        match mapped {
            AuroraError::UpdateFailed { code, message } => {
                assert_eq!(code, "UP-003");
                assert_eq!(message, "integrity check failed");
            }
            other => panic!("expected UpdateFailed, got {other:?}"),
        }

        // Non-coded error (e.g. a network failure surfaced via `?`) → UP-000 fallback,
        // message carried through.
        let mapped = map_update_err(aurora_fleet::FleetError::Network("timeout".into()));
        match mapped {
            AuroraError::UpdateFailed { code, message } => {
                assert_eq!(code, "UP-000");
                assert_eq!(message, "timeout");
            }
            other => panic!("expected UpdateFailed, got {other:?}"),
        }
    }
}
