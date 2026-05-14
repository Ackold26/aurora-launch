"""Aurora `.aurora` bundle ZIP container — writer / reader / format detection.

Block 1A — replaces `.aurora.json` transitional format with real ZIP per
ADR-002 §"Decision". Backwards-compatible reader: handles both legacy
JSON bundles and canonical ZIP bundles transparently.

Architecture:
- Writer: BundleZipWriter — atomic ZIP creation with manifest + files,
  optimistic concurrency via revision counter, advisory file lock
- Reader: BundleZipReader — auto-detects format (ZIP magic vs JSON `{`),
  reads manifest first, returns unified `LoadedBundle` dict-like view
- Format detection: detect_format(path) — peek at magic bytes
- Hash chain: composite bundle hash via BundleManifest.composite_bundle_hash()

Reuses:
- atomic_write_bundle (engines/bundle_persistence.py) — atomic write +
  rolling backup rotation (.bak.1 to .bak.4)
- bundle_lock (engines/bundle_lock.py) — cross-platform advisory locking
- BundleManifest (engines/bundle_manifest.py) — manifest schema + hashes
- LaunchSchemaRegistry (engines/schema_registry_launch.py) — version migration

Per ADR-002 §"Files to create" and §"Save (atomic)" / §"Open" protocols.
"""

from __future__ import annotations

import io
import json
import logging
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from aurora_launch.engines.bundle_lock import bundle_lock
from aurora_launch.engines.bundle_manifest import (
    BundleManifest,
    CompressionMode,
    IntegrityMode,
    compute_file_entry,
    make_initial_manifest,
)
from aurora_launch.engines.bundle_persistence import atomic_write_bundle
from aurora_launch.engines.schema_registry_launch import (
    LaunchSchemaRegistry,
    build_default_launch_registry,
)

_log = logging.getLogger(__name__)

MANIFEST_FILENAME = "manifest.json"
DEFAULT_MIN_APP_VERSION = "0.1.0"

BundleFormat = Literal["zip", "json", "unknown"]


class BundleFormatError(ValueError):
    """Raised when bundle format cannot be detected or is invalid."""


class BundleIntegrityError(RuntimeError):
    """Raised when manifest hash verification fails (file tampering detected)."""


class BundleConflictError(RuntimeError):
    """Raised when optimistic concurrency check fails — bundle on disk is
    newer than the revision the writer was based on (lost-update prevention).
    """

    def __init__(self, expected_revision: int, current_revision: int) -> None:
        super().__init__(
            f"Bundle revision conflict: expected={expected_revision}, "
            f"current={current_revision}. Reload bundle and reapply changes."
        )
        self.expected_revision = expected_revision
        self.current_revision = current_revision


# ----------------------------------------------------------------------------
# Format detection
# ----------------------------------------------------------------------------


def detect_format(path: Path) -> BundleFormat:
    """Detect bundle format by peeking at magic bytes (ADR-002 §"legacy
    detection").

    Returns:
        "zip"     — ZIP magic (PK\\x03\\x04 or PK\\x05\\x06)
        "json"    — first non-whitespace byte is `{` (JSON object)
        "unknown" — neither — caller decides what to do (corrupted, empty, etc.)
    """
    if not path.exists() or path.stat().st_size == 0:
        return "unknown"

    with path.open("rb") as f:
        head = f.read(64)

    if head[:2] == b"PK":  # ZIP local file header (PK\x03\x04) or end of central dir (PK\x05\x06)
        return "zip"

    # Skip leading whitespace
    stripped = head.lstrip()
    if stripped.startswith(b"{"):
        return "json"

    return "unknown"


# ----------------------------------------------------------------------------
# Loaded bundle — read-side container
# ----------------------------------------------------------------------------


