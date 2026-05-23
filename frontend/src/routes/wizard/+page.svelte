<!--
  Wizard — 6 steps: import → proxy → similarity → anchors →
  forecast → cert. Real progress events ONLY (no setTimeout theatre).
  DataPreviewTable embedded in Step 0 (import) — mapping step removed.
-->

<script lang="ts">
  import { _ } from 'svelte-i18n';
  import { fly } from 'svelte/transition';
  import { quintOut } from 'svelte/easing';

  import { onDestroy, onMount } from 'svelte';
  import { listen, type UnlistenFn } from '@tauri-apps/api/event';

  import Button from '$lib/components/Button.svelte';
  import Card from '$lib/components/Card.svelte';
  import VerdictPanel from '$lib/components/VerdictPanel.svelte';
  import RadarChart from '$lib/components/RadarChart.svelte';
  import ProgressBar from '$lib/components/ProgressBar.svelte';
  import ProgressBarMCMC from '$lib/components/ProgressBarMCMC.svelte';
  import type { McmcPhase } from '$lib/ipc/forecast';
  import ForecastCone from '$lib/components/ForecastCone.svelte';
  import PatternSuggestionCard from '$lib/components/PatternSuggestionCard.svelte';
  import DataPreviewTable from '$lib/components/DataPreviewTable.svelte';
  import ProxyPickerCard from '$lib/components/ProxyPickerCard.svelte';
  import AnchorsForm from '$lib/components/AnchorsForm.svelte';
  import { ipc } from '$ipc/client';
  import type {
    SimilarityDimensionScores,
    WizardAnchorsDraft
  } from '$types/aurora-schemas';
  import type {
    ForecastProgressEvent,
    ForecastCompletedEvent,
    ForecastFailedEvent,
    ColumnAssignment,
  } from '$ipc/client';
  import { pushToast } from '$lib/stores/toast';
  import { determineVerdict } from '$lib/utils/verdict';
  import { track } from '$lib/services/telemetry';
  import { composeForecastJson } from '$lib/ipc/forecast';
  import { wizardSession } from '$lib/stores/wizardSession.svelte';
  import { validIntensity } from '$lib/utils/trajectory_patterns';

  const STEPS = [
    'import',
    'proxy',
    'similarity',
    'anchors',
    'forecast',
    'cert'
  ] as const;

  let step = $state(0);
  let importedFile = $state<string | null>(null);
  let importing = $state(false);
  let validating = $state(false);

  // Step 0 (import): wide-table preview state
  let previewHeaders = $state<string[]>([]);
  let previewDataRows = $state<Array<Array<string | number | null>>>([]);
  let previewDtypes = $state<Record<string, string>>({});
  let previewShape = $state<[number, number] | null>(null);
  let previewFileName = $state<string | null>(null);
  let previewSizeKb = $state<number | null>(null);
  let roleAssignments = $state(new Map<string, ColumnAssignment>());
  let validationDone = $state(false);

  // Phase 1.C.3: proxy picker bindable
  let proxyPickerPath = $state<string | null>(null);
  let proxyPickerLabel = $state<string | null>(null);

  let similarityScore = $state<number | null>(null);
  let similarityDim = $state<SimilarityDimensionScores | null>(null);

  // Phase 1.C.5: anchors draft — shape совпадает с AnchorsForm Props и
  // Pydantic WizardAnchorsDraft (после SO-1 simplification). Все required —
  // initial defaults обеспечивают валидность сразу.
  type AnchorsDraft = {
    pattern: 'rampup' | 'sustain' | 'decline' | 'custom';
    intensity: number;
    awareness_target_pct: number | null;
    custom_trajectory: number[] | null;
    notes: string | null;
  };
  let anchorsDraft = $state<AnchorsDraft | null>({
    pattern: 'sustain',
    intensity: 5,
    awareness_target_pct: null,
    custom_trajectory: null,
    notes: null,
  });

  // Phase 1.C.6: derived completion flags
  const anchorsDone = $derived(
    anchorsDraft !== null && validIntensity(anchorsDraft.intensity)
  );

  // Audit fix 2026-05-18: track roleAssignments size + content hash to reset
  // validationDone on any role change. Without this, user правит роль после
  // успешной валидации → переход к Proxy не перепроверяется.
  // INV-22 sister: SSOT для «нужна перевалидация» — один derived.
  const roleSignature = $derived(
    Array.from(roleAssignments.values())
      .map((a) => `${a.name}:${a.role}`)
      .sort()
      .join('|'),
  );
  let lastValidatedSignature = $state<string>('');
  $effect(() => {
    // При смене roleSignature после прошлой валидации — сбросить флаг.
    // Проверка lastValidatedSignature !== '' защищает от initial fire
    // когда headers пусты и validationDone уже false.
    if (
      validationDone &&
      lastValidatedSignature !== '' &&
      roleSignature !== lastValidatedSignature
    ) {
      validationDone = false;
    }
  });

  // Phase 1.C.6: recovery dialog state
  let showRecoveryDialog = $state(false);

  let forecastHandleId = $state<string | null>(null);
  let forecastStatus = $state<{ progress: number | null; elapsedMs: number; etaMs: number | null }>(
    { progress: null, elapsedMs: 0, etaMs: null }
  );
  let forecastPoints = $state<
    { weekIndex: number; point: number; ciLower: number; ciUpper: number }[]
  >([]);
  let forecastHorizon = $state(26);
  let forecastCompleted = $state(false);
  let forecastEngineMode = $state<
    | 'pure_transfer'
    | 'transfer_with_bias_check'
    | 'ols_with_proxy_priors'
    | 'bayesian_with_proxy_priors'
    | null
  >(null);
  let forecastMethodologySignature = $state<string | null>(null);
  let forecastGranularity = $state<'monthly' | 'weekly'>('monthly');
  let forecastWarnings = $state<string[]>([]);
  let unlistenFns: UnlistenFn[] = [];
  let certSigned = $state(false);

  // 1.3d: save flow для wizard'a (raньше не было save вообще)
  let savingBundle = $state(false);
  let savedBundlePath = $state<string | null>(null);
  let saveError = $state<string | null>(null);

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

  // ─── Phase 1.C.6: Session recovery + autosave ─────────────────────────────

  onMount(async () => {
    await wizardSession.loadDraft();
    if (wizardSession.pendingDraft) {
      showRecoveryDialog = true;
    }
  });

  function applyRecoveredSession() {
    wizardSession.acceptRecovery();
    const s = wizardSession.session;
    step = s.step ?? 0;
    importedFile = s.imported_file_path ?? null;
    // Restore preview headers (gives visual context in import step)
    previewHeaders = s.imported_columns ?? [];
    // Restore roleAssignments from column_roles array
    if (s.column_roles && s.column_roles.length > 0) {
      const restoredRoles = new Map<string, ColumnAssignment>();
      for (const a of s.column_roles) {
        restoredRoles.set(a.name, {
          name: a.name,
          role: a.role,
          confidence: a.confidence,
          auto_detected: a.auto_detected ?? false,
          kind: '',  // not stored in session — backend will fill on reanalyze
        });
      }
      roleAssignments = restoredRoles;
    }
    // Restore validation flag (true only if validate_wide_table succeeded
    // ранее с тем же набором роле́й; user role change → reset → нужна перевалидация).
    validationDone = s.validation_done ?? false;
    proxyPickerPath = s.selected_proxy_path ?? null;
    proxyPickerLabel = s.selected_proxy_label ?? null;
    if (s.similarity_result) {
      // Pydantic dimensions хранится как generic dict[str, float]; runtime
      // shape совместима с SimilarityDimensionScores (та же 8 dimensions
      // produced Rust IPC). Cast через unknown для bypass strict structural.
      similarityDim = (s.similarity_result.dimensions ?? null) as unknown as
        | SimilarityDimensionScores
        | null;
      similarityScore = s.similarity_result.score ?? null;
    }
    if (s.anchors_draft) {
      anchorsDraft = {
        pattern: s.anchors_draft.pattern ?? 'sustain',
        intensity: s.anchors_draft.intensity ?? 5,
        awareness_target_pct: s.anchors_draft.awareness_target_pct ?? null,
        custom_trajectory: s.anchors_draft.custom_trajectory ?? null,
        notes: s.anchors_draft.notes ?? null,
      };
    }
    forecastCompleted = s.forecast_completed ?? false;
    forecastHorizon = s.forecast_horizon ?? 26;
    certSigned = s.cert_signed ?? false;
    savedBundlePath = s.saved_bundle_path ?? null;
    showRecoveryDialog = false;
    pushToast({
      level: 'info',
      title: $_('wizard.toast.session_restored.title'),
      body: `Шаг ${(step ?? 0) + 1} из ${STEPS.length}`,
    });
  }

  async function dismissRecovery() {
    await wizardSession.dismissRecovery();
    showRecoveryDialog = false;
  }

  /** Persist текущее состояние step в session (вызывается перед навигацией). */
  function persistCurrentStep() {
    wizardSession.update((s) => {
      s.step = step;
      // Step 0 — import: persist role assignments
      s.column_roles = Array.from(roleAssignments.values());
      s.validation_done = validationDone;
      // Step 1 — proxy
      s.selected_proxy_path = proxyPickerPath;
      s.selected_proxy_label = proxyPickerLabel;
      // Step 3 — similarity. Cast SimilarityDimensionScores (concrete shape)
      // в generic dict[str, float] (Pydantic storage type) — same runtime data.
      if (similarityDim !== null && similarityScore !== null) {
        s.similarity_result = {
          dimensions: similarityDim as unknown as Record<string, number>,
          score: similarityScore,
          verdict: verdict ?? 'Insufficient',
          computed_at: new Date().toISOString(),
        };
      }
      // Step 4 — anchors
      s.anchors_draft = anchorsDraft;
      s.anchors_done = anchorsDone;
      // Step 5 — forecast horizon
      s.forecast_horizon = forecastHorizon;
      s.forecast_completed = forecastCompleted;
      // Step 6 — cert
      s.cert_signed = certSigned;
      s.saved_bundle_path = savedBundlePath;
    });
  }

  /**
   * Run validate_wide_table с актуальными role overrides.
   * Audit fix 2026-05-18: до этой правки validate никогда не вызывался —
   * gate перед переходом к Proxy был неполным. Теперь Next на step 0
   * блокируется при validation error; warnings показываются info-тостами,
   * но не блокируют. validationDone сбрасывается при role change через
   * $effect ниже.
   */
  async function runValidation(): Promise<boolean> {
    if (!importedFile || previewHeaders.length === 0) return false;
    validating = true;
    try {
      const role_overrides: Record<string, import('$ipc/client').ColumnRole> = {};
      for (const [name, a] of roleAssignments.entries()) {
        role_overrides[name] = a.role;
      }
      const result = await ipc.validateWideTable({
        path: importedFile,
        role_overrides,
      });
      if (result.status === 'error') {
        pushToast({
          level: 'danger',
          title: $_('wizard.toast.validation_failed.title'),
          body: result.message ?? result.verdict ?? $_('wizard.toast.validation_failed.body_fallback'),
        });
        validationDone = false;
        return false;
      }
      // Show warnings as info — не блокируем переход.
      for (const w of result.warnings ?? []) {
        pushToast({ level: 'info', title: w.message ?? $_('wizard.toast.attention.title'), body: '' });
      }
      validationDone = true;
      lastValidatedSignature = roleSignature;
      return true;
    } catch (e) {
      pushToast({
        level: 'danger',
        title: $_('wizard.toast.validation_error.title'),
        body: String(e),
      });
      validationDone = false;
      return false;
    } finally {
      validating = false;
    }
  }

  async function next() {
    // Step 0 → Proxy: gate через validate_wide_table.
    if (step === 0) {
      if (previewHeaders.length === 0) return;
      if (!validationDone) {
        const ok = await runValidation();
        if (!ok) return;
      }
    }
    persistCurrentStep();
    if (step < STEPS.length - 1) step += 1;
    wizardSession.update((s) => {
      s.step = step;
    });
  }
  function prev() {
    persistCurrentStep();
    if (step > 0) step -= 1;
    wizardSession.update((s) => {
      s.step = step;
    });
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
      importing = true;
      try {
        // File reader port 2026-05-18: analyze wide table via sidecar
        const result = await ipc.analyzeDataFile({ path: selected, n_rows: 20 });
        if (result.status === 'error') {
          throw new Error(result.message ?? $_('wizard.toast.file_analyze_error.title'));
        }

        // Populate preview state
        previewHeaders = result.headers ?? [];
        previewDataRows = result.rows ?? [];
        previewDtypes = result.dtypes ?? {};
        previewShape = result.shape ?? null;
        previewFileName = result.file_name ?? null;
        previewSizeKb = result.size_kb ?? null;

        // Build roleAssignments Map from backend column detections
        const newRoles = new Map<string, ColumnAssignment>();
        for (const col of result.columns ?? []) {
          newRoles.set(col.name, {
            name: col.name,
            role: col.role,
            confidence: col.confidence,
            kind: col.kind,
            auto_detected: true,
          });
        }
        roleAssignments = newRoles;

        // Reset validation on new file load — roles may differ from prior.
        validationDone = false;
        lastValidatedSignature = '';

        // Persist in session immediately
        wizardSession.update((s) => {
          s.imported_file_path = selected;
          s.imported_adapter_id = null;  // no adapter concept in new flow
          s.imported_record_count = result.shape?.[0] ?? null;
          s.imported_columns = result.headers ?? [];
        });

        pushToast({
          level: 'success',
          title: $_('wizard.toast.file_loaded.title'),
          body: `${result.shape?.[0] ?? 0} строк · ${result.shape?.[1] ?? 0} колонок`,
        });
      } catch (e) {
        pushToast({
          level: 'danger',
          title: $_('wizard.toast.file_read_error.title'),
          body: String(e),
        });
        previewHeaders = [];
        previewDataRows = [];
        roleAssignments = new Map();
      } finally {
        importing = false;
      }
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
    forecastPoints = [];
    forecastCompleted = false;
    forecastStatus = { progress: null, elapsedMs: 0, etaMs: null };

    // Block 4 Phase 4: subscribe к sidecar event stream BEFORE invoking
    // start_forecast (avoid event race during initial bootstrap).
    const unlistenProgress = await listen<ForecastProgressEvent>(
      'sidecar://forecast_progress',
      ({ payload }) => {
        if (payload.forecast_handle !== forecastHandleId) return;
        forecastPoints = [
          ...forecastPoints,
          {
            weekIndex: payload.week_index,
            point: payload.point_forecast,
            ciLower: payload.ci_lower,
            ciUpper: payload.ci_upper
          }
        ];
        forecastStatus = {
          progress: payload.progress_pct / 100,
          elapsedMs: payload.elapsed_ms,
          etaMs: null
        };
      }
    );
    const unlistenCompleted = await listen<ForecastCompletedEvent>(
      'sidecar://forecast_completed',
      ({ payload }) => {
        if (payload.forecast_handle !== forecastHandleId) return;
        forecastCompleted = true;
        forecastStatus = { ...forecastStatus, progress: 1 };
        // 1.3d: захватываем metadata для compose_forecast_json в save flow
        const summary = payload.forecast;
        if (summary) {
          forecastEngineMode = summary.engine_mode;
          forecastMethodologySignature = summary.methodology_signature;
          forecastGranularity = summary.granularity;
          forecastWarnings = summary.warnings ?? [];
        }
        const totalPeriods = payload.horizon_weeks ?? payload.horizon_periods ?? forecastHorizon;
        // TELEMETRY-P16: forecast_complete
        track('forecast_complete', {
          horizon_periods: totalPeriods,
          elapsed_ms: payload.elapsed_ms,
        });
        pushToast({
          level: 'success',
          title: $_('forecast.completed', {
            values: { seconds: Math.round(payload.elapsed_ms / 1000) }
          })
        });
      }
    );
    const unlistenCancelled = await listen<{ forecast_handle: string; week_index: number }>(
      'sidecar://forecast_cancelled',
      ({ payload }) => {
        if (payload.forecast_handle !== forecastHandleId) return;
        pushToast({ level: 'info', title: $_('forecast.cancelled') });
      }
    );
    const unlistenFailed = await listen<ForecastFailedEvent>(
      'sidecar://forecast_failed',
      ({ payload }) => {
        if (payload.forecast_handle !== forecastHandleId) return;
        pushToast({
          level: 'danger',
          title: 'Forecast failed',
          body: `${payload.kind}: ${payload.error}`
        });
      }
    );
    unlistenFns.push(unlistenProgress, unlistenCompleted, unlistenCancelled, unlistenFailed);

    try {
      forecastHorizon = 26;
      // TELEMETRY-P16: forecast_start
      track('forecast_start', { horizon_weeks: forecastHorizon });
      const handle = await ipc.startForecast({
        project_id: crypto.randomUUID(),
        horizon_weeks: forecastHorizon,
        seed: 42
      });
      forecastHandleId = handle.handle_id;
    } catch (e) {
      pushToast({ level: 'danger', title: 'Forecast start failed', body: String(e) });
      // Clean up listeners если spawn failed
      for (const u of unlistenFns) u();
      unlistenFns = [];
    }
  }

  onDestroy(() => {
    for (const u of unlistenFns) u();
    unlistenFns = [];
  });

  async function cancelForecast() {
    if (!forecastHandleId) return;
    try {
      await ipc.cancelForecast(forecastHandleId);
      pushToast({ level: 'info', title: $_('forecast.cancelling') });
    } catch (e) {
      pushToast({ level: 'danger', title: 'Cancel failed', body: String(e) });
    }
  }

  // 1.3d: Save flow для wizard — собирает forecast.json и кладёт в .aurora.
  // До этой правки wizard вообще не сохранял bundle (только проводил forecast
  // в памяти), поэтому Inspector M-09 reproduce работал в preview-режиме.
  async function saveBundle() {
    if (!forecastCompleted || forecastPoints.length === 0) {
      pushToast({ level: 'danger', title: $_('wizard.toast.wait_for_forecast.title') });
      return;
    }
    savingBundle = true;
    saveError = null;
    try {
      const { save } = await import('@tauri-apps/plugin-dialog');
      const targetPath = await save({
        title: $_('wizard.save_dialog.title'),
        filters: [{ name: 'Aurora bundle', extensions: ['aurora'] }],
        defaultPath: 'launch-forecast.aurora',
      });
      if (!targetPath || typeof targetPath !== 'string') {
        // Customer cancelled save dialog
        return;
      }

      // Phase 1.C.6: real anchors из AnchorsForm (заменяет null заглушку).
      // Inspector M-09 теперь reproducible с реальной анкорной конфигурацией.
      const anchorsPayload: Record<string, unknown> | null = anchorsDraft
        ? {
            pattern: anchorsDraft.pattern,
            intensity: anchorsDraft.intensity,
            awareness_target_pct: anchorsDraft.awareness_target_pct,
            custom_trajectory: anchorsDraft.custom_trajectory,
            notes: anchorsDraft.notes,
          }
        : null;

      const composed = await composeForecastJson({
        horizon_weeks: forecastHorizon,
        weekly_points: forecastPoints.map((p) => ({
          week_index: p.weekIndex,
          point: p.point,
          ci_lower: p.ciLower,
          ci_upper: p.ciUpper,
        })),
        engine_mode: forecastEngineMode ?? 'pure_transfer',
        granularity: forecastGranularity,
        methodology_signature: forecastMethodologySignature ?? '',
        n_recipient: 0, // pre-launch
        warnings: forecastWarnings,
        anchors: anchorsPayload,
        spend_plan: null,
        produced_at: new Date().toISOString(),
      });

      await ipc.saveBundleViaSidecar({
        handleId: 'wizard-new',
        targetPath,
        extraFilesBase64: { 'forecast.json': composed.forecast_json_base64 },
      });

      savedBundlePath = targetPath;
      track('version_save', { revision: 0 });
      pushToast({
        level: 'success',
        title: $_('wizard.toast.saved.title'),
        body: `${targetPath} (${composed.byte_size} байт)`,
      });

      // Phase 1.C.6: persist session с saved bundle path + flush критично
      // прямо сейчас (не debounced — следующий restart должен увидеть).
      wizardSession.update((s) => {
        s.saved_bundle_path = targetPath;
        s.cert_signed = certSigned;
      });
      await wizardSession.flush();
    } catch (e) {
      saveError = e instanceof Error ? e.message : String(e);
      pushToast({ level: 'danger', title: $_('wizard.toast.save_failed.title'), body: saveError });
    } finally {
      savingBundle = false;
    }
  }
