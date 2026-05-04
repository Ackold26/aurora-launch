# ADR-004: ESS-Based Partial Pooling Weight Schedule + BMA Fallback

**Status:** Accepted
**Date:** 2026-05-04
**Authors:** Маша (decision design) + Антон (authority delegated, autonomous mandate)
**Sprint context:** Sprint B5 (Posterior Update Workflow)
**Related:** POSTERIOR_UPDATE_DESIGN.md (implements decision), MATH_REFERENCE Section 4, ADR-003 (pre-train + transfer paradigm)

## Context

После initial transfer (Sprint B3, ADAPTATION_RULES + ADR-003), recipient model fitted с structural priors из proxy + magnitude calibration из anchors. По мере накопления recipient data (post-launch), proxy influence должен ослабевать - recipient становится самостоятельной моделью. Это **posterior update workflow**.

P4 (мягкий partial pooling) declares continuous weighting, не on/off switch. Этот ADR locks **формулу weight schedule + workflow** для Sprint B5.

**Forces в conflict:**

1. **Theoretical foundation** - ESS-based partial pooling grounded в Bayesian update math (Konstantinopoulos 2014). Linear/exponential ad-hoc.

2. **Calibration practicality** - schedule должен matchать realistic recipient data accumulation rates (FMCG impulse vs B2B slow signal). Categorical observation values needed.

3. **Drift handling** - recipient может deviate strongly от proxy expectations. Schedule must adapt (faster reduction at drift).

4. **Identifiability при low data** - recipient at <12 weeks risk being stuck в proxy local minimum. Need cap to prevent over-fast proxy reduction.

5. **Architecture choice partial pooling vs BMA** - partial pooling clean Bayesian semantics + reuse modeler.py. BMA provides cleaner separation при severe drift но adds 2× training time.

6. **Cross-app handoff** - proxy "released" threshold needed для Aurora Optimize transition trigger.

## Decision

### A. Weight Schedule: ESS-based partial pooling

**Formula (locked):**

```
w_proxy(t) = ESS_proxy_adj / (ESS_proxy_adj + ESS_recipient(t))
ESS_recipient(t) = t × recipient_obs_value
ESS_proxy_adj = ESS_PROXY_BASE × similarity_factor
```

**Calibrated constants:**
- `ESS_PROXY_BASE = 50` (virtual sample size of proxy priors)
- `similarity_factor`: High 1.0, Medium 0.7, Low 0.5
- `recipient_obs_value`: categorical (FMCG impulse 4.0, FMCG staples 3.0-3.5, OTC 2.5, Telecom/Banking 2.0, B2B 1.5, Rx 1.5)

**Proxy release threshold:** 0.10 (calibrated к realistic Aurora Launch → Optimize transition window ~2.2 years for FMCG High similarity, vs 4.6 years при threshold 0.05 - too long для practical handoff).

### B. Architecture: Partial Pooling Primary

**Default:** modify prior strength based on `w_proxy`. Single Bayesian model re-fit с adjusted priors. Reuses Aurora Econometrica `train_mmm_with_priors()` (ADR-003 paradigm).

**Fallback:** BMA (two independent models averaged) **only при severe drift** (coverage < 0.60 в 95% CI of proxy-priors forecast).

### C. Adaptive Drift Adjustment

```
coverage 0.90-0.95: normal (recipient_obs_value × 1.0)
coverage 0.80-0.90: mild drift (× 1.5)
coverage 0.60-0.80: moderate drift (× 3.0)
coverage < 0.60:    severe drift → switch to BMA mode
```

### D. Identifiability Caps

```
weeks < 12:  w_proxy >= 0.40 (max shrinkage cap)
weeks < 24:  w_proxy >= 0.20
weeks >= 24: full schedule applied
```

Min refit threshold: 4 weeks recipient data accumulated.

### E. Phase D Revisit Triggers

Reconsider this ADR if:
1. Pilot data shows ESS schedule miscalibrated (e.g., empirical proxy weight @T=12w differs от target ±20%)
2. Customer demand для explicit BMA mode (regulatory audit requires "two independent forecasts averaged")
3. NumPyro hierarchical Bayesian sampler becomes 2-3× faster (joint Bayesian becomes practical, supersedes ADR-003 + this ADR jointly)

