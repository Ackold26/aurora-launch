"""Sidecar IPC authentication — Block 4 audit D4 + Phase 2.D.1 HE-2.

INV-05 invariant: cryptographic claim (auth) requires attack scenario test
FIRST. See `tests/test_sidecar_auth.py` for the suite that pins the contract.

Threat model:
- Adversary: a malicious local process that opens our stdin/stdout pipes (e.g.,
  via a shared FIFO, debugger attachment, or another user on the same machine).
- Goal: block adversary from issuing IPC commands without the launch-time
  token shared between Rust parent and Python child.

Phase 2.D.1 mechanism (HE-2): primary channel — first stdin line. Rust
parent writes `{token}\n` immediately after spawn. Env var fallback
сохранён для backwards-compat + dev scripts, но deprecation warning
emit'ится. Reduces env var exposure surface (ps output, /proc/PID/environ
visible других пользователям той же машины на default Linux).

Mechanism:
- Rust generates 32 bytes from CSPRNG, hex-encodes (64 chars).
- Primary: Rust writes `<token>\n` first line stdin сразу после spawn.
- Fallback: env var `AURORA_SIDECAR_AUTH_TOKEN` (deprecation logged если used).
- Python sidecar startup: read stdin first line с timeout 5s; если timeout
  или empty → fallback на env var. Validates 64-char hex. Exit 2 если оба missing.
- Every request must include `auth: <token>` field; otherwise rejected с
  `auth_required` error. Constant-time compare (hmac.compare_digest).
- Token never logged. If both channels fail, sidecar exits 2.

This is per-launch isolation, not cryptographic identity.
"""

from __future__ import annotations

import hmac
import os
import select
import sys

ENV_VAR = "AURORA_SIDECAR_AUTH_TOKEN"
EXPECTED_TOKEN_HEX_LEN = 64  # 32 bytes hex-encoded
STDIN_READ_TIMEOUT_S = 5.0


class AuthError(ValueError):
    """Raised when authentication fails. Sidecar replies с `auth_required` error."""


def _is_valid_token(token: str) -> bool:
    """Token shape check: 64-char hex string."""
    return (
        isinstance(token, str)
        and len(token) == EXPECTED_TOKEN_HEX_LEN
        and all(c in "0123456789abcdefABCDEF" for c in token)
    )


def _read_first_line_stdin(timeout: float) -> str | None:
    """Read first line from stdin с timeout. Returns None при timeout/error.

    select.select работает только на Unix для file descriptors. На Windows
    обходим: используем readline directly (blocks indefinitely) — нерабочее
    решение для HE-2 timeout. Workaround на Windows — fallback на env immediately.

    Linux/macOS: select.select на stdin с timeout — clean.
    """
    if sys.platform == "win32":
        # Windows: select не работает для file descriptors (только sockets).
        # HE-2 stdin path на Windows — defer (env var остаётся primary
        # canal). На Linux/macOS — preferred.
        return None
    try:
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        if not ready:
            return None
        line = sys.stdin.readline()
        return line.strip() if line else None
    except (OSError, ValueError):
        return None


def load_token_from_stdin_or_env(
    *, stdin_timeout: float = STDIN_READ_TIMEOUT_S
) -> str:
    """Load auth token — priority: stdin first line → env var fallback.

    HE-2: stdin reduces env var exposure surface (ps / /proc/PID/environ).
    Env var sохранён для:
    - Windows (select.select не работает для stdin)
    - dev scripts that don't write stdin
    - Backwards compatibility

    Exits с code 2 если оба channels missing.
    """
    # Try stdin first (HE-2 primary)
    stdin_token = _read_first_line_stdin(stdin_timeout)
    if stdin_token and _is_valid_token(stdin_token):
        return stdin_token
    if stdin_token and not _is_valid_token(stdin_token):
        sys.stderr.write(
            f"[aurora-sidecar] stdin token invalid shape (len={len(stdin_token)}), "
            f"falling back to env var.\n"
        )

    # Env fallback
    env_token = os.environ.get(ENV_VAR, "")
    if env_token:
        if sys.platform != "win32" and stdin_token is None:
            # Linux/macOS: stdin timeout passed. Log deprecation warning —
            # parent should use stdin path going forward.
            sys.stderr.write(
                f"[aurora-sidecar] DEPRECATION: {ENV_VAR} env var used; "
                f"prefer stdin first-line token (HE-2). Parent process should "
                f"write token\\n to sidecar stdin immediately after spawn.\n"
            )
        if not _is_valid_token(env_token):
            sys.stderr.write(
                f"[aurora-sidecar] FATAL: {ENV_VAR} must be 64-char hex. "
                f"Got len={len(env_token)}.\n"
            )
            sys.exit(2)
        return env_token

    # Both missing — fail-closed
    sys.stderr.write(
        f"[aurora-sidecar] FATAL: no auth token provided. Expected stdin "
        f"first line OR {ENV_VAR} env var. Parent process must inject one.\n"
    )
    sys.exit(2)


# Backwards-compat alias — existing callers (server.py) импортируют
# load_token_from_env. Keep working.
def load_token_from_env() -> str:
    """Deprecated alias — prefers stdin, falls back to env (HE-2)."""
    return load_token_from_stdin_or_env()


def check_auth(presented: str, expected: str) -> None:
    """Constant-time compare. Raises `AuthError` on mismatch."""
    if not isinstance(presented, str) or not presented:
        raise AuthError("auth field missing or empty")
    if len(presented) != len(expected):
        raise AuthError("auth length mismatch")
    if not hmac.compare_digest(presented, expected):
        raise AuthError("auth token invalid")
