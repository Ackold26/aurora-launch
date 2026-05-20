"""Tests for ``aurora_launch.sidecar.events.emit_mcmc_progress`` + factory (Sprint 2 D4')."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from aurora_launch.sidecar import events
from aurora_launch.sidecar.events import (
    build_mcmc_progress_callback,
    emit_mcmc_progress,
)


# ─── emit_mcmc_progress — event name + payload shape ──────────────────────────


class TestEmitMcmcProgress:
    """Verify event name and payload structure."""

    def test_emits_under_mcmc_progress_event_name(self) -> None:
        with patch.object(events, "emit") as mocked:
            emit_mcmc_progress(handle="abc", pct=42.5, message="Sampling")
        assert mocked.call_count == 1
        event_name = mocked.call_args.args[0]
        assert event_name == "mcmc_progress"

    def test_payload_contains_handle_pct_message_phase(self) -> None:
        with patch.object(events, "emit") as mocked:
            emit_mcmc_progress(
                handle="abc-123",
                pct=37.0,
                message="Drawing posterior",
                phase="sampling",
            )
        payload = mocked.call_args.args[1]
        assert payload == {
            "handle": "abc-123",
            "pct": 37.0,
            "message": "Drawing posterior",
            "phase": "sampling",
        }

    def test_phase_defaults_to_sampling(self) -> None:
        with patch.object(events, "emit") as mocked:
            emit_mcmc_progress(handle="h", pct=50.0, message="m")
        assert mocked.call_args.args[1]["phase"] == "sampling"

    def test_accepts_adaptation_phase(self) -> None:
        with patch.object(events, "emit") as mocked:
            emit_mcmc_progress(handle="h", pct=10.0, message="m", phase="adaptation")
        assert mocked.call_args.args[1]["phase"] == "adaptation"

    def test_accepts_diagnostics_phase(self) -> None:
        with patch.object(events, "emit") as mocked:
            emit_mcmc_progress(handle="h", pct=99.0, message="m", phase="diagnostics")
        assert mocked.call_args.args[1]["phase"] == "diagnostics"

    def test_accepts_done_phase(self) -> None:
        with patch.object(events, "emit") as mocked:
            emit_mcmc_progress(handle="h", pct=100.0, message="m", phase="done")
        assert mocked.call_args.args[1]["phase"] == "done"


# ─── emit_mcmc_progress — defensive pct clamping ──────────────────────────────


class TestEmitMcmcProgressClamping:
    """Defensive clamping protects downstream against bad callback math."""

    def test_clamps_negative_pct_to_zero(self) -> None:
        with patch.object(events, "emit") as mocked:
            emit_mcmc_progress(handle="h", pct=-5.0, message="m")
        assert mocked.call_args.args[1]["pct"] == 0.0

    def test_clamps_above_hundred_to_hundred(self) -> None:
        with patch.object(events, "emit") as mocked:
            emit_mcmc_progress(handle="h", pct=150.0, message="m")
        assert mocked.call_args.args[1]["pct"] == 100.0

    def test_passes_through_zero(self) -> None:
        with patch.object(events, "emit") as mocked:
            emit_mcmc_progress(handle="h", pct=0.0, message="m")
        assert mocked.call_args.args[1]["pct"] == 0.0

    def test_passes_through_hundred(self) -> None:
        with patch.object(events, "emit") as mocked:
            emit_mcmc_progress(handle="h", pct=100.0, message="m")
        assert mocked.call_args.args[1]["pct"] == 100.0

    def test_coerces_int_pct_to_float(self) -> None:
        with patch.object(events, "emit") as mocked:
            emit_mcmc_progress(handle="h", pct=42, message="m")  # type: ignore[arg-type]
        assert isinstance(mocked.call_args.args[1]["pct"], float)


# ─── build_mcmc_progress_callback — factory + dispatch behaviour ──────────────


class TestBuildMcmcProgressCallback:
    """Factory builds train_model-compatible callbacks."""

    def test_returns_callable(self) -> None:
        cb = build_mcmc_progress_callback("h")
        assert callable(cb)

    def test_callback_signature_matches_train_model(self) -> None:
        """train_model expects Callable[[float, str], None]."""
        cb = build_mcmc_progress_callback("h")
        # Should accept (float, str) — call must not raise type-wise
        with patch.object(events, "emit"):
            cb(50.0, "Adapting")

    def test_callback_emits_mcmc_progress_with_handle(self) -> None:
        with patch.object(events, "emit") as mocked:
            cb = build_mcmc_progress_callback("training-xyz")
            cb(75.5, "Drawing samples")
        assert mocked.call_count == 1
        payload = mocked.call_args.args[1]
        assert payload["handle"] == "training-xyz"
        assert payload["pct"] == 75.5
        assert payload["message"] == "Drawing samples"

    def test_callback_phase_baked_in_at_factory_time(self) -> None:
        with patch.object(events, "emit") as mocked:
            cb = build_mcmc_progress_callback("h", phase="adaptation")
            cb(10.0, "Adapt")
        assert mocked.call_args.args[1]["phase"] == "adaptation"

    def test_callback_default_phase_is_sampling(self) -> None:
        with patch.object(events, "emit") as mocked:
            cb = build_mcmc_progress_callback("h")
            cb(50.0, "Sample")
        assert mocked.call_args.args[1]["phase"] == "sampling"

    def test_callback_swallows_emit_exception(self) -> None:
        """Defence-in-depth: emit failure must not crash training thread."""

        def broken_emit(*_args, **_kwargs):
            raise RuntimeError("broken protocol")

        with patch.object(events, "emit", side_effect=broken_emit):
            cb = build_mcmc_progress_callback("h")
            # If exception propagated, this would raise — assertion is the absence
            cb(50.0, "Sample")

    def test_two_factories_distinct_handles(self) -> None:
        """Each factory closes over its own handle without crosstalk."""
        with patch.object(events, "emit") as mocked:
            cb_a = build_mcmc_progress_callback("job-a")
            cb_b = build_mcmc_progress_callback("job-b")
            cb_a(25.0, "Phase A")
            cb_b(75.0, "Phase B")
        handles = [c.args[1]["handle"] for c in mocked.call_args_list]
        assert handles == ["job-a", "job-b"]

    def test_callback_applies_pct_clamping_through_emit(self) -> None:
        """Callback path uses emit_mcmc_progress → clamping carries through."""
        with patch.object(events, "emit") as mocked:
            cb = build_mcmc_progress_callback("h")
            cb(-100.0, "Bad math")
        assert mocked.call_args.args[1]["pct"] == 0.0


# ─── Integration с train_model-style pattern ──────────────────────────────────


class TestTrainModelIntegrationPattern:
    """Verify the factory's callback can be used как train_model's progress_callback arg."""

    def test_simulated_train_loop_emits_progress_events(self) -> None:
        """Simulate a train_model run by calling the callback in a loop;
        verify each tick produces a single mcmc_progress event с правильным handle."""

        captured: list[dict] = []

        def fake_emit(event_name: str, payload: dict) -> None:
            captured.append({"event": event_name, "payload": payload})

        with patch.object(events, "emit", side_effect=fake_emit):
            cb = build_mcmc_progress_callback("sim-handle", phase="sampling")
            for i in range(1, 11):
                cb(i * 10.0, f"Step {i}")

        assert len(captured) == 10
        assert all(c["event"] == "mcmc_progress" for c in captured)
        assert all(c["payload"]["handle"] == "sim-handle" for c in captured)
        # progress monotonic
        pcts = [c["payload"]["pct"] for c in captured]
        assert pcts == sorted(pcts)
        assert pcts[0] == 10.0
        assert pcts[-1] == 100.0


# ─── Module surface guard ─────────────────────────────────────────────────────


def test_event_name_constant_stable() -> None:
    """If event name ever changes — frontend listener will break.  Pin it."""
    with patch.object(events, "emit") as mocked:
        emit_mcmc_progress(handle="h", pct=50.0, message="m")
    # Frontend subscribes к sidecar://mcmc_progress — sidecar emit'ит без prefix
    assert mocked.call_args.args[0] == "mcmc_progress"
