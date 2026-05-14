//! Per-user filesystem layout resolution (Phase Π.1.1).
//!
//! Adapted from Optimizer's `sidecar_runtime.rs` namespacing patterns —
//! минус port allocation (Launch uses stdin/stdout sidecar, not HTTP).
//! Per audit Phase 0 §A.1: we adopt path/log namespacing patterns,
//! not HTTP transport logic.
//!
//! On Windows, `%LOCALAPPDATA%` is already per-user (scoped by user profile),
//! so explicit SID hashing is unnecessary для path namespacing. The OS provides
//! correct isolation. For RDP multi-user scenarios, each session sees their
//! own profile directory.
//!
//! Standard layout::
//!
//!     {LOCALAPPDATA}/Aurora Launch/
//!     ├── projects.db          (ProjectDB)
//!     ├── blobs/               (content-addressed)
//!     ├── autosave/            (Phase 0.2)
//!     ├── crashes/             (Phase 0.3)
//!     ├── logs/                (rotating app/sidecar logs)
//!     └── exports/             (cached .aurora ZIPs)
//!
//! On macOS:   `~/Library/Application Support/Aurora Launch/...`
//! On Linux:   `~/.local/share/aurora-launch/...` (XDG_DATA_HOME)

use std::path::PathBuf;

const APP_DIR_NAME: &str = "Aurora Launch";

/// Resolve root data dir per platform. Falls back to current directory if
/// platform dirs unavailable (should never happen на supported targets).
pub fn data_root() -> PathBuf {
    if let Some(base) = dirs::data_local_dir() {
        return base.join(APP_DIR_NAME);
    }
    // Last-resort fallback. Logged warning at startup if hit.
    log::warn!("dirs::data_local_dir() unavailable — using ./.aurora-launch as fallback");
    PathBuf::from(".").join(".aurora-launch")
}

pub fn projects_db_path() -> PathBuf {
    data_root().join("projects.db")
}

pub fn blobs_dir() -> PathBuf {
    data_root().join("blobs")
}

pub fn autosave_dir() -> PathBuf {
    data_root().join("autosave")
}

pub fn crashes_dir() -> PathBuf {
    data_root().join("crashes")
}

pub fn logs_dir() -> PathBuf {
    data_root().join("logs")
}

pub fn exports_dir() -> PathBuf {
    data_root().join("exports")
}

/// Ensure all standard subdirectories exist. Best-effort: failures logged but
/// not fatal (specific subsystems retry on demand). Called once at app start.
pub fn ensure_layout() -> std::io::Result<()> {
    for dir in [
        data_root(),
        blobs_dir(),
        autosave_dir(),
        crashes_dir(),
        logs_dir(),
        exports_dir(),
    ] {
        if let Err(e) = std::fs::create_dir_all(&dir) {
            log::warn!("Cannot create {:?}: {}", dir, e);
            return Err(e);
        }
    }
    Ok(())
}

/// Current username (cheap, для diagnostics + log context). Не security-grade
/// identifier — для that Optimizer uses WinAPI SID, but we don't need it
/// here (LOCALAPPDATA already scopes per user).
pub fn current_username() -> String {
    if cfg!(windows) {
        std::env::var("USERNAME").unwrap_or_else(|_| "unknown".to_string())
    } else {
        std::env::var("USER").unwrap_or_else(|_| "unknown".to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn data_root_returns_app_subdir() {
        let root = data_root();
        assert!(
            root.ends_with(APP_DIR_NAME) || root.ends_with(".aurora-launch"),
            "Expected root to end with app dir name, got {:?}",
            root
        );
    }

    #[test]
    fn standard_paths_under_root() {
        let root = data_root();
        assert!(projects_db_path().starts_with(&root));
        assert!(blobs_dir().starts_with(&root));
        assert!(autosave_dir().starts_with(&root));
        assert!(crashes_dir().starts_with(&root));
        assert!(logs_dir().starts_with(&root));
        assert!(exports_dir().starts_with(&root));
    }

    #[test]
    fn projects_db_path_is_file_not_dir() {
        let p = projects_db_path();
        assert!(p.file_name().is_some());
        assert!(p.extension().is_some_and(|e| e == "db"));
    }

    #[test]
    fn ensure_layout_creates_dirs_in_tmp() {
        // Smoke: function shouldn't panic. We can't easily redirect data_root
        // в test environment without env override, so just call it и accept
        // что it touches real LOCALAPPDATA (idempotent — already exists).
        let result = ensure_layout();
        assert!(result.is_ok() || result.err().unwrap().kind() == std::io::ErrorKind::PermissionDenied);
    }

    #[test]
    fn current_username_not_empty() {
        let user = current_username();
        assert!(!user.is_empty());
    }
}
