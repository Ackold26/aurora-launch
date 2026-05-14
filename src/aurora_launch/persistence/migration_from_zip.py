"""Migrate `.aurora` ZIP bundles into ProjectDB working storage (Phase 0.1).

Reads existing .aurora bundles via BundleZipReader (or legacy JSON), creates
a ProjectDB project, stores the bundle's files as content-addressed blobs
under a single initial version (revision=1).

Use cases:
- One-time migration when customer first opens Aurora Launch after upgrade
- Importing a shared bundle from regulator/external party
- Restoring from .aurora.bak.N rolling backup

Reverse direction (project_db → .aurora ZIP for sharing) lives in
`zip_export.py` (Phase Π.3.1).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from aurora_launch.engines.bundle_container import (
    BundleZipReader,
    LoadedBundle,
)
from aurora_launch.persistence.project_db import ProjectDB

_log = logging.getLogger(__name__)


class MigrationError(RuntimeError):
    """Raised for migration failures."""


def import_aurora_bundle(
    bundle_path: Path,
    project_db: ProjectDB,
    *,
    project_name: str | None = None,
    granularity: str = "monthly",
    extra_metadata: dict[str, Any] | None = None,
) -> str:
    """Import a `.aurora` bundle (ZIP or legacy JSON) into ProjectDB.

    Creates a new project_uuid и saves an initial version with all bundle
    files. Files are deduplicated into the blob store (content-addressed).

    Args:
        bundle_path: path to `.aurora` (ZIP) or legacy `.aurora.json`
        project_db: target ProjectDB
        project_name: human-friendly name; defaults to bundle filename stem
        granularity: 'monthly' (default) or 'weekly' (D-06)
        extra_metadata: additional project metadata к merge

    Returns:
        New project_uuid

    Raises:
        MigrationError: bundle unreadable or migration failed
    """
    bundle_path = Path(bundle_path)
    if not bundle_path.exists():
        raise MigrationError(f"Bundle not found: {bundle_path}")

    try:
        reader = BundleZipReader(verify_integrity=True, strict_integrity=False)
        loaded: LoadedBundle = reader.read(bundle_path)
    except Exception as exc:
        raise MigrationError(f"Cannot read bundle {bundle_path}: {exc}") from exc

    manifest = loaded.manifest
    if project_name is None:
        project_name = bundle_path.stem

    metadata: dict[str, Any] = {
        "imported_from": str(bundle_path),
        "source_format": loaded.source_format,
        "source_project_id": manifest.project_id,
        "source_revision": manifest.revision,
        "source_aurora_app_version": manifest.aurora_app_version,
        "source_aurora_launch_schema_version": manifest.aurora_launch_schema_version,
    }
    if extra_metadata:
        metadata.update(extra_metadata)

    project_uuid = project_db.create_project(
        name=project_name,
        aurora_app_version=manifest.aurora_app_version,
        granularity=granularity,
        metadata=metadata,
    )

    # Reuse source project_id где возможно для traceability — но project_uuid
    # in new DB is generated fresh by create_project to avoid collision across
    # multiple imports of the same bundle.

    schema_versions = {
        fname: entry.schema_version for fname, entry in manifest.files.items()
    }

    composite = manifest.composite_bundle_hash() if manifest.files else None

    version_id = project_db.save_version(
        project_uuid,
        files=loaded.files,
        label=f"Imported from {bundle_path.name}",
        decision_note=(
            f"Initial import from {loaded.source_format} bundle "
            f"(source revision {manifest.revision})"
        ),
        composite_bundle_hash=composite,
        schema_versions=schema_versions,
        metadata={
            "import_timestamp": json.loads(loaded.files.get("manifest.json", b"{}") or b"{}"),
        }
        if False  # keep metadata pure для now
        else {},
    )

    _log.info(
        "Imported bundle %s → project %s (version_id=%d, %d files)",
        bundle_path,
        project_uuid,
        version_id,
        len(loaded.files),
    )
    return project_uuid


def import_aurora_bundles_batch(
    bundle_paths: list[Path],
    project_db: ProjectDB,
    *,
    granularity: str = "monthly",
) -> list[str]:
    """Import several bundles in sequence. Returns list of created project_uuids.

    Stops on first failure (no partial rollback across bundles — each import
    is its own transaction). Caller can inspect ProjectDB to see successes.
    """
    uuids: list[str] = []
    for path in bundle_paths:
        uuids.append(import_aurora_bundle(path, project_db, granularity=granularity))
    return uuids
