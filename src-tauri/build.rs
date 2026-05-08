// Tauri build script — embeds AURORA_BUILD_PROFILE into binary at compile time.
//
// Block 1D BLOCKER B1 fix: license bypass requires AURORA_BUILD_PROFILE=dev to
// be set BOTH at runtime AND must match value embedded at build time. Without
// this dual gate, end-users could simply set the env var on a production
// install и unlock paid features.
//
// Convention:
//   - Production CI sets AURORA_BUILD_PROFILE=production at `cargo build` time
//   - Local dev: defaults to "dev" (we set in build.rs if env var unset)
//   - Released installers: ALWAYS production via release workflow
//
// At runtime, validate_license code checks env var matches embedded value
// AND embedded value == "dev". If embedded == "production" the env var is
// ignored entirely (compile-time elimination of bypass code path).

fn main() {
    let build_profile =
        std::env::var("AURORA_BUILD_PROFILE").unwrap_or_else(|_| "dev".to_string());

    // Re-run build.rs if env var changes
    println!("cargo:rerun-if-env-changed=AURORA_BUILD_PROFILE");

    // Embed at compile time. Available в Rust код через env!("AURORA_BUILD_PROFILE")
    println!("cargo:rustc-env=AURORA_BUILD_PROFILE={}", build_profile);

    // Emit warning if production build wasn't explicitly requested
    if std::env::var("PROFILE").unwrap_or_default() == "release" && build_profile != "production" {
        println!(
            "cargo:warning=Building в release mode но AURORA_BUILD_PROFILE != 'production' (got '{}'). \
             For pilot/release builds set AURORA_BUILD_PROFILE=production. License bypass remains gated.",
            build_profile
        );
    }

    // Block 3 BLOCKER-3 fix: refuse to compile production release с placeholder
    // updater pubkey. Without this gate, production installer accepts any
    // signature (or none) on auto-updates — an attacker controlling the
    // updates.auroraai.pro endpoint could push arbitrary binaries.
    //
    // Release CI MUST set AURORA_UPDATER_PUBKEY env var с real Ed25519 hex
    // pubkey before `cargo build --release`. The build replaces the
    // placeholder в tauri.conf.json (or fails the build).
    if build_profile == "production" {
        let updater_pubkey = std::env::var("AURORA_UPDATER_PUBKEY").unwrap_or_default();
        if updater_pubkey.is_empty() || updater_pubkey.contains("EMBED_AT_RELEASE_TIME") {
            panic!(
                "BLOCKER-3 GATE: production build requires AURORA_UPDATER_PUBKEY env var \
                 (Ed25519 hex). Got empty or placeholder. Aborting — would ship \
                 unsigned-update vulnerability."
            );
        }
        if updater_pubkey.len() != 64 || !updater_pubkey.chars().all(|c| c.is_ascii_hexdigit()) {
            panic!(
                "BLOCKER-3 GATE: AURORA_UPDATER_PUBKEY must be 64-char hex string (Ed25519 \
                 32-byte raw pubkey). Got {} chars. Aborting.",
                updater_pubkey.len()
            );
        }
        println!("cargo:rerun-if-env-changed=AURORA_UPDATER_PUBKEY");
        println!("cargo:rustc-env=AURORA_UPDATER_PUBKEY={}", updater_pubkey);
    }

    tauri_build::build()
}
