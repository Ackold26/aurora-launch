"""S-20: Redaction regex hardening tests (Phase Scale).

15+ test cases covering:
  - ① Legacy marker-based redaction
  - ② JSON key-value secret pairs
  - ③ URL query parameters
  - ④ HTTP Authorization headers
  - ⑤ AWS access key IDs
  - ⑥ JWT tokens
  - ⑦ Email addresses (PII)
  - ⑧ Generic token assignment lines
  - Edge cases: empty values, whitespace variants, multi-occurrence, false-positive guards
"""
from __future__ import annotations

import pytest

from aurora_launch.support.diagnostics import _redact_sensitive_text


# ---------------------------------------------------------------------------
# ① Legacy marker-based redaction
# ---------------------------------------------------------------------------

class TestLegacyMarkers:
    def test_legacy_auth_token_equals(self) -> None:
        """AURORA_SIDECAR_AUTH_TOKEN=secretXXX → redacted."""
        result = _redact_sensitive_text("AURORA_SIDECAR_AUTH_TOKEN=secretXXX")
        assert "secretXXX" not in result
        assert "REDACTED" in result

    def test_legacy_password_colon(self) -> None:
        """password: hunter2 → redacted (colon-separated)."""
        result = _redact_sensitive_text("password: hunter2")
        assert "hunter2" not in result
        assert "REDACTED" in result

    def test_legacy_license_key_equals(self) -> None:
        """license_key=XXXX-YYYY → redacted."""
        result = _redact_sensitive_text("license_key=XXXX-YYYY-1234")
        assert "XXXX-YYYY-1234" not in result
        assert "REDACTED" in result


# ---------------------------------------------------------------------------
# ② JSON key-value secret pairs
# ---------------------------------------------------------------------------

class TestJsonSecrets:
    def test_json_api_key_quoted(self) -> None:
        """{"api_key": "abc123"} → value replaced."""
        result = _redact_sensitive_text('{"api_key": "abc123"}')
        assert "abc123" not in result
        assert "REDACTED" in result

    def test_json_authorization_no_space(self) -> None:
        """{"authorization":"Bearer xyz"} (no space after colon)."""
        result = _redact_sensitive_text('{"authorization":"Bearer xyz"}')
        assert "Bearer xyz" not in result
        assert "REDACTED" in result

    def test_json_access_token(self) -> None:
        """{"access_token": "tok_live_abc"} → redacted."""
        result = _redact_sensitive_text('{"access_token": "tok_live_abc"}')
        assert "tok_live_abc" not in result

    def test_json_safe_key_not_redacted(self) -> None:
        """False-positive guard: {"app_version": "1.2.3"} must NOT be redacted."""
        result = _redact_sensitive_text('{"app_version": "1.2.3"}')
        assert "1.2.3" in result

    def test_json_multiple_occurrences(self) -> None:
        """Two api_key pairs in same text — both redacted."""
        text = '{"api_key": "first", "api_key": "second"}'
        result = _redact_sensitive_text(text)
        assert "first" not in result
        assert "second" not in result


# ---------------------------------------------------------------------------
# ③ URL query parameters
# ---------------------------------------------------------------------------

class TestUrlQueryParams:
    def test_url_api_key_param(self) -> None:
        """https://api.example.com/v1?api_key=mysecret → redacted."""
        result = _redact_sensitive_text("https://api.example.com/v1?api_key=mysecret")
        assert "mysecret" not in result
        assert "REDACTED" in result

    def test_url_token_in_middle_of_querystring(self) -> None:
        """?foo=bar&token=tok123&baz=qux — only token value redacted."""
        result = _redact_sensitive_text("https://x.com/route?foo=bar&token=tok123&baz=qux")
        assert "tok123" not in result
        # Non-secret params preserved
        assert "baz=qux" in result

    def test_url_safe_param_not_redacted(self) -> None:
        """False-positive guard: ?page=2&sort=desc must NOT be redacted."""
        result = _redact_sensitive_text("https://x.com/results?page=2&sort=desc")
        assert "page=2" in result
        assert "sort=desc" in result


# ---------------------------------------------------------------------------
# ④ HTTP Authorization headers
# ---------------------------------------------------------------------------

