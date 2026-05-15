<!--
  PatternSuggestionCard — Phase Magic M-06.

  Surfaces a "Похоже на ваш предыдущий запуск" suggestion based на
  pattern-matcher heuristic. Mountable в wizard (typically step 0
  import) или в любом entry point после onboarding.

  Self-contained: loads projects from store, computes matches, hides
  if no qualifying matches. Dismissable per-session (не persisted)
  чтобы не мешать experienced users.

  Per INV-14: prefers-reduced-motion respected (no hover transform).
-->

<script lang="ts">
  import { onMount, untrack } from 'svelte';
  import { goto } from '$app/navigation';
  import { projectsStore } from '$lib/stores/projects.svelte';
  import {
    findSimilarPastLaunches,
    formatRecency,
    type PatternMatch,
  } from '$lib/services/pattern-matcher';
  import { fadeIn } from '$lib/services/motion';

  interface Props {
    /** Test escape hatch: skip store refresh, use these matches directly. */
    forceMatches?: PatternMatch[];
  }

  let { forceMatches }: Props = $props();

  // forceMatches — test escape hatch (NEVER set in production). Initial capture намерен.
  let matches = $state<PatternMatch[]>(untrack(() => forceMatches ?? []));
  let dismissed = $state<boolean>(false);

  onMount(async () => {
    if (forceMatches !== undefined) return;

    if (projectsStore.projects.length === 0 && !projectsStore.loading) {
      try {
        await projectsStore.refresh();
      } catch {
        /* swallow — fallback к empty matches */
      }
    }

    matches = findSimilarPastLaunches(projectsStore.projects);
  });

  function openMatch(match: PatternMatch): void {
    goto(`/project/${match.project.project_uuid}/history`);
  }

  function dismiss(): void {
    dismissed = true;
  }
</script>

{#if !dismissed && matches.length > 0}
  <section
    class="pattern-suggestion"
    aria-label="Похожие предыдущие запуски"
    in:fadeIn={{ duration: 220 }}
  >
    <header class="pattern-header">
      <span class="pattern-icon" aria-hidden="true">🔁</span>
      <div class="pattern-headlines">
        <strong>Похоже на ваш предыдущий запуск</strong>
        <p class="pattern-sub">
          Aurora нашла {matches.length === 1
            ? 'один похожий проект'
            : `${matches.length} похожих проекта`} — заберите оттуда настройки и контекст.
        </p>
      </div>
      <button
        type="button"
        class="pattern-dismiss"
        onclick={dismiss}
        aria-label="Скрыть подсказку"
      >
        ×
      </button>
    </header>

    <ul class="pattern-list">
      {#each matches as match (match.project.project_uuid)}
        <li class="pattern-item">
          <button
            type="button"
            class="pattern-card"
            onclick={() => openMatch(match)}
          >
            <div class="card-main">
              <strong class="card-name">{match.project.name}</strong>
              <span class="card-meta">
                {formatRecency(match.project.last_modified)} ·
                {match.project.version_count} {match.project.version_count === 1
                  ? 'версия'
                  : 'версий'}
              </span>
            </div>
            <div class="card-reasons" aria-label="Признаки совпадения">
              {match.reasons.join(' · ')}
            </div>
          </button>
        </li>
      {/each}
    </ul>
  </section>
{/if}

<style>
  .pattern-suggestion {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-3, 0.75rem);
    padding: var(--spacing-3, 0.75rem) var(--spacing-4, 1rem);
    margin: 0 0 var(--spacing-4, 1rem) 0;
    background: var(--bg-surface-elevated, #f9fafb);
    border: 1px solid var(--border-subtle, #e5e7eb);
    border-radius: 8px;
  }

  .pattern-header {
    display: flex;
    align-items: flex-start;
    gap: var(--spacing-3, 0.75rem);
  }

  .pattern-icon {
    font-size: 1.5rem;
    line-height: 1;
    flex-shrink: 0;
  }

  .pattern-headlines {
    flex: 1;
    min-width: 0;
  }

  .pattern-headlines strong {
    display: block;
    color: var(--text-primary, #111827);
    font-weight: 600;
  }

  .pattern-sub {
    margin: var(--spacing-1, 0.25rem) 0 0 0;
    color: var(--text-secondary, #374151);
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
  }

  .pattern-dismiss {
    background: transparent;
    border: none;
    color: var(--text-muted, #6b7280);
    cursor: pointer;
    font-size: 1.5rem;
    line-height: 1;
    padding: 0 var(--spacing-1, 0.25rem);
  }

  .pattern-dismiss:hover {
    color: var(--text-primary, #111827);
  }

  .pattern-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2, 0.5rem);
  }

  .pattern-card {
    width: 100%;
    text-align: left;
    background: var(--bg-surface, white);
    border: 1px solid var(--border-subtle, #e5e7eb);
    border-radius: 6px;
    padding: var(--spacing-2, 0.5rem) var(--spacing-3, 0.75rem);
    cursor: pointer;
    color: inherit;
    font-family: inherit;
    transition:
      border-color var(--motion-duration-fast, 80ms) var(--motion-easing-standard, ease),
      transform var(--motion-duration-fast, 80ms) var(--motion-easing-standard, ease);
  }

  .pattern-card:hover {
    border-color: var(--accent, #2563eb);
    transform: translateX(2px);
  }

  .card-main {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--spacing-2, 0.5rem);
  }

  .card-name {
    color: var(--text-primary, #111827);
    font-weight: 600;
  }

  .card-meta {
    color: var(--text-muted, #6b7280);
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
  }

  .card-reasons {
    margin-top: var(--spacing-1, 0.25rem);
    color: var(--text-secondary, #374151);
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
    font-style: italic;
  }

  @media (prefers-reduced-motion: reduce) {
    .pattern-card {
      transition: none;
    }
    .pattern-card:hover {
      transform: none;
    }
  }
</style>
