"""Phase Scale S-18 — Tauri Rust ↔ Python sidecar version negotiation handshake.

Coverage:
- ping returns protocol_version and min_compatible_rust fields
- negotiate(matching version) → compatible=True, reason=None, advice=None
- negotiate(older Rust major 0.0.5) → compatible=False, advice "Update Tauri shell"
- negotiate(newer minor Rust 0.2.0, same major) → compatible=True
- negotiate(newer major Rust 1.0.0) → compatible=False, advice "Python sidecar update required"
- negotiate(invalid version "abc") → compatible=False, reason "invalid version format"
- negotiate missing param → compatible=False
- protocol_version module constants have correct types
- compatible() predicate covers all three cases (too old / too new / same major)
- parse_semver returns None for garbage, correct tuple for valid semver
- negotiate logs at WARNING for incompatible, INFO for compatible
"""

from __future__ import annotations

import logging

import pytest

from aurora_launch.sidecar.methods import dispatch
from aurora_launch.sidecar.protocol_version import (
    MIN_COMPATIBLE_RUST,
    PROTOCOL_VERSION,
    compatible,
    negotiate,
    parse_semver,
)


# ---------------------------------------------------------------------------
# S-18-T01: ping response fields
# ---------------------------------------------------------------------------


class TestPingProtocolFields:
    def test_ping_returns_protocol_version(self) -> None:
        result = dispatch("ping", {})
        assert "protocol_version" in result

    def test_ping_protocol_version_is_list_of_two_ints(self) -> None:
        result = dispatch("ping", {})
        pv = result["protocol_version"]
        assert isinstance(pv, list)
        assert len(pv) == 2
        assert all(isinstance(x, int) for x in pv)

    def test_ping_returns_min_compatible_rust(self) -> None:
        result = dispatch("ping", {})
        assert "min_compatible_rust" in result

    def test_ping_min_compatible_rust_is_list_of_three_ints(self) -> None:
        result = dispatch("ping", {})
        mc = result["min_compatible_rust"]
        assert isinstance(mc, list)
        assert len(mc) == 3
        assert all(isinstance(x, int) for x in mc)

    def test_ping_protocol_version_matches_module_constant(self) -> None:
        result = dispatch("ping", {})
        assert tuple(result["protocol_version"]) == PROTOCOL_VERSION

    def test_ping_min_compatible_rust_matches_module_constant(self) -> None:
        result = dispatch("ping", {})
        assert tuple(result["min_compatible_rust"]) == MIN_COMPATIBLE_RUST

    def test_ping_still_has_pong_and_version(self) -> None:
        """Regression: extending ping must not drop existing fields."""
        result = dispatch("ping", {})
        assert result["pong"] is True
        assert "version" in result
        assert "methods" in result

    def test_negotiate_listed_in_ping_methods(self) -> None:
        result = dispatch("ping", {})
        assert "negotiate" in result["methods"]


# ---------------------------------------------------------------------------
# S-18-T02: negotiate via dispatch — happy path
# ---------------------------------------------------------------------------


class TestNegotiateCompatible:
    def test_matching_version_compatible(self) -> None:
        """Exact match of MIN_COMPATIBLE_RUST → compatible=True."""
        maj, minor, patch = MIN_COMPATIBLE_RUST
        version_str = f"{maj}.{minor}.{patch}"
        result = dispatch("negotiate", {"rust_version": version_str})
        assert result["compatible"] is True

    def test_compatible_reason_is_none(self) -> None:
        maj, minor, patch = MIN_COMPATIBLE_RUST
        result = dispatch("negotiate", {"rust_version": f"{maj}.{minor}.{patch}"})
        assert result["reason"] is None

    def test_compatible_advice_is_none(self) -> None:
        maj, minor, patch = MIN_COMPATIBLE_RUST
        result = dispatch("negotiate", {"rust_version": f"{maj}.{minor}.{patch}"})
        assert result["advice"] is None

    def test_newer_minor_same_major_compatible(self) -> None:
        """Forward minor compatibility: Rust 0.2.0 with MIN 0.1.0 → compat."""
        maj = MIN_COMPATIBLE_RUST[0]
        result = dispatch("negotiate", {"rust_version": f"{maj}.99.0"})
        assert result["compatible"] is True

    def test_newer_patch_same_major_compatible(self) -> None:
        """Patch bump never breaks compatibility."""
        maj, minor, _ = MIN_COMPATIBLE_RUST
        result = dispatch("negotiate", {"rust_version": f"{maj}.{minor}.99"})
        assert result["compatible"] is True

    def test_prerelease_suffix_accepted(self) -> None:
        """Semver pre-release suffix must not break parsing."""
        maj, minor, patch = MIN_COMPATIBLE_RUST
        result = dispatch("negotiate", {"rust_version": f"{maj}.{minor}.{patch}-beta.1"})
        assert result["compatible"] is True


