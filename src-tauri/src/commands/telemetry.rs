//! Local-only telemetry buffer (Block 2 audit D10).
//!
//! Events appended to local SQLite. Upload pipe to Vercel deferred F1.
//! All events tagged `uploaded_at = NULL` until F1 wiring uploads them.
//!
//! Phase 2.D.2 HE-6: tiered PII redaction.
//! The `redaction_tier` column on telemetry_events tracks which tier was applied
//! to each row. On upgrade (basic→strict→paranoid), existing rows are flagged
//! `redaction_pending = 1` for background re-redaction.

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

// ─── Phase 2.D.2 HE-6: tiered PII redaction ──────────────────────────────────

/// Tier ordering for upgrade detection.  Higher index = more restrictive.
fn tier_rank(tier: &str) -> u8 {
    match tier {
        "basic" => 0,
        "strict" => 1,
        "paranoid" => 2,
        _ => 0,
    }
}

/// Return the customer's current redaction tier (default: "basic").
#[tauri::command]
pub async fn get_redaction_tier(state: State<'_, AppState>) -> AuroraResult<String> {
    let conn_guard = state
        .sqlite
        .lock()
        .map_err(|_| AuroraError::Other("sqlite poisoned".into()))?;
    let conn = conn_guard.as_ref().ok_or(AuroraError::Other("SQLite not initialised".into()))?;
    let row: Option<String> = conn
        .query_row(
            "SELECT value FROM settings WHERE key = 'redaction_tier'",
            [],
            |r| r.get(0),
        )
        .ok();
    Ok(row.unwrap_or_else(|| "basic".into()))
}

/// Persist a new redaction tier.
///
/// If the new tier is more restrictive than the current one (upgrade),
/// all existing `telemetry_events` rows are flagged `redaction_pending = 1`
/// so they can be re-redacted by the frontend or a background job.
///
/// Returns `{ pending_count }` — number of rows flagged (0 if same/downgrade).
#[tauri::command]
pub async fn set_redaction_tier(
    state: State<'_, AppState>,
    tier: String,
) -> AuroraResult<serde_json::Value> {
    // Validate tier value
    if !matches!(tier.as_str(), "basic" | "strict" | "paranoid") {
        return Err(AuroraError::Other(format!(
            "invalid redaction tier: {tier}"
        )));
    }

    let conn_guard = state
        .sqlite
        .lock()
        .map_err(|_| AuroraError::Other("sqlite poisoned".into()))?;
    let conn = conn_guard.as_ref().ok_or(AuroraError::Other("SQLite not initialised".into()))?;

    // Read current tier
    let current: String = conn
        .query_row(
            "SELECT value FROM settings WHERE key = 'redaction_tier'",
            [],
            |r| r.get(0),
        )
        .unwrap_or_else(|_| "basic".into());

    // Persist new tier
    conn.execute(
        "INSERT INTO settings (key, value, updated_at)
         VALUES ('redaction_tier', ?1, ?2)
         ON CONFLICT(key) DO UPDATE SET value = ?1, updated_at = ?2",
        rusqlite::params![tier, chrono::Utc::now().to_rfc3339()],
    )?;

    // Flag existing rows for re-redaction if upgrading tier
    let pending_count: i64 = if tier_rank(&tier) > tier_rank(&current) {
        conn.execute(
            "UPDATE telemetry_events SET redaction_pending = 1
             WHERE redaction_pending = 0",
            [],
        )? as i64
    } else {
        0
    };

    Ok(serde_json::json!({ "pending_count": pending_count }))
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
