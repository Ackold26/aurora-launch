<!--
  Performance footer (Block 2F PREMIUM P7) — visible perf metrics.
  Reads from window.performance + recent forecast events.
-->

<script lang="ts">
  import { onMount } from 'svelte';

  let coldStartMs = $state<number | null>(null);
  let memMb = $state<number | null>(null);
  let buildVersion = $state<string>('');
  let buildProfile = $state<string>('');

  onMount(async () => {
    if (typeof performance !== 'undefined' && performance.timing) {
      const t = performance.timing;
      coldStartMs = Math.max(0, t.domContentLoadedEventEnd - t.navigationStart);
    } else if (typeof performance !== 'undefined') {
      // Modern API (Tauri webview)
      const nav = performance.getEntriesByType('navigation')?.[0] as
        | PerformanceNavigationTiming
        | undefined;
      if (nav) {
        coldStartMs = Math.round(nav.domContentLoadedEventEnd);
      }
    }

    // @ts-expect-error — Chromium-only API
    if (typeof performance !== 'undefined' && performance.memory) {
      // @ts-expect-error
      memMb = Math.round(performance.memory.usedJSHeapSize / 1e6);
    }

    try {
      const { ipc } = await import('$ipc/client');
      const info = await ipc.getBuildInfo();
      buildVersion = info.version;
      buildProfile = info.build_profile;
    } catch {
      // Tauri not available (Storybook / Vitest) — no-op
    }
  });
</script>

<footer class="perf-footer" aria-label="Performance metrics">
  <span class="metric">
    {#if coldStartMs !== null}
      <span class="label">Start</span>
      <span class="value" class:budget-ok={coldStartMs < 2000} class:budget-over={coldStartMs >= 2000}>
        {coldStartMs} ms
      </span>
    {/if}
  </span>

  {#if memMb !== null}
    <span class="metric">
      <span class="label">Heap</span>
      <span class="value">{memMb} MB</span>
    </span>
  {/if}

  {#if buildVersion}
    <span class="metric">
      <span class="label">v</span>
      <span class="value mono">{buildVersion}</span>
      {#if buildProfile && buildProfile !== 'production'}
        <span class="badge dev">{buildProfile}</span>
      {/if}
    </span>
  {/if}
</footer>

<style>
  .perf-footer {
    display: flex;
    align-items: center;
    gap: var(--spacing-4);
    padding: var(--spacing-1) var(--spacing-4);
    background: var(--bg-surface);
    border-top: 1px solid var(--border-subtle);
    font-family: var(--font-mono);
    font-size: var(--typography-fontSize-ui-xs);
    color: var(--text-muted);
    user-select: none;
  }

  .metric {
    display: inline-flex;
    align-items: baseline;
    gap: var(--spacing-1);
  }

  .label {
    color: var(--text-muted);
  }

  .value {
    color: var(--text-secondary);
  }

  .budget-ok {
    color: var(--color-success);
  }
  .budget-over {
    color: var(--color-danger);
  }

  .badge.dev {
    color: var(--color-warning);
    border: 1px solid var(--color-warning);
    border-radius: 4px;
    padding: 0 6px;
    font-size: 10px;
    text-transform: uppercase;
    margin-left: 6px;
  }

  .mono {
    font-family: var(--font-mono);
  }
</style>
