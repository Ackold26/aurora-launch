<!--
  ProgressBar — для real progress events ONLY (no setTimeout theatre).
  Block 2D HIGH: feedback_no_lying_progress_ui.md respected.
-->

<script lang="ts">
  interface Props {
    /** 0..1 progress; null = indeterminate (no fake stages allowed). */
    progress: number | null;
    label?: string;
    elapsedMs?: number;
    etaMs?: number | null;
  }

  let { progress, label, elapsedMs, etaMs }: Props = $props();

  const pct = $derived(progress === null ? 0 : Math.round(progress * 100));
  const indeterminate = $derived(progress === null);

  function fmtMs(ms: number) {
    if (ms < 1000) return `${ms} ms`;
    return `${(ms / 1000).toFixed(1)} s`;
  }
</script>

<div class="wrap" role="progressbar" aria-valuenow={indeterminate ? undefined : pct} aria-valuemin="0" aria-valuemax="100">
  {#if label}<div class="label">{label}</div>{/if}
  <div class="track">
    <div
      class="bar"
      class:indeterminate
      style:width={indeterminate ? undefined : pct + '%'}
    ></div>
  </div>
  {#if elapsedMs !== undefined || etaMs}
    <div class="meta">
      {#if elapsedMs !== undefined}<span>elapsed {fmtMs(elapsedMs)}</span>{/if}
      {#if etaMs}<span>ETA {fmtMs(etaMs)}</span>{/if}
    </div>
  {/if}
</div>

<style>
  .wrap {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1);
    width: 100%;
  }

  .label {
    color: var(--text-secondary);
    font-size: var(--typography-fontSize-ui-sm);
  }

  .track {
    width: 100%;
    height: 6px;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: 999px;
    overflow: hidden;
    position: relative;
  }

  .bar {
    height: 100%;
    background: linear-gradient(90deg, var(--accent), color-mix(in srgb, var(--accent) 70%, var(--accent-sigil)));
    transition: width var(--motion-default) var(--easing-emphasized);
  }

  .bar.indeterminate {
    width: 35%;
    animation: indeterminate 1.4s infinite ease-in-out;
  }

  @keyframes indeterminate {
    0% {
      transform: translateX(-100%);
    }
    100% {
      transform: translateX(300%);
    }
  }

  .meta {
    display: flex;
    gap: var(--spacing-3);
    color: var(--text-muted);
    font-family: var(--font-mono);
    font-size: var(--typography-fontSize-ui-xs);
  }

  @media (prefers-reduced-motion: reduce) {
    .bar.indeterminate {
      animation: none;
      width: 100%;
      opacity: 0.6;
    }
  }
</style>
