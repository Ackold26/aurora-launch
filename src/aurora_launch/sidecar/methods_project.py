"""Project management and bundle handlers.

Handlers: get_memory_report, create_project, list_projects, get_project,
          delete_project, list_versions, compare_versions,
          compare_forecast_versions, import_aurora_bundle, load_sample_bundle,
          save_bundle, parse_data_file, inspect_bundle_entry_json.

Helpers:  _SAMPLE_BUNDLE_PATHS dict.

All singletons (_PROJECT_DB, etc.) live in methods.py; accessed via
_get_project_db() imported from there.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aurora_launch import __version__


def register(name: str):
    """Proxy to methods.register."""
    from aurora_launch.sidecar.methods import register as _register
    return _register(name)


def _get_project_db():
    from aurora_launch.sidecar.methods import _get_project_db as _gpd
    return _gpd()


def _SidecarStorageError():
    from aurora_launch.sidecar.methods import SidecarStorageError
    return SidecarStorageError


# ─── Diagnostic ───────────────────────────────────────────────────────────────


@register("get_memory_report")
def _get_memory_report(_params: dict[str, Any]) -> dict[str, Any]:
    """Phase Scale S-10: return current process memory snapshot для UI policy.

    Returns:
      - rss_bytes: int — process resident set size (or 0 if psutil missing)
      - vms_bytes: int — virtual memory size
      - available_bytes: int — system-wide available RAM
      - severity: 'ok' | 'warning' | 'hard_cap' | 'critical'
      - threshold_bytes: int — threshold for current severity
      - advice: str — Russian advisory text
      - measured: bool — false if psutil missing (severity='ok' anyway)
    """
    from aurora_launch.sidecar.memory_profile import (
        get_memory_report,
        policy_advice,
    )

    try:
        report = get_memory_report()
    except ImportError:
        # psutil missing — degrade gracefully (no policy enforcement)
        return {
            "rss_bytes": 0,
            "vms_bytes": 0,
            "available_bytes": 0,
            "severity": "ok",
            "threshold_bytes": 0,
            "advice": "Профилирование памяти недоступно (psutil не установлен).",
            "measured": False,
        }
    return {
        "rss_bytes": report.rss_bytes,
        "vms_bytes": report.vms_bytes,
        "available_bytes": report.available_bytes,
        "severity": report.severity,
        "threshold_bytes": report.threshold_bytes,
        "advice": policy_advice(report),
        "measured": True,
    }


# ─── Phase Π.3b: ProjectDB handlers ─────────────────────────────────────────


@register("create_project")
def _create_project(params: dict[str, Any]) -> dict[str, Any]:
    """Create a new project in ProjectDB.

    Params:
      - name: str
      - granularity: str = "monthly" | "weekly"
      - metadata: dict = {}
    Returns:
      - project_uuid, name, created_at
    """
    SidecarStorageError = _SidecarStorageError()
    name = str(params.get("name", "")).strip()
    if not name:
        raise ValueError("name must be non-empty")
    granularity = str(params.get("granularity", "monthly"))
    metadata = params.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be a dict")

    db = _get_project_db()
    try:
        project_uuid = db.create_project(
            name=name,
            aurora_app_version=__version__,
            granularity=granularity,
            metadata=metadata,
        )
        detail = db.get_project(project_uuid)
    except Exception as exc:
        raise SidecarStorageError(f"create_project failed: {exc}") from exc

    return {
        "project_uuid": project_uuid,
        "name": detail.name,
        "created_at": detail.created_at,
    }


@register("list_projects")
def _list_projects(_params: dict[str, Any]) -> dict[str, Any]:
    """List all projects ordered by last_modified DESC.

    Returns: {"projects": [...]}
    """
    SidecarStorageError = _SidecarStorageError()
    db = _get_project_db()
    try:
        summaries = db.list_projects()
    except Exception as exc:
        raise SidecarStorageError(f"list_projects failed: {exc}") from exc

    return {
        "projects": [
            {
                "project_uuid": s.project_uuid,
                "name": s.name,
                "created_at": s.created_at,
                "last_modified": s.last_modified,
                "granularity": s.granularity,
                "version_count": s.version_count,
                "current_version_id": s.current_version_id,
            }
            for s in summaries
        ]
    }


@register("get_project")
def _get_project(params: dict[str, Any]) -> dict[str, Any]:
    """Get project detail + all versions (no blob payloads).

    Params: project_uuid: str
    Returns: project metadata + versions list
    """
    SidecarStorageError = _SidecarStorageError()
    project_uuid = str(params.get("project_uuid", "")).strip()
    if not project_uuid:
        raise ValueError("project_uuid must be non-empty")

    db = _get_project_db()
    try:
        detail = db.get_project(project_uuid)
    except Exception as exc:
        raise SidecarStorageError(f"get_project failed: {exc}") from exc

    # Version dicts MUST include decision_note + composite_bundle_hash to match
    # Rust VersionSummary deserialization contract (audit A-01 fix). Missing
    # fields cause serde to fail на UI side даже когда field is Option<String>.
    return {
        "project_uuid": detail.project_uuid,
        "name": detail.name,
        "metadata": detail.metadata,
        "versions": [
            {
                "version_id": v.version_id,
                "revision": v.revision,
                "label": v.label,
                "decision_note": v.decision_note,
                "created_at": v.created_at,
                "composite_bundle_hash": v.composite_bundle_hash,
                "file_count": v.file_count,
            }
            for v in detail.versions
        ],
    }


@register("delete_project")
def _delete_project(params: dict[str, Any]) -> dict[str, Any]:
    """Delete a project and all its versions + blobs.

    Params: project_uuid: str
    Returns: {"deleted": true}
    """
    SidecarStorageError = _SidecarStorageError()
    project_uuid = str(params.get("project_uuid", "")).strip()
    if not project_uuid:
        raise ValueError("project_uuid must be non-empty")

    db = _get_project_db()
    try:
        db.delete_project(project_uuid)
    except Exception as exc:
        raise SidecarStorageError(f"delete_project failed: {exc}") from exc

    return {"deleted": True}


@register("list_versions")
def _list_versions(params: dict[str, Any]) -> dict[str, Any]:
    """List all versions of a project (chronological ascending).

    Params: project_uuid: str
    Returns: {"versions": [...]}
    """
    SidecarStorageError = _SidecarStorageError()
    project_uuid = str(params.get("project_uuid", "")).strip()
    if not project_uuid:
        raise ValueError("project_uuid must be non-empty")

    db = _get_project_db()
    try:
        versions = db.list_versions(project_uuid)
    except Exception as exc:
        raise SidecarStorageError(f"list_versions failed: {exc}") from exc

    return {
        "versions": [
            {
                "version_id": v.version_id,
                "revision": v.revision,
                "label": v.label,
                "decision_note": v.decision_note,
                "created_at": v.created_at,
                "composite_bundle_hash": v.composite_bundle_hash,
                "file_count": v.file_count,
            }
            for v in versions
        ]
    }


@register("compare_versions")
def _compare_versions(params: dict[str, Any]) -> dict[str, Any]:
    """Diff two versions by file-path / blob hash.

    Params: version_id_a: int, version_id_b: int
    Returns: files_only_in_a, files_only_in_b, files_changed, files_unchanged
    """
    SidecarStorageError = _SidecarStorageError()
    try:
        version_id_a = int(params["version_id_a"])
        version_id_b = int(params["version_id_b"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"version_id_a and version_id_b must be integers: {exc}") from exc

    db = _get_project_db()
    try:
        diff = db.compare_versions(version_id_a, version_id_b)
    except Exception as exc:
        raise SidecarStorageError(f"compare_versions failed: {exc}") from exc

    return {
        "files_only_in_a": diff.files_only_in_a,
        "files_only_in_b": diff.files_only_in_b,
        "files_changed": diff.files_changed,
        "files_unchanged": diff.files_unchanged,
    }


@register("compare_forecast_versions")
def _compare_forecast_versions(params: dict[str, Any]) -> dict[str, Any]:
    """Phase 2 semantic diff: compare forecast results между two versions.

    Returns business-metric deltas (point forecast change, CI width
    change, engine mode change), not file-level diff.

    Params: version_id_a: int (earlier), version_id_b: int (later)
    Returns:
        available: bool — false если forecast.json missing в either version
        reason: str — explanation when not available
        point_a / point_b: float — mean point forecast per version
        point_delta_abs / point_delta_pct: float — change a → b
        ci_width_a / ci_width_b: float — mean CI width per version
        ci_width_delta_pct: float — % change in CI width (negative = tighter)
        engine_mode_a / engine_mode_b: str — mode used per version
        horizon_a / horizon_b: int — period count per version
    """
    SidecarStorageError = _SidecarStorageError()
    try:
        version_id_a = int(params["version_id_a"])
        version_id_b = int(params["version_id_b"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"version_id_a and version_id_b must be integers: {exc}") from exc

    db = _get_project_db()
    try:
        loaded_a = db.load_version(version_id_a)
        loaded_b = db.load_version(version_id_b)
    except Exception as exc:
        raise SidecarStorageError(f"compare_forecast_versions failed: {exc}") from exc

    # Find forecast.json в each version (entry name may vary case)
    def _find_forecast_json(files: dict[str, bytes]) -> dict[str, Any] | None:
        for path, content in files.items():
            if path.lower().endswith("forecast.json") or "forecast" in path.lower():
                try:
                    return json.loads(content.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
        return None

    fa = _find_forecast_json(loaded_a.files)
    fb = _find_forecast_json(loaded_b.files)

    if fa is None or fb is None:
        return {
            "available": False,
            "reason": "forecast.json missing в одной из версий",
        }

    # Extract point + CI per version
    def _mean(values: list[float]) -> float:
        return sum(values) / max(len(values), 1)

    def _summarise(forecast: dict[str, Any]) -> tuple[float, float, int]:
        # Schema может варьироваться — пробуем "weekly_points" then "points"
        points = forecast.get("weekly_points") or forecast.get("points") or []
        if not points:
            return 0.0, 0.0, 0
        point_mean = _mean([p.get("point") or p.get("point_forecast") or 0 for p in points])
        ci_widths = [(p.get("ci_upper", 0) - p.get("ci_lower", 0)) for p in points]
        return point_mean, _mean(ci_widths), len(points)

    point_a, ci_a, horizon_a = _summarise(fa)
    point_b, ci_b, horizon_b = _summarise(fb)

    point_delta_abs = point_b - point_a
    point_delta_pct = (point_delta_abs / point_a * 100.0) if point_a != 0 else 0.0
    ci_width_delta_pct = ((ci_b - ci_a) / ci_a * 100.0) if ci_a != 0 else 0.0

    return {
        "available": True,
        "point_a": point_a,
        "point_b": point_b,
        "point_delta_abs": point_delta_abs,
        "point_delta_pct": point_delta_pct,
        "ci_width_a": ci_a,
        "ci_width_b": ci_b,
        "ci_width_delta_pct": ci_width_delta_pct,
        "engine_mode_a": fa.get("engine_mode"),
        "engine_mode_b": fb.get("engine_mode"),
        "horizon_a": horizon_a,
        "horizon_b": horizon_b,
    }


@register("import_aurora_bundle")
def _import_aurora_bundle(params: dict[str, Any]) -> dict[str, Any]:
    """Import a .aurora ZIP bundle into ProjectDB.

    Params:
      - bundle_path: str
      - project_name: str | None
      - granularity: str = "monthly"
    Returns: {"project_uuid": str, "version_id": int}
    """
    from aurora_launch.persistence import migration_from_zip

    SidecarStorageError = _SidecarStorageError()
    bundle_path_raw = str(params.get("bundle_path", "")).strip()
    if not bundle_path_raw:
        raise ValueError("bundle_path must be non-empty")
    bundle_path = Path(bundle_path_raw)

    project_name = params.get("project_name") or None
    granularity = str(params.get("granularity", "monthly"))

    db = _get_project_db()
    try:
        project_uuid = migration_from_zip.import_aurora_bundle(
            bundle_path,
            db,
            project_name=project_name,
            granularity=granularity,
        )
        # get_project to find current_version_id (HEAD after import)
        detail = db.get_project(project_uuid)
    except Exception as exc:
        raise SidecarStorageError(f"import_aurora_bundle failed: {exc}") from exc

    return {
        "project_uuid": project_uuid,
        "version_id": detail.current_version_id,
    }


def _get_sample_bundle_paths() -> dict[str, Path]:
    """Late-import accessor so that tests can monkeypatch
    ``aurora_launch.sidecar.methods._SAMPLE_BUNDLE_PATHS`` and the change is
    visible here (the dict lives in methods.py as the canonical location for
    monkeypatching compatibility)."""
    from aurora_launch.sidecar import methods as _m
    return _m._SAMPLE_BUNDLE_PATHS


@register("load_sample_bundle")
def _load_sample_bundle(params: dict[str, Any]) -> dict[str, Any]:
    """Load pilot XLSX + derive synthetic posterior; save as ProjectDB version.

    Params: scenario: str — one of "kagotsel_venarus" | "afala_afalaza" | "multi_proxy"
    Returns: {"project_uuid", "version_id", "channels", "n_periods"}
    """
    from aurora_launch.persistence.safe_serializer import serialize
    from aurora_launch.sample_bundles.econometrica_xlsx_adapter import (
        load_econometrica_xlsx,
    )
    from aurora_launch.sample_bundles.synthetic_posterior import (
        derive_synthetic_posterior,
    )

    SidecarStorageError = _SidecarStorageError()
    sample_bundle_paths = _get_sample_bundle_paths()
    scenario = str(params.get("scenario", "")).strip()
    if scenario not in sample_bundle_paths:
        raise ValueError(
            f"Unknown scenario {scenario!r}. Valid: {sorted(sample_bundle_paths.keys())}"
        )

    xlsx_path = sample_bundle_paths[scenario]
    if not xlsx_path.exists():
        raise FileNotFoundError(
            f"Sample XLSX not found at {xlsx_path}. "
            f"Ensure pilot test files are present on this machine."
        )

    db = _get_project_db()
    try:
        dataset = load_econometrica_xlsx(xlsx_path)
        posterior_result = derive_synthetic_posterior(dataset)

        # Serialize posterior as msgpack blob (safe_serializer format)
        posterior_payload = {
            "posterior_samples": posterior_result.posterior_samples,
            "normalization": posterior_result.normalization,
            "config": posterior_result.config,
            "media_cols": posterior_result.media_cols,
            "n_proxy_observations": posterior_result.n_proxy_observations,
        }
        posterior_bytes = serialize(posterior_payload)

        project_name = f"Sample: {scenario}"
        project_uuid = db.create_project(
            name=project_name,
            aurora_app_version=__version__,
            granularity=dataset.granularity,
            metadata={
                "scenario": scenario,
                "source_xlsx": xlsx_path.name,
                "n_periods": dataset.n_periods,
                "channel_ids": dataset.channel_ids,
            },
        )

        version_id = db.save_version(
            project_uuid,
            files={"proxy_posterior.msgpack": posterior_bytes},
            label="Initial synthetic posterior",
            decision_note=f"Loaded from sample XLSX: {xlsx_path.name}",
        )
    except (SidecarStorageError, FileNotFoundError, ValueError):
        raise
    except Exception as exc:
        raise SidecarStorageError(f"load_sample_bundle failed: {exc}") from exc

    return {
        "project_uuid": project_uuid,
        "version_id": version_id,
        "channels": dataset.channel_ids,
        "n_periods": dataset.n_periods,
    }


# ─── Phase 2: save_bundle ─────────────────────────────────────────────────────


@register("save_bundle")
def _save_bundle(params: dict[str, Any]) -> dict[str, Any]:
    """Wraps Python `BundleZipWriter` — atomic save с manifest update.

    Inputs:
      - `source_path`: str — input bundle (open .aurora ZIP)
      - `target_path`: str — output path
      - `expected_revision`: int | null — optimistic concurrency check
      - `extra_files`: dict[str, base64-bytes] | null — entries to add/override
      - `aurora_app_version`: str — version stamp for new bundle (optional)
    Output:
      - `revision`: int — new bundle revision
      - `manifest`: dict — new manifest content
      - `composite_hash`: str — composite_bundle_hash() output
    """
    import base64 as _b64

    from aurora_launch.engines.bundle_container import (
        BundleZipReader,
        BundleZipWriter,
    )

    # POST_PILOT_BACKLOG B4-MED-4 close (2026-05-10): explicit nullable
    # source_path. Rust IPC теперь sends null когда нет existing bundle;
    # legacy empty-string sentinel still accepted (graceful migration).
    source_path_raw = params.get("source_path")
    has_source = bool(source_path_raw)  # None or "" → False, real path → True
    source_path = Path(source_path_raw) if has_source else None
    target_path = Path(params["target_path"])
    expected_revision = params.get("expected_revision")
    extra_files = params.get("extra_files") or {}
    new_version = params.get("aurora_app_version")

    if source_path is None or not source_path.exists():
        # Initial save — no source bundle, write fresh
        writer = BundleZipWriter(
            aurora_app_version=new_version or __version__,
            min_app_version="0.1.0",
        )
        for entry, b64 in extra_files.items():
            writer.add_file(entry, _b64.b64decode(b64))
        manifest = writer.write(target_path, expected_revision=expected_revision)
    else:
        loaded = BundleZipReader().read(source_path)
        writer = BundleZipWriter.from_loaded(loaded)
        for entry, b64 in extra_files.items():
            writer.add_file(entry, _b64.b64decode(b64))
        manifest = writer.write(target_path, expected_revision=expected_revision)

    return {
        "revision": manifest.revision,
        "manifest": json.loads(manifest.to_canonical_bytes().decode("utf-8")),
        "composite_hash": manifest.composite_bundle_hash(),
    }


# ─── Phase 3: parse_data_file ─────────────────────────────────────────────────


class UnsupportedFormatError(ValueError):
    pass


@register("parse_data_file")
def _parse_data_file(params: dict[str, Any]) -> dict[str, Any]:
    """Detect adapter for input file + parse first N records (preview).

    Inputs:
      - `path`: str — input file path
      - `adapter_id`: str | null — explicit adapter (skip detection)
      - `max_records`: int — preview cap, default 100
    Output:
      - `adapter_id`: str
      - `adapter_metadata`: dict (FormatAdapterContract serialised)
      - `record_count`: int
      - `records`: list[dict] — preview slice
    """
    from aurora_launch.engines.format_adapters.registry import build_default_registry

    path = params["path"]
    explicit_adapter = params.get("adapter_id")
    max_records = int(params.get("max_records", 100))

    registry = build_default_registry()
    adapter = registry.get_by_id(explicit_adapter) if explicit_adapter else registry.detect(path)
    if adapter is None:
        raise UnsupportedFormatError(f"no adapter detected for {path}")

    records = adapter.parse(path)
    metadata = adapter.get_metadata()

    return {
        "adapter_id": metadata.adapter_id,
        "adapter_metadata": metadata.model_dump(),
        "record_count": len(records),
        "records": records[:max_records],
    }


# ─── Phase 5: inspector data ──────────────────────────────────────────────────


@register("inspect_bundle_entry_json")
def _inspect_bundle_entry_json(params: dict[str, Any]) -> dict[str, Any]:
    """Read JSON entry from bundle for inspector tab data (similarity, forecast,
    etc.). Lazy reader pattern — does NOT load entire bundle.

    Inputs:
      - `bundle_path`: str
      - `entry`: str — manifest key
    Output:
      - `payload`: parsed JSON value
    """
    from aurora_launch.engines.bundle_streaming import open_lazy

    bundle_path = Path(params["bundle_path"])
    entry = str(params["entry"])
    with open_lazy(bundle_path) as bundle:
        payload = bundle.get_json(entry)
    return {"payload": payload}
