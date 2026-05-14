"""Sidecar IPC authentication — Block 4 audit D4.

INV-05 invariant: cryptographic claim (auth) requires attack scenario test
FIRST. See `tests/test_sidecar_auth.py` for the suite that pins the contract.

Threat model:
- Adversary: a malicious local process that opens our stdin/stdout pipes (e.g.,
  via a shared FIFO, debugger attachment, or another user on the same machine).
- Goal: block adversary from issuing IPC commands without the launch-time
  token shared between Rust parent and Python child.

Mechanism:
- Rust generates 32 bytes from a CSPRNG at app startup, hex-encodes (64 chars),
  passes via env var `AURORA_SIDECAR_AUTH_TOKEN`.
- Python sidecar reads env var на startup, stores в memory.
- Every request must include `auth: <token>` field; otherwise rejected с
  `auth_required` error. Constant-time compare (hmac.compare_digest) to
  avoid timing-channel attacks.
- Token never logged. If env var missing на startup, sidecar exits 2.

This is per-launch isolation, not cryptographic identity. Adversary с full
process inspection can read env vars; goal is defense against opportunistic
local probes, not against root-level attackers.
"""

from __future__ import annotations

import hmac
import os
import sys

ENV_VAR = "AURORA_SIDECAR_AUTH_TOKEN"
EXPECTED_TOKEN_HEX_LEN = 64  # 32 bytes hex-encoded


class AuthError(ValueError):
    """Raised when authentication fails. Sidecar replies с `auth_required` error."""


def load_token_from_env() -> str:
    """Read launch-time token. Exits с code 2 if missing — fail-closed."""
    token = os.environ.get(ENV_VAR, "")
    if not token:
        sys.stderr.write(
            f"[aurora-sidecar] FATAL: {ENV_VAR} env var not set. "
            f"Parent process must inject it.\n"
        )
        sys.exit(2)
    if len(token) != EXPECTED_TOKEN_HEX_LEN or not all(
        c in "0123456789abcdefABCDEF" for c in token
    ):
        sys.stderr.write(
            f"[aurora-sidecar] FATAL: {ENV_VAR} must be 64-char hex string. "
            f"Got len={len(token)}.\n"
        )
        sys.exit(2)
    return token


def check_auth(presented: str, expected: str) -> None:
    """Constant-time compare. Raises `AuthError` on mismatch."""
    if not isinstance(presented, str) or not presented:
        raise AuthError("auth field missing or empty")
    if len(presented) != len(expected):
        raise AuthError("auth length mismatch")
    if not hmac.compare_digest(presented, expected):
        raise AuthError("auth token invalid")
