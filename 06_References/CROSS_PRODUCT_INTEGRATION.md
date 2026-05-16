# Cross-Product Integration: Launch Planner ↔ MMM Optimizer

**ROADMAP §3.4** — Перекрёстная сверка между Launch Planner и Optimizer (30ч)

Status: **Skeleton shipped** (2026-05-16). Mock + Local adapter ready. Cloud deferred.

---

## Overview

Aurora Launch Planner forecasts a new brand's launch trajectory using a **proxy brand**
(an existing brand with similar category/pricing/media profile). When the client also
runs **Aurora MMM Optimizer** with real historical data for that same proxy brand,
Launch can calibrate its forecast against reality:

> "Our forecast says the proxy brand should yield ~48 000 units/week over 12 weeks.
> Optimizer actuals show it realized 45 000 units/week. Deviation: +6.7% (low).
> Your forecast is well-calibrated."

This cross-product validation increases trust in the Launch forecast and surfaces
model assumptions that diverge from market reality.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│           Aurora Launch Planner             │
│                                             │
│  validate_against_optimizer (sidecar RPC)   │
│         │                                   │
│         ▼                                   │
│   ServiceContainer.optimizer_client         │
│         │                                   │
│    ┌────┴──────────────────────┐            │
│    │      OptimizerClient      │            │
│    │   (abstract base class)   │            │
│    └────┬──────────┬───────────┘            │
│         │          │                        │
│  MockOptimizer  LocalOptimizer              │
│  (tests/demo)   (same machine)              │
│                      │                      │
└──────────────────────┼──────────────────────┘
                       │ reads SQLite
┌──────────────────────┼──────────────────────┐
│     Aurora MMM Optimizer (separate app)     │
│                      │                      │
│   aurora-econometrica-gui.db                │
└─────────────────────────────────────────────┘
```

### Key files

| File | Role |
|------|------|
| `src/aurora_launch/schemas/cross_product.py` | Pydantic v2 contract schemas |
| `src/aurora_launch/services/optimizer_client.py` | OptimizerClient ABC + Mock + Local skeleton |
| `src/aurora_launch/sidecar/services.py` | DI container slot `optimizer_client` |
| `src/aurora_launch/sidecar/methods.py` | `validate_against_optimizer` JSON-RPC handler |
| `tests/test_cross_product_validation.py` | 18 tests covering schemas + mock + method |

---

## What Launch Planner Consumes from Optimizer

### API Contract (OptimizerClient ABC)

Launch needs exactly two operations from Optimizer:

#### 1. list_projects() → list[OptimizerProjectRef]

Returns all Optimizer projects accessible to this client. Each project ref contains:

```python
OptimizerProjectRef:
    project_uuid: UUID           # Stable identifier for the Optimizer project
    brand_code: str              # Matches proxy brand_code in Launch bundle
    granularity: "weekly" | "monthly"
    last_modified: date          # For cache invalidation
```

#### 2. get_history(query) → OptimizerHistoryResponse | None

Returns realized weekly (or monthly) actuals for the specified brand. Returns `None`
when the brand is not found in any accessible project (not an error).

```python
OptimizerHistoryQuery:
    brand_code: str              # Proxy brand to look up
    period_start: date           # Inclusive
    period_end: date             # Inclusive
    channels: list[str] | None   # Optional: per-channel spend breakdown

OptimizerHistoryResponse:
    brand_code: str
    weekly_actuals: list[WeeklyActual]
    n_observations: int          # == len(weekly_actuals)
    granularity: "weekly" | "monthly"

WeeklyActual:
    week_index: int              # 0-based from project start
    sales: float                 # Realized sales (units or revenue)
    spend_per_channel: dict[str, float]  # Empty if channels not requested
```

### CrossProductValidation (result)

```python
CrossProductValidation:
    proxy_brand: str
    launch_forecast_value: float   # From Launch forecast (same units as Optimizer)
    optimizer_actual_value: float  # Mean actuals over comparison window
    deviation_pct: float           # (launch - actual) / actual * 100
    deviation_severity: "low" | "medium" | "high"
    confidence: float              # [0.0, 1.0]
