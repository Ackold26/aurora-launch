"""Aurora `.aurora` bundle streaming reader (Block 1C — H9 fix).

Eager `BundleZipReader` from Block 1A loads the full bundle into RAM. For
bundles в 50–200MB diapason (real-data proxy training pickle + similarity
matrices + parquet pages) eager mode kills 8GB machines. This module
adds a lazy-loading reader that:

- reads `manifest.json` upfront (few KB) — cheap
- defers per-entry `bytes` materialisation until first access
- caches recently-accessed entries in a size-bounded LRU (default 512 MB)
- holds an open `ZipFile` handle + shared advisory lock for the lifetime
  of the loaded bundle (released on `close()` or context exit)
- still verifies per-entry SHA-256 against `BundleManifest.files` on first
  access (strict mode raises `BundleIntegrityError`; warn mode logs)
- preserves manifest-level checks (missing files / extra files / zip-slip)
  upfront — those are fast (`namelist()` only)

Backwards-compat:
- `BundleZipReader.read(path)` keeps eager semantics (default).
- `BundleZipReader.read_lazy(path)` — new entrypoint returning
  `LazyLoadedBundle` (subclass of `LoadedBundle`) which acts as a context
  manager.
- Legacy `.aurora.json` bundles fall back к eager regardless — they are
  single-file blobs, lazy is pointless.

Per ADR-002 §"Performance budgets":
- Open large project (200 MB): ≤200 ms (manifest only, models lazy).
- Bundle 200MB peak <600MB RAM via cache cap.

Threading note:
- `LazyLoadedBundle` instances are NOT thread-safe. The underlying
  `zipfile.ZipFile` is documented as not thread-safe; the LRU cache uses
  insertion-order dict mutations. Each thread must open its own bundle.
"""

from __future__ import annotations

import contextlib
import json
import logging
import zipfile
from collections.abc import Iterator, KeysView, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from aurora_launch.engines.bundle_container import (
    MANIFEST_FILENAME,
    BundleFormatError,
    BundleIntegrityError,
    LoadedBundle,
    detect_format,
)
from aurora_launch.engines.bundle_lock import bundle_lock
from aurora_launch.engines.bundle_manifest import (
    BundleManifest,
    compute_file_entry,
)

_log = logging.getLogger(__name__)

DEFAULT_CACHE_BYTES = 512 * 1024 * 1024  # 512 MB per ROADMAP v1.3 §1C

# Audit Block 1D — finding B2: zip-bomb defense. Refuse to read any single
# entry whose declared uncompressed size exceeds this cap. 2 GB is far above
# any legitimate Aurora Launch payload (largest realistic: similarity matrix
# + parquet pages, max ~500 MB combined per bundle).
MAX_ENTRY_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB


# ----------------------------------------------------------------------------
# Size-bounded LRU cache
# ----------------------------------------------------------------------------


class ByteSizeLRU:
    """Insertion-ordered byte cache with total-size cap.

    Eviction is LRU on access (`get` moves the key to end). Setting an
    entry whose size alone exceeds `max_bytes` stores it but immediately
    drops every other resident entry — useful when the caller wants the
    latest large entry без preventing it being cached entirely.

    `max_bytes=0` disables caching (every put is dropped); use it when
    callers want raw lazy reads без eviction overhead.
    """

    def __init__(self, max_bytes: int = DEFAULT_CACHE_BYTES) -> None:
        if max_bytes < 0:
            raise ValueError(f"max_bytes must be >= 0, got {max_bytes}")
        self._max_bytes = max_bytes
        self._data: dict[str, bytes] = {}
        self._size = 0

    @property
    def total_size(self) -> int:
        return self._size

    @property
    def max_bytes(self) -> int:
        return self._max_bytes

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def get(self, key: str) -> bytes | None:
        """Return cached bytes (and mark as recently-used) or None."""
        if key not in self._data:
            return None
        # Move to end for LRU ordering
        value = self._data.pop(key)
        self._data[key] = value
        return value

    def put(self, key: str, value: bytes) -> None:
        """Store bytes, evicting LRU entries until total fits within cap.

        If the key already exists it is replaced (its size released).
        If `max_bytes == 0`, the entry is silently dropped.

        Audit Block 1D — finding H1: a single oversized entry (size >
        max_bytes) is refused entirely и existing entries are preserved.
        Previously eviction would empty the cache then store the oversized
        entry anyway, leaving total size > cap.
        """
        if self._max_bytes == 0:
            return

        size = len(value)
        if size > self._max_bytes:
            # Single entry exceeds cap — refuse to cache. Caller still gets
            # the bytes from the read path; we just don't double-buffer here.
            return

        if key in self._data:
            self._size -= len(self._data[key])
            del self._data[key]

        # Evict LRU until value fits (or cache becomes empty)
        while self._data and self._size + size > self._max_bytes:
            oldest_key = next(iter(self._data))
            self._size -= len(self._data[oldest_key])
            del self._data[oldest_key]

        self._data[key] = value
        self._size += size

    def clear(self) -> None:
        self._data.clear()
        self._size = 0


