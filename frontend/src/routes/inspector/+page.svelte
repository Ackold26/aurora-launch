<!--
  Inspector — lazy-load tabs (Block 2B). Tabs render their content только
  при первом активации (PERFORMANCE_BUDGETS §1.3 wizard step ≤200ms ranges).
-->

<script lang="ts">
  import { _ } from 'svelte-i18n';
  import { activeBundle, manifestSummary } from '$lib/stores/bundle';
  import { readEntryJson } from '$lib/stores/bundle';
  import Card from '$lib/components/Card.svelte';
  import Skeleton from '$lib/components/Skeleton.svelte';
  import TrustBadge from '$lib/components/TrustBadge.svelte';
  import RadarChart from '$lib/components/RadarChart.svelte';
  import ForecastCone from '$lib/components/ForecastCone.svelte';
  import { ipc } from '$ipc/client';
  import type { VerificationResult } from '$ipc/client';

  const TABS = ['metadata', 'similarity', 'forecast', 'cert', 'audit'] as const;
  type Tab = (typeof TABS)[number];

  let activeTab = $state<Tab>('metadata');
  let visited = $state<Set<Tab>>(new Set(['metadata']));
  let verification = $state<VerificationResult | null>(null);
  let verifying = $state(false);

  // Block 4 Phase 5: real data tabs (was Skeleton placeholders)
  let similarityData = $state<{
    dimensions: { label: string; value: number }[];
    score: number;
  } | null>(null);
  let forecastData = $state<{
    points: { weekIndex: number; point: number; ciLower: number; ciUpper: number }[];
    horizonWeeks: number;
  } | null>(null);
  let loadingSimilarity = $state(false);
  let loadingForecast = $state(false);

  $effect(() => {
    if (activeTab === 'similarity' && $activeBundle && !similarityData && !loadingSimilarity) {
      loadSimilarity();
    }
    if (activeTab === 'forecast' && $activeBundle && !forecastData && !loadingForecast) {
      loadForecast();
    }
  });

  async function loadSimilarity() {
    loadingSimilarity = true;
    try {
      const payload = await readEntryJson<{
        dimensions: Record<string, number>;
        aggregate_score: number;
      }>('similarity.json');
      if (payload) {
        similarityData = {
          dimensions: Object.entries(payload.dimensions || {}).map(([label, value]) => ({
            label,
            value
          })),
          score: payload.aggregate_score
        };
      }
    } catch (e) {
      console.error('similarity load failed', e);
    } finally {
      loadingSimilarity = false;
    }
  }

  async function loadForecast() {
    loadingForecast = true;
    try {
      const payload = await readEntryJson<{
        weekly_points: Array<{
          week_index: number;
          point: number;
          ci_lower: number;
          ci_upper: number;
        }>;
        horizon_weeks: number;
      }>('forecast.json');
      if (payload) {
        forecastData = {
          points: payload.weekly_points.map((p) => ({
            weekIndex: p.week_index,
            point: p.point,
            ciLower: p.ci_lower,
            ciUpper: p.ci_upper
          })),
          horizonWeeks: payload.horizon_weeks
        };
      }
    } catch (e) {
      console.error('forecast load failed', e);
    } finally {
      loadingForecast = false;
    }
  }

  function selectTab(t: Tab) {
    activeTab = t;
    visited = new Set([...visited, t]);
  }

  $effect(() => {
    if (activeTab === 'cert' && $activeBundle && !verification && !verifying) {
      runVerify();
    }
  });

  async function runVerify() {
    if (!$activeBundle) return;
    verifying = true;
    try {
      // Block 4 Phase 5: BundleHandleSummary now exposes `path` field
      // (was empty string stub до Block 4). verify_bundle_signature gets
      // real path → real result.
      const result = await ipc.verifyBundleSignature({
        bundle_path: $activeBundle.path,
        trust_local_dev: true
      });
      verification = result;
    } catch (e) {
      console.error(e);
    } finally {
      verifying = false;
    }
  }
</script>

