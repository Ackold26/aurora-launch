//! Local-only telemetry buffer (Block 2 audit D10).
//!
//! Events appended to local SQLite. Upload pipe to Vercel deferred F1.
//! All events tagged `uploaded_at = NULL` until F1 wiring uploads them.

use serde::{Deserialize, Serialize};
use tauri::State;

use crate::errors::{AuroraError, AuroraResult};
use crate::state::AppState;

#[derive(Serialize, Deserialize, Debug)]
pub struct TelemetryEvent {
    pub event_type: String,
    pub timestamp: String,
    pub payload: serde_json::Value,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct StoredTelemetryEvent {
    pub id: i64,
    pub event_type: String,
    pub timestamp: String,
    pub payload: serde_json::Value,
    pub uploaded_at: Option<String>,
}

#[tauri::command]
pub async fn log_event(state: State<'_, AppState>, event: TelemetryEvent) -> AuroraResult<i64> {
    let opt_in = *state
        .telemetry_opt_in
        .lock()
        .map_err(|_| AuroraError::Other("opt_in poisoned".into()))?;
    // We always store locally; upload is gated by opt_in (Block 4 reads flag
    // before sending). Storing locally regardless lets users review what
    // would be sent, building trust.
    let _ = opt_in;

    let conn_guard = state
        .sqlite
        .lock()
        .map_err(|_| AuroraError::Other("sqlite poisoned".into()))?;
    let conn = conn_guard.as_ref().ok_or(AuroraError::Other(
        "SQLite not initialised yet".into(),
    ))?;
    conn.execute(
        "INSERT INTO telemetry_events (event_type, timestamp, payload_json, uploaded_at)
         VALUES (?1, ?2, ?3, NULL)",
        rusqlite::params![
            event.event_type,
            event.timestamp,
            serde_json::to_string(&event.payload)?,
        ],
    )?;
    Ok(conn.last_insert_rowid())
}

#[tauri::command]
pub async fn list_events(
    state: State<'_, AppState>,
    limit: Option<i64>,
) -> AuroraResult<Vec<StoredTelemetryEvent>> {
    let conn_guard = state
        .sqlite
        .lock()
        .map_err(|_| AuroraError::Other("sqlite poisoned".into()))?;
    let conn = conn_guard.as_ref().ok_or(AuroraError::Other("SQLite not initialised".into()))?;
    let lim = limit.unwrap_or(500);
    let mut stmt = conn.prepare(
        "SELECT id, event_type, timestamp, payload_json, uploaded_at
         FROM telemetry_events
         ORDER BY id DESC LIMIT ?1",
    )?;
    let rows = stmt.query_map([lim], |row| {
        let payload_json: String = row.get(3)?;
        let payload: serde_json::Value =
            serde_json::from_str(&payload_json).unwrap_or(serde_json::Value::Null);
        Ok(StoredTelemetryEvent {
            id: row.get(0)?,
            event_type: row.get(1)?,
            timestamp: row.get(2)?,
            payload,
            uploaded_at: row.get(4)?,
        })
    })?;
    let mut out = Vec::new();
    for r in rows {
        out.push(r?);
    }
    Ok(out)
}

#[tauri::command]
pub async fn get_telemetry_opt_in(state: State<'_, AppState>) -> AuroraResult<bool> {
    Ok(*state
        .telemetry_opt_in
        .lock()
        .map_err(|_| AuroraError::Other("opt_in poisoned".into()))?)
}

#[tauri::command]
pub async fn set_telemetry_opt_in(
    state: State<'_, AppState>,
    enabled: bool,
) -> AuroraResult<()> {
    *state
        .telemetry_opt_in
        .lock()
        .map_err(|_| AuroraError::Other("opt_in poisoned".into()))?
        = enabled;

    let conn_guard = state
        .sqlite
        .lock()
        .map_err(|_| AuroraError::Other("sqlite poisoned".into()))?;
    if let Some(conn) = conn_guard.as_ref() {
        conn.execute(
            "INSERT INTO settings (key, value, updated_at)
             VALUES ('telemetry_opt_in', ?1, ?2)
             ON CONFLICT(key) DO UPDATE SET value = ?1, updated_at = ?2",
            rusqlite::params![enabled.to_string(), chrono::Utc::now().to_rfc3339()],
        )?;
    }
    Ok(())
}
