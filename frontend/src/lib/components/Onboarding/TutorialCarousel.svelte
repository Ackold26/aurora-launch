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

  const DEFAULT_SLIDES: Slide[] = [
    {
      title: 'Прогноз запуска нового бренда',
      body: 'Aurora Launch Planner строит прогноз продаж для бренда, у которого пока нет своих данных, используя похожий бренд как «прокси».',
      icon: '🎯',
    },
    {
      title: 'Загрузка данных',
      body: 'Принимаем XLSX из Эконометрики, .aurora-бандлы из Data Studio, или подключение к корпоративным источникам.',
      icon: '📊',
    },
    {
      title: 'Прогноз и подтверждение',
      body: 'Алгоритм даёт точечный прогноз + доверительный интервал. Шкала «Доверие» оценивает надёжность одним числом (0–100).',
      icon: '📈',
    },
    {
      title: 'Сценарии чувствительности',
      body: 'Один клик — три сценария: пессимистичный, базовый, оптимистичный. Эксперт-режим разворачивает 6 параметров чувствительности.',
      icon: '🎛',
    },
    {
      title: 'Сертификат методологии',
      body: 'Каждый прогноз подписан Ed25519. Можно проверить независимо через verify.auroraai.pro — алгоритм публичен.',
      icon: '🔐',
    },
  ];

  let { slides = DEFAULT_SLIDES, onsample, onblank, onskip }: Props = $props();

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

<section class="tutorial" aria-label="Учебник Aurora Launch Planner">
  <header class="tutorial-header">
    <div class="dots" role="tablist" aria-label="Прогресс учебника">
      {#each slides as _, i (i)}
        <button
          type="button"
          class="dot"
          class:active={i === currentIndex}
          role="tab"
          aria-selected={i === currentIndex}
          aria-label={`Слайд ${i + 1}`}
          onclick={() => (currentIndex = i)}
        ></button>
      {/each}
    </div>

    <button type="button" class="skip-btn" onclick={skip}>
      Пропустить →
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
      aria-label="Предыдущий слайд"
    >
      ← Назад
    </button>

    <div class="position-indicator" aria-hidden="true">
      {currentIndex + 1} / {total}
    </div>

    {#if !isLast}
      <button
        type="button"
        class="btn btn-primary"
        onclick={next}
        aria-label="Следующий слайд"
      >
        Далее →
      </button>
    {:else}
      <div class="final-ctas">
        <button type="button" class="btn btn-primary" onclick={pickSample}>
          Открыть пример
        </button>
        <button type="button" class="btn btn-ghost" onclick={pickBlank}>
          Начать с нуля
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
    transition: background-color 150ms ease, transform 150ms ease;
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
    transition: background-color 120ms ease, border-color 120ms ease;
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
