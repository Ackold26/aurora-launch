//! Licence resolution — fleet model, consuming the Core `aurora_fleet` crate.
//!
//! Resolution order (fail-closed):
//!   0. dev-bypass gate (BUILD_PROFILE=="dev" AND AURORA_LAUNCH_LICENSE_BYPASS) → all features
//!   1. online: Supabase `/auth` via `aurora_fleet::online_auth` (cabinets + expires_at), 24h disk cache
//!   2. offline fallback: local Ed25519 `license.json` via `aurora_fleet::license` (fleet pubkey)
//!
//! Cutover 2026-06-14: the offline `License` / canonical-JSON / Ed25519 verify,
//! the online `/auth` flow, and the machine fingerprint are no longer app-local
//! copies — they come from the Core SSOT crate `aurora_fleet`. This module is now
//! the thin app-side glue: product identity (`"launch"`), the dev-bypass gate, the
//! `LicenseStatusPayload` the frontend consumes, tier mapping, the in-memory
//! resolution cache, and the Tauri command surface.
//!
//! `has_feature(f)` = membership of `f` in the resolved `cabinets`. In every
//! denied state the resolved cabinets are empty, so the membership test denies —
//! fail-closed by construction.
//!
//! NOTE: the crate's offline `validate(build_date)` also runs an anti-rollback
//! clock check (LI-009). Launch does not yet embed a build date, so we call
//! `validate_without_rollback_check()` to preserve Phase B behaviour exactly;
//! wiring `BUILD_TIMESTAMP` to re-gain LI-009 is a separate hardening follow-up.

use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};
use tauri::Manager;

use aurora_fleet::license::License as FleetLicense;
use aurora_fleet::online_auth;

use crate::errors::{AuroraError, AuroraResult};

/// Launch feature set (cabinet ids). Dev-bypass grants all of these.
const ALL_FEATURES: &[&str] = &["launch_core", "launch_proxy_single", "launch_proxy_multi"];

/// Launch's server-side product id — the `product` arg the shared `online_auth`
/// crate now takes explicitly (the donor derived it from `CARGO_PKG_NAME`).
fn product() -> &'static str {
    "launch"
}

/// In-memory cache of the resolved status so feature checks within a session do
/// not each trigger a network round-trip. Bounded by a short TTL; cleared on
/// licence import. (online_auth keeps a separate 24h disk cache for offline use.)
static RESOLVED_CACHE: Mutex<Option<(Instant, LicenseStatusPayload)>> = Mutex::new(None);
const RESOLVED_TTL: Duration = Duration::from_secs(300);

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct LicenseStatusPayload {
    pub state: String, // active | grace | expired | invalid | no_license | degraded
    pub tier: Option<String>,
    pub enabled_features: Vec<String>,
    pub detail: String,
    pub is_offline_grace: bool,
    pub valid_until: Option<String>,
}

// ── Dev-bypass gate ──────────────────────────────────────────────────────────

/// Dev-bypass predicate, factored pure so the gate is testable without mutating
/// the process env or the compile-time profile: bypass is allowed ONLY when the
/// build profile is `dev` AND the runtime env var is present.
fn bypass_allowed(build_profile: &str, env_present: bool) -> bool {
    build_profile == "dev" && env_present
}

/// Dev-bypass double gate: compile-time profile must be `dev` AND the runtime
/// env var must be set. On a production install the profile is `production`
/// (embedded by build.rs) so the env var is ignored entirely.
fn dev_bypass_active() -> bool {
    bypass_allowed(
        crate::BUILD_PROFILE,
        std::env::var("AURORA_LAUNCH_LICENSE_BYPASS").is_ok(),
    )
}

// ── Helpers ──────────────────────────────────────────────────────────────────

fn tier_from_cabinets(cabinets: &[String]) -> Option<String> {
    if cabinets.iter().any(|c| c == "launch_proxy_multi") {
        Some("pro".to_string())
    } else if cabinets.iter().any(|c| c == "launch_proxy_single") {
        Some("starter".to_string())
    } else if !cabinets.is_empty() {
        Some("custom".to_string())
    } else {
        None
    }
}

