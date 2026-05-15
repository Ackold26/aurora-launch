<!-- Compare — split-pane multi-proxy comparison (Block 2B audit D6). -->

<script lang="ts">
  import { _ } from 'svelte-i18n';
  import Card from '$lib/components/Card.svelte';
  import RadarChart from '$lib/components/RadarChart.svelte';
  import VerdictPanel from '$lib/components/VerdictPanel.svelte';
  import Button from '$lib/components/Button.svelte';

  interface ProxySlot {
    label: string;
    score: number;
    verdict: 'High' | 'Medium' | 'Low' | 'Insufficient';
    dimensions: { label: string; value: number }[];
  }

  // Demo seed; Block 4 wires real bundles into these slots
  let slots = $state<ProxySlot[]>([
    {
      label: 'Proxy A — FMCG snacks',
      score: 0.87,
      verdict: 'High',
      dimensions: [
        { label: 'Cat L1', value: 1 },
        { label: 'Cat L2', value: 1 },
        { label: 'Cat L3', value: 0.9 },
        { label: 'Pricing', value: 0.85 },
        { label: 'Size', value: 0.8 },
        { label: 'Distrib', value: 0.95 },
        { label: 'Media', value: 0.75 },
        { label: 'Lifecycle', value: 0.6 }
      ]
    },
    {
      label: 'Proxy B — FMCG dairy',
      score: 0.72,
      verdict: 'Medium',
      dimensions: [
        { label: 'Cat L1', value: 1 },
        { label: 'Cat L2', value: 0.8 },
        { label: 'Cat L3', value: 0.6 },
        { label: 'Pricing', value: 0.7 },
        { label: 'Size', value: 0.85 },
        { label: 'Distrib', value: 0.7 },
        { label: 'Media', value: 0.6 },
        { label: 'Lifecycle', value: 0.5 }
      ]
    }
  ]);

  function addSlot() {
    slots = [
      ...slots,
      {
        label: `Proxy ${String.fromCharCode(65 + slots.length)} — TBD`,
        score: 0,
        verdict: 'Insufficient',
        dimensions: []
      }
    ];
  }

  function removeSlot(i: number) {
    slots = slots.filter((_, idx) => idx !== i);
  }
</script>

<section class="compare">
  <header class="compare-header">
    <h1>{$_('compare.title')}</h1>
    <Button variant="primary" onclick={addSlot}>
      {#snippet children()}{$_('compare.add')}{/snippet}
    </Button>
  </header>

  <div class="grid">
    {#each slots as slot, i (slot.label)}
      {#snippet cardActions()}
        <Button variant="ghost" size="sm" onclick={() => removeSlot(i)}>
          {#snippet children()}{$_('compare.remove')}{/snippet}
        </Button>
      {/snippet}
      <Card title={slot.label}
        actions={cardActions}>
        {#snippet children()}
          <div class="cell">
            <RadarChart dimensions={slot.dimensions} size={260} />
            <VerdictPanel verdict={slot.verdict} score={slot.score} />
          </div>
        {/snippet}
      </Card>
    {/each}
  </div>
</section>

<style>
  .compare {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-4);
  }

  .compare-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
    gap: var(--spacing-4);
  }

  .cell {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-3);
    align-items: center;
  }
</style>
