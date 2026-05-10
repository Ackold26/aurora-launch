"""Sidecar protocol + server tests. INV-02 runtime smoke (call public method,
не just import) + INV-08 real pytest run.
"""

from __future__ import annotations

import io
import json
import secrets

import pytest

from aurora_launch.sidecar.protocol import (
    Event,
    ProtocolError,
    Request,
    Response,
    parse_request_line,
)
from aurora_launch.sidecar.server import serve_once


@pytest.fixture
def token() -> str:
    return secrets.token_hex(32)


class TestProtocol:
    def test_request_round_trip(self):
        req = Request(id=1, method="ping", params={}, auth="x")
        line = (
            json.dumps({"id": req.id, "method": req.method, "params": req.params, "auth": req.auth})
            + "\n"
        )
        parsed = parse_request_line(line)
        assert parsed == req

    def test_response_to_line_with_result(self):
        line = Response(id=42, result={"ok": True}).to_line()
        data = json.loads(line)
        assert data == {"id": 42, "result": {"ok": True}}

    def test_response_to_line_with_error(self):
        from aurora_launch.sidecar.protocol import ErrorPayload

        line = Response(id=42, error=ErrorPayload("auth_required", "missing")).to_line()
        data = json.loads(line)
        assert data == {"id": 42, "error": {"kind": "auth_required", "message": "missing"}}

    def test_event_to_line(self):
        line = Event(event="forecast_progress", params={"week": 0, "ci_lower": 100.0}).to_line()
        data = json.loads(line)
        assert data == {"event": "forecast_progress", "params": {"week": 0, "ci_lower": 100.0}}

    def test_empty_line_rejected(self):
        with pytest.raises(ProtocolError):
            parse_request_line("")

    def test_malformed_json_rejected(self):
        with pytest.raises(ProtocolError):
            parse_request_line("{not json}")

    def test_missing_method_rejected(self):
        with pytest.raises(ProtocolError):
            parse_request_line('{"id": 1, "auth": "x"}')


