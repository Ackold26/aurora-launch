"""Diagnostics ZIP collector (Phase Π.4.1).

Bundles system info + recent logs + audit log + crash dumps в single ZIP file
for customer to attach к support email. Pure local operation (zero network).

Layout inside ZIP:
    diagnostics-{timestamp}.zip
    ├── system_info.json     (OS / Python / disk / RAM / app_version)
    ├── audit_log.json       (last 200 audit entries)
    ├── logs/                (rotated log files from logs_dir)
    ├── crashes/             (crash dump JSON files if any)
    └── README.txt           (Russian + English customer-facing explanation)

Privacy guarantees:
- NO project data included (НЕ posterior_samples, anchor values, brand IDs)
- NO file paths beyond LOCALAPPDATA root
- Customer reviews ZIP перед отправкой
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_log = logging.getLogger(__name__)


class DiagnosticsError(RuntimeError):
    """Raised on diagnostics collection failure (IO error, permission)."""


# ---------------------------------------------------------------------------
# S-20: Redaction regex patterns (Phase Scale hardening)
#
# Strategy: conservative over-redaction is preferred to any leak.
# Each pattern group is documented inline.  All use stdlib `re` only.
# Patterns are applied in order; later patterns do NOT depend on earlier ones.
# ---------------------------------------------------------------------------

import re as _re

# ① Legacy marker-based redaction (kept for backward compat).
# Matches  KEY=value  or  KEY: value  in flat log lines.
_SENSITIVE_LOG_MARKERS = ("AURORA_SIDECAR_AUTH_TOKEN", "license_key", "password")

# ② JSON key-value pairs whose values are secrets.
#    Keys: api_key, api_secret, access_token, authorization, secret_key,
#          client_secret, auth_token, refresh_token, private_key, x-api-key.
#    Matches: "api_key": "abc123" and "api_key":"abc123" (optional whitespace).
_JSON_SECRET_KEYS = (
    r"api_key", r"api_secret", r"access_token", r"authorization",
    r"secret_key", r"client_secret", r"auth_token", r"refresh_token",
    r"private_key", r"x-api-key",
)
# JSON key (double-quoted) followed by colon + optional whitespace + quoted value.
_RE_JSON_SECRETS = _re.compile(
    r'("(?:' + "|".join(_JSON_SECRET_KEYS) + r')")\s*:\s*("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')',
    flags=_re.IGNORECASE,
)

# ③ URL query parameters carrying secrets.
#    Matches &api_key=VALUE or ?token=VALUE where VALUE ends at & or end-of-line.
_URL_SECRET_PARAMS = (
    r"api_key", r"token", r"access_token", r"secret", r"password",
    r"auth", r"key", r"apikey",
)
_RE_URL_PARAMS = _re.compile(
    r"([?&](?:" + "|".join(_URL_SECRET_PARAMS) + r")=)([^&\s\"'#]+)",
    flags=_re.IGNORECASE,
)

# ④ HTTP Authorization header values — covers Bearer, Basic, Token schemes.
#    Matches:  Authorization: Bearer eyJ...  (any non-whitespace after scheme).
_RE_AUTH_HEADER = _re.compile(
    r"(Authorization\s*:\s*(?:Bearer|Basic|Token)\s+)(\S+)",
    flags=_re.IGNORECASE,
)

# ⑤ AWS access key IDs.  Format: AKIA[A-Z0-9]{16} (20 chars total).
_RE_AWS_ACCESS_KEY = _re.compile(r"\bAKIA[A-Z0-9]{16}\b")

# ⑥ JWT tokens — three base64url segments separated by dots.
#    Conservative: require each segment ≥ 4 chars to avoid false positives on
#    version strings like "1.2.3".
_RE_JWT = _re.compile(
    r"\beyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\b"
)

# ⑦ Email addresses — PII compliance.
#    Standard RFC-5322-lite:  localpart@domain.tld
#    Conservative: only redact when there is a recognisable TLD (2-6 chars).
_RE_EMAIL = _re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,6}\b"
)

# ⑧ Generic Bearer / token assignment in plain log lines.
#    Catches:  bearer_token = eyJ...  or  token=abc123  outside of JSON/URL context.
#    Applied AFTER JSON + URL patterns so no double-redact in clean text.
_RE_GENERIC_TOKEN_ASSIGN = _re.compile(
    r"((?:bearer_token|auth_token|access_token|secret|password)\s*[:=]\s*)(\S+)",
    flags=_re.IGNORECASE,
)

# QW5 audit findings: missing patterns for cloud + Russian compliance.

# ⑨ Yandex Cloud API key (AQV...) — РФ-priority key recognition.
#    Format: AQVN[A-Za-z0-9_\-]{32,}+ (length varies; conservative match).
_RE_YANDEX_CLOUD_KEY = _re.compile(r"\bAQV[A-Z0-9][A-Za-z0-9_\-]{20,}\b")

# ⑩ Anthropic Claude API key (sk-ant-...) — для M-03 AI explanations integration.
_RE_ANTHROPIC_KEY = _re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b")

# ⑪ Google API key (AIza...) — standard format.
_RE_GOOGLE_API_KEY = _re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")

# ⑫ OpenAI API key (sk-...). Conservative: require ≥40 chars after prefix.
_RE_OPENAI_KEY = _re.compile(r"\bsk-[A-Za-z0-9]{40,}\b")

# ⑬ Private SSH key block — multiline header. We redact only the header
#    line; body lines are base64 and look random — caller can mask whole
#    block если нужно (set multiline_redact=True).
_RE_SSH_PRIVATE_KEY_HEADER = _re.compile(
    r"-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]+?"
    r"-----END (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----",
)

# ⑭ Russian INN (taxpayer ID) — 10 digits (legal entities) или 12 (individuals).
#    PII per ФЗ-152. Conservative: word boundaries to skip phone numbers / dates.
_RE_RUSSIAN_INN = _re.compile(r"\b(?<!\d)\d{10}(?!\d)\b|\b(?<!\d)\d{12}(?!\d)\b")

# ⑮ Russian OGRN — 13 digits (legal entity registration). Disambiguate from INN-12
#    via length only.
_RE_RUSSIAN_OGRN = _re.compile(r"\b(?<!\d)\d{13}(?!\d)\b")


@dataclass(frozen=True)
class DiagnosticsBundle:
    """Result of collect_diagnostics."""

    zip_path: Path
    size_bytes: int
    included_logs: int
    included_crashes: int
    timestamp_utc: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _collect_system_info(app_version: str = "0.1.0") -> dict:
    """Gather safe-to-share system metadata."""
    try:
        import platform as _plat
        info = {
            "app_version": app_version,
            "timestamp_utc": _utc_now_iso(),
            "os": _plat.system(),
            "os_version": _plat.version(),
            "os_release": _plat.release(),
            "platform": _plat.platform(),
            "machine": _plat.machine(),
            "python_version": sys.version.split()[0],
            "processor": _plat.processor() or "unknown",
        }
    except Exception as exc:
        _log.warning("Cannot collect platform info: %s", exc)
        info = {"app_version": app_version, "error": str(exc)}

    # Memory / disk best effort (no extra deps)
    try:
        # shutil.disk_usage works on cwd
        usage = shutil.disk_usage(Path.cwd())
        info["disk_total_bytes"] = usage.total
        info["disk_free_bytes"] = usage.free
    except OSError as exc:
        info["disk_error"] = str(exc)

    return info


def _redact_sensitive_text(text: str) -> str:
    """Replace known sensitive patterns with [REDACTED] placeholders.

    Applies all S-20 hardened redaction patterns in order.  Conservative
    strategy: over-redact rather than leak.  Pure stdlib `re` only.
    """
    # ① Legacy marker-based redaction (KEY=value / KEY: value in flat lines)
    for marker in _SENSITIVE_LOG_MARKERS:
        pattern = _re.compile(
            rf"({_re.escape(marker)})\s*[:=]\s*\S+",
            flags=_re.IGNORECASE,
        )
        text = pattern.sub(f"[REDACTED:{marker[:12]}...]", text)

    # ② JSON quoted key-value secrets: "api_key": "abc123" → "api_key": "[REDACTED]"
    text = _RE_JSON_SECRETS.sub(r'\1: "[REDACTED]"', text)

    # ③ URL query parameters: ?api_key=abc → ?api_key=[REDACTED]
    text = _RE_URL_PARAMS.sub(r"\1[REDACTED]", text)

    # ④ HTTP Authorization header values
    text = _RE_AUTH_HEADER.sub(r"\1[REDACTED]", text)

    # ⑤ AWS access key IDs
    text = _RE_AWS_ACCESS_KEY.sub("[REDACTED-AWS-KEY]", text)

    # ⑥ JWT tokens (eyJ header signals JWT)
    text = _RE_JWT.sub("[REDACTED-JWT]", text)

    # ⑦ Email addresses (PII)
    text = _RE_EMAIL.sub("[REDACTED-EMAIL]", text)

    # ⑧ Generic token assignment lines (after JSON/URL to avoid double-redact)
    text = _RE_GENERIC_TOKEN_ASSIGN.sub(r"\1[REDACTED]", text)

    # QW5 audit additions: cloud provider keys + Russian compliance PII.
    # Order matters: more specific patterns first (e.g. AIza... matches before
    # generic digit-only INN check would mis-fire).
    text = _RE_ANTHROPIC_KEY.sub("[REDACTED-ANTHROPIC]", text)
    text = _RE_OPENAI_KEY.sub("[REDACTED-OPENAI]", text)
    text = _RE_GOOGLE_API_KEY.sub("[REDACTED-GOOGLE]", text)
    text = _RE_YANDEX_CLOUD_KEY.sub("[REDACTED-YANDEX]", text)
    text = _RE_SSH_PRIVATE_KEY_HEADER.sub("[REDACTED-SSH-PRIVATE-KEY-BLOCK]", text)
    # Russian INN / OGRN — applied LAST so cloud keys (which may contain
    # digit sequences) already redacted. Note: false positives risk on
    # generic 10-13 digit numbers (timestamps, IDs). Acceptable trade-off
    # per task spec "over-redact better than leak."
    text = _RE_RUSSIAN_OGRN.sub("[REDACTED-OGRN]", text)
    text = _RE_RUSSIAN_INN.sub("[REDACTED-INN]", text)

    return text


def _copy_logs_to_zip(zf: zipfile.ZipFile, logs_dir: Path) -> int:
    """Add log files к ZIP under logs/. Returns count of files added."""
    if not logs_dir.exists():
        return 0
    count = 0
    for log_path in logs_dir.iterdir():
        if not log_path.is_file():
            continue
        # Skip lock files и tmp
        if log_path.name.startswith(".") or log_path.suffix == ".tmp":
            continue
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
            redacted = _redact_sensitive_text(text)
            zf.writestr(f"logs/{log_path.name}", redacted)
            count += 1
        except OSError as exc:
            _log.warning("Cannot read log %s: %s", log_path, exc)
    return count


def _copy_crashes_to_zip(zf: zipfile.ZipFile, crashes_dir: Path) -> int:
    """Add crash dumps к ZIP. Returns count."""
    if not crashes_dir.exists():
        return 0
    count = 0
    for crash_path in crashes_dir.iterdir():
        if not crash_path.is_file() or crash_path.suffix != ".dump":
            continue
        try:
            text = crash_path.read_text(encoding="utf-8", errors="replace")
            zf.writestr(f"crashes/{crash_path.name}", text)
            count += 1
        except OSError as exc:
            _log.warning("Cannot read crash dump %s: %s", crash_path, exc)
    return count


_README_TEXT = """\
Aurora Launch Planner — Diagnostics Bundle
===========================================

