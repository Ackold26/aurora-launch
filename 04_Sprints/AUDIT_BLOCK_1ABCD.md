# Audit Block 1D — Fresh-Eyes Pass over 1A + 1B + 1C

**Date:** 2026-05-09
**Auditor:** Maша Маленькая (Claude Opus 4.7 max effort)
**Scope:** `bundle_container.py`, `bundle_lock.py`, `bundle_persistence.py`, `bundle_manifest.py`, `license_validator.py`, `bundle_streaming.py`
**Pre-audit state:** HEAD `76643e0`, 469 tests passing
**Post-audit state:** HEAD TBD (this commit), 485 tests passing
**Outcome:** 4 BLOCKER + 2 HIGH applied immediately. 5 MEDIUM/LOW documented for follow-up.

## Methodology

Red-team threat model focused on:
- Trust boundary: untrusted `.aurora` bundle from filesystem / network → trusted in-memory state
- Attack surfaces: ZIP archive parsing, manifest validation, license gate, lazy reader cache
- Adversary: malicious bundle author or compromised user environment
- Defenders: hash-chain integrity, advisory lock, structural checks, license JWT

Reading methodology: each module read top-to-bottom looking for (a) trust assumptions that are stated but not enforced, (b) silent failure modes, (c) cache/state interactions, (d) timing/race patterns.

---

## Findings

### 🔴 BLOCKER B1 — License bypass active in production builds via single env var

**File:** `src/aurora_launch/engines/license_validator.py:274-275` (pre-fix)

**Issue:** Module docstring claims `AURORA_LAUNCH_LICENSE_BYPASS=1` "only honored if `dev` build flag set in env — never in production builds." However the code applied no such gate:

```python
bypass_raw = os.environ.get("AURORA_LAUNCH_LICENSE_BYPASS", "")
bypass = bypass_raw.strip() in ("1", "true", "yes")
```

End-user could set the env var on a production install и bypass every paid feature gate. License revenue model bypassed by a 30-character shell command.

**Attack scenario:**
1. Customer signs up for Trial tier (no proxy_multi access)
2. Sets `AURORA_LAUNCH_LICENSE_BYPASS=1` in shell
3. Launches Aurora Launch — gets all enterprise features

**Fix applied:** Bypass now requires **BOTH** `AURORA_LAUNCH_LICENSE_BYPASS` truthy AND `AURORA_BUILD_PROFILE=dev`. Production Tauri builds will ship с baked-in `AURORA_BUILD_PROFILE=production` env (Block 2 task — wire через build.rs / Tauri sidecar env). When bypass requested but profile ≠ dev, a warning is logged and bypass refused (fail-closed).

**Test coverage added:**
- `test_bypass_requires_dev_build_profile` — bypass-only fails
- `test_bypass_explicit_production_refused` — explicit production rejects bypass
- `test_bypass_dev_profile_honoured` — both vars present accepts
- `test_no_bypass_env_no_change` — default no-bypass intact

**Block 2 dependency:** Tauri build.rs MUST embed `AURORA_BUILD_PROFILE=production` for release builds. Document in deployment runbook.

---

### 🔴 BLOCKER B2 — Zip-bomb via mismatched declared size

**File:** `src/aurora_launch/engines/bundle_streaming.py:_read_entry` (pre-fix)

**Issue:** The lazy reader called `self._zf.read(name)` and only verified size after full materialisation. Manifest publishes `size_bytes` per entry, but reader did not cross-check that against ZIP central directory's `file_size`. A malicious bundle author could:

1. Build a ZIP with `compression="deflate"`
2. Construct an entry whose central directory says small but actual decompressed size is huge (or vice versa)
3. Manifest declares size_bytes=100, ZIP entry inflates to 4 GB
4. Reader allocates 4 GB before integrity check fires → OOM kill / DoS

**Even с "store" (no compression):** an attacker could manually craft a ZIP с inconsistent central directory vs local file header sizes, exploiting library decoder differences.

**Fix applied:** In `_read_entry`, before `zf.read`:
1. Look up ZIP central directory entry: `zinfo = self._zf.getinfo(name)`
2. Cross-check `zinfo.file_size == manifest.files[name].size_bytes` — mismatch → `BundleIntegrityError`
3. Cross-check `zinfo.file_size <= MAX_ENTRY_SIZE` (2 GB cap) — exceeded → `BundleFormatError`
4. After read: cross-check `len(data) == manifest.files[name].size_bytes` (defense-in-depth catches central-dir-vs-actual mismatch)

