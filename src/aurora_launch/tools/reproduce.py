"""aurora-launch-reproduce CLI — BLOCKER B1 deliverable.

Headless reproducibility check tool. Used in Methodology Certificate recipe:
    `aurora-launch-reproduce <bundle.aurora.json> <expected_hash>`

Exit codes:
    0 — hash matches expected (within JCS canonical, NOT bit-exact pickle)
    1 — hash mismatch (file tampered or wrong expected_hash)
    2 — error (file not found, parse failure, version skew)

Per PHASE_B_REQUIREMENTS.md §4.1.5 — `reproduce_check`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from aurora_launch import __version__
from aurora_launch.engines.corpus_generator.generator import compute_bundle_hash


@click.command()
@click.argument("bundle_path", type=click.Path(exists=True, path_type=Path))
@click.argument("expected_hash", type=str)
@click.option(
    "--rtol",
    type=float,
    default=1e-4,
    help="Relative tolerance для floating-point comparison (default 1e-4 deterministic).",
)
@click.option(
    "--check-mode",
    type=click.Choice(["manifest", "reproducibility_token"]),
    default="manifest",
    help="Which hash to verify (default: manifest_sha256).",
)
@click.option(
    "--json-output",
    is_flag=True,
    help="Output JSON to stdout (для CI/CD scripting).",
)
@click.version_option(version=__version__)
def main(
    bundle_path: Path,
    expected_hash: str,
    rtol: float,
    check_mode: str,
    json_output: bool,
) -> None:
    """Verify reproducibility of an Aurora Launch .aurora bundle.

    Compares stored hash against expected_hash. Exit 0 = match, 1 = mismatch.
    """
    result: dict[str, object] = {
        "tool": "aurora-launch-reproduce",
        "tool_version": __version__,
        "bundle_path": str(bundle_path),
        "expected_hash": expected_hash,
        "check_mode": check_mode,
        "rtol_used": rtol,
    }

    # FIX H-Audit-1: version skew check
    try:
        with bundle_path.open("r", encoding="utf-8") as f:
            bundle_preview = json.load(f)
        bundle_version = bundle_preview.get("aurora_launch_version", "unknown")
    except (OSError, json.JSONDecodeError) as exc:
        result["status"] = "error"
        result["error"] = f"Cannot read bundle: {exc}"
        _emit_result(result, json_output)
        sys.exit(2)

    result["bundle_aurora_launch_version"] = bundle_version
    result["tool_aurora_launch_version"] = __version__

    if bundle_version != __version__:
        result["version_skew_warning"] = (
            f"Bundle was created с Aurora Launch {bundle_version}, "
            f"but verifying с {__version__}. "
            f"Hashes may legitimately differ across versions. "
            f"For exact reproduction, install matching version."
        )

    try:
        manifest_hash, repro_token = compute_bundle_hash(bundle_path)
    except json.JSONDecodeError as exc:
        result["status"] = "error"
        result["error"] = f"Bundle not valid JSON: {exc}"
        _emit_result(result, json_output)
        sys.exit(2)
    except ValueError as exc:
        # Internal manifest или repro_token hash mismatch — bundle corrupted/tampered
        result["status"] = "error"
        result["error"] = str(exc)
        _emit_result(result, json_output)
        sys.exit(2)
    except Exception as exc:
        result["status"] = "error"
        result["error"] = f"Unexpected: {type(exc).__name__}: {exc}"
        _emit_result(result, json_output)
        sys.exit(2)

    actual_hash = manifest_hash if check_mode == "manifest" else repro_token
    result["computed_hash"] = actual_hash

    if actual_hash == expected_hash:
        result["status"] = "match"
        result["verdict"] = "Bundle reproducibility verified."
        _emit_result(result, json_output)
        sys.exit(0)
    else:
        result["status"] = "mismatch"
        result["verdict"] = (
            f"Bundle hash mismatch. Expected {expected_hash}, "
            f"got {actual_hash}. Bundle may have been tampered or "
            f"reproduced with different Aurora Launch version."
        )
        _emit_result(result, json_output)
        sys.exit(1)


def _emit_result(result: dict, json_output: bool) -> None:
    """Output result to stdout."""
    if json_output:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        status = result.get("status", "unknown")
        if status == "match":
            click.secho("✓ ", fg="green", nl=False)
            click.echo(result.get("verdict", ""))
            click.echo(f"  Hash: {result.get('computed_hash', '')}")
        elif status == "mismatch":
            click.secho("✗ ", fg="red", nl=False)
            click.echo(result.get("verdict", ""))
            click.echo(f"  Expected: {result.get('expected_hash', '')}")
            click.echo(f"  Computed: {result.get('computed_hash', '')}")
        else:
            click.secho("⚠ Error: ", fg="yellow", nl=False)
            click.echo(result.get("error", ""))


if __name__ == "__main__":
    main()
