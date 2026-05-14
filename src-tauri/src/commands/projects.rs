//! Project management IPC — wired к Python sidecar ProjectDB singleton.
//!
//! Commands route via `SidecarManager::invoke()` к Python JSON-RPC handlers.
//! Python side (ProjectDB + LaunchOrchestrator) implemented separately.
//! All struct fields use snake_case to match Python sidecar response format.
//!
//! Closes audit R-03a.

use std::sync::Arc;

use serde::{Deserialize, Serialize};
use tauri::State;

use crate::errors::{AuroraError, AuroraResult};
use crate::sidecar::SidecarManager;

// ---------------------------------------------------------------------------
// Response DTOs — field names MUST match Python sidecar snake_case output.
// ---------------------------------------------------------------------------

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct ProjectSummary {
    pub project_uuid: String,
    pub name: String,
    pub created_at: String,
    pub last_modified: String,
    pub granularity: String,
    pub version_count: i64,
    pub current_version_id: Option<i64>,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct VersionSummary {
    pub version_id: i64,
    pub revision: i64,
    pub label: Option<String>,
    pub decision_note: Option<String>,
    pub created_at: String,
    pub composite_bundle_hash: Option<String>,
    pub file_count: i64,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct ProjectDetail {
    pub project_uuid: String,
    pub name: String,
    pub metadata: serde_json::Value,
    pub versions: Vec<VersionSummary>,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct VersionDiff {
    pub files_only_in_a: Vec<String>,
    pub files_only_in_b: Vec<String>,
    pub files_changed: Vec<String>,
    pub files_unchanged: Vec<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct ImportBundleResult {
    pub project_uuid: String,
    pub version_id: i64,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct SampleBundleResult {
    pub project_uuid: String,
    pub version_id: i64,
    pub channels: Vec<String>,
    pub n_periods: i64,
}

// ---------------------------------------------------------------------------
// IPC commands
// ---------------------------------------------------------------------------

/// Create a new project in ProjectDB. Returns the created project record.
#[tauri::command]
pub async fn create_project(
    sidecar: State<'_, Arc<SidecarManager>>,
    name: String,
    granularity: Option<String>,
    metadata: Option<serde_json::Value>,
) -> AuroraResult<serde_json::Value> {
    let params = serde_json::json!({
        "name": name,
        "granularity": granularity.unwrap_or_else(|| "monthly".to_string()),
        "metadata": metadata.unwrap_or(serde_json::Value::Object(Default::default())),
    });
    sidecar.invoke("create_project", params).await
}

/// List all projects in ProjectDB, ordered by last_modified DESC.
#[tauri::command]
pub async fn list_projects(
    sidecar: State<'_, Arc<SidecarManager>>,
) -> AuroraResult<Vec<ProjectSummary>> {
    let resp: serde_json::Value = sidecar
        .invoke("list_projects", serde_json::json!({}))
        .await?;
    let projects = resp
        .get("projects")
        .and_then(|v| v.as_array())
        .ok_or_else(|| AuroraError::Other("list_projects: missing 'projects' field".into()))?;
    serde_json::from_value(serde_json::Value::Array(projects.clone()))
        .map_err(|e| AuroraError::Other(format!("deserialize projects: {e}")))
}

/// Get full project detail including version history.
#[tauri::command]
pub async fn get_project(
    sidecar: State<'_, Arc<SidecarManager>>,
    project_uuid: String,
) -> AuroraResult<ProjectDetail> {
    let resp: serde_json::Value = sidecar
        .invoke(
            "get_project",
            serde_json::json!({ "project_uuid": project_uuid }),
        )
        .await?;
    serde_json::from_value(resp)
        .map_err(|e| AuroraError::Other(format!("deserialize project detail: {e}")))
}

/// Delete a project and all its versions. Irreversible.
#[tauri::command]
pub async fn delete_project(
    sidecar: State<'_, Arc<SidecarManager>>,
    project_uuid: String,
) -> AuroraResult<()> {
    let _: serde_json::Value = sidecar
        .invoke(
            "delete_project",
            serde_json::json!({ "project_uuid": project_uuid }),
        )
        .await?;
    Ok(())
}

/// List all versions for a project, ordered by revision DESC.
#[tauri::command]
pub async fn list_versions(
    sidecar: State<'_, Arc<SidecarManager>>,
    project_uuid: String,
) -> AuroraResult<Vec<VersionSummary>> {
    let resp: serde_json::Value = sidecar
        .invoke(
            "list_versions",
            serde_json::json!({ "project_uuid": project_uuid }),
        )
        .await?;
    let versions = resp
        .get("versions")
        .and_then(|v| v.as_array())
        .ok_or_else(|| AuroraError::Other("list_versions: missing 'versions' field".into()))?;
    serde_json::from_value(serde_json::Value::Array(versions.clone()))
        .map_err(|e| AuroraError::Other(format!("deserialize versions: {e}")))
}

/// Compare two versions by their version_ids. Returns file-level diff summary.
#[tauri::command]
pub async fn compare_versions(
    sidecar: State<'_, Arc<SidecarManager>>,
    version_id_a: i64,
    version_id_b: i64,
) -> AuroraResult<VersionDiff> {
    let resp: serde_json::Value = sidecar
        .invoke(
            "compare_versions",
            serde_json::json!({
                "version_id_a": version_id_a,
                "version_id_b": version_id_b,
            }),
        )
        .await?;
    serde_json::from_value(resp)
        .map_err(|e| AuroraError::Other(format!("deserialize diff: {e}")))
}

/// Import an existing `.aurora` bundle into ProjectDB, creating a new project
/// or appending a new version to an existing one (sidecar decides).
#[tauri::command]
pub async fn import_aurora_bundle(
    sidecar: State<'_, Arc<SidecarManager>>,
    bundle_path: String,
    project_name: Option<String>,
    granularity: Option<String>,
) -> AuroraResult<ImportBundleResult> {
    let mut params = serde_json::json!({ "bundle_path": bundle_path });
    if let Some(name) = project_name {
        params["project_name"] = serde_json::Value::String(name);
    }
    if let Some(g) = granularity {
        params["granularity"] = serde_json::Value::String(g);
    }
    let resp: serde_json::Value = sidecar.invoke("import_aurora_bundle", params).await?;
    serde_json::from_value(resp)
        .map_err(|e| AuroraError::Other(format!("deserialize import result: {e}")))
}

/// Load a built-in sample bundle (e.g. `"kagocell_demo"`) into ProjectDB.
/// Returns project + version identifiers plus channel / period metadata.
#[tauri::command]
pub async fn load_sample_bundle(
    sidecar: State<'_, Arc<SidecarManager>>,
    scenario: String,
) -> AuroraResult<SampleBundleResult> {
    let resp: serde_json::Value = sidecar
        .invoke(
            "load_sample_bundle",
            serde_json::json!({ "scenario": scenario }),
        )
        .await?;
    serde_json::from_value(resp)
        .map_err(|e| AuroraError::Other(format!("deserialize sample result: {e}")))
}

// ---------------------------------------------------------------------------
// Unit tests — serialize / deserialize roundtrip for each DTO.
// No real sidecar needed; purely data-shape contracts.
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn project_summary_roundtrip() {
        let original = ProjectSummary {
            project_uuid: "abc-123".into(),
            name: "Test Project".into(),
            created_at: "2026-01-01T00:00:00Z".into(),
            last_modified: "2026-01-02T12:00:00Z".into(),
            granularity: "monthly".into(),
            version_count: 3,
            current_version_id: Some(7),
        };
        let json_str = serde_json::to_string(&original).unwrap();
        let decoded: ProjectSummary = serde_json::from_str(&json_str).unwrap();
        assert_eq!(decoded.project_uuid, original.project_uuid);
        assert_eq!(decoded.version_count, 3);
        assert_eq!(decoded.current_version_id, Some(7));
    }

    #[test]
    fn project_summary_no_current_version() {
        let original = ProjectSummary {
            project_uuid: "def-456".into(),
            name: "Empty Project".into(),
            created_at: "2026-01-01T00:00:00Z".into(),
            last_modified: "2026-01-01T00:00:00Z".into(),
            granularity: "weekly".into(),
            version_count: 0,
            current_version_id: None,
        };
        let json_str = serde_json::to_string(&original).unwrap();
        let decoded: ProjectSummary = serde_json::from_str(&json_str).unwrap();
        assert_eq!(decoded.current_version_id, None);
    }

    #[test]
    fn version_summary_roundtrip() {
        let original = VersionSummary {
            version_id: 42,
            revision: 5,
            label: Some("pre-pilot".into()),
            decision_note: Some("Added TV channel".into()),
            created_at: "2026-03-15T09:30:00Z".into(),
            composite_bundle_hash: Some("sha256:abcdef1234567890".into()),
            file_count: 8,
        };
        let json_str = serde_json::to_string(&original).unwrap();
        let decoded: VersionSummary = serde_json::from_str(&json_str).unwrap();
        assert_eq!(decoded.version_id, 42);
        assert_eq!(decoded.revision, 5);
        assert_eq!(decoded.label.as_deref(), Some("pre-pilot"));
        assert_eq!(decoded.file_count, 8);
    }

    #[test]
    fn version_summary_optional_fields_null() {
        let raw = json!({
            "version_id": 1,
            "revision": 1,
            "label": null,
            "decision_note": null,
            "created_at": "2026-01-01T00:00:00Z",
            "composite_bundle_hash": null,
            "file_count": 2
        });
        let decoded: VersionSummary = serde_json::from_value(raw).unwrap();
        assert_eq!(decoded.label, None);
        assert_eq!(decoded.decision_note, None);
        assert_eq!(decoded.composite_bundle_hash, None);
    }

    #[test]
    fn project_detail_roundtrip() {
        let original = ProjectDetail {
            project_uuid: "proj-xyz".into(),
            name: "Full Project".into(),
            metadata: json!({"client": "Materia Medica", "product": "Kagocell"}),
            versions: vec![VersionSummary {
                version_id: 1,
                revision: 1,
                label: None,
                decision_note: None,
                created_at: "2026-01-01T00:00:00Z".into(),
                composite_bundle_hash: None,
                file_count: 5,
            }],
        };
        let json_str = serde_json::to_string(&original).unwrap();
        let decoded: ProjectDetail = serde_json::from_str(&json_str).unwrap();
        assert_eq!(decoded.project_uuid, "proj-xyz");
        assert_eq!(decoded.versions.len(), 1);
        assert_eq!(
            decoded.metadata.get("client").and_then(|v| v.as_str()),
            Some("Materia Medica")
        );
    }

    #[test]
    fn version_diff_roundtrip() {
        let original = VersionDiff {
            files_only_in_a: vec!["old_channel.json".into()],
            files_only_in_b: vec!["new_channel.json".into()],
            files_changed: vec!["manifest.json".into(), "data.csv".into()],
            files_unchanged: vec!["model.pickle".into()],
        };
        let json_str = serde_json::to_string(&original).unwrap();
        let decoded: VersionDiff = serde_json::from_str(&json_str).unwrap();
        assert_eq!(decoded.files_only_in_a.len(), 1);
        assert_eq!(decoded.files_only_in_b.len(), 1);
        assert_eq!(decoded.files_changed.len(), 2);
        assert_eq!(decoded.files_unchanged.len(), 1);
    }

    #[test]
    fn version_diff_all_empty() {
        let raw = json!({
            "files_only_in_a": [],
            "files_only_in_b": [],
            "files_changed": [],
            "files_unchanged": ["manifest.json"]
        });
        let decoded: VersionDiff = serde_json::from_value(raw).unwrap();
        assert!(decoded.files_only_in_a.is_empty());
        assert_eq!(decoded.files_unchanged.len(), 1);
    }

    #[test]
    fn import_bundle_result_roundtrip() {
        let original = ImportBundleResult {
            project_uuid: "new-proj-uuid".into(),
            version_id: 99,
        };
        let json_str = serde_json::to_string(&original).unwrap();
        let decoded: ImportBundleResult = serde_json::from_str(&json_str).unwrap();
        assert_eq!(decoded.project_uuid, "new-proj-uuid");
        assert_eq!(decoded.version_id, 99);
    }

    #[test]
    fn sample_bundle_result_roundtrip() {
        let original = SampleBundleResult {
            project_uuid: "sample-uuid".into(),
            version_id: 1,
            channels: vec!["TV".into(), "Digital".into(), "OOH".into()],
            n_periods: 24,
        };
        let json_str = serde_json::to_string(&original).unwrap();
        let decoded: SampleBundleResult = serde_json::from_str(&json_str).unwrap();
        assert_eq!(decoded.channels.len(), 3);
        assert_eq!(decoded.n_periods, 24);
        assert_eq!(decoded.channels[1], "Digital");
    }

    #[test]
    fn sample_bundle_result_empty_channels() {
        let raw = json!({
            "project_uuid": "empty-uuid",
            "version_id": 2,
            "channels": [],
            "n_periods": 0
        });
        let decoded: SampleBundleResult = serde_json::from_value(raw).unwrap();
        assert!(decoded.channels.is_empty());
        assert_eq!(decoded.n_periods, 0);
    }
}
