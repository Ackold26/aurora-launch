# ADR-003: Pre-Train + Transfer vs Joint Bayesian Training

**Status:** Accepted
**Date:** 2026-05-04
**Authors:** Маша (decision design) + Антон (authority delegated, autonomous mandate)
**Sprint context:** Sprint B3 (Adaptation Layer)
**Related:** ADAPTATION_RULES.md (implements decision), MATH_REFERENCE Section 3 (transfer math), PRINCIPLES P3 + P9

## Context

Aurora Launch transfers structural priors из proxy MMM в recipient model. Два возможных workflow:

**Option A: Pre-train + Transfer (current spec в PRINCIPLES P3 + MATH_REFERENCE Section 3.1):**
- Step 1: Train proxy MMM standalone (Bayesian, NumPyro)
- Step 2: Extract structural priors from proxy posterior (adstock decay, hill shape, seasonality, trend)
- Step 3: Train recipient model с этими priors + anchor magnitudes

**Option B: Joint Hierarchical Bayesian:**
- Single Bayesian model fitted simultaneously к proxy + recipient data
- Hierarchical structure forces partial pooling
- Recipient parameters drawn from hyperpriors shared с proxy

Этот ADR locks **Option A** для Phase B. Option B = Phase D consideration.

**Forces в conflict:**

1. **Engineering velocity** - Phase B has 7-8 нед budget. Pre-train reuses Aurora Econometrica engines (P9: 80%+ reuse). Joint requires новый math layer.

2. **Aurora Econometrica integration** - existing modeler.py engineered для standalone Bayesian MMM. Joint = significant refactor или fork.

3. **Pre-launch use case (zero recipient data)** - в этом сценарии joint Bayesian degenerates: единственный likelihood term = proxy data. Posterior recipient-side = priors only. Mathematically equivalent к pre-train + transfer.

4. **Posterior update workflow (Sprint B5)** - re-fit recipient model с new data, reduce proxy weight по ESS schedule. Это hands-on partial pooling, не requires joint fit. Cleaner semantics: "проходящий вес proxy decreases".

5. **Modular debugging** - pre-train allows inspect proxy fit independently. Joint fit harder to introspect when something goes wrong.

