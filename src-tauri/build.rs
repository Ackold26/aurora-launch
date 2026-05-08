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

    tauri_build::build()
}
