# Aurora Launch - Math Reference

**Status:** v1.0 (2026-05-04)
**Authority:** canonical formulas + derivations + academic references для всех math operations Aurora Launch.

## Контекст

Этот документ - centralized math foundation. Каждое utterance "формула X" в коде, в reports, в conversation с клиентами должна вернуться сюда. Premium product требует transparent methodology - это документация которую можно показать (CFO / regulator / academic peer).

---

## 1. Adstock (Carryover Effect)

**Definition:** advertising adstock - модель carryover (накопления) рекламного эффекта во времени. Реклама на неделе t влияет на отклик на неделях t, t+1, t+2, ...

**Geometric (Koyck) adstock formula:**
```
A_t = X_t + λ × A_{t-1}
```
где:
- `X_t` - GRP / impressions / spend на period t
- `A_t` - adstocked value на period t
- `λ` (lambda) - decay rate, 0 ≤ λ < 1
- λ ≈ 0.5 для TV (50% retention week-over-week)
- λ ≈ 0.2 для digital (быстрее затухает)

**Aurora Launch использует Robyn-style normalization:**
```
A_t / A_mean
```
для scale-invariance (инвариантность к абсолютному уровню spend). См. Phase 2 Aurora Econometrica - hill_normalization_root_fix.

**Per-channel decay в transfer scenario:**
- Из proxy переносим `λ_channel` per channel с uncertainty bound
- Recipient может refine при наличии данных (posterior update)
- Категорийный prior (long-cycle категории - higher λ) применяется как regularization

**References:**
- Koyck (1954). "Distributed Lags and Investment Analysis"
- Tellis (2006). "Modeling Marketing Mix"
- Robyn (Meta) - https://facebookexperimental.github.io/Robyn/

---

## 2. Hill Saturation

**Definition:** функция насыщения - reflects diminishing returns at high spend levels. После определённого порога каждый дополнительный рубль приносит меньше отклика.

**Hill function (Robyn-style 4-parameter):**
```
H(x) = α × x^γ / (k^γ + x^γ)
```
где:
- `x` - normalized spend (spend/mean)
- `α` - max effect (asymptote)
- `γ` (gamma) - shape (S-curve steepness)
- `k` - half-saturation point (где effect достигает α/2)

**Aurora simplification (3-parameter, beta absorbing α):**
```
H(x) = β × x^γ / (k^γ + x^γ)
```

**Per-channel параметры в transfer:**
- `γ` (shape) переносится из proxy с uncertainty
- `k` (half-saturation) - проксимальная категорийная характеристика, переносится с inflation
- `β` (magnitude) - **recipient-specific, не переносится** - calibrated через anchors

**References:**
- Hill (1910). "Possible effects of the aggregation of the molecules"
- Aurora math audit Phase 2 (hill_normalization_root_fix) - см. memory
- Robyn paper: https://github.com/facebookexperimental/Robyn

---

## 3. Hierarchical Bayesian Transfer (single & multi-proxy)

### 3.1 Single-proxy Transfer

**Setup:** один proxy brand с trained model. Recipient brand с anchor data (no media-sales history).

**Step 1:** Train proxy MMM standalone (Bayesian, NumPyro JAX backend):
```
Y_proxy_t ~ Normal(μ_proxy_t, σ_proxy)
μ_proxy_t = baseline_proxy + Σ_c β_c × Hill(Adstock(X_c,t / X_c_mean))
```

**Step 2:** Extract structural priors:
```
priors = {
    "adstock_decay": {channel: (mean, std) per channel},
    "hill_shape_gamma": {channel: (mean, std)},
    "hill_half_sat_k": {channel: (mean, std)},
    "category_seasonality": (mean, std) per period,
    "long_term_trend": (slope_mean, slope_std)
}
```

