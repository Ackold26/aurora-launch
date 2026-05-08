"""Tests для Block 1C — streaming reader (LazyLoadedBundle + LRU cache).

Coverage:
- ByteSizeLRU: insertion order, LRU eviction on size cap, replace, zero cap
- LazyFileMap: lazy reads, manifest-only enumeration, contains, missing key
- open_lazy + LazyLoadedBundle: round-trip, manifest-only open, cache reuse,
  integrity check on access (strict / warn / disabled), zip-slip defense,
  context manager, double-close, fallback for legacy JSON, missing/extra
  files at structural pass, verify_all() audit method
- BundleZipReader.read_lazy: dispatch (zip → lazy, json → eager), cache cap
  override, default cap
- Concurrency: lazy reader holds shared lock; concurrent writer blocked
- Resource cleanup: close releases ZipFile + lock; ExitStack on construction
  failure
"""

from __future__ import annotations

import io
import json
import threading
import time
import zipfile
from pathlib import Path

import pytest

from aurora_launch.engines.bundle_container import (
    BundleConflictError,
    BundleFormatError,
    BundleIntegrityError,
    BundleZipReader,
    BundleZipWriter,
)
from aurora_launch.engines.bundle_lock import BundleLockError, bundle_lock
from aurora_launch.engines.bundle_streaming import (
    DEFAULT_CACHE_BYTES,
    ByteSizeLRU,
    LazyFileMap,
    LazyLoadedBundle,
    open_lazy,
)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _write_bundle(
    path: Path,
    files: dict[str, bytes],
    *,
    aurora_app_version: str = "0.1.0",
    integrity_check: str = "strict",
) -> None:
    writer = BundleZipWriter(
        aurora_app_version=aurora_app_version,
        integrity_check=integrity_check,  # type: ignore[arg-type]
    )
    for name, content in files.items():
        writer.add_file(name, content)
    writer.write(path)


# ----------------------------------------------------------------------------
# ByteSizeLRU
# ----------------------------------------------------------------------------


class TestByteSizeLRU:
    def test_basic_put_get(self):
        cache = ByteSizeLRU(max_bytes=1024)
        cache.put("a", b"hello")
        assert cache.get("a") == b"hello"
        assert cache.total_size == 5
        assert len(cache) == 1

    def test_get_missing_returns_none(self):
        cache = ByteSizeLRU(max_bytes=1024)
        assert cache.get("missing") is None

    def test_eviction_on_size_cap(self):
        cache = ByteSizeLRU(max_bytes=10)
        cache.put("a", b"12345")  # 5 bytes
        cache.put("b", b"67890")  # 5 bytes — total 10
        cache.put("c", b"X")  # 1 byte — must evict "a"
        assert cache.get("a") is None
        assert cache.get("b") == b"67890"
        assert cache.get("c") == b"X"
        assert cache.total_size == 6

    def test_lru_order_on_get(self):
        cache = ByteSizeLRU(max_bytes=10)
        cache.put("a", b"12345")
        cache.put("b", b"67890")
        # Access "a" — bumps it to most-recent
        cache.get("a")
        cache.put("c", b"XX")  # 2 bytes, must evict "b" (least recent)
        assert cache.get("b") is None
        assert cache.get("a") == b"12345"
        assert cache.get("c") == b"XX"

    def test_replace_existing_key(self):
        cache = ByteSizeLRU(max_bytes=100)
        cache.put("a", b"hello")
        cache.put("a", b"world!")  # different length
        assert cache.get("a") == b"world!"
        assert cache.total_size == 6
        assert len(cache) == 1

    def test_zero_cap_disables_caching(self):
        cache = ByteSizeLRU(max_bytes=0)
        cache.put("a", b"hello")
        assert cache.get("a") is None
        assert cache.total_size == 0

    def test_negative_cap_rejected(self):
        with pytest.raises(ValueError):
            ByteSizeLRU(max_bytes=-1)

    def test_clear_resets_state(self):
        cache = ByteSizeLRU(max_bytes=100)
        cache.put("a", b"hello")
        cache.put("b", b"world")
        cache.clear()
        assert cache.total_size == 0
        assert cache.get("a") is None
        assert len(cache) == 0

    def test_oversized_entry_evicts_others_then_stores(self):
        # If a single entry equals (or fits) within cap, прочие entries are
        # evicted to make room for it. Exact-fit case here.
        cache = ByteSizeLRU(max_bytes=10)
        cache.put("a", b"123")
        cache.put("b", b"45")
        cache.put("big", b"0123456789")  # 10 bytes — exact fit
        assert cache.get("a") is None
        assert cache.get("b") is None
        assert cache.get("big") == b"0123456789"

    def test_contains(self):
        cache = ByteSizeLRU(max_bytes=100)
        cache.put("a", b"hi")
        assert "a" in cache
        assert "b" not in cache


