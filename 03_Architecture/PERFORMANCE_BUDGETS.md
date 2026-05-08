# Aurora Launch - Performance Budgets

**Status:** v1.0 (2026-05-04)
**Authority:** Audit finding A9 (performance budget for launch_adapt.py)

## Контекст

Premium product = премиум performance. Slow product = "это какая-то самописная штука". Performance budgets устанавливают per-operation time limits + benchmarking strategy + regression gates.

---

## 1. Performance Budgets per Operation

### 1.1 Critical Path (training + forecast) - revised post-audit 2026-05-04

Budgets имеют **2 tiers** (cold first run / warm subsequent) + premium hardware bonus.

| Operation | Cold budget | Warm budget | Premium HW | Status |
|---|---|---|---|---|
| **Single-proxy transfer training** | ≤ 45s | ≤ 30s | ≤ 18s | Sprint B5 verify |
| **Multi-proxy hierarchical (N=2)** | ≤ 100s | ≤ 70s | ≤ 40s | Sprint B5 verify |
| **Multi-proxy hierarchical (N=3)** | ≤ 180s | ≤ 120s | ≤ 70s | Sprint B5 verify |
| **52-week forecast generation** | ≤ 15s | ≤ 8s | ≤ 5s | Sprint B5 verify |
| **Decomposition (52 weeks)** | ≤ 5s | ≤ 3s | ≤ 2s | Sprint B5 verify |
| **Optimization (constrained, 5 channels)** | ≤ 15s | ≤ 10s | ≤ 6s | Sprint B5 verify |
| **Posterior update (4 weeks new data)** | ≤ 40s | ≤ 25s | ≤ 15s | Sprint B5 verify |

**Hardware reference:**
- Cold/Warm: standard developer / analyst workstation (8-core CPU, 16-32GB RAM, NumPyro JAX backend)
- Premium HW: 16-core CPU, 32-64GB RAM, NVME SSD

**Reasoning revision:** Bayesian MMM с NumPyro JAX в Aurora Econometrica v1.0.16 measured ~20s standard. Transfer scenario adds proxy priors complexity (~20-30% overhead). Multi-proxy hierarchical needs 4× iterations для convergence. Original budgets были overly optimistic.

**Graceful degradation:**
- If budget exceeded by < 50% → warning ("операция заняла дольше ожидаемого")
- If exceeded > 50% → error + log + telemetry (opt-in)
- Forecast и training имеют user-visible time estimate (см. Section 4.1)

### 1.2 Data Loading

| Operation | Budget |
|---|---|
| **DSM Excel parse (24 months)** | ≤ 2s |
| **Mediascope TV parse (78 weeks)** | ≤ 2s |
| **Mediascope Digital parse (78 weeks)** | ≤ 2s |
| **AdIndex Digital Budget parse** | ≤ 1s |
| **Format auto-detection** | ≤ 200ms |
| **Validator full check** | ≤ 1s |

### 1.3 UI Responsiveness

**Updated 2026-05-09 (Block 2 pre-execution audit, decisions D2/D3):**
- Cold start tightened к ≤2s per ROADMAP success criteria (was ≤3s).
- WASM rows removed — Block 2C decided native Rust IPC, no WASM в desktop scope.
- Wizard step explicit budget (was implicit through "Cabinet navigation").

| Operation | Budget | Threshold |
|---|---|---|
| **Cold start (initial app launch)** | ≤ 2s | First Contentful Paint, splash visible immediately |
| **Wizard step navigation** | ≤ 200ms | Click → next step rendered |
| **Cabinet navigation** | ≤ 200ms | Click to render |
| **Form field validation (debounced)** | ≤ 300ms | Debounce + validate |
| **Similarity score recompute (native Rust IPC, cold)** | ≤ 100ms | First IPC call (process warmup) |
| **Similarity score recompute (native Rust IPC, warm)** | ≤ 30ms | Subsequent calls (real-time radar fill) |
| **Forecast cone render** | ≤ 500ms | After data ready, Chart.js tree-shaken |
| **Custom SVG radar render** | ≤ 100ms | 8 dimensions, 60fps на change |
| **Modal open/close** | ≤ 200ms | Spring motion + content |
| **Save project** | ≤ 500ms | Including ZIP write + atomic rename |
| **Open existing project (small, ≤10MB)** | ≤ 200ms | Per ADR-002 (manifest + lazy load) |
| **Open existing project (large, ≤200MB)** | ≤ 500ms | Per ADR-002 + Block 1C streaming reader |
| **Theme switch (light↔dark)** | ≤ 150ms | CSS custom properties only, no rerender |
| **i18n locale switch** | ≤ 300ms | Full re-render с new locale strings |

### 1.4 Reports

| Operation | Budget |
|---|---|
| **PPTX generation (8 sections)** | ≤ 8s |
| **HTML generation (interactive)** | ≤ 5s |
| **XLSX generation** | ≤ 3s |
| **Methodology Certificate PDF** | ≤ 3s |

### 1.5 Backend API

