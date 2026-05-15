//! Aurora Launch sidecar manager (Block 4).
//!
//! Spawns the long-running Python sidecar binary at app startup, manages
//! its stdin/stdout pipes, dispatches JSON-RPC requests, fans out unsolicited
//! events to Tauri webview listeners.
//!
//! Architecture (Block 4 audit D1+D3+D4):
//! - One process for the entire app lifetime.
//! - Per-launch random 32-byte hex token via env var
//!   `AURORA_SIDECAR_AUTH_TOKEN`. Every request includes the token.
//! - Newline-delimited JSON messages on stdin/stdout.
//! - Reader task forwards events к Tauri global event bus
//!   (`emit("sidecar://forecast_progress", ...)`).
//! - `invoke()` allocates fresh request id, writes envelope through plugin's
//!   `CommandChild::write`, awaits response on oneshot channel keyed by `id`.
//!
//! Block 4 audit gate fixes:
//! - B4-S1 (BLOCKER): replace placeholder `attach_writer` no-op с real
//!   `Arc<CommandChild>` stored directly в SidecarManager. Writes go через
//!   `child.write(bytes)`, sync API.
//! - B4-S2: pending requests are cancelled on `CommandEvent::Terminated`
//!   so callers see immediate `sidecar_unavailable` rather than hanging.

use std::collections::HashMap;
use std::sync::atomic::{AtomicI64, Ordering};
use std::sync::Arc;

use rand::RngCore;
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter, Runtime};
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;
use tokio::sync::{oneshot, Mutex};

use crate::errors::{AuroraError, AuroraResult};

const ENV_AUTH_TOKEN: &str = "AURORA_SIDECAR_AUTH_TOKEN";
const SIDECAR_BINARY: &str = "binaries/aurora-sidecar";

#[derive(Serialize, Debug)]
struct SidecarRequestEnvelope<'a> {
    id: i64,
    method: &'a str,
    params: serde_json::Value,
    auth: &'a str,
}

#[derive(Deserialize, Debug)]
struct SidecarErrorPayload {
    kind: String,
    message: String,
}

#[derive(Deserialize, Debug)]
#[serde(untagged)]
enum SidecarMessage {
    Response {
        id: i64,
        #[serde(default)]
        result: Option<serde_json::Value>,
        #[serde(default)]
        error: Option<SidecarErrorPayload>,
    },
    Event {
        event: String,
        #[serde(default)]
        params: serde_json::Value,
    },
}

pub struct SidecarManager {
    next_id: AtomicI64,
    pending: Arc<Mutex<HashMap<i64, oneshot::Sender<Result<serde_json::Value, AuroraError>>>>>,
    /// Block 4 audit B4-S1 fix: hold CommandChild directly. Plugin's
    /// `write(buf: &[u8])` is sync с `&self`; mutex serialises concurrent
    /// callers (writes ARE serialised at OS level anyway via pipe atomicity,
    /// но lock prevents partial-line interleaving в Rust user code).
    child: Arc<Mutex<Option<CommandChild>>>,
    auth_token: String,
}

impl SidecarManager {
    /// Test-only constructor (no real sidecar spawn).
    pub fn auth_token_for_test(token: String) -> Self {
        Self {
            next_id: AtomicI64::new(1),
            pending: Arc::new(Mutex::new(HashMap::new())),
            child: Arc::new(Mutex::new(None)),
            auth_token: token,
        }
    }

