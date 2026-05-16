# Auto-Refresh Forecast Setup (ROADMAP §3.5)

## Overview

Aurora Launch can detect when new XLSX data files appear in a configured local
folder and prompt the user to re-run the forecast. No data leaves the user's
machine; the watcher reads only filesystem modification times (mtime).

## Architecture

```
Frontend (RefreshAvailableBanner)
  onMount → ipc.getRefreshConsent()         -- check opt-in state
  if consent.enabled → ipc.checkDataSourceUpdates(projectUuid, sources)
    → Rust passthrough → Python sidecar
      → DataSourceWatcher.check_for_updates()
          → _scan_folder_max_mtime(Path)    -- read mtime, no file content
          → compare with last_modified_seen
          → return RefreshTrigger[] if new files found

User clicks "Refresh now"
  → window.dispatchEvent('aurora:refresh-forecast')
  → Inspector / project list can subscribe and trigger re-forecast
  → ipc.dismissRefreshTrigger(projectUuid) -- suppress for this session
```

## 152-FZ / PDPL Compliance

The feature is opt-in under Federal Law 152-FZ (Personal Data Protection):

- **No consent = no action.** `ConsentManager.get()` returns `null` on first
  run. The banner shows an explanation and asks for explicit opt-in.
- **Consent is revocable.** Settings page includes a toggle that calls
  `set_refresh_consent({enabled: false})`. The banner also has "Never ask".
- **No network access.** Watcher reads only local `mtime` via `pathlib.Path.stat()`.
  No file content is read; no data is sent anywhere.
- **Audit trail.** `RefreshConsentSetting.last_prompted_at` records when the
  user was last shown the dialog (ISO-8601 UTC, stored in ProjectDB KV store).

## Customer Setup

### Step 1: Enable in Settings

Navigate to Settings → "Автообновление прогнозов" and enable the toggle.
Choose check frequency (daily / weekly / monthly).

### Step 2: Configure Watched Folders

Currently the watcher is configured programmatically via `DataSourceConfig`:

```python
from aurora_launch.schemas.auto_refresh import DataSourceConfig
from aurora_launch.engines.data_source_watcher import DataSourceWatcher

cfg = DataSourceConfig(
    source_kind="dsm_xlsx_folder",       # or "mediascope_xlsx_folder"
    path=r"C:\Users\analyst\Downloads\DSM_exports",
)
watcher = DataSourceWatcher(project_uuid="your-project-uuid", db=project_db)
watcher.register_source(cfg)
triggers = watcher.check_for_updates()   # [] on first run (baseline set)
```

On subsequent runs, any `.xlsx` / `.xls` file with `mtime` after the baseline
will generate a `RefreshTrigger`.

**Note:** UI for folder path configuration is deferred to a future phase. For
Materia Medica pilot: configure path in code or via settings JSON override.

## Source Kinds

| `source_kind` | Description | Path required |
|---|---|---|
| `dsm_xlsx_folder` | Watches a folder for DSM XLSX exports | Yes |
| `mediascope_xlsx_folder` | Watches a folder for Mediascope XLSX exports | Yes |
| `manual` | Customer imports manually via Wizard; never auto-triggers | No |

## Deferred: DSM / Mediascope Real API Integration

When Materia Medica or a future client provides API credentials:

1. **Implement adapter class** (e.g., `DsmApiAdapter`) with method
   `get_latest_export() -> Optional[bytes]` + `get_export_mtime() -> datetime`.
2. **Add new `source_kind`** values: `"dsm_api"`, `"mediascope_api"`.
3. **Register in `DataSourceWatcher._check_source()`** routing switch.
4. **No changes** to `ConsentManager`, schemas, or sidecar methods needed.

Required from DSM:
- REST/SOAP endpoint for data export download
- Auth token / certificate
- Method to query `last_modified` without downloading full file (HEAD or metadata call)

Required from Mediascope:
- SOAP or REST API with export-by-date-range
- `Content-Last-Modified` or equivalent metadata field

## Testing

```bash
# Python unit tests
.venv/Scripts/python.exe -m pytest tests/test_data_source_watcher.py tests/test_auto_refresh_consent.py -v

# Frontend unit tests
cd frontend && npx vitest run tests/unit/RefreshAvailableBanner.test.ts
```

## File Inventory

| File | Purpose |
|---|---|
| `src/aurora_launch/schemas/auto_refresh.py` | Pydantic schemas |
| `src/aurora_launch/engines/data_source_watcher.py` | Watcher logic + ConsentManager |
| `src/aurora_launch/sidecar/methods.py` | 4 sidecar IPC methods |
| `frontend/src/lib/components/RefreshAvailableBanner.svelte` | UI banner |
| `frontend/src/lib/ipc/client.ts` | Typed IPC wrappers |
| `frontend/src/routes/settings/+page.svelte` | Settings section |
| `frontend/src/lib/i18n/locales/{ru,en}.json` | i18n keys |
| `tests/test_data_source_watcher.py` | 12 Python tests |
| `tests/test_auto_refresh_consent.py` | 7 Python tests |
| `frontend/tests/unit/RefreshAvailableBanner.test.ts` | 7 TS tests |
