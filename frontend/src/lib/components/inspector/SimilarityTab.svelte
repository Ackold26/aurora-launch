<script lang="ts">
  import { _ } from 'svelte-i18n';
  import Card from '$lib/components/Card.svelte';
  import Skeleton from '$lib/components/Skeleton.svelte';
  import RadarChart from '$lib/components/RadarChart.svelte';
  import ChartWithDrillDown from '$lib/components/transparency/ChartWithDrillDown.svelte';
  import NumberWithDrillDown from '$lib/components/transparency/NumberWithDrillDown.svelte';

  interface Props {
    similarityData: { dimensions: { label: string; value: number }[]; score: number } | null;
    loading: boolean;
  }

  let { similarityData, loading }: Props = $props();
</script>

<div role="tabpanel" id="tab-similarity" hidden={false}>
  <Card title={$_('inspector.tab.similarity')}>
    {#snippet children()}
      {#if loading}
        <Skeleton width="100%" height="180px" rounded />
      {:else if similarityData}
        <ChartWithDrillDown
          formulaKey="similarity_jensen_shannon"
          chartTitle={$_('inspector.similarity.chart_title', { default: 'Сходство по 8 измерениям' })}
        >
          {#snippet children()}
            <RadarChart
              dimensions={similarityData.dimensions}
              size={320}
              title="Similarity (saved)"
            />
          {/snippet}
        </ChartWithDrillDown>
        <p class="score">Aggregate score: <strong><NumberWithDrillDown
          formulaKey="similarity_jensen_shannon"
          value={`${(similarityData.score * 100).toFixed(0)}%`}
        /></strong></p>
      {:else}
        <p class="muted">No similarity entry в bundle (workflow not yet computed).</p>
      {/if}
    {/snippet}
  </Card>
</div>

<style>
  .muted {
    color: var(--text-muted);
    font-style: italic;
  }

  .score {
    color: var(--text-secondary);
    margin-top: var(--spacing-3);
  }

  .score strong {
    color: var(--accent);
    font-family: var(--font-mono);
  }
</style>
