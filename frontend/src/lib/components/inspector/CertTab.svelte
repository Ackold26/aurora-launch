<script lang="ts">
  import { _ } from 'svelte-i18n';
  import Card from '$lib/components/Card.svelte';
  import Skeleton from '$lib/components/Skeleton.svelte';
  import TrustBadge from '$lib/components/TrustBadge.svelte';
  import type { VerificationResult } from '$ipc/client';

  interface Props {
    verification: VerificationResult | null;
    verifying: boolean;
  }

  let { verification, verifying }: Props = $props();
</script>

<div role="tabpanel" id="tab-cert" hidden={false}>
  <Card title={$_('inspector.tab.cert')}>
    {#snippet children()}
      {#if verifying}
        <Skeleton width="320px" height="40px" rounded />
      {:else if verification}
        <TrustBadge result={verification} />
      {:else}
        <p>Open this tab to verify bundle signature.</p>
      {/if}
    {/snippet}
  </Card>
</div>
