"""B3 Adaptation Layer Pydantic schemas (PHASE_B_REQUIREMENTS §5.1.4).

Frozen contracts для:
- ProxyPriors (5 shape params per channel + global)
- AnchorMagnitudes (recipient-side calibrated magnitudes)
- TransferReport (validation output с heatmap + sensitivity + uncertainty decomp)
- PerChannelHeatmap (per-channel transfer strength)
- SensitivityResult (anchor perturbation effects)
- AnchorUncertaintyDecomp (linear propagation contributions)
- EngineSelectionResult (deterministic engine choice)
- TransferWarning (semantic issues)
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PosteriorParam(BaseModel):
    """Posterior parameter с mean + std + ESS — frozen contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mean: float
    std: float = Field(gt=0)
    n_effective_samples: int = Field(ge=100)


class ProxyPriors(BaseModel):
    """Output of extract_proxy_priors. Per ADAPTATION_RULES §1."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    adstock_decay_per_channel: dict[str, PosteriorParam]
    hill_gamma_per_channel: dict[str, PosteriorParam]
    hill_half_saturation_per_channel: dict[str, PosteriorParam]
    category_seasonality: list[float] = Field(min_length=52, max_length=52)
    long_term_trend_slope: float
    proxy_model_hash: str
    extraction_method: Literal["posterior_mean_std", "full_posterior_samples"]


class PriorParam(BaseModel):
    """Recipient prior parameter — calibrated from proxy + anchors."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mean: float
    std: float = Field(gt=0)
    source: Literal["proxy_transferred", "anchor_calibrated", "fallback_weak"]


class AnchorMagnitudes(BaseModel):
    """Recipient magnitudes calibrated from anchors. Per ADAPTATION_RULES §2."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    baseline_recipient_weekly: list[float] = Field(min_length=52)
    pricing_factor: float
    elasticity_used: float
    distribution_velocity_curve_used: list[float]
    market_share_target_curve: list[float]


class PerChannelHeatmap(BaseModel):
    """Per-channel transfer strength visualization data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    channels: list[str]
    transfer_strength: list[float]
    rationale: list[str]

    @model_validator(mode="after")
    def all_lists_same_length(self) -> "PerChannelHeatmap":
        n = len(self.channels)
        if len(self.transfer_strength) != n or len(self.rationale) != n:
            raise ValueError("channels / transfer_strength / rationale must have same length")
        for s in self.transfer_strength:
            if not 0.0 <= s <= 1.0:
                raise ValueError(f"transfer_strength must be in [0, 1], got {s}")
        return self


class SensitivityResult(BaseModel):
    """Anchor perturbation → forecast effect."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    anchor_field: str
    perturbation_pct: float
    forecast_delta_pct: float
    ci_widening_pct: float


class AnchorUncertaintyDecomp(BaseModel):
    """Linear approximation of anchor uncertainty contribution to forecast CI.

    σ_forecast ≈ √(Σ (∂f/∂a_i)² × σ_a_i²)

    Returns fractional contributions summing to 1.0 (or close).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    market_size_contribution: float = Field(ge=0.0, le=1.0)
    distribution_contribution: float = Field(ge=0.0, le=1.0)
    pricing_contribution: float = Field(ge=0.0, le=1.0)
    creative_contribution: float = Field(ge=0.0, le=1.0)
    competitive_contribution: float = Field(ge=0.0, le=1.0)
    proxy_transfer_contribution: float = Field(ge=0.0, le=1.0)
    total_ci_pct: float = Field(ge=0.0)

    @model_validator(mode="after")
    def contributions_sum_to_unity(self) -> "AnchorUncertaintyDecomp":
        total = (
            self.market_size_contribution + self.distribution_contribution
            + self.pricing_contribution + self.creative_contribution
            + self.competitive_contribution + self.proxy_transfer_contribution
        )
        # Normalized fractions — should sum к 1.0 within float tolerance
        if abs(total - 1.0) > 0.05:
            raise ValueError(
                f"Uncertainty contributions must sum to ~1.0 (±0.05), got {total}"
            )
        return self


class TransferWarning(BaseModel):
    """Semantic validation issue."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    severity: Literal["info", "warning", "blocking"]
    code: str
    message: str
    affected_field: Optional[str] = None
    recovery_action: Optional[str] = None


class ForecastTrajectory(BaseModel):
    """Single forecast sample (weekly values)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    weekly_values: list[float]
    sample_index: int = Field(ge=0)


class TransferReport(BaseModel):
    """Complete transfer validation output."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recipient_priors: dict[str, PriorParam]
    transferred_params_actual: list[str]
    not_transferred: list[str]
    inflation_applied: float = Field(ge=1.0)
    cross_category_distance: int = Field(ge=0, le=4)
    warnings: list[TransferWarning]
    prior_predictive_samples: list[ForecastTrajectory]
    sensitivity_results: list[SensitivityResult]
    per_channel_heatmap: PerChannelHeatmap
    anchor_uncertainty_propagation: AnchorUncertaintyDecomp


class EngineSelectionResult(BaseModel):
    """Deterministic engine selection output (audit M4)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    selected_engine: Literal["single", "multi", "single_with_pooling", "blocked"]
    rationale: str
    n_proxies_used: int = Field(ge=0)
    blocking_reason: Optional[str] = None
