"""Cross-product integration schemas — Launch Planner ↔ Optimizer.

ROADMAP §3.4: «Перекрёстная сверка между Launch Planner и Optimizer».

These schemas define the API contract that Aurora Launch Planner expects from
Aurora MMM Optimizer when cross-product calibration is requested.

Design notes:
- All models are frozen + extra="forbid" (consistent with Aurora Launch schema
  conventions established in proxy.py, forecast.py, bundle.py).
- `OptimizerNotConfigured` is NOT a schema — it lives in optimizer_client.py.
- `CrossProductValidation.deviation_severity` is deterministic (see thresholds
  in CrossProductValidation docstring) so the UI can display a traffic-light.
- `confidence` reflects how many weekly actuals were available for comparison;
  low n_observations → lower confidence even if deviation is small.
"""

from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


_FROZEN = ConfigDict(frozen=True, extra="forbid")


# ---------------------------------------------------------------------------
# Optimizer project reference (List API result item)
# ---------------------------------------------------------------------------


class OptimizerProjectRef(BaseModel):
    """One Optimizer project as returned by the list_projects() adapter call.

    Consumers (Launch Planner) use `brand_code` to match against the proxy
    brand selected by the user. `granularity` must be "weekly" for full
    cross-validation; monthly projects are supported but yield lower confidence.
    """

    model_config = _FROZEN

    project_uuid: UUID
    brand_code: str = Field(min_length=1, max_length=64)
    granularity: Literal["weekly", "monthly"]
    last_modified: date


# ---------------------------------------------------------------------------
# History query (what Launch asks Optimizer for)
# ---------------------------------------------------------------------------


class OptimizerHistoryQuery(BaseModel):
    """Query payload sent to OptimizerClient.get_history().

    `channels` is optional: when None, the adapter returns aggregated total
    spend (sum across all channels). When provided, per-channel spend is
    included in each WeeklyActual entry.
    """

    model_config = _FROZEN

    brand_code: str = Field(min_length=1, max_length=64)
    period_start: date
    period_end: date
    channels: list[str] | None = None

    @model_validator(mode="after")
    def period_ordering(self) -> "OptimizerHistoryQuery":
        if self.period_start > self.period_end:
            raise ValueError(
                f"period_start ({self.period_start}) must be <= period_end ({self.period_end})"
            )
        return self


# ---------------------------------------------------------------------------
# Weekly actuals entry (one row of Optimizer history)
# ---------------------------------------------------------------------------


class WeeklyActual(BaseModel):
    """One week of realized metrics from the Optimizer project.

    `week_index` is 0-based from the project's first data week (not calendar
    index). `spend_per_channel` is optional — populated only when the query
    included a channel list.
    """

    model_config = _FROZEN

    week_index: int = Field(ge=0)
    sales: float = Field(description="Realized sales (units or revenue)")
    spend_per_channel: dict[str, float] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# History response (what OptimizerClient.get_history() returns)
# ---------------------------------------------------------------------------


class OptimizerHistoryResponse(BaseModel):
    """Full history response for one brand from the Optimizer project.

    `n_observations` must equal len(weekly_actuals); enforced by validator.
    `granularity` echoes the project's native cadence so Launch can warn if
    weekly-to-monthly conversion was applied.
    """

    model_config = _FROZEN

    brand_code: str = Field(min_length=1, max_length=64)
    weekly_actuals: list[WeeklyActual]
    n_observations: int = Field(ge=0)
    granularity: Literal["weekly", "monthly"]

    @model_validator(mode="after")
    def n_observations_matches_actuals(self) -> "OptimizerHistoryResponse":
        if self.n_observations != len(self.weekly_actuals):
            raise ValueError(
                f"n_observations={self.n_observations} does not match "
                f"len(weekly_actuals)={len(self.weekly_actuals)}"
            )
        return self


# ---------------------------------------------------------------------------
# Cross-product validation result
# ---------------------------------------------------------------------------


class CrossProductValidation(BaseModel):
    """Result of validating a Launch forecast against Optimizer actuals.

    Severity thresholds (hard-coded, tunable в future release):
      - low    : |deviation_pct| < 15 %
      - medium : 15 % ≤ |deviation_pct| < 35 %
      - high   : |deviation_pct| ≥ 35 %

    `confidence` ∈ [0.0, 1.0]:
      - Derived from n_observations relative to forecast horizon (12 weeks).
      - ≥ 12 observations → 1.0; < 4 → 0.3; interpolated linearly in between.
      - Future: also incorporates similarity score between launch brand and proxy.

    UI interpretation:
      - low    + high confidence  → green badge "Proxy validates forecast"
      - medium + any confidence   → amber badge "Moderate calibration gap"
      - high   + any confidence   → red badge "Large calibration gap — review assumptions"
    """

    model_config = _FROZEN

    proxy_brand: str = Field(min_length=1, max_length=64)
    launch_forecast_value: float = Field(description="Launch point forecast (same units as Optimizer actuals)")
    optimizer_actual_value: float = Field(description="Mean realized Optimizer sales over comparison window")
    deviation_pct: float = Field(description="(launch_forecast - optimizer_actual) / optimizer_actual * 100")
    deviation_severity: Literal["low", "medium", "high"]
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def severity_consistent_with_deviation(self) -> "CrossProductValidation":
        """Verify that severity label matches deviation magnitude."""
        abs_dev = abs(self.deviation_pct)
        expected: Literal["low", "medium", "high"]
        if abs_dev < 15.0:
            expected = "low"
        elif abs_dev < 35.0:
            expected = "medium"
        else:
            expected = "high"
        if self.deviation_severity != expected:
            raise ValueError(
                f"deviation_severity='{self.deviation_severity}' inconsistent with "
                f"deviation_pct={self.deviation_pct:.1f}% (expected '{expected}')"
            )
        return self
