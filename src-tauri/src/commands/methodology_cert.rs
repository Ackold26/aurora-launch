//! Block 2C — Native Rust verification IPC.
//!
//! Replaces removed WASM verifier. Pure Rust ed25519-dalek + BLAKE3 —
//! no IPC bridge overhead, sub-100ms warm for typical .aurora bundles.
//!
//! Two signature provenances per Block 2 audit R7:
//! - `cloud_kms`  — production: signature issued by C7 Vercel + KMS (F1 deploy)
//! - `local_dev`  — dev/sample: ed25519 keypair generated at install; visible
//!                  badge "Local dev signature — not production-grade"
//! - `sample`     — bundled sample.aurora с pre-generated dev signature
//!
//! Verification UI shows distinct trust badges per `signature_provenance`.

use std::path::PathBuf;

use ed25519_dalek::{Signature, Verifier, VerifyingKey, SigningKey, Signer};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use tauri::{AppHandle, Manager};

use crate::errors::{AuroraError, AuroraResult};

/// Compute composite bundle hash matching Python
/// `BundleManifest.composite_bundle_hash()` byte-for-byte (Block 3 BLOCKER-1 fix).
///
/// Algorithm (mirrors `bundle_manifest.py:106-134`):
/// 1. `manifest_h = SHA256(manifest_canonical_bytes_hex)` — hex string
/// 2. `file_hashes = sorted(per-file sha256 hex strings)` — ascii concat
/// 3. `files_hash = SHA256(files_concat).hex()`
/// 4. parts = [manifest_h, files_hash, aurora_app_version] each prepended
///    with 4-byte big-endian length
/// 5. result = SHA256(buf).hex()
///
/// Inputs:
/// - `manifest_buf`: raw canonical bytes of manifest.json (JCS RFC 8785 from
///   Python writer)
/// - `manifest_value`: parsed manifest для extracting per-file hashes +
///   aurora_app_version
fn composite_bundle_hash_mirror(
    manifest_buf: &[u8],
    manifest_value: &serde_json::Value,
) -> Result<String, AuroraError> {
    let manifest_h = hex::encode(Sha256::digest(manifest_buf));

    let files = manifest_value
        .get("files")
        .and_then(|v| v.as_object())
        .ok_or_else(|| AuroraError::BundleFormat {
            reason: "manifest.files missing or not object".into(),
        })?;

    let mut file_hashes: Vec<String> = files
        .values()
        .filter_map(|entry| {
            entry.get("sha256").and_then(|v| v.as_str()).map(String::from)
        })
        .collect();
    file_hashes.sort();
    let files_concat: String = file_hashes.concat();
    let files_hash = hex::encode(Sha256::digest(files_concat.as_bytes()));

    let aurora_app_version = manifest_value
        .get("aurora_app_version")
        .and_then(|v| v.as_str())
        .ok_or_else(|| AuroraError::BundleFormat {
            reason: "manifest.aurora_app_version missing".into(),
        })?;

    // Length-prefix encoding: 4-byte BE length || bytes для each part
    let mut buf: Vec<u8> = Vec::new();
    for part in &[
        manifest_h.as_bytes(),
        files_hash.as_bytes(),
        aurora_app_version.as_bytes(),
    ] {
        let len = part.len() as u32;
        buf.extend_from_slice(&len.to_be_bytes());
        buf.extend_from_slice(part);
    }

    Ok(hex::encode(Sha256::digest(&buf)))
}

