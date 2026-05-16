"""Budget Optimization schemas (ROADMAP §4.4 — Prescriptive Budget Planner).

Pydantic models for BudgetSearchRequest, BestSpendPlan, SpendPlanAlternative.

All float fields carry _finite_check validators per INV-12 (no NaN/Inf in
output from sidecar; per feedback_finite_validator_full_grep session lesson).
"""

from __future__ import annotations

import math
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_FROZEN = ConfigDict(frozen=True, extra="forbid", validate_assignment=True)


def _check_finite(v: float, field_name: str = "value") -> float:
    """Raise ValueError if v is NaN or Inf."""
    if not math.isfinite(v):
        raise ValueError(f"{field_name} must be finite, got {v!r}")
    return v


# ─── Request ─────────────────────────────────────────────────────────────────


class ChannelCap(BaseModel):
    """Min/max spend constraint for a single channel."""

    model_config = _FROZEN

    min: float = Field(ge=0.0, default=0.0)
    max: float = Field(gt=0.0)

    @field_validator("min", "max", mode="before")
    @classmethod
    def _finite(cls, v: object) -> object:
        if isinstance(v, float):
            _check_finite(v, "cap")
        return v

    @model_validator(mode="after")
    def min_le_max(self) -> "ChannelCap":
        if self.min > self.max:
            raise ValueError(
                f"ChannelCap.min ({self.min}) must be ≤ max ({self.max})"
            )
        return self


class BudgetSearchRequest(BaseModel):
    """Customer-facing request: find best spend split for a given total budget.

    Fields
    ------
    total_budget:
        Total budget to distribute (same currency unit as proxy spend data).
        Must be > 0.
    channel_caps:
        Per-channel min/max constraints. Keys must be the channel_ids present
        in the proxy bundle (e.g., "TV", "digital", "OOH").
    horizon_periods:
        Number of periods (weeks if granularity='weekly', else months).
    granularity:
        Time granularity — must match the proxy bundle granularity.
    n_iterations:
        Number of random splits to evaluate (≥ 4, ≤ 5000).
        Default 100 gives good coverage for ≤ 5 channels in < 5 seconds.
    seed:
        Random seed for reproducibility. Default 42.
    """

    model_config = _FROZEN

    total_budget: float = Field(gt=0.0)
    channel_caps: dict[str, ChannelCap] = Field(min_length=1)
    horizon_periods: int = Field(ge=1, le=60)
    granularity: str = Field(default="monthly", pattern="^(monthly|weekly)$")
    n_iterations: int = Field(ge=4, le=5000, default=100)
    seed: int = Field(default=42)

    @field_validator("total_budget", mode="before")
    @classmethod
    def _finite_budget(cls, v: object) -> object:
        if isinstance(v, float):
            _check_finite(v, "total_budget")
        return v

    @model_validator(mode="after")
    def caps_do_not_exceed_budget(self) -> "BudgetSearchRequest":
        for ch, cap in self.channel_caps.items():
            if cap.min > self.total_budget:
                raise ValueError(
                    f"channel_caps[{ch!r}].min ({cap.min}) > total_budget ({self.total_budget})"
                )
        # Audit H-04 (этап 4.5): sum(cap.min) тоже не должен exceed budget.
        # Без этой проверки 3 канала с min=40k каждый и total=100k проходили
        # validation, но потом _random_splits возвращал same split N раз
        # (total_slack < 0 fallback) с alloc.sum() = 120k > budget — overspent.
        total_min = sum(cap.min for cap in self.channel_caps.values())
        if total_min > self.total_budget:
            raise ValueError(
                f"sum(channel_caps[*].min) = {total_min} > total_budget = {self.total_budget}. "
                f"Constraint infeasible — нельзя выделить минимумы всем каналам в рамках бюджета."
            )
        return self


# ─── Response ─────────────────────────────────────────────────────────────────


class BestSpendPlan(BaseModel):
    """Best spend allocation found by grid/random search.

    channel_split maps channel_id → list of per-period spend values
    (length = horizon_periods; uniform split across periods by default).

    expected_total_sales:
        Sum of point_forecast across all horizon periods under this split.
    ci_lower / ci_upper:
        Sum of lower/upper CI bounds across periods (additive).
    methodology_signature:
        Echoed from OrchestrationResult.methodology_signature so caller can
        trace which engine evaluated the best plan.
    n_iterations_used:
        Actual number of splits evaluated (may be < n_iterations if budget
        constraints prune the search space early).
    """

    model_config = _FROZEN

    channel_split: dict[str, list[float]]
    expected_total_sales: float
    ci_lower: float
    ci_upper: float
    methodology_signature: str
    n_iterations_used: int = Field(ge=1)

    @field_validator("expected_total_sales", "ci_lower", "ci_upper", mode="before")
    @classmethod
    def _finite_floats(cls, v: object) -> object:
        if isinstance(v, float):
            _check_finite(v, "forecast aggregate")
        return v

    @model_validator(mode="after")
    def ci_ordering(self) -> "BestSpendPlan":
        if self.ci_lower > self.expected_total_sales:
            raise ValueError(
                f"ci_lower ({self.ci_lower}) > expected_total_sales ({self.expected_total_sales})"
            )
        if self.expected_total_sales > self.ci_upper:
            raise ValueError(
                f"expected_total_sales ({self.expected_total_sales}) > ci_upper ({self.ci_upper})"
            )
        return self


class SpendPlanAlternative(BestSpendPlan):
    """Alternative spend plan (runner-up) returned alongside the best plan.

    rank:
        1-based rank (1 = best, 2 = second-best, …).
    """

    rank: int = Field(ge=1)