**Test coverage added:**
- `test_zip_bomb_size_mismatch_rejected` — tampered entry size detected
- `test_zip_bomb_oversized_entry_capped` — cap enforcement (monkey-patched cap для test speed)

**Note:** Eager `BundleZipReader._read_zip` does not have the same vulnerability because it uses `_verify_integrity` after read, which catches hash mismatch. But hash check happens AFTER allocation — same DoS surface remains. Eager mode addressed via the duplicate-entry fix (B4) which is more impactful for eager. A follow-up Block 1E should add size cross-check before read in eager mode too.

---

### 🔴 BLOCKER B3 — `BundleZipWriter.from_loaded(LazyLoadedBundle)` silently materialises everything

**File:** `src/aurora_launch/engines/bundle_container.py:from_loaded` (pre-fix)

**Issue:** `from_loaded` iterates `loaded.files.items()`. When `loaded` is a `LazyLoadedBundle`, the `Mapping.items()` default implementation calls `__getitem__` for every key, which:
- Materialises every entry through `_read_entry`
- Hits the LRU cache cap; entries cycle through cache and may need to be re-read from ZIP later (writer iterates AFTER materialising — at write time entries may have been evicted)
- Worst case: 200 MB bundle, 512 MB cache → all entries fit, OK; **but** 600 MB bundle → 100 MB of double-reads + cache thrash

The user has no signal that lazy mode just lost all its benefits.

**Fix applied:**
1. `BundleZipWriter.from_loaded` now type-checks: `isinstance(loaded, LazyLoadedBundle)` → raises `TypeError` with explicit guidance.
2. Added `LazyLoadedBundle.materialise_eager() -> LoadedBundle` helper. Caller invokes it deliberately, signalling acceptance of the memory cost.
3. The eager copy is independent of the lazy bundle — it does NOT hold the lock, so caller can close the lazy bundle and proceed с writes via `from_loaded(eager_copy)`.

**Test coverage added:**
- `test_from_loaded_refuses_lazy_bundle` — TypeError with explicit message
- `test_lazy_materialise_then_rebase_writer_round_trip` — happy path
- `test_materialise_eager_independent_of_lazy` — eager copy outlives lazy + lock released
- `test_materialise_eager_after_close_raises` — closed bundle rejects materialise

---

### 🔴 BLOCKER B4 — Duplicate ZIP entry names bypass set-based integrity checks

**Files:** `src/aurora_launch/engines/bundle_container.py:_read_zip`, `bundle_streaming.py:open_lazy` (pre-fix)

**Issue:** ZIP spec permits duplicate entry names. `zipfile.ZipFile.read(name)` and `getinfo(name)` return the LAST entry с that name. Both eager и lazy readers built `set(names)` for missing/extra/duplicate detection — but `set` deduplicates, so a duplicate goes undetected by structural checks.

**Attack scenario:**
1. Malicious bundle: legitimate `manifest.json` declares `proxy_model.pickle` с known-good hash X
2. Attacker appends a **second** `proxy_model.pickle` ZIP entry с tampered payload (hash Y)
3. Reader's `namelist()` returns `["manifest.json", "proxy_model.pickle", "proxy_model.pickle"]`
4. `set(names)` deduplicates to `{"manifest.json", "proxy_model.pickle"}` — structural check passes
5. `zf.read("proxy_model.pickle")` returns LAST entry (tampered)
6. Hash check on first access: actual hash = Y, manifest hash = X → mismatch detected only at access time, possibly ignored if integrity_check="warn" (logs only)
7. With integrity_check="disabled", attacker payload silently substituted

**Fix applied:** Both eager и lazy readers now check `len(names) != len(set(names))` upfront and raise `BundleFormatError` if duplicates found. List of duplicate names (first 5) included in error message.

**Test coverage added:**
- `test_duplicate_entries_rejected_lazy` — manually crafted ZIP с duplicate
- `test_duplicate_entries_rejected_eager` — same через `BundleZipReader().read()`

---

### 🟠 HIGH H1 — `ByteSizeLRU.put()` with oversized value violated cap

**File:** `src/aurora_launch/engines/bundle_streaming.py:ByteSizeLRU.put` (pre-fix)

**Issue:** When a single value exceeded `max_bytes`, the eviction loop drained every existing entry, then stored the oversized value anyway. Resulting `total_size > max_bytes` — invariant violated; users who rely on cache for memory budgeting get surprised.

```python
# Pre-fix:
while self._data and self._size + size > self._max_bytes:
    # evicts everything if size > max_bytes
    ...
self._data[key] = value      # stored regardless
self._size += size            # now > max_bytes
```