    /// Spawn the sidecar binary. Long-running daemon — call once at startup.
    pub async fn spawn<R: Runtime>(app: &AppHandle<R>) -> AuroraResult<Arc<Self>> {
        let mut bytes = [0u8; 32];
        rand::thread_rng().fill_bytes(&mut bytes);
        let token = hex::encode(bytes);

        let cmd = app
            .shell()
            .sidecar(SIDECAR_BINARY)
            .map_err(|e| AuroraError::Other(format!("sidecar binary not found: {e}")))?
            .env(ENV_AUTH_TOKEN, &token);

        let (mut rx, child) = cmd
            .spawn()
            .map_err(|e| AuroraError::Other(format!("sidecar spawn failed: {e}")))?;

        let manager = Arc::new(Self {
            next_id: AtomicI64::new(1),
            pending: Arc::new(Mutex::new(HashMap::new())),
            child: Arc::new(Mutex::new(Some(child))),
            auth_token: token,
        });

        // Protocol version handshake — fire-and-forget background task. Result
        // logged; do not block spawn() return on Python sidecar boot. If
        // handshake fails (timeout / mismatch) — subsequent invoke() calls
        // surface the underlying issue naturally.
        let manager_for_handshake = Arc::clone(&manager);
        tokio::spawn(async move {
            // Short delay даёт sidecar время инициализировать method registry
            tokio::time::sleep(std::time::Duration::from_millis(200)).await;
            match manager_for_handshake.negotiate_protocol().await {
                Ok(_) => {}
                Err(e) => log::warn!("[sidecar handshake] failed: {e}"),
            }
        });

        // Reader task — receives events from CommandEvent stream
        let manager_for_reader = Arc::clone(&manager);
        let app_for_reader = app.clone();
        tokio::spawn(async move {
            use tauri_plugin_shell::process::CommandEvent;
            // Buffer для splitting partial lines across read chunks
            let mut leftover: Vec<u8> = Vec::new();
            while let Some(event) = rx.recv().await {
                match event {
                    CommandEvent::Stdout(line_bytes) => {
                        leftover.extend_from_slice(&line_bytes);
                        // Split on \n; keep last incomplete line в leftover
                        let mut start = 0;
                        let mut emit_lines: Vec<Vec<u8>> = Vec::new();
                        for (i, b) in leftover.iter().enumerate() {
                            if *b == b'\n' {
                                emit_lines.push(leftover[start..i].to_vec());
                                start = i + 1;
                            }
                        }
                        let remainder = leftover[start..].to_vec();
                        leftover = remainder;
                        for line_bytes in emit_lines {
                            let line = String::from_utf8_lossy(&line_bytes);
                            let trimmed = line.trim();
                            if trimmed.is_empty() {
                                continue;
                            }
                            handle_sidecar_line(trimmed, &manager_for_reader, &app_for_reader).await;
                        }
                    }
                    CommandEvent::Stderr(buf) => {
                        let s = String::from_utf8_lossy(&buf);
                        log::warn!("[sidecar stderr] {}", s.trim_end());
                    }
                    CommandEvent::Error(e) => {
                        log::error!("[sidecar error event] {e}");
                    }
                    CommandEvent::Terminated(payload) => {
                        log::warn!("[sidecar terminated] code={:?}", payload.code);
                        // Cancel all pending requests (B4-S2)
                        let mut pending = manager_for_reader.pending.lock().await;
                        for (_id, tx) in pending.drain() {
                            let _ = tx.send(Err(AuroraError::Other(
                                "sidecar_unavailable: terminated unexpectedly".into(),
                            )));
                        }
                        // Clear child handle so subsequent invoke() fails fast
                        let mut child_guard = manager_for_reader.child.lock().await;
                        *child_guard = None;
                        break;
                    }
                    _ => {}
                }
            }
        });

        Ok(manager)
    }

    /// Send a request, await response. Used by all IPC commands needing the
    /// Python backend.
    pub async fn invoke<T: for<'de> Deserialize<'de>>(
        &self,
        method: &str,
        params: serde_json::Value,
    ) -> AuroraResult<T> {
        let id = self.next_id.fetch_add(1, Ordering::SeqCst);
        let envelope = SidecarRequestEnvelope {
            id,
            method,
            params,
            auth: &self.auth_token,
        };
        let line = serde_json::to_string(&envelope)
            .map_err(|e| AuroraError::Other(format!("envelope serialize: {e}")))?;

        let (tx, rx) = oneshot::channel();
        {
            let mut pending = self.pending.lock().await;
            pending.insert(id, tx);
        }

        // Block 4 audit B4-S1 fix: write через CommandChild directly. Mutex
        // serialises to prevent two callers writing partial bytes at once.
        let write_result: AuroraResult<()> = {
            // Phase 2 fix: write requires &mut CommandChild — acquire write lock
            // via mut deref through MutexGuard. Previously `as_ref()` returned
            // &CommandChild which doesn't allow write() (needs mut).
            let mut child_guard = self.child.lock().await;
            match child_guard.as_mut() {
                Some(child) => {
                    let mut buf = Vec::with_capacity(line.len() + 1);
                    buf.extend_from_slice(line.as_bytes());
                    buf.push(b'\n');
                    child
                        .write(&buf)
                        .map_err(|e| AuroraError::Other(format!("sidecar stdin write: {e}")))
                }
                None => Err(AuroraError::Other(
                    "sidecar_not_running: child handle absent (binary missing or terminated)".into(),
                )),
            }
        };

        if let Err(err) = write_result {
            // Roll back pending registration
            let mut pending = self.pending.lock().await;
            pending.remove(&id);
            return Err(err);
        }

        match rx.await {
            Ok(Ok(value)) => serde_json::from_value(value)
                .map_err(|e| AuroraError::Other(format!("response deserialize: {e}"))),
            Ok(Err(err)) => Err(err),
            Err(_) => Err(AuroraError::Other(
                "sidecar response channel dropped".into(),
            )),
        }
    }

