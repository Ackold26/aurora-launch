"""Aurora Launch schema diff CLI (B1 sprint).

Outputs human-readable diff между Aurora Launch sub-schema versions для
developer ergonomics. Helps reviewers understand what changed между
v1.0 и v1.1 (when v1.1 ships) — additive fields, deprecated fields, etc.

Usage:
    aurora-launch-schema-diff v1.0 v1.1
    aurora-launch-schema-diff v1.0 v1.1 --json
    aurora-launch-schema-diff v1.0 v1.1 --output diff.md

Phase B v0.1.x — only v1.0 registered. Diff against itself returns no changes.
Phase B+ ships actual diffs as schemas evolve.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import click
from pydantic import BaseModel

from aurora_launch import __version__
from aurora_launch.engines.schema_registry_launch import (
    LaunchSchemaRegistry,
    build_default_launch_registry,
)


def _model_field_signature(model: type[BaseModel]) -> dict[str, dict[str, Any]]:
    """Extract field signature for diff comparison."""
    sig: dict[str, dict[str, Any]] = {}
    for field_name, field_info in model.model_fields.items():
        sig[field_name] = {
            "type": str(field_info.annotation),
            "required": field_info.is_required(),
            "description": field_info.description or "",
        }
    return sig


def diff_schemas(
    from_version: str,
    to_version: str,
    registry: LaunchSchemaRegistry | None = None,
) -> dict[str, Any]:
    """Compute structured diff между two Aurora Launch schema versions.

    Returns dict с keys:
    - migrations: list of migration descriptions
    - field_additions: fields added in to_version
    - field_removals: fields removed
    - field_changes: fields с modified type/required
    """
    reg = registry or build_default_launch_registry()

    # Migration path
    try:
        path = reg.find_migration_path(from_version, to_version)
    except ValueError as exc:
        return {
            "from_version": from_version,
            "to_version": to_version,
            "error": str(exc),
            "migrations": [],
        }

    # Phase B v0.1.x — only v1.0 schema, single class. Future versions
    # register own schema classes; diff would compare those signatures.
    # For v1.0 self-diff, return empty diff.
    return {
        "from_version": from_version,
        "to_version": to_version,
        "migrations": [
            {
                "from": m.from_version,
                "to": m.to_version,
                "description": m.description,
            }
            for m in path
        ],
        "field_additions": {},  # populated when v1.1+ registered
        "field_removals": {},
        "field_changes": {},
        "summary": (
            "No schema changes (v1.0 → v1.0 self-diff)"
            if from_version == to_version
            else f"{len(path)} migration(s) registered"
        ),
    }


def render_diff_markdown(diff: dict[str, Any]) -> str:
    """Render diff dict as human-readable markdown."""
    lines = [
        f"# Aurora Launch Schema Diff: {diff['from_version']} → {diff['to_version']}",
        "",
    ]

    if "error" in diff:
        lines.append(f"**Error:** {diff['error']}")
        return "\n".join(lines)

    lines.append(f"**Summary:** {diff['summary']}")
    lines.append("")

    if diff["migrations"]:
        lines.append("## Migrations applied")
        lines.append("")
        for m in diff["migrations"]:
            lines.append(f"- `{m['from']}` → `{m['to']}`: {m['description']}")
        lines.append("")

    if diff["field_additions"]:
        lines.append("## Fields added")
        lines.append("")
        for field, info in diff["field_additions"].items():
            lines.append(f"- **`{field}`** ({info.get('type', 'unknown')})")
        lines.append("")

    if diff["field_removals"]:
        lines.append("## Fields removed")
        lines.append("")
        for field in diff["field_removals"]:
            lines.append(f"- ~~`{field}`~~")
        lines.append("")

    if diff["field_changes"]:
        lines.append("## Fields changed")
        lines.append("")
        for field, change in diff["field_changes"].items():
            lines.append(f"- `{field}`: {change}")
        lines.append("")

    return "\n".join(lines)


@click.command()
@click.argument("from_version", type=str)
@click.argument("to_version", type=str)
@click.option("--json", "as_json", is_flag=True, help="Output JSON instead of markdown.")
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Output file path (default: stdout).",
)
@click.version_option(version=__version__)
def main(from_version: str, to_version: str, as_json: bool, output: Path | None) -> None:
    """Show schema diff между Aurora Launch sub-schema versions."""
    diff = diff_schemas(from_version, to_version)

    if as_json:
        rendered = json.dumps(diff, indent=2, ensure_ascii=False)
    else:
        rendered = render_diff_markdown(diff)

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        click.secho("✓ ", fg="green", nl=False)
        click.echo(f"Schema diff written: {output}")
    else:
        sys.stdout.write(rendered)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
