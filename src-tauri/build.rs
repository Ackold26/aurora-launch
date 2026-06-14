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

    // Updater pubkey gate REMOVED (fleet-unify migration 2026-06-14): Launch no
    // longer uses tauri-plugin-updater / minisign. Update integrity is now a
    // SHA256 checksum delivered in the server JSON (see commands/updater.rs), so
    // there is no compile-time pubkey to embed and production builds no longer
    // require AURORA_UPDATER_PUBKEY. This unblocks the production installer
    // (previously build.rs panicked here without a minisign keypair that exists
    // nowhere in the fleet). The AURORA_BUILD_PROFILE license-bypass gate above
    // is unaffected.

    tauri_build::build()
}
