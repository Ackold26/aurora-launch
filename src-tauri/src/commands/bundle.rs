//! Bundle IPC commands — handle-based lazy access (Block 2 audit decision D7).
//!
//! `open_bundle(path)` returns small `BundleHandleSummary { handle_id,
//! manifest, ... }`. Frontend reads entries on demand с
//! `read_bundle_entry(handle_id, entry_path)`. Backend keeps the path +
//! cached manifest; ZIP entries are read fresh on each call (cheap; OS
//! caches recently-read files, ZIP central directory hot).

use std::io::Read;
use std::path::PathBuf;

use serde::{Deserialize, Serialize};
use tauri::State;
use uuid::Uuid;

use crate::errors::{AuroraError, AuroraResult};
use crate::state::{AppState, BundleHandleSummary, OpenBundleHandle};

const MAX_BUNDLE_BYTES: u64 = 2 * 1024 * 1024 * 1024; // 2 GB sanity cap (mirrors Block 1C)
const MAX_MANIFEST_BYTES: u64 = 16 * 1024 * 1024; // 16 MB — Block 3 HIGH-5 fix (was unbounded)
const MAX_ENTRY_BYTES: u64 = 2 * 1024 * 1024 * 1024; // 2 GB — match Python MAX_ENTRY_SIZE
const MANIFEST_FILENAME: &str = "manifest.json";

#[cfg(test)]
mod block_3_tests {
    use super::*;

    #[test]
    fn entry_name_safe_rejects_zip_slip() {
        assert!(!entry_name_safe("/etc/passwd"));
        assert!(!entry_name_safe("\\windows\\system32"));
        assert!(!entry_name_safe("../../etc/passwd"));
        assert!(!entry_name_safe("a/../../b"));
        assert!(!entry_name_safe("C:\\evil"));
        assert!(!entry_name_safe("data\0null"));
    }

    #[test]
    fn entry_name_safe_accepts_normal_paths() {
        assert!(entry_name_safe("data.json"));
        assert!(entry_name_safe("models/proxy.pickle"));
        assert!(entry_name_safe("nested/deeply/file.bin"));
    }
}

/// Block 3 HIGH-1 fix: zip-slip defense (mirrors Python eager + lazy readers).
/// ZIP entry names must NOT contain absolute paths, parent traversal, drive
/// letters, or null bytes. Defense-in-depth even though Rust IPC reads bytes
/// (not extracts to disk) — frontend may later persist bytes к user-chosen
/// path using entry name; trust boundary is at parse time.
fn entry_name_safe(name: &str) -> bool {
    if name.starts_with('/') || name.starts_with('\\') {
        return false;
    }
    if name.contains('\0') {
        return false;
    }
    if name.contains(':') {
        return false; // Windows drive letter / alternate data stream
    }
    for component in name.split(|c| c == '/' || c == '\\') {
        if component == ".." {
            return false;
        }
    }
    true
}

