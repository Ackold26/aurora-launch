//! Crash dump panic handler (Phase 0.3).
//!
//! Installs a `std::panic::set_hook` that writes a structured JSON crash dump
//! to `%LOCALAPPDATA%/Aurora Launch/crashes/crash-{ts}.dump` before the
//! process aborts. On next start, `commands::crash_recovery::list_pending_crashes`
//! discovers these files and surfaces them в the UI for support submission.
//!
//! Crash dump payload:
//! ```json
//! {
//!   "schema_version": 1,
//!   "timestamp_utc": "2026-05-14T12:34:56.789Z",
//!   "app_version": "0.1.0",
//!   "build_profile": "production",
//!   "panic": {
//!     "message": "...",
//!     "location": {
//!       "file": "src/foo.rs",
//!       "line": 42,
//!       "column": 7
//!     },
//!     "thread": "tokio-runtime-worker"
//!   },
//!   "system": {
//!     "os": "windows",
//!     "arch": "x86_64",
//!     "process_id": 12345
//!   },
//!   "backtrace": "..."          // captured if RUST_BACKTRACE != "0"
//! }
//! ```
//!
//! Cargo.toml sets `panic = "abort"` for release; the hook still fires
//! BEFORE abort, so the dump is written safely.

use std::backtrace::{Backtrace, BacktraceStatus};
use std::env;
use std::fs;
use std::panic;
use std::path::{Path, PathBuf};
use std::process;
use std::sync::OnceLock;

use chrono::Utc;
use serde::{Deserialize, Serialize};

const CRASH_SCHEMA_VERSION: u32 = 1;
const CRASH_DIR_NAME: &str = "crashes";
const CRASH_FILE_PREFIX: &str = "crash-";
const CRASH_FILE_SUFFIX: &str = ".dump";

/// Maximum size of a single crash dump file in bytes (defensive cap).
const MAX_CRASH_DUMP_BYTES: usize = 256 * 1024;

/// One-shot init guard — `install_panic_hook` should be called once на app start.
static INSTALLED: OnceLock<()> = OnceLock::new();

