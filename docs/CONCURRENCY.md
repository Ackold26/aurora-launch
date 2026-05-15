# Aurora Launch Planner — Concurrency Model

## Threads in sidecar process

The sidecar (`aurora_launch.sidecar`) runs a single OS process. All threads below
are **daemon threads** — they exit automatically when the main process exits.
Explicit cleanup is performed by the `shutdown` IPC handler.

---

### 1. aurora-forecast-{handle[:8]}  (Phase 4)

**Purpose:** runs LaunchOrchestrator forecast computation in background so the
IPC loop remains non-blocking.

**Spawn:** `start_forecast` IPC handler. One thread per active forecast handle.

**Cancel:** cooperative via `_cancel_flags[handle]` (`threading.Event`). The
sampler checks `cancel.is_set()` at each period boundary. No SIGINT / terminate.

**Cleanup:** `finally` block in runner removes entry from `_forecast_threads` and
`_cancel_flags`. `shutdown` handler drains all active forecast threads
(signals all + join with 5s per-thread timeout).

**Registry:** `_forecast_threads: dict[str, Thread]`, `_cancel_flags: dict[str, Event]`

---

### 2. aurora-gc-periodic  (S-07)

**Purpose:** checks every hour whether `gc_orphan_blobs()` should run (7-day
interval). Avoids accumulating orphan blobs in long-running sidecar sessions.

**Spawn:** `_start_gc_thread()` called from `_get_project_db()` on first
ProjectDB initialisation. Exactly one thread per process lifetime (double-checked
locking in `_GC_THREAD_LOCK`).

**Poll interval:** `GC_POLL_INTERVAL_S = 3600` (1 hour). Sleeps in 60-second
slices so the stop event is honoured quickly on shutdown.

**GC threshold:** `GC_INTERVAL_S = 7 * 24 * 3600` (7 days). Reads
`gc_metadata.last_gc_ran_at` from DB on each poll wake; runs GC only if
threshold exceeded.

**Cancel:** `_GC_STOP_EVENT` (`threading.Event`) set by `shutdown` handler.
Thread body exits on next 60-second slice boundary.

**Startup-time GC:** `ProjectDB._maybe_gc_on_open()` also runs `gc_orphan_blobs`
synchronously on DB open if `last_gc_ran_at` is NULL or older than 7 days. This
covers the common case of the sidecar restarting after a week.

**Registry:** `_GC_THREAD: Thread | None`, `_GC_THREAD_LOCK`, `_GC_STOP_EVENT`

---

### 3. aurora-integrity-{handle[:8]}  (S-08)

**Purpose:** runs `ProjectDB.check_integrity()` in background. For large DBs
the blob filesystem walk + ref-count SQL query can take seconds; offloading
keeps the IPC loop free.

**Spawn:** `start_integrity_check` IPC handler. One thread per active check.

**Events emitted:**
- `integrity_check_progress` — emitted at "starting" and "scanning" phases with
  a `phase` + `detail` field for UI display.
- `integrity_check_completed` — emitted on success with full `report` dict:
  `{missing_blobs, orphan_files, dangling_refs, ref_count_drift}` (all `list[str]`).
- `integrity_check_cancelled` — emitted if cancel flag was set before/during run.
- `integrity_check_failed` — emitted on unexpected exception with `error` + `kind`.

**Cancel:** cooperative via `_integrity_cancel_flags[handle]` (`threading.Event`).
Checked at three points: before DB acquire, after DB acquire, after scan. Mirror
of forecast cancel pattern (D5: no SIGINT, no terminate).

**Cleanup:** `finally` block in runner removes entries from `_integrity_threads`
and `_integrity_cancel_flags`. `shutdown` handler signals all active integrity
threads and joins them (same 5s timeout as forecasts).

**Registry:** `_integrity_threads: dict[str, Thread]`, `_integrity_cancel_flags: dict[str, Event]`

---

## Shared stdout serialisation

All thread-originated `events.emit()` calls share a single `threading.Lock` in
`aurora_launch.sidecar.events` (`_lock`). This prevents byte-interleaving between
concurrent event emitters (forecast + integrity check + GC log lines) and
synchronous RPC responses. Every write goes through `events.write_line()`.

---

## S-14 RACI matrix — concurrency ownership

Per-resource Responsible/Accountable/Consulted/Informed roles.
R = Responsible (does the work). A = Accountable (single owner).
C = Consulted (must be consulted). I = Informed (notified).

| Resource / Decision | Main RPC thread | Forecast thread | GC thread | Integrity thread | Notes |
|---|---|---|---|---|---|
| projects.db (writes) | R/A | — | R (gc_metadata only) | — | GC writes single row; safe via WAL |
| projects.db (reads) | R/A | R (pre-load only) | C | R (PRAGMA integrity_check) | WAL allows concurrent readers |
| Blob filesystem (writes) | R/A | — | R (orphan delete) | — | GC + main both write but не overlap |
| Blob filesystem (reads) | R/A | — | C | R | Integrity walks fs |
| stdout (events.emit) | R | R | R | R | Shared `events._lock` mutex |
| stderr (logging) | R | R | R | R | Python logging thread-safe |
| _forecast_threads dict | R/A | C (own entry cleanup) | I | I | Main writes; threads remove own на exit |
| _integrity_threads dict | R/A | I | I | C (own entry cleanup) | Same pattern |
| _GC_THREAD singleton | R/A | I | C | I | Created once at first ProjectDB init |
| _PROJECT_DB singleton | R/A | I | C | C | Double-checked locking |
| _AUTOSAVE singleton | R/A | I | I | I | SIGTERM handler self-registered |
| sidecar shutdown protocol | A/R | I | I | I | Drains all threads с 5-10s timeout |
| ProxyBundle (frozen dataclass) | R | R (read-only) | I | I | Immutable — no concurrency concerns |
| dispatch_table (engine routing) | R | C | I | I | Pure function lookup, thread-safe |

**Cross-cutting invariants:**
- No thread acquires more than one mutex simultaneously (no deadlock topology).
- All event emission goes through `events.write_line()` под shared lock.
- All cancel flags use `threading.Event` (atomic set/clear). No volatile booleans.
- Shutdown drain is the only place we `join()` other threads — никогда mid-flight.

**Out of scope (future):**
- Cross-process locking (multiple Aurora app instances on same machine): handled by `process_lock.py` (S-04 advisory `.lock` file). Not represented in this matrix because cross-process resources (file locks on disk) live above thread layer.
- Distributed concurrency (cloud sync, KMS signing): Phase Cloud — separate document.

---

## ProjectDB thread safety

`ProjectDB` is **not thread-safe**: a single `sqlite3.Connection` is used per
instance, and SQLite's `check_same_thread` is disabled (isolation_level=None,
WAL mode). The sidecar enforces:

- All **write** operations (save_version, delete_project, gc_orphan_blobs,
  _update_gc_metadata) are called from the **main RPC thread** or from GC thread
  (which acquires no user-visible mutex — GC runs infrequently and serially).
- `check_integrity()` is **read-only** (no INSERTs/UPDATEs) and is safe to call
  from the integrity background thread in WAL mode (concurrent readers allowed).
- sqlite3 connection objects must **never cross thread boundaries** for write
  paths. `start_forecast` pre-loads all DB data in the main thread before
  spawning the runner thread (see `_load_project_forecast_data`).
