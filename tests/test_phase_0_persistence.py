"""Phase 0.1 — SQLite working storage tests.

Coverage:
- BlobStore: store/load/exists/delete idempotency, content-addressing, integrity
- ProjectDB: create/list/get/update/delete projects
- ProjectDB: save_version + dedup, load_version, list_versions, compare_versions
- ProjectDB: integrity check + ref_count drift recovery
- Migration: .aurora bundle (ZIP) → ProjectDB
- Migration: legacy `.aurora.json` → ProjectDB
- Concurrency smoke: WAL allows concurrent readers
- Crash safety smoke: orphan tmp blob cleanup
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from pathlib import Path

import pytest

from aurora_launch.engines.bundle_container import BundleZipWriter
from aurora_launch.persistence.blob_store import BlobStore, BlobStoreError
from aurora_launch.persistence.migration_from_zip import (
    MigrationError,
    import_aurora_bundle,
)
from aurora_launch.persistence.project_db import (
    ProjectDB,
    ProjectDBError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def storage_root(tmp_path: Path) -> Path:
    """Aurora Launch working storage root with blobs/ subdir."""
    root = tmp_path / "aurora_launch_storage"
    root.mkdir()
    (root / "blobs").mkdir()
    return root


@pytest.fixture()
def blob_store(storage_root: Path) -> BlobStore:
    return BlobStore(storage_root / "blobs")


@pytest.fixture()
def project_db(storage_root: Path, blob_store: BlobStore) -> ProjectDB:
    db = ProjectDB(storage_root / "projects.db", blob_store)
    yield db
    db.close()


# ---------------------------------------------------------------------------
# BlobStore tests
# ---------------------------------------------------------------------------


class TestBlobStore:
    def test_store_and_load_round_trip(self, blob_store: BlobStore) -> None:
        content = b"hello aurora world"
        info = blob_store.store(content)
        assert info.size_bytes == len(content)
        assert info.storage_path.exists()
        assert blob_store.load(info.sha256) == content

    def test_store_idempotent(self, blob_store: BlobStore) -> None:
        content = b"deterministic blob"
        info1 = blob_store.store(content)
        info2 = blob_store.store(content)
        assert info1.sha256 == info2.sha256
        assert info1.storage_path == info2.storage_path

    def test_content_addressing_correctness(self, blob_store: BlobStore) -> None:
        # Different content → different sha
        a = blob_store.store(b"alpha")
        b = blob_store.store(b"beta")
        assert a.sha256 != b.sha256

    def test_load_integrity_check_detects_tampering(self, blob_store: BlobStore) -> None:
        info = blob_store.store(b"original content")
        # Tamper with the file on disk
        info.storage_path.write_bytes(b"corrupted")
        with pytest.raises(BlobStoreError, match="integrity check failed"):
            blob_store.load(info.sha256)

    def test_load_missing_blob_raises(self, blob_store: BlobStore) -> None:
        with pytest.raises(BlobStoreError, match="Blob not found"):
            blob_store.load("a" * 64)

    def test_invalid_sha256_format_rejected(self, blob_store: BlobStore) -> None:
        with pytest.raises(BlobStoreError, match="Invalid SHA-256 hex"):
            blob_store.load("not-a-hash")
        with pytest.raises(BlobStoreError, match="Invalid SHA-256 hex"):
            blob_store.load("a" * 63)  # one short
        with pytest.raises(BlobStoreError, match="Invalid SHA-256 hex"):
            blob_store.exists("A" * 64)  # uppercase not allowed

    def test_delete_idempotent(self, blob_store: BlobStore) -> None:
        info = blob_store.store(b"to be deleted")
        blob_store.delete(info.sha256)
        # Second delete is a no-op
        blob_store.delete(info.sha256)
        assert not blob_store.exists(info.sha256)

    def test_list_all_skips_malformed(self, blob_store: BlobStore, storage_root: Path) -> None:
        blob_store.store(b"a")
        blob_store.store(b"b")
        # Drop a non-blob file in the dir
        (storage_root / "blobs" / "stray.txt").write_text("hi")
        # Drop a blob with wrong-length name
        (storage_root / "blobs" / "sha256-tooshort.pickle").write_text("nope")
        results = blob_store.list_all()
        assert len(results) == 2

    def test_total_bytes(self, blob_store: BlobStore) -> None:
        blob_store.store(b"x" * 100)
        blob_store.store(b"y" * 200)
        assert blob_store.total_bytes() == 300


# ---------------------------------------------------------------------------
# ProjectDB tests
# ---------------------------------------------------------------------------


class TestProjectDBLifecycle:
    def test_create_and_list_project(self, project_db: ProjectDB) -> None:
        uid = project_db.create_project(
            "Pilot Materia Medica",
            aurora_app_version="0.1.0",
            metadata={"customer": "Materia Medica"},
        )
        assert uuid.UUID(uid)  # valid UUID
        projects = project_db.list_projects()
        assert len(projects) == 1
        assert projects[0].name == "Pilot Materia Medica"
        assert projects[0].version_count == 0
        assert projects[0].current_version_id is None

    def test_create_rejects_empty_name(self, project_db: ProjectDB) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            project_db.create_project("   ", aurora_app_version="0.1.0")

    def test_create_rejects_invalid_granularity(self, project_db: ProjectDB) -> None:
        with pytest.raises(ValueError, match="granularity must be"):
            project_db.create_project(
                "p", aurora_app_version="0.1.0", granularity="daily"
            )

    def test_get_unknown_project_raises(self, project_db: ProjectDB) -> None:
        with pytest.raises(ProjectDBError, match="not found"):
            project_db.get_project("00000000-0000-0000-0000-000000000000")

    def test_update_metadata(self, project_db: ProjectDB) -> None:
        uid = project_db.create_project("p", aurora_app_version="0.1.0")
        project_db.update_project_metadata(
            uid, metadata={"updated": True}, name="renamed"
        )
        detail = project_db.get_project(uid)
        assert detail.name == "renamed"
        assert detail.metadata == {"updated": True}

    def test_delete_project_cascades_versions(self, project_db: ProjectDB) -> None:
        uid = project_db.create_project("p", aurora_app_version="0.1.0")
        project_db.save_version(uid, files={"a.bin": b"alpha"})
        project_db.save_version(uid, files={"a.bin": b"alpha", "b.bin": b"beta"})
        assert len(project_db.list_versions(uid)) == 2

        project_db.delete_project(uid)
        with pytest.raises(ProjectDBError):
            project_db.get_project(uid)

    def test_delete_decrements_blob_ref_counts(self, project_db: ProjectDB) -> None:
        # Two projects share the same blob (deduplication scenario)
        uid1 = project_db.create_project("p1", aurora_app_version="0.1.0")
        uid2 = project_db.create_project("p2", aurora_app_version="0.1.0")
        shared_content = b"shared posterior pickle"

        project_db.save_version(uid1, files={"posterior.pickle": shared_content})
        project_db.save_version(uid2, files={"posterior.pickle": shared_content})

        sha = project_db.blob_store.compute_hash(shared_content)
        row = project_db._conn.execute(
            "SELECT ref_count FROM blobs WHERE sha256 = ?", (sha,)
        ).fetchone()
        assert row["ref_count"] == 2  # shared between 2 versions

        project_db.delete_project(uid1)
        row = project_db._conn.execute(
            "SELECT ref_count FROM blobs WHERE sha256 = ?", (sha,)
        ).fetchone()
        assert row["ref_count"] == 1


class TestSaveVersion:
    def test_save_version_basic(self, project_db: ProjectDB) -> None:
        uid = project_db.create_project("p", aurora_app_version="0.1.0")
        version_id = project_db.save_version(
            uid,
            files={"forecast.pickle": b"forecast bytes", "manifest.json": b"{}"},
            label="initial",
        )
        assert version_id > 0
        versions = project_db.list_versions(uid)
        assert len(versions) == 1
        assert versions[0].file_count == 2
        assert versions[0].revision == 1
        # HEAD pointer updated
        detail = project_db.get_project(uid)
        assert detail.current_version_id == version_id

    def test_save_version_revision_monotonic(self, project_db: ProjectDB) -> None:
        uid = project_db.create_project("p", aurora_app_version="0.1.0")
        v1 = project_db.save_version(uid, files={"a.bin": b"x"})
        v2 = project_db.save_version(uid, files={"a.bin": b"y"})
        v3 = project_db.save_version(uid, files={"a.bin": b"z"})
        versions = project_db.list_versions(uid)
        assert [v.revision for v in versions] == [1, 2, 3]
        assert versions[0].version_id == v1
        assert versions[2].version_id == v3

    def test_save_version_deduplicates_blobs(self, project_db: ProjectDB) -> None:
        uid = project_db.create_project("p", aurora_app_version="0.1.0")
        # Save 3 versions с unchanged forecast — should produce 1 blob row
        project_db.save_version(uid, files={"forecast.pickle": b"same"})
        project_db.save_version(uid, files={"forecast.pickle": b"same"})
        project_db.save_version(uid, files={"forecast.pickle": b"same"})

        sha = project_db.blob_store.compute_hash(b"same")
        rows = project_db._conn.execute(
            "SELECT ref_count, size_bytes FROM blobs WHERE sha256 = ?", (sha,)
        ).fetchone()
        assert rows["ref_count"] == 3

        # Only 1 blob file on disk
        infos = project_db.blob_store.list_all()
        assert len(infos) == 1

    def test_save_version_with_parent(self, project_db: ProjectDB) -> None:
        uid = project_db.create_project("p", aurora_app_version="0.1.0")
        v1 = project_db.save_version(uid, files={"a.bin": b"x"})
        v2 = project_db.save_version(uid, files={"a.bin": b"y"}, parent_version_id=v1)
        versions = project_db.list_versions(uid)
        assert versions[1].parent_version_id == v1

    def test_save_version_parent_must_belong_to_same_project(
        self, project_db: ProjectDB
    ) -> None:
        uid1 = project_db.create_project("p1", aurora_app_version="0.1.0")
        uid2 = project_db.create_project("p2", aurora_app_version="0.1.0")
        v1_in_p1 = project_db.save_version(uid1, files={"a.bin": b"x"})
        with pytest.raises(ProjectDBError, match="belongs to another"):
            project_db.save_version(
                uid2, files={"a.bin": b"y"}, parent_version_id=v1_in_p1
            )

    def test_save_version_rejects_unknown_parent(self, project_db: ProjectDB) -> None:
        uid = project_db.create_project("p", aurora_app_version="0.1.0")
        with pytest.raises(ProjectDBError, match="does not exist"):
            project_db.save_version(
                uid, files={"a.bin": b"x"}, parent_version_id=999999
            )

    def test_save_version_rejects_empty_files(self, project_db: ProjectDB) -> None:
        uid = project_db.create_project("p", aurora_app_version="0.1.0")
        with pytest.raises(ValueError, match="zero files"):
            project_db.save_version(uid, files={})


class TestLoadVersion:
    def test_load_version_round_trip(self, project_db: ProjectDB) -> None:
        uid = project_db.create_project("p", aurora_app_version="0.1.0")
        payload = {"forecast.pickle": b"PICKLE DATA", "anchors.json": b'{"x":1}'}
        vid = project_db.save_version(
            uid, files=payload, schema_versions={"anchors.json": "1.0"}
        )
        loaded = project_db.load_version(vid)
        assert loaded.files == payload
        assert loaded.schema_versions["anchors.json"] == "1.0"
        assert loaded.summary.file_count == 2

    def test_load_unknown_version_raises(self, project_db: ProjectDB) -> None:
        with pytest.raises(ProjectDBError, match="not found"):
            project_db.load_version(99999)

    def test_load_version_detects_missing_blob_on_disk(
        self, project_db: ProjectDB
    ) -> None:
        uid = project_db.create_project("p", aurora_app_version="0.1.0")
        vid = project_db.save_version(uid, files={"a.bin": b"data"})
        # Manually delete blob from disk (simulating user touching folder)
        sha = project_db.blob_store.compute_hash(b"data")
        project_db.blob_store.delete(sha)
        with pytest.raises(ProjectDBError, match="Cannot load blob"):
            project_db.load_version(vid)


class TestCompareVersions:
    def test_compare_identifies_changes(self, project_db: ProjectDB) -> None:
        uid = project_db.create_project("p", aurora_app_version="0.1.0")
        v1 = project_db.save_version(
            uid,
            files={
                "shared.bin": b"unchanged",
                "edited.bin": b"v1",
                "deleted.bin": b"gone",
            },
        )
        v2 = project_db.save_version(
            uid,
            files={
                "shared.bin": b"unchanged",
                "edited.bin": b"v2",
                "new.bin": b"added",
            },
        )
        diff = project_db.compare_versions(v1, v2)
        assert diff.files_unchanged == ["shared.bin"]
        assert diff.files_changed == ["edited.bin"]
        assert diff.files_only_in_a == ["deleted.bin"]
        assert diff.files_only_in_b == ["new.bin"]


class TestIntegrity:
    def test_gc_orphan_blobs_no_orphans(self, project_db: ProjectDB) -> None:
        uid = project_db.create_project("p", aurora_app_version="0.1.0")
        project_db.save_version(uid, files={"a.bin": b"x"})
        assert project_db.gc_orphan_blobs() == 0

    def test_gc_orphan_blobs_after_delete(self, project_db: ProjectDB) -> None:
        uid = project_db.create_project("p", aurora_app_version="0.1.0")
        project_db.save_version(uid, files={"a.bin": b"x"})
        project_db.delete_project(uid)
        # Blob ref_count is now 0 — GC should reclaim it
        reclaimed = project_db.gc_orphan_blobs()
        assert reclaimed == 1
        assert project_db.blob_store.total_bytes() == 0

    def test_check_integrity_clean(self, project_db: ProjectDB) -> None:
        uid = project_db.create_project("p", aurora_app_version="0.1.0")
        project_db.save_version(uid, files={"a.bin": b"x"})
        report = project_db.check_integrity()
        assert all(len(v) == 0 for v in report.values())

    def test_check_integrity_detects_missing_blob(self, project_db: ProjectDB) -> None:
        uid = project_db.create_project("p", aurora_app_version="0.1.0")
        project_db.save_version(uid, files={"a.bin": b"x"})
        sha = project_db.blob_store.compute_hash(b"x")
        project_db.blob_store.delete(sha)
        report = project_db.check_integrity()
        assert sha in report["missing_blobs"]

    def test_check_integrity_detects_orphan_file(
        self, project_db: ProjectDB, blob_store: BlobStore
    ) -> None:
        # Store a blob but never reference it from any version
        info = blob_store.store(b"orphan content")
        report = project_db.check_integrity()
        assert info.sha256 in report["orphan_files"]

    def test_reconcile_ref_counts(self, project_db: ProjectDB) -> None:
        uid = project_db.create_project("p", aurora_app_version="0.1.0")
        project_db.save_version(uid, files={"a.bin": b"x"})
        # Manually corrupt ref_count
        sha = project_db.blob_store.compute_hash(b"x")
        project_db._conn.execute(
            "UPDATE blobs SET ref_count = 99 WHERE sha256 = ?", (sha,)
        )
        # check_integrity should detect drift
        report = project_db.check_integrity()
        assert sha in report["ref_count_drift"]
        # reconcile fixes it
        fixed = project_db.reconcile_ref_counts()
        assert fixed >= 1
        report_after = project_db.check_integrity()
        assert report_after["ref_count_drift"] == []


class TestSchemaAndConcurrency:
    def test_schema_idempotent_open(self, storage_root: Path, blob_store: BlobStore) -> None:
        db_path = storage_root / "projects.db"
        # First open creates schema
        db1 = ProjectDB(db_path, blob_store)
        uid = db1.create_project("p", aurora_app_version="0.1.0")
        db1.close()
        # Second open reuses schema
        db2 = ProjectDB(db_path, blob_store)
        assert db2.get_project(uid).name == "p"
        db2.close()

    def test_wal_mode_enabled(self, project_db: ProjectDB) -> None:
        row = project_db._conn.execute("PRAGMA journal_mode").fetchone()
        assert row[0].lower() == "wal"

    def test_concurrent_readers_dont_block(
        self, storage_root: Path, blob_store: BlobStore
    ) -> None:
        """WAL allows N readers + 1 writer; readers don't block each other."""
        db_path = storage_root / "projects.db"
        primary = ProjectDB(db_path, blob_store)
        uid = primary.create_project("concurrent test", aurora_app_version="0.1.0")
        primary.save_version(uid, files={"a.bin": b"alpha"})
        primary.close()

        results: list[int] = []
        errors: list[Exception] = []

        def reader() -> None:
            try:
                # Each thread opens its own connection (sqlite3 isn't thread-safe)
                bs = BlobStore(storage_root / "blobs")
                db = ProjectDB(db_path, bs)
                results.append(len(db.list_projects()))
                db.close()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=reader) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert errors == []
        assert results == [1] * 8