**Step 3:** Recipient model with proxy priors + anchor calibration:
```
Y_recipient_t ~ Normal(μ_recipient_t, σ_recipient)
μ_recipient_t = baseline_recipient + Σ_c β_c × Hill(Adstock(X_c,t / X_c_mean))

baseline_recipient = anchor.market_size × anchor.planned_share × anchor.distribution_t × anchor.pricing_factor
β_c ~ Normal(β_recipient_c_prior, σ_β)

# Adstock and Hill shapes use proxy priors:
adstock_decay_c ~ Normal(proxy.adstock_decay[c].mean, proxy.adstock_decay[c].std × inflation_factor)
hill_shape_c ~ Normal(proxy.hill_shape[c].mean, proxy.hill_shape[c].std × inflation_factor)
```

`inflation_factor` зависит от similarity verdict:
- High (≥0.85): inflation = 1.2
- Medium (0.65-0.85): inflation = 1.5
- Low (0.50-0.65): inflation = 2.0

### 3.2 Multi-proxy Hierarchical (N≥2 proxies)

**Setup:** 2-3 proxies для volatile categories. Partial pooling через group-level hyperpriors.

**Hierarchical structure:**
```
# Group level (shared across proxies)
μ_λ ~ Normal(category_prior_mean, 0.5)
σ_λ ~ HalfNormal(0.3)

# Per-proxy level
λ_proxy_p ~ Normal(μ_λ, σ_λ) for p in proxies
λ_recipient ~ Normal(μ_λ, σ_λ × shrinkage_factor)

# Likelihood per proxy
Y_proxy_p,t ~ Normal(μ_proxy_p,t, σ_proxy_p)
```

`shrinkage_factor` controls how much recipient pulls toward group mean vs individual proxy.

### 3.3 Avoiding Mathematical Degeneracy

**Important:** N=1 hierarchical degenerates - hyperpriors lose identifiability. Aurora Launch uses **two separate engines**:
- `single_proxy_transfer.py` - direct prior transfer (no hierarchical layer)
- `multi_proxy_hierarchical.py` - true hierarchical для N≥2

**References:**
- Gelman et al. (2013). "Bayesian Data Analysis", Ch. 5 (Hierarchical Models)
- Carpenter et al. (2017). "Stan: A Probabilistic Programming Language"
- Aurora Trust 3 implementation - см. memory `project_econometrica_trust3_brand_perf_split.md`

---

## 4. Posterior Update via Partial Pooling (Sprint B5)

**Goal:** по мере накопления recipient data, переход от proxy-driven к recipient-driven model.

**ESS-based weighting** (Effective Sample Size):
```
ESS_proxy = some constant (say 1000 - virtual sample size of proxy priors)
ESS_recipient_t = num_observations_t × некоторый коэффициент эффективности

w_proxy_t = ESS_proxy / (ESS_proxy + ESS_recipient_t)
w_recipient_t = 1 - w_proxy_t
```

**Schedule formal calibration:** SUPERSEDED by `POSTERIOR_UPDATE_DESIGN.md` Section 1 + ADR-004 (closed S005b 2026-05-04). ESS-based hyperbolic decay formula:

```
w_proxy(t) = ESS_proxy_adj / (ESS_proxy_adj + t × recipient_obs_value)
ESS_proxy_adj = 50 × similarity_factor (1.0 / 0.7 / 0.5 для High / Medium / Low)
recipient_obs_value: categorical (FMCG impulse 4.0, OTC 2.5, Telecom 2.0, B2B 1.5, default 3.5)
```

Example schedule (FMCG High similarity):
- T=0: w_proxy = 1.0
- T=12 weeks: w_proxy ≈ 0.51
- T=26 weeks: w_proxy ≈ 0.32
- T=52 weeks: w_proxy ≈ 0.19
- T=104 weeks: w_proxy ≈ 0.11
- Proxy released at threshold 0.10 (~113 weeks)

Preliminary schedule в этом документе (T=12w ≈ 0.55, T=24w ≈ 0.30, T=52w ≈ 0.10) был illustrative ad-hoc - formal ESS-based schedule в POSTERIOR_UPDATE_DESIGN now authoritative.