# ---------------------------------------------------------------------------
# S-18-T03: negotiate — older Rust (major too low)
# ---------------------------------------------------------------------------


class TestNegotiateOlderRust:
    def _old_version(self) -> str:
        """Version with major one below MIN_COMPATIBLE_RUST."""
        min_major = MIN_COMPATIBLE_RUST[0]
        old_major = min_major - 1 if min_major > 0 else 0
        # If MIN_COMPATIBLE_RUST is already 0.x.y, use a specific older known
        # version that is strictly below minimum regardless.
        if old_major == min_major:
            # MIN is 0.x.y and we can't go below major 0; use 0.0.5.
            return "0.0.5"
        return f"{old_major}.99.0"

    def test_old_rust_incompatible(self) -> None:
        result = dispatch("negotiate", {"rust_version": "0.0.5"})
        # 0.0.5 < MIN_COMPATIBLE_RUST (0.1.0) → incompatible
        assert result["compatible"] is False

    def test_old_rust_advice_update_tauri(self) -> None:
        result = dispatch("negotiate", {"rust_version": "0.0.5"})
        assert result["advice"] == "Update Tauri shell"

    def test_old_rust_reason_contains_min_version(self) -> None:
        result = dispatch("negotiate", {"rust_version": "0.0.5"})
        reason = result["reason"]
        assert reason is not None
        min_str = ".".join(str(x) for x in MIN_COMPATIBLE_RUST)
        assert min_str in reason


# ---------------------------------------------------------------------------
# S-18-T04: negotiate — newer major Rust (sidecar update required)
# ---------------------------------------------------------------------------


class TestNegotiateNewerMajorRust:
    def test_future_major_incompatible(self) -> None:
        future_major = MIN_COMPATIBLE_RUST[0] + 1
        result = dispatch("negotiate", {"rust_version": f"{future_major}.0.0"})
        assert result["compatible"] is False

    def test_future_major_advice_sidecar_update(self) -> None:
        future_major = MIN_COMPATIBLE_RUST[0] + 1
        result = dispatch("negotiate", {"rust_version": f"{future_major}.0.0"})
        assert result["advice"] == "Python sidecar update required"

    def test_future_major_reason_mentions_major(self) -> None:
        future_major = MIN_COMPATIBLE_RUST[0] + 1
        result = dispatch("negotiate", {"rust_version": f"{future_major}.0.0"})
        reason = result["reason"]
        assert reason is not None
        assert str(future_major) in reason


# ---------------------------------------------------------------------------
# S-18-T05: negotiate — invalid version string
# ---------------------------------------------------------------------------


class TestNegotiateInvalidVersion:
    def test_alpha_string_incompatible(self) -> None:
        result = dispatch("negotiate", {"rust_version": "abc"})
        assert result["compatible"] is False

    def test_alpha_string_reason(self) -> None:
        result = dispatch("negotiate", {"rust_version": "abc"})
        assert result["reason"] == "invalid version format"

    def test_empty_string_returns_missing_param_error(self) -> None:
        result = dispatch("negotiate", {"rust_version": ""})
        assert result["compatible"] is False

    def test_missing_param_returns_error(self) -> None:
        result = dispatch("negotiate", {})
        assert result["compatible"] is False

    def test_partial_semver_incompatible(self) -> None:
        """'1.0' without patch component is invalid semver."""
        result = dispatch("negotiate", {"rust_version": "1.0"})
        assert result["compatible"] is False

    def test_negative_numbers_incompatible(self) -> None:
        result = dispatch("negotiate", {"rust_version": "-1.0.0"})
        assert result["compatible"] is False


