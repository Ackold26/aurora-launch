//! Online authorization (fleet model) — Phase B.
//!
//! Ported from Econometrica `src-tauri/src/commands/online_auth.rs`, trimmed for
//! Launch: validates the licence against the Supabase `/auth` Edge Function
//! (cabinets + expires_at), caches the response 24h, and falls back to the cache
//! when the server is unreachable. The Econometrica-only content-pack / vault /
//! frontend fields are dropped (Launch is local-first). The offline Ed25519
//! `license.json` fallback is handled by `commands::license`.

use anyhow::Result;
use log::{info, warn};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::sync::OnceLock;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::crypto::fingerprint;

/// Supabase Edge Functions base URL (obfuscated at compile time).
fn supabase_url() -> String {
    obfstr::obfstr!("https://quzhkfvglqmppxcrindh.supabase.co/functions/v1").to_string()
}

/// Cache validity period: 24 hours in seconds.
const CACHE_TTL_SECS: u64 = 24 * 60 * 60;

/// HTTP request timeout in seconds.
const REQUEST_TIMEOUT_SECS: u64 = 15;

/// Product identifier sent to the server. Launch is a single product; the auth
/// Edge Function looks up `licenses` by `fingerprint_hash + product`.
pub fn detect_product() -> &'static str {
    "launch"
}

/// Request body for POST /auth.
#[derive(Debug, Serialize)]
struct AuthRequest {
    fingerprint_hash: String,
    instance_id: String,
    session_id: String,
    app_version: String,
    content_version: String,
    hostname: String,
    product: String,
}

/// Server response from /auth (only the fields Launch consumes; extra fields in
/// the JSON are ignored by serde).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthResponse {
    pub status: String,
    #[serde(default)]
    pub cabinets: Vec<String>,
    #[serde(default)]
    pub app_min_version: String,
    #[serde(default)]
    pub expires_at: Option<String>,
    #[serde(default)]
    pub message: Option<String>,
    #[serde(default)]
    pub update_required: bool,
    #[serde(default)]
    pub update_url: Option<String>,
}

/// Cached auth response stored on disk.
#[derive(Debug, Serialize, Deserialize)]
struct CachedAuth {
    response: AuthResponse,
    cached_at: u64, // Unix timestamp
}

/// Combined online auth status returned to the licence layer.
#[derive(Debug, Clone, Serialize)]
pub struct OnlineAuthStatus {
    pub available: bool, // true if the server responded
    pub status: String,  // "ok" | "blocked" | "cached" | "offline"
    pub cabinets: Vec<String>,
    pub app_min_version: String,
    pub expires_at: Option<String>,
    pub machine_id: String,
    pub message: Option<String>,
    pub update_required: bool,
    pub update_url: Option<String>,
}

// ── Session ID (per-launch, NOT persisted) ────────────────

static SESSION_ID: OnceLock<String> = OnceLock::new();

pub fn get_session_id() -> String {
    SESSION_ID
        .get_or_init(|| {
            let id = uuid::Uuid::new_v4().to_string();
            info!("Generated session ID: {}", &id[..8]);
            id
        })
        .clone()
}

// ── Instance ID (persisted) ───────────────────────────────

/// Get or create a persistent instance ID (UUID v4) in `<app_config_dir>/instance.id`.
pub fn get_or_create_instance_id(app_config_dir: &Path) -> Result<String> {
    let path = app_config_dir.join("instance.id");
    if path.exists() {
        let id = std::fs::read_to_string(&path)?.trim().to_string();
        if !id.is_empty() {
            return Ok(id);
        }
    }
    let id = uuid::Uuid::new_v4().to_string();
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&path, &id)?;
    info!("Generated new instance ID: {}", &id[..8]);
    Ok(id)
}

// ── Cache ──────────────────────────────────────────────────

fn cache_path(app_config_dir: &Path) -> PathBuf {
    app_config_dir.join("session_cache.json")
}

fn save_cache(app_config_dir: &Path, response: &AuthResponse) -> Result<()> {
    let now = SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs();
    let cached = CachedAuth {
        response: response.clone(),
        cached_at: now,
    };
    std::fs::write(cache_path(app_config_dir), serde_json::to_string(&cached)?)?;
    Ok(())
}

fn load_cache(app_config_dir: &Path) -> Option<AuthResponse> {
    let data = std::fs::read_to_string(cache_path(app_config_dir)).ok()?;
    let cached: CachedAuth = serde_json::from_str(&data).ok()?;
    let now = SystemTime::now().duration_since(UNIX_EPOCH).ok()?.as_secs();
    if now.saturating_sub(cached.cached_at) > CACHE_TTL_SECS {
        info!("Auth cache expired (age: {}h)", (now - cached.cached_at) / 3600);
        return None;
    }
    info!("Using cached auth response (age: {}m)", (now.saturating_sub(cached.cached_at)) / 60);
    Some(cached.response)
}

// ── HTTP ───────────────────────────────────────────────────

fn build_client() -> Result<reqwest::Client> {
    Ok(reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(REQUEST_TIMEOUT_SECS))
        .build()?)
}

