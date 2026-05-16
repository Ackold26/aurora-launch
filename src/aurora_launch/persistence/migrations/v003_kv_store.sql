-- Aurora Launch Planner schema v3: KV store
--
-- Persistent key-value хранилище для:
--   - Auto-refresh consent (key 'auto_refresh.consent') — §3.5
--   - Wizard session draft (key 'wizard.session.draft') — §1.C BTA-2
--   - Discoverability tips dismissals (key 'tip.<name>') — UX-3
--   - Telemetry privacy tier (key 'telemetry.privacy_tier') — Phase 2.D.2
--   - Future per-customer settings без отдельных таблиц
--
-- Контракт: value хранится как JSON-сериализованный dict. `kv_get` возвращает
-- dict | None, `kv_set` принимает dict. Атомарность через standard write_lock
-- + tx pattern (см. project_db.py methods).
--
-- C-2 fix (audit 4.5 / Phase 1.B.1): закрывает silent breakage
-- ConsentManager.kv_get/kv_set — методов не существовало, AttributeError
-- молча проглатывался. После этой migration §3.5 auto-refresh consent
-- действительно персистится между перезапусками sidecar.

CREATE TABLE IF NOT EXISTS _kv_store (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

INSERT OR REPLACE INTO schema_version (version, applied_at)
VALUES (3, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
