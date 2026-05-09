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
    sidecar: State<'_, std::sync::Arc<crate::sidecar::SidecarManager>>,
    input: ForecastStartInput,
) -> AuroraResult<ForecastHandleSummary> {
    let started_at = chrono::Utc::now();

    // Block 4 Phase 4: route к Python sidecar — sidecar returns its own
    // handle (UUID), emits forecast_progress / forecast_completed /
    // forecast_cancelled / forecast_failed events. Frontend listens via
    // Tauri event bus on `sidecar://forecast_*` channels.
    let params = serde_json::json!({
        "project_id": input.project_id,
        "horizon_weeks": input.horizon_weeks,
        "seed": input.seed,
    });
    let result: serde_json::Value = sidecar
        .invoke("start_forecast", params)
        .await?;

    let handle_id = result
        .get("forecast_handle")
        .and_then(|v| v.as_str())
        .map(String::from)
        .ok_or(AuroraError::Other(
            "sidecar response missing forecast_handle".into(),
        ))?;

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

    Ok(ForecastHandleSummary {
        handle_id,
        project_id: input.project_id,
        started_at: started_at.to_rfc3339(),
    })
}

#[tauri::command]
pub async fn cancel_forecast(
    state: State<'_, AppState>,
    sidecar: State<'_, std::sync::Arc<crate::sidecar::SidecarManager>>,
    handle_id: String,
) -> AuroraResult<()> {
    // Block 4 Phase 4: cooperative cancel via sidecar atomic flag (D5: NO
    // SIGINT, NO terminate). Sidecar sampler thread polls flag, exits
    // gracefully на next iteration boundary.
    let _: serde_json::Value = sidecar
        .invoke(
            "cancel_forecast",
            serde_json::json!({ "forecast_handle": handle_id }),
        )
        .await?;

    // Mirror в Rust state for UI rendering even before Python confirms.
    if let Ok(forecasts) = state.forecasts.lock() {
        if let Some(handle) = forecasts.get(&handle_id) {
            handle.cancelled.store(true, Ordering::SeqCst);
        }
    }
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