# ----------------------------------------------------------------------------
# open_lazy + LazyLoadedBundle round-trip
# ----------------------------------------------------------------------------


class TestLazyOpenBasic:
    def test_round_trip_via_lazy(self, tmp_path: Path):
        path = tmp_path / "test.aurora"
        _write_bundle(path, {"data.json": b'{"k":1}', "model.bin": b"\x00\x01\x02"})

        with open_lazy(path) as bundle:
            assert isinstance(bundle, LazyLoadedBundle)
            assert bundle.source_format == "zip"
            assert bundle.files["data.json"] == b'{"k":1}'
            assert bundle.files["model.bin"] == b"\x00\x01\x02"

    def test_manifest_eager_payload_lazy(self, tmp_path: Path):
        # Verify nothing payload-shaped is materialised до access.
        path = tmp_path / "lazy.aurora"
        _write_bundle(path, {"a.bin": b"A" * 100, "b.bin": b"B" * 100})

        with open_lazy(path) as bundle:
            assert bundle.manifest.revision == 0
            assert set(bundle.files.keys()) == {"a.bin", "b.bin"}
            assert bundle.cache_total_size == 0  # ничего не прочитано
            _ = bundle.files["a.bin"]
            assert bundle.cache_total_size == 100
            _ = bundle.files["b.bin"]
            assert bundle.cache_total_size == 200

    def test_get_json_works(self, tmp_path: Path):
        path = tmp_path / "j.aurora"
        payload = {"hello": "world", "n": 42}
        _write_bundle(path, {"meta.json": json.dumps(payload).encode("utf-8")})

        with open_lazy(path) as bundle:
            assert bundle.get_json("meta.json") == payload

    def test_has_does_not_load(self, tmp_path: Path):
        path = tmp_path / "h.aurora"
        _write_bundle(path, {"x.bin": b"X" * 50})

        with open_lazy(path) as bundle:
            assert bundle.has("x.bin")
            assert not bundle.has("missing.bin")
            assert bundle.cache_total_size == 0

    def test_list_entries(self, tmp_path: Path):
        path = tmp_path / "l.aurora"
        _write_bundle(path, {"b.bin": b"1", "a.bin": b"2", "c.bin": b"3"})

        with open_lazy(path) as bundle:
            assert bundle.list_entries() == ["a.bin", "b.bin", "c.bin"]

    def test_cache_hit_avoids_zip_read(self, tmp_path: Path):
        path = tmp_path / "c.aurora"
        _write_bundle(path, {"x.bin": b"X" * 50})

        with open_lazy(path) as bundle:
            data1 = bundle.files["x.bin"]
            # Access second time — must hit cache (we monitor by patching
            # the underlying zf.read after first read)
            zf = bundle._zf
            assert zf is not None
            calls = {"n": 0}
            original_read = zf.read

            def counting_read(name):  # type: ignore[no-untyped-def]
                calls["n"] += 1
                return original_read(name)

            zf.read = counting_read  # type: ignore[method-assign]
            data2 = bundle.files["x.bin"]
            assert data1 == data2
            assert calls["n"] == 0  # cache hit, no zip read

    def test_unknown_entry_raises_keyerror(self, tmp_path: Path):
        path = tmp_path / "u.aurora"
        _write_bundle(path, {"x.bin": b"x"})

        with open_lazy(path) as bundle:
            with pytest.raises(KeyError):
                _ = bundle.files["missing.bin"]


# ----------------------------------------------------------------------------
# LazyFileMap mapping protocol
# ----------------------------------------------------------------------------


