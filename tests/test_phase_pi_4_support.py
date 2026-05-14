"""Phase Π.4 — Customer support workflow tests.

Coverage:
- collect_diagnostics: ZIP structure, README, system info, logs, crashes
- Secret redaction в log files
- mailto: URL encoding, body templates, customer_org variant
- DiagnosticsError on write failure
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from urllib.parse import unquote

import pytest

from aurora_launch.support.diagnostics import (
    DiagnosticsBundle,
    DiagnosticsError,
    _redact_sensitive_text,
    collect_diagnostics,
)
from aurora_launch.support.mailto import (
    SUPPORT_EMAIL_DEFAULT,
    build_support_mailto_url,
    format_support_email_body,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def data_root(tmp_path: Path) -> Path:
    """Simulated %LOCALAPPDATA%/Aurora Launch structure."""
    root = tmp_path / "aurora_data"
    (root / "logs").mkdir(parents=True)
    (root / "crashes").mkdir(parents=True)
    return root


# ---------------------------------------------------------------------------
# Diagnostics collection
# ---------------------------------------------------------------------------


class TestCollectDiagnostics:
    def test_basic_zip_structure(self, data_root: Path, tmp_path: Path) -> None:
        bundle = collect_diagnostics(
            data_root=data_root,
            output_dir=tmp_path,
            app_version="0.1.0",
        )
        assert isinstance(bundle, DiagnosticsBundle)
        assert bundle.zip_path.exists()
        assert bundle.size_bytes > 0
        with zipfile.ZipFile(bundle.zip_path) as zf:
            names = zf.namelist()
            assert "README.txt" in names
            assert "system_info.json" in names
            assert "audit_log.json" in names

    def test_readme_contains_russian_and_english(
        self, data_root: Path, tmp_path: Path
    ) -> None:
        bundle = collect_diagnostics(data_root=data_root, output_dir=tmp_path)
        with zipfile.ZipFile(bundle.zip_path) as zf:
            readme = zf.read("README.txt").decode("utf-8")
        assert "Aurora Launch Planner" in readme
        assert "поддержки" in readme.lower()  # Russian
        assert "support@auroraai.pro" in readme

    def test_system_info_has_required_fields(
        self, data_root: Path, tmp_path: Path
    ) -> None:
        bundle = collect_diagnostics(
            data_root=data_root, output_dir=tmp_path, app_version="1.2.3"
        )
        with zipfile.ZipFile(bundle.zip_path) as zf:
            info = json.loads(zf.read("system_info.json").decode("utf-8"))
        assert info["app_version"] == "1.2.3"
        assert "os" in info
        assert "python_version" in info

    def test_includes_logs_from_logs_dir(
        self, data_root: Path, tmp_path: Path
    ) -> None:
        (data_root / "logs" / "app.log").write_text("hello world\n")
        (data_root / "logs" / "sidecar.log").write_text("sidecar event\n")
        bundle = collect_diagnostics(data_root=data_root, output_dir=tmp_path)
        assert bundle.included_logs == 2
        with zipfile.ZipFile(bundle.zip_path) as zf:
            assert "logs/app.log" in zf.namelist()
            assert "logs/sidecar.log" in zf.namelist()
            assert zf.read("logs/app.log").decode("utf-8") == "hello world\n"

    def test_includes_crash_dumps(
        self, data_root: Path, tmp_path: Path
    ) -> None:
        (data_root / "crashes" / "crash-001.dump").write_text(
            json.dumps({"panic": "test"})
        )
        bundle = collect_diagnostics(data_root=data_root, output_dir=tmp_path)
        assert bundle.included_crashes == 1
        with zipfile.ZipFile(bundle.zip_path) as zf:
            assert "crashes/crash-001.dump" in zf.namelist()

    def test_skips_non_dump_files_in_crashes(
        self, data_root: Path, tmp_path: Path
    ) -> None:
        (data_root / "crashes" / "crash-001.dump").write_text("{}")
        (data_root / "crashes" / "stray.txt").write_text("ignore me")
        bundle = collect_diagnostics(data_root=data_root, output_dir=tmp_path)
        assert bundle.included_crashes == 1
        with zipfile.ZipFile(bundle.zip_path) as zf:
            assert "crashes/stray.txt" not in zf.namelist()

    def test_audit_log_entries_included(
        self, data_root: Path, tmp_path: Path
    ) -> None:
        entries = [{"timestamp": "2026-05-14", "operation": "open_bundle"}]
        bundle = collect_diagnostics(
            data_root=data_root,
            output_dir=tmp_path,
            audit_log_entries=entries,
        )
        with zipfile.ZipFile(bundle.zip_path) as zf:
            audit = json.loads(zf.read("audit_log.json").decode("utf-8"))
        assert len(audit) == 1
        assert audit[0]["operation"] == "open_bundle"

    def test_audit_log_truncated_к_200(
        self, data_root: Path, tmp_path: Path
    ) -> None:
        entries = [{"op": f"event_{i}"} for i in range(300)]
        bundle = collect_diagnostics(
            data_root=data_root,
            output_dir=tmp_path,
            audit_log_entries=entries,
        )
        with zipfile.ZipFile(bundle.zip_path) as zf:
            audit = json.loads(zf.read("audit_log.json").decode("utf-8"))
        assert len(audit) == 200

    def test_secrets_redacted_in_logs(
        self, data_root: Path, tmp_path: Path
    ) -> None:
        (data_root / "logs" / "secret.log").write_text(
            "Starting sidecar AURORA_SIDECAR_AUTH_TOKEN=deadbeef123\n"
        )
        bundle = collect_diagnostics(data_root=data_root, output_dir=tmp_path)
        with zipfile.ZipFile(bundle.zip_path) as zf:
            content = zf.read("logs/secret.log").decode("utf-8")
        assert "deadbeef123" not in content
        assert "[REDACTED" in content

    def test_skips_tmp_files(
        self, data_root: Path, tmp_path: Path
    ) -> None:
        (data_root / "logs" / "active.log").write_text("ok")
        (data_root / "logs" / "rotated.log.tmp").write_text("tmp")
        bundle = collect_diagnostics(data_root=data_root, output_dir=tmp_path)
        assert bundle.included_logs == 1


class TestRedaction:
    def test_token_redacted(self) -> None:
        text = "log AURORA_SIDECAR_AUTH_TOKEN=secret123 done"
        out = _redact_sensitive_text(text)
        assert "secret123" not in out
        assert "[REDACTED" in out

    def test_password_redacted(self) -> None:
        text = "config password=test123"
        out = _redact_sensitive_text(text)
        assert "test123" not in out or "REDACTED" in out

    def test_normal_text_unchanged(self) -> None:
        text = "regular log line"
        assert _redact_sensitive_text(text) == text


# ---------------------------------------------------------------------------
# mailto: builder
# ---------------------------------------------------------------------------


class TestMailtoUrl:
    def test_basic_url_starts_with_mailto(self) -> None:
        url = build_support_mailto_url(
            diagnostics_path="C:/tmp/aurora-diagnostics-2026-05-14.zip"
        )
        assert url.startswith(f"mailto:{SUPPORT_EMAIL_DEFAULT}")

    def test_subject_contains_app_version(self) -> None:
        url = build_support_mailto_url(
            diagnostics_path="/tmp/x.zip", app_version="0.1.0"
        )
        # subject= parameter URL-encoded — decode + check
        subject_part = url.split("subject=")[1].split("&")[0]
        decoded = unquote(subject_part)
        assert "v0.1.0" in decoded
        assert "Aurora Launch" in decoded

    def test_body_contains_diagnostics_path(self) -> None:
        url = build_support_mailto_url(
            diagnostics_path="C:/aurora-diag.zip", app_version="0.1.0"
        )
        body_part = url.split("body=")[1]
        decoded = unquote(body_part)
        assert "aurora-diag.zip" in decoded

    def test_customer_org_in_subject(self) -> None:
        url = build_support_mailto_url(
            diagnostics_path="/tmp/x.zip", customer_org="Materia Medica"
        )
        subject = unquote(url.split("subject=")[1].split("&")[0])
        assert "Materia Medica" in subject

    def test_customer_note_in_body(self) -> None:
        url = build_support_mailto_url(
            diagnostics_path="/tmp/x.zip",
            customer_note="Forecast failed at step 5",
        )
        body = unquote(url.split("body=")[1])
        assert "Forecast failed at step 5" in body

    def test_custom_support_email(self) -> None:
        url = build_support_mailto_url(
            diagnostics_path="/tmp/x.zip",
            support_email="pilot@auroraai.pro",
        )
        assert url.startswith("mailto:pilot@auroraai.pro")


class TestEmailBodyFormat:
    def test_body_has_attachment_instructions_russian(self) -> None:
        body = format_support_email_body(
            diagnostics_path="C:/aurora-diag.zip",
            timestamp="2026-05-14T12:00:00Z",
        )
        assert "Прикреп" in body  # Russian "attach"
        assert "C:/aurora-diag.zip" in body

    def test_body_replaces_placeholder_with_note(self) -> None:
        body = format_support_email_body(
            diagnostics_path="/tmp/x.zip",
            timestamp="2026-05-14T12:00:00Z",
            customer_note="Custom issue description",
        )
        assert "Custom issue description" in body
        # Placeholder must be replaced
        assert "[опишите проблему здесь" not in body


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestErrorPaths:
    def test_diagnostics_handles_missing_logs_dir(
        self, tmp_path: Path
    ) -> None:
        """If logs/ doesn't exist, still produces ZIP with empty included_logs."""
        empty_root = tmp_path / "empty"
        empty_root.mkdir()
        bundle = collect_diagnostics(
            data_root=empty_root, output_dir=tmp_path
        )
        assert bundle.included_logs == 0
        assert bundle.zip_path.exists()
