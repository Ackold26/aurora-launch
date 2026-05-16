# MASTER AUDIT — Frontend Architecture / UX / A11y
**Aurora Launch Planner** · Branch `feat/stage1-core-1.1-1.4` · HEAD `21e693e`
**Date:** 2026-05-16 · **Auditors (roles):** Principal Product Designer + Senior UX Researcher + Frontend Architect + Product Strategist

---

## 1. Executive Summary

Aurora Launch Planner's frontend is well-structured for a v0.1.x product — Svelte 5 runes adoption is clean, the motion system (INV-14) is properly implemented, and i18n coverage is near-parity. The three **world-class moments** already present — Forecast Cone live streaming, Methodology Certificate, and Reproduce-in-Python — are genuinely differentiating features that no comparable Russian B2B analytics tool offers.

**Three critical issues that block world-class UX:**

1. **Wizard is a skeleton, not a product.** Steps 1 (import), 2 (mapping), 3 (proxy), 4 (anchors) contain placeholder button text in English, hardcoded demo data in `computeSimilarity()`, and zero validation logic. A pilot user reaching Step 2 sees "Apply mapping" with a single button and no column UI. This is a trust-destroying gap for a B2B tool.

2. **Focus management is dangerously incomplete across modals.** `HandshakeIncompatibleModal` has a focus trap (good), but the M-09 Reproduce modal has `tabindex="-1"` on the backdrop with no explicit focus redirect to the modal content on open. The feedback overlay in `+layout.svelte` has no `autofocus` directive and no focus trap at all. For NVDA users this means the modal announces itself but focus stays behind.

3. **Inspector tab keyboard navigation is incomplete.** The `tablist` uses `<button role="tab">` elements but there is no `aria-activedescendant` or Arrow key handler (`ArrowLeft`/`ArrowRight`). WCAG 2.1 §4.1.2 + ARIA Authoring Practices Guide for tabs require arrow-key navigation within the tablist. Keyboard-only users must Tab through each tab individually.

**Three things already done well:**
- prefers-reduced-motion: honored in every component via CSS media query + JS `prefersReducedMotion()` + zeroing `--motion-duration-*` tokens. INV-14 compliance is exemplary.
- i18n: RU/EN parity is near-complete (~240 keys each), Russian plural forms are correctly handled with MessageFormat `{count, plural, one {# неделя} few {# недели} many {# недель} other {# недели}}`.
- Motion service: `motion.ts` is a clean, SSR-safe, self-contained module with no external dependencies.

**5-Star Rating (pre-fix):**

| Dimension | Score |
|---|---|
| Architecture soundness | ★★★★☆ (4/5) |
| UX completeness | ★★☆☆☆ (2/5) |
| A11y maturity | ★★★☆☆ (3/5) |
| Design system consistency | ★★★☆☆ (3/5) |
| i18n / l10n | ★★★★☆ (4/5) |
| **Overall** | **★★★☆☆ (3/5)** |

---

## 2. Architecture Findings

