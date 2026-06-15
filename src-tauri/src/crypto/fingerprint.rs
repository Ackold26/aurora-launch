//! Machine fingerprint for licence binding.
//!
//! Ported from Econometrica `src-tauri/src/crypto/fingerprint.rs` (fleet
//! signing & licensing unification, Phase B). Adapted to Launch's error model
//! (`anyhow::Result` internally; mapped to `AuroraError` at the command/licence
//! boundary) — the donor's `coded_err`/`ErrorCode` infra is not present here.
//!
//! Licence binding uses the **double hash**: `hash_fingerprint(get_machine_fingerprint())`
//! (= `licenses.fingerprint_hash` on the fleet Supabase backend AND the offline
//! `license.json` `machine_fingerprint_hash`). Keep this algorithm byte-identical
//! to the fleet so the same issuer can sign Launch licences.

use anyhow::{anyhow, Result};
use log::info;
use sha2::{Digest, Sha256};
use std::sync::OnceLock;

/// Cached fingerprint - WMI queries are expensive (~100ms each), called 6+ times per session.
static FINGERPRINT_CACHE: OnceLock<String> = OnceLock::new();

/// Collects machine-unique identifiers and produces a SHA-256 fingerprint.
/// Components: Machine UUID + Disk Serial + Motherboard Serial.
/// Result is cached after first computation (hardware doesn't change at runtime).
pub fn get_machine_fingerprint() -> Result<String> {
    if let Some(cached) = FINGERPRINT_CACHE.get() {
        return Ok(cached.clone());
    }
    let components = collect_hw_ids()?;
    let mut hasher = Sha256::new();
    for component in &components {
        hasher.update(component.as_bytes());
        hasher.update(b"|");
    }
    let hash = hasher.finalize();
    let fp = hex::encode(hash);
    let _ = FINGERPRINT_CACHE.set(fp.clone());
    Ok(fp)
}

#[cfg(windows)]
fn collect_hw_ids() -> Result<Vec<String>> {
    // Run WMI queries in a separate thread to avoid COM threading conflicts with Tauri
    std::thread::spawn(collect_hw_ids_inner)
        .join()
        .map_err(|_| anyhow!("WMI thread panicked"))?
}

#[cfg(windows)]
fn collect_hw_ids_inner() -> Result<Vec<String>> {
    use serde::Deserialize;
    use wmi::{COMLibrary, WMIConnection};

    let com = COMLibrary::new().map_err(|e| anyhow!("COM init failed: {e}"))?;
    let wmi_con = WMIConnection::new(com).map_err(|e| anyhow!("WMI connect failed: {e}"))?;

    let mut ids = Vec::new();

    // Machine UUID
    #[derive(Deserialize)]
    #[serde(rename_all = "PascalCase")]
    struct CsProduct {
        #[serde(rename = "UUID")]
        uuid: String,
    }

    if let Ok(results) = wmi_con.raw_query::<CsProduct>("SELECT UUID FROM Win32_ComputerSystemProduct") {
        if let Some(item) = results.first() {
            let uuid = item.uuid.trim();
            info!("WMI UUID: {:?}", uuid);
            if !uuid.is_empty() {
                ids.push(format!("machine-uuid:{uuid}"));
            }
        }
    }

    // Disk serial (sorted by Index for deterministic selection across processes)
    #[derive(Deserialize)]
    #[serde(rename_all = "PascalCase")]
    struct DiskDrive {
        serial_number: Option<String>,
        index: u32,
    }

    if let Ok(mut results) = wmi_con.raw_query::<DiskDrive>("SELECT SerialNumber, Index FROM Win32_DiskDrive") {
        results.sort_by_key(|d| d.index);
        info!("WMI Win32_DiskDrive: {} disk(s)", results.len());
        for (i, d) in results.iter().enumerate() {
            info!("  disk[{}]: Index={}, serial={:?}", i, d.index, d.serial_number);
        }
        if let Some(item) = results.iter().find(|d| {
            d.serial_number.as_ref().is_some_and(|s| !s.trim().is_empty())
        }) {
            let serial = item.serial_number.as_ref().unwrap().trim();
            ids.push(format!("disk-serial:{serial}"));
        }
    }

    // Motherboard serial
    #[derive(Deserialize)]
    #[serde(rename_all = "PascalCase")]
    struct BaseBoard {
        serial_number: Option<String>,
    }

    if let Ok(results) = wmi_con.raw_query::<BaseBoard>("SELECT SerialNumber FROM Win32_BaseBoard") {
        if let Some(item) = results.first() {
            if let Some(ref serial) = item.serial_number {
                let serial = serial.trim();
                info!("WMI BaseBoard serial: {:?}", serial);
                if !serial.is_empty() {
                    ids.push(format!("board-serial:{serial}"));
                }
            }
        }
    }

    if ids.is_empty() {
        return Err(anyhow!("Failed to collect any hardware identifiers"));
    }

    info!("Fingerprint components ({}): {:?}", ids.len(), ids);
    Ok(ids)
}

