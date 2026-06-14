//! Aurora Launch auto-updater — fleet checksum model.
//!
//! Ported from Econometrica `src-tauri/src/commands/updater.rs` (fleet
//! unification migration, 2026-06-14). Replaces `tauri-plugin-updater` +
//! minisign: update integrity = SHA256 checksum delivered in the server JSON
//! (Supabase Edge Function `app-update` → `app_versions`, with GitHub Pages
//! `latest.json` fallback). No signature plugin, no minisign keypair.
//!
//! Product id = `env!("CARGO_PKG_NAME")` = `"aurora-launch"`. Fleet convention:
//! the updater queries with the raw cargo package name (NOT the short
//! `detect_product()` name used for licensing) — this matches the
//! `app_versions` row `product='aurora-launch'` and the GH-Pages folder
//! `rosst-updates/aurora-launch/`.
//!
//! Тhe Tauri command wrappers (`check_update` / `download_update` /
//! `apply_update`) live in `lib.rs`, mirroring the donor split.

use std::path::{Path, PathBuf};
use std::sync::Arc;

use log::info;
use serde::{Deserialize, Serialize};
use sha2::Digest;
use tauri::{AppHandle, Emitter, Manager};

use crate::errors::{AuroraError, AuroraResult};
use crate::sidecar::SidecarManager;

/// Build an `AuroraError::UpdateFailed` with the donor's UP0xx diagnostic code.
fn up_err(code: &str, msg: impl Into<String>) -> AuroraError {
    AuroraError::UpdateFailed {
        code: code.to_string(),
        message: msg.into(),
    }
}

fn update_base_url() -> String {
    obfstr::obfstr!("https://ackold26.github.io/rosst-updates").to_string()
}

fn supabase_update_url() -> String {
    obfstr::obfstr!("https://quzhkfvglqmppxcrindh.supabase.co/functions/v1/app-update").to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VersionInfo {
    pub version: String,
    pub download_url: String,
    #[serde(default)]
    pub release_notes: String,
    #[serde(default)]
    pub mandatory: bool,
    #[serde(default)]
    pub checksum: String,
    #[serde(default)]
    pub min_version: String,
}

/// Check for updates via Supabase Edge Function.
async fn check_supabase(product: &str) -> AuroraResult<VersionInfo> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .map_err(|e| up_err("UP001", format!("HTTP client build failed: {e}")))?;

    let resp = client
        .post(supabase_update_url())
        .json(&serde_json::json!({ "product": product }))
        .send()
        .await
        .map_err(|e| up_err("UP001", format!("Supabase /app-update request failed: {e}")))?;

    if !resp.status().is_success() {
        return Err(up_err(
            "UP001",
            format!("Supabase /app-update returned {}", resp.status()),
        ));
    }

    resp.json()
        .await
        .map_err(|e| up_err("UP001", format!("Supabase /app-update parse failed: {e}")))
}

/// Check for updates via GitHub Pages manifest (fallback).
async fn check_github_pages(product: &str) -> AuroraResult<VersionInfo> {
    let url = format!("{}/{}/latest.json", update_base_url(), product);

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .map_err(|e| up_err("UP001", format!("HTTP client build failed: {e}")))?;

    let resp = client
        .get(&url)
        .send()
        .await
        .map_err(|e| up_err("UP001", format!("GitHub Pages request failed: {e}")))?;

    if !resp.status().is_success() {
        return Err(up_err(
            "UP001",
            format!("Update server returned {}", resp.status()),
        ));
    }

    resp.json()
        .await
        .map_err(|e| up_err("UP001", format!("GitHub Pages parse failed: {e}")))
}

/// Check if a newer version is available.
/// Tries Supabase first, falls back to GitHub Pages.
/// Returns `Some(VersionInfo)` if update available, `None` if current.
pub async fn check_for_updates(current_version: &str) -> AuroraResult<Option<VersionInfo>> {
    let product = env!("CARGO_PKG_NAME");

    let info = match check_supabase(product).await {
        Ok(info) => info,
        Err(e) => {
            info!("UP005: Supabase update check failed ({e}), falling back to GitHub Pages");
            check_github_pages(product).await?
        }
    };

    if is_newer(&info.version, current_version) {
        Ok(Some(info))
    } else {
        Ok(None)
    }
}

