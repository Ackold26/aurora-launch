<!--
  BudgetSplitChart — горизонтальная SVG bar chart для визуализации
  распределения бюджета по каналам.

  Props:
    channels — Record<channelName, number[]> (значения per period)
    width    — ширина SVG (default 600)
    height   — высота SVG (default 200)

  Каждая bar = сумма значений канала по всем периодам.
  Screen-reader friendly: <title> с описанием + aria-label на каждой bar.
-->

<script lang="ts">
  interface Props {
    channels: Record<string, number[]>;
    width?: number;
    height?: number;
  }

  let { channels, width = 600, height = 200 }: Props = $props();

  // Палитра: data tokens из tokens.css
  const PALETTE = [
    'var(--color-data-ocean)',
    'var(--color-data-jade)',
    'var(--color-data-tangerine)',
    'var(--color-data-purple)',
    'var(--color-data-aqua)',
    'var(--color-data-berry)',
    'var(--color-data-peach)',
  ];

  // ─── Derived ─────────────────────────────────────────────────────────────

  // Список каналов с суммами
  const channelEntries = $derived(
    Object.entries(channels).map(([name, values]) => ({
      name,
      total: values.reduce((acc, v) => acc + v, 0),
    }))
  );

  const maxTotal = $derived(
    channelEntries.length > 0 ? Math.max(...channelEntries.map((e) => e.total), 1) : 1
  );

  // Layout constants
  const LABEL_W = 110;   // ширина колонки меток слева
  const VALUE_W = 90;    // ширина колонки значений справа
  const BAR_AREA_W = $derived(Math.max(width - LABEL_W - VALUE_W, 1));
  const ROW_H = $derived(
    channelEntries.length > 0 ? Math.floor(height / channelEntries.length) : height
  );
  const BAR_H = $derived(Math.max(Math.floor(ROW_H * 0.55), 8));
  const BAR_Y_OFFSET = $derived(Math.floor((ROW_H - BAR_H) / 2));

  // Форматирование числа ₽ с разделением тысяч
  function formatRub(value: number): string {
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'RUB',
      maximumFractionDigits: 0,
    }).format(value);
  }

  // Описание для <title> (screen reader)
  const titleText = $derived(
    channelEntries.length === 0
      ? 'Нет данных о распределении бюджета'
      : `Распределение бюджета по каналам: ${channelEntries.map((e) => `${e.name} — ${formatRub(e.total)}`).join(', ')}`
  );
</script>

<svg
  {width}
  {height}
  viewBox="0 0 {width} {height}"
  role="img"
  aria-label={titleText}
  xmlns="http://www.w3.org/2000/svg"
  class="budget-split-chart"
>
  <title>{titleText}</title>

  {#if channelEntries.length === 0}
    <text
      x={width / 2}
      y={height / 2}
      text-anchor="middle"
      dominant-baseline="middle"
      fill="var(--text-muted)"
      font-size="14"
    >Нет данных</text>
  {:else}
    {#each channelEntries as entry, i}
      {@const rowY = i * ROW_H}
      {@const barW = maxTotal > 0 ? Math.round((entry.total / maxTotal) * BAR_AREA_W) : 0}
      {@const color = PALETTE[i % PALETTE.length]}
      {@const barY = rowY + BAR_Y_OFFSET}
      {@const midY = rowY + Math.floor(ROW_H / 2)}

      <!-- Channel label (left) -->
      <text
        x={LABEL_W - 8}
        y={midY}
        text-anchor="end"
        dominant-baseline="middle"
        fill="var(--text-secondary)"
        font-size="12"
        class="chart-label"
      >{entry.name}</text>

      <!-- Bar -->
      <rect
        x={LABEL_W}
        y={barY}
        width={barW}
        height={BAR_H}
        fill={color}
        rx="3"
        aria-label="{entry.name}: {formatRub(entry.total)}"
      />

      <!-- Value label (right) -->
      <text
        x={LABEL_W + BAR_AREA_W + 8}
        y={midY}
        dominant-baseline="middle"
        fill="var(--text-primary)"
        font-size="12"
        class="chart-value"
      >{formatRub(entry.total)}</text>
    {/each}
  {/if}
</svg>

<style>
  .budget-split-chart {
    display: block;
    overflow: visible;
    max-width: 100%;
  }

  .chart-label {
    font-family: var(--font-sans);
  }

  .chart-value {
    font-family: var(--font-sans);
    font-variant-numeric: tabular-nums;
  }
</style>
