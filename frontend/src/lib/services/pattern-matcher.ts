/**
 * Phase Magic M-06: Pattern learning — "Похоже на ваш июньский запуск".
 *
 * Heuristic-driven similarity scoring over past projects. Surfaces top
 * candidates as wizard suggestion. No ML, no backend (v0.1.0); pure
 * deterministic ranking from project metadata + localStorage category.
 *
 * Score breakdown (max 100):
 *   - Category match (via localStorage 'aurora.category')   : 50
 *   - Recency: < 90 days from last_modified                 : 30
 *   - Maturity: version_count ≥ 3                           : 20
 *
 * Threshold for surface: ≥ 50 (i.e. at minimum same category).
 *
 * Returns top-3 ranked matches OR empty array.
 */

import type { ProjectSummary } from '$ipc/projects';

const CATEGORY_KEY = 'aurora.category';
const RECENCY_DAYS = 90;
const MATURITY_VERSIONS = 3;
const MIN_SCORE = 50;
const TOP_N = 3;

export interface PatternMatch {
  project: ProjectSummary;
  score: number;
  reasons: string[];
}

/** Days между ISO date и now, или null if parse fails. */
function daysAgo(iso: string): number | null {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return null;
  return Math.floor((Date.now() - t) / (1000 * 60 * 60 * 24));
}

/** Read user's category from localStorage. Null if not set. */
export function getStoredCategory(): string | null {
  try {
    return window.localStorage.getItem(CATEGORY_KEY);
  } catch {
    return null;
  }
}

/**
 * Find similar past launches ranked by heuristic score.
 *
 * @param projects Project list (from store)
 * @param category Override category for testing (else read from localStorage)
 * @returns Top-3 matches with score ≥ 50
 */
export function findSimilarPastLaunches(
  projects: ProjectSummary[],
  category?: string | null,
): PatternMatch[] {
  const effectiveCategory = category !== undefined ? category : getStoredCategory();
  if (!effectiveCategory) return [];
  if (projects.length === 0) return [];

  const matches: PatternMatch[] = [];

  for (const project of projects) {
    let score = 0;
    const reasons: string[] = [];

    // For v0.1.0 we don't store category per-project — assume any past
    // project под currently-selected category. Score is +50 unconditional
    // когда у пользователя set'нут category. Future: store category per project.
    score += 50;
    reasons.push(`категория ${effectiveCategory}`);

    const recencyDays = daysAgo(project.last_modified);
    if (recencyDays !== null && recencyDays <= RECENCY_DAYS) {
      score += 30;
      reasons.push(`свежий (${recencyDays} дн. назад)`);
    }

    if (project.version_count >= MATURITY_VERSIONS) {
      score += 20;
      reasons.push(`${project.version_count} версии`);
    }

    if (score >= MIN_SCORE) {
      matches.push({ project, score, reasons });
    }
  }

  // Sort by score DESC, then by recency DESC (more recent wins ties)
  matches.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    return b.project.last_modified.localeCompare(a.project.last_modified);
  });

  return matches.slice(0, TOP_N);
}

/** Human-readable "N days ago" / "N months ago". */
export function formatRecency(iso: string): string {
  const days = daysAgo(iso);
  if (days === null) return 'недавно';
  if (days < 1) return 'сегодня';
  if (days < 7) return `${days} дн. назад`;
  if (days < 30) {
    const weeks = Math.floor(days / 7);
    return `${weeks} нед. назад`;
  }
  if (days < 365) {
    const months = Math.floor(days / 30);
    return `${months} мес. назад`;
  }
  const years = Math.floor(days / 365);
  return `${years} г. назад`;
}
