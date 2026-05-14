# build-pilot-installer.ps1
#
# Phase Σ.2 — F2a pilot installer build (lean F1 signing).
#
# Wraps build-beta-installer.ps1 с pilot-specific configuration:
#   - Disables Tauri auto-updater (Σ.1.3) — pilot manual updates
#   - Embeds local Ed25519 public PEM от Veracrypt container (Σ.1.2)
#   - Uses 64-char placeholder pubkey для AURORA_UPDATER_PUBKEY (build gate)
#
# Usage:
#   .\scripts\build-pilot-installer.ps1 -SigningKeyDir "E:\aurora-signer"
#
# Pre-flight (per Final/F1_LEAN_SIGNING_RUNBOOK.md):
#   - Veracrypt container mounted, public.pem present
#   - npm install + cargo build verified (no missing icons / sidecar binary)
#   - secrets/ directory does NOT contain real updater key (pilot = disabled)

param(
    [Parameter(Mandatory=$true)]
    [string]$SigningKeyDir,
    [string]$Target = "x86_64-pc-windows-msvc",
    [switch]$SkipSmokeReminder
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

Write-Host "Aurora Launch PILOT installer build (Σ.2, lean F1 signing)" -ForegroundColor Cyan
Write-Host "Target:        $Target"
Write-Host "SigningKeyDir: $SigningKeyDir"
Write-Host "Repo:          $RepoRoot"
Write-Host ""

# ───────────────────────────────────────────────────────────────────────────
# Step 1: verify public key present
# ───────────────────────────────────────────────────────────────────────────

$PubKeyPath = Join-Path $SigningKeyDir "public.pem"
if (-not (Test-Path $PubKeyPath)) {
    throw "Public key not found: $PubKeyPath`nMount Veracrypt container per F1_LEAN_SIGNING_RUNBOOK Σ.1.0."
}

$PubKeyPem = Get-Content $PubKeyPath -Raw
if ($PubKeyPem -notmatch "BEGIN PUBLIC KEY") {
    throw "Public key does not look like PEM format (expected '-----BEGIN PUBLIC KEY-----')."
}

Write-Host "[OK] Public key loaded (PEM format)" -ForegroundColor Green

# ───────────────────────────────────────────────────────────────────────────
# Step 2: backup tauri.conf.json (will restore at end)
# ───────────────────────────────────────────────────────────────────────────

$ConfPath = Join-Path $RepoRoot "src-tauri/tauri.conf.json"
$ConfBackup = "$ConfPath.bak"
Copy-Item -Path $ConfPath -Destination $ConfBackup -Force
Write-Host "[OK] Backed up tauri.conf.json → $ConfBackup"

try {
    # ─────────────────────────────────────────────────────────────────────
    # Step 3: disable updater в pilot build (Σ.1.3)
    # ─────────────────────────────────────────────────────────────────────

    $Conf = Get-Content $ConfPath -Raw | ConvertFrom-Json
    if ($Conf.plugins -and $Conf.plugins.updater) {
        $Conf.plugins.updater.active = $false
    }
    $Conf | ConvertTo-Json -Depth 20 | Set-Content $ConfPath -Encoding utf8
    Write-Host "[OK] tauri.conf.json updater.active = false (pilot manual updates)"

    # ─────────────────────────────────────────────────────────────────────
    # Step 4: set environment for build
    # ─────────────────────────────────────────────────────────────────────

    $env:AURORA_BUILD_PROFILE = "production"
    $env:AURORA_CLOUD_PUBLIC_KEY_PEM = $PubKeyPem
    # Placeholder updater pubkey (64 hex chars) для build.rs gate satisfaction.
    # Auto-updater is disabled (Σ.1.3) so this is never verified at runtime.
    $env:AURORA_UPDATER_PUBKEY = "0000000000000000000000000000000000000000000000000000000000000000"

    Write-Host ""
    Write-Host "Environment set:"
    Write-Host "  AURORA_BUILD_PROFILE       = production"
    Write-Host "  AURORA_CLOUD_PUBLIC_KEY_PEM = (embedded $($PubKeyPem.Length) chars)"
    Write-Host "  AURORA_UPDATER_PUBKEY      = placeholder (updater disabled)"

    # ─────────────────────────────────────────────────────────────────────
    # Step 5: run underlying build
    # ─────────────────────────────────────────────────────────────────────

    Write-Host ""
    Write-Host "[BUILD] Invoking build-beta-installer.ps1 -SkipHashes" -ForegroundColor Yellow

    & (Join-Path $PSScriptRoot "build-beta-installer.ps1") -Target $Target -SkipHashes
    if ($LASTEXITCODE -ne 0) { throw "Tauri build failed" }

    # ─────────────────────────────────────────────────────────────────────
    # Step 6: SHA-256 manifest (pilot release naming)
    # ─────────────────────────────────────────────────────────────────────

    $BundleDir = Join-Path $RepoRoot "src-tauri/target/release/bundle"
    $NsisExe = Get-ChildItem (Join-Path $BundleDir "nsis") -Filter "*-setup.exe" `
        -ErrorAction SilentlyContinue | Select-Object -First 1
    $MsiFile = Get-ChildItem (Join-Path $BundleDir "msi") -Filter "*.msi" `
        -ErrorAction SilentlyContinue | Select-Object -First 1

    if (-not $NsisExe) { throw "NSIS .exe не создан" }

    $Version = (Select-String -Path $ConfPath -Pattern '"version":\s*"([^"]+)"').Matches[0].Groups[1].Value
    $HashFile = Join-Path $RepoRoot "Final/RELEASE_${Version}_PILOT_HASHES.txt"

    @(
        "# Aurora Launch v$Version — PILOT installer SHA-256 hashes"
        "# Build: lean F1 signing (local Ed25519 key, auto-updater disabled)"
        "# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')"
        ""
        "## Signing key fingerprint:"
        ($PubKeyPem.Substring(0, [Math]::Min(200, $PubKeyPem.Length)) -replace "`r`n", "`n").Trim()
        ""
        "## Installer artefacts:"
    ) | Set-Content $HashFile -Encoding utf8

    Get-FileHash $NsisExe.FullName -Algorithm SHA256 |
        ForEach-Object { "$($_.Hash.ToLower())  $($NsisExe.Name)" } |
        Add-Content $HashFile

    if ($MsiFile) {
        Get-FileHash $MsiFile.FullName -Algorithm SHA256 |
            ForEach-Object { "$($_.Hash.ToLower())  $($MsiFile.Name)" } |
            Add-Content $HashFile
    }

    Write-Host ""
    Write-Host "[OK] Pilot installer build complete:" -ForegroundColor Green
    Write-Host "  NSIS:  $($NsisExe.FullName)"
    if ($MsiFile) { Write-Host "  MSI:   $($MsiFile.FullName)" }
    Write-Host "  Hashes: $HashFile"
}
finally {
    # ─────────────────────────────────────────────────────────────────────
    # Step 7: restore tauri.conf.json (НЕ commit pilot-specific changes)
    # ─────────────────────────────────────────────────────────────────────
    if (Test-Path $ConfBackup) {
        Move-Item -Path $ConfBackup -Destination $ConfPath -Force
        Write-Host "[OK] tauri.conf.json restored from backup"
    }

    # Clear sensitive env vars
    $env:AURORA_CLOUD_PUBLIC_KEY_PEM = $null
}

if (-not $SkipSmokeReminder) {
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "Σ.1.5 Smoke test checklist (Антон ~1h):" -ForegroundColor Cyan
    Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "  - Clean Windows 11 VM (no Aurora previously installed)"
    Write-Host "  - Install NSIS .exe, UAC prompt, install completes"
    Write-Host "  - App launches < 2s к webview ready"
    Write-Host "  - Open Sample Кагоцел → Венарус, forecast < 5s"
    Write-Host "  - Methodology Certificate PDF + signature badge"
    Write-Host "  - Help → Send Diagnostics → ZIP в %TEMP%"
    Write-Host "  - Force-kill sidecar, crash recovery dialog appears"
    Write-Host "  - Uninstall, %LOCALAPPDATA% data preserved"
    Write-Host ""
    Write-Host "Если green → tag v0.1.0-rc2 + email Materia Medica installer + hashes."
}
