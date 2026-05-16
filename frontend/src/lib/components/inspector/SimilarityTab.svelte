<script lang="ts">
  import { _ } from 'svelte-i18n';
  import Card from '$lib/components/Card.svelte';
  import Skeleton from '$lib/components/Skeleton.svelte';
  import RadarChart from '$lib/components/RadarChart.svelte';

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
        <RadarChart
          dimensions={similarityData.dimensions}
          size={320}
          title="Similarity (saved)"
        />
        <p class="score">Aggregate score: <strong>{(similarityData.score * 100).toFixed(0)}%</strong></p>
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