| Sev | File | Finding | Impact | Fix Complexity |
|---|---|---|---|---|
| **Critical** | `routes/wizard/+page.svelte:148–182` | `computeSimilarity()` hardcodes 100% dummy data (`proxy_category_l1: 'FMCG'`, etc.) — this is the pilot path. No connection to the imported file or user-chosen proxy. | Similarity score on Step 3 is always the same regardless of user data. Pilot will see through this immediately. | Medium — wire `selectedProxy` and `importedFile` through to IPC call. |
| **Critical** | `routes/wizard/+page.svelte:261–267` | `startForecast()` generates `project_id: crypto.randomUUID()` fresh each call — no connection to the opened file or actual wizard state. The forecast has no project identity. | Bundle saved in Step 6 cannot be reopened and correlated with original data. | Medium — propagate project_id from import result or generate once per wizard session. |
| **High** | `routes/wizard/+page.svelte:401–416` | Steps 2 (mapping) and 4 (anchors) are single-button placeholders: `onclick={() => (mappingDone = true)}` / `onclick={() => (anchorsDone = true)}`. No column mapping UI, no anchor input fields. | Core workflow steps are non-functional for real data. | High — requires new UI components for column mapping table and anchor parameter form. |
| **High** | `routes/+layout.svelte:323–354` | Feedback overlay `role="dialog"` has no focus trap and no `autofocus` on textarea. After opening via Cmd+Shift+F, focus stays on whatever triggered the shortcut. | NVDA/keyboard: dialog announced but unreachable without Tab mashing. | Low — add `$effect(() => { if (feedbackOpen) textareaEl?.focus(); })` + Tab trap. |
| **High** | `routes/inspector/+page.svelte:598–672` | Reproduce modal: `tabindex="-1"` on backdrop, no `$effect` to focus modal content on open. `role="document"` on inner div is non-standard (should be none or just a div). | NVDA: Escape closes modal but initial focus is not moved inside. | Low — add `bind:this={modalRef}` + `$effect(() => { if (reproduceModalOpen) modalRef?.focus(); })`. |
| **High** | `routes/inspector/+page.svelte:394–406` | `role="tablist"` has no Arrow key handler. Tabs navigated by Tab key only, not ArrowLeft/ArrowRight as ARIA APG requires. No `id` attributes on tab buttons (only on panels), so `aria-controls` can point to panels but `aria-labelledby` cannot be set. | Keyboard/NVDA: tab navigation fails WCAG 2.1 SC 4.1.2. | Low — add `onkeydown` handler on tablist div. |
| **High** | `lib/components/ModeBadge.svelte:105–124` | Tooltip `role="tooltip"` is mounted as a Svelte `{#if}` block — it disappears from DOM when closed. This is correct for screen readers. BUT when `tooltipOpen=true`, there is no focus management: click opens tooltip but focus stays on the button. Keyboard user cannot Tab into the tooltip content to read warnings. | Expert users who want to read mode explanation via keyboard cannot navigate into tooltip. | Medium — tooltip pattern should be a `<dialog popover>` or use aria-live region for content announcement. |
| **Medium** | `routes/+layout.svelte:236–244` | `grid-template-rows: auto auto 1fr auto` assumes UpdateAvailableBanner renders in row 1 and RefreshAvailableBanner also in row 1 — but both are siblings, not stacked in different rows. When both banners are visible simultaneously (update available + opt-in prompt), they stack inside the same `auto` row, potentially overlapping the header or pushing it off screen. | Visual layout breakage when both banners active simultaneously. | Low — wrap both banners in a single `<div class="banner-zone">` with its own stacking, single auto row. |
| **Medium** | `lib/ipc/client.ts:311–316` | `saveBundleViaSidecar` calls `invoke('save_bundle', input as unknown as Record<string, unknown>)` — loses type safety with double cast. The same Rust command `save_bundle` is also called by `saveBundle(handleId, targetPath)` at line 249 with a different payload shape. Two incompatible call signatures to the same IPC command name. | Potential runtime error if Rust deserializer receives unexpected payload shape. | Medium — separate into `save_bundle` (simple overwrite) vs `save_bundle_with_extras` (sidecar path). |
| **Medium** | `lib/stores/bundle.ts` | `activeBundle` is a Svelte `writable` store (Svelte 4 style). All other new state in this session uses Svelte 5 `$state` runes. Mixed paradigm — Svelte 5's `$derived` and `$effect` do not automatically track `writable` store subscriptions in `<script lang="ts">` non-component files the same way. | Potential stale reads if bundle is opened from outside Svelte component context. | Medium — migrate to `$state` rune pattern in `.svelte.ts` file (like `projects.svelte.ts`). |
| **Medium** | `lib/components/ModeBadge.svelte:85` | `<svelte:window onkeydown={handleKeydown} />` installed inside ModeBadge — global Escape handler to close tooltip. If multiple ModeBadge instances are mounted, each registers its own window listener. | Multiple Escape handlers fired simultaneously — minor noise, potential conflict. | Low — use a single `onkeydown` on the wrapper div (`onkeydown` bubbles from tooltip content). |
| **Medium** | `routes/wizard/+page.svelte:379` | `in:fly={{ y: 12, duration: 220 }}` on `step-body` does not check `prefersReducedMotion()`. Uses Svelte built-in `fly` not the project's motion service. | Violates INV-14 for step transitions in wizard specifically. | Low — replace with `in:slideUp` from motion service, or wrap with `prefersReducedMotion()` guard. |
| **Low** | `routes/+layout.svelte:99–103` | `navigator.platform.toLowerCase()` is deprecated (MDN: will be removed). Should use `navigator.userAgentData.platform` with fallback. | Harmless now but will cause warnings in future Chromium/WebView2. | Low — `navigator.userAgentData?.platform ?? navigator.platform`. |
| **Low** | `routes/wizard/+page.svelte:519–533` | Last step (cert) footer shows "Готово" button that calls `pushToast({ level: 'success', title: $_('wizard.finish') })`. No navigation. User completes wizard and stays on same page with no indication of what to do next. | Dead end UX after wizard completion. | Low — `goto('/inspector')` or `goto('/')` after finishing. |
| **Low** | `lib/components/ForecastCone.svelte` | SVG has `role="img"` + `<title>` element for basic screen reader announcement. But there is no `<desc>` with data summary, and no accessible data table fallback. Screen reader users hear "Forecast cone (live streaming)" — nothing about the actual forecast values. | Blind users cannot access forecast data. | Medium — add `<desc>` with key statistics (min, max, mean, CI width) or a visually-hidden `<table>` summary. |
| **Cosmetic** | `lib/components/HandshakeIncompatibleModal.svelte:143` | `--accent-primary: #6366f1` hardcoded fallback in `.actions button.primary` style — different from project accent `#2E5BFF` (tokens.css `--color-ui-accent-primary`). | Two different blues in the app. | Cosmetic — change fallback to `var(--color-ui-accent-primary, #2E5BFF)`. |

---

## 3. UX Friction Map

### 3.1 Wizard Flow — Where Users Stumble

**Step 0 (Import):**
- Button label is English "Choose file" — not i18n-wrapped, hardcoded in template (`{#snippet children()}Choose file{/snippet}`). Jarring for Russian UI.
- After successful import, feedback is a toast with technical info (`Parsed via ${adapter_id}, ${n} records`). Manager-mode user does not know what "adapter_id" means. Copy should be humanized: "Файл подключён — обнаружено 48 строк данных".
- No progress indication during import — `importing` state shows `Button loading=true` but no description of what is happening.
- `PatternSuggestionCard` appears above the import card on Step 0. Pattern suggestions make no sense before data is imported. Non-sequitur.

