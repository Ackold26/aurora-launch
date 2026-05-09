# build-beta-installer.ps1
# F2a beta installer build для Windows (unsigned).
#
# Usage:
#   .\scripts\build-beta-installer.ps1 [-Target x86_64-pc-windows-msvc]
#
# Creates Aurora Launch_<version>_x64-setup.exe (NSIS) + .msi в
# src-tauri/target/release/bundle/{nsis,msi}/.
# Computes SHA-256 + writes Final/RELEASE_<version>_HASHES.txt.
#
# Pre-flight (per Final/F2a_INSTALLER_BUILDBOOK.md):
#   - npm install + cargo build verified
#   - secrets/updater-pubkey.txt exists (для embed в Tauri updater plugin)
#   - VS Build Tools 2019+ present

param(
    [string]$Target = "x86_64-pc-windows-msvc",
    [switch]$SkipHashes
)

$ErrorActionPreference = "Stop"

# Resolve repo root (parent of scripts/)
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

Write-Host "Aurora Launch beta installer build (F2a unsigned)" -ForegroundColor Cyan
Write-Host "Target: $Target"
Write-Host "Repo:   $RepoRoot"

# Step 1 — verify pubkey present (хотя для unsigned сценария Tauri update keys
# embedded анонсом; pubkey строит chain of trust для auto-update verification).
$PubkeyPath = Join-Path $RepoRoot "secrets/updater-pubkey.txt"
if (-not (Test-Path $PubkeyPath)) {
    Write-Warning "secrets/updater-pubkey.txt не найден; auto-updater verification будет broken для пилота."
    Write-Warning "Generate key pair via:  npx @tauri-apps/cli signer generate -p '' -w secrets/updater-priv.txt"
} else {
    $env:AURORA_UPDATER_PUBKEY = (Get-Content $PubkeyPath -Raw).Trim()
}

$env:AURORA_BUILD_PROFILE = "production"

# Step 2 — npm install + frontend build
Write-Host "`n[1/3] npm install + frontend build" -ForegroundColor Yellow
npm install --silent
if ($LASTEXITCODE -ne 0) { throw "npm install failed" }

# Step 3 — Tauri build NSIS + MSI
Write-Host "`n[2/3] Tauri build for $Target" -ForegroundColor Yellow
npm run tauri build -- --target $Target
if ($LASTEXITCODE -ne 0) { throw "Tauri build failed" }

$BundleDir = Join-Path $RepoRoot "src-tauri/target/release/bundle"
$NsisExe = Get-ChildItem (Join-Path $BundleDir "nsis") -Filter "*-setup.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
$MsiFile = Get-ChildItem (Join-Path $BundleDir "msi") -Filter "*.msi" -ErrorAction SilentlyContinue | Select-Object -First 1

if (-not $NsisExe) { throw "NSIS .exe не создан в $BundleDir/nsis/" }

Write-Host "`n[3/3] Build complete:" -ForegroundColor Green
Write-Host "  NSIS:  $($NsisExe.FullName)"
if ($MsiFile) { Write-Host "  MSI:   $($MsiFile.FullName)" }

# Step 4 — SHA-256 manifest
if (-not $SkipHashes) {
    $Version = (Select-String -Path "src-tauri/tauri.conf.json" -Pattern '"version":\s*"([^"]+)"').Matches[0].Groups[1].Value
    $HashFile = Join-Path $RepoRoot "Final/RELEASE_${Version}_HASHES.txt"

    @(
        "# Aurora Launch v$Version — beta installer SHA-256 hashes (F2a unsigned)"
        "# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')"
        ""
    ) | Set-Content $HashFile -Encoding utf8

    Get-FileHash $NsisExe.FullName -Algorithm SHA256 |
        ForEach-Object { "$($_.Hash.ToLower())  $($NsisExe.Name)" } |
        Add-Content $HashFile

    if ($MsiFile) {
        Get-FileHash $MsiFile.FullName -Algorithm SHA256 |
            ForEach-Object { "$($_.Hash.ToLower())  $($MsiFile.Name)" } |
            Add-Content $HashFile
    }

    Write-Host "`nHashes written to: $HashFile"
}

Write-Host "`nNext steps:" -ForegroundColor Cyan
Write-Host "  1. Smoke test installer на чистой Windows VM (SmartScreen workflow per Final/PILOT_INSTALLATION_GUIDE.md)."
Write-Host "  2. Email pilot user installer URL + matching SHA-256 hash."
Write-Host "  3. Verify auto-updater endpoint reachable: https://updates.auroraai.pro/launch/{target}/{arch}/{version}"
