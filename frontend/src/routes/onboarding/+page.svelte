<!--
  Onboarding route — Welcome animation → tutorial carousel → CTA → main app.
  Phase Premium P-01.

  Flow:
    1. Mount: show WelcomeAnimation 800ms
    2. After fade complete: render TutorialCarousel
    3. User picks "Открыть пример" → loadSampleBundle → /wizard
    4. User picks "Начать с нуля" → /wizard (no sample preload)
    5. User skips anytime → /
    6. Always: localStorage.setItem('aurora.onboarded', '1') on exit
-->

<script lang="ts">
  import { goto } from '$app/navigation';
  import WelcomeAnimation from '$lib/components/Onboarding/WelcomeAnimation.svelte';
  import CategorySelector from '$lib/components/Onboarding/CategorySelector.svelte';
  import type { BrandCategory } from '$lib/components/Onboarding/CategorySelector.svelte';
  import TutorialCarousel from '$lib/components/Onboarding/TutorialCarousel.svelte';
  import { loadSampleBundle, type SampleScenario } from '$ipc/projects';
  import { pushToast } from '$lib/stores/toast';

  // Phase 2 personalization: category step between animation + tutorial
  let phase = $state<'animation' | 'category' | 'tutorial' | 'loading'>('animation');
  let selectedCategory = $state<BrandCategory | null>(null);

  function markOnboarded(): void {
    try {
      window.localStorage.setItem('aurora.onboarded', '1');
    } catch {
      // localStorage может быть disabled — onboarding seen this session anyway
    }
  }

  function handleAnimationComplete(): void {
    phase = 'category';
  }

  function handleCategorySelect(cat: BrandCategory): void {
    selectedCategory = cat;
    phase = 'tutorial';
  }

  function handleCategorySkip(): void {
    phase = 'tutorial';
  }

  /** Pick sample scenario matching selected category (pharma → kagotsel,
   * fmcg/b2b/other → multi_proxy generic). */
  function pickSampleScenarioForCategory(): SampleScenario {
    if (selectedCategory === 'pharma_otc') return 'kagotsel_venarus';
    return 'multi_proxy';
  }

  async function pickSample(): Promise<void> {
    markOnboarded();
    phase = 'loading';
    try {
      const scenario = pickSampleScenarioForCategory();
      const result = await loadSampleBundle(scenario);
      pushToast({
        level: 'success',
        title: 'Образец загружен',
        body: `Открыт проект «Sample: ${scenario}» (${result.n_periods} периодов)`,
      });
      await goto(`/project/${result.project_uuid}/history`);
    } catch (e) {
      pushToast({
        level: 'danger',
        title: 'Не удалось загрузить образец',
        body: e instanceof Error ? e.message : String(e),
      });
      await goto('/');
    }
  }

  function pickBlank(): void {
    markOnboarded();
    goto('/wizard');
  }

  function skip(): void {
    markOnboarded();
    goto('/');
  }
</script>

<main class="onboarding-page">
  {#if phase === 'animation'}
    <WelcomeAnimation oncomplete={handleAnimationComplete} />
  {:else if phase === 'category'}
    <CategorySelector onselect={handleCategorySelect} onskip={handleCategorySkip} />
  {:else if phase === 'tutorial'}
    <TutorialCarousel onsample={pickSample} onblank={pickBlank} onskip={skip} />
  {:else}
    <div class="loading-state" role="status" aria-live="polite">
      <p>Загружаем пример…</p>
    </div>
  {/if}
</main>

<style>
  .onboarding-page {
    min-height: 80vh;
    display: flex;
    flex-direction: column;
    justify-content: center;
    max-width: 960px;
    margin: 0 auto;
    padding: var(--spacing-4, 1rem);
  }

  .loading-state {
    text-align: center;
    padding: var(--spacing-8, 2rem);
    color: var(--text-secondary, #6b7280);
  }
</style>