**Step 1 (Mapping):**
- Complete placeholder. Single "Apply mapping" button with no UI. Pilot user expectation: column assignment table. Reality: one button that does nothing except advance state. This is the highest friction point after the pilot opens a real XLSX.

**Step 2 (Proxy):**
- "Pick proxy" button sets `selectedProxy = 'Demo Proxy'` — hardcoded string, no real proxy database browsing. No context on what a proxy brand is or how to find one.

**Step 3 (Similarity):**
- RadarChart axis labels are English machine strings from domain model: "Cat L1", "Cat L2", "Cat L3", "Pricing", "Size", "Distrib", "Media", "Lifecycle". Manager-mode user sees these abbreviations with no explanation.
- No forward reference: after computing similarity, user does not know why they did this or what happens next.

**Step 4 (Anchors):**
- Complete placeholder. "Set anchors ✓" is all that exists. Anchors are defined in `forecast.py` as: market_size, planned_share_trajectory, distribution_trajectory, pricing_index, elasticity, seasonality. None exposed in UI.

**Step 5 (Forecast):**
- "Start forecast" uses `variant="sigil"` (Sacred Lime) — strong visual CTA, correct.
- Forecast Cone animation is genuine delight moment — live streaming is excellent.
- BUT: no explanation of what the numbers mean during live streaming. First-time user watches values populate with no context.
- `forecastWarnings` captured but not shown to user during forecast step — only accessible in Inspector forecast tab later.

**Step 6 (Cert):**
- "Сохранить .aurora" appears only AFTER "Sign certificate". Cognitive disconnect: user signs something, then also has to manually save. Why isn't save automatic after signing?
- Save hint text is developer-internal: "Bundle позволит Inspector → M-09 «Воспроизвести в Python» работать с реальным forecast.json." No user should see M-09 references. This is internal task tracking leaked into UI.
- After successful save, `savedBundlePath` shows raw filesystem path in `<code>`. Nice for developers, cold for managers.
- "Готово" button fires a toast and does nothing else. User is stranded.

### 3.2 Inspector — Five-Tab Information Architecture

**Tab discoverability:** Five tabs rendered as plain `<button>` elements with `color: var(--text-muted)`. No visual affordance that they are tabs vs buttons. No icon, no badge indicators for tabs with data (e.g., a "✓" on cert tab when verified, a warning badge on forecast tab when warnings present).

**Empty state when no bundle:** Shows `$_('audit.empty')` key which resolves to "История пока пуста — выполните любую операцию, чтобы начать запись". This is the history page copy, not inspector copy. Copy mismatch.

**Metadata tab:** Renders technical fields (UUID, SHA-256, revision number) without business context. Manager asking "when was this project created?" must parse ISO timestamp. No friendly date formatting (no `Intl.DateTimeFormat`).

**Similarity tab — empty state:** "No similarity entry в bundle (workflow not yet computed)" — mix of Russian and English in UI text. Grammatically broken in both languages.

**Forecast tab — information density:** ForecastCone + ModeBadge + TrustScore + AI explanation (3 paragraphs) + Reproduce CTA = significant scroll. No visual hierarchy separating "what happened" (cone) from "should I trust it" (trust score) from "what does it mean" (AI explanation).

**Audit tab:** "Per-bundle audit trail entries (Block 4 wires real audit log read)" — developer comment in production UI. This entire panel shows a stub text with internal roadmap reference.

**M-09 Reproduce modal — title:** "🐍 Воспроизвести прогноз в Python" — emoji in heading is fine stylistically but aria-level escalation: `<h2>` inside a modal that is already labeled by `aria-labelledby`. NVDA reads "🐍 Воспроизвести прогноз в Python heading level 2" — the snake emoji text pronunciation varies by NVDA version.

### 3.3 Onboarding — First-Run Experience

**Phase sequence is correct** (animation → category → tutorial → app) but the animation-to-category transition has no loading state if `WelcomeAnimation` fires `oncomplete` before category CSS is painted (300ms race on slow machines).

**CategorySelector** — imported but not audited for a11y separately. If it uses icon-only buttons for category choices, keyboard users need visible labels.

**TutorialCarousel — slide 4 content:** "Один клик — три сценария: пессимистичный, базовый, оптимистичный. Эксперт-режим разворачивает 6 параметров чувствительности." This references a UI feature (sensitivity scenarios) that is implemented in `SensitivityScenarios.svelte` but is NOT accessible from the wizard flow or welcome page in this session's work. If onboarding promises 3-click scenarios, there must be a path to that feature.

**Slide icons** are emoji (🎯, 📊, 📈, 🎛, 🔐) — fine visually but some screen readers announce emoji names. "Bullseye" → "Chart increasing" → "Control knobs" — not all intuitive in audio form. `aria-hidden="true"` is correctly applied.

**Skip button discoverability:** Very small, secondary color, upper-right corner. First-time users who feel overwhelmed by the tutorial need it but may not find it. Apple's convention: skip is center-bottom, not upper-right.

### 3.4 Settings — Information Architecture Degradation

The settings page has grown from 3 sections (theme, locale, telemetry) to 5 (+ auto-refresh + about). This is becoming a configuration dumping ground. Observations:

