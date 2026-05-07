"""Main synthetic corpus project generator (B0.5 §4.1.5).

Generates `.aurora`-equivalent JSON bundle structure (since real `.aurora` ZIP
container requires Phase A C6 SchemaRegistry — using JSON as v0.1.0-b05
intermediate representation).

JSON structure mirrors `.aurora` bundle layout:
- manifest.json (SSoT с integrity hashes)
- structured Pydantic data в JSON (metadata, weekly_data)
- response_params (would be `.pickle` в production)

Per PHASE_B_REQUIREMENTS.md §4.1.5 — `generate_synthetic_project` returns Path.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import get_args

import rfc8785

from aurora_launch import __version__
from aurora_launch.engines.corpus_generator.synthesis import synthesize_project_data
from aurora_launch.schemas.synthetic_corpus import CategoryL3, SyntheticProjectSpec


def list_corpus_categories() -> list[str]:
    """Returns list of supported category_l3 values (per CategoryL3 Literal)."""
    return list(get_args(CategoryL3))


def generate_synthetic_project(
    spec: SyntheticProjectSpec,
    output_dir: Path,
) -> Path:
    """Generate synthetic project as JSON bundle.

    Returns path to generated `.aurora.json` file (JSON intermediate за
    отсутствием Phase A C6 ZIP container в v0.1.0-b05).

    Properties:
    - Same seed → identical bundle hash (deterministic)
    - JCS canonical hash stable across machines
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Synthesize MMM data
    project_data = synthesize_project_data(spec)

    # Compose bundle layout
    bundle = {
        "schema_version": "3.0",
        "aurora_launch_version": __version__,
        "project_type": "synthetic_corpus",
        "spec": spec.model_dump(),
        "data": project_data,
    }

    # Compute JCS canonical hash (cross-platform deterministic)
    canonical_bytes = rfc8785.dumps(bundle)
    manifest_sha256 = hashlib.sha256(canonical_bytes).hexdigest()

    # Manifest со integrity
    bundle["manifest_sha256"] = manifest_sha256

    # Reproducibility token — per PHASE_B_REQUIREMENTS.md §4.2 composite signing
    # token = hash(manifest_sha256 || canonical_data_hash || version)
    repro_input = (
        manifest_sha256.encode("utf-8")
        + hashlib.sha256(canonical_bytes).digest()
        + __version__.encode("utf-8")
    )
    reproducibility_token = hashlib.sha256(repro_input).hexdigest()
    bundle["reproducibility_token"] = reproducibility_token

    # Filename: <category>_<variant>_seed<N>.aurora.json
    safe_category = spec.category_l3.replace(".", "_")
    filename = f"{safe_category}_{spec.variant}_seed{spec.seed}.aurora.json"
    output_path = output_dir / filename

    # Write JSON (pretty-formatted for human inspection)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2, ensure_ascii=False)

    return output_path


def compute_bundle_hash(bundle_path: Path) -> tuple[str, str]:
    """Compute (manifest_sha256, reproducibility_token) of existing bundle.

    Used by `aurora-launch-reproduce` для verification.
    """
    with bundle_path.open("r", encoding="utf-8") as f:
        bundle = json.load(f)

    expected_manifest = bundle.get("manifest_sha256")
    expected_repro_token = bundle.get("reproducibility_token")

    # Verify manifest_sha256 by recomputing
    bundle_for_hash = {k: v for k, v in bundle.items() if k not in ("manifest_sha256", "reproducibility_token")}
    canonical_bytes = rfc8785.dumps(bundle_for_hash)
    computed_manifest = hashlib.sha256(canonical_bytes).hexdigest()

    if computed_manifest != expected_manifest:
        raise ValueError(
            f"Manifest hash mismatch in bundle: "
            f"expected {expected_manifest}, computed {computed_manifest}"
        )

    return computed_manifest, expected_repro_token