class TestLazyFileMap:
    def test_len_iter_keys(self, tmp_path: Path):
        path = tmp_path / "m.aurora"
        _write_bundle(path, {"a": b"1", "b": b"2"})
        with open_lazy(path) as bundle:
            assert len(bundle.files) == 2
            assert sorted(bundle.files) == ["a", "b"]
            assert sorted(bundle.files.keys()) == ["a", "b"]

    def test_contains(self, tmp_path: Path):
        path = tmp_path / "n.aurora"
        _write_bundle(path, {"a": b"1"})
        with open_lazy(path) as bundle:
            assert "a" in bundle.files
            assert "missing" not in bundle.files
            assert 42 not in bundle.files  # type: ignore[operator]


# ----------------------------------------------------------------------------
# Cache cap interaction
# ----------------------------------------------------------------------------


class TestLazyCacheBehavior:
    def test_cache_evicts_under_cap(self, tmp_path: Path):
        path = tmp_path / "e.aurora"
        _write_bundle(path, {"a.bin": b"A" * 100, "b.bin": b"B" * 100, "c.bin": b"C" * 100})

        with open_lazy(path, cache_max_bytes=150) as bundle:
            _ = bundle.files["a.bin"]
            _ = bundle.files["b.bin"]
            # cache had 100, then 100+100=200 > 150 → evict "a"
            assert "a.bin" not in bundle._cache
            assert "b.bin" in bundle._cache
            _ = bundle.files["c.bin"]
            assert "b.bin" not in bundle._cache
            assert "c.bin" in bundle._cache

    def test_zero_cache_lazy_still_works(self, tmp_path: Path):
        path = tmp_path / "z.aurora"
        _write_bundle(path, {"x.bin": b"hello"})

        with open_lazy(path, cache_max_bytes=0) as bundle:
            assert bundle.files["x.bin"] == b"hello"
            assert bundle.cache_total_size == 0
            # second access re-reads from zip — verifies path not broken
            assert bundle.files["x.bin"] == b"hello"

    def test_cache_clear_drops_entries(self, tmp_path: Path):
        path = tmp_path / "cc.aurora"
        _write_bundle(path, {"x.bin": b"X" * 100})

        with open_lazy(path) as bundle:
            _ = bundle.files["x.bin"]
            assert bundle.cache_total_size == 100
            bundle.cache_clear()
            assert bundle.cache_total_size == 0


# ----------------------------------------------------------------------------
# Integrity check on access
# ----------------------------------------------------------------------------


class TestLazyIntegrity:
    def test_strict_raises_on_tampered_entry(self, tmp_path: Path):
        path = tmp_path / "tamper.aurora"
        _write_bundle(path, {"good.bin": b"original"})

        # Mutate ZIP entry без updating manifest
        buf = io.BytesIO(path.read_bytes())
        with zipfile.ZipFile(buf, "r") as zf:
            names = zf.namelist()
            entries = {n: zf.read(n) for n in names}
        entries["good.bin"] = b"TAMPERED"
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as zf:
            # Manifest first preserved; rewrite all с tampered payload
            for n in names:
                zf.writestr(n, entries[n])
        path.write_bytes(out.getvalue())

        with open_lazy(path) as bundle:
            with pytest.raises(BundleIntegrityError):
                _ = bundle.files["good.bin"]

    def test_disabled_integrity_skips_verification(self, tmp_path: Path):
        path = tmp_path / "dis.aurora"
        _write_bundle(path, {"x.bin": b"original"}, integrity_check="disabled")

        # Tamper
        buf = io.BytesIO(path.read_bytes())
        with zipfile.ZipFile(buf, "r") as zf:
            names = zf.namelist()
            entries = {n: zf.read(n) for n in names}
        entries["x.bin"] = b"TAMPERED"
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as zf:
            for n in names:
                zf.writestr(n, entries[n])
        path.write_bytes(out.getvalue())

        with open_lazy(path) as bundle:
            # No exception — disabled mode skips per-entry hash check
            assert bundle.files["x.bin"] == b"TAMPERED"

    def test_warn_mode_logs_but_does_not_raise(self, tmp_path: Path, caplog):
        path = tmp_path / "warn.aurora"
        _write_bundle(path, {"x.bin": b"original"}, integrity_check="warn")

        # Tamper
        buf = io.BytesIO(path.read_bytes())
        with zipfile.ZipFile(buf, "r") as zf:
            names = zf.namelist()
            entries = {n: zf.read(n) for n in names}
        entries["x.bin"] = b"TAMPERED"
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as zf:
            for n in names:
                zf.writestr(n, entries[n])
        path.write_bytes(out.getvalue())

        with open_lazy(path, strict_integrity=False) as bundle:
            data = bundle.files["x.bin"]
            assert data == b"TAMPERED"
        # Не падаем — warn mode

    def test_verify_on_access_disabled(self, tmp_path: Path):
        # verify_integrity=False bypasses per-access hash check entirely
        path = tmp_path / "noverify.aurora"
        _write_bundle(path, {"x.bin": b"original"})

        buf = io.BytesIO(path.read_bytes())
        with zipfile.ZipFile(buf, "r") as zf:
            names = zf.namelist()
            entries = {n: zf.read(n) for n in names}
        entries["x.bin"] = b"TAMPERED"
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as zf:
            for n in names:
                zf.writestr(n, entries[n])
        path.write_bytes(out.getvalue())

        with open_lazy(path, verify_integrity=False) as bundle:
            assert bundle.files["x.bin"] == b"TAMPERED"


