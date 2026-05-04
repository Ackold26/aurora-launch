# Aurora Launch - Schema Design

**Status:** Accepted (S005a closed 2026-05-04 via ADR-002)
**Authority:** ADR-002 "Storage Layer Choice" - `.aurora` = ZIP archive container
**Sprint context:** Sprint B1 implementation reference
**Supersedes:** Draft v0 (recommended SQLite hybrid - rejected post-analysis)

## Контекст

Этот документ определяет физический layout `.aurora` bundle и schema каждого внутреннего файла. Authority - ADR-002, который закрыл S005a с decision **Option D (ZIP archive container)** вместо initial draft Option C (SQLite hybrid).

Sprint B1 implements `engines/aurora_bundle.py` + `engines/manifest.py` + `tools/migrate_aurora_pickle_to_zip.py` per этот документ.

---

## Bundle Layout

`.aurora` файл = ZIP archive (industry pattern, как `.docx/.xlsx/.pptx`):

```
project.aurora  (ZIP container)
├── manifest.json              # SSoT schema versions + integrity hashes
├── metadata.json              # Project info (name, brand, category, timestamps)
├── proxy_brand_metadata.json  # ProxyBrandMetadata Pydantic model
├── recipient_anchors.json     # RecipientAnchorsV1 Pydantic model
├── transfer_provenance.json   # TransferProvenance audit
├── posterior_update_log.json  # List[PosteriorUpdateEvent] append-only
├── consulting_hours_log.json  # List[ConsultingEvent] append-only (mirror local DB per ADR-001)
├── models/
│   ├── proxy_model.pickle      # NumPyro/JAX trained model
│   ├── recipient_model.pickle  # Adapted model post-transfer
│   └── multi_proxy_model.pickle (optional, multi-proxy expert mode)
├── forecasts/
│   ├── horizon_12w.pickle      # ForecastHorizon Pydantic + numpy arrays
│   ├── horizon_26w.pickle
│   └── horizon_52w.pickle
└── cache/  (optional, regenerable)
    ├── decompositions.pickle
    └── scenarios.pickle
```

**Compression default:** ZIP_STORED (store-only). Math arrays в pickle уже binary-compact, deflate yields 3-8% size reduction для +5-15% CPU. Net negative для UX. User может включить deflate в Settings → Storage.

**Per-file schema versioning:** independent evolution. `recipient_anchors.json` v1 → v2 не требует bumping global `schema_version`. Global version bumps только при major breaks.

---

## File Schemas

### manifest.json (SSoT)

```python
# engines/manifest.py
from pydantic import BaseModel, Field
from typing import Dict, Literal, Optional
from datetime import datetime

class FileEntry(BaseModel):
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(ge=0)
    schema_version: str  # per-file independent versioning

class Manifest(BaseModel):
    manifest_version: Literal["1.0"] = "1.0"
    schema_version: str  # global bundle schema version (e.g., "3.0")
    aurora_app: Literal["Aurora Launch", "Aurora Econometrica", "Aurora Optimize", "Aurora Brand"]
    aurora_app_version: str  # e.g., "1.4.0"
    min_app_version: str  # minimum app version that can read this bundle
    created_at: datetime
    last_modified: datetime
    project_id: str  # UUID v4
    files: Dict[str, FileEntry]  # path в ZIP → integrity entry
    integrity_check: Literal["strict", "warn", "disabled"] = "strict"
    compression: Literal["store", "deflate"] = "store"
```

