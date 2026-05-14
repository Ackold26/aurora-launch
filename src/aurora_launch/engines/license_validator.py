"""Aurora Launch license validation — wraps `aurora_common.license.LicenseSDK`.

Block 1B — reuse existing platform-core JWT-based offline grace flow per
ADR-002 jwt-based-offline-grace (in `aurora-platform-core` repo). NOT a new
implementation — just a thin Aurora Launch–side adapter that:

1. Defines Aurora Launch–specific feature flag names (per tier_matrix.py
   already in aurora_common: `launch_proxy_single`, `launch_proxy_multi`).
2. Provides a sync façade over the async LicenseSDK (callers in Aurora
   Launch are mostly synchronous Pydantic-driven flows).
3. Gracefully degrades to "no license available" when `aurora_common`
   is not installed (e.g., CI without sibling-checkout, dev sandbox).
   In degraded mode all paid features default to denied — fail-closed.

Usage in Aurora Launch code::

    from aurora_launch.engines.license_validator import (
        LaunchLicenseValidator, FEATURE_LAUNCH_PROXY_MULTI,
    )

    validator = LaunchLicenseValidator.from_env()
    status = validator.current_status()
    if not status.has_feature(FEATURE_LAUNCH_PROXY_MULTI):
        raise PermissionError("Multi-proxy mode requires Pro tier")

Production deploy (in Tauri build, Block 2): Aurora Launch installer ships
with `aurora_common` as a bundled dependency. Path-dep resolves at install
time; license cache lives in `~/.aurora/aurora-launch/license-cache.json`.

Dev fallback: set ``AURORA_LAUNCH_LICENSE_BYPASS=1`` AND
``AURORA_BUILD_PROFILE=dev`` simultaneously to grant all features. Both
must be set; production builds set ``AURORA_BUILD_PROFILE=production`` at
package time so the bypass cannot be turned on by simply setting one env var.

Audit Block 1D — finding B1 fixed: previously the bypass honoured only
``AURORA_LAUNCH_LICENSE_BYPASS=1`` regardless of build profile, allowing
end-user license circumvention в production билдах через одну env var.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

_log = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Aurora Launch feature flag constants (mirrors aurora_common.license.tier_matrix)
# ----------------------------------------------------------------------------

# Single-proxy mode — included in trial_6mo, pro, and above
FEATURE_LAUNCH_PROXY_SINGLE = "launch_proxy_single"

# Multi-proxy expert mode — Pro+ only (paywalled)
FEATURE_LAUNCH_PROXY_MULTI = "launch_proxy_multi"

# Methodology certificate PDF — trial_6mo+, pro, enterprise
FEATURE_METHODOLOGY_CERT = "report_pdf_methodology_certificate"

# White-label export — agency tier only
FEATURE_WHITE_LABEL = "report_white_label"

# Telemetry export — enterprise only
FEATURE_TELEMETRY_EXPORT = "telemetry_export"


# Aurora Launch features that MUST require a valid license to use.
# This is the integration boundary — every entry-point that uses one of these
# must call validator.require(feature_name) before proceeding.
LAUNCH_GATED_FEATURES: frozenset[str] = frozenset(
    {
        FEATURE_LAUNCH_PROXY_SINGLE,
        FEATURE_LAUNCH_PROXY_MULTI,
        FEATURE_METHODOLOGY_CERT,
        FEATURE_WHITE_LABEL,
    }
)


# ----------------------------------------------------------------------------
# Status types
# ----------------------------------------------------------------------------


class LicenseState(Enum):
    """Coarse license status for UI display + gating decisions."""

    ACTIVE = "active"
    """Valid JWT, not expired, online or recently online."""

    GRACE = "grace"
    """JWT past `exp` but within 7-day offline grace window."""

    EXPIRED = "expired"
    """JWT past offline grace OR `valid_until` passed → must re-validate."""

    INVALID = "invalid"
    """Signature mismatch, malformed cache, tampering."""

    NO_LICENSE = "no_license"
    """No cache + no online check completed — never validated this machine."""

    DEGRADED = "degraded"
    """`aurora_common` not installed — license layer not functional. Fail-closed
    on every gate. Used in CI / dev without sibling-checkout."""


@dataclass(frozen=True)
class LicenseStatus:
    """Aurora Launch–side view of license state.

    Wraps a subset of `aurora_common.license.LicenseInfo` (or synthesizes empty
    in DEGRADED / NO_LICENSE states). Has the only method callers should use:
    `has_feature(flag) -> bool`.
    """

    state: LicenseState
    tier: Optional[str] = None  # e.g., "pro", "trial_6mo", None if no license
    user_id: Optional[str] = None
    license_id: Optional[str] = None
    seat_id: Optional[str] = None
    machine_id: Optional[str] = None
    valid_until: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_offline_grace: bool = False
    enabled_features: frozenset[str] = field(default_factory=frozenset)
    detail: str = ""  # human-readable diagnostic ("offline grace 3/7 days", etc.)

    def has_feature(self, feature: str) -> bool:
        """Returns True if the current license tier includes the feature.

        Fail-closed: any non-ACTIVE/GRACE state returns False for paid features.
        """
        if self.state in (LicenseState.ACTIVE, LicenseState.GRACE):
            return feature in self.enabled_features
        return False

    def require(self, feature: str) -> None:
        """Raise PermissionError if feature not granted by current license."""
        if not self.has_feature(feature):
            raise LicenseFeatureRequired(feature, self.state, self.tier)

    @property
    def is_usable(self) -> bool:
        """True if license currently allows app usage at all (ACTIVE or GRACE)."""
        return self.state in (LicenseState.ACTIVE, LicenseState.GRACE)


class LicenseFeatureRequired(PermissionError):
    """Raised when a gated feature is accessed without sufficient license."""

    def __init__(
        self,
        feature: str,
        current_state: LicenseState,
        current_tier: Optional[str],
    ) -> None:
        msg = (
            f"Feature '{feature}' requires an active license. "
            f"Current state: {current_state.value}"
            f"{f' (tier={current_tier})' if current_tier else ''}."
        )
        super().__init__(msg)
        self.feature = feature
        self.current_state = current_state
        self.current_tier = current_tier


# ----------------------------------------------------------------------------
# Validator
# ----------------------------------------------------------------------------


# Lazy import probe — done at module load, but error is captured, not raised.
try:
    from aurora_common.license import LicenseInfo, LicenseSDK  # type: ignore[import-not-found]
    from aurora_common.license.tier_matrix import TIER_FEATURES  # type: ignore[import-not-found]

    HAS_PLATFORM_CORE = True
except ImportError as _exc:
    HAS_PLATFORM_CORE = False
    _PLATFORM_IMPORT_ERROR: Optional[ImportError] = _exc
    LicenseInfo = None  # type: ignore[assignment,misc]
    LicenseSDK = None  # type: ignore[assignment,misc]
    TIER_FEATURES = {}  # type: ignore[assignment]
else:
    _PLATFORM_IMPORT_ERROR = None


def _info_to_status(info: "LicenseInfo") -> LicenseStatus:
    """Map aurora_common.LicenseInfo → LicenseStatus."""
    state = LicenseState.GRACE if info.is_offline_grace else LicenseState.ACTIVE
    enabled = TIER_FEATURES.get(info.tier, frozenset())
    detail = ""
    if info.is_offline_grace:
        days_offline = (datetime.now(timezone.utc) - info.expires_at).days
        detail = f"offline grace day {days_offline}/7"
    return LicenseStatus(
        state=state,
        tier=info.tier,
        user_id=info.user_id,
        license_id=info.license_id,
        seat_id=info.seat_id,
        machine_id=info.machine_id,
        valid_until=info.valid_until,
        expires_at=info.expires_at,
        is_offline_grace=info.is_offline_grace,
        enabled_features=frozenset(enabled),
        detail=detail,
    )


def _bypass_status() -> LicenseStatus:
    """Dev bypass: all enterprise features granted. Honored only if env flag set."""
    all_features = TIER_FEATURES.get("enterprise", frozenset())
    if not all_features:
        # Even in degraded mode, return broad feature set so dev can iterate
        all_features = frozenset(LAUNCH_GATED_FEATURES) | {
            FEATURE_LAUNCH_PROXY_SINGLE,
            FEATURE_LAUNCH_PROXY_MULTI,
            FEATURE_METHODOLOGY_CERT,
            FEATURE_WHITE_LABEL,
            FEATURE_TELEMETRY_EXPORT,
        }
    return LicenseStatus(
        state=LicenseState.ACTIVE,
        tier="dev_bypass",
        enabled_features=frozenset(all_features),
        detail="DEV BYPASS — all features enabled (AURORA_LAUNCH_LICENSE_BYPASS=1)",
    )


def _degraded_status() -> LicenseStatus:
    """Degraded: aurora_common not available. Fail-closed on every gate."""
    detail = (
        "aurora_common not installed — license layer non-functional. "
        "Install `aurora-common` package or check out aurora-platform-core sibling."
    )
    if _PLATFORM_IMPORT_ERROR is not None:
        detail += f" ImportError: {_PLATFORM_IMPORT_ERROR}"
    return LicenseStatus(state=LicenseState.DEGRADED, detail=detail)


@dataclass
class LaunchLicenseValidator:
    """Aurora Launch license validator — sync façade over async LicenseSDK.

    Two modes:
    - **Platform mode** (HAS_PLATFORM_CORE): real JWT verification via
      `aurora_common.license.LicenseSDK`.
    - **Degraded mode**: aurora_common not installed → fail-closed on every gate.

    Construction: prefer `LaunchLicenseValidator.from_env()` which reads:
    - AURORA_PLATFORM_URL — Vercel signing service base URL
    - AURORA_PUBLIC_VERIFY_KEY_PEM — Ed25519 public key (PEM format)
    - AURORA_LICENSE_CACHE_PATH — local JWT cache (default `~/.aurora/aurora-launch/license-cache.json`)
    - AURORA_MACHINE_ID — stable machine UUID
    - AURORA_LAUNCH_LICENSE_BYPASS=1 — dev bypass (always-grant)
    """

    platform_url: Optional[str] = None
    public_verify_key_pem: Optional[bytes] = None
    cache_path: Optional[Path] = None
    machine_id: Optional[str] = None
    bypass: bool = False
    app_id: str = "aurora-launch"

    # Lazy-initialized SDK reference (constructed on first validate() call)
    _sdk: Optional[object] = None

    @classmethod
    def from_env(cls) -> LaunchLicenseValidator:
        """Construct from environment variables.

        Bypass is honoured ONLY if both:
          - ``AURORA_LAUNCH_LICENSE_BYPASS`` ∈ {"1","true","yes"}
          - ``AURORA_BUILD_PROFILE`` == "dev"
        Production builds set ``AURORA_BUILD_PROFILE=production`` at package
        time. If a user attempts to set the bypass env var in production,
        a warning is logged and bypass is ignored (fail-closed).
        """
        bypass_raw = os.environ.get("AURORA_LAUNCH_LICENSE_BYPASS", "")
        build_profile = os.environ.get("AURORA_BUILD_PROFILE", "production").strip().lower()
        bypass_requested = bypass_raw.strip().lower() in ("1", "true", "yes")
        bypass = bypass_requested and build_profile == "dev"
        if bypass_requested and not bypass:
            _log.warning(
                "license_bypass_refused: AURORA_LAUNCH_LICENSE_BYPASS=%r set но "
                "AURORA_BUILD_PROFILE=%r (≠ 'dev') — bypass ignored, license "
                "validation enforced.",
                bypass_raw,
                build_profile,
            )

        cache_path_raw = os.environ.get("AURORA_LICENSE_CACHE_PATH")
        cache_path = (
            Path(cache_path_raw).expanduser()
            if cache_path_raw
            else Path("~/.aurora/aurora-launch/license-cache.json").expanduser()
        )

        public_key_raw = os.environ.get("AURORA_PUBLIC_VERIFY_KEY_PEM", "")
        public_key_bytes = public_key_raw.encode("utf-8") if public_key_raw else None

        return cls(
            platform_url=os.environ.get("AURORA_PLATFORM_URL"),
            public_verify_key_pem=public_key_bytes,
            cache_path=cache_path,
            machine_id=os.environ.get("AURORA_MACHINE_ID"),
            bypass=bypass,
        )

    def current_status(self, *, user_id: Optional[str] = None) -> LicenseStatus:
        """Return current license status (synchronous).

        Cache-first: if cached JWT valid, return immediately. Online refresh
        happens in `refresh()` which is async (callers must opt in).

        Args:
            user_id: required for online refresh; not needed for cache reads.

        Resolution order:
        1. If `bypass=True` → ACTIVE with all features (dev-only)
        2. If `not HAS_PLATFORM_CORE` → DEGRADED (fail-closed)
        3. If cache valid → ACTIVE/GRACE
        4. Otherwise → NO_LICENSE (caller may invoke `refresh()` to validate online)
        """
        if self.bypass:
            return _bypass_status()

        if not HAS_PLATFORM_CORE:
            return _degraded_status()

        if not self._can_construct_sdk():
            return LicenseStatus(
                state=LicenseState.NO_LICENSE,
                detail="LaunchLicenseValidator missing public_verify_key_pem / cache_path / machine_id",
            )

        sdk = self._get_sdk()
        # Pure-cache read path — no event loop / no network
        try:
            cached = sdk._read_cache()  # type: ignore[attr-defined]
            if cached is None:
                return LicenseStatus(state=LicenseState.NO_LICENSE, detail="No cached license")
            info = sdk._verify_jwt(cached.jwt)  # type: ignore[attr-defined]
            return _info_to_status(info)
        except Exception as exc:  # noqa: BLE001 — broad: SDK exceptions vary
            # Distinguish offline-grace-expired from signature-invalid by name
            name = type(exc).__name__
            if name in ("OfflineGraceExpired", "LicenseExpired"):
                return LicenseStatus(state=LicenseState.EXPIRED, detail=str(exc))
            if name in ("JWTSignatureInvalid", "JWTRefreshRequired"):
                return LicenseStatus(state=LicenseState.INVALID, detail=str(exc))
            _log.warning("license_validator_unexpected_error: %s: %s", name, exc)
            return LicenseStatus(state=LicenseState.INVALID, detail=f"{name}: {exc}")

    def has_feature(self, feature: str) -> bool:
        """Convenience: current_status().has_feature(feature)."""
        return self.current_status().has_feature(feature)

    def require(self, feature: str) -> None:
        """Convenience: raise LicenseFeatureRequired if feature not granted."""
        self.current_status().require(feature)

    def _can_construct_sdk(self) -> bool:
        return all(
            [
                self.platform_url,
                self.public_verify_key_pem,
                self.cache_path,
                self.machine_id,
            ]
        )

    def _get_sdk(self) -> object:
        """Lazily instantiate LicenseSDK. Caller must check HAS_PLATFORM_CORE."""
        if self._sdk is None:
            assert HAS_PLATFORM_CORE
            assert self.platform_url is not None
            assert self.public_verify_key_pem is not None
            assert self.cache_path is not None
            assert self.machine_id is not None
            self._sdk = LicenseSDK(  # type: ignore[misc]
                platform_url=self.platform_url,
                public_verify_key_pem=self.public_verify_key_pem,
                local_cache_path=self.cache_path,
                machine_id=self.machine_id,
                app_id=self.app_id,  # SH-1: required for verify_aud=True
            )
        return self._sdk