fn granted(cabinets: Vec<String>, valid_until: Option<String>, grace: bool, detail: &str) -> LicenseStatusPayload {
    LicenseStatusPayload {
        state: if grace { "grace".to_string() } else { "active".to_string() },
        tier: tier_from_cabinets(&cabinets),
        enabled_features: cabinets,
        detail: detail.to_string(),
        is_offline_grace: grace,
        valid_until,
    }
}

fn denied(state: &str, detail: &str, valid_until: Option<String>, grace: bool) -> LicenseStatusPayload {
    LicenseStatusPayload {
        state: state.to_string(),
        tier: None,
        enabled_features: vec![],
        detail: detail.to_string(),
        is_offline_grace: grace,
        valid_until,
    }
}

/// Map a fleet offline-validation `[LI-xxx]` error string to Launch's
/// (state, RU detail). Unknown / signature failures fail-closed to `invalid`.
fn map_offline_error(err: &str) -> (&'static str, String) {
    if err.contains("LI-005") {
        ("expired", "Срок действия лицензии истёк".to_string())
    } else if err.contains("LI-006") {
        ("invalid", "Лицензия привязана к другому устройству".to_string())
    } else if err.contains("LI-008") {
        ("invalid", "Некорректный формат даты окончания лицензии".to_string())
    } else if err.contains("LI-009") {
        ("invalid", "Системные часы выставлены некорректно. Проверьте дату и время.".to_string())
    } else {
        ("invalid", "Подпись лицензии недействительна".to_string())
    }
}

/// Resolve the licence status: dev-bypass → online (crate) → offline Ed25519 (crate).
async fn resolve_status(app_config_dir: &Path) -> LicenseStatusPayload {
    if dev_bypass_active() {
        return LicenseStatusPayload {
            state: "active".to_string(),
            tier: Some("dev_bypass".to_string()),
            enabled_features: ALL_FEATURES.iter().map(|s| s.to_string()).collect(),
            detail: "DEV bypass активен (build_profile=dev)".to_string(),
            is_offline_grace: false,
            valid_until: None,
        };
    }

    let online = online_auth::authorize(app_config_dir, env!("CARGO_PKG_VERSION"), "", product()).await;
    match online.status.as_str() {
        "ok" => granted(online.cabinets, online.expires_at, false, "Лицензия активна"),
        "cached" => granted(online.cabinets, online.expires_at, false, "Лицензия активна (кэш)"),
        "blocked" => {
            let msg = online.message.unwrap_or_default();
            let state = if msg.to_lowercase().contains("истек") { "expired" } else { "no_license" };
            let detail = if msg.is_empty() {
                "Лицензия не подтверждена сервером".to_string()
            } else {
                msg
            };
            denied(state, &detail, None, false)
        }
        // "offline" — server unreachable AND no fresh cache → offline Ed25519 (crate).
        _ => match FleetLicense::load(app_config_dir) {
            Ok(lic) => match lic.validate_without_rollback_check() {
                Ok(st) if st.valid => granted(
                    st.cabinets,
                    Some(st.expires_at),
                    true,
                    "Офлайн-режим: лицензия подтверждена локально",
                ),
                Ok(st) => {
                    let (state, detail) = map_offline_error(st.error.as_deref().unwrap_or(""));
                    let valid_until = if st.expires_at.is_empty() { None } else { Some(st.expires_at) };
                    denied(state, &detail, valid_until, true)
                }
                Err(e) => denied("invalid", &format!("Лицензия недействительна: {e}"), None, true),
            },
            Err(_) => denied(
                "no_license",
                "Лицензия не найдена. Импортируйте лицензию в настройках.",
                None,
                false,
            ),
        },
    }
}

