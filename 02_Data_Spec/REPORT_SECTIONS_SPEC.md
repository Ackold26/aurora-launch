# Aurora Launch - Report Sections Specification

**Status:** Accepted (S006 closed 2026-05-04)
**Authority:** P5 (Quality stamp transparent) + P10 (Premium Feel) в `00_Overview/PRINCIPLES.md`
**Sprint context:** Sprint B4 implementation reference
**Owner:** Маша (design) + Антон (customer perspective)

## Контекст

P10 declares premium feel - reports = первый touchpoint клиента с результатом Aurora Launch. Plain Excel-style table = wrong impression. Этот документ финализирует:

1. **8-section template** detail (что именно в каждой section)
2. **Per-format guidance** - PPTX (premium presentation), HTML (interactive), XLSX (data drill-down), PDF Methodology Certificate (audit document)
3. **Methodology Certificate** - separate single-page PDF generator spec (WeasyPrint)
4. **Customer-facing language tone** - CFO-friendly framing + plain language phrases
5. **Optional appendices** (decomposition + optimization) - когда включать

Sprint B4 implements `aurora_pptx/launch_forecast/`, `aurora_html/launch_forecast/`, Rust XLSX writer extension, и WeasyPrint Methodology Certificate generator per этот документ.

---

## 1. Eight-Section Template (PPTX primary)

Total slides: **16-20** (8 base sections + ~8 supporting/transition slides). Premium pacing - one major idea per slide, generous whitespace.

### 1.1 Section 1 - Cover (1 slide)

**Purpose:** establish premium impression first 3 seconds.

**Elements:**
- Aurora wordmark logo (custom letterforms, brand standard) - top-left
- Project name (recipient brand name, 32pt) - center
- Subtitle: "Launch Forecast Report" (16pt, secondary)
- Date generated (right-aligned, 12pt)
- Aurora Launch version (e.g., "v1.4.0") - footer left
- Project ID short form (UUID first 8 chars + "...") - footer right
- Hash signature (SHA-256 first 8 chars) - footer center
- Background: Sacred Lime (Aurora primary), Aurora Deep wordmark accent
- Optional: subtle background pattern (radar grid motif)

**Customer phrase (subtitle area):** "Прогноз запуска бренда на основе индивидуально подобранного прокси и recipient anchors"

### 1.2 Section 2 - Executive Summary (1-2 slides)

**Purpose:** CFO/CMO grasps headline в 30 seconds.

**Slide 2.1 - Headline:**
- Large numeric headline: "Прогноз продаж 12 недель: **X млн ₽** ± Y%" (95% CI)
- Tier badge prominent (Gold 🥇 / Silver 🥈 / Bronze 🥉) - top-right
- Confidence verdict text: "Уверенность: Medium" (color-coded)
- Plain-language one-liner: "Запуск базируется на прокси-бренде [X] с similarity 0.78"

**Slide 2.2 - Key Metrics Table:**
| Период | Прогноз продаж, млн ₽ | 95% CI | Tier |
|---|---|---|---|
| 12 недель | X.XX | ±Y.Y% | 🥈 |
| 26 недель | X.XX | ±Y.Y% | 🥈 |
| 52 недели | X.XX | ±Y.Y% | 🥈 |

**Plain-language framing footer:**
"Что это означает: с уверенностью 95% продажи за первые 12 недель будут в диапазоне [X-, X+] млн ₽. Aurora использует распределение неопределённости из 4 источников - см. раздел 4."

**Aurora differentiator note (small text):** "Forecast generated using individual proxy transfer + recipient anchors. Methodology Certificate (PDF) attached separately."

### 1.3 Section 3 - Proxy Quality (2-3 slides)

**Purpose:** trust through transparency - клиент видит как мы измерили "близость прокси".

**Slide 3.1 - Selected Proxy:**
- Proxy brand name + category (L1/L2/L3 path)
- Proxy data period: "DSM 2022-01 to 2024-12 (36 месяцев)"
- Mediascope coverage: "TV + Digital, 30 каналов, weekly grain"
- Image: Aurora category icon + brand name typography