**Sample manifest.json:**
```json
{
  "manifest_version": "1.0",
  "schema_version": "3.0",
  "aurora_app": "Aurora Launch",
  "aurora_app_version": "1.4.0",
  "min_app_version": "1.4.0",
  "created_at": "2026-08-15T14:30:00Z",
  "last_modified": "2026-08-15T16:45:12Z",
  "project_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "files": {
    "metadata.json": {"sha256": "abc...", "size_bytes": 1024, "schema_version": "1.0"},
    "recipient_anchors.json": {"sha256": "def...", "size_bytes": 2048, "schema_version": "1.0"},
    "proxy_brand_metadata.json": {"sha256": "ghi...", "size_bytes": 1536, "schema_version": "1.0"},
    "transfer_provenance.json": {"sha256": "jkl...", "size_bytes": 768, "schema_version": "1.0"},
    "models/proxy_model.pickle": {"sha256": "mno...", "size_bytes": 12582912, "schema_version": "2.0"},
    "models/recipient_model.pickle": {"sha256": "pqr...", "size_bytes": 13107200, "schema_version": "2.0"},
    "forecasts/horizon_12w.pickle": {"sha256": "stu...", "size_bytes": 524288, "schema_version": "1.0"},
    "forecasts/horizon_26w.pickle": {"sha256": "vwx...", "size_bytes": 1048576, "schema_version": "1.0"},
    "forecasts/horizon_52w.pickle": {"sha256": "yz0...", "size_bytes": 2097152, "schema_version": "1.0"},
    "posterior_update_log.json": {"sha256": "123...", "size_bytes": 4096, "schema_version": "1.0"},
    "consulting_hours_log.json": {"sha256": "456...", "size_bytes": 8192, "schema_version": "1.0"}
  },
  "integrity_check": "strict",
  "compression": "store"
}
```

### metadata.json

```python
class ProjectMetadata(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    project_id: str  # UUID v4 (must match manifest)
    project_name: str = Field(min_length=1, max_length=200)
    recipient_brand_name: str
    category: str  # FMCG_snacks, OTC_pharma, etc. (CATEGORY_MEDIA_TO_REV_RATIO keys)
    sub_category: Optional[str] = None
    expected_launch_date: date
    notes: Optional[str] = None
    created_at: datetime
    last_modified: datetime
    aurora_app: str
    aurora_app_version: str
```

### proxy_brand_metadata.json

Per `02_Data_Spec/DATA_REQUIREMENTS.md` Section 5.1 `ProxyBrandMetadata`:

```python
class ProxyBrandMetadata(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    brand_id: str
    brand_name: str
    category: str
    sub_category: str
    similarity_dimensions: dict[str, float]  # 6 dimensions с scores
    similarity_aggregate: float = Field(ge=0, le=1)
    confidence_verdict: Literal["High", "Medium", "Low", "Insufficient"]
    data_period_start: date
    data_period_end: date
    data_sources: List[Literal["DSM_Group", "Mediascope_TV", "Mediascope_Digital", "Digital_Budget"]]
```

### recipient_anchors.json

Per `02_Data_Spec/RECIPIENT_ANCHORS.md` `RecipientAnchorsV1` Pydantic model. Stored as `model.model_dump_json(indent=2)`.

### transfer_provenance.json

Per `03_Architecture/REUSE_FROM_ECONOMETRICA.md` Section 2.1:

```python
class TransferProvenance(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    proxy_engine_version: str  # e.g., "single_proxy_transfer/0.1.0"
    transferred_parameters: List[Literal[
        "adstock_decay_per_channel",
        "hill_saturation_shape",
        "reach_freq_curve_shape",
        "category_seasonality",
        "long_term_trend",
    ]]
    excluded_parameters: List[str]  # e.g., ["beta_magnitude", "baseline"]
    similarity_aggregate: float = Field(ge=0, le=1)
    transfer_timestamp: datetime
    notes: Optional[str] = None
```

### posterior_update_log.json (append-only)

```python
class PosteriorUpdateLog(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    events: List[PosteriorUpdateEvent]  # append-only

# PosteriorUpdateEvent in REUSE_FROM_ECONOMETRICA.md Section 2.1
```

### consulting_hours_log.json (append-only mirror)

**Important:** primary хранилище consulting hours = local SQLite DB `%LOCALAPPDATA%\Aurora Launch\consulting.db` (per ADR-001). Mirror в bundle - **opt-in subset** для project-specific events (proxy review, posterior update, methodology question связанные с этим конкретным project).

```python
class ConsultingHoursLog(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    project_specific_events: List[ConsultingEvent]  # subset, not full DB
    last_synced_from_db: datetime
```

Bundle hours log != full hours DB. Full DB остаётся в local SQLite per ADR-001 для cross-project tracking + billing.

### models/*.pickle

