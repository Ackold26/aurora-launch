-- Aurora Launch Planner schema v4: Telemetry redaction tier (Phase 2.D.2 HE-6)
--
-- NOTE: The `telemetry_events` table lives in the Rust-managed SQLite
-- (aurora_launch.sqlite in AppData), NOT in the Python ProjectDB.  The Python
-- DB (projects.db) uses _kv_store for customer settings, including the
-- redaction tier key 'settings.telemetry.redaction_tier'.
--
-- This migration:
--   1. Seeds the default redaction_tier in _kv_store so kv_get always returns
--      a well-typed dict (not None) for the redaction settings key.
--   2. The Rust-side migration (state.rs init_local_storage) handles the
--      ALTER TABLE telemetry_events ADD COLUMN statements idempotently.
--
-- Backwards compat: INSERT OR IGNORE → existing kv rows are not overwritten.
-- Existing customers who never set a tier will default to 'basic'.

INSERT OR IGNORE INTO _kv_store (key, value_json, updated_at)
VALUES (
    'settings.telemetry.redaction_tier',
    '{"tier": "basic"}',
    strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
);

INSERT OR REPLACE INTO schema_version (version, applied_at)
VALUES (4, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
