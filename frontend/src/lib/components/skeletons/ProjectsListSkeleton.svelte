<!--
  ProjectsListSkeleton — 5 placeholder rows mimicking project list card layout.
  Each row: project-name bar + meta bar + button placeholder.

  INV-14 / P-10: shimmer only when (prefers-reduced-motion: no-preference).
  aria-hidden="true" — decorative; screen readers should not announce loading bars.
-->

<div class="projects-skeleton" aria-hidden="true">
  {#each { length: 5 } as _}
    <div class="skeleton-card">
      <div class="skeleton-line name-bar"></div>
      <div class="skeleton-line meta-bar"></div>
      <div class="skeleton-btn"></div>
    </div>
  {/each}
</div>

<style>
  .projects-skeleton {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-3, 0.75rem);
  }

  .skeleton-card {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2, 0.5rem);
    padding: var(--spacing-4, 1rem);
    border: 1px solid var(--border-subtle, #2a2d37);
    border-radius: var(--border-radius-lg, 8px);
    background: var(--bg-surface, #1a1d27);
  }

  .skeleton-line,
  .skeleton-btn {
    background: var(--surface-skeleton, color-mix(in srgb, var(--bg-surface, #1a1d27) 60%, var(--text-muted, #7a7a90)));
    border-radius: var(--border-radius-md, 4px);
  }

  .name-bar {
    height: 1.125rem;
    width: 55%;
  }

  .meta-bar {
    height: 0.75rem;
    width: 38%;
    opacity: 0.7;
  }

  .skeleton-btn {
    height: 2rem;
    width: 6rem;
    border-radius: var(--border-radius-lg, 8px);
    margin-top: var(--spacing-1, 0.25rem);
  }

  @media (prefers-reduced-motion: no-preference) {
    .skeleton-line,
    .skeleton-btn {
      background: linear-gradient(
        90deg,
        var(--surface-skeleton, color-mix(in srgb, var(--bg-surface, #1a1d27) 60%, var(--text-muted, #7a7a90))) 0%,
        var(--surface-skeleton-shimmer, color-mix(in srgb, var(--bg-surface, #1a1d27) 30%, var(--text-muted, #7a7a90))) 50%,
        var(--surface-skeleton, color-mix(in srgb, var(--bg-surface, #1a1d27) 60%, var(--text-muted, #7a7a90))) 100%
      );
      background-size: 200% 100%;
      animation: skeleton-shimmer 1.5s ease-in-out infinite;
    }

    @keyframes skeleton-shimmer {
      0% { background-position: 200% 0; }
      100% { background-position: -200% 0; }
    }
  }
</style>
