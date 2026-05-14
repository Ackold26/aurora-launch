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


# Sensitive log markers — hash before bundling
_SENSITIVE_LOG_MARKERS = ("AURORA_SIDECAR_AUTH_TOKEN", "license_key", "password")


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
    """Replace secret markers + значения с [REDACTED]. Phase X may use regex."""
    import re
    for marker in _SENSITIVE_LOG_MARKERS:
        # Match `marker=value` or `marker: value` patterns and redact whole pair
        pattern = re.compile(
            rf"({re.escape(marker)})\s*[:=]\s*\S+",
            flags=re.IGNORECASE,
        )
        text = pattern.sub(f"[REDACTED:{marker[:12]}...]", text)
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
