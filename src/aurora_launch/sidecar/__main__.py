"""Sidecar entry point. Invoked as:
- `python -m aurora_launch.sidecar`           (dev)
- `aurora-sidecar.exe / aurora-sidecar` (PyInstaller-built binary in production)

Block 4 audit D1: long-running daemon spawned by Rust at app startup.

Phase 2.D.1 HE-2: auth token читается через combined loader (stdin first
line preferred, env var fallback). Reduces env exposure surface.
"""

from __future__ import annotations

import sys

from aurora_launch.sidecar.server import serve_forever


def main() -> int:
    return serve_forever()


if __name__ == "__main__":
    sys.exit(main())
