-- Aurora Launch Planner schema v2: GC metadata table
--
-- Tracks last time gc_orphan_blobs() ran + cumulative orphans collected.
-- Used by ProjectDB to determine whether startup-time GC is needed
-- (skip if last_gc_ran_at within 7 days).
--
-- Single-row pattern: id=1 is the only row; UPDATE target.

CREATE TABLE IF NOT EXISTS gc_metadata (
    id INTEGER PRIMARY KEY,
    last_gc_ran_at TEXT,                        -- ISO 8601 UTC | NULL = never ran
    orphans_collected_total INTEGER NOT NULL DEFAULT 0
);

INSERT OR IGNORE INTO gc_metadata (id, last_gc_ran_at, orphans_collected_total)
VALUES (1, NULL, 0);

INSERT OR REPLACE INTO schema_version (version, applied_at)
VALUES (2, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
