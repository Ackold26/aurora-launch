"""Aurora bundle manifest schema (Block 1A).

Per ADR-002 §"manifest.json schema (SSoT)" — manifest.json is the entry-point
for any `.aurora` ZIP container. Read first on open, controls integrity check
behavior and per-file schema versioning.

Schema (per ADR-002):
- manifest_version: format-of-manifest version (1.0)
- schema_version: bundle-level schema version (3.0)
- aurora_app: which Suite app produced this bundle ("Aurora Launch")
- aurora_app_version: producing app semver
- min_app_version: minimum app version that can read this bundle
- created_at / last_modified: ISO 8601 timestamps
- project_id: UUID v4 stable for entire lifetime of bundle
- revision: monotonic integer, +1 on each save (Block 1A optimistic concurrency)
- files: dict[zip_entry_path, FileEntry] — per-file integrity + schema version
- integrity_check: "strict" | "warn" | "disabled"
- compression: "store" | "deflate"

Hash chain (Block 1A composite):
    bundle_hash = SHA256(
        manifest_canonical_bytes ||
        sorted_per_file_hashes ||
        aurora_app_version
    )
This is bundle-level integrity verifier — the reproducibility_token in
generator outputs. Independent inputs ensure R8 closure (per audit B-Audit-2).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Literal

import rfc8785
from pydantic import BaseModel, ConfigDict, Field

IntegrityMode = Literal["strict", "warn", "disabled"]
CompressionMode = Literal["store", "deflate"]


class BundleFileEntry(BaseModel):
    """Per-file metadata in manifest.files.

    sha256 — hex digest of raw file bytes (used as ZIP entry content)
    size_bytes — uncompressed size (deflate-aware: still original size)
    schema_version — independent evolution per ADR-002 ("recipient_anchors v1
    can advance to v2 without bumping global schema_version").
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    schema_version: str | None = None


class BundleManifest(BaseModel):
    """Bundle manifest — SSoT for ZIP container, per ADR-002.

    All fields immutable post-construction (frozen). New revision = new manifest
    instance. `extra="forbid"` catches typos на write side; reader handles
    legacy bundles via SchemaRegistry migration before constructing manifest.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    manifest_version: str = "1.0"
    schema_version: str = "3.0"
    aurora_app: str = "Aurora Launch"
    aurora_app_version: str
    min_app_version: str
    created_at: str  # ISO 8601 UTC, e.g. "2026-05-08T14:30:00Z"
    last_modified: str
    project_id: str  # UUID v4
    revision: int = Field(ge=0, default=0)
    files: dict[str, BundleFileEntry] = Field(default_factory=dict)
    integrity_check: IntegrityMode = "strict"
    compression: CompressionMode = "store"

    # Aurora Launch–specific extension hooks (Phase B+)
    aurora_launch_schema_version: str | None = "1.0"
    aurora_launch_migration_history: list[dict[str, str]] = Field(default_factory=list)

    def to_canonical_bytes(self) -> bytes:
        """JCS RFC 8785 canonical serialization for cross-version hash stability.

        Per memory feedback_jcs_canonical_hash.md — Pydantic model_dump_json
        is fragile for cryptographic hash payload. JCS gives bit-stable
        cross-version + cross-language hashes.
        """
        # Use mode='json' to get serializable form; rfc8785 canonicalizes order
        return rfc8785.dumps(self.model_dump(mode="json"))

    def manifest_sha256(self) -> str:
        """Hash of the manifest itself (does not include file contents — those
        are individually hashed in `files` map)."""
        return hashlib.sha256(self.to_canonical_bytes()).hexdigest()

    def composite_bundle_hash(self) -> str:
        """Bundle-level integrity hash for R8 closure (per audit B-Audit-2).

        Independent inputs:
        - manifest_sha256 (catches manifest tampering)
        - sorted(per_file_hashes) (catches file content tampering)
        - aurora_app_version (binds to specific Aurora Launch release)

        Length-prefix encoding prevents '|' separator collision (per audit
        memory feedback — composite signing must avoid separator ambiguity).
        """
        manifest_h = self.manifest_sha256()

        # Sort by file path for deterministic ordering
        file_hashes = sorted(entry.sha256 for entry in self.files.values())
        files_concat = "".join(file_hashes)
        files_hash = hashlib.sha256(files_concat.encode("ascii")).hexdigest()

        # Length-prefix encoding: 4-byte big-endian length + bytes per field
        parts = [
            manifest_h.encode("ascii"),
            files_hash.encode("ascii"),
            self.aurora_app_version.encode("utf-8"),
        ]
        buf = b""
        for p in parts:
            buf += len(p).to_bytes(4, "big") + p

        return hashlib.sha256(buf).hexdigest()

    def with_revision_bump(self, **field_updates: object) -> BundleManifest:
        """Return new manifest instance with revision+1 + last_modified=now.

        Frozen-pattern: BundleManifest is immutable; this is the canonical
        way to advance state. Optional field_updates merged in (e.g., updated
        files map after writing new entries).
        """
        data = self.model_dump()
        data.update(field_updates)
        data["revision"] = self.revision + 1
        data["last_modified"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        return BundleManifest.model_validate(data)


def make_initial_manifest(
    *,
    aurora_app_version: str,
    min_app_version: str,
    project_id: str,
    integrity_check: IntegrityMode = "strict",
    compression: CompressionMode = "store",
) -> BundleManifest:
    """Construct a fresh manifest for a new bundle. Used by BundleZipWriter
    on initial create; subsequent saves use `with_revision_bump()`.
    """
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return BundleManifest(
        aurora_app_version=aurora_app_version,
        min_app_version=min_app_version,
        created_at=now,
        last_modified=now,
        project_id=project_id,
        revision=0,
        files={},
        integrity_check=integrity_check,
        compression=compression,
    )


def compute_file_entry(content: bytes, schema_version: str | None = None) -> BundleFileEntry:
    """Compute BundleFileEntry from raw file content."""
    return BundleFileEntry(
        sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
        schema_version=schema_version,
    )
