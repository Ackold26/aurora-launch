//! Structured error type для IPC commands.
//!
//! All commands return `Result<T, AuroraError>`. The error serializes как
//! `{ kind: "...", message: "...", details?: ... }` so the frontend can
//! display localised messages с context.

use serde::{Serialize, Serializer};
use thiserror::Error;

#[derive(Error, Debug)]
pub enum AuroraError {
    #[error("Bundle not found: {path}")]
    BundleNotFound { path: String },

    #[error("Bundle handle invalid or closed: {handle_id}")]
    BundleHandleInvalid { handle_id: String },

    #[error("Bundle integrity check failed: {reason}")]
    BundleIntegrity { reason: String },

    #[error("Bundle format error: {reason}")]
    BundleFormat { reason: String },

    #[error("ZIP entry not found in bundle: {entry}")]
    BundleEntryNotFound { entry: String },

    #[error("File too large: {size} bytes (cap {cap})")]
    FileTooLarge { size: u64, cap: u64 },

    #[error("Signature verification failed: {reason}")]
    SignatureInvalid { reason: String },

    #[error("Feature requires license: {feature}")]
    LicenseFeatureRequired { feature: String, current_state: String },

    #[error("License bypass requested but compile-time disabled (build_profile={profile})")]
    LicenseBypassRefused { profile: String },

    #[error("Forecast cancelled by user")]
    ForecastCancelled,

    #[error("Forecast handle not found: {handle_id}")]
    ForecastHandleNotFound { handle_id: String },

    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("ZIP error: {0}")]
    Zip(#[from] zip::result::ZipError),

    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("SQLite error: {0}")]
    Sqlite(#[from] rusqlite::Error),

    #[error("Other: {0}")]
    Other(String),
}

impl AuroraError {
    pub fn kind(&self) -> &'static str {
        match self {
            Self::BundleNotFound { .. } => "bundle_not_found",
            Self::BundleHandleInvalid { .. } => "bundle_handle_invalid",
            Self::BundleIntegrity { .. } => "bundle_integrity",
            Self::BundleFormat { .. } => "bundle_format",
            Self::BundleEntryNotFound { .. } => "bundle_entry_not_found",
            Self::FileTooLarge { .. } => "file_too_large",
            Self::SignatureInvalid { .. } => "signature_invalid",
            Self::LicenseFeatureRequired { .. } => "license_feature_required",
            Self::LicenseBypassRefused { .. } => "license_bypass_refused",
            Self::ForecastCancelled => "forecast_cancelled",
            Self::ForecastHandleNotFound { .. } => "forecast_handle_not_found",
            Self::Io(_) => "io",
            Self::Zip(_) => "zip",
            Self::Json(_) => "json",
            Self::Sqlite(_) => "sqlite",
            Self::Other(_) => "other",
        }
    }
}

// Custom serializer — flat JSON shape consumable by frontend без deeper wrapping
impl Serialize for AuroraError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        use serde::ser::SerializeStruct;
        let mut state = serializer.serialize_struct("AuroraError", 2)?;
        state.serialize_field("kind", self.kind())?;
        state.serialize_field("message", &self.to_string())?;
        state.end()
    }
}

pub type AuroraResult<T> = Result<T, AuroraError>;