**Slide 3.2 - Similarity Radar (key visualization):**
- 6-dimension radar chart (ECharts in HTML, native chart в PPTX)
- 6 dimensions с per-dimension scores на radar:
  - Категория: 1.00
  - Pricing tier: 0.50
  - Brand size: 0.30
  - Distribution: 1.00
  - Media maturity: 0.50
  - Lifecycle: 0.30
- Aggregate similarity score prominent: "S = 0.70 (Medium)"
- Color: similarity > 0.85 green, 0.65-0.85 yellow, 0.50-0.65 orange, <0.50 red

**Slide 3.3 - Dimension Scores Table:**
| Dimension | Proxy | Recipient | Score | Comment |
|---|---|---|---|---|
| Category | OTC.cold_flu.antiviral | OTC.cold_flu.antiviral | 1.00 | L3 exact match |
| Pricing tier | MAINSTREAM | PREMIUM | 0.50 | 1 step apart |
| ... | ... | ... | ... | ... |

**Multi-proxy variant:** Section 3 expands к 4-5 slides:
- Per-proxy radar (small) per slot
- Combined aggregate radar
- Pooling weights табличка
- Per-proxy verdicts + combined

### 1.4 Section 4 - Transfer Caveats (1-2 slides)

**Purpose:** intellectual honesty - клиент understands что переносится, что нет.

**Slide 4.1 - What Transfers / What Does Not:**
- Two-column layout
- **Переносится (shape):**
  - Adstock decay (per channel)
  - Hill saturation shape
  - Категорийная сезонность (52-week pattern)
  - Long-term trend slope
- **НЕ переносится (recipient-specific):**
  - β coefficients (масштаб)
  - Baseline продаж
  - ROI levels
  - Cross-category competitive controls
- **Восстанавливается из anchors:**
  - Magnitude calibration (market_size × planned_share × distribution × pricing_factor)
  - β priors (scaled от proxy effectiveness × recipient size)

**Slide 4.2 - Uncertainty Decomposition:**
- Pie chart 4-source decomposition:
  - Proxy uncertainty: 30%
  - Transfer uncertainty: 40% (driven by similarity verdict)
  - Anchor uncertainty: 15%
  - Sampling uncertainty: 15%
- Inflation factor explanation: "Medium verdict → 1.5× CI inflation"
- Plain language: "При лучшем подборе прокси (similarity 0.85+) transfer uncertainty снижается с 40% до 22% общей вариации"

### 1.5 Section 5 - Forecast 12 Weeks (3-4 slides)

**Purpose:** immediate launch period - tight CI, weekly granularity.

**Slide 5.1 - Cone Visualization:**
- Forecast mean line + 50/80/95% CI bands (expanding cone animation в HTML)
- Weekly time axis
- Y-axis: Sales ₽
- Annotations: launch date, key milestones (e.g., "Distribution at 100% of target")

**Slide 5.2 - Weekly Breakdown Table:**
| Неделя | Mean ₽ | CI 50% | CI 95% | Notes |
|---|---|---|---|---|
| 1 | X | [a, b] | [c, d] | Launch week |
| 2 | X | [a, b] | [c, d] | |
| ... | | | | |

**Slide 5.3 - Channel Decomposition:**
- Stacked area chart per channel + baseline
- Show contribution timeline
- Top 3 channels highlighted by color

**Slide 5.4 - Sensitivity Analysis (optional, included для Pro+ tier):**
- Tornado chart: anchor field changes ±20% → forecast impact
- Top sensitive parameters listed

### 1.6 Section 6 - Forecast 26 Weeks (3-4 slides)

**Purpose:** 6-month ramp - distribution и SoV plateau period.

Same structure как Section 5 but:
- Wider CI cone
- Weekly OR monthly grain (toggle)
- Distribution ramp visible (если recipient anchor.distribution_ramp_weeks ≤ 26)

### 1.7 Section 7 - Forecast 52 Weeks (3-4 slides)

**Purpose:** annual planning + ongoing scenario context.

Same structure but:
- Widest CI cone
- Monthly grain (weekly too noisy at this scale)
- Annual summary metrics
- Optional: posterior update reminder ("После 12-16 недель recipient data Aurora обновит прогноз с уменьшенной CI")

