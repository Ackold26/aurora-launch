<script>
  import { Hst } from '@histoire/plugin-svelte';
  import RadarChart from './RadarChart.svelte';

  const high = [
    { label: 'Cat L1', value: 1 },
    { label: 'Cat L2', value: 1 },
    { label: 'Cat L3', value: 0.95 },
    { label: 'Pricing', value: 0.85 },
    { label: 'Size', value: 0.9 },
    { label: 'Distrib', value: 0.85 },
    { label: 'Media', value: 0.8 },
    { label: 'Lifecycle', value: 0.7 }
  ];

  const low = [
    { label: 'Cat L1', value: 0.5 },
    { label: 'Cat L2', value: 0.4 },
    { label: 'Cat L3', value: 0.3 },
    { label: 'Pricing', value: 0.6 },
    { label: 'Size', value: 0.4 },
    { label: 'Distrib', value: 0.3 },
    { label: 'Media', value: 0.5 },
    { label: 'Lifecycle', value: 0.2 }
  ];
</script>

<Hst.Story title="components/RadarChart" group="components">
  <Hst.Variant title="High similarity">
    <RadarChart dimensions={high} title="High similarity" />
  </Hst.Variant>

  <Hst.Variant title="Low similarity">
    <RadarChart dimensions={low} title="Low similarity" />
  </Hst.Variant>

  <Hst.Variant title="Smaller size">
    <RadarChart dimensions={high} size={240} />
  </Hst.Variant>
</Hst.Story>