{#if !$activeBundle}
  <div class="empty">
    <p>{$_('audit.empty')}</p>
    <a href="/" class="link">→ {$_('welcome.cta.sample')}</a>
  </div>
{:else}
  <section class="inspector">
    <nav class="tabs" role="tablist">
      {#each TABS as t}
        <button
          role="tab"
          class:active={activeTab === t}
          aria-selected={activeTab === t}
          aria-controls="tab-{t}"
          onclick={() => selectTab(t)}
        >
          {$_(`inspector.tab.${t}`)}
        </button>
      {/each}
    </nav>

    <div class="tab-panels">
      {#if visited.has('metadata')}
        <div role="tabpanel" id="tab-metadata" hidden={activeTab !== 'metadata'}>
          <Card title={$_('inspector.tab.metadata')}>
            {#snippet children()}
              <dl class="meta-grid">
                <dt>Project ID</dt>
                <dd class="mono">{$manifestSummary?.project_id ?? '—'}</dd>
                <dt>Revision</dt>
                <dd class="mono">{$manifestSummary?.revision ?? '—'}</dd>
                <dt>Aurora Launch version</dt>
                <dd>{$manifestSummary?.aurora_app_version ?? '—'}</dd>
                <dt>Created</dt>
                <dd>{$manifestSummary?.created_at ?? '—'}</dd>
                <dt>Last modified</dt>
                <dd>{$manifestSummary?.last_modified ?? '—'}</dd>
                <dt>Files</dt>
                <dd>{Object.keys($manifestSummary?.files ?? {}).length}</dd>
                <dt>Integrity check</dt>
                <dd>{$manifestSummary?.integrity_check ?? '—'}</dd>
                <dt>Compression</dt>
                <dd>{$manifestSummary?.compression ?? '—'}</dd>
              </dl>
            {/snippet}
          </Card>
        </div>
      {/if}

      {#if visited.has('similarity')}
        <div role="tabpanel" id="tab-similarity" hidden={activeTab !== 'similarity'}>
          <Card title={$_('inspector.tab.similarity')}>
            {#snippet children()}
              {#if loadingSimilarity}
                <Skeleton width="100%" height="180px" rounded />
              {:else if similarityData}
                <RadarChart
                  dimensions={similarityData.dimensions}
                  size={320}
                  title="Similarity (saved)"
                />
                <p class="score">Aggregate score: <strong>{(similarityData.score * 100).toFixed(0)}%</strong></p>
              {:else}
                <p class="muted">No similarity entry в bundle (workflow not yet computed).</p>
              {/if}
            {/snippet}
          </Card>
        </div>
      {/if}

      {#if visited.has('forecast')}
        <div role="tabpanel" id="tab-forecast" hidden={activeTab !== 'forecast'}>
          <Card title={$_('inspector.tab.forecast')}>
            {#snippet children()}
              {#if loadingForecast}
                <Skeleton width="100%" height="240px" rounded />
              {:else if forecastData}
                <ForecastCone
                  points={forecastData.points}
                  horizonWeeks={forecastData.horizonWeeks}
                  width={620}
                  height={300}
                  title="Forecast cone (saved)"
                />
              {:else}
                <p class="muted">No forecast entry в bundle (workflow not yet completed).</p>
              {/if}
            {/snippet}
          </Card>
        </div>
      {/if}

      {#if visited.has('cert')}
        <div role="tabpanel" id="tab-cert" hidden={activeTab !== 'cert'}>
          <Card title={$_('inspector.tab.cert')}>
            {#snippet children()}
              {#if verifying}
                <Skeleton width="320px" height="40px" rounded />
              {:else if verification}
                <TrustBadge result={verification} />
              {:else}
                <p>Open this tab to verify bundle signature.</p>
              {/if}
            {/snippet}
          </Card>
        </div>
      {/if}

      {#if visited.has('audit')}
        <div role="tabpanel" id="tab-audit" hidden={activeTab !== 'audit'}>
          <Card title={$_('inspector.tab.audit')}>
            {#snippet children()}
              <p>Per-bundle audit trail entries (Block 4 wires real audit log read).</p>
            {/snippet}
          </Card>
        </div>
      {/if}
    </div>
  </section>
{/if}

<style>
  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--spacing-2);
    padding: var(--spacing-12);
    color: var(--text-muted);
  }

  .empty .link {
    color: var(--accent);
  }

  .inspector {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-4);
    max-width: 1024px;
    margin: 0 auto;
  }

  .tabs {
    display: flex;
    gap: var(--spacing-2);
    border-bottom: 1px solid var(--border-subtle);
    overflow-x: auto;
  }

  .tabs button {
    background: transparent;
    border: none;
    color: var(--text-muted);
    padding: var(--spacing-2) var(--spacing-3);
    cursor: pointer;
    border-bottom: 2px solid transparent;
    font-family: var(--font-sans);
    transition: color var(--motion-fast) var(--easing-smooth);
  }

  .tabs button:hover {
    color: var(--text-primary);
  }

  .tabs button.active {
    color: var(--accent);
    border-bottom-color: var(--accent);
  }

  .meta-grid {
    display: grid;
    grid-template-columns: 200px 1fr;
    gap: var(--spacing-2) var(--spacing-4);
    margin: 0;
  }

  dt {
    color: var(--text-muted);
  }

  dd {
    margin: 0;
    color: var(--text-primary);
  }

  .mono {
    font-family: var(--font-mono);
    font-size: 0.9em;
  }

  .muted {
    color: var(--text-muted);
    font-style: italic;
  }

  .score {
    color: var(--text-secondary);
    margin-top: var(--spacing-3);
  }

  .score strong {
    color: var(--accent);
    font-family: var(--font-mono);
  }
</style>
