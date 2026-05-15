<!--
  CategorySelector — Phase 2 magical onboarding personalization.

  4-option grid shown between welcome animation + tutorial. Selection
  saved к localStorage 'aurora.category'. Used downstream by smart
  defaults (anchors), sample bundle suggestions, future M-06 pattern
  learning matching.

  Per INV-14 prefers-reduced-motion respected (no animation if user
  disabled).
-->

<script lang="ts">
  import { fadeIn } from '$lib/services/motion';

  export type BrandCategory = 'pharma_otc' | 'fmcg' | 'b2b' | 'other';

  interface CategoryOption {
    id: BrandCategory;
    title: string;
    description: string;
    icon: string;
    example: string;
  }

  interface Props {
    /** Called когда user picks a category. */
    onselect: (category: BrandCategory) => void;
    /** Called когда user skips category step. */
    onskip?: () => void;
  }

  let { onselect, onskip }: Props = $props();

  const OPTIONS: CategoryOption[] = [
    {
      id: 'pharma_otc',
      title: 'Фарма OTC',
      description: 'Безрецептурные препараты',
      icon: '💊',
      example: 'Кагоцел, Венарус, Терафлю',
    },
    {
      id: 'fmcg',
      title: 'FMCG',
      description: 'Товары повседневного спроса',
      icon: '🛒',
      example: 'Косметика, бытовая химия, напитки',
    },
    {
      id: 'b2b',
      title: 'B2B',
      description: 'Корпоративные продукты',
      icon: '🏢',
      example: 'SaaS, услуги, оборудование',
    },
    {
      id: 'other',
      title: 'Другое',
      description: 'Иная категория',
      icon: '📦',
      example: 'Aurora настроится под универсальный сценарий',
    },
  ];

  function pick(id: BrandCategory): void {
    try {
      window.localStorage.setItem('aurora.category', id);
    } catch {
      // Private mode or restricted — ignore
    }
    onselect(id);
  }
</script>

<section class="category-selector" aria-label="Выбор категории бренда">
  <header class="cat-header">
    <h2>Какая у вас категория?</h2>
    <p class="cat-subtitle">
      Aurora настроит примеры, defaults и подсказки под ваш рынок.
    </p>
    {#if onskip}
      <button type="button" class="cat-skip" onclick={onskip}>
        Пропустить →
      </button>
    {/if}
  </header>

  <div class="cat-grid">
    {#each OPTIONS as opt (opt.id)}
      <button
        type="button"
        class="cat-card"
        in:fadeIn={{ duration: 180 }}
        onclick={() => pick(opt.id)}
      >
        <div class="cat-icon" aria-hidden="true">{opt.icon}</div>
        <div class="cat-title">{opt.title}</div>
        <div class="cat-desc">{opt.description}</div>
        <div class="cat-example">{opt.example}</div>
      </button>
    {/each}
  </div>
</section>

<style>
  .category-selector {
    max-width: 720px;
    margin: 0 auto;
    padding: var(--spacing-4, 1rem);
    display: flex;
    flex-direction: column;
    gap: var(--spacing-4, 1rem);
  }

  .cat-header {
    text-align: center;
    position: relative;
  }

  .cat-header h2 {
    font-family: var(--font-display, var(--font-sans, sans-serif));
    font-size: var(--typography-fontSize-display-md, 1.75rem);
    font-weight: 600;
    margin: 0 0 var(--spacing-2, 0.5rem) 0;
    color: var(--text-primary, #111827);
  }

  .cat-subtitle {
    color: var(--text-secondary, #374151);
    font-size: var(--typography-fontSize-ui-md, 1rem);
    margin: 0;
  }

  .cat-skip {
    position: absolute;
    top: 0;
    right: 0;
    background: transparent;
    border: none;
    color: var(--text-muted, #6b7280);
    cursor: pointer;
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    padding: var(--spacing-1, 0.25rem) var(--spacing-2, 0.5rem);
  }

  .cat-skip:hover {
    color: var(--text-primary, #111827);
  }

  .cat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: var(--spacing-3, 0.75rem);
  }

  .cat-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--spacing-2, 0.5rem);
    padding: var(--spacing-4, 1rem);
    background: var(--bg-surface, white);
    border: 2px solid var(--border-subtle, #e5e7eb);
    border-radius: 8px;
    cursor: pointer;
    text-align: center;
    color: inherit;
    font-family: inherit;
    transition:
      transform var(--motion-duration-fast, 80ms) var(--motion-easing-standard, ease),
      border-color var(--motion-duration-fast, 80ms) var(--motion-easing-standard, ease),
      box-shadow var(--motion-duration-normal, 160ms) var(--motion-easing-standard, ease);
  }

  .cat-card:hover {
    transform: translateY(-2px);
    border-color: var(--accent, #2563eb);
    box-shadow: var(--shadow-md, 0 4px 12px rgba(0, 0, 0, 0.08));
  }

  .cat-icon {
    font-size: 2.5rem;
    line-height: 1;
  }

  .cat-title {
    font-weight: 600;
    font-size: var(--typography-fontSize-ui-md, 1rem);
    color: var(--text-primary, #111827);
  }

  .cat-desc {
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    color: var(--text-secondary, #374151);
  }

  .cat-example {
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
    color: var(--text-muted, #6b7280);
    font-style: italic;
    margin-top: var(--spacing-1, 0.25rem);
  }

  @media (prefers-reduced-motion: reduce) {
    .cat-card {
      transition: none;
    }
    .cat-card:hover {
      transform: none;
    }
  }
</style>
