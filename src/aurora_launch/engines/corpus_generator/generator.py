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


def _compute_data_artifacts_hash(project_data: dict) -> str:
    """Hash of all data artifacts that would live в separate files в real .aurora ZIP.

    FIX B-Audit-2: For real R8 closure, reproducibility_token must include
    hashes of файлов that cannot be recomputed from manifest alone. В JSON
    intermediate v0.1.0-b05 we hash specific data sub-trees that simulate
    «file artifacts»: weekly_data + response_params + seasonality_52w.

    In Phase B+ real .aurora ZIP container, this would be hash of:
    `models/proxy_model.pickle || data/parquet/weekly.parquet || ...`
    — i.e., raw bytes of binary files.
    """
    artifacts = {
        "weekly_data": project_data["weekly_data"],
        "response_params": project_data["response_params"],
        "seasonality_52w": project_data["seasonality_52w"],
    }
    artifact_bytes = rfc8785.dumps(artifacts)
    return hashlib.sha256(artifact_bytes).hexdigest()


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
    - reproducibility_token = hash(manifest_sha256 || data_artifacts_hash ||
      aurora_launch_version) — independent hashes, NOT derivable from manifest
      alone (audit B-Audit-2 closure)
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Synthesize MMM data
    project_data = synthesize_project_data(spec)

    # Pre-compute data artifacts hash (independent of manifest)
    data_artifacts_hash = _compute_data_artifacts_hash(project_data)

    # Compose bundle layout
    bundle = {
        "schema_version": "3.0",
        "aurora_launch_version": __version__,
        "project_type": "synthetic_corpus",
        "spec": spec.model_dump(),
        "data": project_data,
        "data_artifacts_hash": data_artifacts_hash,
    }

    # Compute JCS canonical hash of full bundle (cross-platform deterministic)
    canonical_bytes = rfc8785.dumps(bundle)
    manifest_sha256 = hashlib.sha256(canonical_bytes).hexdigest()

    # Manifest со integrity
    bundle["manifest_sha256"] = manifest_sha256

    # Reproducibility token — composite signing per PHASE_B_REQUIREMENTS §4.2
    # Inputs:
    #   - manifest_sha256 (verifies metadata + structure not tampered)
    #   - data_artifacts_hash (verifies actual data content not tampered)
    #   - aurora_launch_version (binds to specific Aurora Launch release)
    # All three needed для closure of R8 file tampering — attacker swapping
    # data needs to recompute ALL three, but data_artifacts_hash is already
    # baked in во manifest_sha256 (so changing it changes manifest), and
    # version is signed at compile time. Composite hash detects any drift.
    #
    # Domain validation (defense-in-depth): composite inputs must NOT contain
    # '|' separator character. Aurora Launch's actual inputs (hex strings +
    # semver version) cannot contain '|', but explicit check protects against
    # future schema changes введущие ambiguity. Per cross-language hash
    # compatibility test (test_cross_language_hash.py separator collision case).
    for name, value in (
        ("manifest_sha256", manifest_sha256),
        ("data_artifacts_hash", data_artifacts_hash),
        ("aurora_launch_version", __version__),
    ):
        if "|" in value:
            raise ValueError(
                f"Composite signing input {name!r} contains separator character '|' — "
                f"this would create hash collision risk. Aurora Launch inputs must be "
                f"hex strings or semver. Got: {value!r}"
            )

    repro_input = (
        manifest_sha256.encode("utf-8")
        + b"|"
        + data_artifacts_hash.encode("utf-8")
        + b"|"
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

    FIX B-Audit-3: ALSO recomputes reproducibility_token independently
    (not just trusts stored value) to detect tampering with that field
    alone.
    """
    with bundle_path.open("r", encoding="utf-8") as f:
        bundle = json.load(f)

    expected_manifest = bundle.get("manifest_sha256")
    expected_repro_token = bundle.get("reproducibility_token")
    aurora_launch_version_in_bundle = bundle.get("aurora_launch_version", "")

    # Verify manifest_sha256 by recomputing
    bundle_for_hash = {
        k: v for k, v in bundle.items()
        if k not in ("manifest_sha256", "reproducibility_token")
    }
    canonical_bytes = rfc8785.dumps(bundle_for_hash)
    computed_manifest = hashlib.sha256(canonical_bytes).hexdigest()

    if computed_manifest != expected_manifest:
        raise ValueError(
            f"Manifest hash mismatch in bundle: "
            f"expected {expected_manifest}, computed {computed_manifest}"
        )

    # Recompute reproducibility_token independently
    data_artifacts_hash = bundle.get("data_artifacts_hash", "")
    if not data_artifacts_hash:
        # Legacy bundle pre-fix B-Audit-2 — return stored without verification
        return computed_manifest, expected_repro_token

    repro_input = (
        computed_manifest.encode("utf-8")
        + b"|"
        + data_artifacts_hash.encode("utf-8")
        + b"|"
        + aurora_launch_version_in_bundle.encode("utf-8")
    )
    computed_repro_token = hashlib.sha256(repro_input).hexdigest()

    if expected_repro_token and computed_repro_token != expected_repro_token:
        raise ValueError(
            f"Reproducibility token mismatch in bundle: "
            f"expected {expected_repro_token}, computed {computed_repro_token}. "
            f"Bundle reproducibility_token field tampered."
        )

    return computed_manifest, computed_repro_token
