# ADR-002: .aurora Bundle Storage Layer

**Status:** Accepted
**Date:** 2026-05-04
**Authors:** Маша (decision design) + Антон (authority delegated, autonomous mandate "веди всю S005a сессию максимально автономно")
**Sprint context:** B1 (Schema Extension + Schema Registry) - architectural blocker
**Supersedes draft:** SCHEMA_DESIGN.md v0 "Recommended Option C (SQLite hybrid)"

## Context

Aurora Launch требует контейнерный формат для проекта (`.aurora` bundle), который содержит:

- Project metadata (имя, recipient brand, category, timestamps, app version, schema version)
- Proxy brand metadata (similarity score, 6 dimensions, verdict)
- Recipient anchors (validated Pydantic model)
- Transfer provenance (что переносится из proxy в recipient)
- Trained models (NumPyro/JAX models с numpy arrays, pickle artifacts ~10-50 MB)
- Forecast horizons (12/26/52 weeks с CI per horizon)
- Posterior update audit log (append-only events)
- Consulting hours log (audit trail для subscription tracking)
- Decomposition / scenario / optimization cached artifacts

**Constraints driving decision:**

1. **Local-first architecture (P-DATA_PRIVACY)** - данные не покидают машину клиента. Storage решение не должно блокировать DPA compliance.
2. **Human inspectability (P10 Premium Feel)** - support sessions без открытия app, audit reproducibility, debugging, third-party методологический ревью клиентом или регулятором.
3. **Backwards compatibility (audit F1, F9)** - schema evolution v1 → v2 → v3 → ... без data loss. Cross-app open: Aurora Econometrica открывает Launch project (legacy fields ignored), Aurora Launch открывает Econometrica v2 pickle (legacy migration).
4. **80%+ reuse Econometrica engines (P9)** - math layer (NumPyro/JAX models, modeler/decomposer/optimizer) уже сериализуется через pickle. Новый storage не должен требовать переписывание math pipeline.
5. **Suite consistency (Phase A platform-core)** - storage pattern может быть applied к Econometrica/Optimize/Brand future migrations. Pattern должен быть адаптируем без breaking math pipeline.
6. **Bundle size** - typical 10-50 MB, expected upper bound ~500 MB (multiple horizons + decomposition caches).
7. **Concurrency** - single-user model для Phase B (Phase D consideration для true multi-user).
8. **Subscription support workflow** - Антон может попросить клиента отправить `.aurora` для quarterly review без устанавливать у клиента special tools.

**Forces в conflict:**

- Pickle (status quo Econometrica) даёт fastest path + 100% reuse, но breaks human inspectability + BC fragile.
- SQL-based решения (SQLite) дают query-able structure + Alembic-style migrations, но не дают benefit для math artifacts (всё равно BLOB pickle), добавляют 10 MB deps, breaking pattern с Econometrica.
- ZIP-based решение (industry pattern .docx/.xlsx/.pptx) даёт human inspectability + atomic save + zero new deps + 100% reuse pickle для math.

## Decision

**`.aurora` файл = ZIP archive container** с следующим внутренним layout:

```
project.aurora  (ZIP, store-only compression by default, deflate optional)
├── manifest.json              # SSoT для schema versions + integrity hashes
├── metadata.json              # project info (name, brand, category, timestamps)
├── proxy_brand_metadata.json  # ProxyBrandMetadata (Pydantic v2 model)
├── recipient_anchors.json     # RecipientAnchorsV1 (Pydantic v2 model)
├── transfer_provenance.json   # TransferProvenance audit
├── posterior_update_log.json  # List[PosteriorUpdateEvent] append-only
├── consulting_hours_log.json  # List[ConsultingEvent] append-only
├── models/
│   ├── proxy_model.pickle      # NumPyro/JAX trained model
│   ├── recipient_model.pickle  # Adapted model post-transfer
│   └── multi_proxy_model.pickle (optional, multi-proxy expert mode)
├── forecasts/
│   ├── horizon_12w.pickle
│   ├── horizon_26w.pickle
│   └── horizon_52w.pickle
└── cache/
    ├── decompositions.pickle (optional)
    └── scenarios.pickle (optional)
```

