<script lang="ts">
  import { _ } from 'svelte-i18n';
  import Card from '$lib/components/Card.svelte';
</script>

<div role="tabpanel" id="tab-audit" hidden={false}>
  <Card title={$_('inspector.tab.audit')}>
    {#snippet children()}
      <p>Per-bundle audit trail entries (Block 4 wires real audit log read).</p>
    {/snippet}
  </Card>
</div>