### 1.8 Section 8 - Methodology + References (2 slides)

**Purpose:** academic rigor signals - peer review-like trustworthiness.

**Slide 8.1 - Math + Citations:**
- Adstock formula (LaTeX): `A_t = X_t + λ × A_{t-1}`
- Hill formula: `H(x) = β × x^γ / (k^γ + x^γ)`
- Transfer math summary
- Academic references (subset, full в Methodology Certificate):
  - Robyn (Meta) - https://facebookexperimental.github.io/Robyn/
  - Konstantinopoulos & Massaro (2014) - ESS
  - Tibshirani et al. (2019) - Conformal Prediction под shift
  - Gelman et al. (2013) - Bayesian Data Analysis

**Slide 8.2 - Model Card + Reproducibility:**
- Model parameters summary
- Diagnostics: Gelman-Rubin <1.05, ESS >400, divergent transitions = 0
- R² posterior = 0.85
- MAPE posterior = 12%
- Hash signature (SHA-256) - full
- Aurora Launch version
- Generated date + project ID
- "Methodology Certificate PDF (single page) attached separately"

---

## 2. Per-Format Guidance

### 2.1 PPTX (premium presentation)

**Purpose:** sales presentation, board-room ready.

**Implementation:**
- `aurora_pptx/launch_forecast/` template (Sprint B4)
- Reuse Aurora Hybrid Design System (Aurora Deep + Sacred Lime + Gold)
- python-pptx + custom layouts
- High-res charts via matplotlib (PNG embedded) + native PPTX charts (для editable)
- Fonts: Inter Variable (body) + Lora (display). Embedded в pptx.
- Premium pacing: ~16-20 slides total

**Recommended for:** CFO/CMO/board presentations, sales deals.

### 2.2 HTML (interactive)

**Purpose:** rich interactive exploration.

**Implementation:**
- `aurora_html/launch_forecast/` template (reuses Aurora narrative_adapter pattern)
- ECharts 5 для interactive charts
- Animations:
  - Forecast cone reveal (0.8s)
  - Similarity radar fill (0.5s)
  - Tier badge bounce on appearance
  - All respect `prefers-reduced-motion`
- Hash signature in URL для sharing reproducible reports
- WCAG AA compliance (contrast, keyboard nav, ARIA)
- Methodology drill-down everywhere (click formula → modal с derivation)
- Cmd+K command palette (jump к section)

**Recommended for:** internal review, online sharing, customer self-service exploration.

### 2.3 XLSX (data drill-down)

**Purpose:** raw numbers для analyst, custom modeling.

**Implementation:**
- Rust XLSX writer extension (existing `src-tauri/src/xlsx_writer/`)
- Multi-sheet workbook:
  - Sheet 1: Summary (key metrics)
  - Sheet 2: 12w forecast (weekly breakdown)
  - Sheet 3: 26w forecast
  - Sheet 4: 52w forecast
  - Sheet 5: Channel decomposition (per channel × period)
  - Sheet 6: Anchors (recipient input snapshot)
  - Sheet 7: Proxy data summary
  - Sheet 8: Diagnostics (model fit, posterior summary)
- All cells with formulas inline (audit-friendly)
- Frozen headers, conditional formatting (CI width, tier colors)

**Recommended for:** analysts custom modeling, due diligence reviews.

### 2.4 PDF Methodology Certificate (audit document)

См. Section 3 ниже.

---

## 3. Methodology Certificate PDF

**Purpose:** single-page (or 2-page) audit document с regulator-ready certification.

**Format:** standalone PDF, Aurora-letterhead style.

**Generator:** WeasyPrint (decided per ADAPTATION_RULES Section 3.3).

### 3.1 Page 1 (Certificate)

**Header:**
- Aurora wordmark logo (top-center, larger)
- "Methodology Certificate" title
- Date issued

**Body:**

**Project identification:**
- Recipient brand: [name]
- Project ID: [UUID]
- Aurora Launch version: [v1.4.0]
- Hash signature: [full SHA-256]

**Methodology summary (2-3 paragraphs):**

