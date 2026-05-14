//! IPC command modules. Each module exports tauri::command-decorated functions
//! registered в lib.rs::run().

pub mod adapters;
pub mod audit_log;
pub mod build_info;
pub mod bundle;
pub mod crash_recovery;
pub mod feedback;
pub mod forecast;
pub mod license;
pub mod methodology_cert;
pub mod similarity;
pub mod telemetry;
