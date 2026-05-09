"""Sidecar auth attack scenarios — INV-05: attack scenario test FIRST.

Pinned threat model для Block 4 D4 sidecar auth. Each test = one attack
scenario. Implementation must reject all of them.

Threat model:
- Local adversary with read access to stdin/stdout pipes can attempt
  unauthenticated commands, forged tokens, malformed payloads, replay.
- Defender: per-launch random 32-byte hex token, constant-time compare.
"""

from __future__ import annotations

import secrets

import pytest

from aurora_launch.sidecar.auth import (
    AuthError,
    EXPECTED_TOKEN_HEX_LEN,
    check_auth,
)


@pytest.fixture
def expected_token() -> str:
    return secrets.token_hex(32)


class TestAuthAttackScenarios:
    """Each test = malicious request shape; defender must raise AuthError."""

    def test_missing_token_rejected(self, expected_token: str):
        with pytest.raises(AuthError):
            check_auth("", expected_token)

    def test_none_rejected(self, expected_token: str):
        with pytest.raises(AuthError):
            check_auth(None, expected_token)  # type: ignore[arg-type]

    def test_wrong_token_rejected(self, expected_token: str):
        forged = secrets.token_hex(32)
        assert forged != expected_token
        with pytest.raises(AuthError):
            check_auth(forged, expected_token)

    def test_truncated_token_rejected(self, expected_token: str):
        with pytest.raises(AuthError):
            check_auth(expected_token[:-1], expected_token)

    def test_extended_token_rejected(self, expected_token: str):
        with pytest.raises(AuthError):
            check_auth(expected_token + "ff", expected_token)

    def test_uppercase_variant_rejected(self, expected_token: str):
        # Case-sensitive check: forged token differing only in case must fail.
        # Only relevant if token contains a-f letters.
        if not any(c in "abcdef" for c in expected_token):
            pytest.skip("token contains no letters to flip")
        flipped = expected_token.upper()
        if flipped == expected_token:
            pytest.skip("uppercase identical to original")
        with pytest.raises(AuthError):
            check_auth(flipped, expected_token)

    def test_correct_token_accepted(self, expected_token: str):
        # Positive control: legitimate token must pass.
        check_auth(expected_token, expected_token)  # no raise

    def test_constant_time_comparison_documented(self):
        """Ensure check_auth uses hmac.compare_digest, not == (avoid timing leak).

        We don't measure timing here (flaky in CI); we assert the import path
        is correct via source inspection. INV-05 documentation requirement.
        """
        import inspect

        from aurora_launch.sidecar import auth as auth_module

        src = inspect.getsource(auth_module.check_auth)
        assert "compare_digest" in src, "check_auth must use hmac.compare_digest"

    def test_token_length_exactly_64(self):
        assert EXPECTED_TOKEN_HEX_LEN == 64

    def test_replay_attempt_with_arbitrary_token(self):
        """Replay of arbitrary captured-from-elsewhere token never matches."""
        # Adversary tries 100 random tokens — none should match
        legit = secrets.token_hex(32)
        for _ in range(100):
            forged = secrets.token_hex(32)
            with pytest.raises(AuthError):
                check_auth(forged, legit)


class TestAuthEnvVarLoad:
    """`load_token_from_env` must fail-closed if env unset / malformed."""

    def test_missing_env_exits(self, monkeypatch):
        from aurora_launch.sidecar import auth as auth_module

        monkeypatch.delenv(auth_module.ENV_VAR, raising=False)
        with pytest.raises(SystemExit) as ex:
            auth_module.load_token_from_env()
        assert ex.value.code == 2

    def test_short_env_exits(self, monkeypatch):
        from aurora_launch.sidecar import auth as auth_module

        monkeypatch.setenv(auth_module.ENV_VAR, "deadbeef")  # 8 chars
        with pytest.raises(SystemExit) as ex:
            auth_module.load_token_from_env()
        assert ex.value.code == 2

    def test_non_hex_env_exits(self, monkeypatch):
        from aurora_launch.sidecar import auth as auth_module

        monkeypatch.setenv(auth_module.ENV_VAR, "G" * 64)  # not hex
        with pytest.raises(SystemExit) as ex:
            auth_module.load_token_from_env()
        assert ex.value.code == 2

    def test_valid_hex_loads_ok(self, monkeypatch):
        from aurora_launch.sidecar import auth as auth_module

        token = secrets.token_hex(32)
        monkeypatch.setenv(auth_module.ENV_VAR, token)
        assert auth_module.load_token_from_env() == token
