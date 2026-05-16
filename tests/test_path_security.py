"""Phase 2.C — symlink/junction/path-traversal защита (H-4 + HE-1)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from aurora_launch.engines.path_security import (
    PathSecurityError,
    validate_safe_path,
)


@pytest.fixture
def allowed_root(tmp_path: Path) -> Path:
    return tmp_path


class TestReadPaths:
    def test_existing_file_in_allowed_root_passes(self, allowed_root: Path) -> None:
        f = allowed_root / "test.txt"
        f.write_text("hello")
        result = validate_safe_path(f, [allowed_root])
        assert result == f.resolve()

    def test_nonexistent_file_rejected(self, allowed_root: Path) -> None:
        with pytest.raises(PathSecurityError, match="не existует"):
            validate_safe_path(allowed_root / "missing.txt", [allowed_root])

    def test_path_outside_allowed_root_rejected(
        self, allowed_root: Path, tmp_path_factory
    ) -> None:
        other_root = tmp_path_factory.mktemp("isolated_root_a")
        outside = other_root / "outside.txt"
        outside.write_text("evil")
        with pytest.raises(PathSecurityError, match="вне allowed roots"):
            validate_safe_path(outside, [allowed_root])

    @pytest.mark.skipif(sys.platform == "win32", reason="symlink требует admin на Windows")
    def test_symlink_to_allowed_target_rejected(self, allowed_root: Path) -> None:
        target = allowed_root / "real.txt"
        target.write_text("safe")
        link = allowed_root / "link.txt"
        link.symlink_to(target)
        with pytest.raises(PathSecurityError, match="symlink"):
            validate_safe_path(link, [allowed_root])

    def test_traversal_attack_rejected(self, allowed_root: Path) -> None:
        # ../../etc/passwd — resolves outside allowed_root
        evil = allowed_root / ".." / ".." / "evil.txt"
        with pytest.raises(PathSecurityError):
            validate_safe_path(evil, [allowed_root])


class TestWritePaths:
    def test_new_file_in_allowed_root_passes(self, allowed_root: Path) -> None:
        target = allowed_root / "new.txt"  # ещё не существует
        result = validate_safe_path(target, [allowed_root], is_write=True)
        assert result.parent == allowed_root.resolve()

    def test_write_to_blocked_root_rejected(
        self, allowed_root: Path, tmp_path_factory
    ) -> None:
        blocked = tmp_path_factory.mktemp("isolated_root_b")
        target = blocked / "new.txt"
        with pytest.raises(PathSecurityError, match="вне allowed roots"):
            validate_safe_path(target, [allowed_root], is_write=True)

    def test_write_missing_parent_rejected(self, allowed_root: Path) -> None:
        nonexistent_parent = allowed_root / "missing" / "subdir" / "file.txt"
        with pytest.raises(PathSecurityError, match="parent dir не existует"):
            validate_safe_path(nonexistent_parent, [allowed_root], is_write=True)


class TestConfigurationErrors:
    def test_no_allowed_roots_rejects(self, allowed_root: Path) -> None:
        with pytest.raises(PathSecurityError, match="no allowed_roots"):
            validate_safe_path(allowed_root / "x.txt", [])

    def test_nonexistent_allowed_roots_filtered(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "missing_root"
        real = tmp_path / "real_root"
        real.mkdir()
        f = real / "test.txt"
        f.write_text("ok")
        # Должна пропустить — real root resolved, nonexistent skipped
        result = validate_safe_path(f, [nonexistent, real])
        assert result == f.resolve()