**Bayesian Model Averaging (BMA) - alternative:**
```
P(Y* | data) = w_proxy × P(Y* | proxy_model) + w_recipient × P(Y* | recipient_model)
weights computed from posterior log-likelihood
```

**Identifiability при partial pooling:**
- При short recipient data (< 4 weeks) - модель может застрять в proxy local minimum
- Mitigation: minimum data threshold для switching weight schedule
- Diagnostic: posterior predictive checks - if recipient data not well explained by proxy, accelerate weight reduction

**References:**
- Konstantinopoulos & Massaro (2014). "Effective Sample Size in Bayesian Hierarchical Models"
- Hoeting et al. (1999). "Bayesian Model Averaging"

---

## 5. Conformal Prediction под Distribution Shift

**Standard Conformal Prediction (Vovk 2005):** distribution-free CI с finite-sample coverage гарантия. Требует **exchangeability** training data.

**Transfer scenario violates exchangeability** - proxy distribution ≠ recipient distribution.

**Aurora Launch adaptation:**

### 5.1 Pre-launch (zero recipient data)
```
CI_recipient_t = CI_proxy_t × inflation_factor(similarity)
inflation = {
    high: 1.2,
    medium: 1.5,
    low: 2.0
}
```

### 5.2 Post-launch (some recipient data)

**With enough recipient calibration set (>= 12 weeks):**
- Standard split conformal на recipient data
- Proxy в priors only (no longer affects CI directly)

**With short recipient data (4-12 weeks):**
- Hybrid: weighted combination
- weight = clip(weeks/12, 0, 1)

### 5.3 Adaptive Conformal Inference

**Adapted from Tibshirani et al. (2019):**

Importance weighting using density ratio:
```
weight_i = density_recipient(x_i) / density_proxy(x_i)
quantile_alpha = weighted_quantile(scores, weights)
```

**References:**
- Vovk, Gammerman, Shafer (2005). "Algorithmic Learning in a Random World" (Conformal Prediction foundational text)
- Tibshirani et al. (2019). "Conformal Prediction Under Covariate Shift" (NeurIPS)
- Angelopoulos & Bates (2023). "A Gentle Introduction to Conformal Prediction" - https://arxiv.org/abs/2107.07511

---

## 6. Similarity Score (Sprint B2)

**Aggregate similarity:**
```
S_aggregate = Σ_d w_d × s_d
where:
- d ∈ {category, pricing_tier, brand_size, distribution, media_maturity, lifecycle}
- s_d ∈ [0, 1] - dimension similarity
- Σ w_d = 1 (weights summed to 1)
```

**Default weights (calibration в S003):**
- category_subcategory: 0.30
- pricing_tier: 0.20
- brand_size: 0.15
- distribution: 0.10
- media_maturity: 0.15
- lifecycle_stage: 0.10

**Verdict thresholds:**
- High: S_aggregate ≥ 0.85
- Medium: 0.65 ≤ S_aggregate < 0.85
- Low: 0.50 ≤ S_aggregate < 0.65
- Insufficient: S_aggregate < 0.50 (block forecast generation)

**Calibration approach (S003):**
- Synthetic transfers с known truth
- Reverse: estimate optimal weights чтобы minimize transfer error на validation set
- Iterative refinement через pilot data (Phase B6+)

---

## 7. Uncertainty Decomposition

Forecast CI имеет 4 источника uncertainty:

1. **Proxy uncertainty** - inherent uncertainty в proxy model (posterior variance)
2. **Transfer uncertainty** - structural uncertainty при переносе priors (similarity-dependent inflation)
3. **Anchor uncertainty** - uncertainty в recipient anchor data (если anchors completeness < 100%)
4. **Sampling uncertainty** - Monte Carlo variance из MCMC sampling

**Total CI variance (independent sources approximation):**
```
σ²_total = σ²_proxy + σ²_transfer + σ²_anchor + σ²_sampling
```

