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

    // ── Sprint 6 D7 #41 — spawn_blocking refactor tests ─────────────────

    use sha2::Digest;
    use std::io::Write;

    /// Helper: build minimal valid .aurora bundle для testing _blocking helpers.
    fn build_test_bundle(dir: &std::path::Path, name: &str) -> PathBuf {
        let entry_content = b"hello world".to_vec();
        let entry_sha = hex::encode(sha2::Sha256::digest(&entry_content));
        let manifest = serde_json::json!({
            "manifest_version": "1.0",
            "schema_version": "3.0",
            "revision": 0,
            "files": {
                "data.txt": {
                    "sha256": entry_sha,
                    "size_bytes": entry_content.len() as u64,
                }
            },
        });
        let manifest_bytes = serde_json::to_vec_pretty(&manifest).unwrap();

        let bundle_path = dir.join(name);
        let file = std::fs::File::create(&bundle_path).unwrap();
        let mut zip = zip::ZipWriter::new(file);
        let opts: zip::write::SimpleFileOptions = zip::write::SimpleFileOptions::default()
            .compression_method(zip::CompressionMethod::Stored);
        zip.start_file(MANIFEST_FILENAME, opts).unwrap();
        zip.write_all(&manifest_bytes).unwrap();
        zip.start_file("data.txt", opts).unwrap();
        zip.write_all(&entry_content).unwrap();
        zip.finish().unwrap();
        bundle_path
    }

    #[test]
    fn open_bundle_blocking_returns_handle_for_valid_zip() {
        let dir = tempfile::tempdir().unwrap();
        let bundle = build_test_bundle(dir.path(), "test.aurora");
        let result =
            open_bundle_blocking(bundle.to_string_lossy().to_string()).expect("open succeeds");
        assert_eq!(result.0.source_format, "zip");
        assert!(result.0.size_bytes > 0);
        assert_eq!(result.0.revision, 0);
        assert!(!result.2.is_empty(), "handle_id non-empty");
    }

    #[test]
    fn open_bundle_blocking_rejects_nonexistent_path() {
        let dir = tempfile::tempdir().unwrap();
        let bogus = dir.path().join("ghost.aurora");
        let result = open_bundle_blocking(bogus.to_string_lossy().to_string());
        assert!(matches!(result, Err(AuroraError::BundleNotFound { .. })));
    }

    #[test]
    fn list_bundle_entries_blocking_returns_entries() {
        let dir = tempfile::tempdir().unwrap();
        let bundle = build_test_bundle(dir.path(), "test.aurora");
        let entries = list_bundle_entries_blocking(bundle).expect("list succeeds");
        assert_eq!(entries.len(), 1, "manifest.json filtered out");
        assert_eq!(entries[0], "data.txt");
    }

    #[test]
    fn read_bundle_entry_blocking_returns_payload() {
        let dir = tempfile::tempdir().unwrap();
        let bundle = build_test_bundle(dir.path(), "test.aurora");
        let manifest_files = serde_json::json!({
            "data.txt": {
                "sha256": hex::encode(sha2::Sha256::digest(b"hello world")),
                "size_bytes": 11_u64,
            }
        });
        let payload = read_bundle_entry_blocking(bundle, manifest_files, "data.txt".into())
            .expect("read succeeds");
        assert_eq!(payload.entry, "data.txt");
        assert_eq!(payload.size_bytes, 11);
        assert_eq!(payload.sha256_hex.len(), 64);
    }

    #[test]
    fn concurrent_blocking_helpers_do_not_starve_runtime() {
        // INV-48 attack scenario для #41 (Tokio worker starvation): без
        // spawn_blocking wrap, 4 parallel async calls к open/list/read would
        // each block runtime worker. С wrap — все progress concurrently.
        //
        // Test verifies _blocking helpers callable from multi_thread runtime
        // с only 2 workers + 4 concurrent tasks через spawn_blocking. Without
        // wrap (если refactor regresses) — potential deadlock либо severe latency.
        let dir = tempfile::tempdir().unwrap();
        let bundle = build_test_bundle(dir.path(), "concurrent.aurora");

        let rt = tokio::runtime::Builder::new_multi_thread()
            .worker_threads(2)
            .enable_all()
            .build()
            .unwrap();

        let bundle_path = bundle.clone();
        let results: Vec<bool> = rt.block_on(async move {
            let p1 = bundle_path.clone();
            let p2 = bundle_path.clone();
            let p3 = bundle_path.clone();
            let p4 = bundle_path.clone();
            let h1 = tokio::task::spawn_blocking(move || list_bundle_entries_blocking(p1));
            let h2 = tokio::task::spawn_blocking(move || list_bundle_entries_blocking(p2));
            let h3 = tokio::task::spawn_blocking(move || list_bundle_entries_blocking(p3));
            let h4 = tokio::task::spawn_blocking(move || list_bundle_entries_blocking(p4));
            let (r1, r2, r3, r4) = tokio::join!(h1, h2, h3, h4);
            vec![
                r1.unwrap().is_ok(),
                r2.unwrap().is_ok(),
                r3.unwrap().is_ok(),
                r4.unwrap().is_ok(),
            ]
        });

        assert_eq!(results.len(), 4);
        for (i, ok) in results.into_iter().enumerate() {
            assert!(ok, "concurrent task {i} should succeed");
        }
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
    // Sprint 6 D7 #41 — spawn_blocking wrap. open_bundle does std::fs::metadata
    // + ZIP read + zip-slip validation — all sync I/O blocking Tokio worker.
    // Pattern mirrors Sprint 5 D4 H2 verify_reproducibility refactor.
    let (summary, handle, handle_id) =
        tokio::task::spawn_blocking(move || open_bundle_blocking(path))
            .await
            .map_err(|e| AuroraError::Other(format!("open_bundle task panicked: {e}")))??;

    state
        .bundles
        .lock()
        .map_err(|_| AuroraError::Other("bundle map poisoned".into()))?
        .insert(handle_id, handle);

    Ok(summary)
}

