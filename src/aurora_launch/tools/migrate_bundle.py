"""aurora-launch-migrate-bundle CLI — migrate `.aurora.json` (legacy) → `.aurora` ZIP.

Block 1A migration tool. Per ADR-002 §"Migration: Econometrica v2 pickle →
Launch v3 zip" pattern, adapted for the v0.1.0-b05 → ZIP transitional path.

Features:
- Single-file or batch (`--input-dir scan all *.aurora.json`)
- Dry-run mode (`--dry-run`) — print plan, do not write
- Automatic backup (.aurora.json.bak.{1..N}) before migration
- Validation: read back the new ZIP and verify composite hash matches
- Atomic: temp + rename, only on validation success

Customer data invariant: `.aurora` bundles cost 2-3 hours of training time
per proxy intake. Loss-of-data unacceptable. The migration tool ALWAYS:
1. Creates backup before write
2. Validates ZIP after write (integrity check + round-trip read)
3. Rolls back if any step fails

Usage:
    aurora-launch-migrate-bundle path/to/bundle.aurora.json
    aurora-launch-migrate-bundle path/to/bundle.aurora.json --dry-run
    aurora-launch-migrate-bundle --input-dir path/to/bundles/
    aurora-launch-migrate-bundle --input-dir path/to/bundles/ --dry-run
"""

from __future__ import annotations

import logging
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import click

from aurora_launch import __version__
from aurora_launch.engines.bundle_container import (
    BundleIntegrityError,
    BundleZipReader,
    BundleZipWriter,
    detect_format,
)

_log = logging.getLogger("aurora_launch.migrate_bundle")


@dataclass
class MigrationPlan:
    """What the migration tool will do for a single bundle."""

    source: Path
    target: Path  # final `.aurora` path (ZIP)
    backup: Path  # `.aurora.json.migrate-bak`
    will_skip: bool  # True if already ZIP or unrecognized
    skip_reason: str | None = None


def _plan(source: Path) -> MigrationPlan:
    """Determine what to do with a single bundle path."""
    fmt = detect_format(source)
    if fmt == "zip":
        return MigrationPlan(
            source=source,
            target=source,
            backup=source.with_suffix(source.suffix + ".migrate-bak"),
            will_skip=True,
            skip_reason="already ZIP format",
        )
    if fmt == "unknown":
        return MigrationPlan(
            source=source,
            target=source,
            backup=source.with_suffix(source.suffix + ".migrate-bak"),
            will_skip=True,
            skip_reason="unrecognized format (not ZIP, not JSON)",
        )

    # JSON legacy → migrate.
    # Source: foo.aurora.json → Target: foo.aurora (drops `.json` suffix)
    if source.suffix == ".json" and source.stem.endswith(".aurora"):
        target = source.with_suffix("")  # foo.aurora.json → foo.aurora
    else:
        target = source.with_suffix(".aurora")
    backup = source.with_suffix(source.suffix + ".migrate-bak")
    return MigrationPlan(source=source, target=target, backup=backup, will_skip=False)


