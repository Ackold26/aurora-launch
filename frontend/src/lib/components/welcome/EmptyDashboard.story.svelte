<script>
  import { Hst } from '@histoire/plugin-svelte';
  import EmptyDashboard from './EmptyDashboard.svelte';
</script>

<Hst.Story title="welcome/EmptyDashboard" group="flows">
  <Hst.Variant title="Default — kagotsel_venarus sample">
    <EmptyDashboard />
  </Hst.Variant>

  <Hst.Variant title="Alternative — venarus_baseline sample">
    <EmptyDashboard sampleScenario="venarus_baseline" />
  </Hst.Variant>

  <Hst.Variant title="Alternative — multi_proxy sample">
    <EmptyDashboard sampleScenario="multi_proxy" />
  </Hst.Variant>
</Hst.Story>
