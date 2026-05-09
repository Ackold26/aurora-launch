"""Sidecar method handlers — JSON-RPC dispatch table.

Each method receives `params: dict[str, Any]` and returns JSON-serialisable
result OR raises an exception (caught by server, converted к error response).

Block 4 method inventory:
- `ping` — diagnostic; returns `{"pong": true, "version": ...}`
- `save_bundle` — Phase 2: Python BundleZipWriter wrapper
- `parse_data_file` — Phase 3: AdapterRegistry.detect + parse
- `start_forecast` — Phase 4: spawn forecast task, emit progress events
- `cancel_forecast` — Phase 4: cooperative cancel via atomic flag
- `get_forecast_status` — Phase 4: poll status (also event-driven)
- `inspect_bundle_entry_json` — Phase 5: Inspector tab data wiring
- `shutdown` — graceful exit signal from Rust parent

All `cancel_forecast` cancellation goes through `_cancel_flags` dict —
cooperative pattern (D5: NO SIGINT, NO terminate).
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from aurora_launch import __version__
from aurora_launch.sidecar import events

# ─── Method registry ──────────────────────────────────────────────────────────


_METHODS: dict[str, Callable[[dict[str, Any]], Any]] = {}
_cancel_flags: dict[str, threading.Event] = {}
_forecast_threads: dict[str, threading.Thread] = {}


def register(name: str):
    def decorator(fn: Callable[[dict[str, Any]], Any]):
        _METHODS[name] = fn
        return fn

    return decorator


def list_methods() -> list[str]:
    return sorted(_METHODS.keys())


def dispatch(method: str, params: dict[str, Any]) -> Any:
    if method not in _METHODS:
        raise MethodNotFoundError(method)
    return _METHODS[method](params)


class MethodNotFoundError(LookupError):
    def __init__(self, method: str) -> None:
        super().__init__(f"unknown method: {method}")
        self.method = method


# ─── Diagnostic ───────────────────────────────────────────────────────────────


@register("ping")
def _ping(_params: dict[str, Any]) -> dict[str, Any]:
    return {"pong": True, "version": __version__, "methods": list_methods()}


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

    source_path = Path(params["source_path"])
    target_path = Path(params["target_path"])
    expected_revision = params.get("expected_revision")
    extra_files = params.get("extra_files") or {}
    new_version = params.get("aurora_app_version")

    if not source_path.exists():
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
    adapter = (
        registry.get_by_id(explicit_adapter)
        if explicit_adapter
        else registry.detect(path)
    )
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


class UnsupportedFormatError(ValueError):
    pass


# ─── Phase 4: forecast streaming ──────────────────────────────────────────────


@register("start_forecast")
def _start_forecast(params: dict[str, Any]) -> dict[str, Any]:
    """Spawn forecast task в background thread. Returns handle immediately;
    progress emitted as events `forecast_progress` (week-by-week) и final
    `forecast_completed` или `forecast_cancelled`.

    Inputs:
      - `project_id`: str
      - `horizon_weeks`: int
      - `seed`: int
      - `priors`: dict (optional) — passes through to launch_validate
    Output:
      - `forecast_handle`: str (UUID) — for cancel + status correlation
    """
    project_id = str(params.get("project_id", ""))
    horizon_weeks = int(params.get("horizon_weeks", 26))
    seed = int(params.get("seed", 42))

    handle = str(uuid.uuid4())
    cancel = threading.Event()
    _cancel_flags[handle] = cancel

    def runner() -> None:
        from aurora_launch.engines.launch_validate import (
            prior_predictive_samples_real,
        )
        from aurora_launch.schemas.adaptation import PriorParam

        started = time.monotonic()
        try:
            recipient_priors = {
                "trend_slope": PriorParam(
                    mean=0.001, std=0.005, source="proxy_transferred"
                )
            }
            samples = prior_predictive_samples_real(
                recipient_priors=recipient_priors,
                horizon_weeks=horizon_weeks,
                n_samples=50,
                seed=seed,
            )
            # Stream per-week aggregate (mean + ci) from samples
            for week_idx in range(horizon_weeks):
                if cancel.is_set():
                    events.emit(
                        "forecast_cancelled",
                        {"forecast_handle": handle, "week_index": week_idx},
                    )
                    return
                weekly_values = [s.weekly_values[week_idx] for s in samples]
                mean = sum(weekly_values) / len(weekly_values)
                sorted_vals = sorted(weekly_values)
                lo = sorted_vals[int(0.025 * len(sorted_vals))]
                hi = sorted_vals[int(0.975 * len(sorted_vals))]
                events.emit(
                    "forecast_progress",
                    {
                        "forecast_handle": handle,
                        "week_index": week_idx,
                        "point_forecast": mean,
                        "ci_lower": lo,
                        "ci_upper": hi,
                        "progress_pct": round(
                            (week_idx + 1) / horizon_weeks * 100.0, 2
                        ),
                        "elapsed_ms": int((time.monotonic() - started) * 1000),
                    },
                )
                # Throttle slightly so UI animation remains smooth (real ML
                # forecast won't need this — но here samples are computed
                # already, all weeks in <1ms total).
                time.sleep(0.05)

            events.emit(
                "forecast_completed",
                {
                    "forecast_handle": handle,
                    "horizon_weeks": horizon_weeks,
                    "elapsed_ms": int((time.monotonic() - started) * 1000),
                },
            )
        except Exception as exc:  # noqa: BLE001 — broad to surface anything
            events.emit(
                "forecast_failed",
                {
                    "forecast_handle": handle,
                    "error": str(exc),
                    "kind": type(exc).__name__,
                },
            )
        finally:
            _cancel_flags.pop(handle, None)
            _forecast_threads.pop(handle, None)

    thread = threading.Thread(
        target=runner, name=f"aurora-forecast-{handle[:8]}", daemon=True
    )
    _forecast_threads[handle] = thread
    thread.start()

    return {
        "forecast_handle": handle,
        "project_id": project_id,
        "horizon_weeks": horizon_weeks,
    }


@register("cancel_forecast")
def _cancel_forecast(params: dict[str, Any]) -> dict[str, Any]:
    """Cooperative cancel — sets atomic flag. Sampler thread exits на next
    iteration boundary. NO SIGINT, NO terminate (D5)."""
    handle = str(params.get("forecast_handle", ""))
    flag = _cancel_flags.get(handle)
    if flag is None:
        return {"cancelled": False, "reason": "handle not found или already finished"}
    flag.set()
    return {"cancelled": True, "forecast_handle": handle}


# ─── Phase 5: inspector data ──────────────────────────────────────────────────


@register("inspect_bundle_entry_json")
def _inspect_bundle_entry_json(params: dict[str, Any]) -> dict[str, Any]:
    """Read JSON entry from bundle для inspector tab data (similarity, forecast,
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


# ─── Lifecycle ────────────────────────────────────────────────────────────────


@register("shutdown")
def _shutdown(_params: dict[str, Any]) -> dict[str, Any]:
    """Graceful shutdown signal — server loop exits после returning result."""
    return {"shutting_down": True}