# ----------------------------------------------------------------------------
# Structural integrity (manifest vs ZIP namelist)
# ----------------------------------------------------------------------------


class TestStructuralIntegrity:
    def test_extra_file_in_zip_rejected_strict(self, tmp_path: Path):
        path = tmp_path / "extra.aurora"
        _write_bundle(path, {"x.bin": b"x"})

        # Inject an extra file not in manifest
        buf = io.BytesIO(path.read_bytes())
        with zipfile.ZipFile(buf, "r") as zf:
            names = zf.namelist()
            entries = {n: zf.read(n) for n in names}
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as zf:
            for n in names:
                zf.writestr(n, entries[n])
            zf.writestr("rogue.bin", b"surprise")
        path.write_bytes(out.getvalue())

        with pytest.raises(BundleIntegrityError):
            open_lazy(path)

    def test_missing_file_rejected_strict(self, tmp_path: Path):
        path = tmp_path / "miss.aurora"
        _write_bundle(path, {"a.bin": b"A", "b.bin": b"B"})

        # Drop "b.bin" from ZIP
        buf = io.BytesIO(path.read_bytes())
        with zipfile.ZipFile(buf, "r") as zf:
            names = [n for n in zf.namelist() if n != "b.bin"]
            entries = {n: zf.read(n) for n in names}
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as zf:
            for n in names:
                zf.writestr(n, entries[n])
        path.write_bytes(out.getvalue())

        with pytest.raises(BundleIntegrityError):
            open_lazy(path)

    def test_zip_slip_path_rejected(self, tmp_path: Path):
        path = tmp_path / "slip.aurora"
        # Manually craft a ZIP с traversal entry name (мимо writer)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as zf:
            # Need a manifest else first BundleFormatError fires earlier.
            # We craft minimal manifest claiming this entry is empty.
            from aurora_launch.engines.bundle_manifest import (
                compute_file_entry,
                make_initial_manifest,
            )

            evil_name = "../etc/passwd"
            evil_payload = b"hacked"
            manifest = make_initial_manifest(
                aurora_app_version="0.1.0",
                min_app_version="0.1.0",
                project_id="evil-test",
            )
            manifest = manifest.model_copy(
                update={"files": {evil_name: compute_file_entry(evil_payload)}}
            )
            zf.writestr("manifest.json", manifest.to_canonical_bytes())
            zf.writestr(evil_name, evil_payload)

        with pytest.raises(BundleFormatError, match="zip-slip"):
            open_lazy(path)

    def test_missing_manifest_rejected(self, tmp_path: Path):
        path = tmp_path / "nomanifest.aurora"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as zf:
            zf.writestr("data.bin", b"hi")
        with pytest.raises(BundleFormatError, match="manifest"):
            open_lazy(path)


# ----------------------------------------------------------------------------
# verify_all explicit audit
# ----------------------------------------------------------------------------


