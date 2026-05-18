//! File analysis & validation IPC commands.
//!
//! После port'а file reader из Aurora Econometrica MMM Optimizer (2026-05-18,
//! design doc `docs/FILE_READER_PORT_DESIGN.md`) этот модуль обслуживает два
//! sidecar метода:
//!   - `analyze_data_file`  — preview первых N строк + автоопределение ролей
//!   - `validate_wide_table` — полная валидация с user role overrides
//!
//! Sidecar Python JSON-RPC (newline-delimited stdio). Возврат — opaque
//! `serde_json::Value`: shape известна только TypeScript-клиенту (см. typed
//! interface в `frontend/src/lib/ipc/client.ts`). Дублировать здесь Rust
//! struct'ы — это maintenance bloat для двух методов.

use std::sync::Arc;

use serde::{Deserialize, Serialize};
use tauri::State;

use crate::errors::AuroraResult;
use crate::sidecar::SidecarManager;

#[derive(Serialize, Deserialize, Debug)]
pub struct AnalyzeDataFileInput {
    pub path: String,
    pub n_rows: Option<u32>,
}

#[tauri::command]
pub async fn analyze_data_file(
    sidecar: State<'_, Arc<SidecarManager>>,
    input: AnalyzeDataFileInput,
) -> AuroraResult<serde_json::Value> {
    let params = serde_json::json!({
        "path": input.path,
        "n_rows": input.n_rows.unwrap_or(20),
    });
    sidecar.invoke("analyze_data_file", params).await
}

#[derive(Serialize, Deserialize, Debug)]
pub struct ValidateWideTableInput {
    pub path: String,
    pub role_overrides: Option<std::collections::BTreeMap<String, String>>,
}

#[tauri::command]
pub async fn validate_wide_table(
    sidecar: State<'_, Arc<SidecarManager>>,
    input: ValidateWideTableInput,
) -> AuroraResult<serde_json::Value> {
    let mut params = serde_json::json!({ "path": input.path });
    if let Some(overrides) = input.role_overrides {
        params["role_overrides"] = serde_json::to_value(overrides)
            .unwrap_or(serde_json::Value::Object(Default::default()));
    }
    sidecar.invoke("validate_wide_table", params).await
}
