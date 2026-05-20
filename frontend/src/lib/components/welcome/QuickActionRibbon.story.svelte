<script>
  import { Hst } from '@histoire/plugin-svelte';
  import QuickActionRibbon from './QuickActionRibbon.svelte';

  // Histoire variant без onRefresh hides the refresh CTA (3 actions).
  // With onRefresh — all 4 actions visible.

  function simulateRefresh() {
    return new Promise((resolve) => setTimeout(resolve, 1500));
  }
</script>

<Hst.Story title="welcome/QuickActionRibbon" group="flows">
  <Hst.Variant title="Default — 3 actions (refresh hidden)">
    <QuickActionRibbon />
  </Hst.Variant>

  <Hst.Variant title="With refresh handler — 4 actions">
    <QuickActionRibbon onRefresh={simulateRefresh} />
  </Hst.Variant>

  <Hst.Variant title="Custom inspector destination">
    <QuickActionRibbon inspectorHref="/inspector?project=demo-uuid" />
  </Hst.Variant>
</Hst.Story>