NumPyro/JAX trained models через `pickle.dumps(model)`. Schema version в manifest.json `files["models/*.pickle"].schema_version` (currently "2.0" - matches Aurora Econometrica v1.2.0 pickle layer).

**Note:** pickle BLOBs хранят:
- `model_version` (string)
- `posterior_samples` (numpy arrays)
- `prior_specs` (Pydantic model)
- `convergence_diagnostics` (dict)
- `intercept_mean`, `control_betas_mean` (existing Econometrica fields)

Loading: `pickle.loads(zf.read("models/proxy_model.pickle"))` returns trained model object.

### forecasts/horizon_NNw.pickle

ForecastHorizon Pydantic model + numpy arrays через pickle:

```python
# Pickle blob contains:
class ForecastHorizonArtifact:
    horizon: ForecastHorizon  # Pydantic v2 model (REUSE_FROM_ECONOMETRICA.md Section 2.1)
    samples: np.ndarray  # shape (n_samples, n_weeks)
    component_decomposition: Optional[dict]  # per-channel contributions
    generated_at: datetime
    model_hash: str  # SHA-256 of source model.pickle для reproducibility
```

---

## Open / Save Protocol

### AuroraBundle class API

```python
# engines/aurora_bundle.py
from pathlib import Path
from typing import Optional, List, Literal
import zipfile
import json
import pickle
import tempfile
import os
import hashlib

class AuroraBundle:
    """ZIP-based .aurora bundle reader/writer."""

    def __init__(self, path: Path, mode: Literal["r", "w", "a"] = "r"):
        self.path = path
        self.mode = mode
        self._zip: Optional[zipfile.ZipFile] = None
        self._manifest: Optional[Manifest] = None
        self._dirty_files: dict[str, bytes] = {}  # path → new content

    def __enter__(self):
        if self.mode == "r":
            self._open_read()
        elif self.mode == "w":
            self._init_write()
        elif self.mode == "a":
            self._open_append()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None and self.mode in ("w", "a") and self._dirty_files:
            self._atomic_save()
        elif self._zip:
            self._zip.close()

    def _open_read(self):
        # 1. Verify ZIP magic (raises BadZipFile if not zip)
        self._zip = zipfile.ZipFile(self.path, "r")
        # 2. Read manifest first
        manifest_bytes = self._zip.read("manifest.json")
        self._manifest = Manifest.model_validate_json(manifest_bytes)
        # 3. Compatibility check
        compat = check_forward_compatibility(
            {"schema_version": self._manifest.schema_version},
            current_app_version=AURORA_APP_VERSION,
        )
        if not compat.can_open:
            raise IncompatibleSchemaError(compat.reason, compat.suggested_action)
        # 4. Optional integrity check
        if self._manifest.integrity_check == "strict":
            issues = self._verify_hashes()
            if issues:
                raise IntegrityError(issues)

    def get_metadata(self) -> ProjectMetadata:
        data = self._zip.read("metadata.json")
        return ProjectMetadata.model_validate_json(data)

    def get_recipient_anchors(self) -> RecipientAnchorsV1:
        data = self._zip.read("recipient_anchors.json")
        return RecipientAnchorsV1.model_validate_json(data)

    def get_proxy_metadata(self) -> ProxyBrandMetadata:
        data = self._zip.read("proxy_brand_metadata.json")
        return ProxyBrandMetadata.model_validate_json(data)

    def get_model(self, model_type: Literal["proxy", "recipient", "multi_proxy"]):
        path = f"models/{model_type}_model.pickle"
        return pickle.loads(self._zip.read(path))

    def get_forecast_horizon(self, weeks: Literal[12, 26, 52]):
        path = f"forecasts/horizon_{weeks}w.pickle"
        return pickle.loads(self._zip.read(path))

    def append_posterior_update(self, event: PosteriorUpdateEvent):
        log = self._read_or_init_log("posterior_update_log.json", PosteriorUpdateLog)
        log.events.append(event)
        self._dirty_files["posterior_update_log.json"] = log.model_dump_json(indent=2).encode()

    def set_metadata(self, metadata: ProjectMetadata):
        self._dirty_files["metadata.json"] = metadata.model_dump_json(indent=2).encode()

    def set_model(self, model_type: str, model):
        path = f"models/{model_type}_model.pickle"
        self._dirty_files[path] = pickle.dumps(model)

    def _atomic_save(self):
        """Write to .aurora.tmp, fsync, atomic rename."""
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        # Backup rotation (rolling 4)
        self._rotate_backups()

        # Build manifest from current + dirty files
        new_manifest = self._build_manifest()

        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_STORED) as zf:
            zf.writestr("manifest.json", new_manifest.model_dump_json(indent=2))
            # Carry forward unchanged files from existing zip
            if self._zip:
                for name in self._zip.namelist():
                    if name == "manifest.json":
                        continue
                    if name in self._dirty_files:
                        continue
                    zf.writestr(name, self._zip.read(name))
            # Write dirty files
            for name, data in self._dirty_files.items():
                zf.writestr(name, data)

        # fsync to ensure durability
        with open(tmp_path, "rb") as f:
            os.fsync(f.fileno())

        # Atomic rename
        os.replace(tmp_path, self.path)

    def _rotate_backups(self):
        """Rolling 4 backups: .aurora.bak.1 (newest) → .bak.4 (oldest)."""
        if not self.path.exists():
            return
        for i in range(4, 1, -1):
            old = self.path.with_suffix(self.path.suffix + f".bak.{i-1}")
            new = self.path.with_suffix(self.path.suffix + f".bak.{i}")
            if old.exists():
                os.replace(old, new)
        bak1 = self.path.with_suffix(self.path.suffix + ".bak.1")
        if bak1.exists():
            bak1.unlink()
        # Don't rotate current file - .tmp + rename does that
```