| Endpoint | Budget |
|---|---|
| `/launch/v1/proxy/validate` | ≤ 500ms |
| `/launch/v1/anchors/validate` | ≤ 200ms |
| `/launch/v1/similarity/compute` | ≤ 100ms (or WASM 50ms) |
| `/launch/v1/adapt` | ≤ 2s |
| `/launch/v1/validate_transfer` | ≤ 5s (включая prior predictive sampling) |
| `/launch/v1/train` | (см. critical path budgets, streaming response) |
| `/launch/v1/forecast` | ≤ 5s |
| `/launch/v1/decompose` | ≤ 3s |
| `/launch/v1/optimize` | ≤ 10s |
| `/launch/v1/report/*` | (см. reports budgets) |
| `/launch/v1/posterior_update` | ≤ 20s (streaming response) |

---

## 2. Optimization Strategies

### 2.1 JAX/NumPyro tier-1 backend

Reuse from Econometrica v1.0.16:
- JAX compilation для critical math operations
- NumPyro NUTS sampler (faster than PyMC default)
- vswhere.exe + vcvars64.bat для Windows JAX speedups (Econometrica session 4)

### 2.2 Native Rust IPC для UI-side computation

**Updated 2026-05-09 (Block 2 audit D3):** WASM removed from desktop scope per ROADMAP §2C. WASM verifier — отдельный проект для web, defer v0.1.1.

Real-time operations через native Tauri IPC commands (Rust process, не WASM bridge):
- `compute_similarity_dimensions(proxy_id, recipient_anchors) → SimilarityDimensionScores` — sub-30ms warm.
- `verify_bundle_signature(path) → VerificationResult` — Block 2C entry.
- `validate_anchors(anchors) → ValidationResult` — sync, fast.

Pydantic schemas reused via `tools/export_typescript.py` — generated `frontend/src/types/aurora.d.ts`. Build pipeline runs export перед каждым `tauri dev` / `tauri build`.

### 2.3 Caching

- Recent forecasts cached locally (faster re-open)
- Similarity scores memoized (no recompute если dimensions не менялись)
- API responses cached с invalidation rules
- Forecast horizons memoized (12⊂26⊂52 - reuse common path prefix)

### 2.4 Streaming responses

Long operations:
- MCMC training - SSE stream traces (audit B6)
- Forecast generation - chunk by horizon
- Posterior update - progress events

User видит "что-то происходит" вместо blocking spinner.

### 2.5 Lazy loading

- Reports generated on-demand (не auto-create при forecast)
- Methodology drill-down content loads on click
- Tour content lazy-loaded

---

## 3. Benchmarking Strategy

### 3.1 Reference Datasets - realistic sizes (corrected post-audit)

| Name | Description | Size (XLSX) |
|---|---|---|
| **fmcg_snacks_24m** | DSM 24 months × 13 cities + MS TV 78 weeks × 6 channels | ~1.0 MB |
| **otc_pharma_36m** | DSM 36 months × 8 cities + MS TV 130 weeks × 8 channels | ~1.5 MB |
| **energy_drink_30m** | DSM 30 months × 10 cities + MS TV 110 weeks × 10 channels + Digital 110 weeks × 5 platforms | ~2.0 MB |

Reasoning: DSM monthly Excel ~25KB per city per year. Mediascope TV ~3KB per channel per week. Plus headers, demo groups, metadata.

### 3.2 Benchmark suite (`tests/performance/`)

```python
import pytest
import time

@pytest.mark.performance
@pytest.mark.parametrize("dataset", REFERENCE_DATASETS)
def test_single_proxy_train_budget(dataset, benchmark_data_factory):
    proxy_data = benchmark_data_factory(dataset)
    anchors = build_default_anchors()

    start = time.perf_counter()
    model = train_single_proxy_transfer(proxy_data, anchors)
    elapsed = time.perf_counter() - start

    assert elapsed < BUDGETS["single_proxy_train"], (
        f"[{dataset}] Single-proxy train took {elapsed:.1f}s "
        f"(budget {BUDGETS['single_proxy_train']}s)"
    )

    # Log для regression tracking
    log_benchmark_result(
        operation="single_proxy_train",
        dataset=dataset,
        elapsed_s=elapsed,
        version=AURORA_LAUNCH_VERSION,
    )
```

### 3.3 CI integration

`.github/workflows/aurora_launch.yml`:
- Performance benchmarks run on every PR
- Compare to baseline (last main commit)
- Block PR if >10% regression
- Plot performance over time (visualization)

### 3.4 Telemetry в production (opt-in)

Anonymous performance metrics:
- Operation timings per machine
- Aggregate stats к Aurora cloud (opt-in)
- Identify slow operations early
- Public dashboard (показывает перформанс - честный signal)

---

## 4. User-Facing Time Estimation

### 4.1 Pre-operation estimates

Before slow operations - show estimated time:
- "Training will take ~25 seconds. You can switch tabs."
- "Posterior update with 4 weeks data: ~15 seconds."
- "Generating 52-week forecast: ~3 seconds."

