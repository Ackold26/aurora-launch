//! Application state — bundle handles, forecast handles, SQLite connection.
//!
//! Handle-based pattern (Block 2 audit decision D7): IPC returns small
//! `BundleHandle { id, manifest_summary }` instead of full bundle bytes;
//! frontend reads entries lazily через `read_bundle_entry(handle_id, entry)`.
//! This mirrors `LazyLoadedBundle` API из Block 1C — same trade-off.

use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Mutex;

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};

use crate::errors::AuroraResult;

#[derive(Default)]
pub struct AppState {
    /// Open bundle handles. Key = handle_id (UUID v4). Value = OpenBundleHandle.
    pub bundles: Mutex<HashMap<String, OpenBundleHandle>>,
    /// Forecast handles for cancellation.
    pub forecasts: Mutex<HashMap<String, ForecastHandle>>,
    /// Local SQLite for telemetry + audit log + feedback queue (Block 2F).
    pub sqlite: Mutex<Option<rusqlite::Connection>>,
    /// Telemetry opt-in flag, default OFF (privacy first).
    pub telemetry_opt_in: Mutex<bool>,
}

pub struct OpenBundleHandle {
    pub path: PathBuf,
    /// We hold the `LazyLoadedBundle`-equivalent state in Rust: lazy reader
    /// over `zip::ZipArchive` that re-opens on demand. For Block 2 we use a
    /// simpler model: keep path + cached manifest bytes; entries read fresh
    /// on each read_bundle_entry call (atomic, advisory-lock-aware).
    pub manifest_json: serde_json::Value,
    pub source_format: String,
    pub size_bytes: u64,
    pub revision: i64,
}

#[derive(Debug)]
pub struct ForecastHandle {
    pub project_id: String,
    pub started_at: chrono::DateTime<chrono::Utc>,
    pub cancelled: std::sync::atomic::AtomicBool,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct BundleHandleSummary {
    pub handle_id: String,
    pub source_format: String,
    pub size_bytes: u64,
    pub revision: i64,
    pub manifest: serde_json::Value,
    /// Block 4 Phase 5: filesystem path included so Inspector can call
    /// `verify_bundle_signature` без storing path separately. INV-01: this
    /// is an additive Optional field (per CPI-02 schema invariant); existing
    /// frontend code that doesn't read it is unaffected.
    pub path: String,
}

pub async fn init_local_storage(app_handle: &AppHandle) -> AuroraResult<()> {
    let app_data_dir = app_handle.path().app_data_dir().map_err(|e| {
        crate::errors::AuroraError::Other(format!("cannot resolve app_data_dir: {e}"))
    })?;
    std::fs::create_dir_all(&app_data_dir)?;
    let db_path = app_data_dir.join("aurora_launch.sqlite");
    let conn = rusqlite::Connection::open(&db_path)?;

    // Schema for telemetry events (Block 2F) — local-only buffer
    conn.execute(
        "CREATE TABLE IF NOT EXISTS telemetry_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            uploaded_at TEXT
        )",
        [],
    )?;

    // Schema for audit log (Block 2F — UI consumer)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            actor TEXT NOT NULL,
            operation TEXT NOT NULL,
            target TEXT,
            outcome TEXT NOT NULL,
            details_json TEXT
        )",
        [],
    )?;

    // Schema for feedback queue (Cmd+Shift+F)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS feedback_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            text TEXT NOT NULL,
            screenshot_path TEXT,
            log_path TEXT,
            uploaded_at TEXT
        )",
        [],
    )?;

    // Settings (theme, locale, telemetry opt-in)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )",
        [],
    )?;

    let state = app_handle.state::<AppState>();
    *state.sqlite.lock().unwrap() = Some(conn);

    log::info!("Local storage initialised: {}", db_path.display());
    Ok(())
}
