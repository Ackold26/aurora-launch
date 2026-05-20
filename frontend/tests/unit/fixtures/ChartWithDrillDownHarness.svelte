<!--
  ChartWithDrillDownHarness — test fixture for ChartWithDrillDown.svelte.

  Provides a concrete children Snippet so @testing-library/svelte can render
  ChartWithDrillDown without hitting the invalid_snippet Svelte 5 error.

  The inner div[data-testid="child-marker"] lets tests verify the children
  snippet renders inside .chart-drill-body.
-->
<script lang="ts">
  import ChartWithDrillDown from '../../../src/lib/components/transparency/ChartWithDrillDown.svelte';

  interface Props {
    formulaKey: string;
    chartTitle: string;
    subtitleOverride?: string;
  }

  let { formulaKey, chartTitle, subtitleOverride }: Props = $props();
</script>

<ChartWithDrillDown {formulaKey} {chartTitle} {subtitleOverride}>
  {#snippet children()}
    <div data-testid="child-marker">Test chart content</div>
  {/snippet}
</ChartWithDrillDown>
