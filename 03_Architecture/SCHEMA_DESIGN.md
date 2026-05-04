# Aurora Launch - Schema Design (S005a deliverable)

**Status:** Draft (S005a session pending)
**Authority:** Architectural decision storage layer
**Sprint context:** Blocker для Sprint B1

## Контекст

Sprint B1 designs pickle/storage schema v3.0. Storage choice (pickle vs SQLite vs hybrid) **fundamentally меняет** schema layout, migration strategy, и backwards compat approach. Нужно решить до B1 start.

**Audit finding F18:** S005 split на S005a (storage decision - до B1) + S005b (posterior math - до B5).

---

## Decision Matrix

### Option A: Pure Pickle (как Aurora Econometrica v1.0.16)

**Layout:** один `.aurora` файл = single pickle blob с nested dict.

**Pros:**
- Simplest dev (no new tooling)
- Reuse Econometrica patterns
- Fast read/write для full project
- Native Python serialization

**Cons:**
- Backwards compat fragile (changes к Pydantic models = breaking)
- Cannot read individual sections без full unpickle (slow project list view)
- Не human-readable
- Cannot query / SQL-style operations

**Migration approach:** schema_registry pattern с migration functions.

### Option B: Pure SQLite

**Layout:** `.aurora` файл = SQLite database с structured tables.

**Pros:**
- Human-readable (через SQL clients)
- Query-able (read individual sections fast)
- Built-in BC support (schema migrations через ALTER)
- Type safety при schema evolution
- Index support (fast lookups)

**Cons:**
- Breaking change vs Aurora Econometrica formats
- Math artifacts (numpy arrays, pickled models) need BLOB columns или external files
- Slower full read (multiple queries vs single load)
- Need ORM (SQLAlchemy) или manual SQL

**Migration approach:** Alembic migrations или native SQLite versioning.

### Option C: Hybrid - SQLite metadata + Pickle BLOBs

**Layout:** `.aurora` файл = SQLite database where:
- Metadata tables (project info, schema version, timestamps, audit logs)
- Math artifacts в BLOB columns (numpy/pickle)

**Pros:**
- Best of both worlds: query metadata fast, math intact
- Backwards compat через schema migrations (Alembic)
- Project list view fast (only SELECT metadata)
- Math libraries unchanged (still pickle для numpy arrays)

**Cons:**
- Slight complexity (mixed paradigm)
- Initial dev cost vs Option A

**Migration approach:** Alembic + SchemaRegistry hybrid.

---

## Recommended Decision: **Option C (Hybrid)**

**Reasoning:**
1. Backwards compat critical (audit F1, F42) - SQLite migrations more reliable
2. Project list view performance (audit B3) - SQLite metadata faster
3. Math artifacts integrity (audit B5) - keep pickle для numpy без conversion
4. Aurora Optimize coordination - same pattern reusable Phase A, не Launch-only

**Tradeoffs accepted:**
- +1 week dev cost vs Option A (Sprint B1 length adjusted)
- New dep: SQLAlchemy + Alembic (~10MB bundle increase)

---

## Schema Layout (recommended)

```sql
-- Metadata table
CREATE TABLE project_metadata (
    id INTEGER PRIMARY KEY,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_modified TEXT NOT NULL,
    aurora_version TEXT NOT NULL,
    project_name TEXT,
    recipient_brand_name TEXT,
    category TEXT,
    notes TEXT
);

-- Proxy data references
CREATE TABLE proxy_brands (
    id INTEGER PRIMARY KEY,
    proxy_brand_name TEXT NOT NULL,
    similarity_score REAL CHECK(similarity_score >= 0 AND similarity_score <= 1),
    similarity_dimensions TEXT,  -- JSON
    confidence_verdict TEXT CHECK(confidence_verdict IN ('High','Medium','Low','Insufficient')),
    data_period_start TEXT,
    data_period_end TEXT,
    pooling_weight REAL DEFAULT 1.0  -- для multi-proxy
);

-- Recipient anchors
CREATE TABLE recipient_anchors (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES project_metadata(id),
    schema_version TEXT NOT NULL,
    anchors_json TEXT NOT NULL  -- JSON-serialized RecipientAnchorsV1
);

-- Models (pickle BLOBs)
CREATE TABLE models (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES project_metadata(id),
    model_type TEXT CHECK(model_type IN ('proxy', 'recipient', 'multi_proxy_hierarchical')),
    trained_at TEXT NOT NULL,
    pickle_blob BLOB NOT NULL,  -- Pydantic model + numpy arrays
    metadata_json TEXT  -- training params, diagnostics
);

-- Forecasts
CREATE TABLE forecasts (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES project_metadata(id),
    generated_at TEXT NOT NULL,
    horizon_weeks INTEGER NOT NULL,
    forecast_blob BLOB NOT NULL,  -- ForecastHorizon pickle
    aurora_version TEXT NOT NULL,
    hash_signature TEXT NOT NULL  -- SHA-256 for reproducibility
);

-- Posterior updates audit log
CREATE TABLE posterior_updates (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES project_metadata(id),
    timestamp TEXT NOT NULL,
    weeks_recipient_data INTEGER NOT NULL,
    proxy_weight_before REAL,
    proxy_weight_after REAL,
    triggering_data_hash TEXT,
    note TEXT
);

-- Reports generated
CREATE TABLE reports (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES project_metadata(id),
    report_type TEXT CHECK(report_type IN ('pptx','html','xlsx','pdf_certificate')),
    generated_at TEXT NOT NULL,
    file_path TEXT NOT NULL,
    hash_signature TEXT NOT NULL
);

-- Schema migration tracking (Alembic)
CREATE TABLE alembic_version (
    version_num TEXT NOT NULL PRIMARY KEY
);
```