Estimation logic:
- Based on dataset size + operation type
- Adjusted to historical timings (per machine)
- Conservative (over-estimate slightly, deliver under)

### 4.2 Mid-operation progress

Streaming operations:
- "Sampling chain 1 of 4 - 250 / 1000 iterations (~12s remaining)"
- "Generating forecast week 27 / 52..."
- "Validating proxy data: 3 of 5 checks complete"

### 4.3 Post-operation feedback

After completion:
- "Done in 23.4s ✓"
- "Posterior update applied. Proxy weight: 50% → 35%."
- Subtle achievement chime (mute-able)

---

## 5. Performance Anti-patterns

### 5.1 НЕ блокировать UI thread

❌ Synchronous heavy computation в frontend
✅ Web Worker / WASM / backend offload

### 5.2 НЕ pre-compute то что не нужно

❌ Generate all reports автоматически после training
✅ Generate on-demand при export click

### 5.3 НЕ load whole .aurora when only metadata нужно

❌ Full unpickle для project list view
✅ SQLite hybrid (audit B3) - read metadata only

### 5.4 НЕ retry без backoff

❌ Tight retry loop при backend error
✅ Exponential backoff + max retries

### 5.5 НЕ ignore memory budgets

Memory budgets:
- Aurora Launch baseline: ≤ 500MB RSS
- During training: ≤ 2GB RSS
- During forecast: ≤ 1GB RSS
- Не leak memory между operations

---

## 6. Performance Regression Detection

### 6.1 Automated detection (CI)

Per PR:
- Run benchmark suite
- Compare to last main baseline
- If any operation > 10% slower → CI warning
- If any operation > 25% slower → CI block (require approval)

### 6.2 Manual review process

- Weekly: review benchmark trends (Маша)
- Monthly: review aggregate telemetry (если opt-in users есть)
- Quarterly: revisit budgets (if hardware tier changed)

### 6.3 Performance debug toolkit

Dev tools для диагностики:
- `tools/profile_training.py` - cProfile training
- `tools/profile_forecast.py` - cProfile forecast
- `tools/profile_ui.ts` - Performance API в frontend
- Lighthouse audits для UI performance

---

## 7. Hardware Tier Recommendations

### 7.1 Minimum requirements

- Windows 10/11 64-bit
- CPU 4+ cores, 2.0 GHz+
- RAM 8GB+
- Disk 5GB free
- WebView2 runtime
- Internet for license validation + updates

При minimum specs - operations работают но slower (single-proxy ~60s, forecast ~10s).

### 7.2 Recommended specs

- CPU 8+ cores (preferably 12+), 3.0 GHz+
- RAM 16GB+
- NVMe SSD
- Internet broadband

При recommended - все budgets met.

### 7.3 Premium tier specs (для consultants / heavy users)

- CPU 16+ cores
- RAM 32-64GB
- NVMe SSD
- Multi-monitor support

Operations 1.5-2× faster than budgets.

### 7.4 Document в IT-doc для клиентов

`PASHE_IT.MD` style document для Aurora Launch:
- System requirements
- Recommended specs
- Performance expectations
- Defender exclusions (для antivirus compatibility)

---

## 8. Per-Sprint Performance Validation

| Sprint | Performance deliverables |
|---|---|
| B0 | Performance budgets defined (this doc) |
| B0.5 | BC corpus performance baseline |
| B1 | Schema migration < 200ms |
| B1.5 | Consulting tracker UI < 50ms responsiveness |
| B2 | Similarity recompute < 50ms (WASM), proxy validate < 500ms |
| B3 | Adapt < 2s, transfer validate < 5s, anchors form responsive |
| B4 | All report generation budgets met |
| B5 | All training/forecast/optimize budgets met (verify), posterior update < 20s |
| B6 | Performance budget validation (full suite), telemetry opt-in framework |

---

## 9. Edge Cases

### 9.1 Very long history datasets (>5 years)

DSM 60+ months или Mediascope 250+ weeks:
- Allowed but slower
- Warn user "Training с такой историей займёт ~120s"
- Aurora correctly handles, just performance boundary

### 9.2 Many channels (>10)

10+ media channels:
- Parameter explosion в hierarchical model
- Multi-proxy with N=3 + 10 channels = potential MCMC convergence issues
- Suggest channel grouping (digital_aggregate, regional_aggregate)

### 9.3 Wide forecast horizons (>52 weeks)

P8 boundary - Aurora Launch не покрывает >52 weeks. UI блокирует.

### 9.4 Posterior updates с большим objem recipient data (>26 weeks)

После 26+ weeks recipient data - proxy weight near zero, model fully recipient-driven. **Suggest transition к Aurora Optimize standard MMM** (handoff scenario).

---

## Связанные документы

- `TEST_STRATEGY.md` - performance test infrastructure
- `UX_PRINCIPLES.md` - performance perception (skeleton screens, streaming)
- `../00_Overview/ROADMAP.md` - performance per Sprint
- Memory: `project_econometrica_v109_progress.md` - 9.5× speedup pattern (NumPyro JAX)