### Migration: pickle v2 → zip v3

```python
# tools/migrate_aurora_pickle_to_zip.py
import pickle
import json
import zipfile
import uuid
from datetime import datetime
from pathlib import Path

def detect_format(path: Path) -> Literal["zip_v3", "pickle_v2", "pickle_v1", "unknown"]:
    with open(path, "rb") as f:
        magic = f.read(4)
    if magic[:2] == b"PK":
        return "zip_v3"
    if magic[:1] == b"\x80":  # pickle protocol marker
        # Open pickle, check schema_version field
        with open(path, "rb") as f:
            data = pickle.load(f)
        sv = data.get("schema_version", "1.0")
        if sv == "1.0":
            return "pickle_v1"
        elif sv == "2.0":
            return "pickle_v2"
    return "unknown"


def migrate_pickle_to_zip(old_path: Path, new_path: Path) -> None:
    """One-time migration: Aurora Econometrica v2 raw pickle → v3 zip."""
    fmt = detect_format(old_path)
    if fmt == "zip_v3":
        raise ValueError(f"{old_path} is already zip format - no migration needed")
    if fmt == "unknown":
        raise ValueError(f"{old_path} is not a recognizable Aurora bundle")

    with open(old_path, "rb") as f:
        data = pickle.load(f)

    # Apply v1 → v2 → v3 schema migrations through SchemaRegistry BFS path
    data = SchemaRegistry.migrate(data, target_version="3.0")

    project_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    with zipfile.ZipFile(new_path, "w", zipfile.ZIP_STORED) as zf:
        # Write structured fields as JSON
        metadata = {
            "schema_version": "1.0",
            "project_id": project_id,
            "project_name": data.get("project_name", "Imported from Econometrica"),
            "recipient_brand_name": data.get("recipient_brand_name", "Unknown"),
            "category": data.get("category", "Unknown"),
            "expected_launch_date": data.get("expected_launch_date"),
            "created_at": now,
            "last_modified": now,
            "aurora_app": "Aurora Launch",
            "aurora_app_version": AURORA_APP_VERSION,
        }
        zf.writestr("metadata.json", json.dumps(metadata, indent=2))

        if data.get("recipient_anchors"):
            zf.writestr("recipient_anchors.json", json.dumps(data["recipient_anchors"], indent=2))
        if data.get("proxy_brand_metadata"):
            zf.writestr("proxy_brand_metadata.json", json.dumps(data["proxy_brand_metadata"], indent=2))
        if data.get("transfer_provenance"):
            zf.writestr("transfer_provenance.json", json.dumps(data["transfer_provenance"], indent=2))
        if data.get("posterior_update_log"):
            zf.writestr("posterior_update_log.json", json.dumps({"schema_version": "1.0", "events": data["posterior_update_log"]}, indent=2))

        # Write models as pickle BLOBs
        if data.get("model"):
            zf.writestr("models/proxy_model.pickle", pickle.dumps(data["model"]))
        if data.get("recipient_model"):
            zf.writestr("models/recipient_model.pickle", pickle.dumps(data["recipient_model"]))

        # Write forecasts
        if data.get("forecast_horizons"):
            for h in (12, 26, 52):
                key = f"horizon_{h}w"
                if key in data["forecast_horizons"]:
                    zf.writestr(f"forecasts/{key}.pickle", pickle.dumps(data["forecast_horizons"][key]))

        # Manifest LAST (after all files written so we can compute hashes)
        manifest = build_manifest_from_zip(zf, project_id, now)
        zf.writestr("manifest.json", manifest.model_dump_json(indent=2))
```