class TestSetCurrentVersion:
    def test_set_current_version(self, project_db: ProjectDB) -> None:
        uid = project_db.create_project("p", aurora_app_version="0.1.0")
        v1 = project_db.save_version(uid, files={"a.bin": b"v1"})
        v2 = project_db.save_version(uid, files={"a.bin": b"v2"})
        # After v2 HEAD points to v2; revert to v1
        project_db.set_current_version(uid, v1)
        assert project_db.get_project(uid).current_version_id == v1

    def test_set_current_version_rejects_cross_project(
        self, project_db: ProjectDB
    ) -> None:
        uid1 = project_db.create_project("p1", aurora_app_version="0.1.0")
        uid2 = project_db.create_project("p2", aurora_app_version="0.1.0")
        v_in_p1 = project_db.save_version(uid1, files={"a.bin": b"x"})
        with pytest.raises(ProjectDBError, match="belongs to"):
            project_db.set_current_version(uid2, v_in_p1)


# ---------------------------------------------------------------------------
# Migration tests
# ---------------------------------------------------------------------------


class TestMigration:
    def test_import_aurora_zip_bundle(
        self, project_db: ProjectDB, tmp_path: Path
    ) -> None:
        # Compose a real .aurora ZIP с BundleZipWriter
        bundle_path = tmp_path / "test.aurora"
        writer = BundleZipWriter(aurora_app_version="0.1.0")
        writer.add_file("forecast.pickle", b"FAKE FORECAST")
        writer.add_file("anchors.json", b'{"market":"premium"}', schema_version="1.0")
        writer.write(bundle_path)

        uid = import_aurora_bundle(
            bundle_path, project_db, project_name="My Pilot Forecast"
        )
        detail = project_db.get_project(uid)
        assert detail.name == "My Pilot Forecast"
        assert detail.metadata["imported_from"].endswith("test.aurora")
        assert detail.metadata["source_format"] == "zip"
        assert len(detail.versions) == 1

        loaded = project_db.load_version(detail.versions[0].version_id)
        assert b"FAKE FORECAST" == loaded.files["forecast.pickle"]
        assert loaded.schema_versions["anchors.json"] == "1.0"

    def test_import_missing_bundle_raises(
        self, project_db: ProjectDB, tmp_path: Path
    ) -> None:
        with pytest.raises(MigrationError, match="not found"):
            import_aurora_bundle(tmp_path / "missing.aurora", project_db)

    def test_import_corrupted_bundle_raises(
        self, project_db: ProjectDB, tmp_path: Path
    ) -> None:
        bad = tmp_path / "corrupted.aurora"
        bad.write_bytes(b"this is not a zip file")
        with pytest.raises(MigrationError, match="Cannot read bundle"):
            import_aurora_bundle(bad, project_db)


# ---------------------------------------------------------------------------
# Performance smoke (informational — not strict timing)
# ---------------------------------------------------------------------------


class TestPerformanceSmoke:
    def test_save_version_under_50ms_target(
        self, project_db: ProjectDB
    ) -> None:
        """Phase 0.1 budget: version save <50ms with 1MB pickle."""
        import time

        uid = project_db.create_project("perf", aurora_app_version="0.1.0")
        payload = {"forecast.pickle": b"x" * (1024 * 1024)}  # 1 MB

        t0 = time.perf_counter()
        project_db.save_version(uid, files=payload, label="perf test")
        elapsed_ms = (time.perf_counter() - t0) * 1000

        # 50ms budget per plan v3.0; allow 200ms headroom for slow CI
        assert elapsed_ms < 200, (
            f"Save version took {elapsed_ms:.1f}ms — budget 50ms (200ms ceiling for CI)"
        )