class TestAuthHeaders:
    def test_bearer_header(self) -> None:
        """Authorization: Bearer eyJtoken → value redacted."""
        result = _redact_sensitive_text("Authorization: Bearer eyJabctoken123")
        assert "eyJabctoken123" not in result
        assert "REDACTED" in result

    def test_basic_auth_header(self) -> None:
        """Authorization: Basic dXNlcjpwYXNz → redacted."""
        result = _redact_sensitive_text("Authorization: Basic dXNlcjpwYXNz")
        assert "dXNlcjpwYXNz" not in result

    def test_auth_header_whitespace_variants(self) -> None:
        """Authorization:  Bearer tok (extra space after colon)."""
        result = _redact_sensitive_text("Authorization:  Bearer tok_extra_space")
        assert "tok_extra_space" not in result


# ---------------------------------------------------------------------------
# ⑤ AWS access key IDs
# ---------------------------------------------------------------------------

class TestAwsKeys:
    def test_aws_access_key_id(self) -> None:
        """AKIAIOSFODNN7EXAMPLE → redacted."""
        result = _redact_sensitive_text("key=AKIAIOSFODNN7EXAMPLE")
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "REDACTED-AWS-KEY" in result

    def test_non_aws_akia_not_redacted(self) -> None:
        """False-positive guard: AKAIFOO (not AKIA format) must survive."""
        result = _redact_sensitive_text("AKAIFOO is a vendor name")
        # AKAIFOO doesn't match AKIA[A-Z0-9]{16}
        assert "AKAIFOO" in result


# ---------------------------------------------------------------------------
# ⑥ JWT tokens
# ---------------------------------------------------------------------------

class TestJwtTokens:
    def test_jwt_redacted(self) -> None:
        """Standard 3-part JWT (eyJ header) → [REDACTED-JWT]."""
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        result = _redact_sensitive_text(f"token={jwt}")
        assert jwt not in result
        assert "REDACTED-JWT" in result

    def test_version_string_not_jwt(self) -> None:
        """False-positive guard: 1.2.3 must NOT be treated as JWT."""
        result = _redact_sensitive_text("version=1.2.3")
        assert "1.2.3" in result


# ---------------------------------------------------------------------------
# ⑦ Email addresses (PII)
# ---------------------------------------------------------------------------

class TestEmailRedaction:
    def test_email_redacted(self) -> None:
        """user@example.com → [REDACTED-EMAIL]."""
        result = _redact_sensitive_text("contact: user@example.com")
        assert "user@example.com" not in result
        assert "REDACTED-EMAIL" in result

    def test_email_in_log_line(self) -> None:
        """Email embedded mid-line is still found."""
        result = _redact_sensitive_text("Login attempt from admin@auroraai.pro failed")
        assert "admin@auroraai.pro" not in result


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_string(self) -> None:
        """Empty input returns empty string without error."""
        assert _redact_sensitive_text("") == ""

    def test_no_secrets_passthrough(self) -> None:
        """Benign log line is returned unchanged."""
        line = "INFO 2026-05-15 app started, version=1.0.0, pid=1234"
        result = _redact_sensitive_text(line)
        assert result == line

    def test_multiple_pattern_types_in_one_text(self) -> None:
        """Text with JWT, email, and AWS key — all three redacted."""
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        text = (
            f"user=admin@corp.io key=AKIAIOSFODNN7EXAMPLE token={jwt}"
        )
        result = _redact_sensitive_text(text)
        assert "admin@corp.io" not in result
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert jwt not in result

    def test_empty_value_after_key(self) -> None:
        """api_key= (empty value) — should not crash, non-secret remains."""
        # Empty after = produces no \S+ match — key should survive unchanged
        result = _redact_sensitive_text("api_key=")
        # No crash is the main invariant; empty match means no redact token
        assert "api_key=" in result

    def test_idempotent_already_redacted(self) -> None:
        """Applying redaction twice does not corrupt [REDACTED] markers."""
        first = _redact_sensitive_text("Authorization: Bearer secrettoken")
        second = _redact_sensitive_text(first)
        assert second == first