const AURORA_CLOUD_PUBLIC_KEY_PEM: &str =
    "-----BEGIN PUBLIC KEY-----\nEMBED_AT_RELEASE_TIME\n-----END PUBLIC KEY-----\n";

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct VerificationResult {
    pub valid: bool,
    pub signature_provenance: String, // "cloud_kms" | "local_dev" | "sample" | "unsigned"
    pub signed_by: Option<String>,
    pub signed_at: Option<String>,
    pub key_fingerprint: Option<String>,
    pub composite_hash: Option<String>,
    pub manifest_revision: Option<i64>,
    pub trust_badge: String, // "production" | "dev" | "sample" | "warning"
    pub failure_reason: Option<String>,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct VerifyBundleInput {
    pub bundle_path: String,
    pub trust_local_dev: bool,
}

#[tauri::command]
pub async fn verify_bundle_signature(
    app: AppHandle,
    input: VerifyBundleInput,
) -> AuroraResult<VerificationResult> {
    let path = PathBuf::from(&input.bundle_path);
    if !path.exists() {
        return Err(AuroraError::BundleNotFound {
            path: path.display().to_string(),
        });
    }

    // Read bundle, locate signature manifest entry (`signature.bin` per
    // ADR-002 §"Methodology Cert"), extract composite hash, verify Ed25519.
    let file = std::fs::File::open(&path)?;
    let mut archive = zip::ZipArchive::new(file).map_err(|e| AuroraError::BundleFormat {
        reason: format!("cannot open ZIP: {e}"),
    })?;

    // Read manifest first
    use std::io::Read;
    let mut manifest_buf = Vec::new();
    {
        let mut manifest_file =
            archive.by_name("manifest.json").map_err(|_| AuroraError::BundleFormat {
                reason: "missing manifest.json".into(),
            })?;
        manifest_file.read_to_end(&mut manifest_buf)?;
    }
    let manifest: serde_json::Value = serde_json::from_slice(&manifest_buf)?;

    // Look for cert metadata entry
    let cert_meta = manifest.get("methodology_cert").cloned();
    let provenance = cert_meta
        .as_ref()
        .and_then(|c| c.get("signature_provenance"))
        .and_then(|v| v.as_str())
        .unwrap_or("unsigned")
        .to_string();

    if provenance == "unsigned" {
        return Ok(VerificationResult {
            valid: false,
            signature_provenance: "unsigned".into(),
            signed_by: None,
            signed_at: None,
            key_fingerprint: None,
            composite_hash: None,
            manifest_revision: manifest.get("revision").and_then(|v| v.as_i64()),
            trust_badge: "warning".into(),
            failure_reason: Some("Bundle has no methodology certificate".into()),
        });
    }

    // Read signature bytes
    let mut sig_buf = Vec::new();
    {
        let mut sig_file = match archive.by_name("signature.bin") {
            Ok(f) => f,
            Err(_) => {
                return Ok(VerificationResult {
                    valid: false,
                    signature_provenance: provenance,
                    signed_by: None,
                    signed_at: None,
                    key_fingerprint: None,
                    composite_hash: None,
                    manifest_revision: manifest.get("revision").and_then(|v| v.as_i64()),
                    trust_badge: "warning".into(),
                    failure_reason: Some("signature.bin missing from bundle".into()),
                })
            }
        };
        sig_file.read_to_end(&mut sig_buf)?;
    }

    if sig_buf.len() != 64 {
        return Ok(VerificationResult {
            valid: false,
            signature_provenance: provenance,
            signed_by: None,
            signed_at: None,
            key_fingerprint: None,
            composite_hash: None,
            manifest_revision: manifest.get("revision").and_then(|v| v.as_i64()),
            trust_badge: "warning".into(),
            failure_reason: Some(format!(
                "signature.bin wrong length: {} (expected 64)",
                sig_buf.len()
            )),
        });
    }

    // Block 3 BLOCKER-1 fix: composite hash mirrors Python
    // `BundleManifest.composite_bundle_hash()` byte-for-byte. Previously Rust
    // used BLAKE3 на manifest_buf only — divergent from Python's SHA256(
    // manifest_h || files_hash || aurora_app_version, length-prefix-encoded).
    // Cross-app verification was broken: Python-signed bundles always failed
    // Rust verify. Now they match.
    let composite_hex = composite_bundle_hash_mirror(&manifest_buf, &manifest)?;
    let composite_bytes = hex::decode(&composite_hex).map_err(|e| AuroraError::Other(format!(
        "composite hex decode: {e}"
    )))?;

    // Signature valid? Need verifying key. For sample provenance, key is
    // bundled with installer; for cloud_kms, embed Aurora's public key
    // (set at release time). For local_dev — read from app data dir.

    let verifying_key_bytes: Option<[u8; 32]> = match provenance.as_str() {
        "cloud_kms" => {
            // Production: Aurora's hardcoded public key
            extract_pubkey_from_pem(AURORA_CLOUD_PUBLIC_KEY_PEM)
        }
        "local_dev" if input.trust_local_dev => {
            // Read local dev key from app data (uses AppHandle для path
            // consistency with generate_local_dev_signature — Block 3 HIGH-3 fix)
            read_local_dev_pubkey(&app)
        }
        "sample" => {
            // Bundled sample key — read from bundle itself
            cert_meta
                .as_ref()
                .and_then(|c| c.get("public_key_hex"))
                .and_then(|v| v.as_str())
                .and_then(|s| {
                    let bytes = hex::decode(s).ok()?;
                    bytes.try_into().ok()
                })
        }
        _ => None,
    };

    let Some(pubkey_bytes) = verifying_key_bytes else {
        return Ok(VerificationResult {
            valid: false,
            signature_provenance: provenance,
            signed_by: None,
            signed_at: None,
            key_fingerprint: None,
            composite_hash: Some(composite_hex),
            manifest_revision: manifest.get("revision").and_then(|v| v.as_i64()),
            trust_badge: "warning".into(),
            failure_reason: Some("Verifying key unavailable for this signature provenance".into()),
        });
    };

    let verifying_key = match VerifyingKey::from_bytes(&pubkey_bytes) {
        Ok(k) => k,
        Err(e) => {
            return Ok(VerificationResult {
                valid: false,
                signature_provenance: provenance,
                signed_by: None,
                signed_at: None,
                key_fingerprint: None,
                composite_hash: Some(composite_hex),
                manifest_revision: manifest.get("revision").and_then(|v| v.as_i64()),
                trust_badge: "warning".into(),
                failure_reason: Some(format!("Invalid verifying key: {e}")),
            })
        }
    };

    // Block 3 HIGH-6 fix: replace try_into().unwrap() с graceful Result handling.
    let sig_array: [u8; 64] = sig_buf.as_slice().try_into().map_err(|_| {
        AuroraError::BundleFormat {
            reason: format!("signature.bin size mismatch: {} bytes (expected 64)", sig_buf.len()),
        }
    })?;
    let signature = Signature::from_bytes(&sig_array);

    let valid = verifying_key
        .verify(&composite_bytes, &signature)
        .is_ok();

    let trust_badge = match (valid, provenance.as_str()) {
        (true, "cloud_kms") => "production",
        (true, "local_dev") => "dev",
        (true, "sample") => "sample",
        _ => "warning",
    };

    let key_fingerprint = blake3::hash(&pubkey_bytes).to_hex().to_string()[..16].to_string();

    let signed_by = cert_meta
        .as_ref()
        .and_then(|c| c.get("signed_by"))
        .and_then(|v| v.as_str())
        .map(String::from);
    let signed_at = cert_meta
        .as_ref()
        .and_then(|c| c.get("signed_at"))
        .and_then(|v| v.as_str())
        .map(String::from);

    Ok(VerificationResult {
        valid,
        signature_provenance: provenance,
        signed_by,
        signed_at,
        key_fingerprint: Some(key_fingerprint),
        composite_hash: Some(composite_hex),
        manifest_revision: manifest.get("revision").and_then(|v| v.as_i64()),
        trust_badge: trust_badge.into(),
        failure_reason: if valid {
            None
        } else {
            Some("Ed25519 signature verification failed".into())
        },
    })
}

#[derive(Serialize, Deserialize, Debug)]
pub struct LocalDevSignatureResult {
    pub public_key_hex: String,
    pub signature_hex: String,
    pub composite_hash_hex: String,
}

#[tauri::command]
pub async fn generate_local_dev_signature(
    app: AppHandle,
    bundle_path: String,
) -> AuroraResult<LocalDevSignatureResult> {
    use rand::rngs::OsRng;

    // Load или generate persistent local dev keypair
    let app_data = app
        .path()
        .app_data_dir()
        .map_err(|e| AuroraError::Other(format!("app_data_dir: {e}")))?;
    std::fs::create_dir_all(&app_data)?;
    let keypair_path = app_data.join("local_dev_signing_key.bin");

    let signing_key = if keypair_path.exists() {
        let bytes = std::fs::read(&keypair_path)?;
        if bytes.len() != 32 {
            return Err(AuroraError::Other("invalid local dev key file size".into()));
        }
        // Block 3 HIGH-6 fix: graceful Result instead of unwrap()
        let arr: [u8; 32] = bytes.as_slice().try_into().map_err(|_| {
            AuroraError::Other("local dev key bytes not 32".into())
        })?;
        SigningKey::from_bytes(&arr)
    } else {
        let mut csprng = OsRng;
        let key = SigningKey::generate(&mut csprng);
        std::fs::write(&keypair_path, key.to_bytes())?;
        // Restrict permissions on Unix
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let mut perms = std::fs::metadata(&keypair_path)?.permissions();
            perms.set_mode(0o600);
            std::fs::set_permissions(&keypair_path, perms)?;
        }
        // Block 3 HIGH-4 fix: Windows ACLs not restricted by default (NTFS
        // ACL API requires winapi crate). On Windows, AppData is per-user
        // (mitigates same-user threats); for shared-machine threats we log
        // an explicit warning. Future hardening: invoke icacls subprocess
        // или windows-acl crate to deny inheritance + grant only current user.
        #[cfg(windows)]
        {
            log::warn!(
                "local_dev_signing_key.bin written с default ACLs ({}). \
                 Per-user AppData scope mitigates most threats; shared-machine \
                 hardening requires NTFS ACL restriction (Block 4 followup).",
                keypair_path.display()
            );
        }
        key
    };

    // Block 3 BLOCKER-1 fix: compute composite hash mirroring Python's
    // BundleManifest.composite_bundle_hash() (was BLAKE3-of-manifest only).
    let file = std::fs::File::open(&bundle_path)?;
    let mut archive = zip::ZipArchive::new(file).map_err(|e| AuroraError::BundleFormat {
        reason: format!("zip open: {e}"),
    })?;
    use std::io::Read;
    let mut manifest_buf = Vec::new();
    let mut mf = archive
        .by_name("manifest.json")
        .map_err(|_| AuroraError::BundleFormat {
            reason: "missing manifest.json".into(),
        })?;
    mf.read_to_end(&mut manifest_buf)?;
    drop(mf);

    let manifest: serde_json::Value = serde_json::from_slice(&manifest_buf)?;
    let composite_hex = composite_bundle_hash_mirror(&manifest_buf, &manifest)?;
    let composite_bytes = hex::decode(&composite_hex).map_err(|e| {
        AuroraError::Other(format!("composite hex decode: {e}"))
    })?;
    let signature = signing_key.sign(&composite_bytes);

    Ok(LocalDevSignatureResult {
        public_key_hex: hex::encode(signing_key.verifying_key().to_bytes()),
        signature_hex: hex::encode(signature.to_bytes()),
        composite_hash_hex: composite_hex,
    })
}

