# Audit Log Schema — Aurora Launch Planner

**S-19 audit (2026-05-15). Schema is clean — no deprecated columns.**

---

## Location

The `audit_log` table lives in the **Tauri-side SQLite** database:

```
%APPDATA%\aurora-launch-planner\aurora_launch.sqlite
```

It is **distinct** from the Python-side persistence DB (`aurora_launch.db`) which
holds projects, versions, blobs, and version_files.

The schema is created at application startup in
`src-tauri/src/state.rs → init_local_storage()`.

---

## Schema (current — v1, no migrations applied)

```sql
CREATE TABLE IF NOT EXISTS audit_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp    TEXT    NOT NULL,   -- ISO 8601 UTC, e.g. "2026-05-15T09:00:00Z"
    actor        TEXT    NOT NULL,   -- "user" | "system" | "sidecar"
    operation    TEXT    NOT NULL,   -- e.g. "open_bundle", "save_bundle", "sign_cert"
    target       TEXT,               -- nullable; e.g. project UUID or file path
    outcome      TEXT    NOT NULL,   -- "success" | "failure" | "warning"
    details_json TEXT               -- nullable; JSON blob with operation-specific data
);
```

### Column inventory

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | No | Row identifier |
| `timestamp` | TEXT | No | ISO 8601 UTC string |
| `actor` | TEXT | No | Who triggered the operation |
| `operation` | TEXT | No | Operation name (discriminator for UI filter) |
| `target` | TEXT | Yes | Affected resource (project UUID, path, etc.) |
| `outcome` | TEXT | No | `success` / `failure` / `warning` |
| `details_json` | TEXT | Yes | JSON-encoded extra context; NULL when empty |

---

## Read path

`src-tauri/src/commands/audit_log.rs` — `list_audit_entries` command.

Selects all 7 columns (index 0-6):

```sql
SELECT id, timestamp, actor, operation, target, outcome, details_json
FROM audit_log
WHERE [optional timestamp / operation filters]
ORDER BY id DESC LIMIT ?
```

Mapped to `AuditEntry` struct via column indices; order is fixed and matches
the SELECT column list.

---

## S-19 Finding: No deprecated columns

All 7 columns are actively read by `list_audit_entries` and used by the frontend
History panel.  No columns were found to be dead/deprecated.

**S-19 verdict: no-op confirmed.** No `ALTER TABLE … DROP COLUMN` migration
is required.

### Rationale

- The schema was introduced as part of Block 2F (Phase Premium) and reached HEAD
  `v0.1.0-rc3` without interim schema changes.
- There is no prior version of the schema that added columns later removed from
  the `SELECT` list.
- SQLite `pragma table_info(audit_log)` would confirm 7 columns on any live DB.

---

## Future migrations

If columns are added in future blocks, apply `ALTER TABLE audit_log ADD COLUMN …`
via the `init_local_storage` migration gate (bump schema_version key in settings
table).  SQLite ≥ 3.35 supports `ALTER TABLE … DROP COLUMN` for future removals.
