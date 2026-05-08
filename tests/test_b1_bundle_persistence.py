"""Tests for B1 bundle atomic write + rolling backup rotation."""

from __future__ import annotations

from pathlib import Path

import pytest

from aurora_launch.engines.bundle_persistence import (
    DEFAULT_BACKUP_COUNT,
    atomic_write_bundle,
    cleanup_orphan_tmp_files,
    list_backups,
    restore_from_backup,
)


class TestAtomicWrite:
    def test_writes_new_file(self, tmp_path: Path) -> None:
        path = tmp_path / "test.aurora.json"
        atomic_write_bundle(path, b"content_v1")
        assert path.exists()
        assert path.read_bytes() == b"content_v1"
        # No tmp orphan
        assert not Path(f"{path}.tmp").exists()

    def test_overwrite_creates_backup(self, tmp_path: Path) -> None:
        path = tmp_path / "test.aurora.json"
        atomic_write_bundle(path, b"v1")
        atomic_write_bundle(path, b"v2")

        # Current = v2
        assert path.read_bytes() == b"v2"
        # Backup .bak.1 = v1
        bak1 = Path(f"{path}.bak.1")
        assert bak1.exists()
        assert bak1.read_bytes() == b"v1"

    def test_rotation_drops_oldest(self, tmp_path: Path) -> None:
        """After 5 writes (with backup_count=4): newest kept + 4 backups rotated."""
        path = tmp_path / "test.aurora.json"
        for i in range(1, 6):
            atomic_write_bundle(path, f"v{i}".encode())

        # Current = v5
        assert path.read_bytes() == b"v5"
        # bak.1 = v4 (most recent backup)
        assert Path(f"{path}.bak.1").read_bytes() == b"v4"
        # bak.2 = v3
        assert Path(f"{path}.bak.2").read_bytes() == b"v3"
        # bak.3 = v2
        assert Path(f"{path}.bak.3").read_bytes() == b"v2"
        # bak.4 = v1
        assert Path(f"{path}.bak.4").read_bytes() == b"v1"

    def test_rotation_drops_oldest_after_6_writes(self, tmp_path: Path) -> None:
        path = tmp_path / "test.aurora.json"
        for i in range(1, 7):
            atomic_write_bundle(path, f"v{i}".encode())

        # Current = v6, bak.1 = v5, bak.4 = v2 (v1 dropped — exceeded backup_count=4)
        assert path.read_bytes() == b"v6"
        assert Path(f"{path}.bak.1").read_bytes() == b"v5"
        assert Path(f"{path}.bak.4").read_bytes() == b"v2"
        # No .bak.5 (count limit enforced)
        assert not Path(f"{path}.bak.5").exists()

    def test_orphan_tmp_cleaned_on_next_write(self, tmp_path: Path) -> None:
        """If previous write left .tmp orphan — cleaned at next write start."""
        path = tmp_path / "test.aurora.json"
        # Simulate orphan from interrupted previous write
        Path(f"{path}.tmp").write_bytes(b"interrupted_content")

        atomic_write_bundle(path, b"clean_write")

        assert path.read_bytes() == b"clean_write"
        assert not Path(f"{path}.tmp").exists()


class TestRestoreFromBackup:
    def test_restore_default_index_1(self, tmp_path: Path) -> None:
        path = tmp_path / "test.aurora.json"
        atomic_write_bundle(path, b"v1")
        atomic_write_bundle(path, b"v2")

        # Corrupt current
        path.write_bytes(b"corrupted")

        # Restore default (.bak.1)
        result = restore_from_backup(path)
        assert result is True
        assert path.read_bytes() == b"v1"

        # Backup still available для second restore (copy, not move)
        assert Path(f"{path}.bak.1").exists()

    def test_restore_specific_index(self, tmp_path: Path) -> None:
        path = tmp_path / "test.aurora.json"
        for i in range(1, 5):
            atomic_write_bundle(path, f"v{i}".encode())

        # bak.3 should be v1
        result = restore_from_backup(path, backup_index=3)
        assert result is True
        assert path.read_bytes() == b"v1"

    def test_restore_missing_backup_returns_false(self, tmp_path: Path) -> None:
        path = tmp_path / "nonexistent.aurora.json"
        result = restore_from_backup(path, backup_index=1)
        assert result is False


class TestListBackups:
    def test_lists_existing_only(self, tmp_path: Path) -> None:
        path = tmp_path / "test.aurora.json"
        # Only 2 writes — bak.1 + bak.2 не yet (depends on rotation)
        atomic_write_bundle(path, b"v1")
        atomic_write_bundle(path, b"v2")

        backups = list_backups(path)
        # Only .bak.1 should exist (only 1 prior write rotated)
        assert len(backups) == 1


class TestCleanupOrphanTmp:
    def test_cleans_orphan_tmp_files(self, tmp_path: Path) -> None:
        # Create some orphan .tmp files
        (tmp_path / "a.aurora.tmp").write_bytes(b"orphan1")
        (tmp_path / "b.aurora.tmp").write_bytes(b"orphan2")
        (tmp_path / "regular.txt").write_bytes(b"keep")

        cleaned = cleanup_orphan_tmp_files(tmp_path)
        assert cleaned == 2
        assert not (tmp_path / "a.aurora.tmp").exists()
        assert not (tmp_path / "b.aurora.tmp").exists()
        assert (tmp_path / "regular.txt").exists()  # non-tmp untouched

    def test_no_orphans_returns_zero(self, tmp_path: Path) -> None:
        cleaned = cleanup_orphan_tmp_files(tmp_path)
        assert cleaned == 0


class TestBackupCountInvariants:
    def test_default_backup_count_is_4(self) -> None:
        assert DEFAULT_BACKUP_COUNT == 4

    @pytest.mark.parametrize("count", [1, 2, 3, 4, 5, 8])
    def test_custom_backup_count(self, tmp_path: Path, count: int) -> None:
        path = tmp_path / "test.aurora.json"
        for i in range(1, count + 3):  # write count+2 versions
            atomic_write_bundle(path, f"v{i}".encode(), backup_count=count)

        # Verify backup chain length
        existing_backups = [
            Path(f"{path}.bak.{i}") for i in range(1, count + 1)
            if Path(f"{path}.bak.{i}").exists()
        ]
        assert len(existing_backups) == count
