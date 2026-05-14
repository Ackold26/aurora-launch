<!--
  ForecastHistorySkeleton — 3 placeholder rows mimicking ForecastHistory timeline-row layout.
  Each row: checkbox-square placeholder + version-meta block (name bar + detail bar).

  Extracted from ForecastHistory.svelte inline .skeleton-stack/.skeleton-row markup.
  INV-14 / P-10: shimmer guard via (prefers-reduced-motion: no-preference).
  aria-hidden="true" — decorative placeholder, not announced to screen readers.
-->

<div class="fh-skeleton" aria-hidden="true">
  {#each { length: 3 } as _}
    <div class="skeleton-row">
      <div class="skeleton-checkbox"></div>
      <div class="skeleton-meta">
        <div class="skeleton-line name-bar"></div>
        <div class="skeleton-line detail-bar"></div>
      </div>
    </div>
  {/each}
</div>

<style>
  .fh-skeleton {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2, 0.5rem);
  }

  .skeleton-row {
    display: flex;
    align-items: flex-start;
    gap: var(--spacing-3, 0.75rem);
    padding: var(--spacing-3, 0.75rem);
    border: 1px solid var(--border-subtle, #2a2d37);
    border-radius: var(--border-radius-lg, 8px);
    background: var(--bg-surface, #1a1d27);
  }

  .skeleton-checkbox {
    width: 22px;
    height: 22px;
    border-radius: var(--border-radius-md, 4px);
    flex-shrink: 0;
    background: var(--surface-skeleton, color-mix(in srgb, var(--bg-surface, #1a1d27) 60%, var(--text-muted, #7a7a90)));
  }

  .skeleton-meta {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2, 0.5rem);
    padding-top: 2px;
  }

  .skeleton-line {
    background: var(--surface-skeleton, color-mix(in srgb, var(--bg-surface, #1a1d27) 60%, var(--text-muted, #7a7a90)));
    border-radius: var(--border-radius-md, 4px);
  }

  .name-bar {
    height: 1rem;
    width: 48%;
  }

  .detail-bar {
    height: 0.75rem;
    width: 30%;
    opacity: 0.65;
  }

  @media (prefers-reduced-motion: no-preference) {
    .skeleton-checkbox,
    .skeleton-line {
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