/// Cached crash directory path — resolved once at install time.
static CRASH_DIR: OnceLock<PathBuf> = OnceLock::new();

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CrashLocation {
    pub file: String,
    pub line: u32,
    pub column: u32,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CrashPanic {
    pub message: String,
    pub location: Option<CrashLocation>,
    pub thread: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CrashSystem {
    pub os: String,
    pub arch: String,
    pub process_id: u32,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CrashDump {
    pub schema_version: u32,
    pub timestamp_utc: String,
    pub app_version: String,
    pub build_profile: String,
    pub panic: CrashPanic,
    pub system: CrashSystem,
    pub backtrace: Option<String>,
}

/// Compute the per-customer crash dump directory.
///
/// Layout:
///   * Windows: `%LOCALAPPDATA%/Aurora Launch/crashes/`
///   * macOS:   `~/Library/Application Support/Aurora Launch/crashes/`
///   * Linux:   `~/.local/share/aurora-launch/crashes/` (XDG_DATA_HOME)
fn resolve_crash_dir() -> PathBuf {
    if let Some(base) = dirs::data_local_dir() {
        return base.join("Aurora Launch").join(CRASH_DIR_NAME);
    }
    // Last-resort fallback — current directory. Should never happen на supported
    // platforms но beats panicking inside the panic hook.
    PathBuf::from(".").join(".aurora-launch").join(CRASH_DIR_NAME)
}

/// Install the global panic hook. Idempotent — second call is a no-op.
pub fn install_panic_hook(app_version: &'static str, build_profile: &'static str) {
    if INSTALLED.set(()).is_err() {
        return; // already installed
    }
    let crash_dir = resolve_crash_dir();
    let _ = CRASH_DIR.set(crash_dir.clone());
    if let Err(e) = fs::create_dir_all(&crash_dir) {
        log::warn!(
            "Cannot create crash dump dir {:?}: {} — crash dumps will be lost",
            crash_dir,
            e
        );
    }

    panic::set_hook(Box::new(move |info| {
        // Build crash dump payload. Every step here must be infallible-ish:
        // we cannot panic inside the panic handler. Errors logged best-effort.
        let dump = build_crash_dump(info, app_version, build_profile);
        if let Some(dir) = CRASH_DIR.get() {
            if let Err(e) = write_crash_dump(dir, &dump) {
                eprintln!("Failed to write crash dump: {e}");
            }
        }
        // Also log to stderr so terminal users / CI logs see it
        eprintln!(
            "Aurora Launch panic [thread={}]: {}",
            dump.panic.thread, dump.panic.message
        );
        if let Some(loc) = &dump.panic.location {
            eprintln!("  at {}:{}:{}", loc.file, loc.line, loc.column);
        }
        if let Some(bt) = &dump.backtrace {
            eprintln!("Backtrace:\n{bt}");
        }
    }));

    log::info!("Panic handler installed (crash dir: {:?})", crash_dir);
}

fn build_crash_dump(
    info: &panic::PanicHookInfo,
    app_version: &str,
    build_profile: &str,
) -> CrashDump {
    let message = panic_payload_to_string(info.payload());
    let location = info.location().map(|loc| CrashLocation {
        file: loc.file().to_string(),
        line: loc.line(),
        column: loc.column(),
    });

    let thread = std::thread::current()
        .name()
        .unwrap_or("unnamed")
        .to_string();

    let backtrace = capture_backtrace();

    CrashDump {
        schema_version: CRASH_SCHEMA_VERSION,
        timestamp_utc: Utc::now().format("%Y-%m-%dT%H:%M:%S%.3fZ").to_string(),
        app_version: app_version.to_string(),
        build_profile: build_profile.to_string(),
        panic: CrashPanic {
            message,
            location,
            thread,
        },
        system: CrashSystem {
            os: std::env::consts::OS.to_string(),
            arch: std::env::consts::ARCH.to_string(),
            process_id: process::id(),
        },
        backtrace,
    }
}

fn panic_payload_to_string(payload: &(dyn std::any::Any + Send)) -> String {
    // Standard pattern — common types для panic payloads are &str and String.
    if let Some(s) = payload.downcast_ref::<&'static str>() {
        return (*s).to_string();
    }
    if let Some(s) = payload.downcast_ref::<String>() {
        return s.clone();
    }
    "Unknown panic payload (not &str or String)".to_string()
}

fn capture_backtrace() -> Option<String> {
    // Respect RUST_BACKTRACE env var (= "0" → disabled).
    if matches!(env::var("RUST_BACKTRACE").as_deref(), Ok("0")) {
        return None;
    }
    let bt = Backtrace::capture();
    match bt.status() {
        BacktraceStatus::Captured => Some(bt.to_string()),
        _ => None,
    }
}

fn crash_filename(timestamp_utc: &str) -> String {
    // Sanitize the timestamp so it's safe as a filename — replace ':' и '.'
    // which Windows treats as path separators.
    let safe = timestamp_utc.replace([':', '.'], "-");
    format!("{CRASH_FILE_PREFIX}{safe}{CRASH_FILE_SUFFIX}")
}

fn write_crash_dump(dir: &Path, dump: &CrashDump) -> std::io::Result<()> {
    // Audit P0-04 fix: atomic write via tmp + rename. fs::write на real path
    // can leave a partial file если process is killed mid-write (panic abort,
    // signal). Atomic rename guarantees readers see either complete file или
    // nothing.
    let json = serde_json::to_vec_pretty(dump)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
    let final_bytes = if json.len() > MAX_CRASH_DUMP_BYTES {
        // Defensive: truncate backtrace and re-serialise. Should be very rare.
        let mut trimmed = dump.clone();
        trimmed.backtrace = Some("(backtrace truncated — dump too large)".to_string());
        serde_json::to_vec_pretty(&trimmed)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?
    } else {
        json
    };

    let path = dir.join(crash_filename(&dump.timestamp_utc));
    let tmp = path.with_extension(format!("dump.{}.tmp", process::id()));
    fs::write(&tmp, &final_bytes)?;
    match fs::rename(&tmp, &path) {
        Ok(()) => Ok(()),
        Err(e) => {
            // Best-effort cleanup of tmp
            let _ = fs::remove_file(&tmp);
            Err(e)
        }
    }
}

/// Crash recovery: enumerate pending dump files. Used by IPC command.
pub fn list_pending_dumps() -> Vec<PathBuf> {
    let Some(dir) = CRASH_DIR.get().cloned().or_else(|| Some(resolve_crash_dir())) else {
        return Vec::new();
    };
    let Ok(entries) = fs::read_dir(&dir) else {
        return Vec::new();
    };
    let mut paths: Vec<PathBuf> = entries
        .filter_map(|r| r.ok())
        .map(|e| e.path())
        .filter(|p| {
            p.is_file()
                && p.file_name()
                    .and_then(|n| n.to_str())
                    .is_some_and(|n| n.starts_with(CRASH_FILE_PREFIX) && n.ends_with(CRASH_FILE_SUFFIX))
        })
        .collect();
    paths.sort_by(|a, b| b.file_name().cmp(&a.file_name())); // newest first
    paths
}

/// Read a single dump file и return its parsed CrashDump payload.
pub fn read_dump(path: &Path) -> std::io::Result<CrashDump> {
    let bytes = fs::read(path)?;
    serde_json::from_slice(&bytes)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))
}

/// Delete a dump file (after customer dismisses or submits to support).
pub fn dismiss_dump(path: &Path) -> std::io::Result<()> {
    match fs::remove_file(path) {
        Ok(()) => Ok(()),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(()), // idempotent
        Err(e) => Err(e),
    }
}

