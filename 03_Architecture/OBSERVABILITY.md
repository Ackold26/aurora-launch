# Aurora Launch - Observability Strategy

**Status:** v1.0 (2026-05-04)
**Authority:** Audit enhancement E9

## Контекст

Premium product требует observability для:
- Performance regression early warning
- Error pattern recognition (bug pre-detection)
- Customer success insights (without violating privacy)
- Product analytics (что работает, что не)

**Key constraint (P14 local-first):** observability должна быть **opt-in** + **no raw client data**. Только aggregates + counts + timings.

---

## 1. Observability Tiers

### Tier 1: Local Debug Logs (always-on, local only)

- File: `%LOCALAPPDATA%\Aurora Launch\logs\aurora-launch.log`
- Rolling files (last 7 days, max 100MB total)
- Stored locally, never sent to cloud
- Used for client-supported troubleshooting (client emails log на request)

**Format (structured JSON Lines):**
```json
{"ts":"2026-05-04T14:23:45Z","level":"INFO","module":"launch_adapt","msg":"extract_proxy_priors","duration_ms":423,"channels":5}
```

**Sensitive data scrubbed:**
- Brand names → "BRAND_<hash6>"
- Specific values → ranges (e.g., budget_rub > 1M_class)
- File paths → relative

### Tier 2: Local Metrics (always-on, local only)

SQLite metrics database `%LOCALAPPDATA%\Aurora Launch\metrics.db`:
```sql
CREATE TABLE operation_metrics (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    operation_name TEXT,        -- e.g., "single_proxy_train"
    duration_ms INTEGER,
    memory_peak_mb INTEGER,
    success BOOLEAN,
    error_type TEXT NULL,        -- if not success
    metadata_json TEXT           -- aggregate counts only
);

CREATE INDEX idx_op_ts ON operation_metrics(operation_name, timestamp);
```

**Used by:**
- Performance regression detection (compare to baseline)
- Time estimation (predict next operation duration)
- "Why slow today?" troubleshooting

### Tier 3: Cloud Telemetry (opt-in)

User enables в Settings → Privacy → "Share aggregate usage analytics".

**What's sent:**
- Operation timings (operation_name + duration_ms histograms, anonymous)
- Error type counts (no stack traces with values)
- Feature usage (which workflows used, frequency)
- Aurora Launch version + Windows version
- License key hash (для group по customer без identification)

**What's NEVER sent:**
- Brand names
- Recipient anchor values (specific numbers)
- Forecast outputs
- File paths
- User identity beyond license hash

**Aggregation:**
- Min batch: 24h, send daily
- Privacy: k-anonymity (≥ 5 customers) before aggregate is public

### Tier 4: Performance Regression Detection (CI-side)

Не client-side. CI runs benchmark suite per PR (см. PERFORMANCE_BUDGETS.md Section 3).

---

## 2. Metrics Catalog

### 2.1 Operation Metrics

| Metric | Description | Tags |
|---|---|---|
| `aurora.launch.operation.duration_ms` | Histogram - operation duration | operation_name, success |
| `aurora.launch.operation.memory_peak_mb` | Memory at peak | operation_name |
| `aurora.launch.error.count` | Errors by type | error_type, operation_name |
| `aurora.launch.feature.used` | Feature usage counter | feature_name |

### 2.2 Workflow Metrics

| Metric | Description |
|---|---|
| `aurora.launch.session.start` | App opened |
| `aurora.launch.project.created` | New project |
| `aurora.launch.project.opened` | Existing project loaded |
| `aurora.launch.proxy.selected` | Proxy chosen |
| `aurora.launch.anchors.completed` | Anchors form submitted |
| `aurora.launch.transfer.validated` | Transfer validation pass |
| `aurora.launch.train.completed` | Model trained |
| `aurora.launch.forecast.generated` | Forecast output |
| `aurora.launch.report.exported` | Report (PPTX/HTML/XLSX) generated |
| `aurora.launch.posterior.updated` | Posterior update applied |

### 2.3 Quality Metrics

| Metric | Description |
|---|---|
| `aurora.launch.similarity.score` | Histogram - similarity scores (anonymous) |
| `aurora.launch.tier.distribution` | Counter - High/Medium/Low/Insufficient verdict |
| `aurora.launch.convergence.r_hat` | Histogram - R-hat values per training |
| `aurora.launch.convergence.divergences` | Counter - divergences encountered |

### 2.4 Performance Budgets

Auto-track через performance budget tests (см. PERFORMANCE_BUDGETS.md). On budget violation:
- Local log warning
- Telemetry (opt-in)
- Possible rollback if regression in production

---

## 3. Error Tracking

### Error Categories

