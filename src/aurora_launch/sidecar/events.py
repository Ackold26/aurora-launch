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
from typing import Any, IO

from aurora_launch.sidecar.protocol import Event

_lock = threading.Lock()


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
