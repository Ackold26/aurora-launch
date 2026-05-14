-- Aurora Launch Planner working storage schema v1
--
-- One file per customer machine. Multiple forecast projects per customer.
-- Versions hold content-addressed blob references — same pickle stored once
-- даже if referenced by N versions (proxy posterior reused).
--
-- WAL journal mode set at connection time (PRAGMA journal_mode=WAL) to
-- support single-writer + concurrent readers без blocking the wizard UI.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    project_uuid TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,                              -- ISO 8601 UTC
    last_modified TEXT NOT NULL,
    aurora_app_version TEXT NOT NULL,
    aurora_launch_schema_version TEXT NOT NULL DEFAULT '1.0',
    current_version_id INTEGER,                            -- FK to versions(version_id), HEAD pointer
    granularity TEXT NOT NULL DEFAULT 'monthly',           -- 'monthly' | 'weekly' (D-06)
    metadata_json TEXT NOT NULL DEFAULT '{}'               -- proxy info, anchors, settings
);

CREATE INDEX IF NOT EXISTS idx_projects_last_modified ON projects(last_modified DESC);

CREATE TABLE IF NOT EXISTS versions (
    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid TEXT NOT NULL,
    parent_version_id INTEGER,                             -- linear history; null for v1
    revision INTEGER NOT NULL,                             -- per-project monotonic counter
    created_at TEXT NOT NULL,
    label TEXT,                                            -- "v1 initial" | "after posterior month 1"
    decision_note TEXT,                                    -- "Why this version exists"
    recipient_data_hash TEXT,                              -- SHA-256 of recipient training data
    composite_bundle_hash TEXT,                            -- full composite hash (compat with BundleManifest)
    metadata_json TEXT NOT NULL DEFAULT '{}',              -- extra per-version state
    UNIQUE (project_uuid, revision),
    FOREIGN KEY (project_uuid) REFERENCES projects(project_uuid) ON DELETE CASCADE,
    FOREIGN KEY (parent_version_id) REFERENCES versions(version_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_versions_project ON versions(project_uuid);
CREATE INDEX IF NOT EXISTS idx_versions_parent ON versions(parent_version_id);
CREATE INDEX IF NOT EXISTS idx_versions_created ON versions(created_at DESC);

CREATE TABLE IF NOT EXISTS version_files (
    version_id INTEGER NOT NULL,
    file_path TEXT NOT NULL,                               -- e.g., 'models/proxy_posterior.pickle'
    blob_sha256 TEXT NOT NULL,                             -- reference to blobs(sha256)
    schema_version TEXT,                                   -- per-file schema (BundleFileEntry compat)
    PRIMARY KEY (version_id, file_path),
    FOREIGN KEY (version_id) REFERENCES versions(version_id) ON DELETE CASCADE,
    FOREIGN KEY (blob_sha256) REFERENCES blobs(sha256)
);

CREATE INDEX IF NOT EXISTS idx_version_files_blob ON version_files(blob_sha256);

CREATE TABLE IF NOT EXISTS blobs (
    sha256 TEXT PRIMARY KEY,                               -- content hash (lowercase hex, 64 chars)
    size_bytes INTEGER NOT NULL,
    ref_count INTEGER NOT NULL DEFAULT 0                   -- 0 = orphan (GC candidate)
        CHECK (ref_count >= 0),                            -- audit P0-03 fix: prevent underflow от double-delete
    created_at TEXT NOT NULL,
    storage_path TEXT NOT NULL                             -- relative path: 'blobs/sha256-aabb.pickle'
);

CREATE INDEX IF NOT EXISTS idx_blobs_ref_count ON blobs(ref_count);

-- Initial schema version
INSERT OR IGNORE INTO schema_version (version, applied_at)
VALUES (1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
