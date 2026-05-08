"""Cross-platform advisory file locking for `.aurora` bundles (Block 1A).

Per ADR-002 §"Multi-machine concurrent edit": file lock через `.aurora.lock`
sentinel file. Phase B single-user model — best-effort advisory locking,
not mandatory enforcement.

Strategy:
- POSIX: `fcntl.flock(fd, LOCK_EX | LOCK_NB)` non-blocking exclusive
- Windows: `msvcrt.locking(fd, LK_NBLCK, 1)` non-blocking exclusive byte-range
- Lock file: `<bundle_path>.lock` sidecar (created on acquire, removed on release)
- If lock acquisition fails → `BundleLockError` raised with current holder PID

The lock protects:
- Concurrent writers (only one writer at a time per bundle)
- Reader-during-write race (writers signal exclusive, readers wait or fail-fast)

Stdlib only — no external `portalocker` / `filelock` dependency per ADR-002.
"""

from __future__ import annotations

import contextlib
import logging
import os
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import IO, Literal

_log = logging.getLogger(__name__)

# Platform-specific imports (lazy, conditional)
if sys.platform == "win32":
    import msvcrt
else:
    import fcntl


LockMode = Literal["exclusive", "shared"]


class BundleLockError(RuntimeError):
    """Raised when bundle lock cannot be acquired (another process holds it)."""

    def __init__(self, lock_path: Path, holder_pid: int | None = None) -> None:
        msg = f"Bundle lock held by another process: {lock_path}"
        if holder_pid is not None:
            msg += f" (pid={holder_pid})"
        super().__init__(msg)
        self.lock_path = lock_path
        self.holder_pid = holder_pid


def _lock_path_for(bundle_path: Path) -> Path:
    """Compute sidecar lock path for given bundle."""
    return Path(f"{bundle_path}.lock")


def _try_acquire_posix(fd: int, mode: LockMode) -> bool:
    """Non-blocking POSIX flock. Returns True if acquired, False if held by another."""
    flags = fcntl.LOCK_NB
    flags |= fcntl.LOCK_EX if mode == "exclusive" else fcntl.LOCK_SH
    try:
        fcntl.flock(fd, flags)
        return True
    except (BlockingIOError, OSError):
        return False


def _try_acquire_windows(fd: int, mode: LockMode) -> bool:
    """Non-blocking Windows msvcrt.locking. Locks first byte of file.

    Note: msvcrt.locking does not distinguish shared vs exclusive — it's
    always exclusive on Windows. For Phase B single-user model this is
    acceptable; concurrent shared readers will fall back to optimistic
    revision-counter check at the manifest layer.
    """
    # Seek to byte 0, lock 1 byte non-blocking
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        return True
    except OSError:
        return False


def _release(fd: int) -> None:
    """Platform-appropriate lock release. Errors logged but not raised."""
    try:
        if sys.platform == "win32":
            os.lseek(fd, 0, os.SEEK_SET)
            with contextlib.suppress(OSError):
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            with contextlib.suppress(OSError):
                fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError as exc:
        _log.warning("Failed to release lock fd %d: %s", fd, exc)


@contextlib.contextmanager
def bundle_lock(
    bundle_path: Path,
    mode: LockMode = "exclusive",
    *,
    timeout: float = 0.0,
    poll_interval: float = 0.1,
) -> Iterator[None]:
    """Acquire advisory lock on `<bundle_path>.lock` sidecar.

    Args:
        bundle_path: Path to the bundle file (the `.lock` sidecar is derived).
        mode: "exclusive" (writers) or "shared" (readers, POSIX-only — Windows
            always exclusive).
        timeout: Total seconds to wait for lock (0.0 = non-blocking, fail-fast).
        poll_interval: Delay between retry attempts (seconds).

    Raises:
        BundleLockError: if lock not acquired within timeout.

    The sidecar file persists after release (not deleted, to avoid races).
    PID of current holder written to sidecar for diagnostics.
    """
    lock_path = _lock_path_for(bundle_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    # Open (create if missing) — read-write to allow PID write
    fd: int | None = None
    fileobj: IO[bytes] | None = None
    try:
        # Open file for lock + PID record. O_RDWR + O_CREAT idempotent.
        fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)

        deadline = time.monotonic() + timeout
        acquired = False
        attempts = 0
        while True:
            if sys.platform == "win32":
                acquired = _try_acquire_windows(fd, mode)
            else:
                acquired = _try_acquire_posix(fd, mode)

            if acquired:
                break

            attempts += 1
            if time.monotonic() >= deadline:
                # Try to read holder PID for diagnostics
                holder_pid: int | None = None
                try:
                    os.lseek(fd, 0, os.SEEK_SET)
                    raw = os.read(fd, 32).decode("ascii", errors="ignore").strip()
                    holder_pid = int(raw) if raw.isdigit() else None
                except (OSError, ValueError):
                    pass
                raise BundleLockError(lock_path, holder_pid)

            time.sleep(poll_interval)

        # Acquired — write PID for diagnostics (best effort)
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            os.ftruncate(fd, 0)
            os.write(fd, str(os.getpid()).encode("ascii"))
        except OSError as exc:
            _log.debug("Could not write PID to lock %s: %s", lock_path, exc)

        _log.debug("Acquired %s lock on %s (attempts=%d)", mode, lock_path, attempts)
        yield
    finally:
        if fd is not None:
            _release(fd)
            with contextlib.suppress(OSError):
                os.close(fd)
        if fileobj is not None:
            with contextlib.suppress(OSError):
                fileobj.close()


def is_locked(bundle_path: Path) -> bool:
    """Probe: is `<bundle_path>.lock` currently held by some process?

    Returns True if held by another process, False otherwise. Acquires and
    immediately releases; useful for "would-block" UI hints. Inherently
    racy — caller must still handle BundleLockError on real acquire.
    """
    lock_path = _lock_path_for(bundle_path)
    if not lock_path.exists():
        return False

    fd = None
    try:
        fd = os.open(str(lock_path), os.O_RDWR)
        if sys.platform == "win32":
            acquired = _try_acquire_windows(fd, "exclusive")
        else:
            acquired = _try_acquire_posix(fd, "exclusive")
        if acquired:
            _release(fd)
            return False
        return True
    except OSError:
        return False
    finally:
        if fd is not None:
            with contextlib.suppress(OSError):
                os.close(fd)