@dataclass
class LoadedBundle:
    """Read-side container for an opened bundle.

    Provides:
    - manifest: BundleManifest (always present for ZIP; synthesized for JSON legacy)
    - files: dict[entry_path, raw_bytes] — eager-loaded for now (Block 1A);
        Block 1C will add lazy-streaming reader
    - source_format: original on-disk format ("zip" | "json")
    - source_path: Path to bundle on disk
    """

    manifest: BundleManifest
    files: dict[str, bytes]
    source_format: BundleFormat
    source_path: Path

    def get_json(self, entry: str) -> dict:
        """Decode a JSON file entry from the bundle."""
        return json.loads(self.files[entry].decode("utf-8"))

    def has(self, entry: str) -> bool:
        return entry in self.files

    def list_entries(self) -> list[str]:
        return sorted(self.files.keys())

    def composite_bundle_hash(self) -> str:
        """Convenience: re-derive composite hash from this loaded manifest."""
        return self.manifest.composite_bundle_hash()


# ----------------------------------------------------------------------------
# Writer
# ----------------------------------------------------------------------------


@dataclass
class BundleZipWriter:
    """Composer for `.aurora` ZIP bundles.

    Usage:
        writer = BundleZipWriter(aurora_app_version="0.1.0")
        writer.add_file("metadata.json", json_bytes, schema_version="1.0")
        writer.add_file("models/proxy_model.pickle", pickle_bytes)
        writer.write(path)

    Rebase pattern (optimistic concurrency for updates):
        loaded = BundleZipReader().read(path)
        writer = BundleZipWriter.from_loaded(loaded)
        writer.add_file(...)  # stage updates
        writer.write(path, expected_revision=loaded.manifest.revision)

    Atomic write + rolling backups via atomic_write_bundle. Lock acquired
    around the read-modify-write window.
    """

    aurora_app_version: str
    min_app_version: str = DEFAULT_MIN_APP_VERSION
    project_id: str | None = None
    integrity_check: IntegrityMode = "strict"
    compression: CompressionMode = "store"
    base_manifest: BundleManifest | None = None  # for revision-bump path
    _files: dict[str, tuple[bytes, str | None]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._files is None:
            self._files = {}
        if self.project_id is None:
            self.project_id = str(uuid.uuid4())

    @classmethod
    def from_loaded(cls, loaded: LoadedBundle) -> BundleZipWriter:
        """Construct writer pre-populated with files from a loaded bundle.

        Subsequent add_file() calls override entries with same name. write()
        will bump revision and re-hash. project_id preserved from manifest.

        Audit Block 1D — finding B3: refuses `LazyLoadedBundle` to prevent
        silent full materialisation через the Mapping ABC's default
        `items()` (which would invoke `__getitem__` per entry, thrashing
        the LRU cache when bundle size exceeds cap and reading some
        entries twice). Caller must explicitly materialise via
        `LazyLoadedBundle.materialise_eager()` so the cost is visible.
        """
        # Local import to avoid circular dep (bundle_streaming imports here).
        from aurora_launch.engines.bundle_streaming import LazyLoadedBundle

        if isinstance(loaded, LazyLoadedBundle):
            raise TypeError(
                "BundleZipWriter.from_loaded does not accept LazyLoadedBundle "
                "directly — it would silently materialise all entries и could "
                "re-read some из ZIP if cache cap < bundle size. Either: "
                "(a) call `loaded.materialise_eager()` to get a plain "
                "LoadedBundle (explicit materialisation cost), or "
                "(b) re-open via `BundleZipReader().read(path)` (eager mode)."
            )

        writer = cls(
            aurora_app_version=loaded.manifest.aurora_app_version,
            min_app_version=loaded.manifest.min_app_version,
            project_id=loaded.manifest.project_id,
            integrity_check=loaded.manifest.integrity_check,
            compression=loaded.manifest.compression,
            base_manifest=loaded.manifest,
        )
        for name, content in loaded.files.items():
            # Skip the old manifest — writer composes a fresh manifest with
            # bumped revision on each write. Otherwise duplicate ZIP entry
            # `manifest.json` would overwrite the new one (silent rev rollback).
            if name == MANIFEST_FILENAME:
                continue
            schema = (
                loaded.manifest.files[name].schema_version
                if name in loaded.manifest.files
                else None
            )
            writer._files[name] = (content, schema)
        return writer

    def add_file(
        self,
        entry_path: str,
        content: bytes,
        *,
        schema_version: str | None = None,
    ) -> None:
        """Stage a file for inclusion в bundle. Overrides if entry already exists."""
        if entry_path == MANIFEST_FILENAME:
            raise ValueError(
                f"Cannot add {MANIFEST_FILENAME} as a file — manifest is "
                f"composed automatically by writer."
            )
        if not isinstance(content, (bytes, bytearray)):
            raise TypeError(f"File content must be bytes, got {type(content).__name__}")
        self._files[entry_path] = (bytes(content), schema_version)

    def remove_file(self, entry_path: str) -> bool:
        """Remove a staged entry. Returns True if was present."""
        return self._files.pop(entry_path, None) is not None

    def list_staged(self) -> list[str]:
        return sorted(self._files.keys())

    def _build_manifest(self) -> BundleManifest:
        """Compose final BundleManifest from staged files."""
        file_entries = {
            name: compute_file_entry(content, schema_version)
            for name, (content, schema_version) in self._files.items()
        }

        if self.base_manifest is not None:
            return self.base_manifest.with_revision_bump(files=file_entries)

        manifest = make_initial_manifest(
            aurora_app_version=self.aurora_app_version,
            min_app_version=self.min_app_version,
            project_id=self.project_id or str(uuid.uuid4()),
            integrity_check=self.integrity_check,
            compression=self.compression,
        )
        # Inject file entries (frozen → use validate)
        return manifest.model_copy(update={"files": file_entries})

    def to_zip_bytes(self) -> tuple[bytes, BundleManifest]:
        """Compose bundle into in-memory ZIP bytes. Returns (zip_bytes, manifest).

        Manifest is written as the FIRST entry (per ADR-002 §"Open" — read
        manifest first). All files use store-only compression unless manifest
        compression="deflate".
        """
        manifest = self._build_manifest()

        compress_type = (
            zipfile.ZIP_DEFLATED if manifest.compression == "deflate" else zipfile.ZIP_STORED
        )

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compress_type) as zf:
            # Manifest first — readers can early-exit on min_app_version mismatch
            manifest_bytes = manifest.to_canonical_bytes()
            zf.writestr(MANIFEST_FILENAME, manifest_bytes)

            for name in sorted(self._files.keys()):
                content, _schema = self._files[name]
                zf.writestr(name, content)

        return buf.getvalue(), manifest

    def write(
        self,
        path: Path,
        *,
        expected_revision: int | None = None,
        backup_count: int = 4,
        lock_timeout: float = 5.0,
    ) -> BundleManifest:
        """Write bundle to disk atomically with backup rotation and locking.

        Args:
            path: destination `.aurora` file path
            expected_revision: if provided, optimistic concurrency check —
                if file on disk has revision != expected_revision, raises
                BundleConflictError. Pass `loaded.manifest.revision` from
                a prior read to detect lost updates.
            backup_count: rolling backup chain depth (.bak.1 ... .bak.N)
            lock_timeout: seconds to wait for advisory lock

        Returns:
            The BundleManifest that was written (with revision bumped).

        Raises:
            BundleConflictError: optimistic concurrency check failed
            BundleLockError: another process holds bundle lock
        """
        path = Path(path)

        with bundle_lock(path, mode="exclusive", timeout=lock_timeout):
            # Optimistic concurrency check (only meaningful if file exists)
            if expected_revision is not None and path.exists():
                current_format = detect_format(path)
                if current_format == "zip":
                    current_manifest = _read_manifest_from_zip(path)
                    if current_manifest.revision != expected_revision:
                        raise BundleConflictError(expected_revision, current_manifest.revision)
                # JSON legacy: no revision counter — skip check (migration path)

            zip_bytes, manifest = self.to_zip_bytes()
            atomic_write_bundle(path, zip_bytes, backup_count=backup_count)
            _log.info(
                "Bundle written: %s (revision=%d, files=%d, hash=%s...)",
                path,
                manifest.revision,
                len(manifest.files),
                manifest.composite_bundle_hash()[:12],
            )
            return manifest


