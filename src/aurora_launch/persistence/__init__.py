"""Aurora Launch Planner working storage (Phase 0.1).

Provides production-grade working storage for forecast projects:
- SQLite WAL-mode database (projects.db) for metadata + version graph
- Content-addressed blob storage (deduplicated pickle artefacts)
- Migration utilities from existing .aurora ZIP bundles

Architecture (per plan v3.0 §A.4):
- Working storage = fast SQLite + blobs (save <50ms vs ZIP rewrite 30s)
- .aurora ZIP container = export/import/share snapshot format (unchanged)
- BundleZipReader/Writer continue to work for legacy bundles + project export

Layout on disk:
    %LOCALAPPDATA%/Aurora Launch/
    ├── projects.db          (SQLite — index, metadata, version graph)
    ├── blobs/               (content-addressed pickle: sha256-XXX.pickle)
    │   └── sha256-aabb...pickle
    ├── autosave/            (Phase 0.2: incremental delta state)
    │   └── project-{uuid}.autosave.json
    └── exports/             (cached .aurora ZIP snapshots, on-demand)
        └── {uuid}.aurora

Multiple customer-facing projects live in one customer's projects.db.
Blobs are deduplicated across projects (e.g., shared proxy posterior).
"""

from aurora_launch.persistence.blob_store import (
    BlobInfo,
    BlobStore,
    BlobStoreError,
)
from aurora_launch.persistence.project_db import (
    LoadedVersion,
    ProjectDB,
    ProjectDBError,
    ProjectDetail,
    ProjectSummary,
    VersionDiff,
    VersionSummary,
)

__all__ = [
    "BlobInfo",
    "BlobStore",
    "BlobStoreError",
    "LoadedVersion",
    "ProjectDB",
    "ProjectDBError",
    "ProjectDetail",
    "ProjectSummary",
    "VersionDiff",
    "VersionSummary",
]