- "Автообновление прогнозов" card appears between "Анонимная диагностика" and "About" — there is no information architecture grouping (privacy vs. data management vs. system). When more settings are added (Phase 2+), this will become unmanageable.
- The telemetry and auto-refresh toggles look identical (same `<label class="switch">` pattern). User must read the label carefully to distinguish them.
- "About" card title is hardcoded English "About" — not i18n-wrapped.

### 3.5 History Page — Two Different Histories

The `/history` route shows global audit log + telemetry events + pending feedback. The `/project/[uuid]/history` route (ForecastHistory component) shows project-specific forecast versions. These are two different concepts with the same nav label "История". Users who want to see their forecast versions navigate to "История" and land on the system audit log. The forecast version history is buried in a project-specific deep link that has no nav entry.

---

## 4. Magical Moments Analysis

### Already Present (Genuine Delight)

| Moment | Quality | Notes |
|---|---|---|
| Forecast Cone live streaming | ★★★★★ | Real-time SVG rendering as backend events stream is technically impressive and visually distinctive. |
| Methodology Certificate + Ed25519 | ★★★★☆ | Strong trust signal. `verify.auroraai.pro` reference in onboarding slide 5 is powerful. |
| Reproduce-in-Python (M-09) | ★★★★☆ | Genuinely unique in the Russian market. Auditable forecast reproducibility is a defensible moat. |
| TrustScore circle widget | ★★★☆☆ | Good visual — "score out of 100" is accessible to non-statisticians. |
| ModeBadge honest disclosure | ★★★☆☆ | Correct transparency. "OLS + Priors (упрощённый)" with fallback warning builds trust. |

### Missing for World-Class Wow

1. **Forecast summary "headline number":** After forecast completes, there should be a prominently styled hero number — e.g., "Прогноз: 2.4M продаж за 26 недель" — before the technical cone visualization. Managers want the headline, then details.

2. **Wizard progress bar with time estimate:** The ProgressBar component exists but is only used in Step 5. Steps 1–4 have no sense of "how long until I get to the forecast." An estimated "5 minutes to your first forecast" at the top of Step 0 would set correct expectations.

3. **Post-save share action:** After "Bundle сохранён" in Step 6, there should be a "Отправить коллеге" action — copy a share link or email with the path. Currently the flow dead-ends at a path string.

4. **Inspector tour / contextual onboarding:** First time opening Inspector, there should be a coach mark on the most powerful tab (Forecast) and on the Reproduce button. Users don't know M-09 exists unless they scroll.

5. **Comparison view as a magic moment:** `/compare` route exists in nav but is sparsely implemented. Side-by-side forecast comparison is a potential "wow" moment that could be the hero feature of the Inspector.

6. **"Why this proxy?" explanation:** After proxy selection (Step 2) and similarity computation (Step 3), there is no narrative explanation of why this proxy was chosen. An AI-generated one-sentence "Кагоцел выбран как прокси, потому что..." would be a delight moment before the technical radar chart.

---

## 5. Accessibility Maturity

### A11y Scoring (NVDA RU + Keyboard + Screen-Reader-Only)

| Area | Status | Finding |
|---|---|---|
| Focus management — HandshakeIncompatibleModal | ✅ Pass | `$effect` auto-focus on `reloadButton`, Tab trap implemented. |
| Focus management — UpdateAvailableBanner | ⚠️ Partial | `role="status"` + `aria-live="polite"` will announce banner text. No focus shift. Acceptable for non-blocking banners. |
| Focus management — RefreshAvailableBanner | ⚠️ Partial | Same pattern as UpdateAvailableBanner. Opt-in dialog is non-blocking, aria-live sufficient. |
| Focus management — Feedback overlay | ❌ Fail | No autofocus, no focus trap. `role="dialog" aria-modal="true"` without focus trap is a WCAG 2.1 SC 2.1.2 violation. |
| Focus management — Reproduce modal | ❌ Fail | No autofocus on modal open. Content has `role="document"` which is incorrect and redundant. |
| Inspector tablist Arrow keys | ❌ Fail | WCAG 2.1 SC 4.1.2 + ARIA APG tabs pattern: requires ArrowLeft/ArrowRight for tab navigation. |
| Wizard stepper aria-current | ✅ Pass | `aria-current={i === step ? 'step' : undefined}` correctly implemented. |
| ForecastCone data access | ❌ Fail | SVG `<title>` present but no `<desc>` with numeric data, no accessible table fallback. Blind users cannot access forecast values. |
| WCAG AA color contrast — dark theme | ✅ Pass | tokens.css dark theme: text-primary `#EAEAF0` on bg-main `#0f1117` = ~14:1 (AAA). |
| WCAG AA color contrast — light theme | ✅ Pass | overrides.css PA-A06 fix applied: color-success `#047857` (4.97:1), color-danger `#B91C1C` (5.94:1). |
| High-contrast theme | ⚠️ Partial | `[data-theme="high-contrast"]` sets `--accent: #00FFFF`. Cyan on `#0F0F0F` = ~20:1 (AAA). BUT no validation that all components that render custom colors (ForecastCone SVG inline styles, ModeBadge hardcoded fallbacks) also respect high-contrast theme tokens. |
| lang attribute | ❌ Fail | No `lang="ru"` or `lang="en"` on `<html>` element found in layout. NVDA uses language attribute to select pronunciation engine. Russian text read with English engine = unintelligible. |
| Spinner in Button | ⚠️ Partial | `<span class="spinner" aria-hidden="true">` is hidden from SR. But `aria-busy={loading}` on the `<button>` element correctly announces "busy" state. Acceptable. |
| Keyboard shortcut hint `<kbd>` in footer | ✅ Pass | `<kbd>Ctrl+K</kbd>` is semantically correct. Screen reader announces "Ctrl K keyboard shortcut". |
| EmptyState `role="status" aria-live="polite"` | ⚠️ Partial | Correct role. But `aria-label={title}` on `role="status"` region creates redundancy — SR announces the label and then reads the child content. Remove `aria-label` from the `<section>` or change to a less aggressive role. |
| prefers-reduced-motion — Wizard fly transition | ❌ Fail | `in:fly={{ y: 12, duration: 220 }}` uses Svelte built-in `fly`, not the project's motion service. Not guarded by `prefersReducedMotion()`. Only CSS `@media` in tokens.css zeroes duration vars, but `fly` transition has its own `duration` parameter that ignores CSS variables. |
| Modal close on Escape | ✅ Pass | Feedback overlay: `if (e.key === 'Escape' && feedbackOpen) feedbackOpen = false` in layout. Reproduce modal: `onkeydown` handler on backdrop. ModeBadge tooltip: `$window onkeydown` handler. |
| Button focus-visible styles | ⚠️ Partial | Button.svelte has no explicit `:focus-visible` CSS override. Relies on browser default outline. WCAG 2.2 SC 2.4.11 (Focus Appearance Enhanced — AA requirement) requires minimum 2px outline with 3:1 contrast against adjacent colors. Browser default on dark background may not meet this. |
| Drag movements (WCAG 2.2 SC 2.5.7) | ✅ Pass | No drag interactions in the app. N/A. |
| Russian-specific ё/е normalization in search | N/A | CommandPalette search uses label string matching. No normalization needed as labels are controlled strings. |

