"""Path security validation — закрывает H-4 (symlink/junction defense).

SO-4: pure function, не class. State-free, side-effect-free. Trivial test
matrix. Reused в 4 file I/O entry points (Phase 2.C).
"""

from __future__ import annotations

import os
from pathlib import Path


class PathSecurityError(ValueError):
    """Raised when path violates security policy.

    HE-1 distinction:
    - is_write=False (read paths): path должен existовать + быть real file
      under allowed root. Strict=True resolve fails если symlink target
      outside allowed root.
    - is_write=True (write paths): file ещё не существует. Validate parent
      directory (strict=True) — она должна existовать + быть в allowed
      root + не быть symlink/junction.
    """


def validate_safe_path(
    path: Path | str,
    allowed_roots: list[Path],
    *,
    is_write: bool = False,
) -> Path:
    """Return resolved Path если path valid, raise PathSecurityError если нет.

    Args:
        path: user-supplied file path
        allowed_roots: list of directories разрешённых для I/O (e.g.,
            APPDATA / Documents / Downloads / temp). Каждый root тоже
            resolve-strict проверяется. Empty list → all paths denied.
        is_write: True для write operations (target file may not exist
            yet). HE-1 fix: для write — resolve без strict + validate
            parent. Без этого create_file в allowed dir → FileNotFoundError.

    Raises:
        PathSecurityError: symlink / junction / outside allowed root /
            path traversal / no allowed roots.

    Returns:
        Resolved Path object (absolute, symlinks followed only при is_write=False).
    """
    if not allowed_roots:
        raise PathSecurityError("no allowed_roots configured — все paths denied")

    p = Path(path)

    # Resolve allowed_roots strictly — каждая должна existовать
    resolved_roots: list[Path] = []
    for root in allowed_roots:
        try:
            resolved_roots.append(Path(root).resolve(strict=True))
        except (OSError, FileNotFoundError):
            # Defensive: missing root configured — skip (но не fatal)
            continue

    if not resolved_roots:
        raise PathSecurityError(
            f"no allowed_roots resolved (raw: {[str(r) for r in allowed_roots]})"
        )

    if is_write:
        # HE-1: для writes — target может не existовать ещё. Validate parent.
        try:
            parent_resolved = p.parent.resolve(strict=True)
        except (OSError, FileNotFoundError):
            raise PathSecurityError(
                f"write target parent dir не existует: {p.parent}"
            )

        # Reject if parent is symlink/junction (parent.is_symlink на parent
        # check'нет если parent сам symlink)
        if p.parent.is_symlink():
            raise PathSecurityError(
                f"parent directory является symlink/junction: {p.parent}"
            )

        if not any(parent_resolved.is_relative_to(root) for root in resolved_roots):
            raise PathSecurityError(
                f"write target parent {parent_resolved} вне allowed roots: "
                f"{[str(r) for r in resolved_roots]}"
            )

        # Возвращаем resolved (с unresolved leaf) — для write open()
        return parent_resolved / p.name

    # Read path: file must existовать + be regular file under allowed root
    try:
        resolved = p.resolve(strict=True)
    except (OSError, FileNotFoundError):
        raise PathSecurityError(f"path не existует: {p}")

    # Symlink check на input — если оригинал symlink, reject (даже если
    # target в allowed root — opaque escalation surface)
    if p.is_symlink():
        raise PathSecurityError(f"путь является symlink: {p}")

    if not any(resolved.is_relative_to(root) for root in resolved_roots):
        raise PathSecurityError(
            f"путь {resolved} вне allowed roots: {[str(r) for r in resolved_roots]}"
        )

    return resolved