**Reporting:** в Methodology Certificate PDF + Aurora Launch UI:
```
Forecast 12 weeks CI = ±X% (95% intervals)
- Proxy uncertainty: 30% of variance
- Transfer uncertainty: 40% (similarity = Medium)
- Anchor uncertainty: 15%
- Sampling uncertainty: 15%
```

Это helps клиенту understand откуда uncertainty приходит и как её уменьшить (e.g., "найти лучший proxy" уменьшает transfer; "fill more anchors" уменьшает anchor).

---

## 8. Magnitude Calibration from Recipient Anchors

**Baseline forecasting:**
```
baseline_recipient_t = market_size × planned_share_t × distribution_t × pricing_factor
where:
- planned_share_t - linear interpolation от 0 до planned_share_pct по distribution_ramp_weeks
- distribution_t - linear ramp 0 до distribution_target_pct по distribution_ramp_weeks
- pricing_factor = 1.0 если pricing_index_vs_proxy ≈ 1.0
              = 0.85 (typical) если pricing_index_vs_proxy ≈ 1.5 (premium - lower volume)
              = 1.20 (typical) если pricing_index_vs_proxy ≈ 0.7 (cheap - higher volume)
```

**β coefficient prior:**
```
β_c_prior = (proxy_β_c / proxy_baseline) × recipient_baseline × similarity_inflation
σ_β_prior = β_c_prior × σ_inflation_factor
```

This allows recipient β to scale with recipient size while preserving proxy's relative channel effectiveness.

---

## 9. Diagnostic Metrics

### 9.1 Convergence
- **Gelman-Rubin (R̂):** target < 1.05 для production-ready, < 1.10 для preview
- **Effective Sample Size (ESS):** per parameter, target > 400 for posterior summary, > 4000 for posterior predictive
- **Divergence transitions:** count, target = 0 (any divergence = sampler unhappy)

### 9.2 Goodness-of-fit
- **R² posterior:** training fit, target > 0.7
- **MAPE posterior:** target < 15% for FMCG, < 25% для launches с high uncertainty
- **Posterior predictive check:** observed in [5%, 95%] CI for >= 90% periods

### 9.3 Reliability
- **Simulation-Based Calibration (SBC):** rank statistic uniform → well-calibrated posterior
- **Conformal coverage:** empirical coverage matches stated CI level (e.g., 95% CI covers 95% truth)

**References:**
- Gelman et al. (1992). "Inference from Iterative Simulation Using Multiple Sequences"
- Vehtari et al. (2021). "Rank-normalization, folding, and localization: An improved R̂"
- Talts et al. (2018). "Validating Bayesian Inference Algorithms with Simulation-Based Calibration"

---

## 10. Notation Summary

| Symbol | Meaning | Range |
|---|---|---|
| `Y_t` | Observed dependent variable (sales) at period t | ≥ 0 |
| `X_c,t` | Marketing input for channel c at period t | ≥ 0 |
| `A_c,t` | Adstocked X | ≥ 0 |
| `H(·)` | Hill saturation function | [0, β_c] |
| `λ_c` | Adstock decay rate, channel c | [0, 1) |
| `α, γ, k` | Hill parameters | various |
| `β_c` | Channel coefficient | ≥ 0 |
| `μ_t` | Mean of Y at t | various |
| `σ` | Residual std | > 0 |
| `S` | Aggregate similarity score | [0, 1] |
| `w_proxy_t` | Proxy weight в posterior update | [0, 1] |
| `R̂` | Gelman-Rubin convergence statistic | ≥ 1, target < 1.05 |
| `ESS` | Effective Sample Size | integer |

---

## Связанные документы

- `../00_Overview/PRINCIPLES.md` - P3 (что переносится / не переносится)
- `REUSE_FROM_ECONOMETRICA.md` - где shared engines живут
- `decisions/` - ADRs для math decisions
- Memory: `project_econometrica_math_audit.md` - prior audit work
- Memory: `project_econometrica_hill_normalization_root_fix.md` - Robyn-style normalization