fn open_bundle_blocking(
    path: String,
) -> AuroraResult<(BundleHandleSummary, OpenBundleHandle, String)> {
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
        path: path.display().to_string(),
    };

    let handle = OpenBundleHandle {
        path: path.clone(),
        manifest_json,
        source_format: "zip".into(),
        size_bytes: metadata.len(),
        revision,
    };

    Ok((summary, handle, handle_id))
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
    let path = {
        let bundles = state
            .bundles
            .lock()
            .map_err(|_| AuroraError::Other("bundle map poisoned".into()))?;
        let handle = bundles
            .get(&handle_id)
            .ok_or(AuroraError::BundleHandleInvalid {
                handle_id: handle_id.clone(),
            })?;
        handle.path.clone()
    };

    // Sprint 6 D7 #41 — spawn_blocking wrap. ZIP re-open + central directory
    // read can stall на large bundles. Same pattern as open_bundle/verify_reproducibility.
    tokio::task::spawn_blocking(move || list_bundle_entries_blocking(path))
        .await
        .map_err(|e| AuroraError::Other(format!("list_bundle_entries task panicked: {e}")))?
}

fn list_bundle_entries_blocking(path: PathBuf) -> AuroraResult<Vec<String>> {
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
    let (path, manifest_files) = {
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
        (path, manifest_files)
    };

    // Sprint 6 D7 #41 — spawn_blocking wrap. read_bundle_entry does std::fs +
    // ZIP read + SHA-256 hash + base64 encode для potentially large entry —
    // blocking Tokio worker. Same pattern as Sprint 5 D4 H2.
    tokio::task::spawn_blocking(move || {
        read_bundle_entry_blocking(path, manifest_files, entry)
    })
    .await
    .map_err(|e| AuroraError::Other(format!("read_bundle_entry task panicked: {e}")))?
}

fn read_bundle_entry_blocking(
    path: PathBuf,
    manifest_files: serde_json::Value,
    entry: String,
) -> AuroraResult<BundleEntryPayload> {
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
    state: State<'_, AppState>,
    sidecar: State<'_, std::sync::Arc<crate::sidecar::SidecarManager>>,
    handle_id: String,
    target_path: String,
    extra_files_base64: Option<std::collections::HashMap<String, String>>,
    expected_revision: Option<i64>,
) -> AuroraResult<serde_json::Value> {
    // Block 4 Phase 2: route save_bundle через Python sidecar JSON-RPC.
    // Sidecar wraps BundleZipWriter с atomic write + rolling backup +
    // optimistic concurrency check (revision counter).
    let source_path = {
        let bundles = state
            .bundles
            .lock()
            .map_err(|_| AuroraError::Other("bundle map poisoned".into()))?;
        match bundles.get(&handle_id) {
            Some(handle) => Some(handle.path.clone()),
            None => None, // Initial save (no source bundle yet) — sidecar handles fresh-create branch
        }
    };

    let mut params = serde_json::json!({
        "target_path": target_path,
    });
    if let Some(p) = source_path {
        params["source_path"] = serde_json::Value::String(p.display().to_string());
    } else {
        // POST_PILOT_BACKLOG B4-MED-4 close (2026-05-10): explicit JSON null
        // вместо empty-string sentinel. Path("") behavior на Windows fragile;
        // null = unambiguous "no source bundle yet".
        params["source_path"] = serde_json::Value::Null;
    }
    if let Some(rev) = expected_revision {
        params["expected_revision"] = serde_json::Value::Number(rev.into());
    }
    if let Some(extras) = extra_files_base64 {
        params["extra_files"] = serde_json::to_value(extras)
            .map_err(|e| AuroraError::Other(format!("extras serialise: {e}")))?;
    }

    sidecar
        .invoke::<serde_json::Value>("save_bundle", params)
        .await
}