### Critical A11y Fixes Needed (Priority Order)

1. Add `lang` attribute to HTML root (missing entirely — highest priority).
2. Add focus trap + autofocus to feedback overlay in `+layout.svelte`.
3. Add autofocus to Reproduce modal content on open.
4. Add Arrow key navigation to Inspector tablist.
5. Add accessible data summary to ForecastCone SVG (`<desc>` or hidden table).
6. Guard wizard `in:fly` with `prefersReducedMotion()`.
7. Add `:focus-visible` explicit styles to Button component (2px, 3:1 ratio).

---

## 6. Design System Inconsistencies

### 6.1 Token Usage

| Issue | Location | Finding |
|---|---|---|
| Two motion token systems | `tokens.css` + `overrides.css` | `tokens.css` defines `--motion-fast: 150ms`, `--motion-default: 200ms`, `--easing-spring`. `overrides.css` defines `--motion-duration-fast: 80ms`, `--motion-duration-normal: 160ms`, `--motion-easing-spring-soft`. Both sets are used in different components. `Button.svelte` uses `var(--motion-fast)`. `TutorialCarousel` uses `var(--motion-duration-fast)`. These resolve to different values (150ms vs 80ms) — motion is inconsistent across components. |
| Hardcoded fallback colors | `HandshakeIncompatibleModal.svelte:171` | `var(--accent-primary, #6366f1)` — `#6366f1` (indigo) vs project accent `#2E5BFF` (blue). |
| Hardcoded `rgba(0, 0, 0, 0.5)` | `inspector/+page.svelte:775` | Reproduce modal backdrop: `rgba(0,0,0,0.5)` instead of `color-mix(in srgb, var(--bg-main) 70%, transparent)` (pattern used in feedback overlay). |
| `font-size: 0.85rem` | `inspector/+page.svelte:857`, `inspector/+page.svelte:946` | Magic number not referencing any token. Should be `var(--typography-fontSize-ui-sm)` (0.875rem) or `var(--typography-fontSize-ui-xs)` (0.75rem). |
| `font-size: 0.85em` in History | `history/+page.svelte:162` | Same pattern — `.target` uses `0.85em` magic number. |
| `border-radius: 8px` vs token | `inspector/+page.svelte:788` | Hardcoded `8px` instead of `var(--border-radius-lg)`. |
| `--shadow-sm` / `--shadow-md` / `--shadow-glow` | Multiple files | These tokens are referenced throughout (`Card.svelte`, `Button.svelte`, `TrustScore.svelte`) but are NOT defined in either `tokens.css` or `overrides.css`. They will resolve to `initial` (invisible/no shadow). |

### 6.2 Component Pattern Divergence

| Pattern | Issue |
|---|---|
| Button variants in EmptyState | `EmptyState.svelte` defines its own inline `.btn` / `.btn-primary` / `.btn-secondary` styles instead of using `Button.svelte`. Hover states differ: EmptyState primary has `translateY(-1px) + shadow-glow`, while `Button.svelte` primary has the same. But ghost/secondary handling differs. Two sources of truth for button appearance. |
| Inline `<button>` styles in `+layout.svelte` | `.save-btn` in layout is a custom button (not `Button.svelte`), with its own padding/radius/color that differs from btn-primary. |
| Progress bar vs ProgressBar component | `UpdateAvailableBanner` has its own inline progress bar CSS. `ProgressBar.svelte` is a separate component. No reuse. |
| Modal backdrop pattern | Feedback overlay uses `backdrop-filter: blur(8px)`. Reproduce modal uses plain `rgba(0,0,0,0.5)`. HandshakeIncompatibleModal uses `rgba(0,0,0,0.7)`. Three different backdrop treatments. |
| Banner component styles | UpdateAvailableBanner and RefreshAvailableBanner have separate but near-identical CSS for `.{x}-banner`, `.{x}-banner__content`, `.{x}-banner__btn--primary`, etc. DRY violation — a `Banner.svelte` base component could reduce ~150 lines of CSS duplication. |