class TestServerSmoke:
    """INV-02: runtime smoke — call serve_once с real method invocation,
    не just module import."""

    def _request(self, method: str, params: dict, auth: str, req_id: int = 1) -> str:
        return json.dumps(
            {"id": req_id, "method": method, "params": params, "auth": auth}
        )

    def test_ping_round_trip(self, token: str):
        out = io.StringIO()
        keep = serve_once(self._request("ping", {}, token), expected_token=token, out=out)
        assert keep is True
        line = out.getvalue().strip()
        data = json.loads(line)
        assert data["id"] == 1
        assert data["result"]["pong"] is True
        assert "version" in data["result"]
        assert "ping" in data["result"]["methods"]

    def test_unknown_method_returns_method_not_found(self, token: str):
        out = io.StringIO()
        serve_once(self._request("nonexistent", {}, token), expected_token=token, out=out)
        data = json.loads(out.getvalue().strip())
        assert data["error"]["kind"] == "method_not_found"

    def test_bad_token_returns_auth_required(self, token: str):
        out = io.StringIO()
        bad = secrets.token_hex(32)
        serve_once(self._request("ping", {}, bad), expected_token=token, out=out)
        data = json.loads(out.getvalue().strip())
        assert data["error"]["kind"] == "auth_required"

    def test_missing_token_returns_auth_required(self, token: str):
        out = io.StringIO()
        serve_once(self._request("ping", {}, ""), expected_token=token, out=out)
        data = json.loads(out.getvalue().strip())
        assert data["error"]["kind"] == "auth_required"

    def test_malformed_line_returns_protocol_error(self, token: str):
        out = io.StringIO()
        keep = serve_once("{not json}", expected_token=token, out=out)
        assert keep is True
        data = json.loads(out.getvalue().strip())
        assert data["error"]["kind"] == "protocol_error"
        assert data["id"] == -1

    def test_shutdown_returns_keep_running_false(self, token: str):
        out = io.StringIO()
        keep = serve_once(
            self._request("shutdown", {}, token), expected_token=token, out=out
        )
        assert keep is False
        data = json.loads(out.getvalue().strip())
        assert data["result"]["shutting_down"] is True
        # New return shape — empty lists when no in-flight forecasts.
        assert data["result"]["forecasts_signaled"] == []
        assert data["result"]["forecasts_joined"] == []
        assert data["result"]["forecasts_timed_out"] == []

    def test_shutdown_drains_inflight_forecast(self, token: str):
        """When `shutdown` runs while a forecast thread is alive, the cancel
        flag is set and the thread is joined within the per-forecast timeout.

        Uses a fake cooperative thread that exits as soon as its flag is set —
        mirrors the contract of the real sampler в `cancel_forecast`.
        """
        import threading
        from aurora_launch.sidecar import methods as sidecar_methods

        # Snapshot module state to restore after test (other tests may register
        # their own forecasts via start_forecast; cleanup keeps suite hermetic).
        original_flags = dict(sidecar_methods._cancel_flags)
        original_threads = dict(sidecar_methods._forecast_threads)

        handle = "fake-handle-abc"
        flag = threading.Event()

        def _fake_sampler() -> None:
            # Wait for cancel signal; exit promptly когда flag set.
            flag.wait(timeout=2.0)

        thread = threading.Thread(target=_fake_sampler, daemon=True)
        thread.start()
        sidecar_methods._cancel_flags[handle] = flag
        sidecar_methods._forecast_threads[handle] = thread

        try:
            out = io.StringIO()
            keep = serve_once(
                self._request("shutdown", {}, token),
                expected_token=token,
                out=out,
            )
            assert keep is False
            data = json.loads(out.getvalue().strip())
            assert data["result"]["shutting_down"] is True
            assert handle in data["result"]["forecasts_signaled"]
            assert handle in data["result"]["forecasts_joined"]
            assert handle not in data["result"]["forecasts_timed_out"]
            assert flag.is_set(), "cancel flag must be set by shutdown"
            assert not thread.is_alive(), "thread must have joined"
        finally:
            # Restore registry to pre-test state — никаких висящих handles.
            sidecar_methods._cancel_flags.clear()
            sidecar_methods._cancel_flags.update(original_flags)
            sidecar_methods._forecast_threads.clear()
            sidecar_methods._forecast_threads.update(original_threads)

    def test_save_bundle_initial_creates_file(self, token: str, tmp_path):
        """End-to-end: sidecar creates new bundle через JSON-RPC."""
        import base64

        target = tmp_path / "fresh.aurora"
        params = {
            "source_path": "/nonexistent/source.aurora",  # forces initial-create branch
            "target_path": str(target),
            "extra_files": {
                "data.json": base64.b64encode(b'{"k":1}').decode("ascii"),
            },
        }
        out = io.StringIO()
        serve_once(self._request("save_bundle", params, token), expected_token=token, out=out)
        data = json.loads(out.getvalue().strip())
        assert "result" in data, data
        assert target.exists()
        assert data["result"]["revision"] == 0

    def test_inspect_bundle_entry_json_roundtrip(self, token: str, tmp_path):
        """Build a real bundle с JSON entry, then read it через sidecar."""
        from aurora_launch.engines.bundle_container import BundleZipWriter

        target = tmp_path / "inspect.aurora"
        writer = BundleZipWriter(aurora_app_version="0.1.0")
        writer.add_file("metadata.json", b'{"hello": "world"}')
        writer.write(target)

        params = {"bundle_path": str(target), "entry": "metadata.json"}
        out = io.StringIO()
        serve_once(
            self._request("inspect_bundle_entry_json", params, token),
            expected_token=token,
            out=out,
        )
        data = json.loads(out.getvalue().strip())
        assert data["result"]["payload"] == {"hello": "world"}

    def test_parse_data_file_unsupported_returns_error(self, token: str, tmp_path):
        """Unknown file format returns structured `unsupported_format` error."""
        bad_file = tmp_path / "random.bin"
        bad_file.write_bytes(b"\x00\x01\x02nothing recognizable")

        params = {"path": str(bad_file)}
        out = io.StringIO()
        serve_once(
            self._request("parse_data_file", params, token), expected_token=token, out=out
        )
        data = json.loads(out.getvalue().strip())
        assert data["error"]["kind"] == "unsupported_format"
