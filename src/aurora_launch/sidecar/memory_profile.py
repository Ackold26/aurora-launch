"""Memory profile + policy (Phase Scale S-10).

Tracks process memory (RSS) via psutil and exposes IPC methods so UI can
display a memory pressure indicator. Policy thresholds are ABSOLUTE
(per-process), not "70% of available" — per audit Pf.2 (master-plan v3.1
revised). 70% of available is fragile on 8GB laptops where other apps
already use 6GB; absolute thresholds give predictable behaviour.

Thresholds (per master-plan §④ S-10):
  - Soft warning: 1.0 GB RSS — UI badge appears
  - Hard cap:     1.5 GB RSS — UI nudges user к close project
  - Critical:     2.0 GB RSS — refuse opening additional projects

Policy enforcement is **advisory only** — never hard-rejects the user's
explicit action. Caller decides whether к honour. The IPC returns
{rss_bytes, threshold, severity} so frontend can present a dialog,
toast, or block, depending on context.

Per INV-04: psutil imported lazily inside functions to avoid pulling
it into sidecar cold-start path. Per INV-11: explicit narrow except.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

_log = logging.getLogger(__name__)

# Thresholds in bytes (1 GB = 2**30)
_GB = 2 ** 30
SOFT_WARNING_BYTES: int = 1 * _GB
HARD_CAP_BYTES: int = int(1.5 * _GB)
CRITICAL_BYTES: int = 2 * _GB

Severity = Literal["ok", "warning", "hard_cap", "critical"]


@dataclass(frozen=True)
class MemoryReport:
    """Snapshot of process memory state."""

    rss_bytes: int
    vms_bytes: int
    available_bytes: int
    severity: Severity
    threshold_bytes: int


def get_memory_report() -> MemoryReport:
    """Return current process memory snapshot.

    Raises:
        ImportError: if psutil not installed (treat as ok / unmeasured upstream).
    """
    try:
        import psutil  # type: ignore[import-not-found]
    except ImportError as exc:
        # Re-raise so caller can decide: degrade gracefully (skip policy)
        # vs fail-loud. Default policy in sidecar handler: degrade.
        raise ImportError(
            "psutil not installed — memory policy disabled. "
            "Install via `pip install psutil` to enable."
        ) from exc

    proc = psutil.Process()
    mem = proc.memory_info()
    virt = psutil.virtual_memory()
    rss = int(mem.rss)

    severity: Severity = "ok"
    threshold = SOFT_WARNING_BYTES
    if rss >= CRITICAL_BYTES:
        severity = "critical"
        threshold = CRITICAL_BYTES
    elif rss >= HARD_CAP_BYTES:
        severity = "hard_cap"
        threshold = HARD_CAP_BYTES
    elif rss >= SOFT_WARNING_BYTES:
        severity = "warning"
        threshold = SOFT_WARNING_BYTES

    return MemoryReport(
        rss_bytes=rss,
        vms_bytes=int(mem.vms),
        available_bytes=int(virt.available),
        severity=severity,
        threshold_bytes=threshold,
    )


def format_bytes(n: int) -> str:
    """Human-readable bytes (KB/MB/GB)."""
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    if n < 1024 ** 3:
        return f"{n / (1024 ** 2):.1f} MB"
    return f"{n / (1024 ** 3):.2f} GB"


def policy_advice(report: MemoryReport) -> str:
    """Return advisory text per severity (Russian, ready for UI display)."""
    if report.severity == "ok":
        return "Память в норме."
    if report.severity == "warning":
        return (
            f"Используется {format_bytes(report.rss_bytes)} памяти "
            f"(порог {format_bytes(report.threshold_bytes)}). "
            f"Можно продолжать работу."
        )
    if report.severity == "hard_cap":
        return (
            f"Высокая загрузка памяти: {format_bytes(report.rss_bytes)}. "
            f"Рекомендуется закрыть неиспользуемые проекты."
        )
    # critical
    return (
        f"Критическая загрузка памяти: {format_bytes(report.rss_bytes)}. "
        f"Откройте только один проект за раз, чтобы избежать сбоя."
    )