### 6.3 Missing `--shadow-*` Tokens

The following shadow tokens are referenced but undefined:

- `--shadow-sm` (Card.svelte, TrustScore.svelte)
- `--shadow-md` (Card.svelte hover)
- `--shadow-lg` (feedback-card in layout)
- `--shadow-glow` (Button.svelte, EmptyState.svelte)

All will silently fall back to no shadow. This is a functional bug on production (no shadow = no depth/elevation system).

---

## 7. Internationalization / Localization Gaps

### 7.1 Hardcoded Strings (Not i18n-Wrapped)

| Location | String | Severity |
|---|---|---|
| `wizard/+page.svelte:388` | `"Choose file"` (Button text) | High |
| `wizard/+page.svelte:393` | `"Parsed via ${adapter_id}"` (toast title) | High |
| `wizard/+page.svelte:394` | `"${n} records detected"` (toast body) | High |
| `wizard/+page.svelte:406` | `"Done ✓"` / `"Apply mapping"` | High |
| `wizard/+page.svelte:412` | `"Pick proxy"` | High |
| `wizard/+page.svelte:422` | `"Compute"` (similarity) | Medium |
| `wizard/+page.svelte:439` | `"Set anchors"` / `"Anchors set ✓"` | Medium |
| `wizard/+page.svelte:450` | `"Start forecast"` | Medium |
| `wizard/+page.svelte:483` | `"Sign certificate"` | Medium |
| `wizard/+page.svelte:487` | `"✓ Сертификат подписан (dev режим — local key)"` | Low (dev message) |
| `wizard/+page.svelte:499` | `"Сохранить .aurora"` | Medium |
| `wizard/+page.svelte:502–504` | Save hint referencing M-09 | High (internal leak) |
| `inspector/+page.svelte:464` | `"Aggregate score: X%"` | Medium |
| `inspector/+page.svelte:467` | `"No similarity entry в bundle (workflow not yet computed)."` | High (mixed language) |
| `inspector/+page.svelte:508–511` | `"💡 Что значит этот прогноз"` (hardcoded) | Medium |
| `inspector/+page.svelte:561` | `"No forecast entry в bundle (workflow not yet completed)."` | High |
| `inspector/+page.svelte:578` | `"Open this tab to verify bundle signature."` | High (English in RU app) |
| `inspector/+page.svelte:589–590` | `"Per-bundle audit trail entries (Block 4 wires real audit log read)."` | Critical (internal note) |
| `history/+page.svelte:43` | `"Audit log"` (Card title) | Medium |
| `history/+page.svelte:74` | `"Telemetry events (local-only buffer)"` (Card title) | Medium |
| `history/+page.svelte:108` | `"Pending feedback (Cmd+Shift+F)"` (Card title) | Medium |
| `settings/+page.svelte:182` | `"About"` (Card title) | Low |
| `settings/+page.svelte:198` | `"Rust"` (dl label) | Low |
| `+layout.svelte:229–231` | `"Feedback capture failed"` (toast title) | Medium |
| `+layout.svelte:351` | `"Cmd+Shift+F · Esc to close"` (feedback hint) | Medium |
| `+page.svelte:64` | Welcome card body text (3 Russian strings) | Medium (missing from JSON) |

### 7.2 EN Locale Missing Keys

The following keys exist in `ru.json` but are absent from `en.json`:

- None found — the two files have near-identical key sets. This is good.

### 7.3 Missing Keys in Both Locales

Keys referenced in template that have no JSON entry:

- Wizard inline strings (entire wizard step body text is not in locales)
- Inspector inline mixed-language strings

### 7.4 Date/Time Formatting

`history/+page.svelte:35` uses `new Date(ts).toLocaleString()` — uses browser locale, which is correct. However, `inspector/+page.svelte` metadata tab renders `$manifestSummary.created_at` and `$manifestSummary.last_modified` as raw ISO strings without any formatting. Should use `Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' })`.

---

## 8. Specific Risks of This Session's Work

### 8.1 Wizard Save (1.3d) — Step 6

- **Risk:** `savedBundlePath` success state shows raw filesystem path to user. On Windows: `C:\Users\username\AppData\Roaming\...`. This is developer-friendly, not user-friendly.
- **Risk:** "Sign certificate" + "Сохранить .aurora" are two sequential manual steps that logically should be one. Cognitive overhead without clear benefit for the user (the cert is what makes the bundle trustworthy — they should be atomic).
- **Risk:** `saveBundle()` uses `save` dialog AFTER forecast completes. If user switches tabs or minimizes the app during the long forecast, they return to a completed forecast with no save prompt and may close the window, losing everything. Auto-save to temp location + offer "Save As" is safer.

### 8.2 Inspector Reproduce (1.4)

