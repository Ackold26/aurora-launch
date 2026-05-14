<!--
  WizardStepSkeleton — placeholder for wizard step content during async transitions.
  Layout: title bar + 3 form-row placeholders (label + input) + button row.

  INV-14 / P-10: shimmer only when (prefers-reduced-motion: no-preference).
  aria-hidden="true" — decorative; not announced to screen readers.
-->

<div class="wizard-skeleton" aria-hidden="true">
  <!-- Step title -->
  <div class="skeleton-line title-bar"></div>

  <!-- 3 form rows -->
  {#each { length: 3 } as _}
    <div class="form-row">
      <div class="skeleton-line label-bar"></div>
      <div class="skeleton-line input-bar"></div>
    </div>
  {/each}

  <!-- Button row -->
  <div class="btn-row">
    <div class="skeleton-btn btn-secondary"></div>
    <div class="skeleton-btn btn-primary"></div>
  </div>
</div>

<style>
  .wizard-skeleton {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-4, 1rem);
    padding: var(--spacing-4, 1rem);
  }

  .form-row {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2, 0.5rem);
  }

  .btn-row {
    display: flex;
    gap: var(--spacing-3, 0.75rem);
    justify-content: flex-end;
    margin-top: var(--spacing-2, 0.5rem);
  }

  .skeleton-line,
  .skeleton-btn {
    background: var(--surface-skeleton, color-mix(in srgb, var(--bg-surface, #1a1d27) 60%, var(--text-muted, #7a7a90)));
    border-radius: var(--border-radius-md, 4px);
  }

  .title-bar {
    height: 1.5rem;
    width: 42%;
    border-radius: var(--border-radius-lg, 8px);
  }

  .label-bar {
    height: 0.75rem;
    width: 28%;
    opacity: 0.7;
  }

  .input-bar {
    height: 2.25rem;
    width: 100%;
    border-radius: var(--border-radius-lg, 8px);
  }

  .skeleton-btn {
    height: 2.25rem;
    border-radius: var(--border-radius-lg, 8px);
  }

  .btn-secondary {
    width: 5rem;
    opacity: 0.6;
  }

  .btn-primary {
    width: 7rem;
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
