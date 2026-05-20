"""Sidecar shared stdout writer + event emitter.

Block 4 audit B4-S3 fix: previously `events.emit` had its own lock и server
responses bypassed it → byte-interleaving race на same stdout FD broke JSON
newline framing under concurrent forecast streaming + RPC responses.

Now: ALL writes к stdout go through `write_line()` here. Single module-level
lock serialises responses + events. Stdout flushed after each line so Rust
parent receives messages without OS buffering delays.
"""

from __future__ import annotations

import sys
import threading
from collections.abc import Callable
from typing import Any, IO, Literal

from aurora_launch.sidecar.protocol import Event

_lock = threading.Lock()

McmcPhase = Literal["adaptation", "sampling", "diagnostics", "done"]


def write_line(line: str, *, out: IO[str] | None = None) -> None:
    """Thread-safe atomic line write + flush. Use this for every stdout write
    (both responses + events), so newline-delimited framing stays intact under
    concurrent emitter threads."""
    target = out if out is not None else sys.stdout
    if not line.endswith("\n"):
        line = line + "\n"
    with _lock:
        target.write(line)
        target.flush()


def emit(event_name: str, params: dict[str, Any] | None = None) -> None:
    """Emit unsolicited event к Rust. Thread-safe + stdout-flushed."""
    line = Event(event=event_name, params=params or {}).to_line()
    write_line(line)


# ─── Sprint 2 D4': MCMC iteration progress events ────────────────────────────


def emit_mcmc_progress(
    *,
    handle: str,
    pct: float,
    message: str,
    phase: McmcPhase = "sampling",
) -> None:
    """Emit ``mcmc_progress`` event (Sprint 2 D4').

    Surfaces per-iteration progress from PyMC-backed training to the
    frontend wait UX. The frontend wait modal subscribes to this event
    and drives the progress bar + tip rotation timer.

    Parameters
    ----------
    handle : str
        Correlation id linking progress ticks to a specific training/forecast
        job. Frontend filters by handle to support concurrent jobs.
    pct : float
        Progress 0..100. Out-of-range values are clamped (defensive — bad
        callback math should not break the protocol downstream).
    message : str
        Human-readable status, e.g. "Adapting NUTS sampler", "Drawing samples".
    phase : "adaptation" | "sampling" | "diagnostics" | "done"
        Phase label for frontend progress indicator. Default "sampling".

    Notes
    -----
    Frontend listens on ``sidecar://mcmc_progress``. Payload keys are
    ``handle``, ``pct``, ``message``, ``phase``.
    """
    clamped_pct = max(0.0, min(100.0, float(pct)))
    emit(
        "mcmc_progress",
        {
            "handle": handle,
            "pct": clamped_pct,
            "message": message,
            "phase": phase,
        },
    )


def build_mcmc_progress_callback(
    handle: str,
    *,
    phase: McmcPhase = "sampling",
) -> Callable[[float, str], None]:
    """Build a progress_callback compatible с aurora_engines.train_model.

    Returns a callable matching ``Callable[[float, str], None]`` — train_model's
    expected signature — that emits an ``mcmc_progress`` event for the supplied
    handle. Use to plug Aurora Launch sidecar's event bus into training:

    >>> from aurora_engines import train_model
    >>> cb = build_mcmc_progress_callback(handle="abc-123")
    >>> train_model(config, project_dir, progress_callback=cb)

    Callback exceptions are swallowed (defence-in-depth) so an emit failure
    cannot crash the training thread. ``train_model`` itself already swallows
    callback exceptions per its API contract — this is the second layer.

    Parameters
    ----------
    handle : str
        Correlation id forwarded into every emitted event.
    phase : "adaptation" | "sampling" | "diagnostics" | "done"
        Phase label baked into emitted events. Use a different factory per
        phase if the training pipeline reports adaptation vs sampling vs
        diagnostics on separate callback ticks.
    """

    def _cb(pct: float, message: str) -> None:
        try:
            emit_mcmc_progress(handle=handle, pct=pct, message=message, phase=phase)
        except Exception:  # noqa: BLE001 — defence-in-depth, never break training
            pass

    return _cb