## Consequences

### Positive

- **Theoretically grounded** - ESS-based weighting reflects Bayesian update math (proxy "evidence" vs recipient "evidence" weighted naturally).
- **Calibrated к realistic schedules** - matches MATH_REFERENCE Section 4 preliminary schedule (T=12w → ~0.55, T=26w → ~0.30, T=52w → ~0.20). Worked examples в POSTERIOR_UPDATE_DESIGN Section 1.3.
- **Categorical sensitivity** - obs_value varies by category, captures "fast vs slow signal" categories correctly.
- **Similarity-aware** - proxy informativeness scaled by verdict. Higher S = larger virtual sample.
- **Adaptive to drift** - automatic acceleration при divergent recipient (mild/moderate/severe tiers).
- **Identifiability protected** - max shrinkage caps prevent recipient being "stuck" в proxy local minimum при low data.
- **BMA fallback only when justified** - не дефолт (avoiding 2× training overhead), но available при severe drift gives robust handling.
- **100% reuse Aurora Econometrica modeler.py** (P9) - partial pooling = adjust prior strength, calls existing engine.
- **Audit trail full** - posterior_update_log.json captures every refit с diagnostics, drift score, weight schedule state. Reproducibility preserved.
- **Cross-app handoff trigger clean** - proxy_release_threshold = 0.10 + 52+ weeks → suggest Optimize transition.

### Negative

- **ESS_proxy_base = 50 calibrated heuristically** - based на target schedule curve, не derived from rigorous proxy data analysis. Phase B initial pilot data может show miscalibration. Mitigation: Sprint B5 sensitivity tests + Sprint B6 pilot validation, refine in Phase C+ ADR-005.
- **Categorical obs_value taxonomy maintenance** - new categories require addition к RECIPIENT_OBS_VALUE map. Acceptable - taxonomy quarterly review per category_taxonomy.yaml maintenance.
- **Drift coverage threshold 0.60 binary** - hard cutoff "severe" might cause oscillation around threshold. Mitigation: hysteresis (требуется coverage <0.60 за 2 consecutive refits для switching к BMA, не single dip).
- **BMA fallback implementation cost** - Sprint B5 must implement two-model training pipeline. Acceptable - fallback path simpler than primary partial pooling integration.

### Neutral

- **Schedule визуально smooth** - ESS-based gives gradually decaying curve, не jerky linear/exponential schedule. UI design (DriftCoverageGauge + WeightScheduleChart) support visualization.
- **Multi-proxy edge case** - hierarchical model с N proxies, each имеет own ESS reduction. Handled через `engines/multi_proxy_posterior_update.py`.

## Alternatives Considered

### Option A: Linear Decay Schedule (rejected)

`w_proxy(t) = max(0, 1 - t/T_release)` где T_release = 52 weeks

**Pros:** trivial to compute, intuitive.
**Cons:** не respects similarity (high-S proxy decays same rate as low-S - wrong). Не adaptive к drift. Not theoretically grounded.

**Why rejected:** ad-hoc heuristic without Bayesian foundation.

### Option B: Exponential Decay Schedule (rejected)

`w_proxy(t) = exp(-t/τ)` где τ = 26 weeks

**Pros:** smooth.
**Cons:** same as linear - not similarity-aware, not drift-adaptive, no theoretical basis.

**Why rejected:** same as Option A.

### Option C: BMA Primary (rejected)

Default workflow: train recipient-only model + train proxy-priors model + BMA combine.

**Pros:** clean separation. Recipient data не "corrupts" proxy при posterior. Two models always available.
**Cons:** 2× training cost always. Recipient-only model at low data overfits. Combination weights ambiguous (log-likelihood, validation, prior?).

**Why rejected:** Phase B compute budget tight (audit performance budget 30s single proxy). 2× cost не justified для default path. BMA reasonably reserved для severe drift fallback.

### Option D: Adaptive ESS Sample Size (deferred Phase D)