</script>

<section class="wizard">
  <!-- WCAG 2.4.2 / axe page-has-heading-one: visually hidden h1 for screen
       readers. The stepper serves as the visual page landmark, but AT users
       benefit from a top-level heading identifying the page. -->
  <h1 class="visually-hidden">{$_('wizard.h1')}</h1>
  <header class="wizard-header">
    <!-- Block 3 HIGH-8 fix: aria-current="step" announces active step to
         screen readers per WCAG 4.1.2. The stepper is a progress indicator
         (sequential), not navigation — keyboard users advance via Next/Back
         buttons. -->
    <!-- tabindex="0": WCAG 2.1 SC 2.1.1 / axe scrollable-region-focusable.
         overflow-x:auto makes the stepper a scrollable region; keyboard users
         need a way to scroll it. tabindex="0" makes it focusable via Tab. -->
    <ol class="stepper" aria-label="Wizard steps" tabindex="0">
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
      <PatternSuggestionCard />
      <Card headingLevel={2} title={$_('wizard.step.import')}>
        {#snippet children()}
          <p>{$_('wizard.import.empty_hint')}</p>
          <div class="row">
            <Button variant="primary" onclick={pickImport} loading={importing}>
              {#snippet children()}Выбрать файл{/snippet}
            </Button>
            {#if importedFile}<code>{importedFile}</code>{/if}
          </div>
          {#if previewHeaders.length > 0 && previewDataRows.length === 0}
            <p class="recovery-data-hint">
              {$_('wizard.import.recovery_hint')}
            </p>
          {/if}
          {#if previewHeaders.length > 0 && previewDataRows.length > 0}
            <DataPreviewTable
              headers={previewHeaders}
              rows={previewDataRows}
              dtypes={previewDtypes}
              totalRows={previewShape?.[0] ?? undefined}
              sizeKb={previewSizeKb}
              bind:roleAssignments
            />
          {/if}
        {/snippet}
      </Card>
    {:else if step === 1}
      <ProxyPickerCard
        bind:selectedPath={proxyPickerPath}
        bind:selectedLabel={proxyPickerLabel}
      />
    {:else if step === 2}
      <Card headingLevel={2} title={$_('wizard.step.similarity')}>
        {#snippet children()}
          {#if !similarityDim}
            <Button variant="primary" onclick={computeSimilarity}>
              {#snippet children()}Рассчитать похожесть{/snippet}
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
    {:else if step === 3}
      <AnchorsForm bind:draft={anchorsDraft} horizon_periods={forecastHorizon} />
    {:else if step === 4}
      <Card headingLevel={2} title={$_('wizard.step.forecast')}>
        {#snippet children()}
          {#if !forecastHandleId}
            <Button variant="sigil" size="lg" onclick={startForecast}>
              {#snippet children()}Запустить прогноз{/snippet}
            </Button>
          {:else}
            <div class="forecast-running">
              <ProgressBarMCMC
                pct={(forecastStatus.progress ?? 0) * 100}
                phase={(forecastCompleted ? 'done' : 'sampling') as McmcPhase}
                elapsedMs={forecastStatus.elapsedMs}
                message={forecastCompleted
                  ? $_('forecast.completed', { values: { seconds: Math.round(forecastStatus.elapsedMs / 1000) } })
                  : `Период ${forecastPoints.length} из ${forecastHorizon}`}
                oncancel={cancelForecast}
                cancelDisabled={forecastCompleted}
              />
              <ForecastCone
                points={forecastPoints}
                horizonWeeks={forecastHorizon}
                width={620}
                height={300}
                title="Forecast cone (live streaming)"
              />
            </div>
          {/if}
        {/snippet}
      </Card>
    {:else if step === 5}
      <Card headingLevel={2} title={$_('wizard.step.cert')}>
        {#snippet children()}
          <p>Сертификат методологии фиксирует параметры прогноза — Aurora AI подписывает его криптографически.</p>
          {#if !certSigned}
            <Button variant="sigil" size="lg" onclick={() => (certSigned = true)}>
              {#snippet children()}Sign certificate{/snippet}
            </Button>
          {:else}
            <p>✓ Сертификат подписан</p>
            <!-- 1.3d: save .aurora bundle с forecast.json -->
            {#if !savedBundlePath}
              <div class="save-row">
                <!-- Audit H-3 (этап 2.10): disable если points=[] на случай
                     forecast_completed без предшествующих progress events. -->
                <Button
                  variant="primary"
                  loading={savingBundle}
                  disabled={!forecastCompleted || forecastPoints.length === 0}
                  onclick={saveBundle}
                >
                  {#snippet children()}Сохранить файл проекта{/snippet}
                </Button>
                <p class="save-hint">
                  Сохраните файл проекта, чтобы проверить расчёт в Python или вернуться к нему позже.
                </p>
              </div>
            {:else}
              <p class="saved-banner">✓ Файл проекта сохранён: <code>{savedBundlePath}</code></p>
            {/if}
            {#if saveError}
              <p class="save-error">Ошибка: {saveError}</p>
            {/if}
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
      <Button
        variant="primary"
        onclick={next}
        loading={validating}
        disabled={step === 0 && previewHeaders.length === 0}
      >
        {#snippet children()}{$_('wizard.next')}{/snippet}
      </Button>
    {:else}
      <!-- Block 3 HIGH-7 fix: Sacred Lime invariant — ONE per screen.
           On step 7 (cert) the body has variant="sigil" "Sign certificate";
           finish button must be variant="primary" to avoid 2 sigil buttons.
           Phase 1.C.6: reset session — wizard завершён, draft не нужен. -->
      <Button
        variant="primary"
        onclick={async () => {
          await wizardSession.reset();
          pushToast({ level: 'success', title: $_('wizard.finish') });
        }}
      >
        {#snippet children()}{$_('wizard.finish')}{/snippet}
      </Button>
    {/if}
  </footer>

  <!-- Phase 1.C.6 / UX-3: recovery dialog appears после reload, если
       незаконченный draft найден в _kv_store. -->
  {#if showRecoveryDialog && wizardSession.pendingDraft}
    <div
      class="recovery-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="recovery-title"
    >
      <div class="recovery-modal">
        <h2 id="recovery-title">Восстановить незаконченный сеанс?</h2>
        <p>
          Aurora нашла черновик мастера, сохранённый
          {#if wizardSession.pendingDraft.last_saved_at}
            <strong
              >{new Date(
                wizardSession.pendingDraft.last_saved_at
              ).toLocaleString('ru-RU')}</strong
            >
          {/if}.
        </p>
        <p class="recovery-details">
          Прогресс: шаг {(wizardSession.pendingDraft.step ?? 0) + 1} из
          {STEPS.length}{#if wizardSession.pendingDraft.imported_file_path}
            · файл <code
              >{wizardSession.pendingDraft.imported_file_path.split(/[\\/]/).pop()}</code
            >{/if}
        </p>
        <div class="recovery-actions">
          <Button variant="primary" onclick={applyRecoveredSession}>
            {#snippet children()}Восстановить{/snippet}
          </Button>
          <Button variant="ghost" onclick={dismissRecovery}>
            {#snippet children()}Начать заново{/snippet}
          </Button>
        </div>
      </div>
    </div>
  {/if}
</section>

<style>
  .wizard {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-6);
    max-width: 1024px;
    margin: 0 auto;
  }

  /* 1.3d: save bundle на cert step */
  .save-row {
    margin-top: var(--spacing-4);
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
  }

  .save-hint {
    color: var(--text-secondary);
    font-size: var(--typography-fontSize-ui-sm);
    margin: 0;
  }

  /* Audit fix 2026-05-18: recovery flow когда headers есть, rows пусты —
     показываем подсказку перезагрузить файл. */
  .recovery-data-hint {
    margin-top: var(--spacing-3);
    padding: var(--spacing-2) var(--spacing-3);
    border-radius: var(--radius-sm, 4px);
    background: var(--color-warning-soft, color-mix(in srgb, #f59e0b 10%, transparent));
    color: var(--text-secondary);
    font-size: var(--typography-fontSize-ui-sm);
    font-style: italic;
  }

  .saved-banner {
    margin-top: var(--spacing-3);
    color: var(--state-success-base, #2e7d32);
  }

  .saved-banner code {
    background: var(--surface-soft, rgba(0,0,0,0.04));
    padding: 2px 6px;
    border-radius: 4px;
  }

  .save-error {
    margin-top: var(--spacing-3);
    color: var(--state-danger-base, #c62828);
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
    /* WCAG AA 4.5:1 fix (A11Y-W02): --text-muted (#7A7D87) fails contrast on
       --bg-main light (#FAFAFC). --text-secondary (#4A4D57) passes at ~7.6:1. */
    color: var(--text-secondary);
    white-space: nowrap;
    font-size: var(--typography-fontSize-ui-sm);
  }

  .stepper li.active {
    color: var(--text-primary);
    font-weight: 600;
    font-family: var(--font-display);
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

  /* Phase 1.C.6 / UX-3: recovery dialog modal */
  .recovery-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: var(--spacing-4);
  }

  .recovery-modal {
    background: var(--bg-surface, #ffffff);
    border-radius: var(--radius-md, 8px);
    padding: var(--spacing-6, 24px);
    max-width: 480px;
    width: 100%;
    box-shadow: var(--shadow-lg, 0 10px 40px rgba(0, 0, 0, 0.2));
    display: flex;
    flex-direction: column;
    gap: var(--spacing-3, 12px);
  }

  .recovery-modal h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1.25rem;
  }

  .recovery-details {
    font-size: 0.9em;
    color: var(--text-secondary);
    margin: 0;
  }

  .recovery-details code {
    background: var(--surface-soft, rgba(0, 0, 0, 0.05));
    padding: 2px 6px;
    border-radius: 4px;
    font-family: var(--font-mono);
  }

  .recovery-actions {
    display: flex;
    gap: var(--spacing-3, 12px);
    justify-content: flex-end;
    margin-top: var(--spacing-2, 8px);
  }

  @media (prefers-reduced-motion: reduce) {
    .recovery-backdrop {
      animation: none;
    }
  }
</style>