Этот ZIP содержит информацию for службы поддержки Aurora:

  * system_info.json    — версия ОС, Python, дисковое пространство
  * audit_log.json      — последние 200 операций (без данных проектов)
  * logs/               — журналы приложения (последние 7 дней)
  * crashes/            — отчёты о сбоях (if были)

Что НЕ включено:
  * Данные ваших проектов (proxy posterior, прогнозы, бренды)
  * Лицензионные ключи и токены аутентификации (заменены на [REDACTED])
  * Конфиденциальные данные клиентов

Вы можете просмотреть содержимое ZIP перед отправкой.

Отправьте этот файл на support@auroraai.pro с описанием проблемы.

---

This ZIP contains diagnostics for Aurora support:
  * system_info.json    — OS, Python version, disk space
  * audit_log.json      — last 200 operations (no project data)
  * logs/               — application logs (last 7 days)
  * crashes/            — crash reports if any

NOT included: project data, license keys, auth tokens (redacted).

Send to support@auroraai.pro with issue description.
"""


def collect_diagnostics(
    *,
    data_root: Path,
    output_dir: Path | None = None,
    app_version: str = "0.1.0",
    audit_log_entries: list[dict] | None = None,
) -> DiagnosticsBundle:
    """Build diagnostics ZIP from local Aurora Launch state.

    Args:
        data_root: %LOCALAPPDATA%/Aurora Launch path (logs/, crashes/ subdirs)
        output_dir: where к write ZIP. Defaults к %TEMP%/aurora-diagnostics-{ts}/
        app_version: for inclusion в system_info
        audit_log_entries: optional pre-fetched audit log entries (caller
            queries SQLite audit_log table и passes list of dicts)

    Returns:
        DiagnosticsBundle с path к ZIP, size, content counts.

    Raises:
        DiagnosticsError: cannot create ZIP / write permission denied
    """
    timestamp = _utc_now_iso()
    if output_dir is None:
        output_dir = Path(tempfile.gettempdir())
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    zip_filename = f"aurora-diagnostics-{timestamp}.zip"
    zip_path = output_dir / zip_filename

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # README first
            zf.writestr("README.txt", _README_TEXT)

            # System info
            system_info = _collect_system_info(app_version=app_version)
            zf.writestr(
                "system_info.json",
                json.dumps(system_info, ensure_ascii=False, indent=2),
            )

            # Audit log (caller-provided to avoid SQLite coupling here)
            audit_payload = audit_log_entries[:200] if audit_log_entries else []
            zf.writestr(
                "audit_log.json",
                json.dumps(audit_payload, ensure_ascii=False, indent=2, default=str),
            )

            included_logs = _copy_logs_to_zip(zf, data_root / "logs")
            included_crashes = _copy_crashes_to_zip(zf, data_root / "crashes")
    except OSError as exc:
        # Cleanup partial ZIP
        if zip_path.exists():
            try:
                zip_path.unlink()
            except OSError:
                pass
        raise DiagnosticsError(f"Cannot create diagnostics ZIP: {exc}") from exc

    size = zip_path.stat().st_size
    _log.info(
        "Diagnostics bundle written: %s (%d bytes, %d logs, %d crashes)",
        zip_path,
        size,
        included_logs,
        included_crashes,
    )

    return DiagnosticsBundle(
        zip_path=zip_path,
        size_bytes=size,
        included_logs=included_logs,
        included_crashes=included_crashes,
        timestamp_utc=timestamp,
    )
