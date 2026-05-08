<!--
  Skeleton — loading placeholder. Premium UX (no fake setTimeout theatre).
  Use only когда loading > 200ms (PERFORMANCE_BUDGETS §1.3 modal budget).
-->

<script lang="ts">
  interface Props {
    width?: string;
    height?: string;
    rounded?: boolean;
    rounded_full?: boolean;
    aria_label?: string;
  }

  let {
    width = '100%',
    height = '1em',
    rounded = false,
    rounded_full = false,
    aria_label = 'Loading'
  }: Props = $props();
</script>

<div
  class="skeleton"
  class:rounded
  class:rounded-full={rounded_full}
  style="width: {width}; height: {height};"
  role="status"
  aria-label={aria_label}
></div>

<style>
  .skeleton {
    background: linear-gradient(
      90deg,
      var(--bg-surface) 0%,
      color-mix(in srgb, var(--bg-surface) 75%, var(--text-muted)) 50%,
      var(--bg-surface) 100%
    );
    background-size: 200% 100%;
    animation: shimmer 1.6s infinite linear;
    border-radius: 4px;
    display: inline-block;
  }

  .rounded {
    border-radius: var(--border-radius-lg);
  }

  .rounded-full {
    border-radius: 999px;
  }

  @keyframes shimmer {
    0% {
      background-position: 200% 0;
    }
    100% {
      background-position: -200% 0;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .skeleton {
      animation: none;
      opacity: 0.6;
    }
  }
</style>
