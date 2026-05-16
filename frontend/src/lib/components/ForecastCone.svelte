<!--
  ForecastCone — streaming forecast visualization (Block 4 Phase 4).
  Custom SVG cone (point line + CI band) animates week-by-week as backend
  emits `sidecar://forecast_progress` events.

  INV-14 mandatory: prefers-reduced-motion → instant render, no animated
  growth. Static fallback respects user's motion preference.

  INV-07 honest progress — only animates real points received from backend
  events. NO setTimeout staged simulation.

  A11y (Phase M-10): SVG title/desc + role="img" + data table toggle for
  screen reader access (NVDA/JAWS/VoiceOver).
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

  // Stable unique ID per component instance (no SSR in Tauri, Math.random is fine)
  const uniqueId = $state(Math.random().toString(36).slice(2, 8));

  let showTable = $state(false);

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

  /** Formats a number for the accessible table with ru-RU locale and 1 decimal. */
  function formatNumber(n: number): string {
    return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 }).format(n);
  }

  // Derived summary values for SVG title text
  const pointMin = $derived(points.length > 0 ? Math.min(...points.map((p) => p.point)) : 0);
  const pointMax = $derived(points.length > 0 ? Math.max(...points.map((p) => p.point)) : 0);

  const svgTitle = $derived(
    title
      ? title
      : `Прогноз awareness на ${horizonWeeks} недель: точка от ${fmtNumber(pointMin)} до ${fmtNumber(pointMax)} с диапазоном доверия 90%`
  );

  const svgDesc = $derived(
    `График отображает прогноз awareness с границами доверительного интервала 90%. ` +
    `По оси X — недели 1 до ${horizonWeeks}, по оси Y — значение awareness в %. ` +
    `Точечный прогноз — синяя линия, диапазон неопределённости — светло-синяя область.`
  );
</script>

<figure class="cone" aria-label={title ?? 'Forecast cone'}>
  {#if points.length === 0}
    <p class="cone-empty" role="status">Нет данных прогноза</p>
  {:else}
    <svg
      width={width}
      height={height}
      viewBox="0 0 {width} {height}"
      role="img"
      aria-labelledby="cone-title-{uniqueId}"
      aria-describedby="cone-desc-{uniqueId}"
    >
      <title id="cone-title-{uniqueId}">{svgTitle}</title>
      <desc id="cone-desc-{uniqueId}">{svgDesc}</desc>

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

    <!-- Toggle: accessible data table -->
    <button
      class="toggle-table"
      aria-expanded={showTable}
      aria-controls="cone-table-{uniqueId}"
      onclick={() => (showTable = !showTable)}
    >
      {showTable ? '▾' : '▸'} Показать данные таблицей
    </button>

    {#if showTable}
      <div class="cone-table-wrap" id="cone-table-{uniqueId}">
        <table>
          <caption class="sr-only">Прогнозируемые значения awareness по неделям</caption>
          <thead>
            <tr>
              <th scope="col">Неделя</th>
              <th scope="col">Прогноз</th>
              <th scope="col">Нижняя граница</th>
              <th scope="col">Верхняя граница</th>
            </tr>
          </thead>
          <tbody>
            {#each points as p}
              <tr>
                <th scope="row">{p.weekIndex + 1}</th>
                <td>{formatNumber(p.point)}</td>
                <td>{formatNumber(p.ciLower)}</td>
                <td>{formatNumber(p.ciUpper)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  {/if}
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

  .cone-empty {
    color: var(--text-secondary, #495057);
    font-size: 0.9em;
    margin: 0;
    padding: 16px 0;
  }

  .toggle-table {
    margin-top: var(--space-sm, 8px);
    background: transparent;
    border: none;
    color: var(--text-secondary, #495057);
    cursor: pointer;
    font-size: 0.9em;
    padding: 4px 8px;
    border-radius: 4px;
  }

  .toggle-table:hover {
    background: var(--surface-soft, rgba(0, 0, 0, 0.04));
  }

  .toggle-table:focus-visible {
    outline: 2px solid var(--color-ui-accent-primary, #2e5bff);
    outline-offset: 2px;
  }

  .cone-table-wrap {
    margin-top: var(--space-sm, 8px);
    overflow-x: auto;
  }

  .cone-table-wrap table {
    border-collapse: collapse;
    font-size: 0.9em;
    width: 100%;
  }

  .cone-table-wrap th,
  .cone-table-wrap td {
    padding: 6px 12px;
    text-align: right;
    border-bottom: 1px solid var(--color-border, #e0e0e0);
  }

  .cone-table-wrap th[scope='row'] {
    text-align: left;
    font-weight: 500;
  }

  .cone-table-wrap th[scope='col'] {
    background: var(--bg-elevated, #fafbfc);
    font-weight: 600;
  }

  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }
</style>