// ── Sprint 3 D6: verify_reproducibility ──────────────────────────────────
//
// Mirror of `aurora-launch-reproduce` CLI semantics: re-hash every file inside
// the bundle ZIP and compare against the per-file `sha256` claims в manifest.
// Verified = all files match; Diverged = any file's bytes have changed since
// manifest creation; Error = bundle malformed (missing manifest, unreadable
// ZIP, hash field absent).
//
// Security:
//   - bundle_path validated за input boundary (exists + .aurora extension).
//   - Canonicalisation prevents path-traversal via "../" prefix tricks.
//   - SHA-256 used (already a dependency for composite hash).

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct ReproducibilityFileMismatch {
    pub entry: String,
    pub expected_sha256: String,
    pub computed_sha256: String,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct ReproducibilityResult {
    /// "verified" — all files match manifest claims.
    /// "diverged" — at least one file's bytes differ from manifest claim.
    /// "error"    — bundle malformed (caller shows `reason` to user).
    pub status: String,
    pub files_checked: u32,
    pub mismatches: Vec<ReproducibilityFileMismatch>,
    pub reason: Option<String>,
}

#[tauri::command]
pub async fn verify_reproducibility(
    bundle_path: String,
) -> AuroraResult<ReproducibilityResult> {
    use std::io::Read;

    // Input validation: .aurora extension + canonicalize to prevent traversal.
    let raw_path = PathBuf::from(&bundle_path);
    if raw_path
        .extension()
        .and_then(|s| s.to_str())
        .map(|s| s.to_ascii_lowercase())
        .as_deref()
        != Some("aurora")
    {
        return Ok(ReproducibilityResult {
            status: "error".into(),
            files_checked: 0,
            mismatches: Vec::new(),
            reason: Some("Файл должен иметь расширение .aurora".into()),
        });
    }
    if !raw_path.exists() {
        return Err(AuroraError::BundleNotFound {
            path: raw_path.display().to_string(),
        });
    }
    let path = raw_path
        .canonicalize()
        .map_err(|e| AuroraError::Other(format!("canonicalize: {e}")))?;

    // Open ZIP + read manifest.json.
    let file = std::fs::File::open(&path)?;
    let mut archive = zip::ZipArchive::new(file).map_err(|e| AuroraError::BundleFormat {
        reason: format!("cannot open ZIP: {e}"),
    })?;
    let mut manifest_buf = Vec::new();
    {
        let mut mf =
            archive
                .by_name("manifest.json")
                .map_err(|_| AuroraError::BundleFormat {
                    reason: "missing manifest.json".into(),
                })?;
        mf.read_to_end(&mut manifest_buf)?;
    }
    let manifest: serde_json::Value = serde_json::from_slice(&manifest_buf)?;

    // manifest.files is the SSOT for per-file hashes (mirrors Python
    // BundleManifest.files dict). Each entry has shape:
    //   "<entry_name>": { "sha256": "<hex>", "size_bytes": N, ... }
    let files = manifest
        .get("files")
        .and_then(|v| v.as_object())
        .ok_or_else(|| AuroraError::BundleFormat {
            reason: "manifest.files missing or not object".into(),
        })?;

    let mut mismatches: Vec<ReproducibilityFileMismatch> = Vec::new();
    let mut files_checked: u32 = 0;

    // Iterate all manifest entries and re-hash from ZIP.
    for (entry_name, entry_meta) in files.iter() {
        let expected = match entry_meta.get("sha256").and_then(|v| v.as_str()) {
            Some(s) => s,
            None => continue, // skip files without claimed hash (e.g. derived artefacts)
        };

        let mut buf: Vec<u8> = Vec::new();
        {
            let zip_entry = archive.by_name(entry_name);
            let mut e = match zip_entry {
                Ok(e) => e,
                Err(_) => {
                    // Manifest claims a file that's not in the ZIP — divergence.
                    mismatches.push(ReproducibilityFileMismatch {
                        entry: entry_name.clone(),
                        expected_sha256: expected.to_string(),
                        computed_sha256: "<missing in ZIP>".to_string(),
                    });
                    files_checked += 1;
                    continue;
                }
            };
            e.read_to_end(&mut buf)?;
        }

        let computed = hex::encode(Sha256::digest(&buf));
        files_checked += 1;
        if computed != expected {
            mismatches.push(ReproducibilityFileMismatch {
                entry: entry_name.clone(),
                expected_sha256: expected.to_string(),
                computed_sha256: computed,
            });
        }
    }

    let status = if mismatches.is_empty() {
        "verified"
    } else {
        "diverged"
    };

    Ok(ReproducibilityResult {
        status: status.into(),
        files_checked,
        mismatches,
        reason: None,
    })
}

/// Block 3 BLOCKER-2 fix: real Ed25519 PEM SPKI extraction.
///
/// Decodes PKCS#8 SubjectPublicKeyInfo PEM с OID 1.3.101.112 (Ed25519 per
/// RFC 8410). Returns None if PEM is the placeholder `EMBED_AT_RELEASE_TIME`
/// or если structure invalid. Caller treats None as "production verifying
/// key not configured" — UI shows warning trust badge.
///
/// Standard Ed25519 SPKI DER layout (44 bytes total):
///   30 2a                                — SEQUENCE, length 42
///   30 05                                — SEQUENCE (AlgorithmIdentifier), length 5
///   06 03 2b 65 70                       — OID 1.3.101.112 (Ed25519)
///   03 21 00 <32-byte raw key>           — BIT STRING, 33 bytes (1 unused bits + 32 key bytes)
fn extract_pubkey_from_pem(pem: &str) -> Option<[u8; 32]> {
    use base64::{engine::general_purpose::STANDARD, Engine};

    if pem.contains("EMBED_AT_RELEASE_TIME") {
        // Production verifying key not yet baked в release; cloud_kms cannot
        // be verified. Block 1D B1 + Block 3 BLOCKER-2 acknowledge this
        // explicitly — release CI MUST replace placeholder before signing.
        return None;
    }

    // Strip PEM armor, base64-decode body
    let body: String = pem
        .lines()
        .filter(|line| !line.starts_with("-----") && !line.is_empty())
        .collect();
    let der = STANDARD.decode(body.as_bytes()).ok()?;

    // Expect 44 bytes for canonical Ed25519 SPKI; some encoders produce extra
    // length bytes — match by OID prefix instead.
    const OID_PREFIX: &[u8] = &[0x06, 0x03, 0x2b, 0x65, 0x70]; // 1.3.101.112
    let oid_pos = der.windows(OID_PREFIX.len()).position(|w| w == OID_PREFIX)?;
    // After OID (5 bytes) we expect BIT STRING tag 0x03, length 0x21 (33),
    // unused-bits byte 0x00, then 32 bytes раw key.
    let after_oid = &der[oid_pos + OID_PREFIX.len()..];
    if after_oid.len() < 35 {
        return None;
    }
    if after_oid[0] != 0x03 || after_oid[1] != 0x21 || after_oid[2] != 0x00 {
        return None;
    }
    let key_bytes: [u8; 32] = after_oid[3..35].try_into().ok()?;
    Some(key_bytes)
}

/// Block 3 HIGH-3 fix: read local dev pubkey using same path resolution
/// as `generate_local_dev_signature` (`AppHandle.path().app_data_dir()`).
/// Previously used `dirs::data_local_dir()` which differs from Tauri's
/// app_data_dir on Windows (roaming vs local AppData) — silently broken
/// verify path.
fn read_local_dev_pubkey(app: &AppHandle) -> Option<[u8; 32]> {
    let app_data = app.path().app_data_dir().ok()?;
    let key_path = app_data.join("local_dev_signing_key.bin");
    let bytes = std::fs::read(&key_path).ok()?;
    if bytes.len() != 32 {
        return None;
    }
    let arr: [u8; 32] = bytes.as_slice().try_into().ok()?;
    let signing = SigningKey::from_bytes(&arr);
    Some(signing.verifying_key().to_bytes())
}
