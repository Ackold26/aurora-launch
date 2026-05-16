"""License validation IPC handlers (Phase 2.A).

Bridge между Rust shell (commands/license.rs) и Python license engine
(engines/license_validator.py). Rust shell вызывает get_license_status
через sidecar JSON-RPC; sidecar возвращает serialised LicenseStatus
включая state / tier / enabled_features / detail.

C-3 closure: до этой партии Rust commands/license.rs возвращал
hardcoded stub (production build → state='no_license' всегда). Платные
features нельзя было использовать в production — продукт нельзя
монетизировать. Этот handler закрывает gap.

HE-3 защита: bypass работает только если build_profile == 'dev'
(verified в LaunchLicenseValidator.from_env). Production installer
устанавливает AURORA_BUILD_PROFILE=production на build time через
build.rs (cargo:rustc-env) — env var на runtime игнорируется.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register(name: str):
    """Proxy to methods.register — fires декоратор при late import."""
    from aurora_launch.sidecar.methods import register as _register
    return _register(name)


def _serialize_status(status: Any) -> dict[str, Any]:
    """LicenseStatus dataclass → JSON-serialisable dict."""
    return {
        "state": status.state.value,  # LicenseState enum → str
        "tier": status.tier,
        "enabled_features": sorted(status.enabled_features),
        "detail": status.detail,
        "is_offline_grace": bool(status.is_offline_grace),
        "valid_until": (
            status.valid_until.isoformat() if status.valid_until else None
        ),
    }


@register("get_license_status")
def _get_license_status(_params: dict[str, Any]) -> dict[str, Any]:
    """Return current license status via LaunchLicenseValidator.

    Pure read — no side effects. Online refresh (async sync с server) —
    отдельный handler refresh_license (todo).

    Returns dict с теми же полями что LicenseStatusPayload в Rust
    (commands/license.rs), а frontend через `ipc.currentLicenseStatus()`.
    """
    from aurora_launch.engines.license_validator import LaunchLicenseValidator

    validator = LaunchLicenseValidator.from_env()
    status = validator.current_status()
    return _serialize_status(status)


@register("has_license_feature")
def _has_license_feature(params: dict[str, Any]) -> dict[str, Any]:
    """Check if a specific feature is granted by current license.

    Inputs:
      - feature: str — feature flag name (launch_proxy_multi, etc.)
    Returns:
      - granted: bool
      - state: str — current license state (для empathetic error в UI)
    """
    from aurora_launch.engines.license_validator import LaunchLicenseValidator

    feature = params.get("feature")
    if not isinstance(feature, str) or not feature:
        raise ValueError("feature must be non-empty string")

    validator = LaunchLicenseValidator.from_env()
    status = validator.current_status()
    return {
        "granted": status.has_feature(feature),
        "state": status.state.value,
    }
