; Aurora Launch — NSIS installer hooks (fleet-unify migration 2026-06-14)
;
; Purpose: release file locks on the bundled Python sidecar before NSIS
; overwrites it during an auto-update install. Aurora Launch uses a
; stdin/stdout sidecar (aurora-sidecar.exe), NOT an HTTP sidecar, so — unlike
; Econometrica — NO loopback firewall rules are needed (no POSTINSTALL hook).
;
; The running aurora-sidecar.exe holds locks on its bundled .pyd / .dll files.
; If NSIS reaches the file-copy stage while it is alive, it silently SKIPS the
; locked files -> frontend new + sidecar old = silent functional gaps. The Rust
; updater::apply_update path stops the sidecar first; this PREINSTALL hook is
; the safety net for cases where that path is bypassed (manual installer run,
; watchdog respawn race).
;
; nsExec::ExecToLog runs the process hidden (no console window) and writes
; stdout to the installer log. Each call leaves an exit code on the stack ->
; Pop $0 is mandatory. taskkill /T kills the process tree (PyInstaller
; multiprocessing workers), /F forces. Exit 128 = "process not found" = OK
; (idempotent). The USERNAME filter scopes the kill to the current installer
; user (RDP multi-user safety — do not kill another user's sidecar).
;
; ASCII-only DetailPrint: Cyrillic in the Tauri 2 NSIS template is not
; production-verified across Aurora products — safer English fallback.

!macro NSIS_HOOK_PREINSTALL
  DetailPrint "Preparing for update: stopping background processes..."
  nsExec::ExecToLog 'taskkill /IM "aurora-sidecar.exe" /FI "USERNAME eq %USERNAME%" /T /F'
  Pop $0
  Sleep 1500
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  DetailPrint "Stopping background processes before uninstall..."
  nsExec::ExecToLog 'taskkill /IM "aurora-sidecar.exe" /FI "USERNAME eq %USERNAME%" /T /F'
  Pop $0
  Sleep 1500
!macroend
