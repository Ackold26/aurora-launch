<!--
  InspectorSkeleton — placeholder matching Inspector tab panel layout.
  Layout: tab-strip placeholders (5 tabs) + content area (metadata grid placeholder).

  INV-14 / P-10: shimmer only when (prefers-reduced-motion: no-preference).
  aria-hidden="true" — decorative; not announced to screen readers.
-->

<div class="inspector-skeleton" aria-hidden="true">
  <!-- Tab strip -->
  <div class="tab-strip">
    {#each { length: 5 } as _, i}
      <div class="skeleton-tab" class:active-tab={i === 0}></div>
    {/each}
  </div>

  <!-- Content area: metadata grid (label + value pairs × 4) -->
  <div class="content-area">
    {#each { length: 4 } as _}
      <div class="meta-row">
        <div class="skeleton-line label-col"></div>
        <div class="skeleton-line value-col"></div>
      </div>
    {/each}
  </div>
</div>

<style>
  .inspector-skeleton {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-4, 1rem);
    max-width: 1024px;
  }

  .tab-strip {
    display: flex;
    gap: var(--spacing-2, 0.5rem);
    border-bottom: 1px solid var(--border-subtle, #2a2d37);
    padding-bottom: var(--spacing-2, 0.5rem);
  }

  .skeleton-tab {
    height: 1.75rem;
    width: 5.5rem;
    border-radius: var(--border-radius-md, 4px);
    background: var(--surface-skeleton, color-mix(in srgb, var(--bg-surface, #1a1d27) 60%, var(--text-muted, #7a7a90)));
    opacity: 0.6;
  }

  .skeleton-tab.active-tab {
    opacity: 1;
    width: 6rem;
  }

  .content-area {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-3, 0.75rem);
    padding: var(--spacing-4, 1rem);
    border: 1px solid var(--border-subtle, #2a2d37);
    border-radius: var(--border-radius-lg, 8px);
    background: var(--bg-surface, #1a1d27);
  }

  .meta-row {
    display: grid;
    grid-template-columns: 200px 1fr;
    gap: var(--spacing-4, 1rem);
    align-items: center;
  }

  .skeleton-line {
    background: var(--surface-skeleton, color-mix(in srgb, var(--bg-surface, #1a1d27) 60%, var(--text-muted, #7a7a90)));
    border-radius: var(--border-radius-md, 4px);
  }

  .label-col {
    height: 0.875rem;
    width: 70%;
    opacity: 0.65;
  }

  .value-col {
    height: 0.875rem;
    width: 50%;
  }

  @media (prefers-reduced-motion: no-preference) {
    .skeleton-tab,
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
