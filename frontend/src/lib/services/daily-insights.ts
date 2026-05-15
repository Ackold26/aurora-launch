/**
 * Phase Magic M-07: Daily insight generation service.
 *
 * Heuristic-driven insights surfaced as in-app banner on home page.
 * Local-first (no backend, no OS notification permission dance for v0.1.0).
 *
 * Algorithm:
 * 1. Load projects from ProjectsStore (caller ensures refresh).
 * 2. Score each candidate insight by priority.
 * 3. Return highest-priority insight OR null.
 *
 * Suppression:
 *   localStorage 'aurora.last-insight-shown' стores ISO date YYYY-MM-DD.
 *   shouldShowInsight() returns false если уже показывали сегодня.
 *
 * Why in-app banner vs. OS notification: avoids OS permission dance,
 * works offline, user always sees Aurora-controlled UX без external mediator.
 * Real OS notifications могут быть добавлены в Phase Cloud / X-04 telemetry.
 */

import type { ProjectSummary } from '$ipc/projects';

export type InsightSeverity = 'info' | 'warning' | 'success';

export interface DailyInsight {
  id: string;
  severity: InsightSeverity;
  title: string;
  body: string;
  /** Action label, e.g. «Обновить прогноз» */
  cta?: string;
  /** Optional route к которому ведёт CTA */
  ctaHref?: string;
  /** Optional project context */
  projectUuid?: string;
}

const SUPPRESS_KEY = 'aurora.last-insight-shown';
const STALE_FORECAST_DAYS = 14;
const VERY_STALE_FORECAST_DAYS = 30;
const ONBOARDED_KEY = 'aurora.onboarded';

/** Today's date as YYYY-MM-DD в local timezone. */
function todayIsoDate(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

/** Days между two ISO timestamps (or null если parse fails). */
function daysBetween(isoA: string, isoB: string): number | null {
  const a = Date.parse(isoA);
  const b = Date.parse(isoB);
  if (Number.isNaN(a) || Number.isNaN(b)) return null;
  return Math.floor(Math.abs(a - b) / (1000 * 60 * 60 * 24));
}

/** Has the user already seen an insight сегодня? */
export function shouldShowInsight(): boolean {
  try {
    const last = window.localStorage.getItem(SUPPRESS_KEY);
    return last !== todayIsoDate();
  } catch (e) {
    // 1.5 fix: было silent → теперь visible в DevTools. localStorage
    // disabled (private browsing / corporate policy) → показываем insight.
    console.warn('[M-07 daily-insights] localStorage read failed, defaulting к show:', e);
    return true;
  }
}

/** Mark insight как shown сегодня (suppress for rest of day). */
export function markInsightShown(): void {
  try {
    window.localStorage.setItem(SUPPRESS_KEY, todayIsoDate());
  } catch (e) {
    // 1.5 fix: было silent → теперь visible в DevTools. Customer увидит
    // тот же insight завтра (suppression не сохранилась) — приемлемо.
    console.warn('[M-07 daily-insights] localStorage write failed, suppression lost:', e);
  }
}

/**
 * Compute highest-priority insight from project list.
 * Priority order: very_stale (warning) > stale (info) > onboarding_nudge > cross_sell.
 * Returns null если nothing actionable.
 */
export function computeDailyInsight(projects: ProjectSummary[]): DailyInsight | null {
  const now = new Date().toISOString();

  // Priority 1: very-stale project (>30 days), warn
  const verySorted = [...projects].sort((a, b) =>
    a.last_modified < b.last_modified ? -1 : 1,
  );
  for (const proj of verySorted) {
    const days = daysBetween(now, proj.last_modified);
    if (days !== null && days > VERY_STALE_FORECAST_DAYS) {
      return {
        id: 'very_stale_forecast',
        severity: 'warning',
        title: `Прогноз «${proj.name}» не обновлялся ${days} дней`,
        body: 'Реальные данные за прошедший месяц могут существенно изменить картину. Откройте проект и сравните с актуалами.',
        cta: 'Открыть проект',
        ctaHref: `/project/${proj.project_uuid}/history`,
        projectUuid: proj.project_uuid,
      };
    }
  }

  // Priority 2: stale project (14-30 days), info
  for (const proj of verySorted) {
    const days = daysBetween(now, proj.last_modified);
    if (days !== null && days >= STALE_FORECAST_DAYS && days <= VERY_STALE_FORECAST_DAYS) {
      return {
        id: 'stale_forecast',
        severity: 'info',
        title: `Прогноз «${proj.name}» создан ${days} дней назад`,
        body: 'Aurora накопила достаточно времени для свежей оценки — самое время сверить с актуалами.',
        cta: 'Открыть проект',
        ctaHref: `/project/${proj.project_uuid}/history`,
        projectUuid: proj.project_uuid,
      };
    }
  }

  // Priority 3: onboarded но 0 projects, gentle nudge
  let isOnboarded = false;
  try {
    isOnboarded = window.localStorage.getItem(ONBOARDED_KEY) === '1';
  } catch (e) {
    // 1.5 fix: localStorage disabled → false → onboarding nudge не показывается.
    // Заметно в DevTools для pilot-диагностики.
    console.warn('[M-07 daily-insights] localStorage onboarded-check failed:', e);
  }
  if (isOnboarded && projects.length === 0) {
    return {
      id: 'onboarding_nudge',
      severity: 'info',
      title: 'Готовы создать первый прогноз?',
      body: 'Aurora помогает за 5 минут получить честный forecast с CI-полосами и трассируемой методологией. Начнём с образца?',
      cta: 'Открыть образец',
      ctaHref: '/onboarding',
    };
  }

  // Priority 4: many projects, cross-sell signal
  if (projects.length >= 5) {
    return {
      id: 'power_user_cross_sell',
      severity: 'success',
      title: `${projects.length} прогнозов в Aurora — вы строите систему`,
      body: 'Когда в портфеле несколько брендов, постоянный tracker эффективности окупается за квартал. Brand Tracker — следующий продукт линейки.',
      cta: 'Узнать больше',
      ctaHref: 'https://auroraai.pro/brand-tracker',
    };
  }

  return null;
}