In-app trigger: `AuroraBundle.load(path)` - if `detect_format(path) == "pickle_v2"`, call `migrate_pickle_to_zip()` to a sibling temp file, then load that. UI dialog informs user "Старый формат файла - конвертируем в новый." Backup of original pickle preserved as `.aurora.legacy_v2.bak`.

---

## Forward / Backwards Compat Matrix

| File created by | Opening app | Behavior |
|---|---|---|
| Econometrica v1.0.10+ (pickle v2) | Aurora Launch v1.4.0+ | Auto-migrate на first save (transparent UI dialog) |
| Aurora Launch v1.4.0+ (zip v3) | Aurora Launch v1.4.0+ | Native open |
| Aurora Launch v1.4.0+ (zip v3) | Aurora Econometrica v1.0.16 | Не открывается. Manifest min_app_version="1.4.0" → clear error "Обновите Econometrica до v1.4.0+" |
| Aurora Launch v1.4.0+ (zip v3) | Aurora Econometrica v1.4.0+ | Native open. Launch fields (proxy_brand_metadata, recipient_anchors, transfer_provenance) ignored if Econometrica UI не показывает их |
| Aurora Launch v1.5.0+ (zip v4 future) | Aurora Launch v1.4.0 | Manifest min_app_version="1.5.0" → clear error suggested_action="update_app" |

---

## Backup Strategy

**Rolling 4 backups per project:**
- `.aurora.bak.1` - last save before current
- `.aurora.bak.2` - prior save
- `.aurora.bak.3` - prior to that
- `.aurora.bak.4` - oldest retained

**Rotation triggered on every successful atomic save.**

**Manual snapshot:** UI offers "Save snapshot" button → creates `.aurora.snapshot_YYYY-MM-DD_HH-MM.bak` (никогда не rotated, manual cleanup).

**Recovery UI:** "Восстановить из backup" в File menu → list of `.bak.N` + snapshots с timestamps + size.

---

## Concurrency

**Phase B scope:** single-user. File lock через `.aurora.lock` sentinel:
- On open: check if `.aurora.lock` exists. If yes, и timestamp recent (< 5 min) → warn user "Project уже открыт другим процессом". User confirms force-open → existing lock removed.
- On close: lock removed.
- Lock file contains: PID + hostname + timestamp.

**Phase D consideration:** true multi-user через Phase D feature (out of S005a scope).

---

## File Size Limits

- **Practical typical:** 10-50 MB per project (mostly trained models pickle).
- **Upper bound expected:** ~500 MB (multi-proxy hierarchical с 3 proxies + extensive scenario cache).
- **Hard limit:** ZIP supports 4 GB single file (ZIP64 для larger). Aurora targets ≤500 MB; larger требует Phase D investigation.

**Atomic save peak disk usage:** 2x bundle size (original + .aurora.tmp during save). Monitored для 500 MB upper bound.

---

## Performance Budgets