# ----------------------------------------------------------------------------
# Lazy file mapping (Mapping[str, bytes] proxy)
# ----------------------------------------------------------------------------


class LazyFileMap(Mapping[str, bytes]):
    """Read-only mapping that materialises bundle entries on demand.

    Contracts:
    - keys() / __iter__ / __len__ enumerate from `manifest.files` only
      (not from `zf.namelist()`); `manifest.json` is excluded.
    - `__getitem__(name)` reads bytes from the underlying `ZipFile`,
      verifies SHA-256 against the manifest entry on first access (если
      `manifest.integrity_check != "disabled"` and cache had no copy),
      then caches in the LRU.
    - `__contains__` does NOT trigger a read — checks manifest membership.
    """

    def __init__(self, owner: LazyLoadedBundle) -> None:
        self._owner = owner

    def __getitem__(self, name: str) -> bytes:
        return self._owner._read_entry(name)

    def __iter__(self) -> Iterator[str]:
        return iter(self._owner.manifest.files)

    def __len__(self) -> int:
        return len(self._owner.manifest.files)

    def __contains__(self, name: object) -> bool:
        if not isinstance(name, str):
            return False
        return name in self._owner.manifest.files

    def keys(self) -> KeysView[str]:  # type: ignore[override]
        return self._owner.manifest.files.keys()

    def __repr__(self) -> str:  # pragma: no cover — diagnostic only
        return f"LazyFileMap(entries={len(self)}, cached={len(self._owner._cache)})"


# ----------------------------------------------------------------------------
# LazyLoadedBundle
# ----------------------------------------------------------------------------


