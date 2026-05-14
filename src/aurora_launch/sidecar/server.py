"""Sidecar JSON-RPC server loop.

Reads stdin line-by-line, parses requests, authenticates, dispatches к
method handler, writes response. Unsolicited events emitted independently
through `events.emit()`.

Lifecycle:
- `serve_forever()` blocks on stdin until EOF or `shutdown` method.
- EOF (parent process closed pipe) → exit 0.
- Unhandled exception in dispatch → error response к Rust, server continues.
- `shutdown` method → return result, then break loop, exit 0.

INV-02 runtime smoke target: `serve_once(line, ...)` callable from tests.
"""

from __future__ import annotations

import sys
import traceback
from typing import IO

from aurora_launch.sidecar import events as _events
from aurora_launch.sidecar.auth import AuthError, check_auth, load_token_from_env
from aurora_launch.sidecar.methods import (
    MethodNotFoundError,
    UnsupportedFormatError,
    dispatch,
)
from aurora_launch.sidecar.protocol import (
    ErrorPayload,
    ProtocolError,
    Request,
    Response,
    parse_request_line,
)


def _error_for(exc: BaseException) -> ErrorPayload:
    """Map Python exception к structured AuroraError-like payload (Rust side
    mirrors the kind→i18n mapping)."""
    if isinstance(exc, AuthError):
        return ErrorPayload("auth_required", str(exc))
    if isinstance(exc, ProtocolError):
        return ErrorPayload("protocol_error", str(exc))
    if isinstance(exc, MethodNotFoundError):
        return ErrorPayload("method_not_found", str(exc))
    if isinstance(exc, UnsupportedFormatError):
        return ErrorPayload("unsupported_format", str(exc))
    if isinstance(exc, FileNotFoundError):
        return ErrorPayload("bundle_not_found", str(exc))
    if isinstance(exc, ValueError):
        return ErrorPayload("invalid_input", str(exc))
    return ErrorPayload(type(exc).__name__.lower(), str(exc))


def serve_once(
    line: str,
    *,
    expected_token: str,
    out: IO[str] | None = None,
) -> bool:
    """Process one request line. Returns True if server should keep running,
    False if `shutdown` was requested.

    Used by tests + main loop. INV-02 runtime smoke: callable from pytest.
    """
    out = out or sys.stdout
    try:
        request = parse_request_line(line)
    except ProtocolError as exc:
        # Cannot extract id если parse failed — emit -1 id (best effort)
        resp = Response(id=-1, error=ErrorPayload("protocol_error", str(exc)))
        _events.write_line(resp.to_line(), out=out)
        return True

    try:
        check_auth(request.auth, expected_token)
    except AuthError as exc:
        _events.write_line(Response(id=request.id, error=_error_for(exc)).to_line(), out=out)
        return True

    try:
        result = dispatch(request.method, request.params)
        _events.write_line(Response(id=request.id, result=result).to_line(), out=out)
        if request.method == "shutdown":
            return False
        return True
    except Exception as exc:  # noqa: BLE001
        # Log unexpected errors к stderr (parent collects). Convert к structured
        # error response.
        sys.stderr.write(
            f"[aurora-sidecar] dispatch error in '{request.method}': {exc}\n"
        )
        sys.stderr.write(traceback.format_exc())
        sys.stderr.flush()
        _events.write_line(Response(id=request.id, error=_error_for(exc)).to_line(), out=out)
        return True


def serve_forever(token: str | None = None) -> int:
    """Blocking stdin loop. Returns exit code."""
    expected = token or load_token_from_env()

    # Audit A-05 fix: eagerly initialize AutosaveManager so SIGTERM/atexit
    # handlers register before any work. If init fails (missing data_root
    # etc.), log a warning but continue — sidecar should still serve simple
    # IPC commands that don't touch ProjectDB.
    try:
        from aurora_launch.sidecar.methods import _get_autosave_manager
        _get_autosave_manager()
    except Exception as exc:  # noqa: BLE001
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "AutosaveManager init at sidecar startup failed: %s. "
            "SIGTERM handler NOT registered. ProjectDB-dependent flows "
            "still work but unclean exits won't clear session marker.",
            exc,
        )

    # Boot beacon (event has no id, no auth — emitted under shared write lock
    # so no race with first response).
    _events.emit("sidecar_ready", {})

    for raw_line in sys.stdin:
        if not serve_once(raw_line, expected_token=expected):
            return 0
    return 0