#[tauri::command]
pub async fn open_bundle(
    state: State<'_, AppState>,
    path: String,
) -> AuroraResult<BundleHandleSummary> {
    let path = PathBuf::from(path);
    if !path.exists() {
        return Err(AuroraError::BundleNotFound {
            path: path.display().to_string(),
        });
    }

    let metadata = std::fs::metadata(&path)?;
    if metadata.len() > MAX_BUNDLE_BYTES {
        return Err(AuroraError::FileTooLarge {
            size: metadata.len(),
            cap: MAX_BUNDLE_BYTES,
        });
    }

    let file = std::fs::File::open(&path)?;
    let mut archive = zip::ZipArchive::new(file).map_err(|e| AuroraError::BundleFormat {
        reason: format!("cannot open ZIP: {e}"),
    })?;

    // Block 1D B4 fix mirror: detect duplicate entries upfront
    let names: Vec<String> = archive.file_names().map(String::from).collect();
    let unique: std::collections::HashSet<&String> = names.iter().collect();
    if names.len() != unique.len() {
        return Err(AuroraError::BundleFormat {
            reason: "duplicate ZIP entries detected — refusing".into(),
        });
    }

    // Block 3 HIGH-1 fix: zip-slip name validation upfront (mirrors Python).
    for name in &names {
        if !entry_name_safe(name) {
            return Err(AuroraError::BundleFormat {
                reason: format!("Suspicious ZIP entry name (zip-slip risk): {name:?}"),
            });
        }
    }

    // Read manifest first (Block 3 HIGH-5 fix: cap manifest size).
    let manifest_json: serde_json::Value = {
        let mut manifest_file = archive.by_name(MANIFEST_FILENAME).map_err(|_| {
            AuroraError::BundleFormat {
                reason: format!("missing {MANIFEST_FILENAME}"),
            }
        })?;
        let manifest_size = manifest_file.size();
        if manifest_size > MAX_MANIFEST_BYTES {
            return Err(AuroraError::BundleFormat {
                reason: format!(
                    "manifest.json too large: {manifest_size} bytes > cap {MAX_MANIFEST_BYTES}"
                ),
            });
        }
        let mut buf = Vec::with_capacity(manifest_size as usize);
        manifest_file.read_to_end(&mut buf)?;
        serde_json::from_slice(&buf)?
    };

    // Block 3 HIGH-2 fix: structural integrity — reject extra files в ZIP not
    // declared в manifest (mirrors Python lazy reader Block 1C). Otherwise
    // malicious bundle с trojan payload bypasses Rust path silently.
    if let Some(files_obj) = manifest_json.get("files").and_then(|v| v.as_object()) {
        let manifest_names: std::collections::HashSet<&String> = files_obj.keys().collect();
        let zip_payload_names: std::collections::HashSet<&String> = names
            .iter()
            .filter(|n| n.as_str() != MANIFEST_FILENAME)
            .collect();
        let extras: Vec<&&String> = zip_payload_names.difference(&manifest_names).collect();
        if !extras.is_empty() {
            return Err(AuroraError::BundleFormat {
                reason: format!(
                    "ZIP contains undeclared entries (manifest mismatch): {extras:?}"
                ),
            });
        }
        let missing: Vec<&&String> = manifest_names.difference(&zip_payload_names).collect();
        if !missing.is_empty() {
            return Err(AuroraError::BundleIntegrity {
                reason: format!(
                    "manifest declares files missing from ZIP: {missing:?}"
                ),
            });
        }
    }

    let revision = manifest_json
        .get("revision")
        .and_then(|v| v.as_i64())
        .unwrap_or(0);

    let handle_id = Uuid::new_v4().to_string();
    let summary = BundleHandleSummary {
        handle_id: handle_id.clone(),
        source_format: "zip".into(),
        size_bytes: metadata.len(),
        revision,
        manifest: manifest_json.clone(),
    };

    let handle = OpenBundleHandle {
        path: path.clone(),
        manifest_json,
        source_format: "zip".into(),
        size_bytes: metadata.len(),
        revision,
    };

    state
        .bundles
        .lock()
        .map_err(|_| AuroraError::Other("bundle map poisoned".into()))?
        .insert(handle_id, handle);

    Ok(summary)
}

#[tauri::command]
pub async fn close_bundle(state: State<'_, AppState>, handle_id: String) -> AuroraResult<()> {
    let mut bundles = state
        .bundles
        .lock()
        .map_err(|_| AuroraError::Other("bundle map poisoned".into()))?;
    bundles.remove(&handle_id).ok_or(AuroraError::BundleHandleInvalid {
        handle_id: handle_id.clone(),
    })?;
    Ok(())
}

#[tauri::command]
pub async fn list_bundle_entries(
    state: State<'_, AppState>,
    handle_id: String,
) -> AuroraResult<Vec<String>> {
    let bundles = state
        .bundles
        .lock()
        .map_err(|_| AuroraError::Other("bundle map poisoned".into()))?;
    let handle = bundles
        .get(&handle_id)
        .ok_or(AuroraError::BundleHandleInvalid {
            handle_id: handle_id.clone(),
        })?;
    let path = handle.path.clone();
    drop(bundles);

    let file = std::fs::File::open(&path)?;
    let archive = zip::ZipArchive::new(file).map_err(|e| AuroraError::BundleFormat {
        reason: format!("re-open ZIP: {e}"),
    })?;
    Ok(archive
        .file_names()
        .filter(|n| *n != MANIFEST_FILENAME)
        .map(String::from)
        .collect())
}

#[derive(Serialize, Deserialize)]
pub struct BundleEntryPayload {
    pub entry: String,
    pub bytes_base64: String,
    pub size_bytes: u64,
    pub sha256_hex: String,
}

