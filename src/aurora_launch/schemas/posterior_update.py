"""B5 Posterior Update schemas (PHASE_B_REQUIREMENTS §5.3.4).

Per POSTERIOR_UPDATE_DESIGN.md — ESS-based partial pooling + BMA fallback +
drift adaptive (audit M-fix min 8 weeks + audit M11 BMA opt-in not silent +
audit M6 auto-trigger all-AND).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


_FROZEN = ConfigDict(frozen=True, extra="forbid", validate_assignment=True)


class PoolingWeights(BaseModel):
    """ESS-based pooling weights per POSTERIOR_UPDATE_DESIGN §1."""

    model_config = _FROZEN

    w_proxy: float = Field(ge=0.0, le=1.0)
    w_recipient: float = Field(ge=0.0, le=1.0)
    weeks_elapsed: int = Field(ge=0)
    similarity_factor_used: float = Field(gt=0)
    recipient_obs_value_used: float = Field(gt=0)

    @model_validator(mode="after")
    def weights_sum_unity(self) -> "PoolingWeights":
        if abs(self.w_proxy + self.w_recipient - 1.0) > 1e-6:
            raise ValueError(
                f"Weights must sum to 1.0, got w_proxy + w_recipient = "
                f"{self.w_proxy + self.w_recipient}"
            )
        return self


class DriftDiagnostics(BaseModel):
    """Drift detection result. Audit M-fix: min 8 weeks for valid result."""

    model_config = _FROZEN

    coverage_observed: float = Field(ge=0.0, le=1.0)
    n_weeks_evaluated: int = Field(ge=0)
    severity: Literal["normal", "mild", "moderate", "severe", "unknown"]
    is_unknown_due_to_few_weeks: bool


class PosteriorDiagnostics(BaseModel):
    """MCMC convergence diagnostics."""

    model_config = _FROZEN

    gelman_rubin_max: float = Field(ge=1.0)
    ess_min: int = Field(ge=0)
    divergent_transitions_count: int = Field(ge=0)
    posterior_predictive_p_value: float = Field(ge=0.0, le=1.0)


class PosteriorUpdateEvent(BaseModel):
    """Audit-trail event for posterior update operation.

    Audit-fixed: includes before_model_hash + after_model_hash for traceability.
    """

    model_config = _FROZEN

    update_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime
    triggering_data_hash: str
    before_model_hash: str
    after_model_hash: str
    pooling_weights: PoolingWeights
    coverage_observed: float = Field(ge=0.0, le=1.0)
    drift_severity: Literal["normal", "mild", "moderate", "severe", "unknown"]
    diagnostics: PosteriorDiagnostics
    methodology_cert_id_previous: Optional[UUID] = None
    methodology_cert_id_new: UUID
    update_mode: Literal["partial_pooling", "bma"] = "partial_pooling"
    bma_opted_in_by_customer: bool = False  # audit M11 — never silent switch


class UpdateEstimate(BaseModel):
    """Closed-form update estimate (HIGH H8 — NOT 'preview', no half-update).

    Cheap deterministic prediction. Customer applies full update for accurate.
    """

    model_config = _FROZEN

    estimated_pooling_weight_after: float = Field(ge=0.0, le=1.0)
    estimated_ci_tightening_pct: float = Field(ge=0.0)
    estimated_release_threshold_eta_weeks: Optional[int] = None
    channel_roi_shift_approximate: dict[str, float] = Field(default_factory=dict)
    notes: str = "This is a closed-form estimate. Apply full update for accurate numbers."
    computation_time_estimate_s: float = Field(default=1.0, ge=0.0)


class AutoTriggerSuggestion(BaseModel):
    """Auto-trigger suggestion for customer review.

    Audit M6: ALL-AND criteria: drift + ≥4 new weeks + CI tightening >10%.
    """

    model_config = _FROZEN

    project_id: UUID
    triggered_at: datetime
    reason: str
    drift_severity: Literal["mild", "moderate", "severe"]
    n_new_weeks: int = Field(ge=4)
    estimated_ci_tightening_pct: float = Field(ge=10.0)
    dismissed_by_customer: bool = False
    dismissed_until: Optional[datetime] = None