/// Download update .exe to a temp directory, emitting `update-progress` events.
pub async fn download_update(url: &str, app_handle: &AppHandle) -> AuroraResult<PathBuf> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(600))
        .build()
        .map_err(|e| up_err("UP002", format!("HTTP client build failed: {e}")))?;

    let resp = client
        .get(url)
        .send()
        .await
        .map_err(|e| up_err("UP002", format!("Download failed: {e}")))?;

    if !resp.status().is_success() {
        return Err(up_err("UP002", format!("Download returned {}", resp.status())));
    }

    let total_size = resp.content_length().unwrap_or(0);
    let temp_dir = tempfile::Builder::new()
        .prefix("aurora-update-")
        .tempdir()
        .map_err(|e| up_err("UP002", format!("Failed to create temp dir: {e}")))?;
    let temp_dir_path = temp_dir.keep();

    // Extract filename from URL
    let filename = url.rsplit('/').next().unwrap_or("update-setup.exe");
    let dest_path = temp_dir_path.join(filename);

    let mut file = tokio::fs::File::create(&dest_path)
        .await
        .map_err(|e| up_err("UP002", format!("Failed to create temp file: {e}")))?;
    let mut downloaded: u64 = 0;

    use futures_util::StreamExt;
    use tokio::io::AsyncWriteExt;
    let mut stream = resp.bytes_stream();

    while let Some(chunk) = stream.next().await {
        let chunk = chunk.map_err(|e| up_err("UP002", format!("Download stream error: {e}")))?;
        file.write_all(&chunk)
            .await
            .map_err(|e| up_err("UP002", format!("Write chunk failed: {e}")))?;
        downloaded += chunk.len() as u64;

        // Emit progress
        let progress = if total_size > 0 {
            (downloaded as f64 / total_size as f64 * 100.0) as u32
        } else {
            0
        };
        let _ = app_handle.emit(
            "update-progress",
            serde_json::json!({
                "downloaded": downloaded,
                "total": total_size,
                "percent": progress
            }),
        );
    }
    file.flush()
        .await
        .map_err(|e| up_err("UP002", format!("Flush failed: {e}")))?;

    info!("Update downloaded: {} ({} bytes)", dest_path.display(), downloaded);
    Ok(dest_path)
}

/// Verify SHA256 checksum of a downloaded file.
pub fn verify_checksum(file_path: &Path, expected: &str) -> AuroraResult<()> {
    if expected.is_empty() {
        return Err(up_err(
            "UP003",
            "Update checksum is missing - refusing to install unverified update",
        ));
    }

    // Strip "sha256:" prefix if present
    let expected_hash = expected.strip_prefix("sha256:").unwrap_or(expected);

    let data = std::fs::read(file_path)
        .map_err(|e| up_err("UP003", format!("Failed to read file for checksum: {e}")))?;
    let hash = sha2::Sha256::digest(&data);
    let actual = hex::encode(hash);

    if actual != expected_hash.to_lowercase() {
        return Err(up_err(
            "UP003",
            format!(
                "Download integrity check failed. Expected: {}..., got: {}...",
                &expected_hash[..12.min(expected_hash.len())],
                &actual[..12]
            ),
        ));
    }

    info!("Checksum verified: {}", &actual[..16]);
    Ok(())
}

/// Launch the installer silently, stop the sidecar (release file locks), exit.
///
/// Ordering (donor audit fix, 2026-05-23): launch-then-shutdown-then-exit.
/// PowerShell `Start-Process … -Verb RunAs` is run with a BLOCKING `.status()`
/// so we only proceed once UAC is granted and the installer process spawned.
/// If the user denies UAC, PowerShell exits 1 → we return `Err`, the sidecar
/// stays alive and the app remains functional (no dead state).
///
/// Then we stop the sidecar so NSIS can overwrite the locked
/// `aurora-sidecar.exe` / bundled `.pyd` files. Launch ships an
/// `installer_hooks.nsh` PREINSTALL `taskkill` as a safety net (manual
/// installer run / race), but this Rust path is the primary lock-release.
pub async fn apply_update(installer_path: &Path, app_handle: &AppHandle) -> AuroraResult<()> {
    if !installer_path.exists() {
        return Err(up_err(
            "UP004",
            format!("Installer not found: {}", installer_path.display()),
        ));
    }

    info!("Applying update: {}", installer_path.display());

    // Launch installer with elevation; block until PowerShell confirms UAC
    // granted + installer process spawned. PS exits 1 if UAC denied OR
    // Start-Process fails → we return Err, sidecar stays alive, app functional.
    let installer_str = installer_path.display().to_string().replace('\'', "''");
    let ps_status = std::process::Command::new("powershell")
        .args([
            "-NoProfile",
            "-Command",
            &format!(
                "try {{ Start-Process -FilePath '{}' -ArgumentList '/S' -Verb RunAs -ErrorAction Stop }} catch {{ exit 1 }}",
                installer_str
            ),
        ])
        .status()
        .map_err(|e| up_err("UP004", format!("Failed to launch PowerShell: {e}")))?;

    if !ps_status.success() {
        return Err(up_err(
            "UP004",
            "Installer launch failed (UAC denied or PowerShell error). App remains functional — please retry update.",
        ));
    }

    info!("Installer elevated successfully; stopping sidecar to release file locks");

    // Stop the sidecar so its `aurora-sidecar.exe` / `.pyd` locks are released
    // before NSIS reaches the file-copy stage. Clone the Arc out of state and
    // drop the borrow before awaiting (State not held across .await).
    let manager = app_handle
        .try_state::<Arc<SidecarManager>>()
        .map(|s| Arc::clone(s.inner()));
    if let Some(manager) = manager {
        manager.shutdown().await;
    }

    // Brief pause so the UI can paint "installing" and the sidecar fully exits
    // before the installer overwrites files.
    std::thread::sleep(std::time::Duration::from_secs(2));

    // Exit current process to allow installer to replace files.
    std::process::exit(0);
}