> Прогноз запуска бренда [recipient_name] подготовлен Aurora AI Launch v1.4.0 с использованием метода Bayesian Marketing Mix Modeling с переносом структурных параметров от прокси-бренда [proxy_name].
>
> Прокси-бренд выбран по 6-мерной similarity framework (категория, ценовой tier, размер, дистрибуция, медиа-зрелость, lifecycle) с aggregate similarity score [S=0.78] (verdict: Medium). Транспортируются shape parameters (adstock decay, hill saturation, категорийная сезонность). Magnitudes калибруются от recipient anchors (market_size_rub, planned_share_pct, distribution_target_pct, pricing_index_vs_proxy).
>
> Неопределённость декомпозирована на 4 источника: proxy uncertainty ([30%]), transfer uncertainty ([40%]), anchor uncertainty ([15%]), sampling uncertainty ([15%]). 95% CI inflated на 1.5× для transfer uncertainty согласно similarity verdict Medium.

**Forecast table:**
| Период | Прогноз ± 95% CI |
|---|---|
| 12 недель | X.XX млн ₽ ± Y.Y% |
| 26 недель | X.XX млн ₽ ± Y.Y% |
| 52 недели | X.XX млн ₽ ± Y.Y% |

**Confidence statement:**
> Aurora AI certifies that this forecast was generated through reproducible methodology согласно архитектурным принципам Aurora Launch v1.4.0. Hash signature [...] позволяет проверить identity модели и входных данных.

**Signature:**
- Антон Сипович, Founder Aurora AI
- Date: 2026-XX-XX
- Cryptographic hash: [SHA-256]

### 3.2 Page 2 (Optional - Detailed Methodology)

**For Pro+ tier:** detailed math + diagnostics:
- Adstock formula
- Hill formula
- Transfer math
- Magnitude calibration formula
- Diagnostics table (Gelman-Rubin, ESS, divergent transitions, R², MAPE)
- Model card (full parameter list, prior strengths, posterior summaries)

**For Starter tier:** Page 2 omitted (single-page certificate).

### 3.3 Branding

- Letterhead: Aurora wordmark (Aurora Deep на Sacred Lime accent)
- Watermark: subtle Aurora Launch logo background
- Footer: "Aurora AI · Платформа Аврора · auroraai.pro · ackold@yandex.ru"
- Embedded fonts (Inter Variable + Lora WOFF2)

### 3.4 Reproducibility

- Hash signature embedded в PDF metadata (not just visible text)
- Hash composition: SHA-256 (project_data + model_artifacts + aurora_version)
- Verification tool (Phase D): `aurora-verify <certificate.pdf> <project.aurora>`

---

## 4. Customer-Facing Language

### 4.1 Tone Principles

- **CFO-friendly framing** - финансовая лексика прежде технической
- **Plain language defaults** - технический жаргон только в methodology section + Pro+ Page 2
- **Honest uncertainty** - "вероятно", "при заданных предпосылках", "с уверенностью 95%" - не "гарантировано"
- **Russian first** - all UI и reports на русском (Phase B). English support Phase D.

### 4.2 Reusable Phrases

**Headline forecast:**
> "Прогноз продаж за первые 12 недель: **X млн ₽** ± Y% (95% доверительный интервал)"

**Tier verdict:**
- High (Gold): "Высокая уверенность - близкий прокси-бренд + полные anchors"
- Medium (Silver): "Средняя уверенность - подходящий прокси, требует verification posterior update"
- Low (Bronze): "Низкая уверенность - прокси не идеален, рекомендуется поиск лучшего candidate"

**Transfer caveat boilerplate:**
> "Прогноз основан на трансфере структурных параметров от прокси-бренда [X]. Magnitude калибруется от ваших recipient anchors. Real-world результаты могут отличаться - неопределённость явно показана в 95% CI."

**Posterior update reminder:**
> "После 12-16 недель реальных recipient данных Aurora обновит прогноз. Предполагаемое сужение CI: -25-40% при стабильном recipient response."

**Methodology cross-reference:**
> "Полная методология + список академических источников - в разделе 8 этого отчёта и в Methodology Certificate PDF."

### 4.3 Forbidden Phrases (anti-patterns)