# ---------------------------------------------------------------------------
# S-18-T06: protocol_version module constants
# ---------------------------------------------------------------------------


class TestProtocolVersionConstants:
    def test_protocol_version_is_tuple_of_two_ints(self) -> None:
        assert isinstance(PROTOCOL_VERSION, tuple)
        assert len(PROTOCOL_VERSION) == 2
        assert all(isinstance(x, int) for x in PROTOCOL_VERSION)

    def test_min_compatible_rust_is_tuple_of_three_ints(self) -> None:
        assert isinstance(MIN_COMPATIBLE_RUST, tuple)
        assert len(MIN_COMPATIBLE_RUST) == 3
        assert all(isinstance(x, int) for x in MIN_COMPATIBLE_RUST)

    def test_protocol_version_major_is_positive(self) -> None:
        assert PROTOCOL_VERSION[0] >= 1

    def test_min_compatible_rust_non_negative(self) -> None:
        assert all(x >= 0 for x in MIN_COMPATIBLE_RUST)


# ---------------------------------------------------------------------------
# S-18-T07: compatible() predicate unit tests
# ---------------------------------------------------------------------------


class TestCompatiblePredicate:
    def test_exact_min_version_compatible(self) -> None:
        assert compatible(MIN_COMPATIBLE_RUST) is True

    def test_same_major_newer_minor_compatible(self) -> None:
        maj = MIN_COMPATIBLE_RUST[0]
        assert compatible((maj, 99, 0)) is True

    def test_same_major_below_min_tuple_incompatible(self) -> None:
        """(major, minor, patch) below MIN_COMPATIBLE_RUST is incompatible even
        when major matches.  Critical for pre-1.0 versions where minor bumps
        can be breaking (e.g. MIN=(0,1,0) and (0,0,0) → incompatible)."""
        if MIN_COMPATIBLE_RUST > (MIN_COMPATIBLE_RUST[0], 0, 0):
            # There exists a version with same major but below min floor.
            assert compatible((MIN_COMPATIBLE_RUST[0], 0, 0)) is False

    def test_lower_major_incompatible(self) -> None:
        maj = MIN_COMPATIBLE_RUST[0]
        if maj > 0:
            assert compatible((maj - 1, 99, 99)) is False

    def test_higher_major_incompatible(self) -> None:
        maj = MIN_COMPATIBLE_RUST[0]
        assert compatible((maj + 1, 0, 0)) is False


# ---------------------------------------------------------------------------
# S-18-T08: parse_semver unit tests
# ---------------------------------------------------------------------------


class TestParseSemver:
    def test_basic_semver(self) -> None:
        assert parse_semver("0.1.0") == (0, 1, 0)

    def test_with_prerelease(self) -> None:
        assert parse_semver("0.1.0-beta.1") == (0, 1, 0)

    def test_with_build_metadata(self) -> None:
        assert parse_semver("1.2.3+build.123") == (1, 2, 3)

    def test_none_for_alpha(self) -> None:
        assert parse_semver("abc") is None

    def test_none_for_partial(self) -> None:
        assert parse_semver("1.0") is None

    def test_none_for_empty(self) -> None:
        assert parse_semver("") is None

    def test_none_for_negative(self) -> None:
        assert parse_semver("-1.0.0") is None


# ---------------------------------------------------------------------------
# S-18-T09: logging behaviour
# ---------------------------------------------------------------------------


class TestNegotiateLogging:
    def test_compatible_logs_info(self, caplog: pytest.LogCaptureFixture) -> None:
        maj, minor, patch = MIN_COMPATIBLE_RUST
        with caplog.at_level(logging.INFO, logger="aurora_launch.sidecar.protocol_version"):
            negotiate(f"{maj}.{minor}.{patch}")
        info_msgs = [r for r in caplog.records if r.levelno == logging.INFO]
        assert any("compatible" in r.message.lower() for r in info_msgs)

    def test_incompatible_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger="aurora_launch.sidecar.protocol_version"):
            negotiate("0.0.5")
        warn_msgs = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warn_msgs) >= 1

    def test_invalid_version_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger="aurora_launch.sidecar.protocol_version"):
            negotiate("not-a-version")
        warn_msgs = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warn_msgs) >= 1
