# Aurora Launch - Posterior Update Design

**Status:** Accepted (S005b closed 2026-05-04)
**Authority:** P4 в `00_Overview/PRINCIPLES.md` + Section 4 `MATH_REFERENCE.md`
**Sprint context:** Sprint B5 implementation reference
**Related ADR:** `decisions/ADR-004-ess-based-weight-schedule.md` - locks ESS-based partial pooling + BMA fallback
**Owner:** Маша (math design) + Антон (domain validation, autonomous mandate)

## Контекст

P4 declares: proxy постепенно "ослабевает" по weight schedule по мере накопления recipient'ом данных. Не "on/off switch", а continuous weighting. Этот документ финализирует:

1. **ESS-based weight schedule formula** с calibrated constants (ESS_proxy_base, recipient_obs_value)
2. **Similarity-adjusted ESS_proxy** - more similar proxy = больший virtual sample size
3. **Proxy release threshold** - когда proxy фактически выходит из влияния
4. **Partial pooling vs BMA** - lock partial pooling primary, BMA fallback при drift
5. **Identifiability mitigations** - min data threshold, max shrinkage cap, weak-data warnings
6. **Drift detection** - empirical coverage based, adaptive weight reduction
7. **Posterior update event audit log** - full diagnostic state captured per refit
8. **Sensitivity testing strategy** Sprint B5

Sprint B5 implements `engines/launch_posterior_update.py` per этот документ.

---

## 1. ESS-Based Weight Schedule

### 1.1 Core Formula

```
w_proxy(t) = ESS_proxy_adj / (ESS_proxy_adj + ESS_recipient(t))
w_recipient(t) = 1 - w_proxy(t)
```

где:
- `t` = number of weeks since launch (recipient data accumulated)
- `ESS_proxy_adj` = similarity-adjusted virtual sample size of proxy priors
- `ESS_recipient(t)` = effective sample size from recipient data

### 1.2 Calibrated Constants

**Virtual sample size base:**
```python
ESS_PROXY_BASE = 50
```

**Similarity adjustment factor:**
```python
SIMILARITY_TO_ESS_FACTOR = {
    "High":         1.0,   # full informativeness
    "Medium":       0.7,   # moderately informative
    "Low":          0.5,   # weakly informative (proxy still helps но less)
}

ESS_proxy_adj = ESS_PROXY_BASE × SIMILARITY_TO_ESS_FACTOR[verdict]
```

**Recipient observation value (per week):**
```python
RECIPIENT_OBS_VALUE = {
    # Short-cycle (impulse) - high observation value, fast accumulation
    "FMCG_food.snacks_*":           4.0,
    "FMCG_beverage.beverage_*":     4.0,
    # Mid-cycle staples
    "FMCG_food.dairy_*":            3.5,
    "FMCG_food.household":          3.0,
    "Cosmetics.cosmetics_mass_*":   3.0,
    # Long-cycle (durable, subscription)
    "Cosmetics.cosmetics_premium_*": 2.5,
    "Telecom.*":                    2.0,
    "Banking.*":                    2.0,
    "B2B.*":                        1.5,
    # Pharma (regulated, slow signal)
    "OTC_pharma.*":                 2.5,
    "Rx_pharma.*":                  1.5,
}

DEFAULT_RECIPIENT_OBS_VALUE = 3.5  # fallback
```

**Why these values:**

ESS_PROXY_BASE = 50 calibrated через ESS-based Bayesian update math (Konstantinopoulos & Massaro 2014). Schedule shape - hyperbolic decay - theoretically grounded. Value 50 chosen для FMCG midpoint (T=12w → ~0.51), которое matches operational expectation что mid-launch period proxy still informative но recipient signals strengthening.

**Note vs MATH_REFERENCE Section 4:** preliminary schedule в MATH_REFERENCE was illustrative target curve (T=12w ≈ 0.55, T=26w ≈ 0.30, T=40+ ≈ 0.10). This document's ESS-based formula **supersedes** preliminary schedule. ESS-based hyperbolic decay differs slightly - at T=52w it gives 0.19 (preliminary suggested 0.10). Difference reflects:
- Hyperbolic decay (theoretically derived) is naturally slower at tail vs ad-hoc target
- Tail values better calibrated by formal Bayesian math чем preliminary intuition
- PROXY_RELEASE_THRESHOLD = 0.10 hits at t ≈ 113w для FMCG High - acceptable handoff window

MATH_REFERENCE Section 4 will be updated to reference этот document как authority.

