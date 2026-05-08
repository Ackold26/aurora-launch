<!--
  TrustBadge — verification provenance display (Block 2C PREMIUM P8).
  Shows chain of trust: signed_by, signed_at MSK, key fingerprint.
-->

<script lang="ts">
  import { _ } from 'svelte-i18n';

  import Badge from './Badge.svelte';
  import type { VerificationResult } from '$ipc/client';

  interface Props {
    result: VerificationResult;
    expandable?: boolean;
  }

  let { result, expandable = true }: Props = $props();

  let expanded = $state(false);

  const labelKey = $derived(`trust_badge.${result.trust_badge}`);
  const variant = $derived(
    result.trust_badge === 'production'
      ? 'success'
      : result.trust_badge === 'dev'
        ? 'info'
        : result.trust_badge === 'sample'
          ? 'sigil'
          : 'warning'
  );
</script>

<div class="trust-badge">
  <button
    type="button"
    class="trust-summary"
    onclick={() => expandable && (expanded = !expanded)}
    aria-expanded={expandable ? expanded : undefined}
  >
    <Badge {variant} size="md">
      {#snippet children()}
        {$_(labelKey)}
        {#if !result.valid}<span aria-hidden="true">⚠</span>{/if}
      {/snippet}
    </Badge>
    {#if expandable}<span class="chevron" class:open={expanded} aria-hidden="true">▾</span>{/if}
  </button>

  {#if expanded}
    <dl class="trust-details">
      {#if result.signed_by}
        <div class="row">
          <dt>Signed by</dt>
          <dd>{result.signed_by}</dd>
        </div>
      {/if}
      {#if result.signed_at}
        <div class="row">
          <dt>Signed at</dt>
          <dd>{result.signed_at}</dd>
        </div>
      {/if}
      {#if result.key_fingerprint}
        <div class="row">
          <dt>Key fingerprint</dt>
          <dd class="mono">{result.key_fingerprint}</dd>
        </div>
      {/if}
      {#if result.composite_hash}
        <div class="row">
          <dt>Composite hash</dt>
          <dd class="mono">{result.composite_hash.slice(0, 24)}…</dd>
        </div>
      {/if}
      {#if result.manifest_revision !== null}
        <div class="row">
          <dt>Manifest revision</dt>
          <dd>{result.manifest_revision}</dd>
        </div>
      {/if}
      {#if result.failure_reason}
        <div class="row failure">
          <dt>Reason</dt>
          <dd>{result.failure_reason}</dd>
        </div>
      {/if}
    </dl>
  {/if}
</div>

<style>
  .trust-badge {
    display: inline-flex;
    flex-direction: column;
    gap: var(--spacing-2);
  }

  .trust-summary {
    display: inline-flex;
    align-items: center;
    gap: var(--spacing-1);
    background: transparent;
    border: none;
    padding: 0;
    cursor: pointer;
    color: inherit;
  }

  .chevron {
    color: var(--text-muted);
    font-size: 0.75em;
    transition: transform var(--motion-fast) var(--easing-smooth);
  }
  .chevron.open {
    transform: rotate(-180deg);
  }

  .trust-details {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-lg);
    padding: var(--spacing-3);
    margin: 0;
    font-size: var(--typography-fontSize-ui-sm);
    display: grid;
    gap: var(--spacing-2);
    min-width: 320px;
    box-shadow: var(--shadow-md);
  }

  .row {
    display: grid;
    grid-template-columns: 140px 1fr;
    gap: var(--spacing-3);
  }

  dt {
    color: var(--text-muted);
  }

  dd {
    margin: 0;
    color: var(--text-primary);
  }

  .mono {
    font-family: var(--font-mono);
    font-size: 0.85em;
  }

  .row.failure dd {
    color: var(--color-danger);
  }
</style>
