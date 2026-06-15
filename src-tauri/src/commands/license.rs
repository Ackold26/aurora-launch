//! Licence resolution — fleet model (Phase B of the signing & licensing
//! unification migration).
//!
//! Resolution order (fail-closed):
//!   0. dev-bypass gate (BUILD_PROFILE=="dev" AND AURORA_LAUNCH_LICENSE_BYPASS) → all features
//!   1. online: Supabase `/auth` (cabinets + expires_at), 24h disk cache
//!   2. offline fallback: local Ed25519 `license.json` (fleet pubkey)
//!
//! `has_feature(f)` = membership of `f` in the resolved `cabinets`. In every
//! denied state (`blocked` / `expired` / `invalid` / `no_license`) the resolved
//! cabinets are empty, so the membership test denies — fail-closed by construction.
//!
//! Replaces the previous Python-sidecar delegation. The Python
//! `engines/license_validator.py` + the sidecar `get_license_status` /
//! `has_license_feature` handlers it superseded were retired 2026-06-14 once
//! this Rust path was verified live (online + offline Ed25519 smoke).
//!
//! The frontend contract (`LicenseStatusPayload`) is unchanged — the commands
//! now take `AppHandle` (Tauri-injected) instead of the sidecar `State`, which
//! is transparent to the JS callers.

use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use base64::Engine;
use chrono::NaiveDate;
use serde::{Deserialize, Serialize};
use tauri::Manager;

use crate::commands::online_auth;
use crate::crypto::{ed25519, fingerprint};
use crate::errors::{AuroraError, AuroraResult};

/// Launch feature set (cabinet ids). Dev-bypass grants all of these.
const ALL_FEATURES: &[&str] = &["launch_core", "launch_proxy_single", "launch_proxy_multi"];

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

// ── Offline Ed25519 licence (ported from Econometrica license.rs) ──────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct License {
    pub license_id: String,
    pub issued_to: String,
    pub expires_at: String, // YYYY-MM-DD
    pub machine_fingerprint_hash: String,
    pub cabinets: Vec<String>,
    pub salt: String,      // base64
    pub signature: String, // base64 Ed25519 over canonical JSON
}

/// Result of validating an offline licence. Never errors — fail-closed with
/// `valid=false` so callers can map to a denied state.
struct OfflineValidation {
    valid: bool,
    state: String, // active | expired | invalid
    cabinets: Vec<String>,
    expires_at: String,
    detail: String,
}

impl License {
    fn license_path(app_config_dir: &Path) -> PathBuf {
        app_config_dir.join("license.json")
    }

    fn load(app_config_dir: &Path) -> Option<Self> {
        let data = std::fs::read_to_string(Self::license_path(app_config_dir)).ok()?;
        serde_json::from_str(&data).ok()
    }

    /// Canonical JSON for signing/verification: sorted keys, no signature field.
    /// Must stay byte-identical to the fleet issuer (gen_license).
    fn canonical_json(&self) -> String {
        format!(
            r#"{{"cabinets":{cabinets},"expires_at":"{expires}","issued_to":"{issued}","license_id":"{id}","machine_fingerprint_hash":"{fp}","salt":"{salt}"}}"#,
            cabinets = serde_json::to_string(&self.cabinets).unwrap_or_else(|_| "[]".to_string()),
            expires = self.expires_at,
            issued = self.issued_to,
            id = self.license_id,
            fp = self.machine_fingerprint_hash,
            salt = self.salt,
        )
    }

    /// Validate machine binding, expiry, then Ed25519 signature. Fail-closed.
    ///
    /// NOTE: the donor also gates on a `BUILD_TIMESTAMP` clock-sanity check
    /// (rejects a system clock set earlier than the build). Launch's build.rs
    /// does not embed that env, so it is omitted here — a possible future
    /// hardening (the online path is clock-authoritative server-side anyway).
    fn validate(&self) -> OfflineValidation {
        let fail = |state: &str, detail: &str| OfflineValidation {
            valid: false,
            state: state.to_string(),
            cabinets: vec![],
            expires_at: self.expires_at.clone(),
            detail: detail.to_string(),
        };

        // 1. machine binding
        let machine_fp_hash = match fingerprint::get_machine_fingerprint() {
            Ok(fp) => fingerprint::hash_fingerprint(&fp),
            Err(_) => return fail("invalid", "Не удалось определить отпечаток устройства"),
        };
        if self.machine_fingerprint_hash != machine_fp_hash {
            return fail("invalid", "Лицензия привязана к другому устройству");
        }

        // 2. expiry
        let expires = match NaiveDate::parse_from_str(&self.expires_at, "%Y-%m-%d") {
            Ok(d) => d,
            Err(_) => return fail("invalid", "Некорректный формат даты окончания лицензии"),
        };
        if chrono::Local::now().date_naive() > expires {
            return fail("expired", "Срок действия лицензии истёк");
        }

        // 3. Ed25519 signature over canonical JSON
        let sig_bytes = match base64::engine::general_purpose::STANDARD.decode(&self.signature) {
            Ok(b) => b,
            Err(_) => return fail("invalid", "Некорректная подпись лицензии (base64)"),
        };
        let sig_ok = ed25519::verify_signature(self.canonical_json().as_bytes(), &sig_bytes)
            .unwrap_or(false);
        if !sig_ok {
            return fail("invalid", "Подпись лицензии недействительна");
        }

        OfflineValidation {
            valid: true,
            state: "active".to_string(),
            cabinets: self.cabinets.clone(),
            expires_at: self.expires_at.clone(),
            detail: "Лицензия подтверждена локально".to_string(),
        }
    }
}

