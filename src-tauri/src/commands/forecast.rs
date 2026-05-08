//! Forecast IPC — start/cancel/status pattern.
//!
//! Backend-side: real forecast generation invokes Python sidecar (deferred
//! Block 4 real integration). Here we provide a handle-based contract:
//! `start_forecast` returns handle, `cancel_forecast` sets cancel flag,
//! `get_forecast_status` polls progress events stored in app state.
//!
//! Block 2D requirement: cancel должен быть **graceful** — flag visible
//! от Python side через shared file / IPC pipe (Block 4 wires это).
//! For Block 2 the cancel just marks handle cancelled; UI shows "cancelling…"
//! and after timeout либо "cancelled" либо "completed despite cancel".

use std::sync::atomic::{AtomicBool, Ordering};

use serde::{Deserialize, Serialize};
use tauri::State;
use uuid::Uuid;

use crate::errors::{AuroraError, AuroraResult};
use crate::state::{AppState, ForecastHandle};

#[derive(Serialize, Deserialize, Debug)]
pub struct ForecastStartInput {
    pub project_id: String,
    pub horizon_weeks: u32,
    pub seed: u64,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct ForecastHandleSummary {
    pub handle_id: String,
    pub project_id: String,
    pub started_at: String,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct ForecastStatus {
    pub handle_id: String,
    pub state: String, // "running" | "cancelling" | "cancelled" | "completed"
    pub progress_pct: f64,
    pub elapsed_ms: u64,
    pub eta_ms: Option<u64>,
}

#[tauri::command]
pub async fn start_forecast(
    state: State<'_, AppState>,
    input: ForecastStartInput,
) -> AuroraResult<ForecastHandleSummary> {
    let handle_id = Uuid::new_v4().to_string();
    let started_at = chrono::Utc::now();

    let handle = ForecastHandle {
        project_id: input.project_id.clone(),
        started_at,
        cancelled: AtomicBool::new(false),
    };

    state
        .forecasts
        .lock()
        .map_err(|_| AuroraError::Other("forecast map poisoned".into()))?
        .insert(handle_id.clone(), handle);

    // Block 4 will spawn Python sidecar here. For Block 2 the handle exists
    // и UI can show progress UI / cancel button; backend will wire real
    // execution в Block 4 integration sprint.

    Ok(ForecastHandleSummary {
        handle_id,
        project_id: input.project_id,
        started_at: started_at.to_rfc3339(),
    })
}

#[tauri::command]
pub async fn cancel_forecast(state: State<'_, AppState>, handle_id: String) -> AuroraResult<()> {
    let forecasts = state
        .forecasts
        .lock()
        .map_err(|_| AuroraError::Other("forecast map poisoned".into()))?;
    let handle = forecasts.get(&handle_id).ok_or(AuroraError::ForecastHandleNotFound {
        handle_id: handle_id.clone(),
    })?;
    handle.cancelled.store(true, Ordering::SeqCst);
    Ok(())
}

#[tauri::command]
pub async fn get_forecast_status(
    state: State<'_, AppState>,
    handle_id: String,
) -> AuroraResult<ForecastStatus> {
    let forecasts = state
        .forecasts
        .lock()
        .map_err(|_| AuroraError::Other("forecast map poisoned".into()))?;
    let handle = forecasts.get(&handle_id).ok_or(AuroraError::ForecastHandleNotFound {
        handle_id: handle_id.clone(),
    })?;
    let elapsed_ms = (chrono::Utc::now() - handle.started_at)
        .num_milliseconds()
        .max(0) as u64;
    let cancelled = handle.cancelled.load(Ordering::SeqCst);
    let state_str = if cancelled { "cancelled" } else { "running" };
    // Block 4 will replace stub with real progress streaming.
    Ok(ForecastStatus {
        handle_id,
        state: state_str.into(),
        progress_pct: if cancelled { 0.0 } else { 0.0 },
        elapsed_ms,
        eta_ms: None,
    })
}