```

Severity thresholds:
- **low**: `|deviation_pct| < 15%` — green badge "Proxy validates forecast"
- **medium**: `15% ≤ |deviation_pct| < 35%` — amber badge "Moderate calibration gap"
- **high**: `|deviation_pct| ≥ 35%` — red badge "Large calibration gap — review assumptions"

Confidence calculation:
- `n_observations ≥ horizon_weeks` → 1.0
- `n_observations < 4` → 0.3
- Otherwise: linear interpolation between 0.3 and 1.0

---

## What Optimizer Must Export (for Маша небесная as Optimizer owner)

To enable `LocalOptimizerClient` (same-machine integration), Optimizer must:

### 1. Expose a SQLite DB at a known path

The DB file must be at `%APPDATA%\aurora-econometrica-gui\aurora-econometrica-gui.db`
(Windows) or the path pointed to by env var `AURORA_OPTIMIZER_DB_PATH`.

The `aurora-econometrica-gui` name is the Cargo binary name (see
`feedback_aurora_appdata_identifier.md`), not the Tauri bundle ID.

### 2. Expose a `projects` table

Minimum required columns:

```sql
CREATE TABLE projects (
    project_id   TEXT PRIMARY KEY,   -- UUID as text
    brand_code   TEXT NOT NULL,      -- Matches Launch proxy brand_code
    granularity  TEXT NOT NULL,      -- 'weekly' or 'monthly'
    updated_at   TEXT NOT NULL       -- ISO-8601 datetime
);
```

### 3. Expose a `weekly_actuals` table

```sql
CREATE TABLE weekly_actuals (
    project_id   TEXT NOT NULL REFERENCES projects(project_id),
    brand_code   TEXT NOT NULL,
    week_index   INTEGER NOT NULL,   -- 0-based from project start
    sales        REAL NOT NULL,
    channel_json TEXT,               -- JSON object {"tv": 1234.5, ...} or NULL
    PRIMARY KEY (project_id, brand_code, week_index)
);
```

### 4. Permission model

- Launch reads Optimizer DB **read-only** (`PRAGMA query_only = ON`).
- No write access required from Launch to Optimizer DB.
- Both apps run under the same Windows user — no auth needed for local SQLite.
- Multi-user / cloud scenario: deferred to cloud-wave (see §Future Work).

### 5. brand_code matching convention

The `brand_code` field must use the same identifier as the proxy brand in the Launch
bundle (`ProxyBrandMetadata.brand_code`). Recommended: lowercase, underscored
normalized name (e.g., `"kagotsel"`, `"venarus"`, `"mmx_afala"`).

---

## Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| Pydantic schemas (`cross_product.py`) | Shipped | Frozen, extra=forbid |
| `MockOptimizerClient` | Shipped | 18 tests passing |
| `LocalOptimizerClient` constructor | Shipped | Raises `OptimizerNotConfigured` if env var absent |
| `LocalOptimizerClient.list_projects()` | Skeleton | `NotImplementedError` — Optimizer DB schema TBD |
| `LocalOptimizerClient.get_history()` | Skeleton | `NotImplementedError` — Optimizer DB schema TBD |
| `validate_against_optimizer` sidecar method | Shipped | Graceful degradation when client=None |
| DI slot `optimizer_client` in `ServiceContainer` | Shipped | `get_optimizer_client()` / `set_optimizer_client()` |
| HTTP/gRPC client | Deferred | Cloud-wave |
| Frontend UI (calibration badge) | Deferred | After Optimizer DB contract finalized |

---

## Example: UI Usage (when integration is available)

When the user has both Launch Planner and Optimizer on the same machine
with `AURORA_OPTIMIZER_DB_PATH` configured:

1. User opens Launch Planner, selects proxy brand "Кагоцел" (brand_code=`kagotsel`).
2. Frontend calls `validate_against_optimizer` via IPC:
   ```json
   {
     "launch_forecast_value": 48000,
     "proxy_brand_code": "kagotsel",
     "horizon_weeks": 12
   }
   ```
3. Sidecar reads Optimizer DB → returns:
   ```json
   {
     "available": true,
     "proxy_brand": "kagotsel",
     "launch_forecast_value": 48000,
     "optimizer_actual_value": 45230.5,
     "deviation_pct": 6.12,
     "deviation_severity": "low",
     "confidence": 1.0
   }
   ```
4. Frontend renders a green badge:
   > "Прокси-бренд проверен: фактические продажи Кагоцела совпадают с прогнозом
   > (расхождение +6.1%). Доверие к прогнозу подтверждено."

When Optimizer is not installed / not configured:
- Sidecar returns `{"available": false, "reason": "optimizer_not_configured"}`
- Frontend hides the calibration section entirely (no error shown to user).

---

## Future Work

- **Finalize LocalOptimizerClient SQL queries** once Optimizer publishes DB schema.
  Owner: Маша небесная (Optimizer) + Маша маленькая (Launch) pair-review.
- **Frontend calibration badge** in Wizard Step 5 (forecast review screen).
- **HTTP client** for cloud scenario (multi-user, Optimizer on separate machine).
  Tracked as backlog item post-cloud-wave.
- **Similarity-weighted confidence**: incorporate `SimilarityDimensionScores`
  from Launch bundle into confidence formula (currently only n_observations-based).
- **brand_code normalization**: shared utility function to ensure Launch proxy
  brand_code matches Optimizer brand_code (handle case/diacritic differences).
