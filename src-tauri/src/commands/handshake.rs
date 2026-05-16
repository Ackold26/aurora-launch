//! Handshake status IPC — этап 2.8 ROADMAP_POST_V0_1_0.
//!
//! Frontend получает результат negotiate-handshake через эту команду,
//! решает показывать ли блокирующий banner «несовместимая версия sidecar».
//!
//! Подробности контракта см. в `sidecar::SidecarManager::negotiate_protocol`.

use std::sync::Arc;
use tauri::State;

use crate::errors::AuroraResult;
use crate::sidecar::{NegotiationResult, SidecarManager};

#[tauri::command]
pub async fn get_handshake_status(
    sidecar: State<'_, Arc<SidecarManager>>,
) -> AuroraResult<Option<NegotiationResult>> {
    Ok(sidecar.handshake_status().await)
}
