<!--
  ForecastCone — streaming forecast visualization (Block 4 Phase 4).
  Custom SVG cone (point line + CI band) animates week-by-week as backend
  emits `sidecar://forecast_progress` events.

  INV-14 mandatory: prefers-reduced-motion → instant render, no animated
  growth. Static fallback respects user's motion preference.

  INV-07 honest progress — only animates real points received from backend
  events. NO setTimeout staged simulation.
-->

<script lang="ts">
  interface Point {
    weekIndex: number;
    point: number;
    ciLower: number;
    ciUpper: number;
  }

  interface Props {
    points: Point[];
    horizonWeeks: number;
    width?: number;
    height?: number;
    title?: string;
  }

  let {
    points,
    horizonWeeks,
    width = 640,
    height = 320,
    title
  }: Props = $props();

  const padding = $derived({ top: 24, right: 24, bottom: 32, left: 56 });

  const dataExtent = $derived.by(() => {
    if (points.length === 0) {
      return { min: 0, max: 100 };
    }
    let min = Number.POSITIVE_INFINITY;
    let max = Number.NEGATIVE_INFINITY;
    for (const p of points) {
      min = Math.min(min, p.ciLower);
      max = Math.max(max, p.ciUpper);
    }
    if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) {
      return { min: 0, max: 100 };
    }
    const pad = (max - min) * 0.1;
    return { min: min - pad, max: max + pad };
  });

  const innerW = $derived(width - padding.left - padding.right);
  const innerH = $derived(height - padding.top - padding.bottom);

  function xFor(weekIdx: number) {
    if (horizonWeeks <= 1) return padding.left;
    return padding.left + (weekIdx / (horizonWeeks - 1)) * innerW;
  }

  function yFor(value: number) {
    const { min, max } = dataExtent;
    const range = max - min;
    if (range === 0) return padding.top + innerH / 2;
    return padding.top + innerH - ((value - min) / range) * innerH;
  }

  const pointPath = $derived.by(() => {
    if (points.length === 0) return '';
    return points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${xFor(p.weekIndex)} ${yFor(p.point)}`).join(' ');
  });

  // Cone band (CI upper + lower → closed polygon)
  const conePath = $derived.by(() => {
    if (points.length === 0) return '';
    const upper = points.map((p) => `${xFor(p.weekIndex)},${yFor(p.ciUpper)}`).join(' ');
    const lower = points
      .slice()
      .reverse()
      .map((p) => `${xFor(p.weekIndex)},${yFor(p.ciLower)}`)
      .join(' ');
    return `M ${upper} L ${lower} Z`;
  });

  const xTicks = $derived.by(() => {
    const step = Math.max(1, Math.round(horizonWeeks / 8));
    return Array.from({ length: horizonWeeks }, (_, i) => i)
      .filter((i) => i % step === 0 || i === horizonWeeks - 1);
  });

  const yTicks = $derived.by(() => {
    const { min, max } = dataExtent;
    const steps = 4;
    return Array.from({ length: steps + 1 }, (_, i) =>
      min + ((max - min) * i) / steps
    );
  });

  function fmtNumber(n: number): string {
    return n.toLocaleString(undefined, {
      maximumFractionDigits: 0,
      useGrouping: true
    });
  }
</script>

<figure class="cone" aria-label={title ?? 'Forecast cone'}>
  <svg
    width={width}
    height={height}
    viewBox="0 0 {width} {height}"
    role="img"
  >
    {#if title}<title>{title}</title>{/if}

    <!-- Y axis grid + ticks -->
    {#each yTicks as tickValue}
      {@const y = yFor(tickValue)}
      <line
        x1={padding.left}
        y1={y}
        x2={padding.left + innerW}
        y2={y}
        stroke="var(--border-subtle)"
        stroke-dasharray="2 4"
      />
      <text
        x={padding.left - 8}
        y={y}
        text-anchor="end"
        dominant-baseline="middle"
        font-size="10"
        font-family="var(--font-mono)"
        fill="var(--text-muted)"
      >{fmtNumber(tickValue)}</text>
    {/each}

    <!-- X axis ticks -->
    {#each xTicks as wk}
      {@const x = xFor(wk)}
      <line
        x1={x}
        y1={padding.top + innerH}
        x2={x}
        y2={padding.top + innerH + 4}
        stroke="var(--border-subtle)"
      />
      <text
        x={x}
        y={padding.top + innerH + 18}
        text-anchor="middle"
        font-size="10"
        font-family="var(--font-mono)"
        fill="var(--text-muted)"
      >W{wk + 1}</text>
    {/each}

    <!-- Cone (CI band) -->
    {#if conePath}
      <path
        d={conePath}
        fill="color-mix(in srgb, var(--accent) 25%, transparent)"
        stroke="none"
        class="cone-band"
      />
    {/if}

    <!-- Point forecast line -->
    {#if pointPath}
      <path
        d={pointPath}
        fill="none"
        stroke="var(--accent)"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        class="cone-line"
      />
    {/if}

    <!-- Vertices for current points -->
    {#each points as p (p.weekIndex)}
      <circle
        cx={xFor(p.weekIndex)}
        cy={yFor(p.point)}
        r="2.5"
        fill="var(--accent)"
        class="cone-vertex"
      />
    {/each}
  </svg>
</figure>

<style>
  .cone {
    margin: 0;
    display: inline-block;
  }

  /* Subtle reveal animation as new points arrive */
  .cone-band,
  .cone-line {
    animation: fade-in var(--motion-default) var(--easing-emphasized);
  }

  .cone-vertex {
    animation: pop-in var(--motion-fast) var(--easing-spring);
  }

  @keyframes fade-in {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  @keyframes pop-in {
    from {
      transform: scale(0);
      transform-origin: center;
    }
    to {
      transform: scale(1);
    }
  }

  /* INV-14 mandatory: respect user motion preference. Static render с no
     fade or pop animations. */
  @media (prefers-reduced-motion: reduce) {
    .cone-band,
    .cone-line,
    .cone-vertex {
      animation: none;
    }
  }
</style>