**Indexes:**
```sql
CREATE INDEX idx_proxy_project ON proxy_brands(project_id);
CREATE INDEX idx_anchors_project ON recipient_anchors(project_id);
CREATE INDEX idx_models_project ON models(project_id);
CREATE INDEX idx_forecasts_project ON forecasts(project_id);
CREATE INDEX idx_posterior_updates_project ON posterior_updates(project_id);
```

---

## Migration Strategy

### Initial Migration (v1.0 - schema creation)

```python
# alembic/versions/001_initial_schema.py
def upgrade():
    op.create_table('project_metadata', ...)
    op.create_table('proxy_brands', ...)
    # ... etc
```

### v2.0 → v3.0 Migration (Aurora Launch additions)

```python
# alembic/versions/002_launch_v3_additions.py
def upgrade():
    op.add_column('project_metadata', sa.Column('recipient_brand_name', sa.Text()))
    op.add_column('project_metadata', sa.Column('category', sa.Text()))
    op.create_table('proxy_brands', ...)
    op.create_table('recipient_anchors', ...)
    # ... etc

def downgrade():
    # Reverse operations (rarely needed, but Alembic supports)
    op.drop_column('project_metadata', 'recipient_brand_name')
    # ...
```

### Aurora Econometrica .aurora projects (v2.0 pickle) Migration

For backwards compat - convert old pickle .aurora к SQLite hybrid:

```python
# tools/migrate_aurora_pickle_to_sqlite.py
def migrate_project(old_aurora_path, new_aurora_path):
    """One-time migration of v2.0 pickle to v3.0 SQLite hybrid."""
    with open(old_aurora_path, 'rb') as f:
        data = pickle.load(f)

    # Apply v2 → v3 schema migrations
    data = SchemaRegistry.migrate(data, target_version="3.0")

    # Create new SQLite project
    db = create_aurora_sqlite(new_aurora_path)

    # Populate metadata
    db.insert_project_metadata({...})

    # Pickle BLOB для models
    db.insert_model({
        'pickle_blob': pickle.dumps(data['model']),
        ...
    })

    db.commit()
```

---

## Open Questions для S005a session

1. **Apply hybrid pattern к Aurora Econometrica?**
   - Pros: Suite consistency, agency multi-tenant easier
   - Cons: Aurora Econometrica is in production - migration risk
   - Recommend: Aurora Launch ships hybrid, Aurora Econometrica migrates Phase D

2. **External vs embedded Alembic?**
   - Embedded Alembic (in-app migrations): simpler distribution
   - External tool (separate CLI): power users
   - Recommend: embedded для Phase B

3. **What if SQLite file corrupted?**
   - Backup strategy? Rolling backups?
   - Recovery tool?
   - Recommend: weekly auto-backup on save (rolling 4)

4. **Concurrency** (multi-user agency workflow)
   - SQLite WAL mode handles concurrent reads
   - Single writer at a time
   - Phase D consideration для true multi-user

5. **File size limits**
   - SQLite supports large files (TB range)
   - Practical .aurora bundle size: ≤ 100MB typical
   - Larger? Investigate Phase D

---

## Связанные документы

- `decisions/ADR-002-storage-layer.md` (TBD после S005a)
- `REUSE_FROM_ECONOMETRICA.md` - schema registry pattern
- `../05_Sessions/SESSION_NEXT_QUESTIONS.md` - S005a session prep
- Memory: `project_econometrica_v1_2_0_foundation_2026_04_28.md` - additive schema pattern
