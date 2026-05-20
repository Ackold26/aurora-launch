<!--
  EmptyDashboard — Sprint 1 UX Foundation, first-run differentiated experience.

  Shown когда `pending_count === 0 && active_count === 0` (no projects yet).
  Goal — turn empty state into a 60-second guided tour of Aurora's value
  prop через sample bundle preview + methodology highlights + clear CTA.

  Composition:
    - Hero c brand wordmark + tagline
    - Sample preview card (load_sample_bundle CTA — primary sigil)
    - Methodology highlights (4 short tips)
    - Hint: «После первого запуска эта страница превратится в ваш Workspace»
-->

<script lang="ts">
  import { _ } from 'svelte-i18n';
  import { goto } from '$app/navigation';
  import { loadSampleBundle } from '$lib/ipc/projects';
  import { pushToast } from '$lib/stores/toast';

  interface Props {
    /** Optional override для default sample scenario ID. */
    sampleScenario?: 'kagotsel_venarus' | 'venarus_baseline' | 'multi_proxy';
  }

  let { sampleScenario = 'kagotsel_venarus' }: Props = $props();

  let loadingSample: boolean = $state(false);

  async function handleLoadSample(): Promise<void> {
    if (loadingSample) return;
    loadingSample = true;
    try {
      const result = await loadSampleBundle(sampleScenario);
      await goto(`/inspector?project=${result.project_uuid}`);
    } catch (e) {
      pushToast({
        level: 'danger',
        title: $_('dashboard.empty.sample_error_title'),
        body: String(e),
      });
      loadingSample = false;
    }
  }

  function handleNewLaunch(): void {
    void goto('/wizard');
  }

  // 4 methodology highlights as static data (i18n keys provide labels).
  const HIGHLIGHTS = [
    { icon: '◆', key: 'proxy_dimensions' },
    { icon: '◇', key: 'transfer_engine' },
    { icon: '◈', key: 'credible_intervals' },
    { icon: '✦', key: 'signed_certificate' },
  ] as const;
</script>

<section
  class="empty-dashboard"
  aria-label={$_('dashboard.empty.aria_label')}
