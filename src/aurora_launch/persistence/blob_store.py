"""Content-addressed blob storage (Phase 0.1).

Stores pickle/JSON artefacts на disk indexed by SHA-256. Idempotent: storing
identical content returns the same hash и increments ref-count. Used by
ProjectDB to dedupe forecasts/posteriors across versions and projects.

Layout::

    {blobs_dir}/
    └── sha256-<full-hex>.pickle      (immutable blob payload)

Per memory feedback_smoke_runtime_not_module_level — public functions are
exercised by tests; no import-only smoke. Per memory
feedback_silent_error_swallowing — explicit narrow excepts, no bare `pass`.

Design constraints:
- Atomic writes (`.tmp` + os.replace) so concurrent stores never see partial files
- Deterministic filename (sha256 prefix + `.pickle`) lets external tools verify
- No fsync-per-blob in tight loops (caller responsible for batching)
- ref_count управляется ProjectDB transactionally (this module is content-only)
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from pathlib import Path

_log = logging.getLogger(__name__)

BLOB_FILE_SUFFIX = ".pickle"
BLOB_FILENAME_PREFIX = "sha256-"


class BlobStoreError(RuntimeError):
    """Raised for blob storage failures (corrupted, IO error, hash mismatch)."""


@dataclass(frozen=True)
class BlobInfo:
    """Metadata for a single content-addressed blob on disk."""

    sha256: str
    size_bytes: int
    storage_path: Path


def _blob_filename(sha256: str) -> str:
    return f"{BLOB_FILENAME_PREFIX}{sha256}{BLOB_FILE_SUFFIX}"


def _validate_sha256(sha256: str) -> None:
    if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
        raise BlobStoreError(
            f"Invalid SHA-256 hex (expected 64 lowercase hex chars): {sha256!r}"
        )


class BlobStore:
    """File-backed content-addressed blob store.

    Thread-safe for single-writer + concurrent readers (relies on atomic
    rename semantics на POSIX и Windows ReplaceFile). Multi-process writers
    are safe because writes are idempotent — racing stores of identical
    content produce the same target file.
    """

    def __init__(self, blobs_dir: Path) -> None:
        self.blobs_dir = Path(blobs_dir)
        self.blobs_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, sha256: str) -> Path:
        return self.blobs_dir / _blob_filename(sha256)

    @staticmethod
    def compute_hash(content: bytes) -> str:
        """Compute SHA-256 hex digest of content (lowercase)."""
        if not isinstance(content, (bytes, bytearray, memoryview)):
            raise TypeError(
                f"compute_hash expects bytes-like, got {type(content).__name__}"
            )
        return hashlib.sha256(bytes(content)).hexdigest()

    def store(self, content: bytes) -> BlobInfo:
        """Store content; returns BlobInfo (idempotent).

        If a blob with identical hash already exists, no write occurs — the
        existing file is left intact и BlobInfo points to it.

        Atomicity: writes to `<target>.<pid>.tmp` then os.replace.
        """
        sha = self.compute_hash(content)
        target = self._path_for(sha)
        size = len(content)

        if target.exists():
            # Idempotent — sanity-check size matches (cheap; full re-hash only on demand)
            on_disk = target.stat().st_size
            if on_disk != size:
                raise BlobStoreError(
                    f"Blob {sha} on disk has size {on_disk}, "
                    f"new content has size {size} — content-addressed contract violated"
                )
            return BlobInfo(sha256=sha, size_bytes=size, storage_path=target)

        # Atomic write (unique tmp suffix to avoid concurrent writer collisions)
        tmp = target.with_suffix(target.suffix + f".{os.getpid()}.tmp")
        try:
            with tmp.open("wb") as f:
                f.write(content)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except (OSError, AttributeError):
                    # Filesystem doesn't support fsync; non-fatal на consumer disks
                    pass
            os.replace(tmp, target)
        except OSError as exc:
            # Cleanup tmp on failure
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError as cleanup_exc:
                    _log.warning("Failed to cleanup tmp %s: %s", tmp, cleanup_exc)
            raise BlobStoreError(f"Failed to store blob {sha}: {exc}") from exc

        _log.debug("Stored blob %s (%d bytes)", sha[:12], size)
        return BlobInfo(sha256=sha, size_bytes=size, storage_path=target)

    def load(self, sha256: str) -> bytes:
        """Load blob content. Verifies hash matches stored bytes (integrity check)."""
        _validate_sha256(sha256)
        target = self._path_for(sha256)
        if not target.exists():
            raise BlobStoreError(f"Blob not found: {sha256}")

        content = target.read_bytes()
        actual = self.compute_hash(content)
        if actual != sha256:
            raise BlobStoreError(
                f"Blob integrity check failed: stored at {sha256} но содержит "
                f"content hashing к {actual}"
            )
        return content

    def exists(self, sha256: str) -> bool:
        _validate_sha256(sha256)
        return self._path_for(sha256).exists()

    def info(self, sha256: str) -> BlobInfo:
        """Get BlobInfo without loading content (cheap)."""
        _validate_sha256(sha256)
        target = self._path_for(sha256)
        if not target.exists():
            raise BlobStoreError(f"Blob not found: {sha256}")
        return BlobInfo(
            sha256=sha256,
            size_bytes=target.stat().st_size,
            storage_path=target,
        )

    def delete(self, sha256: str) -> None:
        """Delete blob from disk. Caller (ProjectDB) ensures ref_count=0.

        Tolerant of already-absent: idempotent.
        """
        _validate_sha256(sha256)
        target = self._path_for(sha256)
        try:
            target.unlink()
            _log.debug("Deleted blob %s", sha256[:12])
        except FileNotFoundError:
            pass  # idempotent
        except OSError as exc:
            raise BlobStoreError(f"Failed to delete blob {sha256}: {exc}") from exc

    def list_all(self) -> list[BlobInfo]:
        """Enumerate всех blobs on disk (for GC reconciliation, audit)."""
        results: list[BlobInfo] = []
        if not self.blobs_dir.exists():
            return results
        for path in self.blobs_dir.iterdir():
            if not path.is_file():
                continue
            name = path.name
            if not name.startswith(BLOB_FILENAME_PREFIX) or not name.endswith(
                BLOB_FILE_SUFFIX
            ):
                continue
            sha = name[len(BLOB_FILENAME_PREFIX) : -len(BLOB_FILE_SUFFIX)]
            if len(sha) != 64:
                _log.warning("Skipping malformed blob filename: %s", name)
                continue
            try:
                results.append(
                    BlobInfo(
                        sha256=sha,
                        size_bytes=path.stat().st_size,
                        storage_path=path,
                    )
                )
            except OSError as exc:
                _log.warning("Cannot stat blob %s: %s", path, exc)
        return results

    def total_bytes(self) -> int:
        """Total bytes on disk (sum of all blobs)."""
        return sum(b.size_bytes for b in self.list_all())
