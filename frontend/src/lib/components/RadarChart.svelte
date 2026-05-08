<!--
  RadarChart — Custom SVG radar для similarity dimensions (Block 2D HIGH H6).
  Premium fit-for-purpose visualisation; ECharts отброшена (1 MB bloat).
  Real-time fill при wizard slider movement (PERFORMANCE_BUDGETS §1.3 ≤30ms warm).
-->

<script lang="ts">
  interface Dimension {
    label: string;
    value: number; // 0..1
    weight?: number; // 0..1
  }

  interface Props {
    dimensions: Dimension[];
    size?: number;
    strokeColor?: string;
    fillColor?: string;
    title?: string;
  }

  let {
    dimensions,
    size = 320,
    strokeColor = 'var(--accent)',
    fillColor = 'color-mix(in srgb, var(--accent) 25%, transparent)',
    title
  }: Props = $props();

  const radius = $derived(size / 2 - 30);
  const center = $derived(size / 2);

  function pointFor(idx: number, value: number, n: number) {
    const angle = (Math.PI * 2 * idx) / n - Math.PI / 2;
    const r = Math.max(0, Math.min(1, value)) * radius;
    return {
      x: center + Math.cos(angle) * r,
      y: center + Math.sin(angle) * r
    };
  }

  function labelPos(idx: number, n: number) {
    const angle = (Math.PI * 2 * idx) / n - Math.PI / 2;
    const r = radius + 16;
    return {
      x: center + Math.cos(angle) * r,
      y: center + Math.sin(angle) * r
    };
  }

  const polygonPoints = $derived(
    dimensions
      .map((d, i) => {
        const p = pointFor(i, d.value, dimensions.length);
        return `${p.x},${p.y}`;
      })
      .join(' ')
  );

  const gridLevels = [0.25, 0.5, 0.75, 1.0];
</script>

<figure class="radar" aria-label={title ?? 'Similarity dimensions radar'}>
  <svg width={size} height={size} viewBox="0 0 {size} {size}" role="img">
    {#if title}<title>{title}</title>{/if}

    <!-- Grid concentric polygons -->
    {#each gridLevels as level}
      <polygon
        points={dimensions
          .map((_, i) => {
            const p = pointFor(i, level, dimensions.length);
            return `${p.x},${p.y}`;
          })
          .join(' ')}
        fill="none"
        stroke="var(--border-subtle)"
        stroke-width="1"
      />
    {/each}

    <!-- Axes -->
    {#each dimensions as _, i}
      {@const tip = pointFor(i, 1, dimensions.length)}
      <line
        x1={center}
        y1={center}
        x2={tip.x}
        y2={tip.y}
        stroke="var(--border-subtle)"
        stroke-width="1"
      />
    {/each}

    <!-- Data polygon -->
    <polygon
      points={polygonPoints}
      fill={fillColor}
      stroke={strokeColor}
      stroke-width="2"
    />

    <!-- Vertices -->
    {#each dimensions as d, i}
      {@const p = pointFor(i, d.value, dimensions.length)}
      <circle cx={p.x} cy={p.y} r="3.5" fill={strokeColor} />
    {/each}

    <!-- Labels -->
    {#each dimensions as d, i}
      {@const lp = labelPos(i, dimensions.length)}
      <text
        x={lp.x}
        y={lp.y}
        text-anchor="middle"
        dominant-baseline="middle"
        font-size="11"
        fill="var(--text-secondary)"
        font-family="var(--font-sans)"
      >{d.label}</text>
    {/each}
  </svg>
</figure>

<style>
  .radar {
    margin: 0;
    display: inline-block;
  }
</style>