// ── Helpers ────────────────────────────────────────────────────────────────

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

/// Resolve the licence status: dev-bypass → online → offline Ed25519.
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

    let online = online_auth::authorize(app_config_dir, env!("CARGO_PKG_VERSION"), "").await;
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
        // "offline" — server unreachable AND no fresh cache → offline Ed25519
        _ => match License::load(app_config_dir) {
            Some(lic) => {
                let v = lic.validate();
                if v.valid {
                    granted(v.cabinets, Some(v.expires_at), true, "Офлайн-режим: лицензия подтверждена локально")
                } else {
                    let valid_until = if v.expires_at.is_empty() { None } else { Some(v.expires_at) };
                    denied(&v.state, &v.detail, valid_until, true)
                }
            }
            None => denied(
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
/// before saving to the per-app config dir. Invalidates the resolution cache.
#[tauri::command]
pub fn import_license(path: String, app: tauri::AppHandle) -> AuroraResult<()> {
    let dir = config_dir(&app)?;
    let data = std::fs::read_to_string(&path)
        .map_err(|e| AuroraError::Other(format!("Не удалось прочитать файл лицензии: {e}")))?;
    let lic: License = serde_json::from_str(&data)
        .map_err(|e| AuroraError::Other(format!("Некорректный файл лицензии: {e}")))?;

    let v = lic.validate();
    if !v.valid {
        return Err(AuroraError::Other(format!("Лицензия недействительна: {}", v.detail)));
    }

    let dest = License::license_path(&dir);
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
    fn invalid_signature_fails_closed() {
        // Wrong machine binding → invalid, no cabinets (fail-closed). Uses the
        // real machine fingerprint so the binding check trips on the bogus hash.
        let lic = License {
            license_id: "test".into(),
            issued_to: "test".into(),
            expires_at: "2099-01-01".into(),
            machine_fingerprint_hash: "0".repeat(64),
            cabinets: vec!["launch_core".into(), "launch_proxy_multi".into()],
            salt: "AAAA".into(),
            signature: base64::engine::general_purpose::STANDARD.encode([0u8; 64]),
        };
        let v = lic.validate();
        assert!(!v.valid);
        assert!(v.cabinets.is_empty(), "denied validation must expose no cabinets");
        assert_eq!(v.state, "invalid");
    }

    #[test]
    fn expired_offline_licence_is_expired_state() {
        // Past expiry → expired (binding check first; use the real hash so we
        // reach the expiry branch).
        let fp = fingerprint::get_machine_fingerprint().unwrap();
        let fp_hash = fingerprint::hash_fingerprint(&fp);
        let lic = License {
            license_id: "t".into(),
            issued_to: "t".into(),
            expires_at: "2000-01-01".into(),
            machine_fingerprint_hash: fp_hash,
            cabinets: vec!["launch_core".into()],
            salt: "AAAA".into(),
            signature: base64::engine::general_purpose::STANDARD.encode([0u8; 64]),
        };
        let v = lic.validate();
        assert!(!v.valid);
        assert_eq!(v.state, "expired");
        assert!(v.cabinets.is_empty());
    }

    /// Offline Ed25519 smoke against a REAL fleet-signed `license.json`
    /// (machine-bound to this dev box). Ignored — needs the signed file. Run:
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
        let lic = License::load(&dir).expect("license.json present and parseable");
        let v = lic.validate();
        println!(
            "offline validate: valid={} state={} cabinets={:?} detail={}",
            v.valid, v.state, v.cabinets, v.detail
        );
        assert!(v.valid, "fleet-signed licence for this machine must validate (got: {})", v.detail);
        assert!(v.cabinets.iter().any(|c| c == "launch_proxy_single"), "Starter grants proxy_single");
        assert!(!v.cabinets.iter().any(|c| c == "launch_proxy_multi"), "Starter must NOT grant proxy_multi");
    }
}