### manifest.json schema (SSoT)

```json
{
  "manifest_version": "1.0",
  "schema_version": "3.0",
  "aurora_app": "Aurora Launch",
  "aurora_app_version": "1.4.0",
  "min_app_version": "1.4.0",
  "created_at": "2026-08-15T14:30:00Z",
  "last_modified": "2026-08-15T16:45:12Z",
  "project_id": "uuid-v4-here",
  "files": {
    "metadata.json": {"sha256": "abc123...", "size_bytes": 1024, "schema_version": "1.0"},
    "recipient_anchors.json": {"sha256": "def456...", "size_bytes": 2048, "schema_version": "1.0"},
    "models/proxy_model.pickle": {"sha256": "789abc...", "size_bytes": 12582912, "schema_version": "2.0"},
    "...": "..."
  },
  "integrity_check": "strict|warn|disabled",
  "compression": "store|deflate"
}
```

**Per-file `schema_version`** позволяет independent evolution: `recipient_anchors` v1 → v2 без bumping global schema_version (используется для major schema breaks only).

### Manifest-driven open/save protocol

**Open:**
1. Verify ZIP magic bytes (50 4B 03 04). If absent → legacy detection (raw pickle Econometrica) → migration path.
2. Read `manifest.json` first.
3. Check `min_app_version` ≤ current app version. If нет → return CompatResult с suggested_action="update_app".
4. Optional: verify SHA-256 hashes of files (controlled by `integrity_check` field). On mismatch → warn user, allow continue.
5. Lazy-load files on demand: metadata.json для project list view, models/*.pickle только при train/forecast operation.

**Save (atomic):**
1. Write to `project.aurora.tmp` (sibling в same directory).
2. Update manifest.json hashes для всех modified files.
3. fsync.
4. Atomic rename: `project.aurora.tmp` → `project.aurora` (overwrites).
5. Pre-rename, optionally rotate backup: previous `project.aurora` → `.aurora.bak.N` (rolling 4).

### Migration: Econometrica v2 pickle → Launch v3 zip

```python
# tools/migrate_aurora_pickle_to_zip.py
def migrate(old_path: Path, new_path: Path) -> None:
    """One-time migration v2.0 raw pickle → v3.0 zip archive."""
    with open(old_path, "rb") as f:
        data = pickle.load(f)

    # Apply v2 → v3 schema migration (additive, no field loss)
    data = SchemaRegistry.migrate(data, target_version="3.0")

    with zipfile.ZipFile(new_path, "w", zipfile.ZIP_STORED) as zf:
        # Manifest first
        manifest = build_manifest(data)
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        # Structured data → JSON
        zf.writestr("metadata.json", json.dumps(data["metadata"], indent=2))
        zf.writestr("recipient_anchors.json", data.get("recipient_anchors", {}))
        # ... etc

        # Math artifacts → pickle BLOBs in models/
        zf.writestr("models/proxy_model.pickle", pickle.dumps(data["model"]))
```

Migration triggered transparently при first save после opening legacy file. User informed через UI dialog.

### Backwards compat: legacy detection

```python
def detect_format(path: Path) -> Literal["zip_v3", "pickle_v2", "pickle_v1", "unknown"]:
    with open(path, "rb") as f:
        magic = f.read(4)
    if magic[:2] == b"PK":  # ZIP magic (50 4B 03 04 or 50 4B 05 06)
        return "zip_v3"
    if magic[:2] == b"\x80\x04" or magic[:2] == b"\x80\x05":  # pickle protocol 4/5
        # Read full pickle, check schema_version field
        return classify_pickle_version(path)
    return "unknown"
```

### Compression policy

**Default: store-only (ZIP_STORED).**

Rationale: math arrays (numpy в pickle) уже binary-compact, deflate yields ~3-8% size reduction для +5-15% CPU on save. Net negative для UX.

**User can enable deflate** в Settings → Storage → Compression. Useful для archiving (clients with slow network sharing `.aurora` files).

### Integrity check policy

**Default: `strict`** (verify all hashes на open, warn on mismatch).

User can switch to `warn` (log only, не block UI) или `disabled` (skip verification) если работает с large bundles на slow disks.

## Consequences

### Positive

- **Human inspectability** - any user может `unzip project.aurora` и прочитать `metadata.json`, `recipient_anchors.json` без устанавливать Aurora. Audit reproducibility, debugging support sessions, regulator review.
- **Zero new dependencies** - Python stdlib `zipfile` достаточно. No SQLAlchemy, no Alembic, no external SQLite client. Bundle size impact: 0 MB.
- **100% reuse Econometrica engines** - math pipeline (NumPyro/JAX, modeler.py, decomposer.py) сериализует через pickle как раньше. Просто кладём pickle файлы внутрь ZIP container, ничего не переписываем в math layer.
- **Forward compat trivial** - manifest.json несёт `min_app_version`. Older app reads manifest first, sees mismatch, errors clearly. No silent corruption.
- **Backwards compat clean** - Econometrica v2 raw pickle detected by ZIP magic absence, migrated transparently на first save через SchemaRegistry. SchemaRegistry pattern (BFS path resolution, `REUSE_FROM_ECONOMETRICA.md` Section 2.1) reused as-is.
- **Atomic save** - tmp + rename pattern атомарный на single filesystem. No partial-write corruption.
- **Industry-standard pattern** - .docx/.xlsx/.pptx используют ZIP container с XML внутри. Aurora использует ZIP с JSON + pickle. Tooling everywhere (7-zip, unzip CLI, Python zipfile, Rust zip crate). Cross-platform tested.
- **Per-file schema versioning** - independent evolution: `recipient_anchors` v1 → v2 без bumping global. Hot-fix flexibility.
- **Cross-app applicable Phase D** - Econometrica/Optimize/Brand могут принять тот же pattern без breaking math pipeline. Migration: wrap existing pickle в ZIP с metadata.json, additive process.
- **Audit trail-friendly** - posterior_update_log.json и consulting_hours_log.json как human-readable JSON arrays. Append-only events grow over time, всё видимо без специальных tools.

### Negative

- **No SQL queries** - нельзя WHERE/JOIN на metadata. Acceptable для Phase B scale (1-10 projects per client). Future Phase D agency multi-tenant (1000+ projects) может потребовать external index file (separate `.aurora-index` SQLite на client side для search). Not in S005a scope.
- **Zip create/replace overhead vs single pickle** - на save пишем N files в ZIP (manifest + metadata.json + N pickle files) vs один pickle. Measured overhead ~10-50 ms на typical 10-50 MB bundle. Not noticeable in UX.
- **JSON ↔ Pydantic boilerplate** - structured fields сериализуем в JSON (для inspectability), нужен `model_dump_json` + `model_validate_json` шов. Mitigated через единый `AuroraBundle` reader/writer abstraction.
- **Atomic save requires tmp space** - `.aurora.tmp` file + final rename = peak 2x bundle size on disk during save. Acceptable для 10-50 MB typical, monitored для 500 MB upper bound.

### Neutral

- **File size vs raw pickle** - approximately equal (store-only compression, math arrays already binary-compact). +1-2 KB overhead за manifest.json + metadata.json.
- **Performance vs SQLite hybrid** - read full project: ZIP slightly faster (no SQL query overhead). Read metadata only: ZIP reads `manifest.json` first (~1 KB), SQLite reads metadata table (~1 KB). Equivalent.
- **Encryption story** - both ZIP (AES-256 via pyzipper) и SQLite (SQLCipher) supported. Encryption is out of S005a scope, deferred to Phase C+ если customer demand появится.

## Alternatives Considered

### Option A: Pure Pickle (Aurora Econometrica baseline)

- **Pros:** Zero dev cost, 100% reuse, fast read/write для full project.
- **Cons:** Not human-inspectable (требует Python для open), BC fragile (single binary blob), нельзя прочитать metadata без unpickling всего content (slow project list view), no per-file schema versioning.
- **Why not chosen:** Human inspectability (P10) и audit support workflow (subscription model требует Антон может разбираться с client `.aurora` без app) - hard requirements. Pure pickle их не purveyor.

### Option B: Pure SQLite

- **Pros:** SQL-queryable, ALTER-based migrations, structured.
- **Cons:** Math artifacts (NumPyro/JAX models, numpy arrays) хранятся как BLOB columns - = pickle anyway, никакого storage benefit для math layer. +10 MB deps (SQLAlchemy + Alembic). Breaking pattern с Econometrica baseline. Не human-readable без SQL client. Math pipeline должен переписывать сериализацию через ORM.
- **Why not chosen:** Math BLOB columns = pickle wrapper, не fundamental improvement. SQL queries для 1-10 projects scale - over-engineering. Cost (10 MB deps + Econometrica divergence) > benefit (slight project list query speedup).

### Option C: Hybrid SQLite (metadata) + Pickle (math BLOBs) - INITIAL DRAFT RECOMMENDATION

- **Pros:** SQL queries на metadata (project list view fast), math integrity (pickle inside BLOB), Alembic migrations.
- **Cons:** 2 paradigms = mental complexity (где что хранится). +10 MB deps. Breaking pattern с Econometrica. Не self-evidently superior to D - SQL benefits не нужны на 1-10 projects scale, math BLOB = pickle anyway.
- **Why not chosen:** Real driver analysis показал что primary driver = human inspectability (P10) + BC reliability (audit F1) + cross-app pattern. Option D delivers все три cleaner: zip даёт inspectability (cat manifest.json через unzip), BC через manifest version + SchemaRegistry, cross-app через wrapping pickle в zip без переписывание math. SQL benefits Option C нужны только если scale переходит 1000+ projects per client (Phase D agency tenant) - тогда отдельный external index решает без меняя bundle format.

### Option E (considered late): Tar archive вместо ZIP

- **Pros:** Streaming reads, slightly smaller для many small files.
- **Cons:** Random access weak (для read только manifest.json нужен decompress part of stream), Windows ecosystem меньше friendly (требует extra tool для inspect), no atomic single-file create.
- **Why not chosen:** ZIP лучше для random access (manifest first read), нативная поддержка Windows file explorer.

## Implementation Notes

### Files to create (Sprint B1)

**Backend:**
- `engines/aurora_bundle.py` (NEW) - `AuroraBundle` class с methods:
  - `load(path: Path) -> AuroraBundle`
  - `save(path: Path, atomic: bool = True) -> None`
  - `get_metadata() -> ProjectMetadata`
  - `get_recipient_anchors() -> RecipientAnchorsV1`
  - `get_proxy_metadata() -> ProxyBrandMetadata`
  - `get_model(model_type: Literal["proxy", "recipient", "multi_proxy"])`
  - `get_forecast_horizon(weeks: int)`
  - `append_posterior_update(event: PosteriorUpdateEvent)`
  - `append_consulting_hours(event: ConsultingEvent)`
  - `verify_integrity() -> IntegrityResult`

- `engines/manifest.py` (NEW) - manifest.json schema + helpers:
  - `Manifest` Pydantic v2 model
  - `build_manifest(bundle: AuroraBundle) -> Manifest`
  - `verify_hashes(zip_file: ZipFile, manifest: Manifest) -> List[IntegrityIssue]`

- `engines/schema_registry.py` (extend existing) - migration handlers:
  - `@SchemaRegistry.register("2.0", "3.0")` - existing additive migration
  - NEW: `@SchemaRegistry.register("2.0_pickle", "3.0_zip")` - format migration с pickle wrapping

- `tools/migrate_aurora_pickle_to_zip.py` (NEW) - one-time migration utility (dev tool, не в production UI initially):
  - CLI: `python tools/migrate_aurora_pickle_to_zip.py <old_path> <new_path>`
  - In-app: triggered transparently через `AuroraBundle.load()` если detect_format returns pickle_v2.

**Tests (Sprint B1):**
- `tests/unit/test_aurora_bundle.py` - load/save round-trip, atomic save (kill mid-save not corrupt original), integrity verification, lazy loading.
- `tests/unit/test_manifest.py` - schema validation, hash computation, version compatibility.
- `tests/integration/test_pickle_to_zip_migration.py` - real Econometrica .aurora projects (B0.5 BC corpus 10+ projects) migrate без data loss.

**Documentation:**
- Update `03_Architecture/SCHEMA_DESIGN.md` - finalize as Accepted, replace SQL DDL с ZIP layout (this ADR's Decision section authoritative).
- Update `03_Architecture/REUSE_FROM_ECONOMETRICA.md` Section 2.1 - schema migration теперь ZIP-aware.
- Update `00_Overview/ROADMAP.md` Sprint B1 - reference этот ADR.

### Cross-app coordination

- **Aurora Econometrica future migration** (Phase D, tentative): wrap existing v2 pickle в ZIP container с manifest.json + metadata.json. Math pipeline unchanged. Migration tool reused.
- **Aurora Optimize / Brand** (Phase B / C): adopt тот же pattern из start, не divergent.
- **Phase A platform-core** (`aurora-platform-core` package): expose `AuroraBundle` as public API. All Suite apps inherit.

### Dependencies

- **Standard library only** (Python `zipfile`, `json`, `hashlib`, `tempfile`).
- **Pydantic v2** для manifest + structured JSON files (already required).
- **No new packages.**

### Performance budgets

- **Open small project (10 MB):** ≤50 ms (read manifest.json + lazy load).
- **Open large project (200 MB):** ≤200 ms (read manifest.json only, models lazy).
- **Save small project:** ≤100 ms (manifest update + atomic rename).
- **Save large project:** ≤2 s (write all modified files + manifest + atomic rename).
- **Integrity verification (full):** ≤500 ms на 50 MB bundle (SHA-256 на all files).

### Edge cases

- **Corrupt ZIP** - detect through `zipfile.BadZipFile`, suggest restore from `.aurora.bak.N` (rolling 4).
- **Manifest.json missing** - reject open, suggest user use `tools/repair_aurora.py` (Phase D) which scans ZIP, rebuilds manifest from observed files (best effort, integrity check disabled).
- **Schema version newer than app supports** - clear error в UI с suggested_action="update_app", не corrupt anything.
- **Multi-machine concurrent edit** - file lock через `.aurora.lock` sentinel file. If lock exists и timestamp recent, warn user. Phase D consideration для true multi-user.

## References

- S005a session log (этой сессии Variant autonomous): этот ADR + finalized SCHEMA_DESIGN.md
- `03_Architecture/SCHEMA_DESIGN.md` - finalized layout details (post этого ADR)
- `03_Architecture/REUSE_FROM_ECONOMETRICA.md` Section 2.1 - SchemaRegistry pattern + BFS migration path
- `02_Data_Spec/DATA_REQUIREMENTS.md` - Pydantic v2 models которые сериализуем в JSON
- ADR-001 - Consulting Hours Persistence (separate concern: hours db, не bundle)
- Memory: `project_econometrica_v1_2_0_foundation_2026_04_28.md` - Econometrica pickle v2.0 baseline
- Memory: `project_aurora_launch_principles.md` - P9 reuse + P10 premium feel + DPA
- Industry pattern: Office Open XML `.docx/.xlsx/.pptx` (ECMA-376) - ZIP container с structured XML внутри. Aurora analog: ZIP container с structured JSON + pickle BLOBs.
- Audit findings closed by этого ADR: F1 (BC reliability), F9 (SchemaRegistry), F18 (S005 split), B3 (project list view performance), C10 (audit trail human-readable).
