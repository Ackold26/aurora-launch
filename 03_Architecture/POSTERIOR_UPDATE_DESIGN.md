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

ESS_PROXY_BASE = 50 calibrated так чтобы schedule аппроксимировал target curve из MATH_REFERENCE Section 4 (T=12w → w ≈ 0.55, T=26w → w ≈ 0.30, T=52w → w ≈ 0.19).

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
t=156:  w_proxy = 50 / (50 + 624) = 0.074
t=190:  w_proxy = 50 / (50 + 760) = 0.062  # near release threshold
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
PROXY_RELEASE_THRESHOLD = 0.05
```

Когда `w_proxy < 0.05` → proxy фактически "released" из модели:
- UI shows badge "Proxy independent" (recipient полностью самостоятельный)
- Methodology Certificate отмечает "Phase: standalone (proxy released)"
- Re-fit can drop proxy priors completely (use weakly informative defaults)

**Cross-app handoff trigger:** при release threshold + accumulated 52+ weeks data → suggest user transition к Aurora Optimize standalone.

---

## 2. Partial Pooling vs BMA - Architecture Choice

### 2.1 Partial Pooling (Primary, Default)

**Mechanism:** single Bayesian model, prior strength controlled by `w_proxy`.

```python
# engines/launch_posterior_update.py

def construct_partial_pooled_priors(
    transferred_priors: RecipientPriors,
    w_proxy: float,
) -> RecipientPriors:
    """Adjust prior strength based on proxy weight.
    
    w_proxy=1.0: priors fully informative (как initial transfer)
    w_proxy=0.5: priors halved strength (std × 2)
    w_proxy=0.05: priors weakly informative (std × 20, near uninformative)
    """
    strength_factor = 1.0 / max(w_proxy, 0.01)  # std multiplier
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
    """Bayesian Model Averaging."""
    return ForecastHorizon(
        horizon_weeks=proxy_priors_forecast.horizon_weeks,
        mean=[
            w_proxy * pm + (1 - w_proxy) * rm
            for pm, rm in zip(proxy_priors_forecast.mean, recipient_only_forecast.mean)
        ],
        # Combined CI: variance = w² × var_proxy + (1-w)² × var_recipient + 2×w×(1-w)×cov
        # cov assumed 0 (independent models)
        ci_95_lower=[
            w_proxy * p_lo + (1 - w_proxy) * r_lo
            for p_lo, r_lo in zip(proxy_priors_forecast.ci_95_lower, recipient_only_forecast.ci_95_lower)
        ],
        # ... etc для всех CI levels
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
def compute_empirical_coverage(
    actual_values: np.ndarray,        # observed recipient sales per week
    proxy_priors_ci_lower: np.ndarray,  # 95% CI lower from proxy-priors model
    proxy_priors_ci_upper: np.ndarray,
) -> float:
    """Returns % of weeks where actual ∈ [CI_lower, CI_upper]."""
    in_ci = (actual_values >= proxy_priors_ci_lower) & (actual_values <= proxy_priors_ci_upper)
    return in_ci.mean()
```

Expected: coverage ≈ 0.95 for 95% CI. Lower = drift detected.

### 4.2 Adaptive Adjustment Rules

```python
def adjust_recipient_obs_value_for_drift(
    base_obs_value: float,
    coverage: float,
) -> float:
    """Accelerate weight reduction если recipient diverges от proxy expectations."""
    if coverage >= 0.90:
        return base_obs_value          # normal
    elif coverage >= 0.80:
        return base_obs_value * 1.5    # mild drift
    elif coverage >= 0.60:
        return base_obs_value * 3.0    # moderate drift - aggressive reduction
    else:
        return None  # severe - switch to BMA mode (Section 4.4)
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
    
    # Triggering data
    triggering_data_hash: str  # SHA-256 of incremental recipient data
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

Each event captures full state нужный для reproducibility:
- New data hash → can verify input
- Weights + diagnostics → can verify output
- Model artifacts saved alongside (models/recipient_model_v2.pickle, _v3, ...)

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

При multi-proxy (S007), each proxy имеет own posterior update schedule:

```python
def multi_proxy_posterior_update(
    project: AuroraBundle,
    new_data: RecipientData,
) -> RefitResult:
    """Posterior update для multi-proxy hierarchical model."""
    # Each proxy weight reduces independently
    # Pooling weights между proxies (S007 user-set) preserved
    # Hierarchical model re-fit с reduced individual proxy weights
    
    proxies = project.get_proxies()
    new_proxy_weights = []
    for p in proxies:
        ess_p = ESS_PROXY_BASE * SIMILARITY_TO_ESS_FACTOR[p.verdict]
        ess_recipient = compute_ess_recipient(new_data, p.category)
        w_p = ess_p / (ess_p + ess_recipient)
        w_p = cap_proxy_weight_for_short_data(w_p, new_data.weeks_count)
        new_proxy_weights.append(w_p)
    
    # Re-fit hierarchical model с new proxy weights
    new_model = train_multi_proxy_hierarchical_with_weights(
        proxies, new_data, proxy_weights=new_proxy_weights,
        pooling_weights=project.get_pooling_weights(),
    )
    
    return RefitResult(...)
```

Multi-proxy adds 5% inflation penalty per extra proxy (per SIMILARITY_FRAMEWORK Section 6).

### 9.2 Posterior Update без media data

If new data is sales-only (DSM but no Mediascope), posterior update applies к baseline + seasonality only. Media betas + adstock + hill remain at previous estimates. Warning surfaced.

### 9.3 Data Quality Issue в New Recipient Data

Validators (DATA_REQUIREMENTS Section 4) check new data перед refit:
- Negative values → block
- Extreme outliers (>5σ from rolling mean) → warn user, allow override
- Mixed currencies → block

If issues - refit blocked, user fixes data first.

### 9.4 Aurora Optimize Handoff (Phase D Trigger)

При w_proxy < 0.05 + 52+ weeks data:
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