class TestVerifyAll:
    def test_verify_all_clean_bundle(self, tmp_path: Path):
        path = tmp_path / "clean.aurora"
        _write_bundle(path, {"a.bin": b"A" * 100, "b.bin": b"B" * 100})
        with open_lazy(path) as bundle:
            assert bundle.verify_all() == []

    def test_verify_all_does_not_blow_cache(self, tmp_path: Path):
        # verify_all reads everything, но не должно cache_size > cache_max_bytes
        path = tmp_path / "big.aurora"
        _write_bundle(path, {f"f{i}.bin": b"X" * 1000 for i in range(20)})
        with open_lazy(path, cache_max_bytes=500) as bundle:
            issues = bundle.verify_all()
            assert issues == []
            assert bundle.cache_total_size <= 500


# ----------------------------------------------------------------------------
# Lifecycle / context manager
# ----------------------------------------------------------------------------


class TestLifecycle:
    def test_context_manager_releases_resources(self, tmp_path: Path):
        path = tmp_path / "cm.aurora"
        _write_bundle(path, {"x.bin": b"x"})
        with open_lazy(path) as bundle:
            assert bundle._zf is not None
            assert bundle._closed is False
        assert bundle._zf is None
        assert bundle._closed is True

    def test_double_close_safe(self, tmp_path: Path):
        path = tmp_path / "dc.aurora"
        _write_bundle(path, {"x.bin": b"x"})
        bundle = open_lazy(path)
        bundle.close()
        bundle.close()  # idempotent — must not raise

    def test_access_after_close_raises(self, tmp_path: Path):
        path = tmp_path / "ac.aurora"
        _write_bundle(path, {"x.bin": b"x"})
        bundle = open_lazy(path)
        bundle.close()
        with pytest.raises(ValueError, match="closed"):
            _ = bundle.files["x.bin"]

    def test_failed_open_releases_lock(self, tmp_path: Path):
        # Manifest-missing should still release the held lock + close zip
        path = tmp_path / "fail.aurora"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("nope.bin", b"x")
        with pytest.raises(BundleFormatError):
            open_lazy(path)
        # Lock must be free now — acquire-and-release proves it
        with bundle_lock(path, mode="exclusive", timeout=1.0):
            pass

    def test_nonexistent_path_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            open_lazy(tmp_path / "missing.aurora")

    def test_non_zip_format_raises(self, tmp_path: Path):
        path = tmp_path / "legacy.aurora.json"
        path.write_text(json.dumps({"aurora_launch_version": "0.0.5", "manifest_sha256": "abc"}))
        with pytest.raises(BundleFormatError, match="ZIP"):
            open_lazy(path)


# ----------------------------------------------------------------------------
# BundleZipReader.read_lazy dispatch
# ----------------------------------------------------------------------------


class TestReaderDispatch:
    def test_read_lazy_zip_returns_lazy_bundle(self, tmp_path: Path):
        path = tmp_path / "d.aurora"
        _write_bundle(path, {"x.bin": b"x"})
        reader = BundleZipReader()
        with reader.read_lazy(path) as bundle:
            assert isinstance(bundle, LazyLoadedBundle)

    def test_read_lazy_legacy_falls_back_to_eager(self, tmp_path: Path):
        path = tmp_path / "legacy.aurora.json"
        path.write_text(
            json.dumps(
                {
                    "aurora_launch_version": "0.0.5",
                    "manifest_sha256": "abc",
                    "schema_version": "3.0",
                }
            )
        )
        reader = BundleZipReader()
        result = reader.read_lazy(path)
        # Eager LoadedBundle, NOT LazyLoadedBundle
        assert not isinstance(result, LazyLoadedBundle)
        assert result.source_format == "json"

    def test_read_lazy_uses_configured_cache_cap(self, tmp_path: Path):
        path = tmp_path / "c.aurora"
        _write_bundle(path, {"x.bin": b"X" * 50})
        reader = BundleZipReader(cache_max_bytes=42)
        with reader.read_lazy(path) as bundle:
            assert bundle.cache_max_bytes == 42

    def test_read_lazy_default_cap(self, tmp_path: Path):
        path = tmp_path / "c2.aurora"
        _write_bundle(path, {"x.bin": b"x"})
        reader = BundleZipReader()  # cache_max_bytes=None → default
        with reader.read_lazy(path) as bundle:
            assert bundle.cache_max_bytes == DEFAULT_CACHE_BYTES

    def test_read_lazy_missing_path(self, tmp_path: Path):
        reader = BundleZipReader()
        with pytest.raises(FileNotFoundError):
            reader.read_lazy(tmp_path / "nope.aurora")