```python
class ErrorCategory(str, Enum):
    DATA_VALIDATION = "data_validation"      # invalid DSM/MS/anchors data
    SCHEMA_INCOMPATIBILITY = "schema_incompatibility"  # старая Aurora не open new schema
    MODEL_CONVERGENCE = "model_convergence"  # MCMC failed to converge
    TRANSFER_INSUFFICIENT = "transfer_insufficient"  # similarity below threshold
    NETWORK = "network"                      # license validation, updates
    LICENSE = "license"                      # expired, invalid, exceeded
    DEPENDENCY = "dependency"                # missing WebView2, JAX failure, etc.
    INTERNAL = "internal"                    # bugs - high priority alerts
```

### Error Handling Flow

```
Error occurs
    ↓
Local log entry (Tier 1)
    ↓
Local metric increment (Tier 2)
    ↓
User-facing error message (sanitized)
    ↓
If telemetry opt-in:
    Send error type + frequency к Aurora cloud (Tier 3)
    Aggregate alerts если threshold exceeded
```

### User-Facing Error Messages

**Bad (current pattern):**
```
ValidationError: market_size_rub must be > 0
```

**Better (Aurora style):**
```
Размер рынка должен быть положительным числом (например 5,000,000,000 ₽).
Проверьте поле "Размер рынка" в форме anchors.
[Перейти к полю]
```

Error registry в `engines/error_messages.py` с Russian-localized strings + actionable suggestions.

---

## 4. Distributed Tracing (Phase D consideration)

OpenTelemetry trace context propagation:
- Aurora Launch UI (Tauri webview) → backend (Python sidecar)
- Span hierarchy для long workflows (proxy_select → adapt → train → forecast)
- Trace ID отображается в error reports для support

**Not implemented Phase B** - operational complexity без clear customer value yet. Reconsider Phase D.

---

## 5. Health Checks

### Local Health Endpoint

`GET http://localhost:5180/health` (Tauri sidecar):
```json
{
  "status": "healthy",
  "version": "1.4.0",
  "uptime_seconds": 1234,
  "components": {
    "modeler": "ok",
    "data_studio": "ok",
    "license_validator": "ok"
  },
  "last_train_seconds_ago": 567,
  "memory_rss_mb": 384
}
```

Used by:
- Aurora Launch UI heartbeat (detect sidecar crashed)
- Auto-recovery (restart sidecar if unhealthy)

### Cloud Health Dashboard (Phase C+, public)

URL: `auroraai.pro/status/launch` (после Phase C):
- Aurora Launch services status
- License validation latency
- Update channel availability
- Public incidents

Trust signal через transparency. Differentiator vs Nielsen / Kantar (closed status).

---

## 6. Privacy Policy (telemetry section)

В public privacy policy + Settings → Privacy modal explanation:

> Aurora Launch может собирать **только** anonymous performance metrics с вашего согласия.
>
> **Что мы собираем (если включено):**
> - Время выполнения операций (training, forecast, etc.)
> - Типы возникших ошибок (без detail)
> - Версия приложения и Windows
> - Использование функций (какие workflows использованы)
>
> **Что мы НЕ собираем:**
> - Названия брендов
> - Значения anchor data
> - Forecast результаты
> - Содержимое .aurora файлов
> - Имена файлов / пути
>
> Данные передаются раз в день в зашифрованном виде. Включается / выключается в Settings → Privacy.

---

## 7. Per-Sprint Observability Deliverables

| Sprint | Deliverable |
|---|---|
| B0 | OBSERVABILITY.md (this doc) |
| B0.5 | Local logging framework setup |
| B1 | Schema migration metrics (success/fail counters) |
| B1.5 | Consulting hours metrics |
| B2 | Proxy validation metrics |
| B3 | Adapt + transfer metrics |
| B4 | Forecast generation metrics |
| B5 | Posterior update metrics |
| B6 | Error message registry, performance regression tests, opt-in telemetry framework |

---

## 8. Tools & Libraries

| Layer | Tool | Notes |
|---|---|---|
| Python logging | `structlog` | JSON Lines, structured |
| Metrics SQLite | Stdlib `sqlite3` | Simple, no deps |
| Performance | `time.perf_counter` + benchmarking suite | Already used Aurora Econometrica |
| Frontend perf | Performance API (built-in) | No deps |
| OpenTelemetry | `opentelemetry-api` (Phase D consideration) | Not Phase B |
| Cloud aggregation | TBD (custom endpoint or Posthog/Plausible) | Phase C decision |

---

## Связанные документы

- `PERFORMANCE_BUDGETS.md` - performance test infrastructure
- `DATA_PRIVACY.md` - privacy constraints
- `THREAT_MODEL.md` - security context
- `decisions/` - ADRs для observability tooling
