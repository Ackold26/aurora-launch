//! Cryptographic helpers for Aurora Launch.
//!
//! - `fingerprint` — machine fingerprint for licence binding (fleet-shared algorithm).
//! - `ed25519` — fleet licence Ed25519 public-key verification (offline licence).

pub mod ed25519;
pub mod fingerprint;