#[tauri::command]
pub async fn read_bundle_entry(
    state: State<'_, AppState>,
    handle_id: String,
    entry: String,
) -> AuroraResult<BundleEntryPayload> {
    let bundles = state
        .bundles
        .lock()
        .map_err(|_| AuroraError::Other("bundle map poisoned".into()))?;
    let handle = bundles
        .get(&handle_id)
        .ok_or(AuroraError::BundleHandleInvalid {
            handle_id: handle_id.clone(),
        })?;
    let path = handle.path.clone();
    let manifest_files = handle
        .manifest_json
        .get("files")
        .cloned()
        .unwrap_or(serde_json::Value::Object(Default::default()));
    drop(bundles);

    let entry_meta = manifest_files
        .get(&entry)
        .ok_or(AuroraError::BundleEntryNotFound { entry: entry.clone() })?;

    let expected_size = entry_meta
        .get("size_bytes")
        .and_then(|v| v.as_u64())
        .ok_or(AuroraError::BundleFormat {
            reason: format!("manifest missing size_bytes for {entry}"),
        })?;

    // Block 3 HIGH-5 fix: cap entry size before allocation (defense-in-depth).
    if expected_size > MAX_ENTRY_BYTES {
        return Err(AuroraError::FileTooLarge {
            size: expected_size,
            cap: MAX_ENTRY_BYTES,
        });
    }

    let file = std::fs::File::open(&path)?;
    let mut archive = zip::ZipArchive::new(file).map_err(|e| AuroraError::BundleFormat {
        reason: format!("re-open ZIP: {e}"),
    })?;

    // Zip-bomb defense (mirrors Block 1C B2 fix)
    let zinfo = archive.by_name(&entry).map_err(|_| {
        AuroraError::BundleEntryNotFound {
            entry: entry.clone(),
        }
    })?;
    if zinfo.size() != expected_size {
        return Err(AuroraError::BundleIntegrity {
            reason: format!(
                "ZIP central directory size {} != manifest size {} для {entry}",
                zinfo.size(),
                expected_size
            ),
        });
    }
    drop(zinfo);

    let mut zfile = archive.by_name(&entry).map_err(|_| {
        AuroraError::BundleEntryNotFound {
            entry: entry.clone(),
        }
    })?;
    let mut buf = Vec::with_capacity(expected_size as usize);
    zfile.read_to_end(&mut buf)?;

    if buf.len() as u64 != expected_size {
        return Err(AuroraError::BundleIntegrity {
            reason: format!(
                "decompressed size {} != manifest {} для {entry}",
                buf.len(),
                expected_size
            ),
        });
    }

    // Per-entry SHA-256 verify (BLAKE3 для stronger но manifest uses sha256 чтобы match Python side)
    let expected_sha = entry_meta
        .get("sha256")
        .and_then(|v| v.as_str())
        .ok_or(AuroraError::BundleFormat {
            reason: format!("manifest missing sha256 for {entry}"),
        })?;
    use sha2::Digest;
    let actual = sha2::Sha256::digest(&buf);
    let actual_hex = hex::encode(actual);
    if actual_hex != expected_sha {
        return Err(AuroraError::BundleIntegrity {
            reason: format!(
                "sha256 mismatch для {entry}: expected {}…, got {}…",
                &expected_sha[..16],
                &actual_hex[..16]
            ),
        });
    }

    use base64::{engine::general_purpose::STANDARD, Engine};
    Ok(BundleEntryPayload {
        entry,
        bytes_base64: STANDARD.encode(&buf),
        size_bytes: buf.len() as u64,
        sha256_hex: actual_hex,
    })
}

#[tauri::command]
pub async fn get_manifest(
    state: State<'_, AppState>,
    handle_id: String,
) -> AuroraResult<serde_json::Value> {
    let bundles = state
        .bundles
        .lock()
        .map_err(|_| AuroraError::Other("bundle map poisoned".into()))?;
    let handle = bundles
        .get(&handle_id)
        .ok_or(AuroraError::BundleHandleInvalid {
            handle_id: handle_id.clone(),
        })?;
    Ok(handle.manifest_json.clone())
}

#[tauri::command]
pub async fn save_bundle(
    _state: State<'_, AppState>,
    _handle_id: String,
    _target_path: String,
) -> AuroraResult<serde_json::Value> {
    // Phase B: full save flow goes через Python backend (BundleZipWriter).
    // Block 2A wires это via Tauri sidecar → Python subprocess (deferred Block 4
    // when real adapter integration lands). Block 2 stub:
    Err(AuroraError::Other(
        "save_bundle: deferred Block 4 (Python BundleZipWriter sidecar integration)".into(),
    ))
}
