//! Audit log UI consumer (Block 2F PREMIUM P6).
//!
//! Read-only listing of audit_log table populated by other commands when they
//! perform significant operations (open bundle, save bundle, sign cert,
//! verify cert, etc.). UI History panel renders chronological timeline.

use serde::{Deserialize, Serialize};
use tauri::State;

use crate::errors::{AuroraError, AuroraResult};
use crate::state::AppState;

#[derive(Serialize, Deserialize, Debug)]
pub struct AuditEntry {
    pub id: i64,
    pub timestamp: String,
    pub actor: String,
    pub operation: String,
    pub target: Option<String>,
    pub outcome: String,
    pub details: serde_json::Value,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct AuditQuery {
    pub limit: Option<i64>,
    pub since: Option<String>,
    pub operation_filter: Option<String>,
}

#[tauri::command]
pub async fn list_audit_entries(
    state: State<'_, AppState>,
    query: AuditQuery,
) -> AuroraResult<Vec<AuditEntry>> {
    let conn_guard = state
        .sqlite
        .lock()
        .map_err(|_| AuroraError::Other("sqlite poisoned".into()))?;
    let conn = conn_guard.as_ref().ok_or(AuroraError::Other("SQLite not initialised".into()))?;

    let limit = query.limit.unwrap_or(200);

    let sql = match (&query.since, &query.operation_filter) {
        (Some(_), Some(_)) => {
            "SELECT id, timestamp, actor, operation, target, outcome, details_json
             FROM audit_log
             WHERE timestamp >= ?1 AND operation = ?2
             ORDER BY id DESC LIMIT ?3"
        }
        (Some(_), None) => {
            "SELECT id, timestamp, actor, operation, target, outcome, details_json
             FROM audit_log
             WHERE timestamp >= ?1
             ORDER BY id DESC LIMIT ?2"
        }
        (None, Some(_)) => {
            "SELECT id, timestamp, actor, operation, target, outcome, details_json
             FROM audit_log
             WHERE operation = ?1
             ORDER BY id DESC LIMIT ?2"
        }
        (None, None) => {
            "SELECT id, timestamp, actor, operation, target, outcome, details_json
             FROM audit_log
             ORDER BY id DESC LIMIT ?1"
        }
    };

    let mut stmt = conn.prepare(sql)?;

    let map_row = |row: &rusqlite::Row| -> rusqlite::Result<AuditEntry> {
        let details_json: Option<String> = row.get(6)?;
        let details = details_json
            .and_then(|s| serde_json::from_str(&s).ok())
            .unwrap_or(serde_json::Value::Null);
        Ok(AuditEntry {
            id: row.get(0)?,
            timestamp: row.get(1)?,
            actor: row.get(2)?,
            operation: row.get(3)?,
            target: row.get(4)?,
            outcome: row.get(5)?,
            details,
        })
    };

    let entries: Vec<AuditEntry> = match (&query.since, &query.operation_filter) {
        (Some(since), Some(op)) => {
            let rows = stmt.query_map(rusqlite::params![since, op, limit], map_row)?;
            rows.collect::<Result<Vec<_>, _>>()?
        }
        (Some(since), None) => {
            let rows = stmt.query_map(rusqlite::params![since, limit], map_row)?;
            rows.collect::<Result<Vec<_>, _>>()?
        }
        (None, Some(op)) => {
            let rows = stmt.query_map(rusqlite::params![op, limit], map_row)?;
            rows.collect::<Result<Vec<_>, _>>()?
        }
        (None, None) => {
            let rows = stmt.query_map(rusqlite::params![limit], map_row)?;
            rows.collect::<Result<Vec<_>, _>>()?
        }
    };

    Ok(entries)
}