/// Get the resolved crash directory (after install). Returns None если не installed.
pub fn crash_dir() -> Option<PathBuf> {
    CRASH_DIR.get().cloned()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex;

    // Tests serialise through this lock — panic_handler.rs uses global state
    // (OnceLock + std::panic::set_hook) so concurrent test execution is unsafe.
    static TEST_LOCK: Mutex<()> = Mutex::new(());

    #[test]
    fn crash_filename_sanitizes_colons() {
        let name = crash_filename("2026-05-14T12:34:56.789Z");
        assert!(!name.contains(':'));
        assert!(name.starts_with("crash-"));
        assert!(name.ends_with(".dump"));
    }

    #[test]
    fn write_and_read_dump_roundtrip() {
        let _guard = TEST_LOCK.lock().unwrap();
        let tmp = tempfile::tempdir().expect("tmpdir");
        let dump = CrashDump {
            schema_version: CRASH_SCHEMA_VERSION,
            timestamp_utc: "2026-05-14T12-34-56-789Z".to_string(),
            app_version: "0.1.0-test".to_string(),
            build_profile: "test".to_string(),
            panic: CrashPanic {
                message: "test panic".to_string(),
                location: Some(CrashLocation {
                    file: "src/foo.rs".to_string(),
                    line: 42,
                    column: 7,
                }),
                thread: "main".to_string(),
            },
            system: CrashSystem {
                os: "test-os".to_string(),
                arch: "test-arch".to_string(),
                process_id: 1234,
            },
            backtrace: Some("stack frame 1\nstack frame 2".to_string()),
        };
        write_crash_dump(tmp.path(), &dump).expect("write");
        let listed: Vec<_> = fs::read_dir(tmp.path())
            .unwrap()
            .filter_map(|e| e.ok())
            .map(|e| e.path())
            .collect();
        assert_eq!(listed.len(), 1);
        let read_back = read_dump(&listed[0]).expect("read");
        assert_eq!(read_back.app_version, "0.1.0-test");
        assert_eq!(read_back.panic.message, "test panic");
        assert_eq!(read_back.panic.location.as_ref().unwrap().line, 42);
    }

    #[test]
    fn dismiss_dump_is_idempotent() {
        let _guard = TEST_LOCK.lock().unwrap();
        let tmp = tempfile::tempdir().expect("tmpdir");
        let nonexistent = tmp.path().join("crash-never-existed.dump");
        // Should not error на missing file
        dismiss_dump(&nonexistent).expect("idempotent");
    }

    #[test]
    fn panic_payload_to_string_handles_str() {
        let payload: Box<dyn std::any::Any + Send> = Box::new("static str panic");
        assert_eq!(panic_payload_to_string(&*payload), "static str panic");
    }

    #[test]
    fn panic_payload_to_string_handles_string() {
        let payload: Box<dyn std::any::Any + Send> = Box::new(String::from("owned string panic"));
        assert_eq!(panic_payload_to_string(&*payload), "owned string panic");
    }

    #[test]
    fn panic_payload_to_string_handles_unknown() {
        let payload: Box<dyn std::any::Any + Send> = Box::new(42_i32);
        assert!(panic_payload_to_string(&*payload).contains("Unknown panic payload"));
    }

    #[test]
    fn list_pending_dumps_sorts_newest_first() {
        let _guard = TEST_LOCK.lock().unwrap();
        let tmp = tempfile::tempdir().expect("tmpdir");
        // Override CRASH_DIR for test — note: this is a one-shot OnceLock, so
        // we can't safely use install_panic_hook here. Instead we test the
        // listing logic directly с a tmp directory.
        for ts in ["2026-05-14T10-00-00-000Z", "2026-05-14T11-00-00-000Z", "2026-05-14T09-00-00-000Z"] {
            let path = tmp.path().join(crash_filename(ts));
            fs::write(&path, b"{}").unwrap();
        }
        // Reproduce list_pending_dumps logic over tmp
        let mut paths: Vec<_> = fs::read_dir(tmp.path())
            .unwrap()
            .filter_map(|e| e.ok())
            .map(|e| e.path())
            .filter(|p| {
                p.file_name()
                    .and_then(|n| n.to_str())
                    .is_some_and(|n| n.starts_with(CRASH_FILE_PREFIX) && n.ends_with(CRASH_FILE_SUFFIX))
            })
            .collect();
        paths.sort_by(|a, b| b.file_name().cmp(&a.file_name()));
        assert_eq!(paths.len(), 3);
        // Newest first: 11-00 > 10-00 > 09-00
        assert!(paths[0].file_name().unwrap().to_str().unwrap().contains("11-00"));
        assert!(paths[2].file_name().unwrap().to_str().unwrap().contains("09-00"));
    }
}