/// Resolve with the short in-memory cache (one network round-trip per TTL).
async fn resolve_cached(app_config_dir: &Path) -> LicenseStatusPayload {
    {
        let guard = RESOLVED_CACHE.lock().unwrap();
        if let Some((at, payload)) = guard.as_ref() {
            if at.elapsed() < RESOLVED_TTL {
                return payload.clone();
            }
        }
    }
    let payload = resolve_status(app_config_dir).await;
    *RESOLVED_CACHE.lock().unwrap() = Some((Instant::now(), payload.clone()));
    payload
}

fn invalidate_cache() {
    *RESOLVED_CACHE.lock().unwrap() = None;
}

fn config_dir(app: &tauri::AppHandle) -> AuroraResult<PathBuf> {
    app.path()
        .app_config_dir()
        .map_err(|e| AuroraError::Other(format!("config dir unavailable: {e}")))
}

// ── Commands (surface preserved) ───────────────────────────────────────────

#[tauri::command]
pub async fn current_license_status(app: tauri::AppHandle) -> AuroraResult<LicenseStatusPayload> {
    let dir = config_dir(&app)?;
    Ok(resolve_cached(&dir).await)
}

#[tauri::command]
pub async fn has_feature(app: tauri::AppHandle, feature: String) -> AuroraResult<bool> {
    let dir = config_dir(&app)?;
    let status = resolve_cached(&dir).await;
    // cabinets are empty in every denied state → fail-closed.
    Ok(status.enabled_features.iter().any(|f| f == &feature))
}

#[tauri::command]
pub async fn require_feature(app: tauri::AppHandle, feature: String) -> AuroraResult<()> {
    let dir = config_dir(&app)?;
    let status = resolve_cached(&dir).await;
    if status.enabled_features.iter().any(|f| f == &feature) {
        Ok(())
    } else {
        Err(AuroraError::LicenseFeatureRequired {
            feature,
            current_state: status.state,
        })
    }
}

#[tauri::command]
pub async fn is_dev_build() -> AuroraResult<bool> {
    // Compile-time embedded profile — cannot be flipped at runtime.
    Ok(crate::BUILD_PROFILE == "dev")
}

