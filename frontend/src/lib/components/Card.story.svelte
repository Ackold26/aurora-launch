<script>
  import { Hst } from '@histoire/plugin-svelte';
  import Card from './Card.svelte';
  import Button from './Button.svelte';
</script>

<Hst.Story title="components/Card" group="components">
  <Hst.Variant title="Default">
    <Card title="Bundle metadata" subtitle="Project xyz · revision 7">
      {#snippet children()}
        <p>Static content area для metadata, similarity scores, etc.</p>
      {/snippet}
    </Card>
  </Hst.Variant>

  <Hst.Variant title="Interactive">
    <Card title="Open sample" interactive onclick={() => alert('clicked')}>
      {#snippet children()}
        <p>Click to open the bundled sample.</p>
      {/snippet}
    </Card>
  </Hst.Variant>

  <Hst.Variant title="With actions">
    <Card title="Settings">
      {#snippet actions()}
        <Button variant="ghost" size="sm">
          {#snippet children()}Edit{/snippet}
        </Button>
      {/snippet}
      {#snippet children()}
        <p>Configurable area</p>
      {/snippet}
    </Card>
  </Hst.Variant>

  <Hst.Variant title="Accent variants">
    <div style="display: grid; gap: 0.5rem;">
      <Card title="Success" accent="success">
        {#snippet children()}<p>OK</p>{/snippet}
      </Card>
      <Card title="Warning" accent="warning">
        {#snippet children()}<p>Caution</p>{/snippet}
      </Card>
      <Card title="Danger" accent="danger">
        {#snippet children()}<p>Failure</p>{/snippet}
      </Card>
      <Card title="Info" accent="info">
        {#snippet children()}<p>Info</p>{/snippet}
      </Card>
    </div>
  </Hst.Variant>
</Hst.Story>