6. **Information flow correctness** - pre-train posterior → transferred priors → recipient posterior. No retroactive influence (recipient data не affects proxy posterior). Joint allows information flow recipient → proxy, который для Aurora не desirable (proxy's structural patterns должны быть anchored before recipient observed).

7. **Computational cost** - joint requires re-fitting full hierarchical model каждый раз recipient data updates. Pre-train caches proxy fit, recipient training cheaper.

## Decision

**Pre-train + transfer workflow для Phase B.** Joint Bayesian = Phase D consideration if customer demand emerges.

### Workflow (locked):

1. **Train proxy MMM standalone** через `aurora_platform_core.modeler.train_mmm()` (existing Aurora Econometrica engine).
2. **Extract structural priors** через `engines/launch_adapt.py:extract_proxy_priors()` - posterior means + std for adstock/hill/seasonality/trend.
3. **Train recipient model** через `aurora_platform_core.modeler.train_mmm_with_priors()` - Bayesian MMM с transferred priors + anchor magnitudes calibration.

### Multi-proxy edge case:

При multi-proxy mode (S007), используется true hierarchical Bayesian (`engines/multi_proxy_hierarchical.py`) - но это hierarchical в смысле hyperpriors over multiple proxies, не joint в смысле "fit proxy + recipient simultaneously". Recipient parameters drawn из hyperpriors after proxies fitted. Still pre-train + transfer paradigm.

### Phase D revisit triggers:

Reconsider Option B if:
- Pilot data shows pre-train inadequate (e.g., overconfident CI, miscalibrated posterior coverage)
- Customer demand for "tightly coupled" launch + reference brand modelling
- Computational tools mature enough (NumPyro joint hierarchical training time becomes practical)

ADR superseded только через explicit ADR-XXX referencing this one.

## Consequences

### Positive

- **80%+ reuse Econometrica engines** preserved (P9). Sprint B3 implements adaptation layer без re-engineering math foundations.
- **Pre-launch case clean** - zero recipient data → priors-only forecast. Pre-train degenerates correctly to "use proxy as best estimate". Joint formulation в этом случае is just proxy fit с extra wasted compute.
- **Modular debugging** - inspect proxy fit standalone, validate priors extraction, validate recipient fit separately.
- **Clear information flow** - proxy posterior → recipient prior. No retroactive recipient → proxy update.
- **Faster iteration** - cached proxy fit reused across multiple recipient launch attempts (e.g., scenario analysis с different anchors but same proxy).
- **Posterior update Sprint B5 simpler** - re-fit recipient с reduced proxy weight = standard Bayesian с different prior strength, не joint hierarchical re-fit.
- **Computational cost predictable** - proxy training ~30s (Aurora Econometrica baseline), recipient training ~30-60s. Total ~60-90s. Joint hierarchical Bayesian = potentially 5-10× slower.

### Negative

- **Two-stage uncertainty propagation** - pre-train uses point estimate of proxy posterior std для prior (mean + std), не full distribution. Possible underestimation of uncertainty, может cause overconfident posterior. Mitigated через:
  - Conformal Prediction adapted (MATH_REFERENCE Section 5) - distribution-free CI alongside Bayesian
  - similarity-based inflation factor (1.2-2.0×) inflates std для transfer uncertainty
  - σ²_anchor + σ²_transfer separately tracked (MATH_REFERENCE Section 7)
- **No retroactive proxy update** - if recipient data shows proxy was misleading, can't propagate back. Acceptable trade-off: proxy is reference, не learnable model. If proxy needs revision - re-train proxy standalone, не through recipient.
- **Reproducibility:** results depend on proxy posterior summarization choice (mean + std vs full distribution). Documented в transfer_provenance.json so reproducible.

### Neutral

- **Phase D reconsideration possible** - если pilot data validates Option B benefits, future ADR может supersede. ADR не immutable architecturally - principle yes, implementation can evolve.
- **Multi-proxy hierarchical** still uses pre-train paradigm для individual proxies, hierarchical layer added on top. Не changes этот ADR's scope.

## Alternatives Considered

### Option B: Joint Hierarchical Bayesian (rejected для Phase B)

**Pros:**
- Single posterior - cleanest uncertainty propagation
- Recipient data inform proxy parameters too (regularizing if recipient unique signal)
- True hierarchical Bayesian (no two-stage hacks)

**Cons:**
- Slower (full re-fit each time recipient data changes)
- Harder to debug
- Aurora Econometrica engines не designed for это - significant refactor
- Pre-launch case degenerates (zero recipient data → joint = proxy fit anyway, wasted compute)
- Posterior update Sprint B5 не straightforward in joint formulation
- Information flow recipient → proxy не desired (proxy should be anchored reference, не learnable from single recipient launch)

**Why rejected:** all benefits theoretically apply, but practical Phase B constraints (engineering budget, reuse Econometrica) + zero recipient data zone (где joint degenerates) make Option A strongly dominant. Phase D reconsider.

### Option C: Empirical Bayes (point-estimate proxy params, no posterior std)

**Pros:**
- Simpler than full posterior summary
- Faster

**Cons:**
- Loses transfer uncertainty completely
- Overconfident recipient CI

**Why rejected:** undermines core Aurora value (transparent uncertainty). P1 requires structural uncertainty visible. Empirical Bayes silently absorbs it.

### Option D: Bootstrapped Proxy Priors (multiple proxy fits, average priors)

**Pros:**
- More robust than single proxy posterior summary
- Captures proxy fit instability

**Cons:**
- Computational cost ~5-10× single fit
- Not significantly better than well-chosen proxy posterior summary
- Multi-proxy mode (S007) already addresses proxy uncertainty по другому

**Why rejected:** marginal benefit vs cost, multi-proxy mode handles same concern more naturally.

## Implementation Notes

### Files affected (Sprint B3)

**New (per ADAPTATION_RULES Section 11):**
- `engines/launch_adapt.py` - extract_proxy_priors + apply_recipient_magnitudes
- `engines/single_proxy_transfer.py` - workflow orchestrator
- `engines/multi_proxy_hierarchical.py` (separate from pre-train debate - this is hierarchical layer over multiple proxies, still pre-train paradigm для each)

**Reused (no changes):**
- `aurora_platform_core.modeler.train_mmm()` - existing Bayesian MMM training
- `aurora_platform_core.modeler.train_mmm_with_priors()` - existing prior-aware training (extension of existing)

**Documentation (already covered):**
- `ADAPTATION_RULES.md` - implementation reference
- `MATH_REFERENCE.md` Section 3.1 - mathematical foundation

### Tests

`tests/integration/test_adaptation_sensitivity.py` (Sprint B5):
- Synthetic data tests confirm pre-train + transfer recovers known truth
- Property-based tests (monotonicity, parity)
- Pilot data validation (Sprint B6)

### Phase D revisit decision criteria

В future ADR-XXX считаем Option B if:
1. Pilot CI coverage consistently < 90% при stated 95% (suggests pre-train understates uncertainty)
2. Customer feedback explicit demand для tighter proxy-recipient coupling
3. NumPyro hierarchical Bayesian sampler shows 2-3× speed improvement (currently joint formulation impractical computational)

If revisit triggers met - new ADR-XXX written, this ADR-003 status changes к "Superseded by ADR-XXX".

## References

- `../ADAPTATION_RULES.md` - implementation following this decision
- `../MATH_REFERENCE.md` Section 3 - hierarchical Bayesian transfer math
- `../decisions/ADR-001-consulting-hours-persistence.md` - precedent для local-first storage decisions
- `../decisions/ADR-002-storage-layer.md` - where transfer_provenance stored
- `../REUSE_FROM_ECONOMETRICA.md` Section 1.1 - shared modeler.py engine
- `../../00_Overview/PRINCIPLES.md` P3 (shape transfer) + P9 (80%+ reuse)
- `../../05_Sessions/SESSION_NEXT_QUESTIONS.md` S004 closed reference
- Memory: `project_econometrica_target_architecture_v3.md` - target architecture
- Gelman et al. (2013), "Bayesian Data Analysis" Ch. 5 (Hierarchical Models foundation)
- Carpenter et al. (2017), "Stan: A Probabilistic Programming Language" (joint hierarchical example)