/// Semver comparison с учётом prerelease: returns true if `remote` > `current`.
///
/// Старая версия делала `split('.').filter_map(parse::<u32>)` и МОЛЧА отбрасывала
/// хвост `0-rc11` → "2.1.0-rc11" и "2.1.0-rc10" оба сводились к `[2,1]` → считались
/// равными → rc→rc авто-апдейт НИКОГДА не срабатывал (баг найден на rc10→rc11,
/// Econometrica 2026-06-13, commit 8dfc631). Теперь база и prerelease сравниваются
/// раздельно:
///   - stable (без `-`) ранжируется ВЫШЕ любого prerelease той же базы (rank = u32::MAX);
///   - `rc11` > `rc10` (числовой хвост тега, не лексический — иначе "rc2" > "rc10");
///   - база ("2.1.0") доминирует над prerelease-рангом.
fn is_newer(remote: &str, current: &str) -> bool {
    fn parse(v: &str) -> (Vec<u32>, u32) {
        let v = v.trim_start_matches('v');
        let (base, pre_rank) = match v.split_once('-') {
            Some((b, tag)) => {
                // rc11 → 11, beta3 → 3, без цифр → 0. Всегда < u32::MAX (= release).
                let n = tag
                    .chars()
                    .filter(|c| c.is_ascii_digit())
                    .collect::<String>()
                    .parse()
                    .unwrap_or(0);
                (b, n)
            }
            None => (v, u32::MAX), // нет prerelease = stable релиз
        };
        let nums = base.split('.').filter_map(|s| s.parse().ok()).collect();
        (nums, pre_rank)
    }
    parse(remote) > parse(current)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn version_comparison() {
        assert!(is_newer("0.2.0", "0.1.0"));
        assert!(is_newer("1.0.0", "0.9.9"));
        assert!(is_newer("v0.1.1", "0.1.0"));
        assert!(!is_newer("0.1.0", "0.1.0"));
        assert!(!is_newer("0.0.9", "0.1.0"));
    }

    #[test]
    fn version_not_newer_than_self() {
        // Одинаковая версия НЕ является более новой
        assert!(!is_newer("0.2.0", "0.2.0"));
        assert!(!is_newer("1.0.0", "1.0.0"));
        assert!(!is_newer("v0.0.1", "0.0.1"));
    }

    #[test]
    fn version_comparison_prerelease() {
        // rc → rc одной базы: раньше оба сводились к [2,1] и считались равными (баг rc10→rc11).
        assert!(is_newer("2.1.0-rc11", "2.1.0-rc10"));
        assert!(!is_newer("2.1.0-rc10", "2.1.0-rc11"));
        assert!(!is_newer("2.1.0-rc11", "2.1.0-rc11"));
        // числовой хвост, не лексический: rc2 < rc10
        assert!(!is_newer("2.1.0-rc2", "2.1.0-rc10"));
        assert!(is_newer("2.1.0-rc10", "2.1.0-rc2"));
        // stable > любой prerelease той же базы; prerelease < stable
        assert!(is_newer("2.1.0", "2.1.0-rc11"));
        assert!(!is_newer("2.1.0-rc11", "2.1.0"));
        // числовая база доминирует над prerelease-рангом
        assert!(is_newer("2.2.0-rc1", "2.1.0-rc11"));
        assert!(is_newer("2.1.0-rc1", "2.0.0"));
    }
}