| Operation | Target | Rationale |
|---|---|---|
| Open small project (10 MB) | ≤50 ms | Read manifest only, lazy load |
| Open large project (200 MB) | ≤200 ms | Manifest first, models on demand |
| Save small project | ≤100 ms | Manifest update + atomic rename |
| Save large project | ≤2 s | Write modified files + manifest + atomic rename |
| Integrity verification (full SHA-256 на 50 MB) | ≤500 ms | Optional, controlled by manifest setting |
| Migration pickle v2 → zip v3 | ≤5 s per 100 MB | One-time per legacy file |

---

## Testing Strategy (Sprint B1)

**Unit tests:** `tests/unit/test_aurora_bundle.py`
- Round-trip: save + reload, structured fields equal, models equal (pickle hash)
- Atomic save: kill mid-save (Ctrl+C / process kill simulation) - original file uncorrupted, .tmp cleaned up next open
- Integrity: corrupt one byte in models/proxy_model.pickle, integrity_check=strict raises, =warn logs only, =disabled passes
- Lazy loading: open large bundle, only read manifest + metadata, не unpickle models (verify zipfile.read called only for accessed files)

**Migration tests:** `tests/integration/test_pickle_to_zip_migration.py`
- 10+ Econometrica .aurora projects from B0.5 BC corpus
- Migrate каждый через `migrate_pickle_to_zip()`, verify все math fields preserved (model parameters bit-identical после repickle)
- Verify all metadata fields populated correctly

**Property-based tests:**
- Fuzz manifest.json (invalid JSON, missing fields, hash mismatches) - all caught with clear errors
- Random ZIP corruption - graceful failure with backup recovery suggestion

**End-to-end tests (Sprint B6):**
- Create project в Aurora Launch → save .aurora → open в Aurora Econometrica v1.4.0 (cross-app open)
- Verify backwards compat (Launch fields visible или gracefully ignored в Econometrica)

---

## Implementation Files (Sprint B1)

**New files:**
- `engines/aurora_bundle.py` - AuroraBundle class
- `engines/manifest.py` - Manifest Pydantic model + helpers
- `tools/migrate_aurora_pickle_to_zip.py` - migration utility (CLI + library)

**Extended files:**
- `engines/schema_registry.py` - add migration handlers для bundle format
- `engines/launch_schema.py` - reuse Pydantic models in JSON serialization

**Tests:**
- `tests/unit/test_aurora_bundle.py`
- `tests/unit/test_manifest.py`
- `tests/integration/test_pickle_to_zip_migration.py`

**Documentation:**
- This file (SCHEMA_DESIGN.md) - finalized
- `decisions/ADR-002-storage-layer.md` - decision authority
- `00_Overview/ROADMAP.md` Sprint B1 - reference этот файл

---

## Cross-app Coordination

**Aurora Econometrica future migration (Phase D, tentative):**
- Phase D candidate: wrap existing v2 pickle в ZIP container с manifest + metadata.json, math pipeline unchanged
- `tools/migrate_aurora_pickle_to_zip.py` reused as-is
- Aurora Econometrica `aurora_bundle.py` import from `aurora-platform-core` package

**Aurora Optimize / Brand:**
- Adopt тот же pattern из start (Phase B / C)
- No divergent storage decisions across Suite

**Phase A platform-core (`aurora-platform-core` package):**
- Expose `AuroraBundle` + `Manifest` + `SchemaRegistry` as public API
- All Suite apps inherit one storage layer

---

## Связанные документы

- `decisions/ADR-002-storage-layer.md` - decision authority (this document implements)
- `REUSE_FROM_ECONOMETRICA.md` - SchemaRegistry pattern + BFS migration path
- `decisions/ADR-001-consulting-hours-persistence.md` - consulting hours separate concern (local SQLite DB, not bundle)
- `../02_Data_Spec/DATA_REQUIREMENTS.md` - Pydantic models которые сериализуем в JSON
- `../02_Data_Spec/recipient_anchors_v1.schema.json` - JSON Schema SSoT для recipient_anchors.json
- `../05_Sessions/SESSION_NEXT_QUESTIONS.md` - S005a closed reference
- Memory: `project_econometrica_v1_2_0_foundation_2026_04_28.md` - Econometrica v2 pickle baseline
- Memory: `project_aurora_launch_principles.md` - P9 reuse + P10 inspectability + DPA
