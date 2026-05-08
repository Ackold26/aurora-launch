<script>
  import { Hst } from '@histoire/plugin-svelte';
  import ProgressBar from './ProgressBar.svelte';
</script>

<Hst.Story title="components/ProgressBar" group="components">
  <Hst.Variant title="Determinate 35%">
    <ProgressBar progress={0.35} label="Forecast in progress" elapsedMs={4200} etaMs={8000} />
  </Hst.Variant>

  <Hst.Variant title="Determinate 100%">
    <ProgressBar progress={1.0} label="Complete" elapsedMs={12000} />
  </Hst.Variant>

  <Hst.Variant title="Indeterminate (real)">
    <ProgressBar progress={null} label="Waiting on backend…" />
  </Hst.Variant>
</Hst.Story>
