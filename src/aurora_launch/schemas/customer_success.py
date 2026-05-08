"""B1.5 Customer Success schemas (PHASE_B_REQUIREMENTS §4.3.4)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


_FROZEN_CONFIG = ConfigDict(frozen=True, extra="forbid", validate_assignment=True)


EventType = Literal[
    "proxy_review",
    "anchors_workshop",
    "posterior_update",
    "methodology_question",
    "training_run_supervised",
    "report_review",
    "pilot_kickoff",
    "quarterly_review",
    "custom",
]


class ConsultingLogEntry(BaseModel):
    """One consulting hours log entry — append-only event."""

    model_config = _FROZEN_CONFIG

    event_id: UUID = Field(default_factory=uuid4)
    customer_id: UUID
    machine_id: UUID
    timestamp_start: datetime
    duration_minutes: int = Field(ge=1)
    event_type: EventType
    project_id: Optional[UUID] = None
    notes: Optional[str] = Field(default=None, max_length=2000)
    consulting_hours_charged: Decimal = Field(ge=0, default=Decimal("0"))


class UsageSummary(BaseModel):
    """Aggregated usage report for period."""

    model_config = _FROZEN_CONFIG

    period_start: datetime
    period_end: datetime
    total_hours_used: Decimal
    total_hours_allowed: Decimal
    breakdown_by_event_type: dict[str, Decimal] = Field(default_factory=dict)
    n_launches_initiated: int = Field(ge=0, default=0)
    n_launches_completed: int = Field(ge=0, default=0)
    n_posterior_updates: int = Field(ge=0, default=0)
    avg_forecast_accuracy_12w: Optional[float] = None


class UserPreferences(BaseModel):
    """User preferences с cross-device sync (UX U6)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)  # mutable

    customer_id: UUID
    preferred_audience_framing: Literal["cfo", "cmo", "marketer", "balanced"] = "balanced"
    preferred_chart_style: Literal["minimal", "detailed", "premium"] = "premium"
    chart_color_palette: Literal["default", "high_contrast", "color_blind_safe"] = "default"
    notifications_enabled: bool = True
    quarterly_pdf_email: bool = True
    favorite_proxies: list[str] = Field(default_factory=list, max_length=10)