# ----------------------------------------------------------------------------
# Reader
# ----------------------------------------------------------------------------


def _read_manifest_from_zip(path: Path) -> BundleManifest:
    """Read manifest.json from a ZIP without loading other files."""
    with zipfile.ZipFile(path, "r") as zf:
        if MANIFEST_FILENAME not in zf.namelist():
            raise BundleFormatError(f"Bundle {path} missing required {MANIFEST_FILENAME}")
        manifest_bytes = zf.read(MANIFEST_FILENAME)
    data = json.loads(manifest_bytes.decode("utf-8"))
    return BundleManifest.model_validate(data)


@dataclass
class BundleZipReader:
    """Reader for `.aurora` bundles. Auto-detects ZIP vs legacy JSON.

    Default `read()` is eager (Block 1A) — full bundle into RAM. For 50MB+
    bundles call `read_lazy()` (Block 1C) to defer per-entry reads behind
    a size-bounded LRU cache; the lazy bundle holds the ZipFile + advisory
    lock for its lifetime and must be closed (or used as context manager).
    """

    schema_registry: LaunchSchemaRegistry | None = None
    lock_timeout: float = 5.0
    verify_integrity: bool = True
    strict_integrity: bool = True
    cache_max_bytes: int | None = None  # None → bundle_streaming.DEFAULT_CACHE_BYTES

    def __post_init__(self) -> None:
        if self.schema_registry is None:
            self.schema_registry = build_default_launch_registry()

    def read_lazy(self, path: Path):
        """Open the bundle in streaming mode; returns a `LazyLoadedBundle`.

        Block 1C entrypoint. Reads `manifest.json` upfront, defers payload
        entries to first access (cached в size-bounded LRU). Caller MUST
        close the returned bundle (or use `with`).

        Falls back to `read()` (eager) for legacy `.aurora.json` bundles —
        single-file blobs где lazy не имеет смысла. The returned object in
        that case is a plain `LoadedBundle`, not LazyLoadedBundle.
        """
        # Imported here to avoid a circular import (bundle_streaming imports
        # from bundle_container).
        from aurora_launch.engines.bundle_streaming import (
            DEFAULT_CACHE_BYTES,
            open_lazy,
        )

        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Bundle not found: {path}")
        fmt = detect_format(path)
        if fmt == "json":
            return self.read(path)
        cap = self.cache_max_bytes if self.cache_max_bytes is not None else DEFAULT_CACHE_BYTES
        return open_lazy(
            path,
            cache_max_bytes=cap,
            lock_timeout=self.lock_timeout,
            verify_integrity=self.verify_integrity,
            strict_integrity=self.strict_integrity,
        )

    def read(self, path: Path) -> LoadedBundle:
        """Open and load a bundle. Cross-format dispatch.

        Args:
            path: bundle file path (`.aurora` ZIP or legacy `.aurora.json`)

        Returns:
            LoadedBundle with manifest, files, source format

        Raises:
            BundleFormatError: format unrecognized or corrupted
            BundleIntegrityError: hash verification failed (strict mode)
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Bundle not found: {path}")

        fmt = detect_format(path)

        # Acquire shared lock for read window
        # (POSIX shared; Windows always exclusive — see bundle_lock.py)
        with bundle_lock(path, mode="shared", timeout=self.lock_timeout):
            if fmt == "zip":
                return self._read_zip(path)
            if fmt == "json":
                return self._read_json_legacy(path)
            raise BundleFormatError(
                f"Unrecognized bundle format at {path}. Expected ZIP (PK magic) "
                f"or JSON (starts with '{{'). Got first bytes: "
                f"{path.read_bytes()[:8]!r}"
            )

    def _read_zip(self, path: Path) -> LoadedBundle:
        files: dict[str, bytes] = {}
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
            if MANIFEST_FILENAME not in names:
                raise BundleFormatError(f"ZIP bundle {path} missing {MANIFEST_FILENAME}")

            # Audit Block 1D — finding B4: reject duplicate entry names. ZIP
            # spec permits duplicates and zipfile.ZipFile.read() returns the
            # last entry, so an attacker could ship a tampered manifest plus
            # a "real" manifest и bypass set-based integrity checks.
            if len(names) != len(set(names)):
                duplicates = [n for n in set(names) if names.count(n) > 1]
                raise BundleFormatError(
                    f"Duplicate ZIP entries в {path}: {duplicates[:5]} — refusing"
                )

            for name in names:
                # Defense-in-depth against zip-slip (ADR-002 §"Edge cases").
                # ZIP entry names must NOT contain absolute paths or `..`.
                if (
                    name.startswith("/")
                    or ".." in Path(name).parts
                    or ":" in name  # Windows drive letter
                ):
                    raise BundleFormatError(f"Suspicious ZIP entry name (zip-slip risk): {name!r}")
                files[name] = zf.read(name)

        manifest_data = json.loads(files[MANIFEST_FILENAME].decode("utf-8"))
        manifest = BundleManifest.model_validate(manifest_data)

        # Integrity check per manifest.integrity_check setting
        if self.verify_integrity and manifest.integrity_check != "disabled":
            issues = self._verify_integrity(manifest, files)
            if issues:
                msg = f"Integrity check failed for {path}: {len(issues)} mismatches: {issues[:3]}"
                if manifest.integrity_check == "strict":
                    raise BundleIntegrityError(msg)
                _log.warning(msg)

        return LoadedBundle(
            manifest=manifest,
            files=files,
            source_format="zip",
            source_path=path,
        )

    @staticmethod
    def _verify_integrity(manifest: BundleManifest, files: dict[str, bytes]) -> list[str]:
        """Verify per-file SHA-256 hashes match manifest claims.

        Returns list of mismatched file names (empty if all OK).
        Also catches missing files claimed in manifest, and EXTRA files
        present in ZIP but not in manifest (per Phase A audit C3 fix).
        """
        issues: list[str] = []
        manifest_files = set(manifest.files.keys())
        zip_files = set(files.keys()) - {MANIFEST_FILENAME}

        # Missing in ZIP but claimed in manifest
        for name in manifest_files - zip_files:
            issues.append(f"missing:{name}")

        # Extra in ZIP not declared in manifest
        for name in zip_files - manifest_files:
            issues.append(f"extra:{name}")

        # Hash mismatches на пересечении
        for name in manifest_files & zip_files:
            entry = manifest.files[name]
            actual = compute_file_entry(files[name])
            if actual.sha256 != entry.sha256:
                issues.append(f"hash:{name}")

        return issues

    def _read_json_legacy(self, path: Path) -> LoadedBundle:
        """Read legacy `.aurora.json` bundle and synthesize a manifest.

        Legacy format (v0.1.0-b05) stores everything in a single JSON file
        with `manifest_sha256` + `data_artifacts_hash` + `reproducibility_token`
        fields. We synthesize a BundleManifest so callers can use uniform API.

        For backwards-compat reads, file content is the raw JSON bytes,
        registered as entry `legacy_bundle.json`. project_id is derived from
        manifest_sha256 (deterministic) if legacy bundle не содержит explicit ID.
        """
        raw_bytes = path.read_bytes()
        legacy = json.loads(raw_bytes.decode("utf-8"))

        # Synthesize manifest. Legacy bundles do not have revision counter —
        # we report revision=0 (any subsequent write will bump to 1).
        aurora_app_version = legacy.get("aurora_launch_version", "unknown")
        manifest_sha = legacy.get("manifest_sha256", "")

        # Stable project_id from manifest_sha256 if explicit not present
        # (UUID v5 from a fixed namespace + manifest_sha keeps это deterministic
        #  for same legacy bundle)
        synth_project_id = legacy.get("project_id") or str(
            uuid.uuid5(uuid.NAMESPACE_OID, manifest_sha or path.name)
        )

        manifest = BundleManifest(
            aurora_app_version=aurora_app_version,
            min_app_version=DEFAULT_MIN_APP_VERSION,
            created_at=legacy.get("created_at", "1970-01-01T00:00:00Z"),
            last_modified=legacy.get("last_modified", "1970-01-01T00:00:00Z"),
            project_id=synth_project_id,
            revision=0,
            files={"legacy_bundle.json": compute_file_entry(raw_bytes, schema_version="legacy")},
            integrity_check="disabled",  # legacy: no per-file hashes available
            compression="store",
            aurora_launch_schema_version=str(legacy.get("schema_version", "3.0")),
        )

        return LoadedBundle(
            manifest=manifest,
            files={"legacy_bundle.json": raw_bytes},
            source_format="json",
            source_path=path,
        )