# ----------------------------------------------------------------------------
# Concurrency — lazy reader holds shared lock for its lifetime
# ----------------------------------------------------------------------------


class TestConcurrency:
    def test_lazy_reader_blocks_concurrent_writer(self, tmp_path: Path):
        path = tmp_path / "lock.aurora"
        _write_bundle(path, {"x.bin": b"x"})

        with open_lazy(path):  # holds shared lock for its lifetime
            with pytest.raises(BundleLockError):
                with bundle_lock(path, mode="exclusive", timeout=0.1):
                    pass

    def test_lazy_reader_releases_lock_on_close(self, tmp_path: Path):
        path = tmp_path / "rel.aurora"
        _write_bundle(path, {"x.bin": b"x"})

        bundle = open_lazy(path)
        try:
            _ = bundle.files["x.bin"]
        finally:
            bundle.close()

        # After close — exclusive lock acquireable
        with bundle_lock(path, mode="exclusive", timeout=1.0):
            pass


# ----------------------------------------------------------------------------
# Round-trip via writer rebase from lazy (revision bump path)
# ----------------------------------------------------------------------------


class TestWriterFromLazyLoaded:
    def test_lazy_materialise_then_rebase_writer_round_trip(self, tmp_path: Path):
        path = tmp_path / "rb.aurora"
        _write_bundle(path, {"a.bin": b"A", "b.bin": b"B"})

        # B3 fix: materialise_eager() is the explicit conversion path.
        with open_lazy(path) as bundle:
            base_revision = bundle.manifest.revision
            eager = bundle.materialise_eager()

        # eager is independent of bundle (lock released), works с from_loaded
        writer = BundleZipWriter.from_loaded(eager)
        writer.add_file("c.bin", b"C")
        new_manifest = writer.write(path, expected_revision=base_revision)
        assert new_manifest.revision == base_revision + 1

        with open_lazy(path) as bundle2:
            assert bundle2.files["a.bin"] == b"A"
            assert bundle2.files["c.bin"] == b"C"
            assert bundle2.manifest.revision == base_revision + 1

    def test_from_loaded_refuses_lazy_bundle(self, tmp_path: Path):
        """Audit Block 1D B3: passing LazyLoadedBundle directly raises TypeError."""
        path = tmp_path / "refuse.aurora"
        _write_bundle(path, {"a.bin": b"A"})

        with open_lazy(path) as bundle:
            with pytest.raises(TypeError, match="LazyLoadedBundle"):
                BundleZipWriter.from_loaded(bundle)

    def test_materialise_eager_independent_of_lazy(self, tmp_path: Path):
        """Materialised copy survives lazy bundle close (no lock retention)."""
        path = tmp_path / "mat.aurora"
        _write_bundle(path, {"a.bin": b"A" * 50})

        with open_lazy(path) as bundle:
            eager = bundle.materialise_eager()
        # bundle closed; eager still usable
        assert eager.files["a.bin"] == b"A" * 50
        assert eager.manifest.revision == 0
        # eager does NOT hold the lock — exclusive lock acquireable
        with bundle_lock(path, mode="exclusive", timeout=1.0):
            pass

    def test_materialise_eager_after_close_raises(self, tmp_path: Path):
        path = tmp_path / "macl.aurora"
        _write_bundle(path, {"a.bin": b"A"})
        bundle = open_lazy(path)
        bundle.close()
        with pytest.raises(ValueError, match="closed"):
            bundle.materialise_eager()


# ----------------------------------------------------------------------------
# Audit Block 1D fixes — new tests
# ----------------------------------------------------------------------------