❌ "Гарантированный результат" - никогда. Aurora не гарантирует.
❌ "Точный прогноз" - всегда есть uncertainty.
❌ "Превзойдёт конкурентов" - вне scope MMM.
❌ "Полностью автоматизированный" - assisted product (P6).

---

## 5. Optional Appendices

### 5.1 Appendix A - Decomposition (Pro+ tier only)

When to include: Pro/Enterprise deliverables, или explicit Antón/customer request.

**Content:**
- Per-channel contribution to total sales (week × channel matrix)
- Baseline vs media decomposition
- ROI per channel (computed from posterior)
- Diminishing returns visualization (hill curve per channel)

**Slide count:** 3-4 dedicated slides если включено.

### 5.2 Appendix B - Optimization Scenario (Pro+ tier only)

When to include: customer asks "what if I change budget allocation?".

**Content:**
- Budget reallocation suggestion (Aurora optimizer.py results)
- Constrained optimization (per-channel limits respect)
- "What-if" comparisons
- ROI improvement potential

**Slide count:** 2-3 dedicated slides.

### 5.3 Appendix C - Sensitivity Analysis (all tiers)

When to include: always - audit reproducibility requirement.

**Content:**
- Tornado chart: anchor fields ±20% → forecast impact
- Top 3 sensitive parameters listed
- Recommendation: "Refine [parameter X] для tighter forecast"

**Slide count:** 1 slide.

---

## 6. Implementation Files (Sprint B4)

**PPTX template:**
- `aurora_pptx/launch_forecast/launch_forecast.report.yaml` (template definition)
- `aurora_pptx/launch_forecast/templates/` (slide layouts XML)
- Reuse `aurora_pptx/narrative_adapter.py` pattern (data → context object → render)

**HTML template:**
- `aurora_html/launch_forecast/index.html.jinja2`
- `aurora_html/launch_forecast/style.css` (extends Aurora Hybrid)
- ECharts integrations

**XLSX writer:**
- `src-tauri/src/xlsx_writer/launch_forecast.rs` (multi-sheet generator)

**PDF Methodology Certificate:**
- `engines/methodology_certificate.py` (WeasyPrint generator)
- `engines/templates/certificate.html` (Jinja2 template)
- `engines/templates/certificate.css` (print-specific styles)

**Tests:**
- `tests/integration/test_launch_forecast_report.py` - generate sample → snapshot match
- `tests/unit/test_methodology_certificate.py` - PDF generation + hash verification

---

## 7. Acceptance Criteria (Sprint B4 ship)

- [ ] PPTX template renders 16-20 slides из real recipient project
- [ ] HTML version interactive (charts work, animations smooth, a11y AA)
- [ ] XLSX 8-sheet workbook generates без формула errors
- [ ] PDF Methodology Certificate single-page (Starter) или 2-page (Pro+) generates
- [ ] Hash signature embedded в PDF metadata + visible text
- [ ] All Russian copy reviewed (no spelling/grammar errors)
- [ ] Customer phrases match Section 4.2 reusable list
- [ ] Animation respects `prefers-reduced-motion`
- [ ] Generated reports < 30 seconds (PPTX), < 5 seconds (HTML), < 10 seconds (XLSX), < 15 seconds (PDF)

---

## 8. Связанные документы

- `../00_Overview/PRINCIPLES.md` P5 (Quality stamp transparent) + P10 (Premium Feel)
- `../03_Architecture/UX_PRINCIPLES.md` - design system + interaction patterns
- `../03_Architecture/REUSE_FROM_ECONOMETRICA.md` Section 1.2 - reporting layer reuse
- `../03_Architecture/ADAPTATION_RULES.md` - что показываем в Section 4 Transfer Caveats
- `../03_Architecture/POSTERIOR_UPDATE_DESIGN.md` - posterior update reminder copy
- `SIMILARITY_FRAMEWORK.md` - что показываем в Section 3 Proxy Quality
- `../06_References/PRICING_TIERS.md` (S009) - Pro+ tier features (Section 5/Appendices)
- `../05_Sessions/SESSION_NEXT_QUESTIONS.md` S006 closed reference