RECIPIENT_OBS_VALUE varies categorically because:
- Impulse purchase data fully informative каждую неделю (стохастическое поведение recipient'а быстро видно)
- Long-cycle (cosmetics, telecom) decisions - autocorrelation high, каждая неделя дает less unique info
- Pharma - regulated channels limit signal, slow accumulation

### 1.3 Worked Schedule Examples

**Example 1: FMCG snacks, similarity High (S=0.85+)**

```
ESS_proxy_adj = 50 × 1.0 = 50
recipient_obs_value = 4.0

t=0:    w_proxy = 50 / (50 + 0) = 1.000
t=4:    w_proxy = 50 / (50 + 16) = 0.758
t=8:    w_proxy = 50 / (50 + 32) = 0.610
t=12:   w_proxy = 50 / (50 + 48) = 0.510
t=16:   w_proxy = 50 / (50 + 64) = 0.439
t=26:   w_proxy = 50 / (50 + 104) = 0.325
t=40:   w_proxy = 50 / (50 + 160) = 0.238
t=52:   w_proxy = 50 / (50 + 208) = 0.194
t=78:   w_proxy = 50 / (50 + 312) = 0.138
t=104:  w_proxy = 50 / (50 + 416) = 0.107
t=113:  w_proxy = 50 / (50 + 452) ≈ 0.100  # release threshold reached
t=156:  w_proxy = 50 / (50 + 624) = 0.074
t=190:  w_proxy = 50 / (50 + 760) = 0.062  # below release threshold (proxy independent)
t=∞:    w_proxy → 0
```

**Example 2: OTC pharma, similarity Medium (S=0.70)**

```
ESS_proxy_adj = 50 × 0.7 = 35
recipient_obs_value = 2.5

t=4:    w_proxy = 35 / (35 + 10) = 0.778
t=12:   w_proxy = 35 / (35 + 30) = 0.538
t=26:   w_proxy = 35 / (35 + 65) = 0.350
t=52:   w_proxy = 35 / (35 + 130) = 0.212
t=104:  w_proxy = 35 / (35 + 260) = 0.119
```

**Example 3: B2B, similarity Low (S=0.55)**

```
ESS_proxy_adj = 50 × 0.5 = 25
recipient_obs_value = 1.5

t=12:   w_proxy = 25 / (25 + 18) = 0.581
t=26:   w_proxy = 25 / (25 + 39) = 0.391
t=52:   w_proxy = 25 / (25 + 78) = 0.243
t=104:  w_proxy = 25 / (25 + 156) = 0.138
```

### 1.4 Proxy Release Threshold

```python
PROXY_RELEASE_THRESHOLD = 0.10
```

Когда `w_proxy < 0.10` → proxy фактически "released" из модели:
- UI shows badge "Proxy independent" (recipient полностью самостоятельный)
- Methodology Certificate отмечает "Phase: standalone (proxy released)"
- Re-fit can drop proxy priors completely (use weakly informative defaults)

**Cross-app handoff trigger:** при release threshold + accumulated 52+ weeks data → suggest user transition к Aurora Optimize standalone.

**Release timing examples** (typical FMCG High similarity, ESS_proxy_adj=50, obs_value=4.0):
- w_proxy = 0.10 reached at t ≈ 113 weeks (~2.2 years)
- Compares to 0.05 threshold which would require ~237 weeks (~4.6 years) - too long для practical handoff window

Threshold 0.10 calibrated к realistic Aurora Launch → Optimize transition window (~2 years). Customer subscription remains active throughout, transition is opt-in suggestion not forced migration.

---

## 2. Partial Pooling vs BMA - Architecture Choice

### 2.1 Partial Pooling (Primary, Default)

**Mechanism:** single Bayesian model, prior strength controlled by `w_proxy`.

```python
# engines/launch_posterior_update.py

import math

def construct_partial_pooled_priors(
    transferred_priors: RecipientPriors,
    w_proxy: float,
) -> RecipientPriors:
    """Adjust prior strength based on proxy weight (Bayesian precision math).
    
    Bayesian derivation: prior precision τ_prior = w_proxy × τ_original (linear weight).
    Therefore variance σ² scales as 1/w_proxy, std σ scales as 1/√w_proxy.
    
    w_proxy=1.0: priors fully informative (как initial transfer, std unchanged)
    w_proxy=0.5: std × √2 ≈ 1.414 (variance × 2)
    w_proxy=0.10: std × √10 ≈ 3.16 (variance × 10)
    w_proxy=0.01: std × 10 (variance × 100, near-uninformative)
    """
    strength_factor = 1.0 / math.sqrt(max(w_proxy, 0.01))  # std multiplier (Bayesian precision)
    return RecipientPriors(
        baseline_trajectory=transferred_priors.baseline_trajectory,
        # baseline as anchor magnitude - не подверженно proxy weight (anchor-driven)
        betas={
            c: PriorSpec(
                mean=spec.mean,
                std=spec.std * strength_factor,
            )
            for c, spec in transferred_priors.betas.items()
        },
        adstock_decay={
            c: PriorSpec(
                mean=spec.mean,
                std=spec.std * strength_factor,
            )
            for c, spec in transferred_priors.adstock_decay.items()
        },
        hill_gamma={
            c: PriorSpec(mean=spec.mean, std=spec.std * strength_factor)
            for c, spec in transferred_priors.hill_gamma.items()
        },
        hill_k={
            c: PriorSpec(mean=spec.mean, std=spec.std * strength_factor)
            for c, spec in transferred_priors.hill_k.items()
        },
        seasonality=SeasonalityPrior(
            weekly_pattern=transferred_priors.seasonality.weekly_pattern,
            weekly_std=transferred_priors.seasonality.weekly_std * strength_factor,
        ),
        trend=TrendPrior(
            slope_mean=transferred_priors.trend.slope_mean,
            slope_std=transferred_priors.trend.slope_std * strength_factor,
        ),
        provenance=transferred_priors.provenance,
    )
```

**Pros:** clean Bayesian semantics, single posterior, reuse modeler.py.
**Cons:** at low proxy weight, prior near-uninformative - может undertrain если recipient data also weak.

### 2.2 BMA Fallback (Drift Triggered)

**Mechanism:** train two models separately, average forecasts.

```python
def bma_combine_forecasts(
    proxy_priors_forecast: ForecastHorizon,
    recipient_only_forecast: ForecastHorizon,
    w_proxy: float,
) -> ForecastHorizon:
    """Bayesian Model Averaging - combined predictive distribution.

    Math: combined predictive Y* ~ w × N(μ_p, σ_p²) + (1-w) × N(μ_r, σ_r²) (mixture).
    For CI extraction, use moment-matched Gaussian approximation:
      μ_combined = w × μ_p + (1-w) × μ_r
      σ²_combined = w × σ_p² + (1-w) × σ_r² + w × (1-w) × (μ_p - μ_r)²
      (last term: between-model variance contribution)

    NOTE: linear interpolation of CI bounds (mean ± z × σ) wrong because:
    - σ_p² ≠ σ_r² in general (heteroscedastic)
    - mixture variance has between-model term
    - CI bounds не additive linearly when spreads differ
    """
    import math
    Z_BY_LEVEL = {0.50: 0.674, 0.80: 1.282, 0.95: 1.960}

    horizon_weeks = proxy_priors_forecast.horizon_weeks

    def combined_at(level: float) -> tuple[list[float], list[float]]:
        z = Z_BY_LEVEL[level]
        proxy_lo = getattr(proxy_priors_forecast, f"ci_{int(level*100)}_lower")
        proxy_hi = getattr(proxy_priors_forecast, f"ci_{int(level*100)}_upper")
        recipient_lo = getattr(recipient_only_forecast, f"ci_{int(level*100)}_lower")
        recipient_hi = getattr(recipient_only_forecast, f"ci_{int(level*100)}_upper")

        lower_combined: list[float] = []
        upper_combined: list[float] = []
        for i in range(horizon_weeks):
            mu_p = proxy_priors_forecast.mean[i]
            mu_r = recipient_only_forecast.mean[i]
            sigma_p = (proxy_hi[i] - proxy_lo[i]) / (2 * z)  # back из CI bounds
            sigma_r = (recipient_hi[i] - recipient_lo[i]) / (2 * z)

            mu_combined = w_proxy * mu_p + (1 - w_proxy) * mu_r
            var_combined = (
                w_proxy * sigma_p ** 2
                + (1 - w_proxy) * sigma_r ** 2
                + w_proxy * (1 - w_proxy) * (mu_p - mu_r) ** 2
            )
            sigma_combined = math.sqrt(var_combined)
            lower_combined.append(mu_combined - z * sigma_combined)
            upper_combined.append(mu_combined + z * sigma_combined)
        return lower_combined, upper_combined

    ci_50_lower, ci_50_upper = combined_at(0.50)
    ci_80_lower, ci_80_upper = combined_at(0.80)
    ci_95_lower, ci_95_upper = combined_at(0.95)

    mean_combined = [
        w_proxy * mp + (1 - w_proxy) * mr
        for mp, mr in zip(proxy_priors_forecast.mean, recipient_only_forecast.mean)
    ]

    # Uncertainty decomposition (proportional к moment-matched variance contributions)
    decomp_proxy = sum(w_proxy * ((proxy_priors_forecast.ci_95_upper[i] - proxy_priors_forecast.ci_95_lower[i]) / (2 * 1.96)) ** 2 for i in range(horizon_weeks))
    decomp_recipient = sum((1 - w_proxy) * ((recipient_only_forecast.ci_95_upper[i] - recipient_only_forecast.ci_95_lower[i]) / (2 * 1.96)) ** 2 for i in range(horizon_weeks))
    decomp_between = sum(w_proxy * (1 - w_proxy) * (proxy_priors_forecast.mean[i] - recipient_only_forecast.mean[i]) ** 2 for i in range(horizon_weeks))
    total = decomp_proxy + decomp_recipient + decomp_between
    uncertainty_decomposition = {
        "proxy_uncertainty": decomp_proxy / total if total > 0 else 0,
        "recipient_uncertainty": decomp_recipient / total if total > 0 else 0,
        "between_model_uncertainty": decomp_between / total if total > 0 else 0,
        "anchor_uncertainty": 0.0,  # accounted for в proxy/recipient priors
        "sampling_uncertainty": 0.0,  # accounted for в posterior σ
    }

    return ForecastHorizon(
        horizon_weeks=horizon_weeks,
        mean=mean_combined,
        ci_50_lower=ci_50_lower, ci_50_upper=ci_50_upper,
        ci_80_lower=ci_80_lower, ci_80_upper=ci_80_upper,
        ci_95_lower=ci_95_lower, ci_95_upper=ci_95_upper,
        uncertainty_decomposition=uncertainty_decomposition,
    )
```

**When BMA fallback triggered:**
- Severe drift detected (coverage < 0.60, см. Section 4)
- User explicit toggle "use BMA instead of partial pooling" (Advanced setting)

**Pros:** clean separation - proxy vs recipient models не "пересекаются". Useful когда recipient deviates strongly.
**Cons:** 2× training time. Recipient-only fit at low data может overfit.

### 2.3 Decision Lock (per ADR-004)

**Default Phase B:** partial pooling. BMA = fallback при severe drift.

**Phase D consideration:** if customer demand for explicit BMA mode (e.g., regulatory audit requires "two independent forecasts averaged"), может expose BMA как explicit mode.

---

## 3. Refit Trigger Logic

### 3.1 Minimum Data Threshold

```python
MIN_RECIPIENT_WEEKS_FOR_REFIT = 4
```

Before T=4 weeks accumulated, **don't refit** - too noisy. Use initial transfer priors directly. UI shows "Posterior update available после 4 недель данных".

### 3.2 Refit Cadence (Recommended)

```python
DEFAULT_REFIT_CADENCE = "monthly"  # ~4-week intervals
```

User can override:
- Weekly (для high-stakes launches с rapid signal change)
- Monthly (default, balanced)
- Quarterly (для slow categories like B2B)

UI shows "Next posterior update recommended: 2026-12-15".

### 3.3 Manual Refit

User can trigger refit anytime:
- "Update model with new data" button
- Upload new recipient DSM/Mediascope data
- System validates >=4 weeks new data added since last refit

---

## 4. Drift Detection + Adaptive Adjustment

### 4.1 Empirical Coverage Computation

После refit, compute coverage of recipient data в proxy-priors-driven 95% CI:

```python
MIN_WEEKS_FOR_DRIFT_CHECK = 8  # binomial noise too high below this

def compute_empirical_coverage(
    actual_values: np.ndarray,        # observed recipient sales per week
    proxy_priors_ci_lower: np.ndarray,  # 95% CI lower from proxy-priors model
    proxy_priors_ci_upper: np.ndarray,
) -> Optional[float]:
    """Returns % of weeks where actual ∈ [CI_lower, CI_upper], or None if too few weeks.

    With < 8 weeks, binomial variance в coverage estimate too high (e.g., 4 weeks
    с 1 outlier = 75% coverage, могут falsely flag drift). Below threshold,
    return None и assume normal coverage (skip adaptive adjustment).
    """
    n = len(actual_values)
    if n < MIN_WEEKS_FOR_DRIFT_CHECK:
        return None  # caller should treat as "normal coverage" (skip drift adjustment)
    in_ci = (actual_values >= proxy_priors_ci_lower) & (actual_values <= proxy_priors_ci_upper)
    return float(in_ci.mean())
```

Expected: coverage ≈ 0.95 for 95% CI. Lower = drift detected. При None (< 8 weeks data), drift detection skipped - normal schedule applied.

### 4.2 Adaptive Adjustment Rules

```python
def adjust_recipient_obs_value_for_drift(
    base_obs_value: float,
    coverage: Optional[float],  # None = insufficient data for drift check
) -> Optional[float]:
    """Accelerate weight reduction если recipient diverges от proxy expectations.

    Returns None if severe drift detected (caller switches к BMA mode).
    coverage=None (too few weeks) → normal obs_value (skip adjustment, no false drift).
    """
    if coverage is None or coverage >= 0.90:
        return base_obs_value          # normal (or insufficient data, treat as normal)
    elif coverage >= 0.80:
        return base_obs_value * 1.5    # mild drift
    elif coverage >= 0.60:
        return base_obs_value * 3.0    # moderate drift - aggressive reduction
    else:
        return None  # severe - switch to BMA mode (Section 4.4)
```

**Drift severity classification:**
```python
def classify_drift(coverage: Optional[float]) -> Literal["unknown", "none", "mild", "moderate", "severe"]:
    if coverage is None:
        return "unknown"  # insufficient data
    if coverage >= 0.90:
        return "none"
    elif coverage >= 0.80:
        return "mild"
    elif coverage >= 0.60:
        return "moderate"
    return "severe"
```

This causes faster proxy weight reduction для drift-detected projects:

**Worked example: FMCG snacks, similarity High, drift coverage 0.75**

```
base_obs_value = 4.0 → adjusted = 4.0 × 3.0 = 12.0
ESS_proxy_adj = 50

t=12: w_proxy = 50 / (50 + 12 × 12) = 50 / 194 = 0.258  (instead of 0.510 normal)
t=26: w_proxy = 50 / (50 + 12 × 26) = 50 / 362 = 0.138  (instead of 0.325)
```

Proxy released significantly faster.

### 4.3 Drift Visualization (UI Sprint B5)

`PosteriorUpdateStep.svelte` shows:
- Empirical coverage gauge (target 0.95, actual computed)
- Drift severity badge: ✅ None / ⚠️ Mild / 🟠 Moderate / 🔴 Severe
- "Why drift detected": tooltip с topline reasons (e.g., "Кампания провалилась первые 4 недели" or "Recipient grows faster than proxy")
- Updated weight schedule график

### 4.4 Severe Drift (BMA Fallback)

Coverage < 0.60 → switch to BMA mode:

```python
def severe_drift_workflow(
    project: AuroraBundle,
    new_data: RecipientData,
) -> RefitResult:
    """When coverage < 0.60, partial pooling unreliable. Switch to BMA."""
    # Train recipient-only model (priors не from proxy, weakly informative)
    recipient_only_model = train_mmm_with_weak_priors(new_data)
    
    # Existing proxy-priors model unchanged
    proxy_priors_model = project.get_model("recipient")  # initial transfer model
    
    # BMA combine
    w_proxy_severe = 0.20  # capped low for severe drift
    combined_forecast = bma_combine_forecasts(
        proxy_priors_forecast=proxy_priors_model.forecast(),
        recipient_only_forecast=recipient_only_model.forecast(),
        w_proxy=w_proxy_severe,
    )
    
    return RefitResult(
        method="BMA_severe_drift",
        w_proxy=w_proxy_severe,
        coverage=coverage,
        warning="Severe drift detected. Switched to BMA с two independent models.",
    )
```

UI prominently warns: "Severe drift detected. Recipient develops differently from proxy expectations. Aurora switched to two-model averaging (BMA)."

---

## 5. Identifiability Mitigations

### 5.1 Max Shrinkage Cap (Early Data)

При short recipient data (4-12 weeks), recipient may не overcome proxy local minimum. Cap max shrinkage:

```python
def cap_proxy_weight_for_short_data(
    w_proxy_computed: float,
    weeks_observed: int,
) -> float:
    """Don't allow proxy weight too low until enough recipient data."""
    if weeks_observed < 12:
        return max(w_proxy_computed, 0.40)  # at least 40% proxy weight
    elif weeks_observed < 24:
        return max(w_proxy_computed, 0.20)
    return w_proxy_computed
```

This prevents over-fast proxy reduction в short data scenarios.

### 5.2 Posterior Predictive Diagnostic

After each refit, validate model fit:

```python
def diagnose_posterior_fit(model: TrainedModel) -> DiagnosticResult:
    return DiagnosticResult(
        gelman_rubin_max=model.posterior.gelman_rubin().max(),
        ess_min=model.posterior.ess().min(),
        divergent_transitions=model.posterior.diverging.sum(),
        posterior_predictive_p_value=compute_pp_pvalue(model),
        identifiability_warnings=collect_identifiability_warnings(model),
    )

DIAGNOSTIC_THRESHOLDS = {
    "gelman_rubin_max": 1.05,         # convergence target
    "ess_min": 400,                    # sampling adequacy
    "divergent_transitions": 0,        # ideal zero
    "posterior_predictive_p_value": (0.05, 0.95),  # not too extreme
}
```

UI warns user если diagnostics fail. Project not committed unless user confirms (override).

### 5.3 Weak Recipient Data Warning

If recipient data has:
- Less than 4 weeks → no refit
- 4-12 weeks AND noise level high (CV > 30%) → warn "data too noisy for reliable refit"
- 12+ weeks but flat (no media variation) → warn "limited media signal in recipient data, posterior update will be limited"

---

## 6. Audit Log Event

Per `ADR-002` storage layer, refit events appended к `posterior_update_log.json`:

```python
class PosteriorUpdateEvent(BaseModel):
    """Audit log entry for posterior update."""
    schema_version: Literal["1.0"] = "1.0"
    event_id: str  # UUID v4
    timestamp: datetime
    weeks_of_recipient_data: int
    
    # Weight schedule
    w_proxy_before: float = Field(ge=0, le=1)
    w_proxy_after: float = Field(ge=0, le=1)
    w_proxy_method: Literal["partial_pooling", "BMA", "BMA_severe_drift"]
    
    # Drift state
    empirical_coverage: float = Field(ge=0, le=1)
    drift_severity: Literal["none", "mild", "moderate", "severe"]
    recipient_obs_value_used: float
    ess_proxy_adjusted: float
    ess_recipient_computed: float
    
    # Triggering data + model traceability
    triggering_data_hash: str  # SHA-256 of incremental recipient data
    before_model_hash: str      # SHA-256 of models/recipient_model.pickle BEFORE refit
    after_model_hash: str       # SHA-256 of models/recipient_model.pickle AFTER refit
    new_weeks_added: int
    
    # Diagnostics
    gelman_rubin_max: float
    ess_min: int
    divergent_transitions: int
    posterior_predictive_p_value: float
    identifiability_warnings: List[str]
    
    # User context
    triggered_by: Literal["scheduled", "manual", "data_upload", "drift_alert"]
    user_note: Optional[str] = None
```

### 6.1 Reproducibility

Each event captures full state нужный для traceability:
- `triggering_data_hash` → SHA-256 incremental data → can verify input
- `before_model_hash` + `after_model_hash` → SHA-256 of model pickle blobs → can verify which model produced which forecast
- Weights + diagnostics → can verify output

**Model storage policy (per ADR-002 SCHEMA_DESIGN):** `.aurora` bundle stores **latest model only** в `models/recipient_model.pickle`. Historical models NOT preserved within bundle (size limits). Audit trail в `posterior_update_log.json` references model hashes; for full byte-identical reconstruction of historical model, restore from `.aurora.bak.N` rolling backups (Section 9 SCHEMA_DESIGN).

**Why latest-only:** typical `models/recipient_model.pickle` is 10-15MB. With 13+ refits over 1 year (monthly cadence), historical preservation would push bundle к 130+ MB (audit performance budget concern). Rolling backups provide 4-deep history; methodology certificate captures full audit trail.

**Phase D consideration:** if customer demand для full historical model reconstruction (regulatory audit), separate `models/history/` directory с timestamped pickles can be added (additive schema migration v3.0 → v3.1).

### 6.2 Methodology Certificate Integration

При generating Methodology Certificate PDF, include posterior update history:

```
Posterior Update History:

| Date | Weeks | w_proxy | Drift | Method |
|---|---|---|---|---|
| 2026-09-15 | 4 | 1.00 → 0.76 | None | partial_pooling |
| 2026-10-15 | 8 | 0.76 → 0.61 | None | partial_pooling |
| 2026-11-15 | 12 | 0.61 → 0.51 | None | partial_pooling |
| 2026-12-15 | 16 | 0.51 → 0.44 | Mild (coverage 0.85) | partial_pooling |
| 2027-02-15 | 24 | 0.44 → 0.18 | Moderate (coverage 0.72) | partial_pooling |
```

---

## 7. Implementation Workflow

### 7.1 Refit Pipeline (Sprint B5)

```python
# engines/launch_posterior_update.py

def posterior_update(
    project: AuroraBundle,
    new_recipient_data: RecipientData,
    triggered_by: str = "manual",
) -> RefitResult:
    """Run posterior update workflow."""
    
    # 1. Load current state
    current_priors = project.get_recipient_priors()
    similarity_verdict = project.get_proxy_metadata().confidence_verdict
    weeks_observed_total = project.get_total_weeks_observed() + new_recipient_data.weeks_count
    category = project.get_metadata().category
    
    # 2. Min threshold check
    if weeks_observed_total < MIN_RECIPIENT_WEEKS_FOR_REFIT:
        return RefitResult(
            success=False,
            reason=f"Insufficient data ({weeks_observed_total}w < {MIN_RECIPIENT_WEEKS_FOR_REFIT}w threshold)",
        )
    
    # 3. Compute drift coverage (using existing recipient_priors model on full observed data)
    full_observed = project.get_recipient_data_history() + new_recipient_data
    proxy_priors_model = project.get_model("recipient")
    pp_forecast_at_observed_weeks = proxy_priors_model.forecast_for_weeks(full_observed.weeks)
    coverage = compute_empirical_coverage(
        actual_values=full_observed.sales,
        proxy_priors_ci_lower=pp_forecast_at_observed_weeks.ci_95_lower,
        proxy_priors_ci_upper=pp_forecast_at_observed_weeks.ci_95_upper,
    )
    drift_severity = classify_drift(coverage)
    
    # 4. Determine method
    if drift_severity == "severe":
        return severe_drift_workflow(project, full_observed)
    
    # 5. Compute weights (partial pooling)
    obs_value_base = RECIPIENT_OBS_VALUE.get(category, DEFAULT_RECIPIENT_OBS_VALUE)
    obs_value_adjusted = adjust_recipient_obs_value_for_drift(obs_value_base, coverage)
    
    ess_proxy_adj = ESS_PROXY_BASE * SIMILARITY_TO_ESS_FACTOR[similarity_verdict]
    ess_recipient = weeks_observed_total * obs_value_adjusted
    w_proxy_raw = ess_proxy_adj / (ess_proxy_adj + ess_recipient)
    w_proxy = cap_proxy_weight_for_short_data(w_proxy_raw, weeks_observed_total)
    
    # 6. Construct partial-pooled priors + train
    new_priors = construct_partial_pooled_priors(current_priors, w_proxy)
    new_model = train_mmm_with_priors(
        sales=full_observed.sales,
        media=full_observed.media,
        priors=new_priors,
    )
    
    # 7. Diagnostic check
    diagnostics = diagnose_posterior_fit(new_model)
    if diagnostics.gelman_rubin_max > 1.05:
        # Surface warning, не block
        pass
    
    # 8. Save event + new model
    event = PosteriorUpdateEvent(
        event_id=str(uuid.uuid4()),
        timestamp=datetime.now(),
        weeks_of_recipient_data=weeks_observed_total,
        w_proxy_before=project.get_current_w_proxy(),
        w_proxy_after=w_proxy,
        w_proxy_method="partial_pooling",
        empirical_coverage=coverage,
        drift_severity=drift_severity,
        recipient_obs_value_used=obs_value_adjusted,
        ess_proxy_adjusted=ess_proxy_adj,
        ess_recipient_computed=ess_recipient,
        triggering_data_hash=hash_data(new_recipient_data),
        new_weeks_added=new_recipient_data.weeks_count,
        gelman_rubin_max=diagnostics.gelman_rubin_max,
        ess_min=diagnostics.ess_min,
        divergent_transitions=diagnostics.divergent_transitions,
        posterior_predictive_p_value=diagnostics.posterior_predictive_p_value,
        identifiability_warnings=diagnostics.identifiability_warnings,
        triggered_by=triggered_by,
    )
    
    project.append_posterior_update(event)
    project.set_model("recipient", new_model)
    project.save()
    
    return RefitResult(
        success=True,
        event=event,
        new_forecast=new_model.forecast_horizons(),
    )
```

### 7.2 UI Flow (Sprint B5)

```
PosteriorUpdateStep.svelte (Sprint B5):

┌────────────────────────────────────────────────┐
│ Posterior Update                               │
├────────────────────────────────────────────────┤
│ Current state:                                 │
│   Weeks observed: 12                           │
│   Current proxy weight: 0.51                   │
│   Last update: 2026-11-15                      │
│                                                 │
│ Upload new recipient data:                     │
│   [📂 DSM Group XLSX]                          │
│   [📂 Mediascope TV (optional)]                │
│   [📂 Mediascope Digital (optional)]           │
│                                                 │
│ [Compute Update Preview]                       │
│                                                 │
│ Preview:                                        │
│   Weeks after update: 16                       │
│   Coverage check: 0.85 (mild drift) ⚠️         │
│   New proxy weight: 0.51 → 0.36                │
│   Method: partial_pooling                      │
│                                                 │
│   [Streaming MCMC trace visualization]         │
│   [Diagnostic plot: posterior predictive]      │
│                                                 │
│ Warnings:                                       │
│   ⚠️ Mild drift detected. Recipient growing    │
│     faster than proxy expectations.            │
│                                                 │
│ [Cancel]                  [Confirm Update]     │
└────────────────────────────────────────────────┘
```

### 7.3 Streaming MCMC (Audit B6)

`/launch/v1/posterior_update` endpoint streams MCMC traces к UI как Server-Sent Events. User видит progress в real-time. Cancellation supported (kill button).

---

## 8. Sensitivity Tests Sprint B5

`tests/integration/test_posterior_update.py`:

### 8.1 Convergence to Truth

```python
def test_posterior_update_converges_to_truth():
    """Synthetic recipient evolved from known proxy. After 52w, model recovers truth."""
    proxy = generate_synthetic_proxy(category="FMCG_food.snacks_savoury.chips")
    truth_recipient = derive_synthetic_recipient(
        proxy, similarity=0.85, true_betas={"TV": 2.5e6, "digital": 1.2e6}
    )
    
    # Initial transfer
    initial_priors = adapt(proxy, truth_recipient.anchors)
    initial_forecast = forecast_with_priors(initial_priors)
    initial_mape = compute_mape(initial_forecast.mean, truth_recipient.true_values[:52])
    
    # Posterior updates at 4, 12, 26, 52 weeks
    project = AuroraBundle.create_from_initial_transfer(initial_priors)
    for week in [4, 8, 12, 16, 26, 52]:
        new_data = truth_recipient.true_data[:week]
        result = posterior_update(project, new_data, triggered_by="test")
        assert result.success
    
    # At 52w, MAPE should be <12% (close to recipient-only fit)
    final_forecast = project.get_recipient_model().forecast_horizons()
    final_mape = compute_mape(final_forecast.horizon_52w.mean, truth_recipient.true_values[52:104])
    assert final_mape < 0.12, f"Final MAPE {final_mape:.2%}, expected < 12%"


def test_drift_detection_accelerates_reduction():
    """Recipient deviates from proxy → faster weight reduction."""
    proxy = generate_synthetic_proxy(category="FMCG_food.snacks_savoury.chips")
    drifted_recipient = derive_synthetic_recipient(
        proxy, similarity=0.85, drift_factor=0.4  # 40% deviation от proxy expectation
    )
    
    project = AuroraBundle.create_from_initial_transfer(adapt(proxy, drifted_recipient.anchors))
    result = posterior_update(project, drifted_recipient.data[:12], triggered_by="test")
    
    # Coverage low → drift detected → w_proxy below normal
    assert result.event.drift_severity in ("moderate", "severe")
    normal_w_proxy_at_12w = 0.510  # from non-drift schedule
    assert result.event.w_proxy_after < normal_w_proxy_at_12w * 0.7  # accelerated


def test_identifiability_capped_short_data():
    """Short recipient data → max shrinkage cap respected."""
    proxy = generate_synthetic_proxy()
    short_data = mock_recipient_data(weeks=8)  # short
    
    project = AuroraBundle.create_from_initial_transfer(...)
    result = posterior_update(project, short_data, triggered_by="test")
    
    # Cap: at 8w, w_proxy >= 0.40
    assert result.event.w_proxy_after >= 0.40
```

### 8.2 Property-Based Tests

```python
from hypothesis import given, strategies as st

@given(
    weeks=st.integers(min_value=4, max_value=200),
    similarity_verdict=st.sampled_from(["High", "Medium", "Low"]),
)
def test_w_proxy_monotonic_decreasing(weeks, similarity_verdict):
    """More recipient data = lower proxy weight (assuming no drift)."""
    obs_value = 3.5
    ess_proxy = ESS_PROXY_BASE * SIMILARITY_TO_ESS_FACTOR[similarity_verdict]
    
    w_at_t = lambda t: ess_proxy / (ess_proxy + t * obs_value)
    
    assert w_at_t(weeks) >= w_at_t(weeks + 4)  # monotonic decreasing


@given(
    coverage=st.floats(min_value=0.0, max_value=1.0),
    base_obs=st.floats(min_value=1.0, max_value=10.0),
)
def test_drift_adjustment_increases_obs_value(coverage, base_obs):
    """Lower coverage = larger obs_value (faster reduction)."""
    if coverage >= 0.90:
        adjusted = adjust_recipient_obs_value_for_drift(base_obs, coverage)
        assert adjusted == base_obs
    elif coverage >= 0.80:
        assert adjust_recipient_obs_value_for_drift(base_obs, coverage) > base_obs
```

### 8.3 Pilot Validation (Sprint B6)

При live-test (Materia Medica или FMCG launch team):
- Track w_proxy schedule по weeks
- Track empirical coverage at 4w, 12w, 26w
- Compare predicted MAPE vs actual MAPE - schedule calibration validated

---

## 9. Edge Cases

### 9.1 Multi-Proxy Mode

При multi-proxy (S007), used **aggregate ESS** model: all proxies contribute combined virtual sample size, recipient must accumulate enough data чтобы overcome combined proxy weight.

**Why aggregate vs per-proxy:**
- Per-proxy independent decay: each proxy releases at different t. Hierarchical model has dynamic structure - hard to re-fit cleanly.
- Aggregate: simple - recipient ESS overcomes combined proxy ESS. Hierarchical model retains structural integrity throughout schedule.
- Practical: at threshold release, ALL proxies released simultaneously - recipient transitions к standalone в один момент.

```python
def multi_proxy_posterior_update(
    project: AuroraBundle,
    new_data: RecipientData,
) -> RefitResult:
    """Posterior update для multi-proxy hierarchical model (aggregate ESS approach)."""
    proxies = project.get_proxies()
    pooling_weights = project.get_pooling_weights()  # user-set, preserved

    # Aggregate ESS: weighted sum over proxies (по их similarity verdicts)
    # Multi-proxy adds 5% inflation per extra proxy (per SIMILARITY_FRAMEWORK Section 6)
    multi_penalty = 1.0 + 0.05 * (len(proxies) - 1)
    ess_proxy_aggregate = sum(
        pw * ESS_PROXY_BASE * SIMILARITY_TO_ESS_FACTOR[p.verdict]
        for pw, p in zip(pooling_weights, proxies)
    ) / multi_penalty  # divide for inflation (less informative aggregate)

    # Recipient ESS uses category of recipient, not proxies
    recipient_category = project.get_metadata().category
    obs_value = RECIPIENT_OBS_VALUE.get(recipient_category, DEFAULT_RECIPIENT_OBS_VALUE)
    ess_recipient = new_data.total_weeks * obs_value

    w_proxy_aggregate = ess_proxy_aggregate / (ess_proxy_aggregate + ess_recipient)
    w_proxy_aggregate = cap_proxy_weight_for_short_data(w_proxy_aggregate, new_data.total_weeks)

    # Re-fit hierarchical model: single aggregate proxy weight, individual pooling preserved
    new_model = train_multi_proxy_hierarchical_with_weights(
        proxies, new_data,
        proxy_aggregate_weight=w_proxy_aggregate,
        pooling_weights=pooling_weights,
    )

    return RefitResult(
        method="partial_pooling_multi",
        w_proxy=w_proxy_aggregate,
        # ... etc
    )
```

**Performance budget multi-proxy refit:** 60-150s (vs 30-60s single-proxy) - hierarchical model 2-3× более expensive.

### 9.2 Posterior Update без media data

If new data is sales-only (DSM but no Mediascope), posterior update applies к baseline + seasonality only. Media betas + adstock + hill remain at previous estimates. Warning surfaced.

### 9.3 Data Quality Issue в New Recipient Data

Validators (DATA_REQUIREMENTS Section 4) check new data перед refit:
- Negative values → block
- Extreme outliers (>5σ from rolling mean) → warn user, allow override
- Mixed currencies → block

If issues - refit blocked, user fixes data first.

### 9.4 Aurora Optimize Handoff (Phase D Trigger)

При w_proxy < 0.10 + 52+ weeks data (release threshold per ADR-004):
- UI banner: "Ваш бренд готов к standard MMM. Рассмотрите переход на Aurora Optimize."
- Click → seamless project file transfer (.aurora bundle opens в Optimize, schema additive ignored)
- Pricing:client остаётся на Suite bundle или downgrades.

---

## 10. Implementation Files (Sprint B5)

**Backend:**
- `engines/launch_posterior_update.py` - posterior_update + helpers (construct_partial_pooled_priors, cap_proxy_weight, classify_drift)
- `engines/drift_detector.py` - compute_empirical_coverage + classify_drift
- `engines/multi_proxy_posterior_update.py` - multi-proxy variant

**Tests:**
- `tests/unit/test_posterior_update_weights.py` - ESS formula calibration
- `tests/integration/test_posterior_update.py` - convergence + drift + identifiability
- Property-based tests как Section 8.2

**API endpoints:**
- `POST /launch/v1/posterior_update` - run refit (streaming SSE)
- `GET /launch/v1/posterior_update/preview` - compute expected weight change без full refit

**UI Sprint B5:**
- `src/lib/components/PosteriorUpdateStep.svelte`
- `src/lib/components/DriftCoverageGauge.svelte`
- `src/lib/components/WeightScheduleChart.svelte`

---

## 11. Связанные документы

- `decisions/ADR-004-ess-based-weight-schedule.md` - workflow choice authority
- `decisions/ADR-002-storage-layer.md` - где хранится posterior_update_log.json
- `decisions/ADR-003-pretrain-vs-joint-training.md` - re-fit с reduced priors paradigm
- `MATH_REFERENCE.md` Section 4 - canonical posterior update formulas
- `ADAPTATION_RULES.md` - initial transfer (priors source для posterior update)
- `../00_Overview/PRINCIPLES.md` P4 - мягкий partial pooling principle
- `../02_Data_Spec/SIMILARITY_FRAMEWORK.md` - similarity verdict (used для ESS_proxy_adj)
- `../05_Sessions/SESSION_NEXT_QUESTIONS.md` S005b closed reference
- Konstantinopoulos & Massaro (2014) "Effective Sample Size in Bayesian Hierarchical Models"
- Hoeting et al. (1999) "Bayesian Model Averaging" (BMA fallback foundation)
- Vehtari et al. (2021) "Rank-normalization, folding, and localization: An improved R̂"
