<script>
  import { Hst } from '@histoire/plugin-svelte';
  import ConsultingHoursWidget from './ConsultingHoursWidget.svelte';
</script>

<Hst.Story title="welcome/ConsultingHoursWidget" group="flows">
  <Hst.Variant title="Low usage — success (25%)">
    <ConsultingHoursWidget used={10} total={40} />
  </Hst.Variant>

  <Hst.Variant title="Warning (80%)">
    <ConsultingHoursWidget used={32} total={40} />
  </Hst.Variant>

  <Hst.Variant title="Danger (95%)">
    <ConsultingHoursWidget used={38} total={40} />
  </Hst.Variant>

  <Hst.Variant title="Unlimited (total = 0)">
    <ConsultingHoursWidget used={5} total={0} />
  </Hst.Variant>

  <Hst.Variant title="Over budget (45/40)">
    <ConsultingHoursWidget used={45} total={40} />
  </Hst.Variant>

  <Hst.Variant title="Custom label override">
    <ConsultingHoursWidget used={12} total={20} label="Поминутный биллинг" />
  </Hst.Variant>
</Hst.Story>
