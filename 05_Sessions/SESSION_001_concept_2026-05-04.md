# Session 001: Concept Finalization Aurora Launch

**Date:** 2026-05-04
**Participants:** Антон + Маша
**Duration:** ~5 часов (concept dialogue + audit + autonomous file creation)
**Output:** 17 files в `D:\Docs\Aurora_Ai\Aurora Launch\` + memory update + audit

## Цель сессии

Концептуально проработать идеологию и принципы работы Aurora Launch (продукт Phase B Aurora Analytics Suite, №1 priority). Завершить:
1. 9 принципов работы продукта
2. Data Requirements Spec (Variant 2)
3. Общий план разработки (все этапы)
4. Critical audit плана с improvements
5. Implementation начало (17 файлов проектной документации)

## Ключевые решения (Decision Log)

### D001: Aurora Launch цель
- Помочь новым компаниям + компаниям с длительной паузой в рекламе сделать MMM-прогноз без собственной истории
- Через индивидуально подобранный прокси-бренд + recipient anchor data
- Базируется на Aurora Econometrica engines (80%+ reuse)

### D002: Отказ от donor library
**Антон:** "я не верю в библиотеку - прокси будет подбираться каждый раз разный - это индивидуально".

**Rationale:**
- Categorical heterogeneity РФ-рынка не покрывается 5-10 моделями
- Bias-by-curation (library = "лучший представитель категории на момент N", но клиенту нужна модель **близкая к его рыночному положению**)
- Single-version-of-truth ловушка
- Maintenance burden без incremental revenue

**Альтернатива:** AI-assisted proxy suggestion (Phase C+) - **помощь эксперту**, не self-serve replacement (P6 maintained).

### D003: Бизнес-модель = subscription
- **Тестовый период + годовая подписка с поддержкой и обновлениями**
- Unlimited launches + 20-40h consulting hours
- Premium pricing 1.5-3M/год (Starter / Pro / Enterprise tiers - финал в S009)
- Hours tracker нужен с старта Phase B (не Phase C - audit A14)

### D004: Source данных = DSM Group + Mediascope
- DSM Group monthly Excel (sales рубли + упаковки + дистрибуция + цена + пенетрация)
- Mediascope TV (TRP / GRP / budget per channel/demo)
- Mediascope Digital (impressions / budget per platform)
- AdIndex Digital Budget как alternative source
- **Legal-clean industrial syndicated data** - нет правовых рисков (все клиенты подписчики)

### D005: Подбор прокси и сбор данных = клиент / агентство
- Aurora даёт **точный перечень данных** (обязательно + рекомендовано)
- Клиент или агентство собирают данные через свою подписку DSM/MS
- Aurora обрабатывает локально - **local-first архитектура** (audit A8)
- Антон participates в **Proxy Discovery Session** (не self-serve)

### D006: Single-proxy default + multi-proxy expert toggle
- UI default: один прокси-бренд + 6 similarity dimensions
- Expert toggle: 2-3 прокси с partial pooling для volatile categories
- **Технически - два разных engine** (single_proxy_transfer + multi_proxy_hierarchical) для избежания mathematical degeneracy hierarchical с N=1 (audit A4)

### D007: Awareness не в Launch (отдан Aurora Brand)
- Aurora Launch = **только sales forecast**
- Awareness modeling = Aurora Brand
- Hочешь и launch sales + awareness → Suite bundle
- Это упрощает Launch: не нужен Weibull adstock + dual-posterior schema

### D008: Use cases scope
- ✅ (1) Новый бренд (zero history)
- ✅ (2) Бренд с длительной паузой в рекламе (organic baseline есть)
- ❌ (3) Новый SKU в существующем портфеле → **Aurora Optimize "New SKU" workflow**
- Это даёт чёткий sales pitch + clean product boundaries

### D009: Forecast horizon до 52 недель
- Three views: 12 нед (immediate, tight CI) / 26 нед (6-month ramp, medium CI) / 52 нед (year planning, wider CI)
- Visual: expanding uncertainty cone animation (audit C4)
- >52 нед не покрываем (uncertainty слишком велика)

### D010: 80%+ reuse из Econometrica
- Engines (modeler, decomposer, optimizer, scenario, conformal) - shared
- Reporting (aurora_html, aurora_pptx, Rust XLSX) - shared
- Design system tokens, Tauri shell - shared
- Trust 3 hierarchical priors - shared (basis для transfer)
- Pickle schema - additive extension v3.0 (не breaking)

### D011: Pydantic v2 + JSON Schema как SSoT (audit B1, B2)
- JSON Schema = single source of truth
- Auto-gen Python TypedDict + Pydantic models
- Auto-gen TypeScript interfaces для frontend
- Reduces двойная maintenance + ensures contract consistency

### D012: Quality stamp transparent (P5)
- Tier badges Olympic-style: Gold (>=0.85) / Silver (0.65-0.85) / Bronze (0.50-0.65) / Insufficient (<0.50)
- Block forecast generation при Insufficient
- Similarity radar chart real-time fill
- Confidence verdict видим до forecast generation

### D013: Premium Feel as P10 (audit A12 + C-series)
- Audit revealed UX premium feel не упомянут в исходном плане
- Added as 10-th principle с specific UX deliverables: Dashboard "My Aurora", live radar, forecast cone animation, tier badges, methodology drill-down, methodology certificate PDF, versioning slider, audit trail, Cmd+K command palette, templates library

### D014: Local-first architecture explicit (audit A8)
- Все клиентские данные хранятся **локально** на машине клиента
- Aurora cloud получает только: license validation + updates + opt-in telemetry
- **НЕ** shared между клиентами через Aurora cloud
- DPA template prep Sprint B5 для enterprise клиентов

## Что обсуждалось но НЕ решено (open questions)

### OQ001: Pricing tiers финал (Starter/Pro/Enterprise) - **S009**

Predварительно (S009 will finalize):
- Starter 1.5M/год + 20h consulting
- Pro 2.5M/год + 30h consulting + priority
- Enterprise 3M+/год + 40h + custom training + on-site

### OQ002: Free trial длительность - **S009**

Variants:
- 30 дней
- 60 дней
- 90 дней
- Pilot first launch free с case study consent

### OQ003: Aurora Launch git repo / sub-folder - **до Sprint B0.5**

Variants:
- Separate `Aurora_Launch` repo
- Sub-folder в `aurora-business`
- Внутри Aurora monorepo (если monorepo создаётся в Phase A)

### OQ004: SQLite hybrid vs pure pickle - **S005 (audit B3)**

Tradeoff:
- SQLite hybrid: read individual sections, SQL queries, BC через migrations
- Pure pickle: simpler, как Econometrica, breaking change

### OQ005: WASM module для UI similarity - **Sprint B2 prereq (audit B4)**

Variants:
- Rust → WASM module (premium real-time feel)
- Backend API only (simpler)

### OQ006: Streaming MCMC visualization - **Sprint B1 prereq (audit B6)**

Variants:
- SSE / WebSocket streaming traces (turn waiting → teaching moment)
- Simple progress bar

### OQ007: Posterior update math формула - **S005 (audit A7)**

Decision needed:
- ESS-based weighting (Konstantinopoulos 2014)
- Bayesian Model Averaging
- Linear/exponential decay
- Threshold для "proxy released"

### OQ008: Pilot client identification - **S008**

Кто будет первым pilot:
- 1-2 фарма OTC launch teams
- FMCG snacks / напитки launches

### OQ009: Sales playbook - **S010**

Outreach + demo + pilot + conversion templates.

### OQ010: Mediascope/DSM подписка - кто платит - **S010**

- Антон лично (cost overhead)
- Клиент / агентство приносит (default - confirmed)

## Audit findings (60+ items)

См. `C:\Users\ackol\.claude\plans\zippy-wobbling-waffle.md` Часть 3 для полного списка.

**Summary:**
- **A1-A20:** потенциальные ошибки и скрытые риски (HIGH RISK: A1 schema versioning, A3 format adapters drift, A4 hierarchical degeneracy, A7 posterior math, A8 data privacy, A10 similarity algorithm, A11 test strategy)
- **B1-B10:** более эффективные тех решения (Pydantic v2 + JSON Schema, SQLite hybrid, WASM, streaming MCMC, ECharts, plug-in architecture, model cards)
- **C1-C17:** UX premium additions (dashboard, radar chart, cone animation, tier badges, methodology drill-down, methodology certificate, versioning slider, audit trail, Cmd+K, templates, sounds, theme)
- **D1-D8:** trust signals (transparency, reproducibility, open methodology, conformal CI, SBC, compliance, stable release cadence, Aurora seal)
- **E1-E6:** architectural improvements (DDD boundaries, plug-in proxy sources, event sourcing audit, decoupled UI/backend OpenAPI, CQRS lite, performance monitoring)

## Plan delta после audit

**Sprints added:**
- Sprint B0.5: BC Test Corpus & Format Adapters (1 неделя)
- Sprint B1.5: Customer Success Lite (3 дня parallel)

**Q&A blockers reordered:**
- S003 + S007 → до Sprint B2
- S004 → до Sprint B3
- S006 + S009 → до Sprint B4 (S009 moved up)
- S005 → до Sprint B5
- S008 + S010 → до Sprint B6

**Files добавлены (3 новых):**
- TEST_STRATEGY.md (audit A11)
- UX_PRINCIPLES.md (audit A12)
- DATA_PRIVACY.md (audit A8)
- PERFORMANCE_BUDGETS.md (audit A9)
- recipient_anchors_v1.schema.json (audit B1)

**Code stack:**
- Pydantic v2 + JSON Schema SSoT
- Svelte 5 runes patterns explicit
- ECharts 5
- Streaming MCMC visualization
- WASM для UI similarity
- SQLite hybrid for .aurora bundle (decision в S005)
- Two engines (single_proxy_transfer + multi_proxy_hierarchical)

**Phase B длительность:** **7-8 нед** (revised post-implementation audit 2026-05-04: sequential dependencies B0.5 → B1 → B2 → B3 → B4 → B5 → B6, B1.5 parallel).

## Deliverables этой сессии (17 файлов)

### 00_Overview/ (3 файла)
- PRINCIPLES.md - 10 принципов (P1-P10) с full descriptions
- ROADMAP.md - все этапы Phase A/B/C/D + sprints B0-B6 + Q&A roadmap
- PRODUCT_BOUNDARIES.md - что входит/не входит, decision tree для sales

### 02_Data_Spec/ (5 файлов)
- DATA_REQUIREMENTS.md - master spec (proxy + recipient + validators)
- DSM_FIELDS.md - DSM Group fields detail + format adapters
- MEDIASCOPE_FIELDS.md - Mediascope TV/Digital + AdIndex
- RECIPIENT_ANCHORS.md - anchor form spec + UI hints
- recipient_anchors_v1.schema.json - JSON Schema SSoT

### 03_Architecture/ (5 файлов)
- REUSE_FROM_ECONOMETRICA.md - 80%+ reuse map
- TEST_STRATEGY.md - test pyramid + property-based + coverage targets
- UX_PRINCIPLES.md - premium UX (P10 implementation)
- DATA_PRIVACY.md - local-first + DPA + multi-tenant
- PERFORMANCE_BUDGETS.md - per-operation time limits

### 05_Sessions/ (2 файла)
- SESSION_001_concept_2026-05-04.md (этот файл)
- SESSION_NEXT_QUESTIONS.md - Q&A roadmap S002-S010

### Memory (2 файла)
- project_aurora_launch_principles.md - memory entry
- MEMORY.md update - index entry

## Next Actions

### Immediate (после этой сессии)

1. Антон ревьюит документы в `D:\Docs\Aurora_Ai\Aurora Launch\`
2. Decision на open questions:
   - OQ003: где будет git репо
   - OQ005: WASM commitment
   - OQ006: streaming MCMC commitment
3. **Schedule S003** (Proxy Similarity Framework) - до Sprint B2 start

### Phase A coordination

Phase A platform foundation prerequisites:
- Inference Core extraction в `aurora-platform-core` package
- Data Studio MVP с DSM/MS importers
- Tauri shell template
- cross_app_license framework
- schema_registry pattern

### Phase B kickoff

Когда Phase A complete + S003 + S007 done:
- Sprint B0.5 starts (BC test corpus + format adapters)
- Then B1, B1.5 (parallel), B2, B3, B4, B5, B6
- Total ~5-6 недель + parallel work

## Reflections (Маша)

Сессия удалась. Антон чёткий по решениям - быстро отвечает на вопросы, не размывает scope. Concept от vague идеи перешёл в operational principles + concrete data spec за один dialogue. Audit улучшил план существенно - 60+ findings без эхо-камеры.

Premium feel как explicit principle (P10) - правильное решение. Это то, что отличает Aurora от commodity tools. Implementation в Sprint B6 polish phase.

Local-first architecture (P14 в DATA_PRIVACY) - critical для multi-tenant scenario с конкурентами как клиентами. Решение элегантное: Aurora работает локально, у Антона нет access к raw data.

Pydantic v2 + JSON Schema как SSoT - чистое архитектурное решение. Reduces drift между Python backend и TypeScript frontend, ensures contract consistency.

Open questions (10) сосредоточены - пilot client + pricing finals + technical decisions (SQLite, WASM, streaming). Их финал нужен до соответствующих sprints, но не блокируют продолжение работы над shared platform layer (Phase A).

## Связанные документы

- Plan file (audit + delta): `C:\Users\ackol\.claude\plans\zippy-wobbling-waffle.md`
- Track file: `C:\Users\ackol\Desktop\zippy-wobbling-waffle-track.md`
- Memory: `~/.claude/projects/D--Docs-Aurora-Ai/memory/project_aurora_launch_principles.md`
- Project root: `D:\Docs\Aurora_Ai\Aurora Launch\`
