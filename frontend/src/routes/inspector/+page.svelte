<!--
  Inspector — lazy-load tabs (Block 2B). Tabs render their content только
  при первом активации (PERFORMANCE_BUDGETS §1.3 wizard step ≤200ms ranges).
-->

<script lang="ts">
  import { _ } from 'svelte-i18n';
  import { activeBundle, manifestSummary, readEntryJson } from '$lib/stores/bundle';
  import { ipc } from '$ipc/client';
  import type { VerificationResult } from '$ipc/client';
  import MetadataTab from '$lib/components/inspector/MetadataTab.svelte';
  import SimilarityTab from '$lib/components/inspector/SimilarityTab.svelte';
  import ForecastTab from '$lib/components/inspector/ForecastTab.svelte';
  import CertTab from '$lib/components/inspector/CertTab.svelte';
  import AuditTab from '$lib/components/inspector/AuditTab.svelte';
  import type { ForecastData, SimilarityData, EngineMode } from '$lib/components/inspector/types';

  const TABS = ['metadata', 'similarity', 'forecast', 'cert', 'audit'] as const;
  type Tab = (typeof TABS)[number];

  let activeTab = $state<Tab>('metadata');
  let visited = $state<Set<Tab>>(new Set(['metadata']));

  // Shared data loaded from bundle entries — passed as props to tab components.
  let similarityData = $state<SimilarityData | null>(null);
  let forecastData = $state<ForecastData | null>(null);

  let loadingSimilarity = $state(false);
  let loadingForecast = $state(false);

  // Cert tab
  let verification = $state<VerificationResult | null>(null);
  let verifying = $state(false);

  // H-6: roving tabindex keyboard navigation for tablist.
  let tabRefs = $state<Array<HTMLButtonElement | undefined>>([]);

  function selectTab(t: Tab) {
    activeTab = t;
    visited = new Set([...visited, t]);
  }

  function tabsKeyboardNav(e: KeyboardEvent): void {
    const currentIndex = TABS.indexOf(activeTab);
    let nextIndex: number | null = null;

    if (e.key === 'ArrowRight') {
      nextIndex = (currentIndex + 1) % TABS.length;
    } else if (e.key === 'ArrowLeft') {
      nextIndex = (currentIndex - 1 + TABS.length) % TABS.length;
    } else if (e.key === 'Home') {
      nextIndex = 0;
    } else if (e.key === 'End') {
      nextIndex = TABS.length - 1;
    }

    if (nextIndex !== null) {
      e.preventDefault();
      selectTab(TABS[nextIndex] as Tab);
      requestAnimationFrame(() => tabRefs[nextIndex!]?.focus());
    }
  }

  // Lazy-load tab data on first activation.
  $effect(() => {
    if (activeTab === 'similarity' && $activeBundle && !similarityData && !loadingSimilarity) {
      loadSimilarity();
    }
    if (activeTab === 'forecast' && $activeBundle && !forecastData && !loadingForecast) {
      loadForecast();
    }
    if (activeTab === 'cert' && $activeBundle && !verification && !verifying) {
      runVerify();
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
        engine_mode?: EngineMode;
        methodology_signature?: string;
        warnings?: string[];
        n_recipient?: number;
        granularity?: 'monthly' | 'weekly';
        anchors?: Record<string, unknown> | null;
        spend_plan?: Record<string, number[]> | null;
      }>('forecast.json');
      if (payload) {
        forecastData = {
          points: payload.weekly_points.map((p) => ({
            weekIndex: p.week_index,
            point: p.point,
            ciLower: p.ci_lower,
            ciUpper: p.ci_upper
          })),
          horizonWeeks: payload.horizon_weeks,
          engineMode: payload.engine_mode ?? _inferEngineMode(payload.methodology_signature),
          methodologySignature: payload.methodology_signature,
          warnings: payload.warnings ?? [],
          nRecipient: payload.n_recipient,
          granularity: payload.granularity,
          anchors: payload.anchors ?? null,
          spendPlan: payload.spend_plan ?? null,
        };
      }
    } catch (e) {
      console.error('forecast load failed', e);
    } finally {
      loadingForecast = false;
    }
  }

  /** Derive EngineMode from methodology_signature when bundle lacks explicit field. */
  function _inferEngineMode(sig?: string): EngineMode | undefined {
    if (!sig) return undefined;
    if (sig.startsWith('pure_transfer')) return 'pure_transfer';
    if (sig.startsWith('transfer_with_bias_check')) return 'transfer_with_bias_check';
    if (sig.startsWith('ols_with_proxy_priors')) return 'ols_with_proxy_priors';
    if (sig.startsWith('bayesian_with_proxy_priors')) return 'bayesian_with_proxy_priors';
    return undefined;
  }

  async function runVerify() {
    if (!$activeBundle) return;
    verifying = true;
    try {
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
    <!-- role=tablist on div (not nav) per 4.3 a11y. H-6: Arrow/Home/End nav (ARIA APG). -->
    <div class="tabs" role="tablist" tabindex="-1" onkeydown={tabsKeyboardNav}>
      {#each TABS as t, i}
        <button
          id="tab-trigger-{t}"
          role="tab"
          tabindex={activeTab === t ? 0 : -1}
          class:active={activeTab === t}
          aria-selected={activeTab === t}
          aria-controls="tab-{t}"
          bind:this={tabRefs[i]}
          onclick={() => selectTab(t)}
        >
          {$_(`inspector.tab.${t}`)}
        </button>
      {/each}
    </div>

    <div class="tab-panels">
      {#if visited.has('metadata')}
        <div hidden={activeTab !== 'metadata'}><MetadataTab /></div>
      {/if}
      {#if visited.has('similarity')}
        <div hidden={activeTab !== 'similarity'}>
          <SimilarityTab similarityData={similarityData} loading={loadingSimilarity} />
        </div>
      {/if}
      {#if visited.has('forecast')}
        <div hidden={activeTab !== 'forecast'}>
          <ForecastTab
            forecastData={forecastData} loading={loadingForecast}
            similarityScore={similarityData?.score ?? null}
            verificationValid={verification?.valid ?? null}
          />
        </div>
      {/if}
      {#if visited.has('cert')}
        <div hidden={activeTab !== 'cert'}>
          <CertTab
            verification={verification}
            verifying={verifying}
            bundlePath={$activeBundle?.path ?? ''}
            appVersion={$manifestSummary?.aurora_app_version ?? ''}
          />
        </div>
      {/if}
      {#if visited.has('audit')}
        <div hidden={activeTab !== 'audit'}><AuditTab /></div>
      {/if}
    </div>
  </section>
{/if}

<style>
  .empty {
    display: flex; flex-direction: column; align-items: center;
    gap: var(--spacing-2); padding: var(--spacing-12); color: var(--text-muted);
  }
  .empty .link { color: var(--accent); }
  .inspector { display: flex; flex-direction: column; gap: var(--spacing-4); max-width: 1024px; margin: 0 auto; }
  .tabs { display: flex; gap: var(--spacing-2); border-bottom: 1px solid var(--border-subtle); overflow-x: auto; }
  .tabs button {
    background: transparent; border: none; color: var(--text-muted);
    padding: var(--spacing-2) var(--spacing-3); cursor: pointer;
    border-bottom: 2px solid transparent; font-family: var(--font-sans);
    transition: color var(--motion-fast) var(--easing-smooth);
  }
  .tabs button:hover { color: var(--text-primary); }
  .tabs button.active { color: var(--accent); border-bottom-color: var(--accent); }
</style>