@dataclass
class LazyLoadedBundle(LoadedBundle):
    """Lazy-loading variant of `LoadedBundle`.

    Files are read из the underlying `zipfile.ZipFile` on first access and
    cached в a size-bounded LRU. The owning `BundleZipReader` configures
    the cache cap; default 512 MB per ROADMAP §1C.

    Use as a context manager to guarantee resource cleanup:

        with reader.read_lazy(path) as bundle:
            payload = bundle.files["models/proxy.pickle"]
            meta = bundle.get_json("metadata.json")
        # ZipFile closed, advisory lock released

    Calling `close()` more than once is safe.
    """

    # Inherited from LoadedBundle: manifest, files, source_format, source_path
    # We override `files` with a lazy mapping after init.
    _zf: zipfile.ZipFile | None = None
    _cache: ByteSizeLRU = field(default_factory=ByteSizeLRU)
    _stack: contextlib.ExitStack | None = None
    _strict_integrity: bool = True
    _verify_on_access: bool = True
    _verified_entries: set[str] = field(default_factory=set)
    _closed: bool = False

    def __post_init__(self) -> None:
        # Replace any caller-provided `files` dict with the lazy proxy.
        # (LoadedBundle base class types `files` as `dict[str, bytes]`,
        # but at runtime callers go through the Mapping protocol — so the
        # proxy is a drop-in replacement for everything that goes through
        # `bundle.files[name]` / `name in bundle.files` / `len(...)`.)
        self.files = LazyFileMap(self)  # type: ignore[assignment]

    # -- Lazy read core -----------------------------------------------------

    def _read_entry(self, name: str) -> bytes:
        if self._closed:
            raise ValueError(f"Cannot read from closed LazyLoadedBundle: {self.source_path}")
        if name not in self.manifest.files:
            raise KeyError(name)

        cached = self._cache.get(name)
        if cached is not None:
            return cached

        assert self._zf is not None, "ZipFile handle missing on lazy bundle"

        # Audit Block 1D — finding B2: zip-bomb defense. ZIP central directory
        # publishes uncompressed size; cross-check that это (a) matches manifest
        # and (b) doesn't exceed sane cap before allocating bytes.
        expected_entry = self.manifest.files[name]
        try:
            zinfo = self._zf.getinfo(name)
        except KeyError as exc:
            raise BundleIntegrityError(
                f"Bundle entry declared in manifest missing from ZIP: {name}"
            ) from exc

        if zinfo.file_size != expected_entry.size_bytes:
            raise BundleIntegrityError(
                f"ZIP entry size mismatch для {name}: zip claims "
                f"{zinfo.file_size} bytes, manifest claims "
                f"{expected_entry.size_bytes} bytes (zip-bomb / tampering signal)"
            )
        if zinfo.file_size > MAX_ENTRY_SIZE:
            raise BundleFormatError(
                f"Bundle entry {name} too large: {zinfo.file_size} > "
                f"{MAX_ENTRY_SIZE} bytes (refused for safety)"
            )

        try:
            data = self._zf.read(name)
        except KeyError as exc:
            raise BundleIntegrityError(
                f"Bundle entry declared in manifest missing from ZIP: {name}"
            ) from exc

        # Defense-in-depth: even с central directory check above, real
        # decompressed size could differ если archive crafted maliciously.
        if len(data) != expected_entry.size_bytes:
            raise BundleIntegrityError(
                f"Decompressed size mismatch для {name}: actual "
                f"{len(data)} bytes, manifest claims "
                f"{expected_entry.size_bytes} bytes"
            )

        # Verify per-entry hash on first access (strict mode raises; warn logs)
        if (
            self._verify_on_access
            and name not in self._verified_entries
            and self.manifest.integrity_check != "disabled"
        ):
            expected = self.manifest.files[name]
            actual = compute_file_entry(data)
            if actual.sha256 != expected.sha256:
                msg = (
                    f"Integrity check failed lazily для {name} в {self.source_path}: "
                    f"expected {expected.sha256[:16]}..., got {actual.sha256[:16]}..."
                )
                if self._strict_integrity:
                    raise BundleIntegrityError(msg)
                _log.warning(msg)
            self._verified_entries.add(name)

        self._cache.put(name, data)
        return data

    # -- Convenience --------------------------------------------------------

    def verify_all(self) -> list[str]:
        """Eagerly verify every manifest entry. Returns list of issues
        (empty list = всё OK). Useful for explicit integrity audits.

        В strict mode the first hash mismatch raises; в warn/disabled
        mode all issues are collected.
        """
        if self._closed:
            raise ValueError("Cannot verify_all on closed bundle")
        assert self._zf is not None
        issues: list[str] = []
        zip_names = set(self._zf.namelist()) - {MANIFEST_FILENAME}
        manifest_names = set(self.manifest.files.keys())

        for missing in manifest_names - zip_names:
            issues.append(f"missing:{missing}")
        for extra in zip_names - manifest_names:
            issues.append(f"extra:{extra}")

        if self.manifest.integrity_check != "disabled":
            for name in manifest_names & zip_names:
                # Reuse cached bytes if any; otherwise read but do not cache
                # the full bundle (avoid blowing the cap on verify_all).
                cached = self._cache.get(name)
                data = cached if cached is not None else self._zf.read(name)
                actual = compute_file_entry(data)
                if actual.sha256 != self.manifest.files[name].sha256:
                    issues.append(f"hash:{name}")
                else:
                    self._verified_entries.add(name)

        if issues and self._strict_integrity and self.manifest.integrity_check == "strict":
            raise BundleIntegrityError(
                f"verify_all failed для {self.source_path}: {len(issues)} issues: {issues[:3]}"
            )
        return issues

    def materialise_eager(self) -> LoadedBundle:
        """Read every entry into memory and return a plain `LoadedBundle`.

        Block 1D B3 fix: callers that need the writer rebase path
        (`BundleZipWriter.from_loaded`) must explicitly materialise so the
        memory cost is visible. The returned object is independent of the
        lazy bundle и does not hold the lock / ZipFile.

        Existing cache entries are reused; missing ones read directly from
        the ZIP without polluting the cache.
        """
        if self._closed:
            raise ValueError("Cannot materialise closed bundle")
        assert self._zf is not None
        eager_files: dict[str, bytes] = {}
        for name in self.manifest.files.keys():
            cached = self._cache.get(name)
            if cached is not None:
                eager_files[name] = cached
            else:
                eager_files[name] = self._read_entry(name)
        return LoadedBundle(
            manifest=self.manifest,
            files=eager_files,
            source_format=self.source_format,
            source_path=self.source_path,
        )

    @property
    def cache_total_size(self) -> int:
        return self._cache.total_size

    @property
    def cache_max_bytes(self) -> int:
        return self._cache.max_bytes

    def cache_clear(self) -> None:
        """Drop all cached entries (manifest + lock retained)."""
        self._cache.clear()

    # -- Lifecycle ----------------------------------------------------------

    def close(self) -> None:
        """Close the underlying ZipFile, release the advisory lock, drop
        the cache. Idempotent."""
        if self._closed:
            return
        self._closed = True
        try:
            if self._stack is not None:
                self._stack.close()
        finally:
            self._zf = None
            self._stack = None
            self._cache.clear()

    def __enter__(self) -> LazyLoadedBundle:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001 — match contextmanager API
        self.close()

    def __del__(self) -> None:  # best-effort safety net
        try:
            self.close()
        except Exception:  # noqa: BLE001 — never raise from finalizer
            pass


