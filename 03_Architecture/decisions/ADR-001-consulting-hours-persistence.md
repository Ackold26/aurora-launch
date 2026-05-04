# ADR-001: Consulting Hours Persistence Layer

**Status:** Accepted
**Date:** 2026-05-04
**Authors:** Маша + Антон
**Sprint context:** B1.5 (Customer Success Lite)

## Context

Aurora Launch subscription model = unlimited launches + 20-40h consulting hours per год. Hours need to be tracked для:
- Billing reconciliation
- Customer success review (quarterly)
- Client visibility ("12/30 used")
- Renewal negotiations (overage / loyalty discount)

Where to store hours data? Privacy и operational concerns:
- Local-first principle (P14 в DATA_PRIVACY.md) запрещает sending raw client data в Aurora cloud
- Но hours sync upgrades sales velocity (Антон видит usage trends across clients)
- Sub-license: per-license-key vs per-machine

## Decision

**Local SQLite database** в `%LOCALAPPDATA%\Aurora Launch\consulting.db`, **per-license-key scoped**, **CSV export для billing**, **opt-in cloud sync для aggregate usage analytics в Phase C+**.

### Schema:
```sql
CREATE TABLE consulting_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    license_key_hash TEXT NOT NULL,  -- SHA-256 of license key
    timestamp TEXT NOT NULL,         -- ISO 8601
    event_type TEXT NOT NULL CHECK(event_type IN (
        'proxy_review',
        'posterior_update_session',
        'methodology_question',
        'training',
        'onsite',
        'kickoff',
        'quarterly_review'
    )),
    duration_minutes INTEGER NOT NULL CHECK(duration_minutes > 0 AND duration_minutes <= 600),
    note TEXT,
    auto_generated BOOLEAN DEFAULT 1  -- 1 = auto-logged by app, 0 = manual entry
);

CREATE INDEX idx_timestamp ON consulting_log(timestamp);
CREATE INDEX idx_event_type ON consulting_log(event_type);

CREATE TABLE billing_periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    license_key_hash TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    tier TEXT CHECK(tier IN ('starter', 'pro', 'enterprise')),
    hours_allowance INTEGER,
    hours_used INTEGER,
    closed BOOLEAN DEFAULT 0
);
```

### Auto-logged events:
- App launch / project open (session start markers, used для context, не billed)
- "Generate forecast" - 0 minutes (instrumentation only)
- User "Schedule consulting session" - manual entry с duration prompt

### Manual entries:
- User opens hours log → "Add manual entry" button
- Date/time picker + event_type dropdown + duration + note

### Export:
- CSV export to `%USERPROFILE%\Documents\Aurora Launch\consulting_export_YYYY-MM-DD.csv`
- Format: timestamp, event_type, duration_minutes, note, auto_generated
- Headers in Russian + English

### Opt-in cloud sync (Phase C+):
- User enables в Settings → Privacy → "Share aggregate usage analytics"
- Aurora cloud receives **only** `event_type` counts + `duration_minutes` aggregates per month (no notes, no project names)
- Used для product analytics (popular event types, time of day patterns)

## Consequences

### Positive
- Local-first principle preserved
- Per-license isolation (multi-machine support через manual import - см. Limitations)
- Antón может request CSV from client при quarterly review (consent-based)
- SQLite robustly handles concurrent access (WAL mode)
- Zero infrastructure cost при no-cloud-sync default

### Negative
- Hours not synced across multiple machines (one license, two laptops = manual export/import)
- Loss of consulting.db = loss of history (mitigated через regular CSV export reminder)
- Manual entry friction для events не auto-logged

### Neutral
- Future Phase D могут переехать на cloud-first storage если customer demand появится

## Alternatives Considered

### Option A: Cloud-first SQLite
- Pros: Multi-machine sync, Aurora team analytics
- Cons: **Violates local-first principle** (consulting events содержат client/project names в notes)
- Why not chosen: P14 hard constraint, privacy concerns paramount

### Option B: Excel file in user's Documents folder
- Pros: User-readable directly
- Cons: Concurrent access issues, no schema enforcement, easily corrupted
- Why not chosen: SQLite robust, ergonomic

### Option C: No persistence, in-memory only + Antón maintains spreadsheet
- Pros: Simplest
- Cons: Не scales beyond ~5 clients, single point of failure (Antón's spreadsheet)
- Why not chosen: Subscription model requires reliable tracking

## Implementation Notes

- File: `engines/consulting_tracker.py` (new, Sprint B1.5)
- File: `src/lib/components/ConsultingHoursWidget.svelte` (new, Sprint B1.5)
- Tests: `tests/unit/test_consulting_tracker.py`
- Migration: schema versioned via SQLAlchemy Alembic (или simpler: native SQLite version table)
- Backup: weekly auto-backup `consulting.db` → `consulting.db.bak` (rolling 4 backups)

## References

- DATA_PRIVACY.md Section 4 (Aurora Team Access)
- UX_PRINCIPLES.md C8 (Audit trail visible) + Sprint B1.5 deliverables
- ConsultingEvent schema в REUSE_FROM_ECONOMETRICA.md
- Audit finding F32 (track persistence undefined)