#[cfg(target_os = "macos")]
fn collect_hw_ids() -> Result<Vec<String>> {
    let mut ids = Vec::new();

    // IOPlatformUUID via ioreg
    if let Ok(output) = std::process::Command::new("ioreg")
        .args(["-rd1", "-c", "IOPlatformExpertDevice"])
        .output()
    {
        let text = String::from_utf8_lossy(&output.stdout);
        for line in text.lines() {
            if line.contains("IOPlatformUUID") {
                if let Some(uuid) = line.split('"').nth(3) {
                    let uuid = uuid.trim();
                    if !uuid.is_empty() {
                        ids.push(format!("machine-uuid:{uuid}"));
                    }
                }
            }
        }
    }

    // Disk serial via diskutil
    if let Ok(output) = std::process::Command::new("diskutil")
        .args(["info", "disk0"])
        .output()
    {
        let text = String::from_utf8_lossy(&output.stdout);
        for line in text.lines() {
            if line.contains("Disk / Partition UUID") || line.contains("Volume UUID") {
                if let Some(serial) = line.split(':').nth(1) {
                    let serial = serial.trim();
                    if !serial.is_empty() {
                        ids.push(format!("disk-serial:{serial}"));
                        break;
                    }
                }
            }
        }
    }

    // Board serial via system_profiler
    if let Ok(output) = std::process::Command::new("system_profiler")
        .args(["SPHardwareDataType"])
        .output()
    {
        let text = String::from_utf8_lossy(&output.stdout);
        for line in text.lines() {
            if line.contains("Serial Number") {
                if let Some(serial) = line.split(':').nth(1) {
                    let serial = serial.trim();
                    if !serial.is_empty() {
                        ids.push(format!("board-serial:{serial}"));
                    }
                }
            }
        }
    }

    if ids.is_empty() {
        return Err(anyhow!("Failed to collect any hardware identifiers on macOS"));
    }

    Ok(ids)
}

#[cfg(not(any(windows, target_os = "macos")))]
fn collect_hw_ids() -> Result<Vec<String>> {
    Err(anyhow!("Machine fingerprinting is only supported on Windows and macOS"))
}

/// Produce a hex-encoded SHA-256 hash of a fingerprint string (for license matching).
pub fn hash_fingerprint(fingerprint: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(fingerprint.as_bytes());
    hex::encode(hasher.finalize())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hash_fingerprint_is_deterministic_sha256() {
        // sha256("abc") — guards the hashing contract against accidental change.
        let h = hash_fingerprint("abc");
        assert_eq!(
            h,
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
        assert_eq!(hash_fingerprint("abc"), hash_fingerprint("abc"));
    }

    /// Manual helper: prints THIS dev box's licensing hash so a test licence can
    /// be issued against it. Ignored by default (hits WMI). Run with:
    ///   cargo test print_dev_fingerprint_hash -- --ignored --nocapture
    #[test]
    #[ignore = "prints this machine's licensing fingerprint hash for test-licence issuance"]
    fn print_dev_fingerprint_hash() {
        let fp = get_machine_fingerprint().expect("get_machine_fingerprint");
        let hash = hash_fingerprint(&fp);
        println!("AURORA_LAUNCH_MACHINE_FINGERPRINT = {fp}");
        println!("AURORA_LAUNCH_LICENSING_HASH (= licenses.fingerprint_hash) = {hash}");
    }
}
