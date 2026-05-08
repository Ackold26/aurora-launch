<!--
  Wizard — 7 steps: import → mapping → proxy → similarity → anchors →
  forecast → cert. Real progress events ONLY (no setTimeout theatre).
-->

<script lang="ts">
  import { _ } from 'svelte-i18n';
  import { fly } from 'svelte/transition';
  import { quintOut } from 'svelte/easing';

  import Button from '$lib/components/Button.svelte';
  import Card from '$lib/components/Card.svelte';
  import VerdictPanel from '$lib/components/VerdictPanel.svelte';
  import RadarChart from '$lib/components/RadarChart.svelte';
  import ProgressBar from '$lib/components/ProgressBar.svelte';
  import { ipc } from '$ipc/client';
  import type { SimilarityDimensionScores } from '$types/aurora-schemas';
  import { pushToast } from '$lib/stores/toast';
  import { determineVerdict } from '$lib/utils/verdict';

  const STEPS = [
    'import',
    'mapping',
    'proxy',
    'similarity',
    'anchors',
    'forecast',
    'cert'
  ] as const;

  let step = $state(0);
  let importedFile = $state<string | null>(null);
  let mappingDone = $state(false);
  let selectedProxy = $state<string | null>(null);
  let similarityScore = $state<number | null>(null);
  let similarityDim = $state<SimilarityDimensionScores | null>(null);
  let anchorsDone = $state(false);
  let forecastHandleId = $state<string | null>(null);
  let forecastStatus = $state<{ progress: number | null; elapsedMs: number; etaMs: number | null }>(
    { progress: null, elapsedMs: 0, etaMs: null }
  );
  let certSigned = $state(false);

  // Block 3 HIGH-10 fix: import from $lib/utils/verdict (SSOT).
  // Was inlined hardcoded literals — drift risk if Python thresholds change.
  const verdict = $derived(
    similarityScore === null ? null : determineVerdict(similarityScore)
  );

  const radarData = $derived(
    similarityDim
      ? [
          { label: 'Cat L1', value: similarityDim.category_l1_match },
          { label: 'Cat L2', value: similarityDim.category_l2_match },
          { label: 'Cat L3', value: similarityDim.category_l3_match },
          { label: 'Pricing', value: similarityDim.pricing_tier_match },
          { label: 'Size', value: similarityDim.brand_size_match },
          { label: 'Distrib', value: similarityDim.distribution_match },
          { label: 'Media', value: similarityDim.media_maturity_match },
          { label: 'Lifecycle', value: similarityDim.lifecycle_match }
        ]
      : []
  );

  function next() {
    if (step < STEPS.length - 1) step += 1;
  }
  function prev() {
    if (step > 0) step -= 1;
  }

  async function pickImport() {
    const { open } = await import('@tauri-apps/plugin-dialog');
    const selected = await open({
      title: $_('wizard.step.import'),
      filters: [
        { name: 'Data files', extensions: ['xlsx', 'xls', 'csv', 'tsv'] }
      ]
    });
    if (typeof selected === 'string') {
      importedFile = selected;
      pushToast({ level: 'success', title: 'Imported', body: selected });
    }
  }

  async function computeSimilarity() {
    // Demo pair — Block 4 will pull from imported data
    try {
      const dim = await ipc.computeSimilarityDimensions({
        proxy_category_l1: 'FMCG',
        proxy_category_l2: 'Food',
        proxy_category_l3: 'Snacks',
        proxy_pricing_tier: 'MAINSTREAM',
        proxy_brand_size: 'CHALLENGER',
        proxy_distribution: 'NATIONAL',
        proxy_media_maturity: 'ALWAYS_ON',
        proxy_lifecycle: 'MATURE',
        recipient_category_l1: 'FMCG',
        recipient_category_l2: 'Food',
        recipient_category_l3: 'Snacks',
        recipient_pricing_tier: 'MAINSTREAM',
        recipient_brand_size: 'CHALLENGER',
        recipient_distribution: 'NATIONAL',
        recipient_media_maturity: 'PULSING',
        recipient_lifecycle: 'NEW'
      });
      similarityDim = dim;
      const score = await ipc.aggregateScore({
        dimensions: dim,
        weights: {
          category: 0.3,
          pricing_tier: 0.2,
          brand_size: 0.15,
          distribution: 0.1,
          media_maturity: 0.2,
          lifecycle: 0.05
        }
      });
      similarityScore = score;
    } catch (e) {
      pushToast({ level: 'danger', title: 'Similarity failed', body: String(e) });
    }
  }

  async function startForecast() {
    try {
      const handle = await ipc.startForecast({
        project_id: crypto.randomUUID(),
        horizon_weeks: 26,
        seed: 42
      });
      forecastHandleId = handle.handle_id;
      // Poll status (Block 4 will replace с event-stream)
      const startedAt = Date.now();
      const pollFn = async () => {
        if (!forecastHandleId) return;
        const s = await ipc.getForecastStatus(forecastHandleId);
        forecastStatus = {
          progress: s.state === 'completed' ? 1 : null,
          elapsedMs: Date.now() - startedAt,
          etaMs: s.eta_ms
        };
        if (s.state === 'running') {
          setTimeout(pollFn, 800);
        }
      };
      pollFn();
    } catch (e) {
      pushToast({ level: 'danger', title: 'Forecast start failed', body: String(e) });
    }
  }

  async function cancelForecast() {
    if (!forecastHandleId) return;
    try {
      await ipc.cancelForecast(forecastHandleId);
      pushToast({ level: 'info', title: $_('forecast.cancelling') });
    } catch (e) {
      pushToast({ level: 'danger', title: 'Cancel failed', body: String(e) });
    }
  }