# ----------------------------------------------------------------------------
# Lazy reader entrypoint
# ----------------------------------------------------------------------------


def open_lazy(
    path: Path,
    *,
    cache_max_bytes: int = DEFAULT_CACHE_BYTES,
    lock_timeout: float = 5.0,
    verify_integrity: bool = True,
    strict_integrity: bool = True,
) -> LazyLoadedBundle:
    """Open a `.aurora` ZIP bundle in streaming mode.

    Manifest is read eagerly (sub-millisecond on real bundles). All other
    entries are deferred to first `bundle.files[name]` access, cached в a
    size-bounded LRU.

    Args:
        path: bundle file path (must be ZIP format; legacy JSON not supported
            here — caller should use `BundleZipReader.read()` for legacy).
        cache_max_bytes: LRU cap; 0 disables caching entirely.
        lock_timeout: seconds to wait for advisory shared lock.
        verify_integrity: per-entry SHA-256 check on first access.
        strict_integrity: raise `BundleIntegrityError` on mismatch
            (otherwise log a warning).

    Returns:
        Open `LazyLoadedBundle`. Caller MUST `close()` it (or use
        `with` block) to release the file handle and advisory lock.

    Raises:
        FileNotFoundError: bundle path missing.
        BundleFormatError: not a ZIP, or manifest absent, or zip-slip name.
        BundleIntegrityError: manifest claims entries that are missing from
            the ZIP (strict mode), or extra entries present (strict mode).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Bundle not found: {path}")

    fmt = detect_format(path)
    if fmt != "zip":
        raise BundleFormatError(
            f"open_lazy requires ZIP format, got {fmt!r} at {path}. "
            f"Use BundleZipReader.read(path) for legacy JSON bundles."
        )

    stack = contextlib.ExitStack()
    try:
        # Acquire shared lock first — held для bundle lifetime
        stack.enter_context(bundle_lock(path, mode="shared", timeout=lock_timeout))
        zf = stack.enter_context(zipfile.ZipFile(path, "r"))

        names = zf.namelist()
        if MANIFEST_FILENAME not in names:
            raise BundleFormatError(f"ZIP bundle {path} missing {MANIFEST_FILENAME}")

        # Audit Block 1D — finding B4: reject duplicate entry names upfront.
        # ZIP spec permits duplicates; zipfile.ZipFile.read()/getinfo() return
        # the LAST entry, so a tampered manifest paired с a "real" manifest
        # would be silently chosen.
        if len(names) != len(set(names)):
            duplicates = [n for n in set(names) if names.count(n) > 1]
            raise BundleFormatError(
                f"Duplicate ZIP entries в {path}: {duplicates[:5]} — refusing"
            )

        # Zip-slip defense — must run upfront because lazy reads later assume
        # entry names are safe (defense-in-depth).
        for name in names:
            if (
                name.startswith("/")
                or ".." in Path(name).parts
                or ":" in name  # Windows drive letter
            ):
                raise BundleFormatError(f"Suspicious ZIP entry name (zip-slip risk): {name!r}")

        manifest_bytes = zf.read(MANIFEST_FILENAME)
        manifest_data = json.loads(manifest_bytes.decode("utf-8"))
        manifest = BundleManifest.model_validate(manifest_data)

        # Manifest-level structural checks (cheap — names only, no payload reads).
        if verify_integrity and manifest.integrity_check != "disabled":
            zip_files = set(names) - {MANIFEST_FILENAME}
            manifest_files = set(manifest.files.keys())
            issues: list[str] = []
            for missing in manifest_files - zip_files:
                issues.append(f"missing:{missing}")
            for extra in zip_files - manifest_files:
                issues.append(f"extra:{extra}")
            if issues:
                msg = (
                    f"Lazy open structural integrity failed для {path}: "
                    f"{len(issues)} issues: {issues[:3]}"
                )
                if manifest.integrity_check == "strict" and strict_integrity:
                    raise BundleIntegrityError(msg)
                _log.warning(msg)

        bundle = LazyLoadedBundle(
            manifest=manifest,
            files={},  # placeholder — overridden by __post_init__
            source_format="zip",
            source_path=path,
            _zf=zf,
            _cache=ByteSizeLRU(max_bytes=cache_max_bytes),
            _stack=stack,
            _strict_integrity=strict_integrity,
            _verify_on_access=verify_integrity,
        )
        return bundle
    except Exception:
        stack.close()
        raise
