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
  import TutorialCarousel from '$lib/components/Onboarding/TutorialCarousel.svelte';
  import { loadSampleBundle } from '$ipc/projects';
  import { pushToast } from '$lib/stores/toast';

  let phase = $state<'animation' | 'tutorial' | 'loading'>('animation');

  function markOnboarded(): void {
    try {
      window.localStorage.setItem('aurora.onboarded', '1');
    } catch {
      // localStorage может быть disabled — onboarding seen this session anyway
    }
  }

  function handleAnimationComplete(): void {
    phase = 'tutorial';
  }

  async function pickSample(): Promise<void> {
    markOnboarded();
    phase = 'loading';
    try {
      // Default sample: Кагоцел РФ → Венарус (pharma OTC scenario)
      const result = await loadSampleBundle('kagotsel_venarus');
      pushToast({
        level: 'success',
        title: 'Образец загружен',
        body: `Открыт проект «Sample: kagotsel_venarus» (${result.n_periods} периодов)`,
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
