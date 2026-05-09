"""Sidecar JSON-RPC protocol — message shapes + parsing/serialisation.

Wire format: newline-delimited JSON, each line = one message.
Direction:
- Rust → Python: requests {id, method, params, auth}
- Python → Rust: responses {id, result} | {id, error}
- Python → Rust: events {event, params}  (no id; unsolicited)

Block 4 audit D3.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class Request:
    id: int
    method: str
    params: dict[str, Any]
    auth: str

    @classmethod
    def from_line(cls, line: str) -> "Request":
        data = json.loads(line)
        return cls(
            id=int(data["id"]),
            method=str(data["method"]),
            params=data.get("params") or {},
            auth=str(data.get("auth", "")),
        )


@dataclass(frozen=True)
class ErrorPayload:
    kind: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "message": self.message}


@dataclass(frozen=True)
class Response:
    id: int
    result: Any = None
    error: Optional[ErrorPayload] = None

    def to_line(self) -> str:
        payload: dict[str, Any] = {"id": self.id}
        if self.error is not None:
            payload["error"] = self.error.to_dict()
        else:
            payload["result"] = self.result
        return json.dumps(payload, ensure_ascii=False) + "\n"


@dataclass(frozen=True)
class Event:
    event: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_line(self) -> str:
        return json.dumps(
            {"event": self.event, "params": self.params}, ensure_ascii=False
        ) + "\n"


class ProtocolError(ValueError):
    """Raised when an incoming line cannot be parsed as a valid Request."""


def parse_request_line(line: str) -> Request:
    """Wrapper around `Request.from_line` с consistent error type."""
    line = line.strip()
    if not line:
        raise ProtocolError("empty line")
    try:
        return Request.from_line(line)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ProtocolError(f"malformed request: {exc}") from exc