- **Risk:** `reproduceScript` displayed in `<pre tabindex=0>` with `role="region"`. `role="region"` requires an accessible name — it has `aria-label="Сгенерированный Python-скрипт"`. This is correct. But `role="document"` on the modal content div is wrong — `role="document"` is for embedded documents inside an `application` context (e.g., iframes). Remove `role="document"`.
- **Risk:** Download link `<a href="data:text/x-python;charset=utf-8,..." download>` uses `role="button"`. This is incorrect — the element is a native `<a>` with `href` and `download`, which has `role="link"`, not `role="button"`. Using `role="button"` overrides the native link semantics and means keyboard Enter key (native link) works but Space key (button convention) does not.
- **Risk:** Emoji in modal title `"🐍 Воспроизвести прогноз в Python"` — NVDA will read "snake emoji". Use `aria-hidden` span for the emoji as done elsewhere: `<span aria-hidden="true">🐍</span>`.

### 8.3 HandshakeIncompatibleModal (2.8)

- **Risk:** During handshake wait (before `result !== null`), the app renders normally with no "connecting..." skeleton. If handshake takes >500ms (slow machine, cold start), user may begin interacting with the app before the sidecar is ready. Add a loading skeleton or `aria-busy` state to the main content during handshake pending.
- **Risk:** Focus trap uses `trapFocus` that catches ALL Tab presses and returns to `reloadButton`. If the user has navigated using Tab into the modal's `<p>` texts (which are not focusable), the handler fires on the backdrop's `onkeydown`. This is correct behavior but the backdrop must be focused first (it has `tabindex="-1"`). If the backdrop itself doesn't have focus, keyboard events on it won't fire. The modal may not trap reliably in all SR+keyboard combinations.

### 8.4 UpdateAvailableBanner (2.9)

- **Risk:** "Скачать и установить" triggers immediate download with no confirmation, no changelog preview, no size indication. Enterprise B2B users may be in the middle of an important analysis when the update banner appears. The pattern should be: click "Узнать, что нового" → changelog sheet → then "Установить".
- **Risk:** The `dismissedThisSession` flag is a `$state` variable that resets on page reload. But `bannerState` being `'error'` also sets `dismissedThisSession = false` in the 4-hour re-check interval code. If update check fails permanently (no network), the error banner appears and dismisses, then reappears every 4 hours. For an offline B2B scenario this is disruptive.

### 8.5 RefreshAvailableBanner (3.5)

- **Risk:** The opt-in dialog is the FIRST thing shown on startup to a first-time user whose consent is `null`. This means: new user opens app → onboarding redirect fires → user goes through onboarding → returns to `/` → RefreshAvailableBanner immediately shows the consent dialog. The sequence competes with the welcome screen, creating two simultaneous first-run experiences.
- **Risk:** Legal text "152-ФЗ" appears in `refresh.settings.detail` and `refresh.optin.detail`. This creates an intimidating tone — "data law compliance notice" as first interaction. The emotional register should be benefit-first: "Экономьте время — Aurora сама заметит новые данные" → with the 152-ФЗ detail available via expandable "Подробнее о защите данных".
- **Risk:** `handleRefreshNow()` dispatches `window.CustomEvent('aurora:refresh-forecast')` but no component in the frontend subscribes to this event. It is fired into the void. The refresh trigger is dismissed, but no actual forecast refresh is initiated.

### 8.6 Budget Optimizer (4.4)

- IPC types added (`BudgetOptimizerInput`, `BudgetResult` presumably in client.ts or types) and Python sidecar handlers implemented — but there is zero UI surface. The customer cannot access this feature. If pilot clients are shown this in a demo, it needs at minimum a "coming soon" placeholder in the wizard anchors step or settings.

---

## 9. Top-10 Quick Wins (Effort: S = 1-4h, Impact: M+)

| # | Change | Effort | Impact | File |
|---|---|---|---|---|
| QW-1 | Add `lang="ru"` (or dynamic locale) to `<html>` in `app.css` root or layout. Most impactful a11y fix. | S (30min) | Critical | `app.css` / `+layout.svelte` |
| QW-2 | Add `--shadow-sm`, `--shadow-md`, `--shadow-lg`, `--shadow-glow` to `overrides.css`. Currently all shadows are invisible. | S (1h) | High | `overrides.css` |
| QW-3 | Add autofocus + focus trap to feedback overlay in `+layout.svelte`. | S (1h) | High | `+layout.svelte:323` |
| QW-4 | Add ArrowLeft/ArrowRight keyboard handler to Inspector tablist. | S (1h) | High | `inspector/+page.svelte:394` |
| QW-5 | Replace hardcoded `"Choose file"` / `"Apply mapping"` / `"Compute"` / `"Start forecast"` in wizard with i18n keys. | S (2h) | High | `wizard/+page.svelte` |
| QW-6 | Replace internal developer note in Inspector audit tab with user-friendly "Журнал аудита появится здесь" EmptyState. | S (30min) | High | `inspector/+page.svelte:589` |
| QW-7 | Fix mixed RU/EN strings: "No similarity entry в bundle", "No forecast entry в bundle", "Open this tab to verify bundle signature." | S (1h) | High | `inspector/+page.svelte:467,561,578` |
| QW-8 | Remove `role="button"` from `<a>` download link in reproduce modal; remove `role="document"` from modal content div. | S (30min) | Medium | `inspector/+page.svelte:647,615` |
| QW-9 | Guard wizard `in:fly` transition with `prefersReducedMotion()` from motion service. | S (30min) | Medium | `wizard/+page.svelte:379` |
| QW-10 | Add `goto('/inspector')` after wizard "Готово" button click (or navigate to relevant page). Current: fires toast and stays. | S (30min) | Medium | `wizard/+page.svelte:530` |

