# Aurora Launch - UX Principles (Premium Feel)

**Status:** v1.0 (2026-05-04)
**Authority:** P10 в `00_Overview/PRINCIPLES.md` (Premium Feel)
**Source:** Critical audit findings A12, C1-C17

## Контекст

Aurora Launch pricing 1.5-3M/год требует **premium feel с первой секунды**. Иначе клиент думает "за 3M я могу нанять консультанта". Premium UX = differentiator vs commodity tools (Excel + Python) + trust signal vs enterprise alternatives (Nielsen / Kantar - дорогие но closed).

Этот документ - operational UX principles + concrete deliverables per Sprint.

---

## 1. UX Foundation Principles

### 1.1 Принцип "Workspace, не Utility"

**Rule:** при открытии Aurora Launch клиент видит **workspace** (активные launches, reminders, hours), не пустую form.

**Why:** workspace создаёт ощущение **continuous relationship**, что соответствует subscription model. Form = transactional, workspace = relational.

**Deliverable:** Dashboard "My Aurora" entry point (Sprint B6, audit C1):
- Активные launches (cards с превью forecast'а)
- Posterior update reminders (badges на cards)
- Consulting hours: "12 used / 30 total" widget
- Recent activity timeline (last 7 days)
- Quick actions: New Launch / Update Existing / From Template / Tutorials

### 1.2 Принцип "Visceral Feedback"

**Rule:** каждое действие пользователя получает **immediate visual response** (sub-100ms perceived latency).

**Why:** real-time feedback = premium tool. Slow lag = "это какая-то самописная штука".

**Deliverables:**
- WASM module для similarity calculator (audit B4) - real-time radar chart fill
- Svelte 5 runes + derived stores - reactive form validation
- Optimistic UI updates где applicable
- Skeleton screens вместо spinners (где loading > 200ms)

### 1.3 Принцип "Transparency by Default"

**Rule:** каждый chart / number / verdict имеет drill-down "Как это рассчитано?".

**Why:** premium product может объяснить себя. Black box = enterprise consulting (which we replace), transparency = our differentiator.

**Deliverable:** Methodology drill-down everywhere (Sprint B4-B6, audit C5):
- Click any number → modal с formula (LaTeX rendered)
- Click any chart → modal с data source + computation steps
- "Verify reproducibility" button - re-run check с same seed

### 1.4 Принцип "Reproducibility as Trust"

**Rule:** same inputs + same model version + same seed = identical outputs (always). Hash signatures на forecast'ах.

**Why:** клиент / CFO / regulator должны быть уверены что forecast не меняется случайно. Это base trust signal premium product.

**Deliverables:**
- Model card auto-gen (audit B10)
- Methodology Certificate PDF per forecast (audit C10)
- Hash-signed forecasts
- Versioning slider для projects (audit C7)

### 1.5 Принцип "Accountability via Audit Trail"

**Rule:** каждое значимое действие logged + visible. Sidebar timeline с event history.

**Why:** consulting hours model = continuous relationship. Антон / клиент должны иметь общую "историю" работы. Audit trail = premium accountability.

**Deliverable:** Event sourcing audit trail (Sprint B5, audit C8):
- Sidebar timeline с key events
- Filterable timeline (proxy changes, posterior updates, forecast generations)
- Export to CSV для quarterly review

---

## 2. Visual Design

### 2.1 Aurora Hybrid Design System

**Updated 2026-05-09 (Block 2 audit D2):** конфликт между tokens.json (SSOT 2026-04-24) и UX_PRINCIPLES старой версии resolved в пользу tokens.json. Все hex-значения ниже синхронизированы с `06_Aurora_Design_system/01_Tokens/tokens.json`.

**Color tokens** (read from `tokens.json` SSOT, ui.* palette для Tauri webview):

| Role | Token path | Hex |
|---|---|---|
| Background main | `color.ui.bg.main` | `#0f1117` |
| Background surface | `color.ui.bg.surface` | `#1a1d27` |
| Border subtle | `color.ui.bg.border` | `#2a2d37` |
| Text primary | `color.ui.text.primary` | `#EAEAF0` |
| Text secondary | `color.ui.text.secondary` | `#A8A8B8` |
| Text muted | `color.ui.text.muted` | `#7A7A90` |
| Accent primary (Aurora Launch) | `color.ui.accent.primary` | `#2E5BFF` |
| Accent secondary (sacred lime) | `color.ui.accent.secondary` | `#CCFF00` |
| Error | `color.semantic.danger` | `#EF4444` |
| Warning | `color.semantic.warning` | `#F59E0B` |
| Success | `color.semantic.success` | `#10B981` |
| Info | `color.semantic.info` | `#22D3EE` |

Light theme — derived через CSS custom properties с `[data-theme="light"]` overrides; tokens.json остаётся SSOT для dark, light = computed inverses where appropriate.

**Typography (UI stack per tokens.json):**
- UI headlines: `Noto Serif` (SIL OFL 1.1, bundled с installer)
- UI body: `Inter` (SIL OFL 1.1, bundled)
- Code/data: `JetBrains Mono` (SIL OFL 1.1, bundled)

**Spacing:** 4px base unit per tokens.json (`spacing.0`...`spacing.16`); CSS rem с `1rem = 16px`. Core scale: 4/8/12/16/24/32/48/64 px.

**Sacred Lime invariant:** `#CCFF00` (== `color.brand.sig.lime`, also bridged в `color.ui.accent.secondary`) — используется только для primary CTA action sigil + 2pt action title underline. Никогда не для decoration / hover / borders.

**Border radius:** 6px (small), 12px (medium), 20px (large/cards)

### 2.2 Theme support

- **Aurora Deep** (default, premium dark)
- **Light mode** (для accessibility / printing context)
- **Fun mode** (warm cream surfaces, как в Econometrica)

User can switch в Settings. Persist в local storage.

### 2.3 Iconography

- Lucide Icons (consistent с Econometrica)
- Aurora-specific glyphs (custom): Aurora wordmark mini, Tier badges (Gold/Silver/Bronze), Sacred Lime arrow, Posterior Update spiral

---

## 3. Animation & Micro-interactions

### 3.1 Forecast Cone Reveal (audit C4)

When forecast computed:
- Mean line draws first (left to right, 1s duration)
- 50% CI fills (0.5s)
- 80% CI (0.5s)
- 95% CI (0.5s)
- Total ~2.5s
- Subtle achievement chime (mute-able)
- Easing: ease-out (final CI fade-in последним)

Implementation: ECharts 5 с custom `setOption` sequence + CSS transitions.

### 3.2 Similarity Radar Fill (audit C3)

When similarity dimensions filled in form:
- Radar polygon fills smoothly с each field update
- Color gradient (Sacred Lime good → Red bad) by aggregate score
- Center number animates (count-up effect, 500ms)
- Tooltip on hover каждой axis с explainer

### 3.3 Tier Badge Reveal

When forecast verdict computed:
- Badge fades in с slight scale animation (300ms)
- Gold/Silver/Bronze ring rotates на 360° (medal-style)
- Sound chime (mute-able)

### 3.4 Subtle micro-interactions

- Hover на cards: subtle lift (translateY -2px + shadow expand)
- Button press: 0.95 scale flash (50ms)
- Successful save: green checkmark slide-in
- Error: red shake (200ms)
- Loading dots: pulsing 3-dot indicator

**Принцип:** все animations 100-500ms, easing ease-out, не блокируют interaction.

### 3.5 Sound design

**Subtle sounds (mute-able, off by default):**
- "Done" chime когда forecast ready (1s tone)
- "Notification" sound для posterior update reminders
- Configurable в Settings

**Sound library:** custom OGG Vorbis files в `assets/sounds/` (~30KB total - WAV→OGG ≈10× compression).

Source files (Lottie JSON for animations):
- `assets/animations/aurora_wordmark_intro.json` (~5KB)
- `assets/animations/forecast_cone_reveal.json` (computed via ECharts setOption sequence, no static file)
- `assets/animations/tier_badge_unveil.json` (~3KB Lottie)

---

## 4. Onboarding & Education

### 4.1 First-launch experience (Sprint B6, audit A13)

Welcome screen sequence:
1. Splash (Aurora wordmark animated)
2. "Привет! Я - Aurora Launch."
3. Feature pillars (3 cards): Proxy Selection / Recipient Anchoring / Posterior Update
4. CTAs: "Начать с template" / "Discovery call (Антон)" / "Skip - готов работать"

### 4.2 Product Tour (5 steps)

After first project creation:
- Step 1: ProxySelectionStep "Здесь выбирается прокси-бренд..."
- Step 2: RecipientAnchorsStep "Anchors калибруют magnitudes..."
- Step 3: TransferValidateStep "Проверка similarity и confidence..."
- Step 4: Forecast view "52-недельный прогноз с CI..."
- Step 5: Methodology drill-down "Каждое число объяснимо..."

Skippable, auto-saved progress, "Show again" в Settings.

### 4.3 Glossary modal

Accessible через "?" в any cabinet:
- 30+ terms: adstock, hill saturation, posterior update, similarity score, transfer learning, partial pooling, ESS, Gelman-Rubin, conformal prediction
- Each term: 1-2 sentence definition + "Learn more" link к methodology document

### 4.4 Templates Library (audit C14)

Pre-filled sample projects (Sprint B6):
- "FMCG Snacks Launch (template)"
- "OTC Pharma Launch (template)"
- "Premium Cosmetic Launch (template)"
- "Energy Drink Launch (template)"
- "Telecom Service Launch (template)"

User clones → fills with own data. Reduces blank-page anxiety.

### 4.5 Educational sidebar

В каждом cabinet - sidebar "Did you know?" с context-relevant tips:
- "Excess SoV theory: для роста SoV должна быть 1-3 п.п. выше market share"
- "Adstock decay показывает скорость затухания эффекта рекламы"
- "Similarity score 0.85+ = High confidence transfer"

---

## 5. Accessibility (WCAG AA target)

### 5.1 Color contrast

- Text on background: minimum 4.5:1 ratio (AA)
- Large text (18pt+): minimum 3:1
- Verified через automated tool (`tools/verify_aurora_html_a11y.py` - reuse from Econometrica)

**Aurora token contrast verification (2026-05-04):**

| Foreground | Background | Ratio | Status |
|---|---|---|---|
| #F5F5F5 text primary | #0A0F1F Aurora Deep | 17.4:1 | AAA |
| #A8B2D1 text secondary | #0A0F1F Aurora Deep | 8.7:1 | AAA |
| #BFFF00 Sacred Lime | #0A0F1F Aurora Deep | 13.1:1 | AAA |
| #3B82F6 Electric Blue | #0A0F1F Aurora Deep | 4.6:1 | AA |
| #FFD700 Gold | #0A0F1F Aurora Deep | 13.0:1 | AAA |
| #EF4444 Error | #0A0F1F Aurora Deep | 4.7:1 | AA |
| #F59E0B Warning | #0A0F1F Aurora Deep | 8.4:1 | AAA |
| #10B981 Success | #0A0F1F Aurora Deep | 5.2:1 | AA |

Все pairs pass WCAG AA. Sacred Lime + Gold pass AAA (premium contrast).

### 5.2 Keyboard navigation

- All interactive elements focusable
- Visible focus indicators (Sacred Lime ring)
- Tab order logical (top-to-bottom, left-to-right)
- Escape closes modals
- Enter triggers primary action

### 5.3 Screen reader support

- ARIA labels на all interactive elements
- Live regions для dynamic updates (validation feedback)
- Skip links ("Skip to main content")
- Semantic HTML5 (header, main, nav, etc.)

### 5.4 Motion preferences

- Respect `prefers-reduced-motion` media query
- Disable animations при reduced motion
- Sound off by default

### 5.5 Internationalization-ready

Phase B - Russian only. Phase D - i18n framework (для potential English market).

---

## 6. Empty States

### 6.1 No projects yet

```
[Aurora wordmark animated]

Готовы запустить новый продукт?
Начнём с прокси-бренда.

[Start from scratch]    [From template]    [Discovery call]
```

### 6.2 No proxy selected yet

```
[Outline silhouette of brand cards]

Найдите близкий прокси-бренд из вашей категории.
Это бренд с похожим размером, ценой, дистрибуцией.

[Browse my data]    [Need help? Talk to Антон]
```

### 6.3 No anchors filled

```
[Outline silhouette of form]

Заполните 7 ключевых параметров о вашем бренде.
Они откалибруют прогноз под ваш масштаб.

[Use template]    [Start filling]
```

### 6.4 Insufficient confidence

```
[Tier badge: Insufficient]

Текущий прокси не подходит для надёжного transfer'а.

Что можно сделать:
- Найти прокси с большим similarity (3 dimensions требуют улучшения)
- Запросить consulting session с Антон
- Уточнить recipient anchors
```

---

## 7. Power User Features

### 7.1 Ctrl+K Command Palette (audit C9)

Shortcut: **Ctrl+K** или **Ctrl+Shift+P** (VSCode-style alternate). Aurora Launch - Windows-only Phase B (см. PRINCIPLES Platform scope).

Opens quick action overlay:
- "Run forecast"
- "Add posterior data"
- "Switch proxy"
- "Open project [name]"
- "Search through projects"
- "Settings"
- "Help"

Keyboard navigation, fuzzy search, recent commands at top.

### 7.2 Keyboard shortcuts (Windows)

- `Ctrl+N` - New project
- `Ctrl+O` - Open project
- `Ctrl+S` - Save project
- `Ctrl+E` - Export report
- `Ctrl+,` - Settings
- `?` - Help / Glossary
- `Esc` - Close modal / cancel
- `Ctrl+/` - Show all shortcuts
- `Ctrl+K` / `Ctrl+Shift+P` - Command palette
- `F1` - Help (alternate)

### 7.3 Project history slider (audit C7)

In project view, slider shows project state at different times:
- "Forecast 2026-08-15 (initial)"
- "Forecast 2026-09-01 (after posterior update 4w)"
- "Forecast 2026-10-15 (after posterior update 12w)"
- Compare side-by-side (split view)

---

## 8. Real-time Streaming Visualization (audit B6)

### 8.1 MCMC training visualization

**Why:** train ~20s waiting time = teaching moment + premium feel.

**Implementation (Sprint B1+):**
- Server-Sent Events (SSE) или WebSocket из sidecar
- Live MCMC trace plots (parameters convergence)
- Gelman-Rubin diagnostic updates real-time
- ESS counter live
- Estimated time remaining

**UI элементы:**
- 4 trace plots (β, adstock, hill, baseline) рядом
- Convergence indicator: red → yellow → green
- "Bayesian inference - building probability distributions" caption
- Educational hover: "что такое MCMC?", "почему важна сходимость?"

### 8.2 Forecast streaming

**Why:** 52-week forecast generation - визуально appealing process.

**Implementation:**
- Stream forecast points week-by-week
- Cone gradually expands
- Confidence intervals fill progressively
- "Generating forecast for week 27 / 52..."

---

## 9. Notifications & Reminders

### 9.1 In-app notifications

- Posterior update reminder: "Прошло 4 недели после launch. Готовы добавить recipient data?"
- Consulting hours: "Использовано 25/30 часов. Renewal через 60 дней."
- Forecast version available: "Aurora Launch v1.4.1 обновляет methodology - re-run рекомендован"

### 9.2 Email notifications (optional, opt-in)

Phase C+:
- Posterior update reminders (monthly cadence)
- Quarterly review summary
- Major version updates announcements

### 9.3 Toast notifications

Brief in-app toasts:
- Save successful (1s, green)
- Forecast generated (2s, with action "Open report")
- Validation errors (4s, with action "Fix")

---

## 10. Performance Perception

### 10.1 Skeleton screens

Where loading > 200ms:
- Skeleton placeholders mimicking final layout
- Subtle shimmer animation
- No spinners (which feel slow)

### 10.2 Optimistic UI updates

- Form field changes save immediately (with rollback on error)
- Project list updates before backend confirms
- Comments appear immediately

### 10.3 Caching

- Recent forecasts cached locally (faster re-open)
- Similarity scores memoized
- API responses cached с invalidation rules

### 10.4 Progressive disclosure

- Show summary first, drill-down on demand
- Avoid overwhelming first-time users
- "Advanced settings" collapsed by default

---

## 11. Trust Signals (Visible)

### 11.1 Tier Badges (audit C11)

Olympic-style:
- **Tier-1 Confidence (Gold)** - similarity ≥ 0.85, all anchors filled
- **Tier-2 Confidence (Silver)** - similarity 0.65-0.85, anchors mostly filled
- **Tier-3 Confidence (Bronze)** - similarity 0.50-0.65, partial anchors
- **Insufficient (Grey)** - block forecast, suggest different proxy

Hover: explanation что значит badge.

### 11.2 Methodology Certificate PDF (audit C10)

Download per forecast - signed audit document:
- Aurora wordmark + version + hash signature
- Proxy used (brand, period, sources)
- Transfer dimensions matched + scores
- Training params, MCMC settings, posterior update history
- Validation metrics
- Confidence verdict
- Signature: SHA-256 of inputs + model + version

For client to show CFO / regulator.

### 11.3 Aurora seal на every report

Consistent branding across PPTX/HTML/XLSX/PDF:
- Aurora wordmark в header
- Version + hash в footer
- "Powered by Aurora Launch v1.4.0"

### 11.4 Public methodology documentation

Phase C+:
- Methodology document publicly accessible (auroraai.pro/methodology)
- Academic references (DOIs)
- Open-source mathematical components где возможно

---

## 12. Per-Sprint UX Deliverables

| Sprint | UX deliverables | A11y checks |
|---|---|---|
| B0 | UX_PRINCIPLES.md (this doc) + design system token review | Token contrast verified ✅ |
| B0.5 | Empty states for old project import flow | Empty states ARIA labels |
| B1 | Schema versioning UI (silent migration) + skeleton placeholder patterns | Skeleton ARIA-busy |
| B1.5 | Consulting hours widget design + tracker UI | Widget keyboard nav |
| B2 | ProxySelectionStep cabinet, similarity radar chart (live), tier badges | **A11y per cabinet:** ARIA, focus, contrast 4.5:1, keyboard nav |
| B3 | RecipientAnchorsStep с real-time validation, TransferValidateStep | **A11y per cabinet:** form errors aria-invalid + aria-describedby |
| B4 | Forecast cone animation, methodology certificate PDF, report polish | Charts: alt-text, screen reader summaries |
| B5 | Posterior update visualization (weight schedule), audit trail timeline | Timeline: aria-live для updates |
| B6 | Welcome experience, product tour, templates library, dashboard "My Aurora", **full a11y audit**, performance perception polish | Final WCAG AA audit + edge cases |

**A11y - design-time discipline, не sprint-end audit.** Каждый Sprint включает basic a11y checks для своих deliverables. Sprint B6 - comprehensive audit + edge cases.

---

## 13. UX Anti-patterns

### 13.1 НЕ делать spinners для long operations

❌ Spinner крутится 20s
✅ Streaming MCMC trace + educational caption

### 13.2 НЕ показывать sterile error messages

❌ "Error: ValidationError on field market_size_rub"
✅ "Размер рынка должен быть положительным числом. Например: 5,000,000,000 ₽."

### 13.3 НЕ требовать читать docs до старта

❌ "Read methodology before using"
✅ Templates + tour + glossary доступны но не блокируют start

### 13.4 НЕ скрывать confidence

❌ Показать прогноз без quality stamp
✅ Tier badge always visible, blocking при Insufficient

### 13.5 НЕ блокировать work спустя обновления

❌ Force update + reset state
✅ Background updates + opt-in apply

---

## Связанные документы

- `../00_Overview/PRINCIPLES.md` - P10 Premium Feel
- `../02_Data_Spec/RECIPIENT_ANCHORS.md` - form UI spec
- `TEST_STRATEGY.md` - a11y testing
- `PERFORMANCE_BUDGETS.md` - performance perception thresholds
- Memory: `feedback_econometrica_patterns.md` - reusable patterns from Econometrica
