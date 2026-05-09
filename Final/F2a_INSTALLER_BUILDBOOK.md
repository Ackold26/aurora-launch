# F2a Beta Installer Buildbook (unsigned)

**Status:** Scaffold 2026-05-10
**Scope:** Pilot beta installer без OS code signing. Used до F2b (post-юрлицо) для Materia Medica pilot.
**Targets:** Windows NSIS (unsigned) + macOS DMG (ad-hoc codesigned).
**Trigger:** Antоn infra ready (Yandex KMS + Vercel + DNS + GitHub secrets) → tag `v0.1.0-rc2` → release.yml builds installers cross-platform via GH Actions matrix; this buildbook is fallback / local build path.

---

## Prerequisites

### Common

- Aurora Launch repo checked out, branch `main`, HEAD on tag (e.g., `v0.1.0-rc2`).
- `npm install` ✅ + `cargo build` ✅ (verified locally).
- Aurora Platform Core editable installs (sibling checkout) — see `06_References/INSTALL.md` §Prerequisites.
- Tauri CLI installed: `cargo install tauri-cli@^2.0` (или `npm install -D @tauri-apps/cli`).

### Windows-specific

- Visual Studio Build Tools 2019+ с MSVC + Windows SDK.
- NSIS не требуется отдельно — Tauri скачивает через bundler.
- (Optional) `signtool.exe` from Windows SDK (для Phase F2b sign step).

### macOS-specific

- Xcode Command Line Tools (`xcode-select --install`).
- `codesign --sign -` working (built-in).
- macOS 11.0+ (Big Sur) для build target.

---

## Build commands

### Windows (unsigned NSIS)

```powershell
# From repo root
$env:AURORA_BUILD_PROFILE = "production"
$env:AURORA_UPDATER_PUBKEY = (Get-Content secrets/updater-pubkey.txt -Raw).Trim()
npm run tauri build -- --target x86_64-pc-windows-msvc

# Output:
# src-tauri/target/release/bundle/nsis/Aurora Launch_0.1.0_x64-setup.exe
# src-tauri/target/release/bundle/msi/Aurora Launch_0.1.0_x64_en-US.msi
```

**SmartScreen behavior (unsigned):** SmartScreen покажет «Unrecognized app» с кнопкой «More info» → «Run anyway». User confirms 2-clicks. Это нормально для pre-юрлицо beta. См. `Final/PILOT_INSTALLATION_GUIDE.md`.

### macOS (ad-hoc codesigned DMG)

```bash
# From repo root
export AURORA_BUILD_PROFILE=production
export AURORA_UPDATER_PUBKEY=$(cat secrets/updater-pubkey.txt | tr -d '\n')

# Build target (ARM64 Apple Silicon)
npm run tauri build -- --target aarch64-apple-darwin

# Output:
# src-tauri/target/release/bundle/dmg/Aurora Launch_0.1.0_aarch64.dmg
# src-tauri/target/release/bundle/macos/Aurora Launch.app

# Apply ad-hoc codesign (locally, no Apple ID required)
codesign --sign - --deep --force --options runtime \
    src-tauri/target/release/bundle/macos/"Aurora Launch.app"

# Verify ad-hoc signature applied
codesign --verify --deep --strict --verbose=2 \
    src-tauri/target/release/bundle/macos/"Aurora Launch.app"
# Expect: «satisfies its Designated Requirement» + «signed by signature: Apple Root CA → adhoc»
```

**Optional — Intel build:**

```bash
npm run tauri build -- --target x86_64-apple-darwin
# Same codesign step on the resulting .app
```

**Gatekeeper behavior (ad-hoc signed):** macOS shows «Aurora Launch.app не может быть открыто, потому что разработчик не подтверждён». User делает right-click → «Открыть». Это убирает «повреждённый» error без Apple Developer ID. См. pilot guide.

### Linux (AppImage + Deb)

```bash
# AppImage + .deb produced на любом modern Linux
npm run tauri build -- --target x86_64-unknown-linux-gnu

# Output:
# src-tauri/target/release/bundle/appimage/aurora-launch_0.1.0_amd64.AppImage
# src-tauri/target/release/bundle/deb/aurora-launch_0.1.0_amd64.deb
```

Linux pilots не блокируются signing concerns (AppImage runs verbatim, deb installs via apt). Materia Medica pilot — Windows-first, Linux secondary.

---

## Artifact verification

### SHA-256 manifest

```powershell
# Windows PowerShell
Get-FileHash src-tauri\target\release\bundle\nsis\*.exe -Algorithm SHA256 | Format-List
Get-FileHash src-tauri\target\release\bundle\msi\*.msi -Algorithm SHA256 | Format-List
```

```bash
# macOS / Linux
shasum -a 256 src-tauri/target/release/bundle/dmg/*.dmg
shasum -a 256 src-tauri/target/release/bundle/appimage/*.AppImage
shasum -a 256 src-tauri/target/release/bundle/deb/*.deb
```

Save hashes к `Final/RELEASE_v0.1.0_HASHES.txt` для pilot verification.

### Update key embed verification

After build, ensure pubkey embedded в binary (Tauri updater plugin):

```bash
# macOS / Linux: strings | grep
strings src-tauri/target/release/aurora-launch | grep -E "^[A-Za-z0-9+/]{40,}=$" | head -5

# Windows PowerShell
$bytes = [IO.File]::ReadAllBytes("src-tauri\target\release\aurora-launch.exe")
# Manual inspection harder on Windows — verify via Tauri update endpoint hit instead
```

If pubkey absent → installer cannot verify auto-update signatures → broken auto-update flow.

---

## Pilot delivery checklist (per Final/PILOT_INSTALLATION_GUIDE.md)

- [ ] Windows NSIS installer + SHA-256 hash file
- [ ] macOS DMG (ARM + Intel separate) + ad-hoc codesigned + SHA-256
- [ ] Linux AppImage + .deb + SHA-256
- [ ] Installation Guide PDF (rendered from `Final/PILOT_INSTALLATION_GUIDE.md`)
- [ ] Sample bundle (anonymized FMCG / OTC) для first-run wow (60s)
- [ ] Emergency contact info embedded в installer (about screen + bug report channel)

---

## Phase F2b transition (post-юрлицо)

Когда регистрация ООО завершена и Authenticode EV / Apple Developer ID purchased:

1. **Windows:** install signtool, configure EV cert, modify `release.yml` step «Sign installer» с `signtool.exe sign /tr <ts-server> /sha1 <thumbprint> ...`
2. **macOS:** Apple Developer Program enrollment + Developer ID Application cert + replace `codesign --sign -` with `codesign --sign "Developer ID Application: Aurora AI (XXXXXXXXXX)"` + `notarytool submit` + `stapler staple`
3. **Auto-updater rollover:** push signed update via existing `tauri-plugin-updater` flow → pilot client получает update одним кликом, без повторной ручной установки.
4. Этот документ archived; F2b dedicated buildbook supersedes.

---

## Risk register

| Risk | Mitigation |
|---|---|
| Ad-hoc macOS signature stripped by Quarantine | Distribute как DMG (preserves xattr) + add `xattr -d com.apple.quarantine` instruction в pilot guide |
| SmartScreen confusion для non-tech pilot user | Step-by-step screenshots в Installation Guide; Антон walkthrough на kickoff call |
| Pilot reports «installer rejected» blocking 24h SLA | Hot-fix channel: rebuild с small change → push update via Tauri updater (pubkey уже embedded) |
| AppImage missing libwebkit2gtk на customer Linux | Provide .deb fallback; document apt install instructions |