>
  <header class="empty-hero">
    <p class="empty-eyebrow">{$_('dashboard.empty.eyebrow')}</p>
    <h1 class="empty-title">{$_('dashboard.empty.title')}</h1>
    <p class="empty-tagline">{$_('dashboard.empty.tagline')}</p>
  </header>

  <article class="sample-card">
    <div class="sample-card__content">
      <span class="sample-card__badge">{$_('dashboard.empty.sample_badge')}</span>
      <h2 class="sample-card__title">{$_('dashboard.empty.sample_title')}</h2>
      <p class="sample-card__body">{$_('dashboard.empty.sample_body')}</p>
      <ul class="sample-card__bullets">
        <li>{$_('dashboard.empty.sample_bullet_1')}</li>
        <li>{$_('dashboard.empty.sample_bullet_2')}</li>
        <li>{$_('dashboard.empty.sample_bullet_3')}</li>
      </ul>
    </div>
    <div class="sample-card__actions">
      <button
        type="button"
        class="cta cta--sigil"
        onclick={handleLoadSample}
        disabled={loadingSample}
        aria-busy={loadingSample}
      >
        {#if loadingSample}
          <span class="cta__spinner" aria-hidden="true"></span>
          {$_('dashboard.empty.sample_loading')}
        {:else}
          {$_('dashboard.empty.sample_cta')}
        {/if}
      </button>
      <button
        type="button"
        class="cta cta--ghost"
        onclick={handleNewLaunch}
        disabled={loadingSample}
      >
        {$_('dashboard.empty.new_launch_cta')}
      </button>
    </div>
  </article>

  <section class="highlights" aria-label={$_('dashboard.empty.highlights_label')}>
    <h2 class="highlights-title">{$_('dashboard.empty.highlights_title')}</h2>
    <ul class="highlights-list">
      {#each HIGHLIGHTS as item (item.key)}
        <li class="highlight">
          <span class="highlight-icon" aria-hidden="true">{item.icon}</span>
          <div class="highlight-body">
            <p class="highlight-label">{$_(`dashboard.empty.highlight.${item.key}.label`)}</p>
            <p class="highlight-text">{$_(`dashboard.empty.highlight.${item.key}.text`)}</p>
          </div>
        </li>
      {/each}
    </ul>
  </section>

  <footer class="empty-hint">
    <span class="hint-icon" aria-hidden="true">↻</span>
    <p>{$_('dashboard.empty.hint')}</p>
  </footer>
</section>

<style>
  .empty-dashboard {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-8);
    max-width: var(--sizing-ui-containerMax, 1100px);
    margin: 0 auto;
    padding: var(--spacing-6) 0;
  }

  /* ── Hero ────────────────────────────────────────────────────────────────── */

  .empty-hero {
    text-align: center;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
    align-items: center;
  }

  .empty-eyebrow {
    margin: 0;
    color: var(--accent);
    font-family: var(--font-mono);
    font-size: var(--typography-fontSize-ui-xs);
    font-weight: var(--typography-fontWeight-medium);
    text-transform: uppercase;
    letter-spacing: 0.12em;
  }

  .empty-title {
    margin: 0;
    color: var(--text-primary);
    font-family: var(--font-display);
    font-size: var(--typography-fontSize-display-lg);
    font-weight: var(--typography-fontWeight-bold);
    line-height: var(--typography-lineHeight-tight);
    letter-spacing: -0.02em;
  }

  .empty-tagline {
    margin: 0;
    color: var(--text-secondary);
    font-size: var(--typography-fontSize-ui-h3);
    line-height: var(--typography-lineHeight-normal);
    max-width: 56ch;
  }

  /* ── Sample card ─────────────────────────────────────────────────────────── */

  .sample-card {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: var(--spacing-6);
    align-items: center;
    background: linear-gradient(
      135deg,
      color-mix(in srgb, var(--accent) 8%, var(--bg-surface)) 0%,
      var(--bg-surface) 100%
    );
    border: 1px solid color-mix(in srgb, var(--accent) 25%, var(--border-subtle));
    border-radius: var(--border-radius-lg);
    padding: var(--spacing-6);
    box-shadow: var(--shadow-md);
  }

  .sample-card__content {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
    min-width: 0;
  }

  .sample-card__badge {
    align-self: flex-start;
    padding: var(--spacing-1) var(--spacing-3);
    background: color-mix(in srgb, var(--accent-sigil) 18%, transparent);
    border: 1px solid color-mix(in srgb, var(--accent-sigil) 40%, transparent);
    border-radius: var(--border-radius-sm);
    color: var(--accent-sigil);
    font-family: var(--font-mono);
    font-size: var(--typography-fontSize-ui-xs);
    font-weight: var(--typography-fontWeight-bold);
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  .sample-card__title {
    margin: 0;
    color: var(--text-primary);
    font-family: var(--font-display);
    font-size: var(--typography-fontSize-ui-h2);
    font-weight: var(--typography-fontWeight-medium);
    line-height: var(--typography-lineHeight-snug);
  }

  .sample-card__body {
    margin: 0;
    color: var(--text-secondary);
    font-size: var(--typography-fontSize-ui-body);
    line-height: var(--typography-lineHeight-normal);
  }

  .sample-card__bullets {
    list-style: none;
    margin: var(--spacing-2) 0 0 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1);
  }

  .sample-card__bullets li {
    color: var(--text-secondary);
    font-size: var(--typography-fontSize-ui-sm);
    line-height: var(--typography-lineHeight-normal);
    padding-left: var(--spacing-4);
    position: relative;
  }

  .sample-card__bullets li::before {
    content: '·';
    color: var(--accent);
    position: absolute;
    left: var(--spacing-2);
    font-weight: var(--typography-fontWeight-bold);
  }

  .sample-card__actions {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
    align-items: stretch;
    flex-shrink: 0;
    min-width: 220px;
  }

  /* ── CTAs ────────────────────────────────────────────────────────────────── */

  .cta {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--spacing-2);
    padding: var(--spacing-3) var(--spacing-5, var(--spacing-4));
    border-radius: var(--border-radius-md);
    font-family: var(--font-sans);
    font-size: var(--typography-fontSize-ui-body);
    font-weight: var(--typography-fontWeight-medium);
    cursor: pointer;
    border: 1px solid transparent;
    transition:
      transform var(--motion-default) var(--easing-spring),
      box-shadow var(--motion-default) var(--easing-smooth),
      background var(--motion-default) var(--easing-smooth);
  }

  .cta:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .cta:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .cta--sigil {
    background: var(--accent-sigil);
    color: var(--color-brand-deep-100, #0a1628);
    border-color: var(--accent-sigil);
    font-weight: var(--typography-fontWeight-bold);
  }

  .cta--sigil:not(:disabled):hover {
    transform: translateY(-1px);
    box-shadow: 0 0 28px color-mix(in srgb, var(--accent-sigil) 45%, transparent);
  }

  .cta--ghost {
    background: transparent;
    color: var(--text-primary);
    border-color: var(--border-subtle);
  }

  .cta--ghost:not(:disabled):hover {
    border-color: var(--accent);
    color: var(--accent);
  }

  .cta__spinner {
    width: 14px;
    height: 14px;
    border: 2px solid currentColor;
    border-right-color: transparent;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  /* ── Methodology highlights ─────────────────────────────────────────────── */

  .highlights {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-4);
  }

  .highlights-title {
    margin: 0;
    color: var(--text-primary);
    font-family: var(--font-display);
    font-size: var(--typography-fontSize-ui-h3);
    font-weight: var(--typography-fontWeight-medium);
    text-align: center;
  }

  .highlights-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: var(--spacing-4);
  }

  .highlight {
    display: flex;
    gap: var(--spacing-3);
    align-items: flex-start;
    padding: var(--spacing-4);
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-md);
    transition: border-color var(--motion-default) var(--easing-smooth);
  }

  .highlight:hover {
    border-color: color-mix(in srgb, var(--accent) 30%, var(--border-subtle));
  }

  .highlight-icon {
    color: var(--accent);
    font-size: var(--typography-fontSize-ui-h2);
    line-height: 1;
    flex-shrink: 0;
  }

  .highlight-body {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1);
    min-width: 0;
  }

  .highlight-label {
    margin: 0;
    color: var(--text-primary);
    font-size: var(--typography-fontSize-ui-body);
    font-weight: var(--typography-fontWeight-medium);
  }

  .highlight-text {
    margin: 0;
    color: var(--text-muted);
    font-size: var(--typography-fontSize-ui-sm);
    line-height: var(--typography-lineHeight-normal);
  }

  /* ── Hint footer ─────────────────────────────────────────────────────────── */

  .empty-hint {
    display: flex;
    gap: var(--spacing-3);
    align-items: center;
    justify-content: center;
    padding: var(--spacing-3) var(--spacing-4);
    background: color-mix(in srgb, var(--accent) 5%, var(--bg-surface));
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-md);
    color: var(--text-muted);
    font-size: var(--typography-fontSize-ui-sm);
    text-align: center;
  }

  .empty-hint p {
    margin: 0;
  }

  .hint-icon {
    color: var(--accent);
    font-size: var(--typography-fontSize-ui-h3);
    line-height: 1;
  }

  /* ── Responsive ──────────────────────────────────────────────────────────── */

  @media (max-width: 768px) {
    .sample-card {
      grid-template-columns: 1fr;
    }
    .sample-card__actions {
      min-width: 0;
    }
  }

  /* ── INV-14 reduced motion ───────────────────────────────────────────────── */

  @media (prefers-reduced-motion: reduce) {
    .cta,
    .highlight {
      transition: none;
    }
    .cta__spinner {
      animation: none;
    }
  }
</style>
