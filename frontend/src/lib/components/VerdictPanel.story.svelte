<script>
  import { Hst } from '@histoire/plugin-svelte';
  import VerdictPanel from './VerdictPanel.svelte';
</script>

<Hst.Story title="components/VerdictPanel" group="components">
  <Hst.Variant title="High">
    <VerdictPanel verdict="High" score={0.92} />
  </Hst.Variant>

  <Hst.Variant title="Medium">
    <VerdictPanel verdict="Medium" score={0.74} />
  </Hst.Variant>

  <Hst.Variant title="Low">
    <VerdictPanel verdict="Low" score={0.55} />
  </Hst.Variant>

  <Hst.Variant title="Insufficient">
    <VerdictPanel verdict="Insufficient" score={0.32} />
  </Hst.Variant>
</Hst.Story>