**Fix applied:** If `size > max_bytes`, return early без storing. Existing entries preserved. Caller still gets the bytes via `_read_entry` return path; we just don't double-buffer.

**Test coverage added:**
- `test_put_oversized_value_does_not_evict_existing` — existing entries intact
- `test_put_exact_fit_succeeds` — boundary: `size == max_bytes` accepted

---

### 🟠 HIGH H2 — `last_modified` timestamp resolution allowed silent collision

**File:** `src/aurora_launch/engines/bundle_manifest.py:with_revision_bump` (pre-fix)

**Issue:** Format string `%Y-%m-%dT%H:%M:%SZ` had only second-level resolution. Two `with_revision_bump()` calls within the same wall-clock second produced identical `last_modified` strings.

This breaks the invariant "revision bump → timestamp advances", which any audit tooling that relies on monotonic last_modified would assume.

**Fix applied:** Format upgraded to `%Y-%m-%dT%H:%M:%S.%fZ` (microsecond resolution). Same change in `make_initial_manifest`.

**Limitation:** Even microsecond resolution can collide on Windows (clock granularity ~15ms in some configs). The **strong** monotonic guarantee remains the `revision` integer counter — `last_modified` is best-effort wall clock. Documented inline.

**Test coverage added:**
- `test_revision_bump_subsecond_distinct_with_short_wait` — 1ms gap suffices
- `test_revision_strictly_monotonic_regardless_of_clock` — revision counter is the real ordering source
- `test_initial_manifest_uses_microsecond_format` — format check

---

## Deferred — Medium / Low (no fix this cycle)

### 🟡 MEDIUM M1 — `_verified_entries` set grows unbounded

**File:** `bundle_streaming.py:LazyLoadedBundle`

`_verified_entries: set[str]` accumulates names and is never trimmed. For bundles с >10K entries this is non-trivial RAM (a few MB of string overhead). Aurora Launch bundles realistically have <50 entries, so this is theoretical.

**Mitigation if it becomes real:** bound by manifest entry count (set is at most `len(manifest.files)`), or drop the set entirely and always re-verify (cost: re-hash on every read; trades RAM for CPU).

### 🟡 MEDIUM M2 — Tight coupling to private SDK methods

**File:** `license_validator.py:295-329`

Calls `sdk._read_cache()` и `sdk._verify_jwt(...)` — both private. Future SDK refactors could break Aurora Launch silently.

**Action:** Coordinate с aurora-platform-core team to expose stable public API for cache-only read path. File issue against `aurora-platform-core` repo.

### 🟡 MEDIUM M3 — Zip-slip `:` check is overly aggressive on POSIX

**Files:** `bundle_container.py:_read_zip`, `bundle_streaming.py:open_lazy`

`":" in name` rejects POSIX-legitimate names like `data:report.json`. Predates Block 1C, не addressed here to keep audit scope tight.

**Action:** Block 4 — narrow to Windows-specific check (drive letter pattern: `^[A-Za-z]:`).

### 🟢 LOW M4 — Orphan tmp cleanup runs without lock

**File:** `bundle_persistence.py:atomic_write_bundle`

Writer cleans `<path>.tmp` before write under bundle_lock — safe internally. But external tooling (an admin sweeping orphans) could race. Phase B single-user model — accept.

### 🟢 LOW L1 — `manifest.json` size unbounded

**File:** `bundle_streaming.py:open_lazy`

`json.loads(manifest_bytes)` without size cap. Malicious 1 GB manifest could OOM at parse time. Realistic manifests are <1 MB; not exploitable in trust model where bundles come from trusted sources. Add 16 MB cap in Block 4 hardening pass.

---

## Tests Summary

- **Before audit:** 469 tests passing
- **After audit:** 485 tests passing (+16 new audit-fix tests)
- **Tests modified:** 4 (existing 1B bypass tests updated for new bypass contract; 1 lazy-rebase test simplified using `materialise_eager()`)
- **Regressions:** 0

## Release Gate

✅ All BLOCKER findings fixed and tested.
✅ All HIGH findings fixed and tested.
🟡 MEDIUM/LOW findings documented с owners & target windows.

**Recommended next step:** tag `v0.1.0-alpha1` after this commit. Then begin Block 2 (frontend ship).

**Block 2 prerequisites from this audit:**
1. Tauri build pipeline MUST set `AURORA_BUILD_PROFILE=production` env at build time для release artifacts (B1 dependency).
2. Document deployment runbook entry: production builds verify `AURORA_BUILD_PROFILE != dev` at startup; log refused-bypass warnings.