/// Import an offline Ed25519 `license.json`: verify signature + machine binding
/// (via the fleet crate) before saving to the per-app config dir. Invalidates the
/// resolution cache. Uses `validate_without_rollback_check` to match resolution
/// (anti-rollback LI-009 is a deferred hardening — see module note).
#[tauri::command]
pub fn import_license(path: String, app: tauri::AppHandle) -> AuroraResult<()> {
    let dir = config_dir(&app)?;
    let data = std::fs::read_to_string(&path)
        .map_err(|e| AuroraError::Other(format!("Не удалось прочитать файл лицензии: {e}")))?;
    let lic: FleetLicense = serde_json::from_str(&data)
        .map_err(|e| AuroraError::Other(format!("Некорректный файл лицензии: {e}")))?;

    let st = lic
        .validate_without_rollback_check()
        .map_err(|e| AuroraError::Other(format!("Лицензия недействительна: {e}")))?;
    if !st.valid {
        let reason = st.error.unwrap_or_else(|| "Неизвестная ошибка".to_string());
        return Err(AuroraError::Other(format!("Лицензия недействительна: {reason}")));
    }

    let dest = FleetLicense::license_path(&dir);
    if let Some(parent) = dest.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| AuroraError::Other(format!("Не удалось создать каталог лицензии: {e}")))?;
    }
    std::fs::copy(&path, &dest)
        .map_err(|e| AuroraError::Other(format!("Не удалось сохранить лицензию: {e}")))?;
    invalidate_cache();
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tier_derivation() {
        assert_eq!(tier_from_cabinets(&["launch_core".into(), "launch_proxy_multi".into()]), Some("pro".to_string()));
        assert_eq!(tier_from_cabinets(&["launch_core".into(), "launch_proxy_single".into()]), Some("starter".to_string()));
        assert_eq!(tier_from_cabinets(&["launch_core".into()]), Some("custom".to_string()));
        assert_eq!(tier_from_cabinets(&[]), None);
    }

    #[test]
    fn dev_bypass_gate_requires_both_dev_profile_and_env() {
        // Ported from the retired Python `TestAuditB1LicenseBypassGate`
        // (engines/license_validator.py) on its 2026-06-14 removal: the
        // dev-bypass must require BOTH the `dev` build profile AND the env var,
        // and a `production` build can never bypass even with the env set.
        assert!(bypass_allowed("dev", true), "dev profile + env set → bypass on");
        assert!(!bypass_allowed("dev", false), "dev profile, no env → no bypass");
        assert!(
            !bypass_allowed("production", true),
            "production refuses bypass even with env (audit B1 gate)"
        );
        assert!(!bypass_allowed("production", false), "production, no env → no bypass");
    }

    #[test]
    fn offline_error_mapping() {
        // Pin the LI-code → (state, RU detail) glue mapping; unknown fails closed.
        assert_eq!(map_offline_error("[LI-005] License has expired").0, "expired");
        assert_eq!(map_offline_error("[LI-006] bound to a different machine").0, "invalid");
        assert_eq!(map_offline_error("[LI-007] signature invalid").0, "invalid");
        assert_eq!(map_offline_error("").0, "invalid");
    }

    /// Live integration smoke against the prod Supabase `/auth` Edge Function via
    /// the fleet crate, using THIS dev box's fingerprint + the Starter test
    /// licence. Ignored (network + machine-specific). Validates the Core SSOT
    /// under a live consumer. Run:
    ///   cargo test live_online_auth_smoke -- --ignored --nocapture
    #[tokio::test]
    #[ignore = "live: hits prod Supabase /auth with this dev box's fingerprint via the crate"]
    async fn live_online_auth_smoke() {
        let dir = std::env::temp_dir().join("aurora-launch-auth-smoke");
        std::fs::create_dir_all(&dir).unwrap();
        let status = online_auth::authorize(&dir, env!("CARGO_PKG_VERSION"), "", product()).await;
        println!(
            "online_auth (fleet crate): status={} available={} cabinets={:?} expires={:?} msg={:?}",
            status.status, status.available, status.cabinets, status.expires_at, status.message
        );
        assert_eq!(status.status, "ok", "prod backend must authorize the test licence via the crate");
        assert!(status.cabinets.iter().any(|c| c == "launch_proxy_single"), "Starter grants proxy_single");
        assert!(!status.cabinets.iter().any(|c| c == "launch_proxy_multi"), "Starter must NOT grant proxy_multi");
    }

    /// Offline Ed25519 smoke against a REAL fleet-signed `license.json`
    /// (machine-bound to this dev box) via the fleet crate. Ignored — needs the
    /// signed file. Run:
    ///   AURORA_LAUNCH_TEST_LICENSE_DIR=<dir-with-license.json> \
    ///   cargo test live_offline_license_smoke -- --ignored --nocapture
    #[test]
    #[ignore = "offline: needs a fleet-signed license.json via AURORA_LAUNCH_TEST_LICENSE_DIR"]
    fn live_offline_license_smoke() {
        let dir = match std::env::var("AURORA_LAUNCH_TEST_LICENSE_DIR") {
            Ok(d) => std::path::PathBuf::from(d),
            Err(_) => {
                eprintln!("skip: set AURORA_LAUNCH_TEST_LICENSE_DIR to a dir containing license.json");
                return;
            }
        };
        let lic = FleetLicense::load(&dir).expect("license.json present and parseable");
        let st = lic.validate_without_rollback_check().expect("validate returns Ok");
        println!(
            "offline validate (fleet crate): valid={} cabinets={:?} err={:?}",
            st.valid, st.cabinets, st.error
        );
        assert!(st.valid, "fleet-signed licence for this machine must validate (got: {:?})", st.error);
        assert!(st.cabinets.iter().any(|c| c == "launch_proxy_single"), "Starter grants proxy_single");
        assert!(!st.cabinets.iter().any(|c| c == "launch_proxy_multi"), "Starter must NOT grant proxy_multi");
    }
}
