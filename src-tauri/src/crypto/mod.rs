//! Cryptographic helpers for Aurora Launch.
//!
//! - `fingerprint` — machine fingerprint for licence binding (fleet-shared algorithm).
//! - `ed25519` (added in Phase B with the offline licence rewrite) — fleet
//!   licence Ed25519 public-key verification.

pub mod fingerprint;
