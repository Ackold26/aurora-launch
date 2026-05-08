//! In-app feedback channel (Block 2F PREMIUM P10) — Cmd+Shift+F.
//!
//! Captures user text + auto-attached screenshot + recent log slice into
//! local queue. Upload pipe to Vercel function → GitHub Issue defers to F1.
//! Block 2 stub: persist locally; UI surfaces "Pending sync" badge on
//! queued feedback в History panel.

use serde::{Deserialize, Serialize};
use tauri::State;

use crate::errors::{AuroraError, AuroraResult};
use crate::state::AppState;

#[derive(Serialize, Deserialize, Debug)]
pub struct FeedbackInput {
    pub text: String,
    pub screenshot_path: Option<String>,
    pub log_path: Option<String>,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct FeedbackEntry {
    pub id: i64,
    pub timestamp: String,
    pub text: String,
    pub screenshot_path: Option<String>,
    pub log_path: Option<String>,
    pub uploaded_at: Option<String>,
}

#[tauri::command]
pub async fn capture_feedback(
    state: State<'_, AppState>,
    input: FeedbackInput,
) -> AuroraResult<i64> {
    let conn_guard = state
        .sqlite
        .lock()
        .map_err(|_| AuroraError::Other("sqlite poisoned".into()))?;
    let conn = conn_guard.as_ref().ok_or(AuroraError::Other("SQLite not initialised".into()))?;
    conn.execute(
        "INSERT INTO feedback_queue (timestamp, text, screenshot_path, log_path, uploaded_at)
         VALUES (?1, ?2, ?3, ?4, NULL)",
        rusqlite::params![
            chrono::Utc::now().to_rfc3339(),
            input.text,
            input.screenshot_path,
            input.log_path,
        ],
    )?;
    Ok(conn.last_insert_rowid())
}

#[tauri::command]
pub async fn list_pending_feedback(
    state: State<'_, AppState>,
) -> AuroraResult<Vec<FeedbackEntry>> {
    let conn_guard = state
        .sqlite
        .lock()
        .map_err(|_| AuroraError::Other("sqlite poisoned".into()))?;
    let conn = conn_guard.as_ref().ok_or(AuroraError::Other("SQLite not initialised".into()))?;
    let mut stmt = conn.prepare(
        "SELECT id, timestamp, text, screenshot_path, log_path, uploaded_at
         FROM feedback_queue
         WHERE uploaded_at IS NULL
         ORDER BY id DESC",
    )?;
    let rows = stmt.query_map([], |row| {
        Ok(FeedbackEntry {
            id: row.get(0)?,
            timestamp: row.get(1)?,
            text: row.get(2)?,
            screenshot_path: row.get(3)?,
            log_path: row.get(4)?,
            uploaded_at: row.get(5)?,
        })
    })?;
    let mut out = Vec::new();
    for r in rows {
        out.push(r?);
    }
    Ok(out)
}
