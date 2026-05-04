# Aurora Launch - Principles v1.0

**Status:** CONCEPT FINALIZED 2026-05-04
**Source:** Concept session 001 (Антон + Маша) + Critical audit
**Authority:** эти принципы - foundation для всех product decisions Aurora Launch. Изменения только через explicit decision в Q&A session с logged rationale.

## Контекст

Aurora Launch - продукт Aurora Analytics Suite, цель: предоставить MMM-прогноз для **новых брендов** и **брендов с длительной паузой в рекламе**, у которых нет своих исторических данных для standard MMM. Подход: использовать индивидуально подобранный прокси-бренд из той же категории + recipient anchor data, перенести структурные параметры (adstock shape, hill saturation), сохранив магнитуды recipient-specific.

10 принципов ниже определяют **как работаем**. Они дополняются техническими спецификациями в `02_Data_Spec/` и архитектурными гайдами в `03_Architecture/`.

---

## P1: Прокси - honest baseline, не silver bullet

**Rule:** все transfer'ы прокси -> recipient имеют structural uncertainty. Эта uncertainty явно показана в CI прогноза, decomposed по источникам.

**Why:** клиент должен понимать что прогноз основан на близкой, но не идентичной реальности. Прятать uncertainty = дать iллюзию точности и потерять trust при первом отклонении.

**How to apply:**
- В каждом forecast output - decomposition uncertainty: proxy uncertainty / transfer uncertainty / recipient anchor uncertainty / sampling uncertainty
- В UI confidence interval визуализирован как expanding cone, не single line
- В отчётах explicit caveat: "Прогноз основан на transfer от прокси-бренда X. Реальные результаты зависят от ..."

**Edge case:** если прокси очень близкий по всем 6 dimensions (similarity > 0.9) - всё равно показываем uncertainty (не нули). Вычисление similarity не отменяет фундаментальную uncertainty transfer'а.

---

## P2: Similarity по 6+ measurements (explicit framework)

**Rule:** "близкий прокси" определяется numerically через 6 dimensions. Каждое measurement - explicit similarity score 0-1. Aggregate score - weighted average с обоснованными весами.

**6 dimensions:**
1. **Категория и sub-категория** (например: FMCG snacks / chips / сырные snacks) - точное совпадение sub-категории = 1.0, родственная sub-категория = 0.7, та же категория но другая sub = 0.5, другая категория = 0
2. **Ценовой tier** (премиум / mainstream / эконом / private label) - совпадение = 1.0, соседний tier = 0.5, через tier = 0.2
3. **Размер бренда** (лидер / челленджер / нишевый) - совпадение = 1.0, соседний = 0.6, через = 0.3
4. **Дистрибуция** (национальная / регио / нишевая) - совпадение = 1.0, соседний = 0.5
5. **Медиа-зрелость** (always-on / pulsing / promo-driven / dormant) - совпадение = 1.0, соседний = 0.5
6. **Жизненный цикл** (mature / growing / declining / new) - совпадение = 1.0, соседний = 0.6

**Why:** без explicit framework "близкий прокси" = subjective. Это критично для repeatability и trust.

**How to apply:**
- В UI: form с 6 dimensions, dropdown'ы для каждой
- Real-time radar chart визуализация (см. UX_PRINCIPLES C3)
- Aggregate score = simple weighted average (веса определяются в S003 Similarity Framework session)
- Threshold для verdict: High (>=0.85), Medium (0.65-0.85), Low (0.50-0.65), Insufficient (<0.50)

**Edge case:** если recipient в новой категории без established прокси - предупреждение "Insufficient proxy match" + suggestions к пересмотру.

---

## P3: Адаптация переносит shape, не magnitude

**Rule:** из прокси переносятся **структурные параметры** (формы кривых) с категорийными priors, не **магнитуды** (значения в абсолютных единицах). Магнитуды восстанавливаются из recipient anchors. Каждый shape parameter имеет prior с uncertainty bounds - точные значения refine при training с recipient data (если есть).

**Что переносится (shape):**
- **Adstock decay** (per channel, с категорийным prior) - decay варьируется по типу медиа (TV ~50% weekly, digital ~80%), категории (long-cycle vs impulse), креативу. Переносится **per-channel decay rate с inflation factor для transfer uncertainty**, не single категорийный value.
- **Hill saturation shape** (формы кривой насыщения spend -> response, alpha + gamma parameters)
- **Reach-frequency response curve shape**
- **Категорийная сезонность** (deviation from yearly mean - категорийная характеристика)
- **Long-term trend** (категория растёт / падает / стагнирует - категорийная характеристика)

