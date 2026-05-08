"""Tests for Block 1B — LaunchLicenseValidator wrapper over aurora_common.license.

Coverage:
- LicenseStatus.has_feature() / require() semantics
- Bypass mode (dev) grants all
- Degraded mode (no platform-core) fails closed on every gate
- NO_LICENSE state when env vars incomplete
- Feature flag constants match aurora_common.tier_matrix entries (when available)
- LicenseFeatureRequired raised by require() with correct context

These tests run without aurora-platform-core sibling-checkout: degraded path
is exercised always; platform-core path is conditionally tested via probe.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from aurora_launch.engines.license_validator import (
    FEATURE_LAUNCH_PROXY_MULTI,
    FEATURE_LAUNCH_PROXY_SINGLE,
    FEATURE_METHODOLOGY_CERT,
    FEATURE_WHITE_LABEL,
    HAS_PLATFORM_CORE,
    LAUNCH_GATED_FEATURES,
    LaunchLicenseValidator,
    LicenseFeatureRequired,
    LicenseState,
    LicenseStatus,
    _bypass_status,
    _degraded_status,
)


# ----------------------------------------------------------------------------
# LicenseStatus value semantics
# ----------------------------------------------------------------------------


class TestLicenseStatus:
    def test_has_feature_active_with_grant(self):
        status = LicenseStatus(
            state=LicenseState.ACTIVE,
            tier="pro",
            enabled_features=frozenset({FEATURE_LAUNCH_PROXY_MULTI}),
        )
        assert status.has_feature(FEATURE_LAUNCH_PROXY_MULTI) is True
        assert status.has_feature(FEATURE_WHITE_LABEL) is False

    def test_has_feature_grace_still_grants(self):
        """Offline grace still allows usage."""
        status = LicenseStatus(
            state=LicenseState.GRACE,
            tier="pro",
            enabled_features=frozenset({FEATURE_LAUNCH_PROXY_SINGLE}),
            is_offline_grace=True,
        )
        assert status.has_feature(FEATURE_LAUNCH_PROXY_SINGLE) is True

    def test_has_feature_expired_denies_all(self):
        status = LicenseStatus(
            state=LicenseState.EXPIRED,
            tier="pro",
            enabled_features=frozenset({FEATURE_LAUNCH_PROXY_MULTI}),
        )
        assert status.has_feature(FEATURE_LAUNCH_PROXY_MULTI) is False

    def test_has_feature_invalid_denies_all(self):
        status = LicenseStatus(
            state=LicenseState.INVALID,
            tier="pro",
            enabled_features=frozenset({FEATURE_LAUNCH_PROXY_MULTI}),
        )
        assert status.has_feature(FEATURE_LAUNCH_PROXY_MULTI) is False

    def test_has_feature_no_license_denies_all(self):
        status = LicenseStatus(state=LicenseState.NO_LICENSE)
        for feature in LAUNCH_GATED_FEATURES:
            assert status.has_feature(feature) is False

    def test_has_feature_degraded_denies_all(self):
        """Degraded mode (no platform-core) fails closed."""
        status = _degraded_status()
        for feature in LAUNCH_GATED_FEATURES:
            assert status.has_feature(feature) is False

    def test_require_raises_on_missing_feature(self):
        status = LicenseStatus(
            state=LicenseState.ACTIVE, tier="trial_6mo", enabled_features=frozenset()
        )
        with pytest.raises(LicenseFeatureRequired) as exc:
            status.require(FEATURE_LAUNCH_PROXY_MULTI)
        assert exc.value.feature == FEATURE_LAUNCH_PROXY_MULTI
        assert exc.value.current_state == LicenseState.ACTIVE
        assert exc.value.current_tier == "trial_6mo"

    def test_require_passes_on_granted_feature(self):
        status = LicenseStatus(
            state=LicenseState.ACTIVE,
            tier="pro",
            enabled_features=frozenset({FEATURE_LAUNCH_PROXY_MULTI}),
        )
        # Should not raise
        status.require(FEATURE_LAUNCH_PROXY_MULTI)

    def test_is_usable_only_for_active_or_grace(self):
        for state, expected in [
            (LicenseState.ACTIVE, True),
            (LicenseState.GRACE, True),
            (LicenseState.EXPIRED, False),
            (LicenseState.INVALID, False),
            (LicenseState.NO_LICENSE, False),
            (LicenseState.DEGRADED, False),
        ]:
            status = LicenseStatus(state=state)
            assert status.is_usable is expected, f"{state}: expected is_usable={expected}"


# ----------------------------------------------------------------------------
# Bypass mode (dev)
# ----------------------------------------------------------------------------


class TestBypassMode:
    def test_bypass_status_grants_all_launch_features(self):
        status = _bypass_status()
        assert status.state == LicenseState.ACTIVE
        assert status.tier == "dev_bypass"
        for feature in LAUNCH_GATED_FEATURES:
            assert status.has_feature(feature), f"bypass should grant {feature}"

    def test_validator_with_bypass_env_var(self, monkeypatch):
        monkeypatch.setenv("AURORA_LAUNCH_LICENSE_BYPASS", "1")
        v = LaunchLicenseValidator.from_env()
        status = v.current_status()
        assert status.state == LicenseState.ACTIVE
        assert status.tier == "dev_bypass"
        assert status.has_feature(FEATURE_LAUNCH_PROXY_MULTI)

    def test_validator_bypass_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("AURORA_LAUNCH_LICENSE_BYPASS", raising=False)
        v = LaunchLicenseValidator.from_env()
        assert v.bypass is False

    def test_bypass_accepts_truthy_strings(self, monkeypatch):
        for truthy in ("1", "true", "yes"):
            monkeypatch.setenv("AURORA_LAUNCH_LICENSE_BYPASS", truthy)
            v = LaunchLicenseValidator.from_env()
            assert v.bypass is True, f"'{truthy}' should enable bypass"

    def test_bypass_rejects_falsy_strings(self, monkeypatch):
        for falsy in ("0", "false", "no", "", "FAKE"):
            monkeypatch.setenv("AURORA_LAUNCH_LICENSE_BYPASS", falsy)
            v = LaunchLicenseValidator.from_env()
            assert v.bypass is False, f"'{falsy}' should NOT enable bypass"


# ----------------------------------------------------------------------------
# Degraded mode (no platform-core)
# ----------------------------------------------------------------------------


class TestDegradedMode:
    def test_degraded_status_state(self):
        status = _degraded_status()
        assert status.state == LicenseState.DEGRADED
        assert status.tier is None
        assert "aurora_common" in status.detail.lower()

    def test_degraded_denies_every_gate(self):
        status = _degraded_status()
        for feature in LAUNCH_GATED_FEATURES:
            assert not status.has_feature(feature)

    def test_validator_degraded_when_platform_core_missing(self, monkeypatch):
        """Simulate platform-core not installed via patch."""
        with patch("aurora_launch.engines.license_validator.HAS_PLATFORM_CORE", False):
            v = LaunchLicenseValidator()
            status = v.current_status()
            assert status.state == LicenseState.DEGRADED


# ----------------------------------------------------------------------------
# from_env construction
# ----------------------------------------------------------------------------


class TestFromEnv:
    def test_default_cache_path(self, monkeypatch):
        monkeypatch.delenv("AURORA_LICENSE_CACHE_PATH", raising=False)
        v = LaunchLicenseValidator.from_env()
        assert v.cache_path == Path("~/.aurora/aurora-launch/license-cache.json").expanduser()

    def test_explicit_cache_path(self, monkeypatch, tmp_path):
        monkeypatch.setenv("AURORA_LICENSE_CACHE_PATH", str(tmp_path / "test-cache.json"))
        v = LaunchLicenseValidator.from_env()
        assert v.cache_path == tmp_path / "test-cache.json"

    def test_platform_url_from_env(self, monkeypatch):
        monkeypatch.setenv("AURORA_PLATFORM_URL", "https://test.example.com")
        v = LaunchLicenseValidator.from_env()
        assert v.platform_url == "https://test.example.com"

    def test_machine_id_from_env(self, monkeypatch):
        monkeypatch.setenv("AURORA_MACHINE_ID", "machine-uuid-1234")
        v = LaunchLicenseValidator.from_env()
        assert v.machine_id == "machine-uuid-1234"

    def test_no_license_when_env_incomplete(self, monkeypatch):
        """Without all required env vars + platform-core, returns NO_LICENSE."""
        # Clear env to ensure none of the required vars are set
        for var in (
            "AURORA_PLATFORM_URL",
            "AURORA_PUBLIC_VERIFY_KEY_PEM",
            "AURORA_MACHINE_ID",
            "AURORA_LAUNCH_LICENSE_BYPASS",
        ):
            monkeypatch.delenv(var, raising=False)

        v = LaunchLicenseValidator.from_env()
        status = v.current_status()
        # If platform-core unavailable → DEGRADED; if available → NO_LICENSE
        # (either way, no usable license)
        assert not status.is_usable
        assert status.state in (LicenseState.NO_LICENSE, LicenseState.DEGRADED)


# ----------------------------------------------------------------------------
# Convenience methods on validator
# ----------------------------------------------------------------------------


class TestValidatorConvenience:
    def test_has_feature_via_validator(self, monkeypatch):
        monkeypatch.setenv("AURORA_LAUNCH_LICENSE_BYPASS", "1")
        v = LaunchLicenseValidator.from_env()
        assert v.has_feature(FEATURE_LAUNCH_PROXY_SINGLE)
        assert v.has_feature(FEATURE_LAUNCH_PROXY_MULTI)

    def test_require_via_validator(self, monkeypatch):
        # Without bypass — should fail closed
        monkeypatch.delenv("AURORA_LAUNCH_LICENSE_BYPASS", raising=False)
        v = LaunchLicenseValidator()  # no env, no bypass
        with patch("aurora_launch.engines.license_validator.HAS_PLATFORM_CORE", False):
            with pytest.raises(LicenseFeatureRequired):
                v.require(FEATURE_LAUNCH_PROXY_MULTI)


# ----------------------------------------------------------------------------
# Feature flag constants are correct
# ----------------------------------------------------------------------------


class TestFeatureConstants:
    def test_launch_features_in_gated_set(self):
        assert FEATURE_LAUNCH_PROXY_SINGLE in LAUNCH_GATED_FEATURES
        assert FEATURE_LAUNCH_PROXY_MULTI in LAUNCH_GATED_FEATURES
        assert FEATURE_METHODOLOGY_CERT in LAUNCH_GATED_FEATURES
        assert FEATURE_WHITE_LABEL in LAUNCH_GATED_FEATURES

    @pytest.mark.skipif(not HAS_PLATFORM_CORE, reason="aurora-platform-core not available")
    def test_feature_constants_match_platform_tier_matrix(self):
        """If platform-core checked out: our feature constants must exist in
        aurora_common.tier_matrix.ALL_FEATURES (not silent typos)."""
        from aurora_common.license.tier_matrix import ALL_FEATURES  # type: ignore[import-not-found]

        assert FEATURE_LAUNCH_PROXY_SINGLE in ALL_FEATURES
        assert FEATURE_LAUNCH_PROXY_MULTI in ALL_FEATURES
        assert FEATURE_METHODOLOGY_CERT in ALL_FEATURES
        assert FEATURE_WHITE_LABEL in ALL_FEATURES

    @pytest.mark.skipif(not HAS_PLATFORM_CORE, reason="aurora-platform-core not available")
    def test_pro_tier_includes_multi_proxy(self):
        """Pro tier should grant multi-proxy mode (key paywall claim)."""
        from aurora_common.license.tier_matrix import TIER_FEATURES  # type: ignore[import-not-found]

        assert FEATURE_LAUNCH_PROXY_MULTI in TIER_FEATURES.get("pro", set())

    @pytest.mark.skipif(not HAS_PLATFORM_CORE, reason="aurora-platform-core not available")
    def test_trial_tier_excludes_multi_proxy(self):
        """Trial 6mo should NOT grant multi-proxy (paywall enforcement)."""
        from aurora_common.license.tier_matrix import TIER_FEATURES  # type: ignore[import-not-found]

        assert FEATURE_LAUNCH_PROXY_MULTI not in TIER_FEATURES.get("trial_6mo", set())


# ----------------------------------------------------------------------------
# Sanity: module imports cleanly
# ----------------------------------------------------------------------------


def test_block_1b_module_importable():
    """All Block 1B exports are importable + LICENSE_GATED_FEATURES non-empty."""
    from aurora_launch.engines import license_validator
    from aurora_launch.tools import validate_license_cli

    assert hasattr(license_validator, "LaunchLicenseValidator")
    assert hasattr(license_validator, "LicenseStatus")
    assert hasattr(license_validator, "LicenseState")
    assert len(LAUNCH_GATED_FEATURES) >= 4
    assert hasattr(validate_license_cli, "main")
