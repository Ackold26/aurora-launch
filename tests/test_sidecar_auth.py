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
    _is_valid_token,
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


class TestStdinTokenChannelHE2:
    """Phase 2.D.1 HE-2: prefer stdin first line, fallback env var."""

    def test_valid_token_predicate(self):
        from aurora_launch.sidecar import auth as auth_module

        assert auth_module._is_valid_token(secrets.token_hex(32))

    def test_invalid_shape_rejected(self):
        from aurora_launch.sidecar import auth as auth_module

        assert not auth_module._is_valid_token("")
        assert not auth_module._is_valid_token("deadbeef")  # too short
        assert not auth_module._is_valid_token("G" * 64)  # not hex
        assert not auth_module._is_valid_token("a" * 65)  # too long

    def test_stdin_token_preferred_over_env(self, monkeypatch, capsys):
        """Если оба source имеют валидный token — stdin priority."""
        from aurora_launch.sidecar import auth as auth_module

        stdin_token = secrets.token_hex(32)
        env_token = secrets.token_hex(32)
        assert stdin_token != env_token

        monkeypatch.setenv(auth_module.ENV_VAR, env_token)
        monkeypatch.setattr(
            auth_module, "_read_first_line_stdin", lambda timeout: stdin_token
        )

        loaded = auth_module.load_token_from_stdin_or_env()
        assert loaded == stdin_token  # stdin wins

    def test_env_fallback_when_stdin_empty(self, monkeypatch, capsys):
        """stdin timeout/empty → env fallback с deprecation warning (Linux/macOS)."""
        from aurora_launch.sidecar import auth as auth_module

        env_token = secrets.token_hex(32)
        monkeypatch.setenv(auth_module.ENV_VAR, env_token)
        monkeypatch.setattr(
            auth_module, "_read_first_line_stdin", lambda timeout: None
        )

        loaded = auth_module.load_token_from_stdin_or_env()
        assert loaded == env_token

    def test_invalid_stdin_token_falls_back_to_env(self, monkeypatch, capsys):
        """Stdin содержит мусор → fallback env (с warning к stderr)."""
        from aurora_launch.sidecar import auth as auth_module

        env_token = secrets.token_hex(32)
        monkeypatch.setenv(auth_module.ENV_VAR, env_token)
        monkeypatch.setattr(
            auth_module, "_read_first_line_stdin", lambda timeout: "garbage"
        )

        loaded = auth_module.load_token_from_stdin_or_env()
        assert loaded == env_token
        captured = capsys.readouterr()
        assert "stdin token invalid" in captured.err

    def test_both_missing_exits_2(self, monkeypatch):
        """Fail-closed: оба channels missing → exit 2."""
        from aurora_launch.sidecar import auth as auth_module

        monkeypatch.delenv(auth_module.ENV_VAR, raising=False)
        monkeypatch.setattr(
            auth_module, "_read_first_line_stdin", lambda timeout: None
        )

        with pytest.raises(SystemExit) as ex:
            auth_module.load_token_from_stdin_or_env()
        assert ex.value.code == 2

    def test_backward_compat_alias(self, monkeypatch):
        """load_token_from_env() — alias на новый combined loader."""
        from aurora_launch.sidecar import auth as auth_module

        env_token = secrets.token_hex(32)
        monkeypatch.setenv(auth_module.ENV_VAR, env_token)
        monkeypatch.setattr(
            auth_module, "_read_first_line_stdin", lambda timeout: None
        )

        # Alias должен работать — existing server.py не сломается
        assert auth_module.load_token_from_env() == env_token
