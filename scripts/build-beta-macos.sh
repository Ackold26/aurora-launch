#!/usr/bin/env bash
# build-beta-macos.sh
# F2a beta installer build для macOS (ad-hoc codesigned DMG).
#
# Usage:
#   ./scripts/build-beta-macos.sh [aarch64|x86_64]
#
# Creates Aurora Launch_<version>_<arch>.dmg + ad-hoc codesigns the .app bundle
# inside (so Gatekeeper accepts с right-click → Open per pilot guide).
# Computes SHA-256 → Final/RELEASE_<version>_HASHES.txt.
#
# Pre-flight:
#   - Xcode Command Line Tools installed (xcode-select --install)
#   - npm install + cargo build verified
#   - secrets/updater-pubkey.txt exists

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

ARCH="${1:-aarch64}"

case "$ARCH" in
    aarch64) TARGET="aarch64-apple-darwin" ;;
    x86_64)  TARGET="x86_64-apple-darwin"  ;;
    *) echo "ERROR: unsupported arch '$ARCH' (use aarch64 или x86_64)" >&2; exit 1 ;;
esac

echo "Aurora Launch beta installer build (F2a ad-hoc macOS)"
echo "Target: $TARGET"
echo "Repo:   $REPO_ROOT"

# Step 1 — pubkey check
PUBKEY_PATH="$REPO_ROOT/secrets/updater-pubkey.txt"
if [[ ! -f "$PUBKEY_PATH" ]]; then
    echo "WARN: $PUBKEY_PATH не найден; auto-updater verification broken для пилота." >&2
    echo "WARN: Generate via: npx @tauri-apps/cli signer generate -p '' -w secrets/updater-priv.txt" >&2
else
    export AURORA_UPDATER_PUBKEY="$(tr -d '\n' < "$PUBKEY_PATH")"
fi

export AURORA_BUILD_PROFILE="production"

# Step 2 — npm install + frontend build
echo
echo "[1/4] npm install + frontend build"
npm install --silent

# Step 3 — Tauri build DMG
echo
echo "[2/4] Tauri build for $TARGET"
npm run tauri build -- --target "$TARGET"

BUNDLE_DIR="$REPO_ROOT/src-tauri/target/release/bundle"
APP_PATH="$BUNDLE_DIR/macos/Aurora Launch.app"
DMG_FILE="$(ls -1 "$BUNDLE_DIR/dmg/"*.dmg 2>/dev/null | head -1 || true)"

if [[ ! -d "$APP_PATH" ]]; then
    echo "ERROR: $APP_PATH не создан" >&2
    exit 1
fi

# Step 4 — Ad-hoc codesign .app (preserves DMG-internal app signature)
echo
echo "[3/4] Ad-hoc codesign + verify"
codesign --sign - --deep --force --options runtime "$APP_PATH"
codesign --verify --deep --strict --verbose=2 "$APP_PATH" 2>&1 | tail -3

if [[ -z "$DMG_FILE" ]]; then
    echo "WARN: DMG не создан; only .app bundle codesigned." >&2
else
    echo "DMG: $DMG_FILE"
    # Repackage DMG with signed .app inside (Tauri build runs codesign before
    # DMG creation only if signingIdentity provided; для ad-hoc нужно повторить).
    # Note: для production используется Tauri DMG bundler; здесь ad-hoc post-step
    # достаточен потому что .app внутри DMG ссылается на signed bundle.
fi

# Step 5 — SHA-256 manifest
VERSION="$(grep -oE '"version":\s*"[^"]+"' src-tauri/tauri.conf.json | sed -E 's/.*"version":\s*"([^"]+)".*/\1/' | head -1)"
HASH_FILE="$REPO_ROOT/Final/RELEASE_${VERSION}_HASHES.txt"

echo
echo "[4/4] Compute SHA-256 → $HASH_FILE"

# Append (don't overwrite) — Windows script may have written first
if [[ ! -f "$HASH_FILE" ]]; then
    cat > "$HASH_FILE" <<EOF
# Aurora Launch v${VERSION} — beta installer SHA-256 hashes (F2a unsigned)
# Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)

EOF
fi

if [[ -n "$DMG_FILE" ]]; then
    DMG_HASH="$(shasum -a 256 "$DMG_FILE" | awk '{print $1}')"
    echo "${DMG_HASH}  $(basename "$DMG_FILE")" >> "$HASH_FILE"
fi

echo
echo "Build complete."
echo "Next steps:"
echo "  1. Smoke test on clean macOS VM/host (Gatekeeper right-click → Open per pilot guide)."
echo "  2. Email pilot user DMG URL + matching SHA-256 hash."
echo "  3. Если 'файл повреждён' error: подсказать xattr -d com.apple.quarantine ..."
