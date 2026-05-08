"""Bundle atomic write + rolling backup rotation (B1 sprint).

Implements Aurora bundle persistence with safety guarantees:
- Atomic write via `<path>.aurora.tmp` + `os.replace` (cross-platform)
- Rolling backups: `<path>.aurora.bak.1`, `.bak.2`, `.bak.3`, `.bak.4`
- Backup rotation on each successful write
- Resilient к interrupted writes (tmp file cleanup)

Per memory feedback_circular_import_shared_module.md и audit B7 fix:
`os.replace` is atomic on Windows (since Python 3.3 win32 implementation
uses MoveFileExW с MOVEFILE_REPLACE_EXISTING — atomic at filesystem level).
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

_log = logging.getLogger(__name__)

# Per memory: 4 rolling backups (.bak.1 newest, .bak.4 oldest before deletion)
DEFAULT_BACKUP_COUNT = 4


def atomic_write_bundle(
    path: Path,
    content_bytes: bytes,
    *,
    backup_count: int = DEFAULT_BACKUP_COUNT,
) -> None:
    """Write bundle to `path` atomically с backup rotation.

    Steps:
    1. Write content to `<path>.aurora.tmp`
    2. If `path` exists — rotate backups (`.bak.N` → `.bak.N+1`, oldest dropped)
    3. Move existing `path` to `.bak.1`
    4. `os.replace(tmp, path)` — atomic finalize

    Crash safety:
    - Crash during step 1 → `.tmp` orphan exists; backups intact, original valid
    - Crash during step 2-3 → some backups may be misnamed; original may exist as .bak.1
    - Crash during step 4 → original gone, tmp file present (manual recovery from .bak.1)

    Cross-platform atomicity: `os.replace` atomic on POSIX + Windows (Python 3.3+).
    """
    path = Path(path)
    tmp_path = Path(f"{path}.tmp")

    # Cleanup orphan tmp from previous interrupted write
    if tmp_path.exists():
        try:
            tmp_path.unlink()
            _log.debug("Cleaned orphan tmp: %s", tmp_path)
        except OSError as exc:
            _log.warning("Failed to clean orphan tmp %s: %s", tmp_path, exc)

    # Step 1: write tmp
    path.parent.mkdir(parents=True, exist_ok=True)
    with tmp_path.open("wb") as f:
        f.write(content_bytes)
        f.flush()
        try:
            os.fsync(f.fileno())  # POSIX flush к disk; no-op on Windows но safe
        except (OSError, AttributeError):
            pass  # Some filesystems don't support fsync; non-fatal

    # Step 2-3: rotate backups + move existing к .bak.1
    if path.exists():
        _rotate_backups(path, backup_count)

    # Step 4: atomic replace (this is the critical step)
    os.replace(tmp_path, path)

    _log.info("Bundle saved atomically: %s", path)


def _rotate_backups(path: Path, backup_count: int) -> None:
    """Rotate `.bak.N` chain — oldest deleted, others renamed.

    Before:
        path.aurora       (current — будет moved to .bak.1)
        path.aurora.bak.1 (will become .bak.2)
        path.aurora.bak.2 (will become .bak.3)
        path.aurora.bak.3 (will become .bak.4)
        path.aurora.bak.4 (will be DELETED)

    After:
        path.aurora       (новый — written by caller after this)
        path.aurora.bak.1 (was current)
        path.aurora.bak.2 (was bak.1)
        path.aurora.bak.3 (was bak.2)
        path.aurora.bak.4 (was bak.3)
    """
    # Iterate from oldest к newest — drop oldest, rename others
    # Step backwards from backup_count to 1
    oldest_path = Path(f"{path}.bak.{backup_count}")
    if oldest_path.exists():
        try:
            oldest_path.unlink()
            _log.debug("Dropped oldest backup: %s", oldest_path)
        except OSError as exc:
            _log.warning("Failed to drop oldest backup %s: %s", oldest_path, exc)

    # Rename .bak.N к .bak.N+1 (от backup_count-1 down к 1)
    for i in range(backup_count - 1, 0, -1):
        src = Path(f"{path}.bak.{i}")
        dst = Path(f"{path}.bak.{i + 1}")
        if src.exists():
            try:
                os.replace(src, dst)
            except OSError as exc:
                _log.warning("Failed to rotate backup %s → %s: %s", src, dst, exc)

    # Move current к .bak.1
    bak1 = Path(f"{path}.bak.1")
    try:
        os.replace(path, bak1)
    except OSError as exc:
        _log.warning("Failed to move current к .bak.1: %s", exc)


def restore_from_backup(path: Path, backup_index: int = 1) -> bool:
    """Restore bundle from `.bak.N` (1=newest, default).

    Returns True if restored successfully, False if no backup at that index.
    """
    path = Path(path)
    bak_path = Path(f"{path}.bak.{backup_index}")

    if not bak_path.exists():
        _log.warning("Backup not found: %s", bak_path)
        return False

    # Copy (don't move) so .bak.N stays available for second restore
    shutil.copy2(bak_path, path)
    _log.info("Bundle restored from %s", bak_path)
    return True


def list_backups(path: Path, backup_count: int = DEFAULT_BACKUP_COUNT) -> list[Path]:
    """List existing backup files for given bundle path."""
    path = Path(path)
    return [
        Path(f"{path}.bak.{i}")
        for i in range(1, backup_count + 1)
        if Path(f"{path}.bak.{i}").exists()
    ]


def cleanup_orphan_tmp_files(directory: Path) -> int:
    """Sweep directory for `*.tmp` orphan files (crash recovery utility).

    Returns count of orphans cleaned.
    """
    directory = Path(directory)
    if not directory.exists():
        return 0

    cleaned = 0
    for tmp_path in directory.glob("*.tmp"):
        try:
            tmp_path.unlink()
            cleaned += 1
            _log.info("Cleaned orphan tmp: %s", tmp_path)
        except OSError as exc:
            _log.warning("Failed to clean %s: %s", tmp_path, exc)
    return cleaned
