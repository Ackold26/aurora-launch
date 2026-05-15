<!--
  TutorialCarousel — 5-slide tutorial для first-time users.
  Phase Premium P-01.

  Slides:
    1. Что такое Launch Planner (concept)
    2. Загрузка датасета (data flow)
    3. Прогноз и подтверждение (forecast + trust score)
    4. Сценарии чувствительности (sensitivity)
    5. Сертификат методологии (cryptographic chain)

  Skip-anytime button always visible. Arrow keys navigate.
  Final slide CTA: "Открыть пример" / "Начать с нуля".

  Per INV-14: reduced-motion skips slide transitions, shows static change.
-->

<script lang="ts">
  import { _ } from 'svelte-i18n';

  interface Slide {
    title: string;
    body: string;
    icon?: string;
  }

  interface Props {
    slides?: Slide[];
    /** Called when user clicks "Открыть пример" CTA. */
    onsample?: () => void;
    /** Called when user clicks "Начать с нуля" CTA. */
    onblank?: () => void;
    /** Called when user clicks skip OR finishes tutorial. */
    onskip?: () => void;
  }

  let { slides: slidesProp = undefined as Slide[] | undefined, onsample, onblank, onskip }: Props = $props();

  // Default slides derived from locale — reactive to language switch (INV-25).
  const defaultSlides = $derived<Slide[]>([
    { title: $_('onboarding.tutorial.slide1.title'), body: $_('onboarding.tutorial.slide1.body'), icon: '🎯' },
    { title: $_('onboarding.tutorial.slide2.title'), body: $_('onboarding.tutorial.slide2.body'), icon: '📊' },
    { title: $_('onboarding.tutorial.slide3.title'), body: $_('onboarding.tutorial.slide3.body'), icon: '📈' },
    { title: $_('onboarding.tutorial.slide4.title'), body: $_('onboarding.tutorial.slide4.body'), icon: '🎛' },
    { title: $_('onboarding.tutorial.slide5.title'), body: $_('onboarding.tutorial.slide5.body'), icon: '🔐' },
  ]);

  const slides = $derived(slidesProp ?? defaultSlides);

  let currentIndex = $state(0);
  let total = $derived(slides.length);
  let isLast = $derived(currentIndex === total - 1);
  let currentSlide = $derived(slides[currentIndex] ?? slides[0]);

  function next(): void {
    if (currentIndex < total - 1) currentIndex += 1;
  }

  function prev(): void {
    if (currentIndex > 0) currentIndex -= 1;
  }

  function skip(): void {
    onskip?.();
  }

  function pickSample(): void {
    onsample?.();
  }

  function pickBlank(): void {
    onblank?.();
  }

  function handleKey(e: KeyboardEvent): void {
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      next();
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      prev();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      skip();
    }
  }
</script>

<svelte:window onkeydown={handleKey} />