/// Attempt online authorization against Supabase. Caches on success.
/// Err if the server is unreachable / response unparseable.
pub async fn check_auth(
    app_config_dir: &Path,
    app_version: &str,
    content_version: &str,
) -> Result<AuthResponse> {
    let fp = fingerprint::get_machine_fingerprint()?;
    let fp_hash = fingerprint::hash_fingerprint(&fp);
    let instance_id = get_or_create_instance_id(app_config_dir)?;

    let hostname = std::env::var("COMPUTERNAME")
        .or_else(|_| std::env::var("HOSTNAME"))
        .unwrap_or_default();

    let req = AuthRequest {
        fingerprint_hash: fp_hash,
        instance_id,
        session_id: get_session_id(),
        app_version: app_version.to_string(),
        content_version: content_version.to_string(),
        hostname,
        product: detect_product().to_string(),
    };

    let client = build_client()?;
    let url = format!("{}/auth", supabase_url());
    info!("Online auth: POST {}", url);

    let res = client.post(&url).json(&req).send().await?;
    let status_code = res.status();
    let body = res.text().await?;

    let auth_response: AuthResponse = serde_json::from_str(&body)
        .map_err(|e| anyhow::anyhow!("Failed to parse auth response: {e}, body: {body}"))?;

    if auth_response.status == "ok" {
        if let Err(e) = save_cache(app_config_dir, &auth_response) {
            warn!("Failed to cache auth response: {e}");
        }
        info!("Online auth: OK, cabinets: {:?}", auth_response.cabinets);
    } else {
        warn!(
            "Online auth: {} (HTTP {}): {:?}",
            auth_response.status, status_code, auth_response.message
        );
    }

    Ok(auth_response)
}

/// Full online flow: try online → fallback to cache → status. Does NOT fall back
/// to Ed25519 (the caller in `commands::license` does that).
pub async fn authorize(
    app_config_dir: &Path,
    app_version: &str,
    content_version: &str,
) -> OnlineAuthStatus {
    let machine_id = fingerprint::get_machine_fingerprint()
        .map(|fp| fingerprint::hash_fingerprint(&fp)[..12].to_string())
        .unwrap_or_else(|_| "unknown".to_string());

    match check_auth(app_config_dir, app_version, content_version).await {
        Ok(resp) if resp.status == "ok" => OnlineAuthStatus {
            available: true,
            status: "ok".to_string(),
            cabinets: resp.cabinets,
            app_min_version: resp.app_min_version,
            expires_at: resp.expires_at,
            machine_id,
            message: None,
            update_required: resp.update_required,
            update_url: resp.update_url,
        },
        Ok(resp) => OnlineAuthStatus {
            // Server responded but denied (blocked / expired / no licence).
            available: true,
            status: resp.status,
            cabinets: vec![],
            app_min_version: resp.app_min_version,
            expires_at: None,
            machine_id,
            message: resp.message,
            update_required: false,
            update_url: None,
        },
        Err(e) => {
            warn!("Online auth failed: {e}");
            if let Some(cached) = load_cache(app_config_dir) {
                info!("Using cached auth (server unreachable)");
                OnlineAuthStatus {
                    available: false,
                    status: "cached".to_string(),
                    cabinets: cached.cabinets,
                    app_min_version: cached.app_min_version,
                    expires_at: cached.expires_at,
                    machine_id,
                    message: Some("Работа по кэшу (сервер недоступен)".to_string()),
                    update_required: cached.update_required,
                    update_url: cached.update_url,
                }
            } else {
                OnlineAuthStatus {
                    available: false,
                    status: "offline".to_string(),
                    cabinets: vec![],
                    app_min_version: String::new(),
                    expires_at: None,
                    machine_id,
                    message: Some("Сервер недоступен, кэш отсутствует".to_string()),
                    update_required: false,
                    update_url: None,
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn product_is_launch() {
        assert_eq!(detect_product(), "launch");
    }

    /// Live integration smoke against the prod Supabase `/auth` Edge Function,
    /// using THIS dev box's fingerprint. Requires the test licence row
    /// (Starter: launch_core + launch_proxy_single) issued for this machine.
    /// Ignored by default (network + machine-specific). Run with:
    ///   cargo test live_online_auth_smoke -- --ignored --nocapture
    #[tokio::test]
    #[ignore = "live: hits prod Supabase /auth with this dev box's fingerprint"]
    async fn live_online_auth_smoke() {
        let dir = std::env::temp_dir().join("aurora-launch-auth-smoke");
        std::fs::create_dir_all(&dir).unwrap();
        let status = authorize(&dir, env!("CARGO_PKG_VERSION"), "").await;
        println!(
            "online_auth: status={} available={} cabinets={:?} expires={:?} msg={:?}",
            status.status, status.available, status.cabinets, status.expires_at, status.message
        );
        assert_eq!(status.status, "ok", "expected prod backend to authorize the test licence");
        assert!(
            status.cabinets.iter().any(|c| c == "launch_proxy_single"),
            "Starter licence must grant launch_proxy_single"
        );
        assert!(
            !status.cabinets.iter().any(|c| c == "launch_proxy_multi"),
            "Starter licence must NOT grant launch_proxy_multi (deny path)"
        );
    }
}
