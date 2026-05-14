"""Cross-platform advisory file lock for ProjectDB single-writer guarantee (S-04 audit fix).

Closes audit ARCH-06 / S-04: multiple Aurora Launch processes на same Windows
account would write к same projects.db без coordination → WAL conflicts → user
sees random failures OR DB corruption.

Strategy: advisory lock на `<projects.db>.lock` file at process start. Second
process opening DB sees lock contention → user-visible error "Aurora Launch
already running."

Cross-platform:
- POSIX: fcntl.flock с LOCK_EX | LOCK_NB
- Windows: msvcrt.locking с LK_NBLCK on a small region

Released on process exit or explicit release().
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import IO, Any

_log = logging.getLogger(__name__)


class ProcessLockError(RuntimeError):
    """Raised when lock acquisition fails (already held by another process)."""


class ProcessLock:
    """File-based advisory lock. Use as context manager OR explicit acquire/release.

    Usage:
        with ProcessLock(Path("projects.db.lock")):
            # ... DB operations ...
            pass  # released on exit
    """

    def __init__(self, lock_path: Path) -> None:
        self.lock_path = Path(lock_path)
        self._handle: IO[Any] | None = None
        self._acquired = False

    def acquire(self, *, blocking: bool = False) -> bool:
        """Try to acquire exclusive lock. Returns True if acquired.

        Args:
            blocking: if True, wait until lock available (not recommended for UI app)

        Raises:
            ProcessLockError if blocking=False and lock held by another process.
        """
        if self._acquired:
            return True

        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        # Open in r+b mode if exists, else create. Use a+b for cross-platform safety.
        self._handle = open(self.lock_path, "a+b")
        # Write PID into lock file for diagnostics
        try:
            self._handle.seek(0)
            self._handle.truncate()
            self._handle.write(f"pid={os.getpid()}\n".encode())
            self._handle.flush()
        except OSError as exc:
            _log.warning("Cannot write PID к lock file: %s", exc)

        if sys.platform.startswith("win"):
            return self._acquire_windows(blocking=blocking)
        else:
            return self._acquire_posix(blocking=blocking)

    def _acquire_windows(self, *, blocking: bool) -> bool:
        import msvcrt
        try:
            mode = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK
            self._handle.seek(0)
            msvcrt.locking(self._handle.fileno(), mode, 1)
            self._acquired = True
            return True
        except OSError as exc:
            # PI-RESCUE-08 audit fix: both blocking + non-blocking paths raise on OSError.
            # Previously blocking=True silently returned False, masking real failures
            # (permission denied, ENFILE, etc.) as innocent "lock contended."
            self._close_handle()
            raise ProcessLockError(
                f"Lock {self.lock_path} acquisition failed (blocking={blocking}): {exc}"
            ) from exc

    def _acquire_posix(self, *, blocking: bool) -> bool:
        import fcntl
        try:
            flags = fcntl.LOCK_EX if blocking else (fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(self._handle.fileno(), flags)
            self._acquired = True
            return True
        except OSError as exc:
            # PI-RESCUE-08 audit fix: same as Windows — both paths raise.
            self._close_handle()
            raise ProcessLockError(
                f"Lock {self.lock_path} acquisition failed (blocking={blocking}): {exc}"
            ) from exc

    def release(self) -> None:
        if not self._acquired or self._handle is None:
            return
        try:
            if sys.platform.startswith("win"):
                import msvcrt
                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        except OSError as exc:
            _log.warning("Lock release failed (probably already released): %s", exc)
        finally:
            self._close_handle()
            self._acquired = False

    def _close_handle(self) -> None:
        if self._handle is not None:
            try:
                self._handle.close()
            except OSError:
                pass
            self._handle = None

    def __enter__(self) -> ProcessLock:
        self.acquire(blocking=False)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()

    def __del__(self) -> None:
        self.release()