`ESS_proxy_adj` not constant 50, instead computed dynamically from proxy posterior CV:

```
ESS_proxy_adj = κ × T_proxy / (1 + ρ²)
where ρ² = posterior CV of key params
```

**Pros:** more rigorously derived от proxy data quality.
**Cons:** complex calibration κ, not implemented in Phase B.

**Why deferred:** Phase D consideration if pilot data shows ESS_PROXY_BASE = 50 не fits universally. Until then, fixed = 50 simpler + works.

### Option E: Posterior Distillation Tracking (deferred Phase D)

Use full posterior distribution propagation (not just mean+std summary) для prior update.

**Pros:** retains full posterior shape, не loses information.
**Cons:** computationally heavy, requires saving full proxy posterior samples. ADR-002 storage layer doesn't currently optimize для это (pickle BLOBs work но size grows).

**Why deferred:** Phase D computational efficiency improvements (NumPyro JAX backend) могут позволить full posterior tracking. Phase B uses summary (mean+std).

## Implementation Notes

### Files (Sprint B5)

**New:**
- `engines/launch_posterior_update.py` - main workflow + helpers
- `engines/drift_detector.py` - empirical coverage + classify_drift
- `engines/multi_proxy_posterior_update.py` - multi-proxy variant
- `engines/bma_combiner.py` - BMA fallback combine logic

**Existing extended:**
- `aurora_platform_core.modeler.train_mmm_with_priors()` - already supports prior strength via std parameter, no breaking changes.

**Tests:**
- `tests/unit/test_posterior_update_weights.py` - ESS formula calibration
- `tests/integration/test_posterior_update.py` - convergence + drift + identifiability
- Property-based tests (см. POSTERIOR_UPDATE_DESIGN Section 8.2)

**Documentation:**
- `POSTERIOR_UPDATE_DESIGN.md` - implementation reference
- `MATH_REFERENCE.md` Section 4 - canonical formula

### Calibration Tracking

Sprint B6 pilot live-test tracks:
- w_proxy schedule actual vs predicted at 4w, 12w, 26w, 52w
- Empirical coverage actual vs predicted CI
- MAPE convergence trajectory

If deviates significantly от model expectations - trigger Phase C+ recalibration ADR.

### Constants Maintenance

```python
# engines/posterior_update_constants.py

ESS_PROXY_BASE = 50  # ADR-004 calibrated
PROXY_RELEASE_THRESHOLD = 0.10  # audit-revised from 0.05 (calibrated к ~2.2y FMCG handoff)
MIN_RECIPIENT_WEEKS_FOR_REFIT = 4

SIMILARITY_TO_ESS_FACTOR = {
    "High": 1.0,
    "Medium": 0.7,
    "Low": 0.5,
}

# Categorical obs_value maintained в ADR-004 + reviewed quarterly
# Updates require new ADR (ADR-XXX-recalibrate-obs-values) referencing this one
```

## References

- `../POSTERIOR_UPDATE_DESIGN.md` - implementation following this decision
- `../MATH_REFERENCE.md` Section 4 - canonical formulas
- `../decisions/ADR-002-storage-layer.md` - posterior_update_log.json storage
- `../decisions/ADR-003-pretrain-vs-joint-training.md` - paradigm для re-fit с adjusted priors
- `../ADAPTATION_RULES.md` Section 5 - initial transfer (source priors)
- `../../00_Overview/PRINCIPLES.md` P4 (мягкий partial pooling)
- `../../02_Data_Spec/SIMILARITY_FRAMEWORK.md` - similarity verdict used для similarity_factor
- `../../05_Sessions/SESSION_NEXT_QUESTIONS.md` S005b closed reference
- Konstantinopoulos & Massaro (2014) "Effective Sample Size in Bayesian Hierarchical Models"
- Hoeting et al. (1999) "Bayesian Model Averaging" (BMA fallback foundation)
- Gelman et al. (2013) "Bayesian Data Analysis" Ch. 5 (hierarchical priors)
- Vehtari et al. (2021) "Rank-normalization, folding, and localization: An improved R̂"