def _migrate_one(plan: MigrationPlan, *, dry_run: bool, force: bool = False) -> bool:
    """Execute migration for a single bundle. Returns True on success.

    Steps (rollback-safe):
    1. Read legacy JSON via BundleZipReader (synthesizes manifest)
    2. Build new BundleZipWriter, copy `legacy_bundle.json` entry as-is
    3. Write to temp ZIP file (NOT target yet)
    4. Read back temp ZIP, verify composite hash
    5. Backup source: shutil.copy2 to plan.backup
    6. Atomic rename: temp ZIP → target
    7. (If target != source) optionally remove source after successful rename

    Audit (post-1D extended): refuses to overwrite an existing distinct
    `target` без `--force`. Previously a re-run would silently clobber
    a prior migration's output (`os.replace` is unconditional).

    On any failure, temp file deleted, source untouched.
    """
    # Pre-flight overwrite check — only meaningful when target != source
    # (when target == source we are converting in place, замещение ожидается).
    if plan.target != plan.source and plan.target.exists() and not force:
        click.echo(
            f"  ✗ REFUSED: target already exists: {plan.target.name}. "
            f"Re-run with --force to overwrite.",
            err=True,
        )
        return False

    if dry_run:
        click.echo(f"  [DRY-RUN] would migrate: {plan.source}")
        click.echo(f"           → target: {plan.target}")
        click.echo(f"           → backup: {plan.backup}")
        if plan.target.exists() and plan.target != plan.source:
            click.echo(f"           ⚠ target exists; --force {'set' if force else 'NOT set'}")
        return True

    try:
        # Step 1: read legacy
        loaded = BundleZipReader(verify_integrity=False).read(plan.source)

        # Step 2: build ZIP writer with legacy_bundle.json entry preserved
        writer = BundleZipWriter(
            aurora_app_version=loaded.manifest.aurora_app_version
            if loaded.manifest.aurora_app_version != "unknown"
            else __version__,
            min_app_version=loaded.manifest.min_app_version,
            project_id=loaded.manifest.project_id,
            integrity_check="strict",
            compression="store",
        )

        for entry_name, content in loaded.files.items():
            schema_v = (
                loaded.manifest.files[entry_name].schema_version
                if entry_name in loaded.manifest.files
                else None
            )
            writer.add_file(entry_name, content, schema_version=schema_v)

        # Step 3: write to temp ZIP (sibling of target so atomic rename works
        # within same filesystem)
        tmp_dir = plan.target.parent
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=".aurora.tmp-migrate",
            dir=tmp_dir,
            delete=False,
        ) as tmpf:
            tmp_path = Path(tmpf.name)

        zip_bytes, new_manifest = writer.to_zip_bytes()
        tmp_path.write_bytes(zip_bytes)

        # Step 4: validate via read-back
        verify_loaded = BundleZipReader().read(tmp_path)
        verify_hash = verify_loaded.composite_bundle_hash()
        expected_hash = new_manifest.composite_bundle_hash()
        if verify_hash != expected_hash:
            raise BundleIntegrityError(
                f"Round-trip hash mismatch: expected {expected_hash}, got {verify_hash}"
            )

        # Step 5: backup source
        if plan.backup.exists():
            plan.backup.unlink()
        shutil.copy2(plan.source, plan.backup)

        # Step 6: atomic finalize
        # If target == source path (same name, different format), one rename.
        # If target != source, write target then remove source.
        import os

        if plan.target == plan.source:
            os.replace(tmp_path, plan.target)
        else:
            os.replace(tmp_path, plan.target)
            # Source file (legacy `.aurora.json`) is NOT deleted automatically —
            # the .migrate-bak is the safety copy, the original is left as-is
            # for explicit user removal. Keep blast radius small.

        click.echo(f"  ✓ migrated: {plan.source.name} → {plan.target.name}")
        click.echo(f"    backup:   {plan.backup.name}")
        click.echo(f"    hash:     {verify_hash[:16]}...")
        return True

    except Exception as exc:
        click.echo(f"  ✗ FAILED: {plan.source.name} — {type(exc).__name__}: {exc}", err=True)
        # Cleanup temp if it was created
        try:
            if "tmp_path" in locals():
                tmp_path.unlink(missing_ok=True)  # type: ignore[name-defined]
        except OSError:
            pass
        return False


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------


@click.command()
@click.argument("source", type=click.Path(exists=False, path_type=Path), required=False)
@click.option(
    "--input-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Batch mode — scan directory for *.aurora.json files.",
)
@click.option("--dry-run", is_flag=True, help="Print plan without writing.")
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing target file. Без флага migration refuses to "
    "clobber a target that already exists (e.g., from a previous migration).",
)
@click.version_option(version=__version__)
def main(source: Path | None, input_dir: Path | None, dry_run: bool, force: bool) -> None:
    """Migrate Aurora Launch bundles from `.aurora.json` (legacy) to `.aurora` ZIP.

    Pass either a single SOURCE file path, or use --input-dir for batch mode.

    Always creates a `.migrate-bak` backup of the source before migration.
    Validates by reading back the new ZIP and verifying composite hash.

    Refuses to overwrite an existing target unless --force is set (post-1D
    audit fix — protects against silent data loss on accidental re-runs).
    """
    if not source and not input_dir:
        click.echo("ERROR: provide SOURCE path or --input-dir", err=True)
        sys.exit(2)

    if source and input_dir:
        click.echo("ERROR: provide either SOURCE or --input-dir, not both", err=True)
        sys.exit(2)

    plans: list[MigrationPlan] = []
    if source:
        if not source.exists():
            click.echo(f"ERROR: file not found: {source}", err=True)
            sys.exit(2)
        plans.append(_plan(source))
    else:
        assert input_dir is not None
        candidates = sorted(input_dir.glob("*.aurora.json"))
        if not candidates:
            click.echo(f"No *.aurora.json files in {input_dir}", err=True)
            sys.exit(0)
        plans = [_plan(p) for p in candidates]

    click.echo(f"Plan: {len(plans)} bundle(s)")
    if dry_run:
        click.echo("--dry-run mode: no files will be modified.")
    click.echo("")

    successes = 0
    failures = 0
    skipped = 0
    for plan in plans:
        if plan.will_skip:
            click.echo(f"  - skip: {plan.source.name} ({plan.skip_reason})")
            skipped += 1
            continue
        if _migrate_one(plan, dry_run=dry_run, force=force):
            successes += 1
        else:
            failures += 1

    click.echo("")
    click.echo(f"Done: {successes} migrated, {skipped} skipped, {failures} failed")
    if failures > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
