"""Content-addressed blob storage (Phase 0.1).

Stores msgpack+Ed25519-signed artefacts on disk indexed by SHA-256. Idempotent:
storing identical content returns the same hash and increments ref-count. Used
by ProjectDB to dedupe forecasts/posteriors across versions and projects.

Layout::

    {blobs_dir}/
    └── sha256-<full-hex>.blob      (immutable signed blob payload)

On-disk format: 64-byte Ed25519 signature || raw content bytes.
The SHA-256 key is computed over the raw content bytes (not the signed wrapper),
so the address is stable and project_db.compute_hash() remains consistent with
what store() indexes by.

Signature verification on load: sign(content) detaches the signature from the
content. If content is tampered the signature will fail. If the file itself is
replaced (different sha prefix), the hash-filename mismatch is caught first.

Hard-cut policy (2026-05-14): legacy `.pickle` files are detected by magic bytes
and rejected with BlobLegacyFormatError. No read-pickle fallback — security > compat.
Pilot has no production data so no migration tool needed.

Per memory feedback_smoke_runtime_not_module_level — public functions exercised by tests.
Per memory feedback_silent_error_swallowing — explicit narrow excepts, no bare `pass`.

Design constraints:
- Atomic writes (`.tmp` + os.replace) so concurrent stores never see partial files
- Deterministic filename (sha256 prefix + `.blob`) lets external tools verify
- No fsync-per-blob in tight loops (caller responsible for batching)
- ref_count managed by ProjectDB transactionally (this module is content-only)
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from aurora_launch.persistence.safe_serializer import (
    BlobLegacyFormatError,
    BlobSignatureError,
    _dev_private_key,
    _dev_public_key,
    is_pickle_magic,
    sign_blob,
    verify_blob,
)

_log = logging.getLogger(__name__)

# Suffix changed from .pickle to .blob; prefix unchanged for path-compat.
BLOB_FILE_SUFFIX = ".blob"
BLOB_FILENAME_PREFIX = "sha256-"

# Legacy suffix: kept for detection/warning only, never written.
_LEGACY_SUFFIX = ".pickle"

_SIG_LEN = 64  # Ed25519 signature is always 64 bytes

_LEGACY_PICKLE_MSG = (
    "Legacy pickle blobs unsupported в v0.1.0+. Re-import project from .aurora bundle."
)


class BlobStoreError(RuntimeError):
    """Raised for blob storage failures (corrupted, IO error, hash mismatch)."""


# Re-export so callers only need to import from blob_store
__all__ = [
    "BlobStore",
    "BlobInfo",
    "BlobStoreError",
    "BlobSignatureError",
    "BlobLegacyFormatError",
]


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
    rename semantics on POSIX and Windows ReplaceFile). Multi-process writers
    are safe because writes are idempotent — racing stores of identical
    content produce the same target file.

    On-disk layout per blob file:
        [0:64]  Ed25519 signature over content bytes
        [64:]   raw content bytes (msgpack-encoded payload)

    The SHA-256 address is computed over the raw content bytes (not the
    signature prefix), so compute_hash() is consistent with the storage key
    and project_db can pre-compute hashes before calling store().

    Dev mode: uses an ephemeral Ed25519 keypair (_dev_private_key / _dev_public_key)
    generated at first call and cached for the process lifetime. Production code
    passes explicit keys via BlobStore(blobs_dir, private_key=..., public_key=...).
    """

    def __init__(
        self,
        blobs_dir: Path,
        *,
        private_key=None,
        public_key=None,
    ) -> None:
        """Open blob store at blobs_dir.

        Args:
            blobs_dir: Directory for blob files. Created if absent.
            private_key: Ed25519PrivateKey for signing (default: dev ephemeral key).
            public_key: Ed25519PublicKey for verification (default: dev ephemeral key).
        """
        self.blobs_dir = Path(blobs_dir)
        self.blobs_dir.mkdir(parents=True, exist_ok=True)
        self._private_key = private_key if private_key is not None else _dev_private_key()
        self._public_key = public_key if public_key is not None else _dev_public_key()

    def _path_for(self, sha256: str) -> Path:
        return self.blobs_dir / _blob_filename(sha256)

    @staticmethod
    def compute_hash(content: bytes) -> str:
        """Compute SHA-256 hex digest of content bytes (lowercase).

        Hash is over the raw content bytes (pre-signature), consistent with
        what store() indexes by. project_db calls this to pre-compute hashes.
        """
        if not isinstance(content, (bytes, bytearray, memoryview)):
            raise TypeError(
                f"compute_hash expects bytes-like, got {type(content).__name__}"
            )
        return hashlib.sha256(bytes(content)).hexdigest()

    def _wrap(self, content: bytes) -> bytes:
        """Wrap content in Ed25519 signature: returns sig(64) || content."""
        sig = self._private_key.sign(content)
        return sig + content

    def _unwrap_and_verify(self, on_disk: bytes) -> bytes:
        """Verify Ed25519 signature and return raw content bytes.

        Raises:
            BlobLegacyFormatError: if content looks like legacy pickle.
            BlobSignatureError: if Ed25519 verification fails.
            BlobStoreError: if on_disk is too short to contain a signature.
        """
        # Verify the signature FIRST. The on-disk layout is `sig(64) || content`,
        # so the raw bytes begin with a 64-byte Ed25519 signature whose random
        # leading bytes occasionally collide with pickle magic (0x80 followed by
        # a 0x00–0x05 proto byte). Running is_pickle_magic() on the raw blob —
        # as the previous version did — therefore spuriously rejected ~1-in-10k
        # validly-signed blobs as "legacy pickle" (flaky reads, Sprint Buffer
        # #71). A blob that verifies is, by definition, not a legacy pickle.
        if len(on_disk) < _SIG_LEN:
            # Too short to be a signed blob. A genuine legacy pickle is unsigned
            # raw pickle bytes — surface the actionable error if it looks like one.
            if is_pickle_magic(on_disk):
                raise BlobLegacyFormatError(_LEGACY_PICKLE_MSG)
            raise BlobStoreError(
                f"Blob file too short ({len(on_disk)} bytes) — expected "
                f"≥{_SIG_LEN} bytes for signature header"
            )
        try:
            # verify_blob raises BlobSignatureError on failure (explicit, narrow)
            return verify_blob(on_disk, self._public_key)
        except BlobSignatureError:
            # Verification failed: this is not a blob we signed. Only now is the
            # pickle-magic check meaningful — a legacy pickle is unsigned, so it
            # never verifies. Give the actionable migration error if it matches.
            if is_pickle_magic(on_disk):
                raise BlobLegacyFormatError(_LEGACY_PICKLE_MSG) from None
            raise

    def store(self, content: bytes) -> BlobInfo:
        """Store content; returns BlobInfo (idempotent).

        Args:
            content: Raw bytes to store (msgpack-encoded by caller, or opaque bytes).
                     Will be signed with Ed25519 before writing.

        If a blob with identical hash already exists, no write occurs.
        Atomicity: writes to `<target>.<pid>.tmp` then os.replace.
        """
        sha = self.compute_hash(content)
        wrapped = self._wrap(content)
        target = self._path_for(sha)
        size = len(wrapped)

        if target.exists():
            on_disk = target.stat().st_size
            if on_disk != size:
                raise BlobStoreError(
                    f"Blob {sha} on disk has size {on_disk}, "
                    f"new content produces size {size} — content-addressed contract violated"
                )
            return BlobInfo(sha256=sha, size_bytes=size, storage_path=target)

        tmp = target.with_suffix(target.suffix + f".{os.getpid()}.tmp")
        try:
            with tmp.open("wb") as f:
                f.write(wrapped)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except (OSError, AttributeError):
                    pass  # filesystem doesn't support fsync; non-fatal
            os.replace(tmp, target)
        except OSError as exc:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError as cleanup_exc:
                    _log.warning("Failed to cleanup tmp %s: %s", tmp, cleanup_exc)
            raise BlobStoreError(f"Failed to store blob {sha}: {exc}") from exc

        _log.debug("Stored blob %s (%d bytes content)", sha[:12], len(content))
        return BlobInfo(sha256=sha, size_bytes=size, storage_path=target)

    def load(self, sha256: str) -> bytes:
        """Load blob content. Verifies hash + Ed25519 signature; returns raw bytes.

        Raises:
            BlobStoreError: blob not found or sha256 mismatch (file tampered at fs level).
            BlobLegacyFormatError: blob is legacy pickle (hard-cut policy).
            BlobSignatureError: Ed25519 signature invalid (content tampered).
        """
        _validate_sha256(sha256)
        target = self._path_for(sha256)
        if not target.exists():
            raise BlobStoreError(f"Blob not found: {sha256}")

        on_disk = target.read_bytes()
        # Verify hash over raw content (bytes after signature prefix).
        # We must first split off the sig to get content bytes for hashing.
        # But _unwrap_and_verify also checks legacy magic before splitting.
        content = self._unwrap_and_verify(on_disk)
        actual = self.compute_hash(content)
        if actual != sha256:
            raise BlobStoreError(
                f"Blob integrity check failed: stored at {sha256} but content hashes to {actual}"
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
        """Enumerate all blobs on disk (for GC reconciliation, audit).

        Recognises .blob (current). Legacy .pickle files are logged as warnings
        and excluded from results (hard-cut policy).
        """
        results: list[BlobInfo] = []
        if not self.blobs_dir.exists():
            return results
        for path in self.blobs_dir.iterdir():
            if not path.is_file():
                continue
            name = path.name
            if name.startswith(BLOB_FILENAME_PREFIX) and name.endswith(_LEGACY_SUFFIX):
                _log.warning(
                    "Legacy pickle blob detected (unsupported): %s — "
                    "re-import from .aurora bundle to upgrade.",
                    name,
                )
                continue
            if not name.startswith(BLOB_FILENAME_PREFIX) or not name.endswith(
                BLOB_FILE_SUFFIX
            ):
                continue
            sha = name[len(BLOB_FILENAME_PREFIX) : -len(BLOB_FILE_SUFFIX)]
            if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
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