    /// Graceful shutdown — sends `shutdown` JSON-RPC, child exits на next
    /// loop iteration. Best-effort: errors logged, не propagated.
    pub async fn shutdown(&self) {
        let _ = self
            .invoke::<serde_json::Value>("shutdown", serde_json::json!({}))
            .await;
        // Drop child handle (its destructor on plugin side кills process if
        // still running)
        let mut guard = self.child.lock().await;
        *guard = None;
    }

    /// Protocol version handshake. Calls Python sidecar `negotiate` to confirm
    /// Rust↔Python compatibility before issuing any other methods. Logs warning
    /// if incompatible — caller decides whether to abort или продолжать.
    ///
    /// Best-effort: handshake failure не valит spawn — sidecar может ещё
    /// инициализироваться. Result returned для логирования/телеметрии.
    pub async fn negotiate_protocol(&self) -> AuroraResult<NegotiationResult> {
        let rust_version = env!("CARGO_PKG_VERSION").to_string();
        let result: NegotiationResult = self
            .invoke(
                "negotiate",
                serde_json::json!({ "rust_version": &rust_version }),
            )
            .await?;
        if !result.compatible {
            log::warn!(
                "[sidecar handshake] incompatible: reason={:?} advice={:?}",
                result.reason,
                result.advice
            );
        } else {
            log::info!(
                "[sidecar handshake] compatible (rust={})",
                rust_version
            );
        }
        Ok(result)
    }
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct NegotiationResult {
    pub compatible: bool,
    #[serde(default)]
    pub reason: Option<String>,
    #[serde(default)]
    pub advice: Option<String>,
}

async fn handle_sidecar_line<R: Runtime>(
    line: &str,
    manager: &Arc<SidecarManager>,
    app: &AppHandle<R>,
) {
    let parsed: Result<SidecarMessage, _> = serde_json::from_str(line);
    let Ok(msg) = parsed else {
        log::warn!("[sidecar] unparseable line: {}", line);
        return;
    };

    match msg {
        SidecarMessage::Response { id, result, error } => {
            let mut pending = manager.pending.lock().await;
            if let Some(tx) = pending.remove(&id) {
                let outcome = match (result, error) {
                    (Some(value), _) => Ok(value),
                    (_, Some(err)) => Err(AuroraError::Other(format!(
                        "{}: {}",
                        err.kind, err.message
                    ))),
                    (None, None) => Err(AuroraError::Other(
                        "response missing both result + error".into(),
                    )),
                };
                let _ = tx.send(outcome);
            } else {
                log::warn!("[sidecar] response for unknown id={}", id);
            }
        }
        SidecarMessage::Event { event, params } => {
            // Forward к Tauri event bus с `sidecar://` prefix
            let event_name = format!("sidecar://{}", event);
            if let Err(e) = app.emit(&event_name, params) {
                log::error!("[sidecar] failed to emit {}: {}", event_name, e);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn invoke_without_child_returns_structured_error() {
        let mgr = SidecarManager::auth_token_for_test("0".repeat(64));
        let res: AuroraResult<serde_json::Value> = mgr.invoke("ping", serde_json::json!({})).await;
        assert!(res.is_err());
        let msg = res.err().unwrap().to_string();
        assert!(msg.contains("sidecar_not_running"), "got: {msg}");
    }

    #[tokio::test]
    async fn shutdown_when_no_child_is_safe() {
        let mgr = SidecarManager::auth_token_for_test("0".repeat(64));
        // Should not panic — silently no-op
        mgr.shutdown().await;
    }
}