---

## 10. Top-10 Strategic Improvements (Delightful UX, Emotional Design, Predictive Behavior)

| # | Improvement | Rationale |
|---|---|---|
| S-1 | **Forecast headline number before the cone.** After forecast completes, show a prominent hero stat: "Прогноз: 2.4M за 26 недель · Доверие 78%". Managers present this to stakeholders — they need the bottom line first. Implement as a `ForecastSummaryHero` component placed above `ForecastCone`. | This is the most shared moment of the product. Make it screenshot-worthy. |
| S-2 | **Auto-save to temp + "Save As" prompt.** Instead of requiring manual "Сохранить .aurora" on cert step, auto-save to `%TEMP%/aurora-launch/session-{uuid}.aurora` after forecast completes. Show banner "Прогноз сохранён временно". Offer "Сохранить постоянно" in inspector. | Eliminates the most likely data loss scenario (close window after long forecast). |
| S-3 | **Column mapping UI for Step 2.** Implement a table showing detected columns on left, canonical fields on right, with `<select>` dropdowns. Pre-populate with adapter-detected mapping. This is the minimum viable Step 2. | Without this, pilot clients cannot use real data. |
| S-4 | **Proxy search UI for Step 3.** Instead of "Pick proxy" button → hardcoded "Demo Proxy", implement a searchable list of proxy brands from the sidecar `list_adapters` or a proxy catalog endpoint. Even a 10-item static list with fuzzy search is better than a placeholder. | Core methodology step has zero UI. |
| S-5 | **Anchor parameter form for Step 4.** Minimal viable: 4 numeric inputs with tooltips (market_size, pricing_index, distribution_velocity, creative_quality). Tie to the `spend_plan` passed to `saveBundle`. | Without anchors, the saved bundle always uses null anchors → M-09 always in preview mode. |
| S-6 | **Inspector coach mark on first visit.** On first time Inspector opens with a bundle, show a guided tooltip pointing to the Forecast tab: "Здесь живёт ваш прогноз". Then on Forecast tab, highlight the Reproduce button with "Узнайте, как это воспроизвести". Use `localStorage` to show once. | Discoverability of M-09 and TrustScore is currently zero without reading docs. |
| S-7 | **Refresh banner: benefit-first copy rewrite.** Change opt-in dialog from legal-first to benefit-first: "Хотите, чтобы Aurora сама замечала новые данные? Мы проверяем только локальные папки — в интернет ничего не уходит." Move "152-ФЗ" to a small `<details>` element. | Current cold legal tone discourages opt-in. Opt-in = more data refresh = more engagement. |
| S-8 | **Accessible ForecastCone data table.** Add a visually hidden `<table>` with 5–6 key forecast weeks (W1, W5, W13, W26, max, min) below the SVG. Aria-label "Данные прогноза". Screen reader users get the numbers, sighted users see the visual. | Opens product to visually impaired analysts. Mandatory for any serious enterprise B2B. |
| S-9 | **Dual nav entry for history.** Rename current `/history` (system audit) to `/activity` in nav. Make `/history` point to the `ForecastHistory` component (forecast version timeline). The current UX sends users looking for forecast history to the wrong page. | The most common user intent for "История" is "see past forecasts", not "see system audit log". |
| S-10 | **Update banner: "What's new" side sheet before install.** When "Скачать и установить" is clicked, first show a modal/sheet with the release notes (`updateInfo.body`) and total download size. Confirm → then download. | Enterprise users are cautious about auto-updates during active sessions. Trust-building before destructive action. |

---

## Appendix: Files Audited

- `frontend/src/routes/+layout.svelte`
- `frontend/src/routes/+page.svelte`
- `frontend/src/routes/wizard/+page.svelte`
- `frontend/src/routes/inspector/+page.svelte`
- `frontend/src/routes/onboarding/+page.svelte`
- `frontend/src/routes/settings/+page.svelte`
- `frontend/src/routes/history/+page.svelte`
- `frontend/src/lib/components/HandshakeIncompatibleModal.svelte`
- `frontend/src/lib/components/UpdateAvailableBanner.svelte`
- `frontend/src/lib/components/RefreshAvailableBanner.svelte`
- `frontend/src/lib/components/ForecastCone.svelte`
- `frontend/src/lib/components/TrustScore.svelte`
- `frontend/src/lib/components/ModeBadge.svelte`
- `frontend/src/lib/components/EmptyState.svelte`
- `frontend/src/lib/components/Button.svelte`
- `frontend/src/lib/components/Card.svelte`
- `frontend/src/lib/components/Onboarding/TutorialCarousel.svelte`
- `frontend/src/lib/ipc/client.ts`
- `frontend/src/lib/stores/bundle.ts`
- `frontend/src/lib/services/motion.ts`
- `frontend/src/lib/i18n/locales/ru.json`
- `frontend/src/lib/i18n/locales/en.json`
- `frontend/src/lib/styles/tokens.css`
- `frontend/src/lib/styles/overrides.css`
