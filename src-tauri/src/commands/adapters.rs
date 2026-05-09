//! Adapter IPC commands (Block 4 Phase 3).
//!
//! Wires frontend file picker к Python AdapterRegistry через sidecar JSON-RPC.
//! Auto-detects DSM/Mediascope/AdEx/Custom XLSX format, parses к canonical
//! records, returns preview slice for UI display.

use std::sync::Arc;

use serde::{Deserialize, Serialize};
use tauri::State;

use crate::errors::{AuroraError, AuroraResult};
use crate::sidecar::SidecarManager;

#[derive(Serialize, Deserialize, Debug)]
pub struct ParseDataFileInput {
    pub path: String,
    pub adapter_id: Option<String>,
    pub max_records: Option<u32>,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct ParseDataFileResult {
    pub adapter_id: String,
    pub adapter_metadata: serde_json::Value,
    pub record_count: u64,
    pub records: Vec<serde_json::Value>,
}

#[tauri::command]
pub async fn parse_data_file(
    sidecar: State<'_, Arc<SidecarManager>>,
    input: ParseDataFileInput,
) -> AuroraResult<ParseDataFileResult> {
    let mut params = serde_json::json!({
        "path": input.path,
        "max_records": input.max_records.unwrap_or(100),
    });
    if let Some(id) = input.adapter_id {
        params["adapter_id"] = serde_json::Value::String(id);
    }

    sidecar.invoke("parse_data_file", params).await
}

#[derive(Serialize, Deserialize, Debug)]
pub struct AdapterInfo {
    pub adapter_id: String,
    pub adapter_version: String,
    pub schema_version: String,
    pub sample_files_glob: Vec<String>,
    pub canonical_record_mapping: std::collections::BTreeMap<String, String>,
    pub detected_signatures: Vec<String>,
}

#[tauri::command]
pub async fn list_adapters(
    sidecar: State<'_, Arc<SidecarManager>>,
) -> AuroraResult<Vec<AdapterInfo>> {
    // Convenience IPC for Settings → Adapters tab. Sidecar returns the registry.
    // Block 4 method `list_adapters` not yet defined — use a wrapper pinging
    // ping result's `methods` for now; future sidecar method will return full
    // metadata. For Block 4 Phase 3 we ship the contract; sidecar Phase 1+
    // will add the method.
    let result: serde_json::Value = sidecar
        .invoke("ping", serde_json::json!({}))
        .await?;
    let _ = result;
    // Until the sidecar method ships, return empty list (frontend gracefully
    // shows "no adapters registered").
    Ok(Vec::new())
}
