<!--
  VerdictPanel — High / Medium / Low / Insufficient with explainer tooltip.
  Block 2B requirement.
-->

<script lang="ts">
  import { _ } from 'svelte-i18n';

  import Badge from './Badge.svelte';

  interface Props {
    verdict: 'High' | 'Medium' | 'Low' | 'Insufficient';
    score: number;
    explainer?: string;
  }

  let { verdict, score, explainer }: Props = $props();

  const variant = $derived(
    verdict === 'High'
      ? 'verdict-high'
      : verdict === 'Medium'
        ? 'verdict-medium'
        : verdict === 'Low'
          ? 'verdict-low'
          : 'verdict-insufficient'
  );

  const scorePct = $derived(Math.round(score * 100));
</script>

<div class="verdict" data-verdict={verdict}>
  <div class="header">
    <Badge {variant} size="md">
      {#snippet children()}{$_(`verdict.${verdict}`)}{/snippet}
    </Badge>
    <span class="score">{scorePct}%</span>
  </div>
  <p class="explainer" title={explainer ?? $_('verdict.explainer')}>
    {explainer ?? $_('verdict.explainer')}
  </p>
</div>

<style>
  .verdict {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
    padding: var(--spacing-3);
    border-radius: var(--border-radius-lg);
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
  }

  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--spacing-3);
  }

  .score {
    font-family: var(--font-mono);
    font-size: var(--typography-fontSize-ui-h3);
    font-weight: 500;
    color: var(--text-primary);
  }

  .explainer {
    font-size: var(--typography-fontSize-ui-sm);
    color: var(--text-secondary);
    line-height: 1.4;
    margin: 0;
  }
</style>
