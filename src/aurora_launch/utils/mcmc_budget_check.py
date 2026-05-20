"""MCMC OOM pre-flight + memory monitor (Sprint 2 D5, spec §5.350-353).

Two related concerns:

1.  **Pre-flight check** — before initiating MCMC sampling, verify enough
    RAM is available. If short, surface ``status='low_ram'`` (allow proceed
    on customer opt-in) or ``status='critical'`` (recommend OLS fallback).
    Pure function, side-effect free, safe для frontend invoke.

2.  **MemoryMonitor** — background thread polling ``psutil.virtual_memory().percent``
    during long MCMC runs. When system-wide RAM consumption crosses the
    abort threshold (default 80 %) it sets ``aborted`` and invokes the
    caller-supplied ``on_abort`` hook so the sampling thread can cancel
    cooperatively (no SIGKILL, no terminate — D5 INV-39 compatible).

The customer-facing impact (pilot Q3): on a 4 GB-RAM laptop the Bayesian
training path crashed с raw MemoryError mid-sample. With this module,
the wizard can pre-flight the budget and offer an OLS downgrade, OR start
sampling with a monitor that exits gracefully before the OS swaps to disk.

Design notes:

- ``min_required_bytes`` default 4 GB — derived from observed PyMC NUTS
  peak (≈3.2 GB на 31 obs × 5 channels × 7 params model, headroom + safety).
- ``abort_threshold_pct`` default 80 — leaves OS room to breathe, avoids
  swap-thrashing which makes the abort itself slow.
- Russian recommendations — surfaced directly в UI без localisation layer
  (manager mode, INV-25). EN locale added IF Sprint Buffer EN strings flag
  on (deferred per A16).
- ``status`` enum {"ok", "low_ram", "critical"} — backend whitelist, INV-41
  applies к IPC handler that wraps this module.
- No new dependencies — only ``psutil`` (already declared в pyproject).

INV cross-refs:
- INV-39 — defensive safety net, не proactive MCMC bump
- INV-41 — backend handler whitelists ``status`` + ``suggested_fallback``
- INV-11 — explicit exception handling, no bare pass
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

import psutil

__all__ = [
    "MIN_RAM_AVAILABLE_BYTES",
    "ABORT_RAM_THRESHOLD_PCT",
    "POLL_INTERVAL_SECONDS",
    "BudgetCheckStatus",
    "SuggestedFallback",
    "BudgetCheckResult",
    "MemoryMonitor",
    "check_mcmc_budget",
    "format_bytes_human",
]

_log = logging.getLogger(__name__)


# ─── Constants ────────────────────────────────────────────────────────────────

MIN_RAM_AVAILABLE_BYTES: int = 4_000_000_000  # 4 GB — Bayesian baseline
ABORT_RAM_THRESHOLD_PCT: float = 80.0
POLL_INTERVAL_SECONDS: float = 2.0


# ─── Types ────────────────────────────────────────────────────────────────────

BudgetCheckStatus = Literal["ok", "low_ram", "critical"]
SuggestedFallback = Literal["bayesian", "ols", None]


@dataclass(frozen=True)
class BudgetCheckResult:
    """Pre-flight verdict.

    Fields
    ------
    status : "ok" | "low_ram" | "critical"
        ``ok`` — available ≥ ``min_required_bytes``.
        ``low_ram`` — between half and full requirement: proceed but warn.
        ``critical`` — < half requirement: recommend fallback.
    available_bytes : int
        ``psutil.virtual_memory().available`` snapshot.
    total_bytes : int
        ``psutil.virtual_memory().total``.
    used_pct : float
        ``psutil.virtual_memory().percent`` (system-wide RAM usage).
    recommendation : str
        Plain Russian, customer-facing one-sentence guidance.
    suggested_fallback : "bayesian" | "ols" | None
        ``None`` when status==ok (no downgrade needed). ``ols`` when the
        memory budget recommends a switch to closed-form regression.
    """

    status: BudgetCheckStatus
    available_bytes: int
    total_bytes: int
    used_pct: float
    recommendation: str
    suggested_fallback: SuggestedFallback


# ─── Pre-flight check ─────────────────────────────────────────────────────────


def check_mcmc_budget(
    *,
    min_required_bytes: int = MIN_RAM_AVAILABLE_BYTES,
) -> BudgetCheckResult:
    """Snapshot system memory and classify availability against threshold.

    Pure function — no side effects. Safe to invoke repeatedly, including
    from frontend pre-flight calls before кнопка "Запустить Bayesian".

    Parameters
    ----------
    min_required_bytes : int, default 4 GB
        The minimum available memory considered safe for Bayesian sampling.
        Sub-half of this triggers ``critical``.

    Returns
    -------
    BudgetCheckResult
        Verdict + diagnostic snapshot + Russian recommendation.

    Raises
    ------
    ValueError
        If ``min_required_bytes`` is negative or zero.
    """
    if min_required_bytes <= 0:
        raise ValueError(
            f"min_required_bytes must be positive, got {min_required_bytes}"
        )

    vm = psutil.virtual_memory()
    available = int(vm.available)
    total = int(vm.total)
    used_pct = float(vm.percent)

    if available >= min_required_bytes:
        return BudgetCheckResult(
            status="ok",
            available_bytes=available,
            total_bytes=total,
            used_pct=used_pct,
            recommendation=(
                f"Доступно {format_bytes_human(available)} оперативной памяти — "
                f"достаточно для Bayesian обучения."
            ),
            suggested_fallback=None,
        )

    half_threshold = min_required_bytes // 2
    if available >= half_threshold:
        return BudgetCheckResult(
            status="low_ram",
            available_bytes=available,
            total_bytes=total,
            used_pct=used_pct,
            recommendation=(
                f"Доступно {format_bytes_human(available)} при минимуме "
                f"{format_bytes_human(min_required_bytes)}. Bayesian может "
                "сработать, но рекомендуем закрыть другие приложения или "
                "переключиться на OLS (быстрее, без доверительных интервалов)."
            ),
            suggested_fallback="ols",
        )

    return BudgetCheckResult(
        status="critical",
        available_bytes=available,
        total_bytes=total,
        used_pct=used_pct,
        recommendation=(
            f"Доступно всего {format_bytes_human(available)} — Bayesian модель "
            "почти наверняка упадёт с ошибкой нехватки памяти. Используйте OLS — "
            "точечные оценки сохранятся, но доверительных интервалов не будет."
        ),
        suggested_fallback="ols",
    )


# ─── Memory monitor ───────────────────────────────────────────────────────────


class MemoryMonitor:
    """Background thread polling RAM during MCMC sampling.

    When ``psutil.virtual_memory().percent`` crosses ``abort_threshold_pct``
    the monitor sets ``aborted`` and fires the supplied ``on_abort`` hook so
    the sampler thread can cancel cooperatively. The monitor itself does NOT
    kill any thread — INV-39 cooperative cancel only.

    Use as a context manager OR call ``start()`` / ``stop()`` manually:

    >>> def on_abort(used_pct, message):
    ...     cancel_event.set()
    >>>
    >>> with MemoryMonitor(on_abort=on_abort):
    ...     # ... run pm.sample() ...
    ...     pass

    The monitor swallows individual poll exceptions (logged as warnings)
    so a transient psutil failure does not crash the sampler. A persistent
    failure stops polling but does not raise.
    """

    def __init__(
        self,
        *,
        abort_threshold_pct: float = ABORT_RAM_THRESHOLD_PCT,
        poll_interval_s: float = POLL_INTERVAL_SECONDS,
        on_abort: Callable[[float, str], None] | None = None,
    ) -> None:
        if not 0.0 < abort_threshold_pct <= 100.0:
            raise ValueError(
                f"abort_threshold_pct must be in (0, 100], got {abort_threshold_pct}"
            )
        if poll_interval_s <= 0.0:
            raise ValueError(
                f"poll_interval_s must be positive, got {poll_interval_s}"
            )

        self._threshold = float(abort_threshold_pct)
        self._poll_interval = float(poll_interval_s)
        self._on_abort = on_abort
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.aborted: threading.Event = threading.Event()
        self.last_reading_pct: float | None = None

    def start(self) -> None:
        """Spawn the polling thread. Re-start after stop() requires a new instance."""
        if self._thread is not None:
            raise RuntimeError("MemoryMonitor already started — create new instance")
        self._stop_event.clear()
        self.aborted.clear()
        self.last_reading_pct = None
        self._thread = threading.Thread(
            target=self._loop,
            name="aurora-mcmc-memory-monitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal stop and join the polling thread (best-effort timeout)."""
        self._stop_event.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=self._poll_interval * 2 + 1.0)
        self._thread = None

    def _loop(self) -> None:
        """Polling loop — runs until stop_event set OR abort triggered."""
        while not self._stop_event.is_set():
            try:
                used_pct = float(psutil.virtual_memory().percent)
                self.last_reading_pct = used_pct
                if used_pct >= self._threshold and not self.aborted.is_set():
                    self.aborted.set()
                    msg = (
                        f"Потребление памяти достигло {used_pct:.1f}% "
                        f"(порог {self._threshold:.0f}%). Прерываем MCMC, "
                        "чтобы избежать сбоя системы."
                    )
                    _log.warning("MCMC memory abort triggered: %s", msg)
                    if self._on_abort is not None:
                        try:
                            self._on_abort(used_pct, msg)
                        except Exception as exc:  # noqa: BLE001
                            # Caller hook bug — log + continue to stop loop cleanly
                            _log.error(
                                "MemoryMonitor on_abort callback raised: %s", exc
                            )
                    return
            except (psutil.Error, OSError) as exc:
                # Transient psutil/OS failure — log + continue polling
                _log.warning("MemoryMonitor poll error (continuing): %s", exc)
            # Use Event.wait so stop() interrupts sleep immediately
            self._stop_event.wait(self._poll_interval)

    def __enter__(self) -> MemoryMonitor:
        self.start()
        return self

    def __exit__(self, *_args: Any) -> None:
        self.stop()


# ─── Formatting helper ────────────────────────────────────────────────────────


def format_bytes_human(value: int) -> str:
    """Render bytes as compact human-readable Russian-locale string.

    Examples
    --------
    >>> format_bytes_human(512)
    '512 Б'
    >>> format_bytes_human(2_000_000_000)
    '1.86 ГБ'
    """
    if value < 0:
        return f"−{format_bytes_human(-value)}"
    if value < 1024:
        return f"{value} Б"
    if value < 1024 ** 2:
        return f"{value / 1024:.1f} КБ"
    if value < 1024 ** 3:
        return f"{value / 1024 ** 2:.1f} МБ"
    return f"{value / 1024 ** 3:.2f} ГБ"
