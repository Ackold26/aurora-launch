"""Validation method handlers — JSON-RPC dispatch для file analysis.

Phase: file reader port (2026-05-18).

Methods:
- analyze_data_file: preview + auto-detected column roles
- validate_wide_table: full validation with role overrides
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from aurora_launch.sidecar.methods import (
    SidecarSecurityError,
    _get_allowed_roots,
)

# Whitelist канонических ролей. Frontend Literal mirror.
# Backend MUST validate role_overrides values против этого set, иначе
# malicious / buggy payload пропишет произвольный role в response →
# validator.py detected recompute его проигнорирует, но clients увидят
# инконсистентный state.
_VALID_ROLES = frozenset(
    ["kpi", "media", "control", "date", "unused", "unknown"]
)


def register(name: str):
    from aurora_launch.sidecar.methods import register as _register
    return _register(name)


@register("analyze_data_file")
def _analyze_data_file(params: dict[str, Any]) -> dict[str, Any]:
    """Preview file + auto-detect column roles."""
    from aurora_launch.engines.path_security import (
        PathSecurityError,
        validate_safe_path,
    )
    from aurora_launch.engines.validator import (
        data_preview,
        detect_column_role_with_confidence,
    )
    from aurora_launch.utils.column_detection import classify_column

    path_raw = str(params.get("path", "")).strip()
    if not path_raw:
        raise ValueError("path must be non-empty")
    n_rows = int(params.get("n_rows", 20))

    try:
        path = validate_safe_path(Path(path_raw), _get_allowed_roots(), is_write=False)
    except PathSecurityError as e:
        raise SidecarSecurityError(str(e)) from e

    preview = data_preview(str(path), n_rows=n_rows)
    if preview.get("status") != "ok":
        return preview  # error envelope passes through

    columns = []
    for name in preview["headers"]:
        role, confidence = detect_column_role_with_confidence(name)
        kind = classify_column(name)
        columns.append({
            "name": name,
            "role": role,
            "confidence": confidence,
            "kind": kind,
        })

    return {**preview, "columns": columns}


@register("validate_wide_table")
def _validate_wide_table(params: dict[str, Any]) -> dict[str, Any]:
    """Full validation with optional role overrides."""
    from aurora_launch.engines.path_security import (
        PathSecurityError,
        validate_safe_path,
    )
    from aurora_launch.engines.validator import validate_data

    path_raw = str(params.get("path", "")).strip()
    if not path_raw:
        raise ValueError("path must be non-empty")
    role_overrides = params.get("role_overrides") or {}
    if not isinstance(role_overrides, dict):
        raise ValueError("role_overrides must be a dict or null")

    # Whitelist guard для role values (audit fix 2026-05-18).
    for _col, _role in role_overrides.items():
        if _role not in _VALID_ROLES:
            raise ValueError(
                f"role_overrides[{_col!r}] = {_role!r} is not a valid role. "
                f"Allowed: {sorted(_VALID_ROLES)}"
            )

    try:
        path = validate_safe_path(Path(path_raw), _get_allowed_roots(), is_write=False)
    except PathSecurityError as e:
        raise SidecarSecurityError(str(e)) from e

    result = validate_data(str(path))

    # Apply role overrides if provided. Mutate columns + recompute detected lists.
    #
    # NOTE: recompute logic ниже дублирует часть validator.validate_data().
    # При изменении validator (новая роль, изменение detection logic) ОБЯЗАТЕЛЬНО
    # синхронизировать здесь — иначе detected lists разойдутся.
    # Альтернатива: модифицировать validate_data принимать role_overrides param
    # (но это разойдётся с Optimizer-shared validator.py — текущий подход
    # сознательно держит validator.py идентичным Optimizer).
    if role_overrides and result.get("status") != "error":
        for col_info in result.get("columns", []):
            if col_info["name"] in role_overrides:
                col_info["role"] = role_overrides[col_info["name"]]
                col_info["confidence"] = 1.0  # user override = max confidence
        # Recompute detected lists
        detected = {"date": None, "kpi": [], "media": [], "control": []}
        for col_info in result.get("columns", []):
            role = col_info["role"]
            name = col_info["name"]
            if role == "date":
                detected["date"] = name
            elif role == "kpi":
                detected["kpi"].append(name)
            elif role == "media":
                detected["media"].append(name)
            elif role == "control":
                detected["control"].append(name)
        n_pred = len(detected["media"]) + len(detected["control"])
        detected["n_predictors"] = n_pred
        detected["ratio"] = round(result["file"]["rows"] / max(n_pred, 1), 1)
        detected["date_frequency"] = result.get("detected", {}).get("date_frequency", "unknown")
        result["detected"] = detected

    return result
