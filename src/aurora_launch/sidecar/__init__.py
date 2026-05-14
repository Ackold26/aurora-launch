"""Aurora Launch Python sidecar — Block 4.

Long-running daemon process spawned by Tauri shell plugin (sidecar API).
Communicates с Rust IPC through stdin/stdout JSON-RPC messages, plus
unsolicited events (forecast progress, etc.) emitted on stdout.

Architecture:
- Rust spawns the binary (PyInstaller-built) at app startup with auth token
  injected via env var `AURORA_SIDECAR_AUTH_TOKEN`.
- Sidecar reads newline-delimited JSON requests from stdin.
- Each request `{"id": int, "method": str, "params": object, "auth": str}`
  is auth-checked, then dispatched к method handler.
- Responses `{"id": int, "result": ...}` or `{"id": int, "error": {...}}`
  written к stdout, newline-terminated.
- Unsolicited events `{"event": str, "params": object}` (no `id`) emitted
  for forecast progress, audit log, etc.

Block 4 audit decisions:
- D1 sidecar = PyInstaller binary + long-running daemon
- D3 protocol = JSON-RPC 2.0-ish с auth field
- D4 per-launch random 32-byte auth token
- D5 cancel = cooperative atomic flag, NOT SIGINT

INV compliance:
- INV-02 runtime smoke (call public method, не just import)
- INV-05 attack scenario test FIRST (auth bypass, replay, malformed input)
- INV-08 real pytest run before declaring sidecar ready
- INV-10 read tauri-plugin-shell sidecar API docs до wiring
"""
