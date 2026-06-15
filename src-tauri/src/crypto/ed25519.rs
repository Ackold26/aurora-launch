//! Ed25519 verification of the **fleet licence** public key.
//!
//! Ported from Econometrica `src-tauri/src/crypto/ed25519.rs` (fleet signing &
//! licensing unification, Phase B). Launch embeds the SAME fleet licence public
//! key so the one backend / issuer that signs the rest of the fleet's licences
//! also signs Launch's — no separate keypair.
//!
//! Distinct from `commands/methodology_cert.rs`, which verifies the
//! Methodology-Certificate signature against a *different* (cert) key.

use anyhow::{anyhow, Result};
use ed25519_dalek::{Signature, Verifier, VerifyingKey};

/// Fleet licence public key, XOR'd with a mask to avoid a plaintext key in the
/// binary. Original bytes (for reference):
/// [107, 117, 227, 176, 209, 81, 172, 175, 75, 122, 86, 18, 25, 248, 116, 202,
///  245, 64, 171, 148, 143, 9, 223, 199, 99, 58, 27, 251, 191, 84, 219, 56]
const MASKED_KEY: [u8; 32] = [
    62, 32, 182, 229, 132, 4, 249, 250, 30, 47, 3, 71, 76, 173, 33, 159,
    160, 21, 254, 193, 218, 92, 138, 146, 54, 111, 78, 174, 234, 1, 142, 109,
];
const KEY_MASK: u8 = 0x55;

fn public_key_bytes() -> [u8; 32] {
    let mut out = [0u8; 32];
    for i in 0..32 {
        out[i] = MASKED_KEY[i] ^ KEY_MASK;
    }
    out
}

/// Verify an Ed25519 signature over `data` against the fleet licence public key.
pub fn verify_signature(data: &[u8], signature_bytes: &[u8]) -> Result<bool> {
    let public_key = VerifyingKey::from_bytes(&public_key_bytes())
        .map_err(|e| anyhow!("Invalid public key: {e}"))?;

    let sig_array: [u8; 64] = signature_bytes
        .try_into()
        .map_err(|_| anyhow!("Signature must be 64 bytes"))?;
    let signature = Signature::from_bytes(&sig_array);

    Ok(public_key.verify(data, &signature).is_ok())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn wrong_length_signature_errors() {
        let garbage_short: &[u8] = b"not-a-real-signature";
        assert!(verify_signature(b"test data", garbage_short).is_err());
    }

    #[test]
    fn valid_length_garbage_does_not_verify() {
        let garbage_64 = [0xABu8; 64];
        let r = verify_signature(b"test data", &garbage_64);
        assert!(r.is_ok(), "64-byte garbage should not error");
        assert!(!r.unwrap(), "64-byte garbage must not verify as valid");
    }

    #[test]
    fn embedded_key_is_valid_ed25519_point() {
        // Guards the XOR-masked key: unmasking must yield a usable VerifyingKey.
        assert!(VerifyingKey::from_bytes(&public_key_bytes()).is_ok());
    }
}