<section class="tutorial" aria-label={$_("onboarding.tutorial.section_label")}>
  <header class="tutorial-header">
    <div class="dots" role="tablist" aria-label={$_("onboarding.tutorial.progress_label")}>
      {#each slides as _slide, i (i)}
        <button
          type="button"
          class="dot"
          class:active={i === currentIndex}
          role="tab"
          aria-selected={i === currentIndex}
          aria-label={$_("onboarding.tutorial.slide_label", { values: { index: i + 1 } })}
          onclick={() => (currentIndex = i)}
        ></button>
      {/each}
    </div>

    <button type="button" class="skip-btn" onclick={skip}>
      {$_("onboarding.tutorial.skip")}
    </button>
  </header>

  <article class="slide" role="tabpanel" aria-live="polite">
    {#if currentSlide?.icon}
      <div class="slide-icon" aria-hidden="true">{currentSlide.icon}</div>
    {/if}
    <h2 class="slide-title">{currentSlide?.title}</h2>
    <p class="slide-body">{currentSlide?.body}</p>
  </article>

  <footer class="tutorial-footer">
    <button
      type="button"
      class="btn btn-ghost"
      onclick={prev}
      disabled={currentIndex === 0}
      aria-label={$_("onboarding.tutorial.prev_label")}
    >
      {$_("onboarding.tutorial.prev")}
    </button>

    <div class="position-indicator" aria-hidden="true">
      {$_("onboarding.tutorial.position", { values: { current: currentIndex + 1, total } })}
    </div>

    {#if !isLast}
      <button
        type="button"
        class="btn btn-primary"
        onclick={next}
        aria-label={$_("onboarding.tutorial.next_label")}
      >
        {$_("onboarding.tutorial.next")}
      </button>
    {:else}
      <div class="final-ctas">
        <button type="button" class="btn btn-primary" onclick={pickSample}>
          {$_("onboarding.tutorial.cta_sample")}
        </button>
        <button type="button" class="btn btn-ghost" onclick={pickBlank}>
          {$_("onboarding.tutorial.cta_blank")}
        </button>
      </div>
    {/if}
  </footer>
</section>

<style>
  .tutorial {
    max-width: 720px;
    margin: 0 auto;
    padding: var(--spacing-4, 1rem);
    display: flex;
    flex-direction: column;
    gap: var(--spacing-4, 1rem);
    min-height: 480px;
  }

  .tutorial-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .dots {
    display: flex;
    gap: var(--spacing-2, 0.5rem);
  }

  .dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    border: 1px solid var(--border-default, #d1d5db);
    background: var(--surface-base, white);
    cursor: pointer;
    padding: 0;
    transition:
      background-color var(--motion-duration-fast, 80ms) var(--motion-easing-standard, ease),
      transform       var(--motion-duration-fast, 80ms) var(--motion-easing-spring-soft, cubic-bezier(0.34,1.56,0.64,1));
  }

  .dot.active {
    background: var(--accent, #2563eb);
    border-color: var(--accent, #2563eb);
    transform: scale(1.2);
  }

  .skip-btn {
    background: transparent;
    border: none;
    color: var(--text-secondary, #6b7280);
    cursor: pointer;
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    padding: var(--spacing-1, 0.25rem) var(--spacing-2, 0.5rem);
  }

  .skip-btn:hover {
    color: var(--text-primary, #111827);
  }

  .slide {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--spacing-3, 0.75rem);
    text-align: center;
    padding: var(--spacing-6, 1.5rem) var(--spacing-4, 1rem);
  }

  .slide-icon {
    font-size: 3rem;
    line-height: 1;
  }

  .slide-title {
    font-family: var(--font-display, var(--font-sans, sans-serif));
    font-size: var(--typography-fontSize-display-md, 1.75rem);
    font-weight: 600;
    margin: 0;
    color: var(--text-primary, #111827);
  }

  .slide-body {
    font-size: var(--typography-fontSize-ui-md, 1rem);
    line-height: 1.6;
    color: var(--text-secondary, #374151);
    max-width: 560px;
    margin: 0;
  }

  .tutorial-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--spacing-3, 0.75rem);
  }

  .position-indicator {
    font-family: var(--font-mono, monospace);
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    color: var(--text-muted, #6b7280);
  }

  .final-ctas {
    display: flex;
    gap: var(--spacing-2, 0.5rem);
  }

  .btn {
    padding: 0.5rem 1rem;
    border-radius: 6px;
    border: 1px solid transparent;
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    cursor: pointer;
    transition:
      background-color var(--motion-duration-normal, 160ms) var(--motion-easing-standard, ease),
      border-color     var(--motion-duration-normal, 160ms) var(--motion-easing-standard, ease);
  }

  .btn-primary {
    background: var(--accent, #2563eb);
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    background: var(--accent-hover, #1d4ed8);
  }

  .btn-ghost {
    background: transparent;
    border-color: var(--border-default, #d1d5db);
    color: var(--text-primary, #111827);
  }

  .btn-ghost:hover:not(:disabled) {
    background: var(--surface-hover, #f9fafb);
  }

  .btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  /* Reduced motion — INV-14 (tokens.css already zeroes --motion-duration-*
     under this media query; explicit none is belt-and-suspenders for components
     that use shorthand transition without CSS variable durations). */
  @media (prefers-reduced-motion: reduce) {
    .dot,
    .btn {
      transition: none;
    }
    .dot.active {
      transform: none;
    }
  }
</style>