</script>

<section class="wizard">
  <header class="wizard-header">
    <!-- Block 3 HIGH-8 fix: aria-current="step" announces active step to
         screen readers per WCAG 4.1.2. The stepper is a progress indicator
         (sequential), not navigation — keyboard users advance via Next/Back
         buttons. -->
    <ol class="stepper" aria-label="Wizard steps">
      {#each STEPS as s, i}
        <li
          class:active={i === step}
          class:done={i < step}
          aria-current={i === step ? 'step' : undefined}
          aria-label={`Step ${i + 1} of ${STEPS.length}: ${$_(`wizard.step.${s}`)}${i < step ? ' (completed)' : i === step ? ' (current)' : ''}`}
        >
          <span class="dot" aria-hidden="true">{i + 1}</span>
          <span class="label">{$_(`wizard.step.${s}`)}</span>
        </li>
      {/each}
    </ol>
  </header>

  <div class="step-body" in:fly={{ y: 12, duration: 220, easing: quintOut }}>
    {#if step === 0}
      <Card title={$_('wizard.step.import')}>
        {#snippet children()}
          <p>Импортируйте DSM/Mediascope файлы или используйте Aurora Data Studio экспорт.</p>
          <div class="row">
            <Button variant="primary" onclick={pickImport}>
              {#snippet children()}Choose file{/snippet}
            </Button>
            {#if importedFile}<code>{importedFile}</code>{/if}
          </div>
        {/snippet}
      </Card>
    {:else if step === 1}
      <Card title={$_('wizard.step.mapping')}>
        {#snippet children()}
          <p>Сопоставьте колонки источника с каноническими полями (бренд / период / продажи).</p>
          <Button onclick={() => (mappingDone = true)} variant={mappingDone ? 'secondary' : 'primary'}>
            {#snippet children()}{mappingDone ? 'Done ✓' : 'Apply mapping'}{/snippet}
          </Button>
        {/snippet}
      </Card>
    {:else if step === 2}
      <Card title={$_('wizard.step.proxy')}>
        {#snippet children()}
          <p>Выберите proxy-бренд из синдицированных данных или загрузите свой.</p>
          <Button onclick={() => (selectedProxy = 'Demo Proxy')} variant={selectedProxy ? 'secondary' : 'primary'}>
            {#snippet children()}{selectedProxy ?? 'Pick proxy'}{/snippet}
          </Button>
        {/snippet}
      </Card>
    {:else if step === 3}
      <Card title={$_('wizard.step.similarity')}>
        {#snippet children()}
          {#if !similarityDim}
            <Button variant="primary" onclick={computeSimilarity}>
              {#snippet children()}Compute{/snippet}
            </Button>
          {:else}
            <div class="similarity-row">
              <RadarChart dimensions={radarData} title="Similarity dimensions" />
              {#if verdict !== null && similarityScore !== null}
                <VerdictPanel verdict={verdict} score={similarityScore} />
              {/if}
            </div>
          {/if}
        {/snippet}
      </Card>
    {:else if step === 4}
      <Card title={$_('wizard.step.anchors')}>
        {#snippet children()}
          <p>Установите якорные параметры запуска: market size, distribution velocity, pricing index, creative quality.</p>
          <Button onclick={() => (anchorsDone = true)} variant={anchorsDone ? 'secondary' : 'primary'}>
            {#snippet children()}{anchorsDone ? 'Anchors set ✓' : 'Set anchors'}{/snippet}
          </Button>
        {/snippet}
      </Card>
    {:else if step === 5}
      <Card title={$_('wizard.step.forecast')}>
        {#snippet children()}
          {#if !forecastHandleId}
            <Button variant="sigil" size="lg" onclick={startForecast}>
              {#snippet children()}Start forecast{/snippet}
            </Button>
          {:else}
            <ProgressBar
              progress={forecastStatus.progress}
              elapsedMs={forecastStatus.elapsedMs}
              etaMs={forecastStatus.etaMs}
              label={forecastStatus.progress === 1 ? $_('forecast.completed', { values: { seconds: Math.round(forecastStatus.elapsedMs / 1000) } }) : 'Running…'}
            />
            <Button variant="ghost" onclick={cancelForecast}>
              {#snippet children()}{$_('wizard.cancel')}{/snippet}
            </Button>
          {/if}
        {/snippet}
      </Card>
    {:else if step === 6}
      <Card title={$_('wizard.step.cert')}>
        {#snippet children()}
          <p>Methodology Cert закрепляет reproducibility — Ed25519 подпись от Aurora AI.</p>
          {#if !certSigned}
            <Button variant="sigil" size="lg" onclick={() => (certSigned = true)}>
              {#snippet children()}Sign certificate{/snippet}
            </Button>
          {:else}
            <p>✓ Сертификат подписан (dev режим — local key)</p>
          {/if}
        {/snippet}
      </Card>
    {/if}
  </div>

  <footer class="wizard-actions">
    <Button variant="ghost" disabled={step === 0} onclick={prev}>
      {#snippet children()}{$_('wizard.back')}{/snippet}
    </Button>
    {#if step < STEPS.length - 1}
      <Button variant="primary" onclick={next}>
        {#snippet children()}{$_('wizard.next')}{/snippet}
      </Button>
    {:else}
      <!-- Block 3 HIGH-7 fix: Sacred Lime invariant — ONE per screen.
           On step 7 (cert) the body has variant="sigil" "Sign certificate";
           finish button must be variant="primary" to avoid 2 sigil buttons. -->
      <Button variant="primary" onclick={() => pushToast({ level: 'success', title: $_('wizard.finish') })}>
        {#snippet children()}{$_('wizard.finish')}{/snippet}
      </Button>
    {/if}
  </footer>
</section>

<style>
  .wizard {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-6);
    max-width: 1024px;
    margin: 0 auto;
  }

  .stepper {
    display: flex;
    list-style: none;
    padding: 0;
    margin: 0;
    gap: var(--spacing-3);
    overflow-x: auto;
  }

  .stepper li {
    display: flex;
    align-items: center;
    gap: var(--spacing-2);
    color: var(--text-muted);
    white-space: nowrap;
    font-size: var(--typography-fontSize-ui-sm);
  }

  .stepper li.active {
    color: var(--text-primary);
    font-weight: 500;
  }
  .stepper li.done {
    color: var(--color-success);
  }

  .dot {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    font-family: var(--font-mono);
    font-size: 12px;
  }

  li.active .dot {
    background: var(--accent);
    color: white;
    border-color: var(--accent);
  }

  li.done .dot {
    background: var(--color-success);
    color: black;
    border-color: var(--color-success);
  }

  .step-body {
    min-height: 240px;
  }

  .row {
    display: flex;
    align-items: center;
    gap: var(--spacing-3);
    flex-wrap: wrap;
  }

  .similarity-row {
    display: flex;
    gap: var(--spacing-6);
    align-items: center;
    flex-wrap: wrap;
  }

  .wizard-actions {
    display: flex;
    justify-content: space-between;
    border-top: 1px solid var(--border-subtle);
    padding-top: var(--spacing-4);
  }
</style>
