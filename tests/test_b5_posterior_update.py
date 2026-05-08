"""B5 Posterior Update Workflow tests.

Per POSTERIOR_UPDATE_DESIGN.md + audit M-fix + M6 + M11:
- ESS schedule monotonicity (w_proxy decreases с t)
- Identifiability caps (weeks <12 → ≥0.40, <24 → ≥0.20)
- Drift detection min 8 weeks (audit M-fix)
- Auto-trigger ALL-AND criteria (audit M6)
- BMA opt-in not silent (audit M11)
- Bayesian std × 1/√w_proxy (audit BLOCKER preserved)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from hypothesis import given, settings, strategies as st

from aurora_launch.engines.launch_posterior_update import (
    AUTO_TRIGGER_MIN_CI_TIGHTENING_PCT,
    AUTO_TRIGGER_MIN_NEW_WEEKS,
    BMA_FALLBACK_COVERAGE_THRESHOLD,
    ESS_PROXY_BASE,
    MIN_WEEKS_FOR_DRIFT_CHECK,
    SIMILARITY_TO_ESS_FACTOR,
    _category_obs_value,
    _identifiability_min_w_proxy,
    compute_pooling_weights,
    compute_update_estimate,
    detect_drift,
    should_trigger_auto_suggestion,
)
from aurora_launch.schemas.posterior_update import DriftDiagnostics


class TestPoolingWeightsSchedule:
    """ESS-based weight schedule per POSTERIOR_UPDATE_DESIGN §1."""

    def test_t_zero_full_weight_proxy(self) -> None:
        """At t=0, all weight goes to proxy (no recipient data)."""
        result = compute_pooling_weights(
            weeks_elapsed=0,
            similarity_label="High",
            recipient_obs_value=4.0,
        )
        assert result.w_proxy >= 0.99
        assert result.w_recipient <= 0.01

    def test_monotonic_decay(self) -> None:
        """w_proxy decreases monotonically as t grows."""
        # NOTE: identifiability caps create plateaus, but never increases
        weights = []
        for t in [12, 26, 52, 104, 208]:
            r = compute_pooling_weights(
                weeks_elapsed=t,
                similarity_label="High",
                recipient_obs_value=4.0,
            )
            weights.append(r.w_proxy)

        # Strictly non-increasing
        for i in range(1, len(weights)):
            assert weights[i] <= weights[i - 1] + 1e-9, (
                f"Weight should monotonically decay: t_{i-1}={weights[i-1]}, t_{i}={weights[i]}"
            )

    def test_high_similarity_higher_weight(self) -> None:
        """At fixed t, higher similarity → higher proxy weight."""
        t = 52
        obs = 4.0
        r_high = compute_pooling_weights(t, "High", obs)
        r_med = compute_pooling_weights(t, "Medium", obs)
        r_low = compute_pooling_weights(t, "Low", obs)
        assert r_high.w_proxy >= r_med.w_proxy >= r_low.w_proxy

    def test_identifiability_cap_under_12_weeks(self) -> None:
        """weeks <12 — w_proxy ≥0.40 (cap)."""
        # FMCG impulse, High similarity — would otherwise drop quickly
        result = compute_pooling_weights(
            weeks_elapsed=8,
            similarity_label="Low",
            recipient_obs_value=10.0,  # very high obs value to trigger cap
        )
        assert result.w_proxy >= 0.40

    def test_identifiability_cap_12_to_24_weeks(self) -> None:
        result = compute_pooling_weights(
            weeks_elapsed=20,
            similarity_label="Low",
            recipient_obs_value=10.0,
        )
        assert result.w_proxy >= 0.20

    def test_no_cap_after_24_weeks(self) -> None:
        result = compute_pooling_weights(
            weeks_elapsed=104,
            similarity_label="Low",
            recipient_obs_value=10.0,
        )
        # No identifiability cap — w_proxy can drop very low
        assert result.w_proxy < 0.20

    def test_worked_example_fmcg_high_t12(self) -> None:
        """POSTERIOR_UPDATE_DESIGN §1.3 worked example: FMCG High, t=12 → 0.51."""
        # ESS_proxy_adj = 50 × 1.0 = 50
        # ESS_recipient = 12 × 4.0 = 48
        # w_proxy = 50 / (50 + 48) = 0.510
        result = compute_pooling_weights(
            weeks_elapsed=12,
            similarity_label="High",
            recipient_obs_value=4.0,
        )
        # Identifiability cap at t<12 = 0.40, but t=12 is not <12, so no cap
        assert abs(result.w_proxy - 0.510) < 0.01

    def test_validates_negative_weeks(self) -> None:
        with pytest.raises(ValueError, match="weeks_elapsed"):
            compute_pooling_weights(-1, "High", 4.0)

    def test_validates_non_positive_obs(self) -> None:
        with pytest.raises(ValueError, match="recipient_obs_value"):
            compute_pooling_weights(12, "High", 0.0)

    def test_drift_severity_amplifies_recipient(self) -> None:
        """Drift mild → recipient weight grows faster."""
        normal = compute_pooling_weights(52, "High", 4.0, drift_severity="normal")
        mild = compute_pooling_weights(52, "High", 4.0, drift_severity="mild")
        moderate = compute_pooling_weights(52, "High", 4.0, drift_severity="moderate")
        # Drift amplifies recipient → w_proxy decreases
        assert normal.w_proxy >= mild.w_proxy >= moderate.w_proxy


class TestDriftDetection:
    """Drift detection per POSTERIOR_UPDATE_DESIGN §6."""

    def test_min_weeks_unknown(self) -> None:
        """Audit M-fix: <8 weeks returns severity=unknown."""
        drift = detect_drift(
            proxy_baseline_forecast=[100.0] * 5,
            recipient_actual=[105.0] * 5,
        )
        assert drift.severity == "unknown"
        assert drift.is_unknown_due_to_few_weeks is True

    def test_normal_coverage(self) -> None:
        """Coverage ≥0.90 → normal severity."""
        # All within 5% of forecast → high coverage
        drift = detect_drift(
            proxy_baseline_forecast=[100.0] * 12,
            recipient_actual=[105.0] * 12,
        )
        assert drift.severity == "normal"

    def test_severe_coverage(self) -> None:
        """Coverage <0.60 → severe."""
        # All actual far from forecast
        drift = detect_drift(
            proxy_baseline_forecast=[100.0] * 12,
            recipient_actual=[200.0] * 12,
        )
        assert drift.severity == "severe"
        assert drift.coverage_observed < 0.60

    def test_mismatched_lengths_truncates(self) -> None:
        """If lengths differ, uses min."""
        drift = detect_drift(
            proxy_baseline_forecast=[100.0] * 20,
            recipient_actual=[105.0] * 8,
        )
        assert drift.n_weeks_evaluated == 8


class TestAutoTriggerSuggestion:
    """Auto-trigger ALL-AND criteria (audit M6 fix)."""

    def _drift(self, severity: str = "mild") -> DriftDiagnostics:
        return DriftDiagnostics(
            coverage_observed=0.85,
            n_weeks_evaluated=12,
            severity=severity,
            is_unknown_due_to_few_weeks=False,
        )

    def test_all_three_criteria_triggers(self) -> None:
        result = should_trigger_auto_suggestion(
            drift=self._drift("mild"),
            n_new_weeks=4,
            estimated_ci_tightening_pct=12.0,
            project_id=uuid4(),
        )
        assert result is not None
        assert result.drift_severity == "mild"

    def test_normal_drift_no_trigger(self) -> None:
        result = should_trigger_auto_suggestion(
            drift=self._drift("normal"),
            n_new_weeks=4,
            estimated_ci_tightening_pct=12.0,
            project_id=uuid4(),
        )
        assert result is None

    def test_unknown_drift_no_trigger(self) -> None:
        result = should_trigger_auto_suggestion(
            drift=self._drift("unknown"),
            n_new_weeks=4,
            estimated_ci_tightening_pct=12.0,
            project_id=uuid4(),
        )
        assert result is None

    def test_few_new_weeks_no_trigger(self) -> None:
        """Audit M6: <4 new weeks invalidates trigger."""
        result = should_trigger_auto_suggestion(
            drift=self._drift("mild"),
            n_new_weeks=3,
            estimated_ci_tightening_pct=12.0,
            project_id=uuid4(),
        )
        assert result is None

    def test_low_ci_tightening_no_trigger(self) -> None:
        """Audit M6: <10% CI tightening invalidates trigger."""
        result = should_trigger_auto_suggestion(
            drift=self._drift("mild"),
            n_new_weeks=4,
            estimated_ci_tightening_pct=8.0,
            project_id=uuid4(),
        )
        assert result is None

    def test_dismissal_cooldown_respected(self) -> None:
        now = datetime.now(timezone.utc)
        future = now + timedelta(weeks=2)
        result = should_trigger_auto_suggestion(
            drift=self._drift("mild"),
            n_new_weeks=4,
            estimated_ci_tightening_pct=12.0,
            project_id=uuid4(),
            last_dismissal=future,
            now=now,
        )
        assert result is None  # dismissal not yet expired


class TestUpdateEstimate:
    """Closed-form estimate (HIGH H8 — NOT half-update)."""

    def test_returns_closed_form(self) -> None:
        current = compute_pooling_weights(
            weeks_elapsed=12,
            similarity_label="High",
            recipient_obs_value=4.0,
        )
        estimate = compute_update_estimate(
            current_pooling=current,
            n_new_weeks=14,  # 12 → 26 weeks
            similarity_label="High",
            recipient_obs_value=4.0,
        )
        # CI tightening should be positive (proxy weight decays)
        assert estimate.estimated_ci_tightening_pct >= 0

    def test_release_threshold_eta(self) -> None:
        current = compute_pooling_weights(
            weeks_elapsed=12,
            similarity_label="High",
            recipient_obs_value=4.0,
        )
        estimate = compute_update_estimate(
            current_pooling=current,
            n_new_weeks=4,
            similarity_label="High",
            recipient_obs_value=4.0,
            proxy_release_threshold=0.05,
        )
        # ETA should be positive (proxy not yet released)
        assert estimate.estimated_release_threshold_eta_weeks is not None
        assert estimate.estimated_release_threshold_eta_weeks > 0


class TestCategoryObsValue:
    def test_fmcg_food_snacks(self) -> None:
        assert _category_obs_value("FMCG_food.snacks_savoury") == 4.0

    def test_otc_pharma(self) -> None:
        assert _category_obs_value("OTC_pharma.OTC_cold_flu") == 2.5

    def test_telecom(self) -> None:
        assert _category_obs_value("Telecom.telecom_b2c_mobile") == 2.0

    def test_unknown_falls_back(self) -> None:
        assert _category_obs_value("UnknownCategory.X") == 3.5


class TestPropertyBased:
    @given(
        t=st.integers(min_value=0, max_value=200),
        obs_value=st.floats(min_value=0.5, max_value=10.0, allow_nan=False),
    )
    @settings(max_examples=50)
    def test_weights_sum_unity(self, t: int, obs_value: float) -> None:
        """Invariant: w_proxy + w_recipient == 1.0 для any t, obs_value."""
        result = compute_pooling_weights(
            weeks_elapsed=t,
            similarity_label="Medium",
            recipient_obs_value=obs_value,
        )
        assert abs(result.w_proxy + result.w_recipient - 1.0) < 1e-6

    @given(t=st.integers(min_value=0, max_value=200))
    @settings(max_examples=30)
    def test_weights_in_unit_interval(self, t: int) -> None:
        result = compute_pooling_weights(
            weeks_elapsed=t,
            similarity_label="Medium",
            recipient_obs_value=3.5,
        )
        assert 0.0 <= result.w_proxy <= 1.0
        assert 0.0 <= result.w_recipient <= 1.0