class TestAuditB2ZipBomb:
    def test_zip_bomb_size_mismatch_rejected(self, tmp_path: Path):
        """B2: ZIP entry size larger than manifest claims → BundleIntegrityError.

        Build a bundle, then maliciously replace one entry с a larger payload
        without updating manifest's `size_bytes`.
        """
        path = tmp_path / "bomb.aurora"
        _write_bundle(path, {"x.bin": b"small"})

        # Replace x.bin с larger payload; keep manifest unchanged
        buf = io.BytesIO(path.read_bytes())
        with zipfile.ZipFile(buf, "r") as zf:
            names = zf.namelist()
            entries = {n: zf.read(n) for n in names}
        entries["x.bin"] = b"X" * 10_000  # was 5 bytes
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as zf:
            for n in names:
                zf.writestr(n, entries[n])
        path.write_bytes(out.getvalue())

        with open_lazy(path) as bundle:
            with pytest.raises(BundleIntegrityError, match="size mismatch|size_bytes"):
                _ = bundle.files["x.bin"]

    def test_zip_bomb_oversized_entry_capped(self, tmp_path: Path, monkeypatch):
        """B2: entry larger than MAX_ENTRY_SIZE raises BundleFormatError.

        We monkey-patch the cap to a tiny value so we can test без allocating
        gigabytes.
        """
        from aurora_launch.engines import bundle_streaming as bs

        monkeypatch.setattr(bs, "MAX_ENTRY_SIZE", 100)

        path = tmp_path / "big.aurora"
        _write_bundle(path, {"x.bin": b"X" * 500})  # 500 > 100 cap

        with open_lazy(path) as bundle:
            with pytest.raises(BundleFormatError, match="too large"):
                _ = bundle.files["x.bin"]


class TestAuditB4DuplicateEntries:
    def test_duplicate_entries_rejected_lazy(self, tmp_path: Path):
        """B4: open_lazy refuses ZIP с duplicate entry names."""
        from aurora_launch.engines.bundle_manifest import (
            compute_file_entry,
            make_initial_manifest,
        )

        path = tmp_path / "dup.aurora"
        manifest = make_initial_manifest(
            aurora_app_version="0.1.0",
            min_app_version="0.1.0",
            project_id="dup-test",
        )
        manifest = manifest.model_copy(
            update={"files": {"x.bin": compute_file_entry(b"clean")}}
        )
        with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as zf:
            zf.writestr("manifest.json", manifest.to_canonical_bytes())
            zf.writestr("x.bin", b"clean")
            zf.writestr("x.bin", b"TAMPERED")  # duplicate!

        with pytest.raises(BundleFormatError, match="[Dd]uplicate"):
            open_lazy(path)

    def test_duplicate_entries_rejected_eager(self, tmp_path: Path):
        """B4 (eager path): BundleZipReader.read() also refuses duplicates."""
        from aurora_launch.engines.bundle_manifest import (
            compute_file_entry,
            make_initial_manifest,
        )

        path = tmp_path / "dup2.aurora"
        manifest = make_initial_manifest(
            aurora_app_version="0.1.0",
            min_app_version="0.1.0",
            project_id="dup-test-2",
        )
        manifest = manifest.model_copy(
            update={"files": {"x.bin": compute_file_entry(b"clean")}}
        )
        with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as zf:
            zf.writestr("manifest.json", manifest.to_canonical_bytes())
            zf.writestr("x.bin", b"clean")
            zf.writestr("x.bin", b"TAMPERED")

        reader = BundleZipReader()
        with pytest.raises(BundleFormatError, match="[Dd]uplicate"):
            reader.read(path)


class TestAuditH1OversizedLRURefused:
    def test_put_oversized_value_does_not_evict_existing(self):
        """H1: a value larger than cap is refused, existing entries preserved."""
        cache = ByteSizeLRU(max_bytes=10)
        cache.put("a", b"12345")
        cache.put("b", b"6789")
        # Oversized — refused
        cache.put("BIG", b"X" * 100)
        assert cache.get("BIG") is None
        # Existing entries intact
        assert cache.get("a") == b"12345"
        assert cache.get("b") == b"6789"
        assert cache.total_size == 9
        assert len(cache) == 2

    def test_put_exact_fit_succeeds(self):
        """Boundary: value size == cap is accepted."""
        cache = ByteSizeLRU(max_bytes=10)
        cache.put("a", b"X" * 10)
        assert cache.get("a") == b"X" * 10
        assert cache.total_size == 10


