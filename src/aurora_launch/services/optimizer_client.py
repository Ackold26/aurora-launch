"""Optimizer adapter layer — Aurora Launch ↔ Aurora MMM Optimizer.

ROADMAP §3.4: Cross-product validation skeleton.

Architecture
-----------
``OptimizerClient`` is an abstract base that defines the two operations Launch
needs from Optimizer:

  list_projects() → list[OptimizerProjectRef]
  get_history(query) → OptimizerHistoryResponse | None

Two concrete implementations ship here:

``MockOptimizerClient``
    Returns deterministic synthetic data derived from the numeric ranges in
    existing sample bundle fixtures. Used in all automated tests; zero disk I/O.

``LocalOptimizerClient``
    Reads the Aurora MMM Optimizer SQLite database on the same machine.
    Requires the ``AURORA_OPTIMIZER_DB_PATH`` env var to point at
    ``<optimizer-appdata>/aurora-econometrica-gui.db``.
    Raises ``OptimizerNotConfigured`` when the env var is absent or the file
    does not exist.

Deferred (cloud-wave)
    ``HttpOptimizerClient`` — REST/gRPC call to a shared Optimizer service.
    Tracked in CROSS_PRODUCT_INTEGRATION.md §Future Work.

Usage (production)
    The sidecar ``validate_against_optimizer`` method resolves the client via
    the DI ServiceContainer (slot ``optimizer_client``).  When no client is
    configured the method returns None with a warning log — graceful degradation.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from datetime import date, timedelta
from uuid import UUID

from aurora_launch.schemas.cross_product import (
    OptimizerHistoryQuery,
    OptimizerHistoryResponse,
    OptimizerProjectRef,
    WeeklyActual,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sentinel exception
# ---------------------------------------------------------------------------


class OptimizerNotConfigured(RuntimeError):
    """Raised when no Optimizer data source is available.

    Callers (validate_against_optimizer) catch this and return null/None —
    graceful degradation so Launch works without Optimizer present.
    """


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class OptimizerClient(ABC):
    """Contract between Aurora Launch and Aurora MMM Optimizer.

    All implementations MUST be thread-safe: the sidecar may call these
    methods from concurrent JSON-RPC handler threads.
    """

    @abstractmethod
    def list_projects(self) -> list[OptimizerProjectRef]:
        """Return all Optimizer projects accessible to this client.

        Implementations should return an empty list (not raise) when the
        data source is accessible but contains no projects.
        """

    @abstractmethod
    def get_history(self, query: OptimizerHistoryQuery) -> OptimizerHistoryResponse | None:
        """Return historical actuals for the specified brand and period.

        Returns None when the brand_code is not found in any project (not
        an error — the proxy brand may simply not have Optimizer data yet).
        Raises OptimizerNotConfigured if the data source became unavailable
        after the client was constructed.
        """


# ---------------------------------------------------------------------------
# Mock implementation (tests + UI demo mode)
# ---------------------------------------------------------------------------

# Synthetic weekly sales baseline for mock data — chosen to produce realistic
# OTC pharma-scale numbers (units sold per week) without requiring real data.
_MOCK_WEEKLY_SALES_BASE: dict[str, float] = {
    "kagotsel": 48_000.0,
    "venarus": 31_500.0,
    "mmx_afala": 12_800.0,
    "default": 25_000.0,
}

_MOCK_PROJECT_UUID = UUID("00000000-0000-0000-0000-000000000001")
_MOCK_START_DATE = date(2023, 1, 2)  # Monday


class MockOptimizerClient(OptimizerClient):
    """Deterministic synthetic Optimizer client for tests and demo mode.

    Returns predictable data based on the brand_code lookup table above.
    Weekly actuals follow a mild sinusoidal seasonality pattern to mimic
    real-world flu-season variation (OTC pharma proxy brands).

    Thread-safe: all state is read-only after construction.
    """

    def __init__(
        self,
        brand_codes: list[str] | None = None,
        n_weeks: int = 52,
    ) -> None:
        """
        Args:
            brand_codes: Brands this mock "knows about". Defaults to the full
                         built-in lookup table keys.
            n_weeks:     How many weeks of history to generate per brand.
        """
        self._brand_codes: list[str] = brand_codes if brand_codes is not None else list(_MOCK_WEEKLY_SALES_BASE.keys())
        self._n_weeks = n_weeks

    def list_projects(self) -> list[OptimizerProjectRef]:
        return [
            OptimizerProjectRef(
                project_uuid=_MOCK_PROJECT_UUID,
                brand_code=bc,
                granularity="weekly",
                last_modified=date(2025, 1, 15),
            )
            for bc in self._brand_codes
        ]

    def get_history(self, query: OptimizerHistoryQuery) -> OptimizerHistoryResponse | None:
        if query.brand_code not in self._brand_codes:
            logger.warning(
                "MockOptimizerClient: brand_code=%r not found in mock data",
                query.brand_code,
            )
            return None

        base_sales = _MOCK_WEEKLY_SALES_BASE.get(query.brand_code, _MOCK_WEEKLY_SALES_BASE["default"])
        actuals = []
        for i in range(self._n_weeks):
            # Mild seasonality: ±20 % peak at week ~10 (flu season onset)
            import math

            seasonality = 1.0 + 0.20 * math.sin(2 * math.pi * (i - 4) / 52)
            sales = round(base_sales * seasonality, 2)
            spend: dict[str, float] = {}
            if query.channels:
                spend = {ch: round(sales * 0.08, 2) for ch in query.channels}
            actuals.append(WeeklyActual(week_index=i, sales=sales, spend_per_channel=spend))

        return OptimizerHistoryResponse(
            brand_code=query.brand_code,
            weekly_actuals=actuals,
            n_observations=len(actuals),
            granularity="weekly",
        )


# ---------------------------------------------------------------------------
# Local implementation (same-machine Optimizer SQLite)
# ---------------------------------------------------------------------------

# Env var that must point to the Optimizer SQLite file.
# Typical value on Windows:
#   %APPDATA%\aurora-econometrica-gui\aurora-econometrica-gui.db
OPTIMIZER_DB_PATH_ENV = "AURORA_OPTIMIZER_DB_PATH"


class LocalOptimizerClient(OptimizerClient):
    """Reads Aurora MMM Optimizer's SQLite database on the local machine.

    Construction raises ``OptimizerNotConfigured`` immediately when:
    - ``AURORA_OPTIMIZER_DB_PATH`` env var is not set, OR
    - The path it points to does not exist on disk.

    This fail-fast design means the sidecar DI layer can decide at startup
    whether to register this client or fall back to None (graceful degradation).

    SQL schema dependency:
    The Optimizer DB must expose at minimum:
      - Table ``projects``:  columns project_id (TEXT/UUID), brand_code (TEXT),
                             granularity (TEXT), updated_at (TEXT ISO-8601)
      - Table ``weekly_actuals``: columns project_id, brand_code, week_index (INT),
                                  sales (REAL), channel_json (TEXT JSON or NULL)

    NOTE: this implementation is a skeleton. The exact schema will be finalized
    when Optimizer ships its public DB contract (tracked in CROSS_PRODUCT_INTEGRATION.md).
    Until then, query methods raise NotImplementedError to signal «schema TBD».
    """

    def __init__(self) -> None:
        db_path_str = os.environ.get(OPTIMIZER_DB_PATH_ENV)
        if not db_path_str:
            raise OptimizerNotConfigured(
                f"Env var {OPTIMIZER_DB_PATH_ENV!r} is not set. "
                "Aurora MMM Optimizer cross-product validation is not available."
            )
        from pathlib import Path

        db_path = Path(db_path_str)
        if not db_path.exists():
            raise OptimizerNotConfigured(
                f"Optimizer DB not found at {db_path}. "
                f"Ensure {OPTIMIZER_DB_PATH_ENV!r} points to a valid Optimizer SQLite file."
            )
        self._db_path = db_path
        logger.info("LocalOptimizerClient: using Optimizer DB at %s", db_path)

    def list_projects(self) -> list[OptimizerProjectRef]:
        """Query Optimizer SQLite for project list.

        Schema TBD — raises NotImplementedError until Optimizer publishes
        its DB contract. See CROSS_PRODUCT_INTEGRATION.md §Optimizer Exports.
        """
        raise NotImplementedError(
            "LocalOptimizerClient.list_projects(): Optimizer DB schema not yet finalized. "
            "See 06_References/CROSS_PRODUCT_INTEGRATION.md §Optimizer Exports."
        )

    def get_history(self, query: OptimizerHistoryQuery) -> OptimizerHistoryResponse | None:
        """Query Optimizer SQLite for weekly actuals.

        Schema TBD — raises NotImplementedError until Optimizer publishes
        its DB contract. See CROSS_PRODUCT_INTEGRATION.md §Optimizer Exports.
        """
        raise NotImplementedError(
            "LocalOptimizerClient.get_history(): Optimizer DB schema not yet finalized. "
            "See 06_References/CROSS_PRODUCT_INTEGRATION.md §Optimizer Exports."
        )
