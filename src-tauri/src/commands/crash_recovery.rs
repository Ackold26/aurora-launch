//! Crash recovery IPC commands (Phase 0.3).
//!
//! Frontend calls these on startup to discover pending crash dumps from a
//! previous unclean exit. Customer sees dialog: "Aurora Launch encountered
//! an issue last time. Review crash report or dismiss?"
//!
//! Commands:
//! - `list_pending_crashes` — enumerate dump files, return summary metadata
//! - `get_crash_details` — load full dump JSON for the support-attachment flow
//! - `dismiss_crash` — delete a single dump (user chose не submit)
//! - `dismiss_all_crashes` — bulk dismiss

use std::path::PathBuf;

use serde::{Deserialize, Serialize};

use crate::errors::{AuroraError, AuroraResult};
use crate::panic_handler::{self, CrashDump};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CrashSummary {
    pub file_path: String,
    pub timestamp_utc: String,
    pub app_version: String,
    pub panic_message: String,
    pub thread: String,
}

#[tauri::command]
pub async fn list_pending_crashes() -> AuroraResult<Vec<CrashSummary>> {
    let dumps = panic_handler::list_pending_dumps();
    let mut summaries = Vec::with_capacity(dumps.len());
    for path in dumps {
        match panic_handler::read_dump(&path) {
            Ok(dump) => summaries.push(CrashSummary {
                file_path: path.to_string_lossy().to_string(),
                timestamp_utc: dump.timestamp_utc,
                app_version: dump.app_version,
                panic_message: truncate(&dump.panic.message, 200),
                thread: dump.panic.thread,
            }),
            Err(e) => {
                log::warn!("Cannot read crash dump {:?}: {}", path, e);
                // Skip corrupted dumps — но don't fail the whole list
            }
        }
    }
    Ok(summaries)
}

#[tauri::command]
pub async fn get_crash_details(file_path: String) -> AuroraResult<CrashDump> {
    let path = PathBuf::from(&file_path);
    validate_inside_crash_dir(&path)?;
    panic_handler::read_dump(&path).map_err(|e| {
        AuroraError::Other(format!("Cannot read crash dump {file_path}: {e}"))
    })
}

#[tauri::command]
pub async fn dismiss_crash(file_path: String) -> AuroraResult<()> {
    let path = PathBuf::from(&file_path);
    validate_inside_crash_dir(&path)?;
    panic_handler::dismiss_dump(&path).map_err(|e| {
        AuroraError::Other(format!("Cannot dismiss crash dump {file_path}: {e}"))
    })
}

#[tauri::command]
pub async fn dismiss_all_crashes() -> AuroraResult<u32> {
    let dumps = panic_handler::list_pending_dumps();
    let mut count = 0;
    for path in dumps {
        if let Err(e) = panic_handler::dismiss_dump(&path) {
            log::warn!("Failed to dismiss {:?}: {}", path, e);
            continue;
        }
        count += 1;
    }
    Ok(count)
}

/// Guard against path traversal: the file must reside inside the resolved
/// crash directory. Frontend should never pass a path obtained from anywhere
/// other than list_pending_crashes, но we double-check.
fn validate_inside_crash_dir(path: &std::path::Path) -> AuroraResult<()> {
    let Some(crash_dir) = panic_handler::crash_dir() else {
        return Err(AuroraError::Other(
            "Crash handler not initialised — cannot validate path".to_string(),
        ));
    };
    // Canonicalise both sides где возможно. If the path doesn't exist
    // (already dismissed) we still want consistent behaviour, поэтому fall
    // back to parent comparison.
    let canon_dir = crash_dir.canonicalize().unwrap_or(crash_dir.clone());
    let canon_path = path
        .canonicalize()
        .or_else(|_| {
            path.parent()
                .map(|p| p.canonicalize())
                .unwrap_or_else(|| Ok(path.to_path_buf()))
                .map(|parent| parent.join(path.file_name().unwrap_or_default()))
        })
        .unwrap_or_else(|_| path.to_path_buf());

    if !canon_path.starts_with(&canon_dir) {
        return Err(AuroraError::Other(format!(
            "Path {} is outside crash dump directory",
            path.display()
        )));
    }
    Ok(())
}

fn truncate(s: &str, max: usize) -> String {
    if s.len() <= max {
        return s.to_string();
    }
    // Character boundary safe truncation
    let mut end = max;
    while !s.is_char_boundary(end) && end > 0 {
        end -= 1;
    }
    let mut out = s[..end].to_string();
    out.push_str("…");
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn truncate_short() {
        assert_eq!(truncate("short", 10), "short");
    }

    #[test]
    fn truncate_long() {
        let s = "a".repeat(300);
        let t = truncate(&s, 100);
        // 100 ASCII chars + ellipsis
        assert!(t.starts_with(&"a".repeat(100)));
        assert!(t.ends_with('…'));
    }

    #[test]
    fn truncate_handles_multibyte() {
        // Cyrillic 2-byte chars — must not split в middle
        let s = "Лонч Планер — это продукт для прогноза новых брендов";
        let t = truncate(s, 20);
        // Either fits within 20 bytes OR is shorter due к boundary search;
        // either way, must be valid UTF-8
        assert!(t.is_char_boundary(t.len()));
    }
}
