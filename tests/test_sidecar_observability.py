"""Integration tests — aurora_observability wiring in sidecar/server.py.

Sprint Buffer #50: verify 3 structured emission points:
  #1  serve_forever() → sidecar_started (INFO)
  #2  serve_forever() autosave init failure → autosave_init_failed (WARNING)
  #3  serve_once() unexpected dispatch exception → dispatch_error (ERROR + exc_info)
"""

from __future__ import annotations

import io
import json
import os
import secrets
import sys
from typing import Any
from unittest.mock import patch

import pytest

import aurora_launch.sidecar.server as _server_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json_lines(text: str) -> list[dict[str, Any]]:
    """Parse all valid JSON lines from captured text."""
    lines = []
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            lines.append(json.loads(raw))
        except json.JSONDecodeError:
            pass
    return lines


def _find_message(lines: list[dict[str, Any]], message: str) -> dict[str, Any] | None:
    for line in lines:
        if line.get("message") == message:
            return line
    return None


def _redirect_log_to_buf(buf: io.StringIO) -> None:
    """Point all handlers of _log onto buf so capsys can't intercept a closed stream.

    StructuredLogger stores a StreamHandler added at first instantiation.
    The handler holds a reference to sys.stderr at the time it was created;
    under capsys that object gets swapped.  We redirect explicitly so the
    handler writes into our StringIO buf instead.
    """
    for handler in _server_mod._log._logger.handlers:
        if getattr(handler, "_aurora_obs_handler", False):
            handler.stream = buf


# ---------------------------------------------------------------------------
# Test 1: serve_forever() emits sidecar_started on startup
# ---------------------------------------------------------------------------

def test_sidecar_startup_emits_structured_log(monkeypatch):
    """serve_forever() with EOF stdin emits a JSON sidecar_started line."""
    token = secrets.token_hex(32)

    monkeypatch.setenv("AURORA_SIDECAR_AUTH_TOKEN", token)
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    buf = io.StringIO()
    _redirect_log_to_buf(buf)

    with patch("aurora_launch.sidecar.events.emit"):
        exit_code = _server_mod.serve_forever(token)

    assert exit_code == 0

    lines = _parse_json_lines(buf.getvalue())
    record = _find_message(lines, "sidecar_started")
    assert record is not None, (
        f"Expected 'sidecar_started' JSON line. Got:\n{buf.getvalue()!r}"
    )
    assert record.get("component") == "aurora_launch.sidecar.server"
    assert "pid" in record, "Expected 'pid' field in sidecar_started log"
    assert isinstance(record["pid"], int)
    assert record["pid"] == os.getpid()

    # ISO 8601 timestamp sanity check
    ts = record.get("ts", "")
    assert ts, "Expected non-empty 'ts' field"
    assert "T" in ts, f"Expected ISO 8601 timestamp, got: {ts!r}"


# ---------------------------------------------------------------------------
# Test 2: serve_once() dispatch exception emits dispatch_error
# ---------------------------------------------------------------------------

def test_dispatch_error_emits_exception_log():
    """serve_once() with a dispatch method that raises emits dispatch_error JSON."""
    token = secrets.token_hex(32)

    def _failing_dispatch(method: str, params: Any) -> Any:
        raise RuntimeError("synthetic dispatch failure")

    request_line = json.dumps({
        "id": 99,
        "method": "ping",
        "params": {},
        "auth": token,
    })

    buf = io.StringIO()
    _redirect_log_to_buf(buf)

    out = io.StringIO()
    with patch.object(_server_mod, "dispatch", _failing_dispatch):
        keep = _server_mod.serve_once(request_line, expected_token=token, out=out)

    assert keep is True  # server keeps running after error

    # Parse the JSON-RPC error response (stdout)
    response_data = json.loads(out.getvalue().strip())
    assert response_data["error"]["kind"] == "runtimeerror"

    # Parse structured log from the redirected buffer
    lines = _parse_json_lines(buf.getvalue())
    record = _find_message(lines, "dispatch_error")
    assert record is not None, (
        f"Expected 'dispatch_error' JSON line. Got:\n{buf.getvalue()!r}"
    )
    assert record.get("method") == "ping", f"Expected method='ping', got: {record}"
    assert "error_type" in record, (
        "Expected 'error_type' field (from exc_info) in dispatch_error log"
    )
    assert record["error_type"] == "RuntimeError"


# ---------------------------------------------------------------------------
# Test 3: serve_forever() autosave init failure emits autosave_init_failed WARNING
# ---------------------------------------------------------------------------

def test_autosave_init_warning_emits_structured_log(monkeypatch):
    """When _get_autosave_manager raises, serve_forever emits autosave_init_failed WARNING."""
    token = secrets.token_hex(32)

    monkeypatch.setenv("AURORA_SIDECAR_AUTH_TOKEN", token)
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    def _failing_autosave_manager() -> None:
        raise OSError("missing data_root — synthetic failure")

    buf = io.StringIO()
    _redirect_log_to_buf(buf)

    with patch("aurora_launch.sidecar.methods._get_autosave_manager", _failing_autosave_manager), \
         patch("aurora_launch.sidecar.events.emit"):
        exit_code = _server_mod.serve_forever(token)

    assert exit_code == 0

    lines = _parse_json_lines(buf.getvalue())
    record = _find_message(lines, "autosave_init_failed")
    assert record is not None, (
        f"Expected 'autosave_init_failed' JSON line. Got:\n{buf.getvalue()!r}"
    )
    assert record.get("level") == "WARNING", f"Expected WARNING level, got: {record.get('level')}"
    assert "error" in record, "Expected 'error' field in autosave_init_failed log"
    assert "missing data_root" in record["error"]