**Что НЕ переносится (magnitude):**
- β coefficients (масштаб эффекта на recipient зависит от его размера)
- Baseline продаж (зависит от дистрибуции, цены, organic спроса)
- Cross-category competitive pressure (зависит от competitive set recipient'а)

**Что восстанавливается из recipient anchor data:**
- Magnitude calibration через market_size + planned_share + distribution_target
- Initial baseline projection
- Competitive context

**Why:** механический копирование magnitudes = wrong. Премиум-бренд с share 5% не может иметь те же абсолютные продажи как mainstream-лидер с share 20%, даже при идентичной кривой adstock.

**How to apply:**
- В `engines/launch_adapt.py`: `extract_proxy_priors()` extracts shapes + uncertainty bounds, `apply_recipient_magnitudes()` rescales к recipient context
- Каждый shape parameter имеет prior (point estimate + variance) для recipient model
- Magnitudes - **independent priors** на recipient, informed только anchor data

**Edge case:** если recipient в **той же ценовой группе и размере** что прокси (similarity 0.9+) - можно permit small magnitude transfer (ratio scaling). Но default - independent magnitudes.

---

## P4: Posterior update - мягкий partial pooling

**Rule:** прокси постепенно "ослабевает" по weight schedule по мере накопления recipient'ом данных. Не "on/off switch", а continuous weighting.

**Schedule (предварительный, финал в S005):**
- T=0 (pre-launch): 100% proxy priors, 0% recipient likelihood
- T=4-8 нед: 80% proxy / 20% recipient
- T=12-16 нед: 50/50
- T=20-26 нед: 30% proxy / 70% recipient
- T=40+ нед: 5% proxy (residual в priors only) / 95% recipient

**Why:** жёсткий switch (proxy on / proxy off) = discontinuity в forecast'е, разрушающая trust клиента. Мягкое ослабление = honest reflection того что у нас становится больше recipient evidence.

**How to apply:**
- Weight schedule вычисляется на основе Effective Sample Size (ESS) recipient data
- В UI: visible "Proxy weight: 50%" badge с tooltip объяснением
- В отчёте: explicit "Forecast generated с proxy weight = X%"
- Posterior update event logged + reproducible

**Edge case:** если recipient data drift'ует существенно от proxy expectations (high posterior predictive deviation) - **accelerate weight reduction** (proxy reflects category but not this recipient).

---

## P5: Quality stamp transparent перед использованием

**Rule:** клиент видит **до** генерации forecast'а:
- Aggregate similarity score (0-1)
- Confidence verdict (High / Medium / Low / Insufficient)
- Explicit warnings какие dimensions не совпадают и почему это важно
- Block forecast generation если Insufficient

**Why:** прогноз без quality context = опасный. Клиент должен сделать informed decision: "доверять / искать другой прокси / собрать больше anchors".

**How to apply:**
- UI step "Proxy Selection" имеет confidence panel (live update при заполнении dimensions)
- "Generate Forecast" button **disabled** при Insufficient
- При Medium/Low - warning modal с suggestions
- В отчёте - первая страница содержит quality summary

**Edge case:** Quality verdict влияет на CI спецификацию - High = tighter CI, Low = wider CI (uncertainty propagated explicitly).

---

## P6: Assisted product, не self-serve (с AI helper, не AI replacement)

**Rule:** Aurora Launch - **assisted SaaS** с consulting hours встроенными в subscription. Proxy selection ВСЕГДА финализируется человеком (эксперт клиента / эксперт агентства / Антон). AI может помочь, не подменить.

**Why:**
- Proxy подбор требует category expertise + judgment - это **value premium** Aurora Launch
- Library попыток (canned 5-10 моделей) не покроет heterogeneity РФ-рынка
- Human-in-the-loop = quality control + trust signal

**How to apply:**
- Sales process включает "Proxy Discovery Session" (Антон или customer expert)
- В UI: AI suggestion sidebar ("эти 3 прокси похожи на recipient") - но **не auto-pick**
- Финальный proxy choice - explicit user action ("Confirm proxy: X")
- Consulting hours tracker логирует proxy review sessions
- AI suggestion использует категорийные метаданные, не библиотеку моделей (см. P-history note)

**Edge case:** Phase C+ AI helper может предлагать candidates на основе recipient brief, но decision всегда у эксперта.

---

## P7: Single-proxy default, multi-proxy через expert toggle

**Rule:** UI default режим - один прокси, прямой transfer. Multi-proxy (2-3 proxies с partial pooling) - power-user feature, включается экспертом explicitly с обоснованием.

**Why:**
- Single-proxy: simple to explain, faster training, easier UI
- Multi-proxy: robust к outliers одного бренда, лучше для volatile categories - но сложнее
- Большинство launches не требуют multi-proxy
- Decision "когда multi" - экспертная

**How to apply:**
- UI default: single field "Proxy brand" + 6 similarity dimensions
- Expert toggle: "Использовать несколько прокси (для volatile categories)" - разворачивает 2-3 прокси form + weight assignment
- Tooltip explanation: "Multi-proxy полезно когда лидер категории нестабилен (sharp swings в SoV или recent change ownership)"
- Технически - **два разных engine** (single_proxy_transfer + multi_proxy_hierarchical) с common interface (избегаем mathematical degeneracy hierarchical с N=1 group)

**Edge case:** если эксперт всё-таки выбирает multi с N=2 и very similar proxies - warning "лучше выбрать single + sensitivity analysis".

---

## P8: Strict product boundaries

**Rule:** Aurora Launch покрывает **только**:
- KPI: продажи (sales-only). Awareness modeling - в Aurora Brand
- Use cases: (1) новый бренд (zero history), (2) бренд с длительной паузой в рекламе. Use case (3) - новый SKU в существующем портфеле - **не в Launch**, в Aurora Optimize "New SKU" workflow

**Why:**
- Узкий продукт = чёткий sales pitch, понятный pricing, focused engineering
- Awareness в отдельном продукте позволяет CMO/CFO conversation отдельный sales motion
- Portfolio launches требуют multi-output Bayesian - другая math, входит в Aurora Portfolio (Phase D)

**Decision tree для sales:**
- "Нет MMM-истории по этому бренду, новый продукт" -> **Aurora Launch**
- "Есть данные по другим SKU портфеля, launchаем новый flavor" -> **Aurora Optimize** + New SKU workflow
- "Хотим понять как реклама строит знание для CFO" -> **Aurora Brand**
- "Есть собственная MMM-история, оптимизируем" -> **Aurora Optimize** standard
- "Всё перечисленное" -> **Aurora Suite Bundle**

**How to apply:**
- Onboarding wizard в Aurora Launch проверяет use case fit (если client says "у меня есть данные за 2 года" - redirect к Optimize)
- Marketing landing explicit "когда нужен Launch / когда не нужен"
- Cross-product handoff в UI: "Этот use case лучше в Aurora Optimize - открыть?"

**Edge case:** борьба с paid customer "только Launch достаточно" когда явно нужен Suite - честный совет купить Brand (loss of one-product sale, gain trust).

---

## P9: Максимум reuse из Econometrica (80%+ codebase)

**Rule:** Aurora Launch - не parallel codebase, а **расширение** Aurora Econometrica engines + design system. Изменения в shared code coordinated через Phase A platform foundation.

**Полностью переиспользуем:**
- `engines/modeler.py` - Bayesian MMM core (ready Phase 2.7)
- `engines/decomposer.py` - decomposition logic
- `engines/optimizer.py` - budget optimization
- `engines/scenario.py` - what-if scenarios
- `aurora_html/`, `aurora_pptx/`, Rust XLSX writers
- Aurora Hybrid Design System tokens (Sacred Lime + Aurora Deep + Gold)
- Tauri shell template (Phase A deliverable)
- Trust 3 hierarchical priors (готовые priors для категорий)
- Conformal Prediction CI (distribution-free)
- KPI registry pattern (extension с launch sales-only config)
- Pickle schema v2.0 (additive под proxy_metadata + recipient_anchors + transfer_provenance)

**Расширяем (additive, не breaking):**
- Pickle schema (v3.0 additive fields)
- Validate UI (proxy quality badges на existing badges layer)
- Help system (launch-specific docs в shared format)

**Новое (Aurora Launch specific):**
- `engines/launch_adapt.py` - extract_proxy_priors + apply_recipient_magnitudes
- `engines/launch_posterior_update.py` - partial pooling weight schedule
- `engines/launch_validators.py` - SemanticValidator + ProxyDataValidator
- `engines/single_proxy_transfer.py` - single-proxy transfer engine
- `engines/multi_proxy_hierarchical.py` - hierarchical engine для N>=2 proxies
- `aurora_pptx/launch_forecast/` - report template (8 sections)
- 4 Svelte cabinets: ProxySelectionStep, RecipientAnchorsStep, TransferValidateStep, PosteriorUpdateStep

**Why:**
- Engineering velocity: не строим заново working math
- Consistency: клиенты Suite видят shared visual language + shared accuracy
- Maintenance: один engine - один patch для всех

**How to apply:**
- Code review: каждый PR в Launch проверяется на "можно ли это сделать в shared, не Launch-specific?"
- Architecture decision: shared code lives в `aurora-platform-core` package (Phase A deliverable)
- Refactoring during Phase B coordinate с Phase A platform team

**Edge case:** если новая Launch функция требует math изменения в shared engine - phase coordination + regression test (Optimize/Brand/Promo не должны сломаться).

---

## Platform scope (Phase B)

**Rule:** Aurora Launch Phase B - **Windows 10/11 64-bit only**. Phase D consideration: Mac / Linux support (after Suite Bundle stabilization).

**Why:** Tauri shell template Phase A targets Windows (consistent с Aurora Econometrica installer). Sales focus РФ-рынок где Windows dominate enterprise workstations.

**How to apply:**
- All UX patterns (keyboard shortcuts, file paths) - Windows-style
- Installer NSIS only Phase B
- WebView2 runtime requirement
- "Cmd+K" патерны переписываются как **Ctrl+K** или Ctrl+Shift+P (VSCode-style)
- Documentation для customer setup - Windows-specific

---

## P10: Premium Feel - продукт ощущается технологичным с первой секунды (NEW after audit)

**Rule:** UX details, transparency, reproducibility - first-class citizens с Sprint B0. Не "polish" в конце, а foundation principle. Каждое UI решение проходит через "premium product lens".

**Why:**
- Pricing 1.5-3M/год требует premium feel. Иначе клиент думает "за 3M я могу нанять консультанта"
- Trust = первое впечатление. Slow loading + ugly forms = no trust
- Differentiator vs commodity tools (Excel + Python) = experience quality

**How to apply:**
- **Visual:** Aurora Hybrid Design System (Aurora Deep + Sacred Lime + Gold)
- **Interactivity:** real-time validation, instant feedback (WASM для similarity, см. B4)
- **Animations:** forecast cone reveal, similarity radar fill, achievement chimes (mute-able)
- **Transparency:** methodology drill-down everywhere, formulas visible (LaTeX)
- **Reproducibility:** hash signatures, model cards, methodology certificates (PDF)
- **Accountability:** event sourcing audit trail, versioning slider, project history
- **Power user:** Cmd+K command palette, keyboard shortcuts
- **A11y:** WCAG AA compliance (как в Econometrica HTML)
- **Empty states:** branded illustrations + helpful CTAs
- **Onboarding:** templates library, product tour, glossary

**Specific deliverables (Sprint B2-B6):**
- Dashboard "My Aurora" entry point (см. UX_PRINCIPLES C1)
- Live similarity radar chart (C3)
- Forecast cone animation (C4)
- Tier badges Gold/Silver/Bronze (C11)
- Methodology certificate PDF per forecast (C10)
- Versioning slider + audit trail (C7, C8)
- Ctrl+K command palette (C9)
- Templates library (C14)

**Testable criteria для P10:**
- Initial app launch ≤ 3s (First Contentful Paint)
- 95% UI interactions feedback ≤ 200ms
- WCAG AA compliance verified per Sprint (не только B6)
- Lighthouse perf score ≥ 90 (HTML reports)
- All charts have methodology drill-down
- All forecasts have hash signature + Methodology Certificate PDF
- 0 spelling/grammar errors в user-facing copy (validated через review)
- All animations respect `prefers-reduced-motion`
- Sound effects mute-able

**Edge case:** balance между premium feel и performance. Если animation slows down workflow - simplify. Premium != heavy.

---

## Принципы как контракт

Эти 10 принципов - foundation. Каждое product decision Aurora Launch проверяется против них. Изменение принципа = explicit Q&A session с logged rationale в `05_Sessions/`.

**Связанные документы:**
- `ROADMAP.md` - реализация принципов в sprints B0-B6
- `PRODUCT_BOUNDARIES.md` - детали P8 (что в Launch, что не в Launch)
- `02_Data_Spec/DATA_REQUIREMENTS.md` - детали P3 (что переносим / откуда anchors)
- `03_Architecture/REUSE_FROM_ECONOMETRICA.md` - детали P9 (reuse map)
- `03_Architecture/UX_PRINCIPLES.md` - детали P10 (premium UX implementation)
- `03_Architecture/DATA_PRIVACY.md` - operational principles (local-first, DPA)