class TestAuditH2TimestampResolution:
    def test_revision_bump_subsecond_distinct_with_short_wait(self):
        """H2: two bumps separated by 1ms produce different timestamps.

        Microsecond precision allows collision на back-to-back calls because
        Windows wall clock resolution can be coarser than 1µs. Real ordering
        guarantee is `revision`. We test that even a tiny gap (1ms — well
        above Windows clock resolution) yields distinct `last_modified`.
        """
        import time as _time

        from aurora_launch.engines.bundle_manifest import make_initial_manifest

        m0 = make_initial_manifest(
            aurora_app_version="0.1.0",
            min_app_version="0.1.0",
            project_id="ts-test",
        )
        _time.sleep(0.001)
        m1 = m0.with_revision_bump()
        _time.sleep(0.001)
        m2 = m1.with_revision_bump()
        assert m1.last_modified != m0.last_modified
        assert m2.last_modified != m1.last_modified
        assert m2.revision == 2

    def test_revision_strictly_monotonic_regardless_of_clock(self):
        """The strong ordering guarantee is revision counter, not timestamp."""
        from aurora_launch.engines.bundle_manifest import make_initial_manifest

        m0 = make_initial_manifest(
            aurora_app_version="0.1.0",
            min_app_version="0.1.0",
            project_id="ts-mono",
        )
        m1 = m0.with_revision_bump()
        m2 = m1.with_revision_bump()
        m3 = m2.with_revision_bump()
        assert [m0.revision, m1.revision, m2.revision, m3.revision] == [0, 1, 2, 3]

    def test_initial_manifest_uses_microsecond_format(self):
        from aurora_launch.engines.bundle_manifest import make_initial_manifest

        m = make_initial_manifest(
            aurora_app_version="0.1.0",
            min_app_version="0.1.0",
            project_id="ts-fmt",
        )
        # %f produces 6-digit microseconds — string contains '.' before 'Z'
        assert "." in m.last_modified and m.last_modified.endswith("Z")


class TestAuditB1LicenseBypassGate:
    def test_bypass_requires_dev_build_profile(self, monkeypatch):
        """B1: bypass env var alone не activates bypass — build profile gate."""
        from aurora_launch.engines.license_validator import (
            LaunchLicenseValidator,
            LicenseState,
        )

        monkeypatch.setenv("AURORA_LAUNCH_LICENSE_BYPASS", "1")
        monkeypatch.delenv("AURORA_BUILD_PROFILE", raising=False)
        v = LaunchLicenseValidator.from_env()
        assert v.bypass is False
        # Status must NOT be ACTIVE с dev_bypass tier
        status = v.current_status()
        assert status.tier != "dev_bypass"

    def test_bypass_explicit_production_refused(self, monkeypatch, caplog):
        from aurora_launch.engines.license_validator import LaunchLicenseValidator

        monkeypatch.setenv("AURORA_LAUNCH_LICENSE_BYPASS", "1")
        monkeypatch.setenv("AURORA_BUILD_PROFILE", "production")
        v = LaunchLicenseValidator.from_env()
        assert v.bypass is False

    def test_bypass_dev_profile_honoured(self, monkeypatch):
        from aurora_launch.engines.license_validator import (
            LaunchLicenseValidator,
            LicenseState,
        )

        monkeypatch.setenv("AURORA_LAUNCH_LICENSE_BYPASS", "1")
        monkeypatch.setenv("AURORA_BUILD_PROFILE", "dev")
        v = LaunchLicenseValidator.from_env()
        assert v.bypass is True
        status = v.current_status()
        assert status.state == LicenseState.ACTIVE
        assert status.tier == "dev_bypass"

    def test_no_bypass_env_no_change(self, monkeypatch):
        """Default (no env) — bypass off, behaviour unchanged."""
        from aurora_launch.engines.license_validator import LaunchLicenseValidator

        monkeypatch.delenv("AURORA_LAUNCH_LICENSE_BYPASS", raising=False)
        monkeypatch.delenv("AURORA_BUILD_PROFILE", raising=False)
        v = LaunchLicenseValidator.from_env()
        assert v.bypass is False
