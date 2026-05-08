<script>
  import { Hst } from '@histoire/plugin-svelte';
  import Button from './Button.svelte';
</script>

<Hst.Story title="components/Button" group="components">
  <Hst.Variant title="Primary">
    <Button variant="primary">
      {#snippet children()}Continue{/snippet}
    </Button>
  </Hst.Variant>

  <Hst.Variant title="Secondary">
    <Button variant="secondary">
      {#snippet children()}Cancel{/snippet}
    </Button>
  </Hst.Variant>

  <Hst.Variant title="Ghost">
    <Button variant="ghost">
      {#snippet children()}Skip{/snippet}
    </Button>
  </Hst.Variant>

  <Hst.Variant title="Sigil (sacred lime CTA)">
    <Button variant="sigil" size="lg">
      {#snippet children()}Start forecast{/snippet}
    </Button>
  </Hst.Variant>

  <Hst.Variant title="Loading">
    <Button variant="primary" loading>
      {#snippet children()}Loading…{/snippet}
    </Button>
  </Hst.Variant>

  <Hst.Variant title="Disabled">
    <Button variant="primary" disabled>
      {#snippet children()}Unavailable{/snippet}
    </Button>
  </Hst.Variant>

  <Hst.Variant title="Sizes">
    <div style="display: flex; gap: 0.5rem; align-items: center">
      <Button variant="primary" size="sm">
        {#snippet children()}Small{/snippet}
      </Button>
      <Button variant="primary" size="md">
        {#snippet children()}Medium{/snippet}
      </Button>
      <Button variant="primary" size="lg">
        {#snippet children()}Large{/snippet}
      </Button>
    </div>
  </Hst.Variant>
</Hst.Story>
