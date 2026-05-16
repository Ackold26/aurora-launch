"""Phase 2.A — sidecar get_license_status handler tests.

Verifies sidecar JSON-RPC method correctly wraps LaunchLicenseValidator
state и возвращает контракт совместимый с Rust LicenseStatusPayload
(commands/license.rs).

Closes C-3: Rust stub'у больше негде брать данные о лицензии — теперь
sidecar — единственный источник правды.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _reset_module_singletons():
    from aurora_launch.sidecar.services import reset_services_for_testing

    reset_services_for_testing()
    yield
    reset_services_for_testing()


@pytest.fixture
def _clean_license_env(monkeypatch: pytest.MonkeyPatch):
    """Очищает env vars влияющие на license validator между tests."""
    for var in (
        "AURORA_LAUNCH_LICENSE_BYPASS",
        "AURORA_BUILD_PROFILE",
        "AURORA_PLATFORM_URL",
        "AURORA_PUBLIC_VERIFY_KEY_PEM",
        "AURORA_LICENSE_CACHE_PATH",
        "AURORA_MACHINE_ID",
    ):
        monkeypatch.delenv(var, raising=False)


class TestGetLicenseStatus:
    def test_returns_required_fields(self, _clean_license_env) -> None:
        from aurora_launch.sidecar.methods import dispatch

        result = dispatch("get_license_status", {})

        # Contract совместим с Rust LicenseStatusPayload
        assert "state" in result
        assert "tier" in result
        assert "enabled_features" in result
        assert "detail" in result
        assert "is_offline_grace" in result
        assert "valid_until" in result

    def test_state_is_string_enum_value(self, _clean_license_env) -> None:
        from aurora_launch.sidecar.methods import dispatch

        result = dispatch("get_license_status", {})

        # Должно быть одно из 6 known states
        assert result["state"] in (
            "active",
            "grace",
            "expired",
            "invalid",
            "no_license",
            "degraded",
        )

    def test_enabled_features_is_sorted_list(self, _clean_license_env) -> None:
        from aurora_launch.sidecar.methods import dispatch

        result = dispatch("get_license_status", {})

        assert isinstance(result["enabled_features"], list)
        # Sorted invariant — детерминированный для frontend caching
        assert result["enabled_features"] == sorted(result["enabled_features"])

    def test_dev_bypass_grants_features(
        self, _clean_license_env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """HE-3: bypass работает ТОЛЬКО при build_profile=dev."""
        from aurora_launch.sidecar.methods import dispatch

        monkeypatch.setenv("AURORA_LAUNCH_LICENSE_BYPASS", "1")
        monkeypatch.setenv("AURORA_BUILD_PROFILE", "dev")

        result = dispatch("get_license_status", {})
        assert result["state"] == "active"
        assert result["tier"] == "dev_bypass"
        # All gated features included
        assert "launch_proxy_single" in result["enabled_features"]
        assert "launch_proxy_multi" in result["enabled_features"]

    def test_bypass_refused_in_production(
        self, _clean_license_env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """HE-3 защита: bypass ignored если build_profile=production."""
        from aurora_launch.sidecar.methods import dispatch

        monkeypatch.setenv("AURORA_LAUNCH_LICENSE_BYPASS", "1")
        monkeypatch.setenv("AURORA_BUILD_PROFILE", "production")

        result = dispatch("get_license_status", {})
        # Must NOT be bypass-granted — должно быть либо degraded (нет
        # aurora_common) либо no_license (нет cache). НЕ "active" с tier='dev_bypass'.
        assert result["tier"] != "dev_bypass"
        assert result["state"] in ("no_license", "degraded")


class TestHasLicenseFeature:
    def test_returns_granted_bool(
        self, _clean_license_env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from aurora_launch.sidecar.methods import dispatch

        monkeypatch.setenv("AURORA_LAUNCH_LICENSE_BYPASS", "1")
        monkeypatch.setenv("AURORA_BUILD_PROFILE", "dev")

        result = dispatch("has_license_feature", {"feature": "launch_proxy_multi"})
        assert result["granted"] is True
        assert result["state"] == "active"

    def test_denies_unknown_feature(
        self, _clean_license_env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from aurora_launch.sidecar.methods import dispatch

        monkeypatch.setenv("AURORA_LAUNCH_LICENSE_BYPASS", "1")
        monkeypatch.setenv("AURORA_BUILD_PROFILE", "dev")

        result = dispatch("has_license_feature", {"feature": "totally_fake_feature"})
        assert result["granted"] is False

    def test_denies_in_no_license_state(self, _clean_license_env) -> None:
        from aurora_launch.sidecar.methods import dispatch

        result = dispatch("has_license_feature", {"feature": "launch_proxy_multi"})
        assert result["granted"] is False
        # State может быть no_license или degraded — fail-closed либо
        assert result["state"] in ("no_license", "degraded")

    def test_rejects_missing_feature_param(self, _clean_license_env) -> None:
        from aurora_launch.sidecar.methods import dispatch

        with pytest.raises(ValueError, match="feature.*non-empty"):
            dispatch("has_license_feature", {})

    def test_rejects_empty_feature_string(self, _clean_license_env) -> None:
        from aurora_launch.sidecar.methods import dispatch

        with pytest.raises(ValueError, match="feature.*non-empty"):
            dispatch("has_license_feature", {"feature": ""})


class TestLicenseStatusSidecarBoundary:
    """Контракт C-3: Rust `LicenseStatusPayload` поля — точное match."""

    def test_payload_keys_match_rust_struct(self, _clean_license_env) -> None:
        from aurora_launch.sidecar.methods import dispatch

        result = dispatch("get_license_status", {})
        # Rust LicenseStatusPayload (commands/license.rs) имеет fields:
        # state / tier / enabled_features / detail / is_offline_grace / valid_until
        expected_keys = {
            "state",
            "tier",
            "enabled_features",
            "detail",
            "is_offline_grace",
            "valid_until",
        }
        assert set(result.keys()) == expected_keys
