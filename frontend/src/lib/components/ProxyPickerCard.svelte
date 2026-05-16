<!--
  ProxyPickerCard — Step 2 wizard: choose proxy bundle.

  Lets the user pick one of up to 3 sample bundles (radio-card semantics)
  OR upload their own .aurora file via the Tauri dialog plugin.

  Props (Svelte 5 $bindable):
    selectedPath  — filesystem path of the chosen bundle (null = none selected)
    selectedLabel — human-readable label for next-step display

  On mount: calls ipc.listSampleBundles() to populate cards. Cards with
  exists=false render as disabled.

  A11y:
    - radiogroup + aria-label on sample-cards container
    - Each card is a <button aria-pressed> (card semantics, not native radio)
    - Keyboard: Tab navigates, Space/Enter selects
    - prefers-reduced-motion: transition disabled via CSS media query

  INV-14: no JS-driven animation; CSS transition only + reduced-motion guard.
-->

<script lang="ts">
  import { onMount } from 'svelte';
  import { ipc } from '$ipc/client';
  import { open as openDialog } from '@tauri-apps/plugin-dialog';

  interface Props {
    /** Bindable: selected proxy path (null if nothing selected). */
    selectedPath: string | null;
    /** Bindable: selected proxy human label (shown in next steps). */
    selectedLabel: string | null;
  }

  let {
    selectedPath = $bindable(),
    selectedLabel = $bindable(),
  }: Props = $props();

  // ── State ──────────────────────────────────────────────────────────────────

  type SampleBundle = { id: string; path: string; label: string; exists: boolean };

  let bundles = $state<SampleBundle[]>([]);
  let loading = $state<boolean>(true);
  let errorMsg = $state<string | null>(null);

  // ── Mount: fetch sample bundles ────────────────────────────────────────────

  onMount(async () => {
    try {
      const result = await ipc.listSampleBundles();
      bundles = result.bundles;
    } catch (err) {
      errorMsg =
        err instanceof Error
          ? err.message
          : 'Не удалось загрузить список примеров. Попробуйте перезапустить.';
    } finally {
      loading = false;
    }
  });

  // ── Helpers ────────────────────────────────────────────────────────────────

  function selectBundle(bundle: SampleBundle): void {
    if (!bundle.exists) return;
    selectedPath = bundle.path;
    selectedLabel = bundle.label;
  }

  async function handleUpload(): Promise<void> {
    try {
      const chosen = await openDialog({
        multiple: false,
        filters: [{ name: 'Aurora bundle', extensions: ['aurora'] }],
      });
      if (chosen) {
        // With multiple:false + no directory flag, Tauri returns string | null.
        // `chosen` is guaranteed string here after the truthiness guard.
        const filePath: string = chosen;
        selectedPath = filePath;
        // Extract basename for the label.
        const basename = filePath.split(/[\\/]/).pop() ?? filePath;
        selectedLabel = `Свой файл: ${basename}`;
      }
    } catch {
      // User cancelled — no-op.
    }
  }
</script>

<section class="proxy-picker">
  <header class="picker-header">
    <h2 class="picker-heading">Шаг 2 — Выберите прокси-бренд</h2>
    <p class="picker-subtitle">
      Aurora использует данные похожего бренда как образец для прогноза
    </p>
  </header>

  <!-- Sample bundle cards -->
  {#if loading}
    <p class="loading-msg" aria-live="polite" aria-busy="true">Загружаем примеры…</p>
  {:else if errorMsg}
    <p class="error-msg" role="alert">{errorMsg}</p>
  {:else}
    <div
      class="card-grid"
      role="radiogroup"
      aria-label="Выбор прокси-бренда"
    >
      {#each bundles as bundle (bundle.id)}
        {@const isSelected =
          selectedPath !== null && selectedPath === bundle.path}
        <button
          type="button"
          class="bundle-card"
          class:card-selected={isSelected}
          class:card-disabled={!bundle.exists}
          aria-pressed={isSelected}
          aria-disabled={!bundle.exists}
          disabled={!bundle.exists}
          onclick={() => selectBundle(bundle)}
        >
          <span class="card-label">{bundle.label}</span>
          <span class="card-sub">
            Готовый пример Aurora
            {#if bundle.exists}
              · <span class="card-available">✓ Файл доступен</span>
            {:else}
              · <span class="card-unavailable">Файл не найден</span>
            {/if}
          </span>
        </button>
      {/each}
    </div>
  {/if}

  <!-- Divider -->
  <div class="divider" aria-hidden="true"><span class="divider-label">или</span></div>

  <!-- Custom upload -->
  <button
    type="button"
    class="upload-btn"
    onclick={handleUpload}
  >
    📁 Загрузить свой .aurora файл
  </button>

  <!-- Selection indicator -->
  {#if selectedLabel !== null}
    <p class="selected-indicator" aria-live="polite">
      Выбран: <strong>{selectedLabel}</strong>
    </p>
  {/if}
</section>

<style>
  .proxy-picker {
    display: flex;
    flex-direction: column;
    gap: var(--space-lg, 1.5rem);
  }

  /* ── Header ──────────────────────────────────────────────────────────────── */

  .picker-header {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs, 0.25rem);
  }

  .picker-heading {
    margin: 0;
    font-size: var(--typography-fontSize-ui-lg, 1.125rem);
    font-weight: var(--typography-fontWeight-semibold, 600);
    color: var(--text-primary, var(--color-ui-text-primary, #eaeaf0));
  }

  .picker-subtitle {
    margin: 0;
    font-size: 0.95em;
    color: var(--text-muted, var(--color-ui-text-muted, #7a7a90));
  }

  /* ── Loading / Error ─────────────────────────────────────────────────────── */

  .loading-msg {
    color: var(--text-secondary, var(--color-ui-text-secondary, #a8a8b8));
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
  }

  .error-msg {
    color: var(--color-semantic-error, #ef4444);
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
  }

  /* ── Card grid ───────────────────────────────────────────────────────────── */

  .card-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: var(--space-md, 1rem);
  }

  .bundle-card {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs, 0.25rem);
    padding: var(--space-md, 1rem);
    border: 1px solid var(--color-border, var(--color-ui-bg-border, #2a2d37));
    border-radius: var(--radius-md, 8px);
    background: var(--bg-surface, var(--color-ui-bg-surface, #1a1d27));
    color: inherit;
    font-family: inherit;
    font-size: inherit;
    text-align: left;
    cursor: pointer;
    transition: var(--motion-card-hover, transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease);
  }

  .bundle-card:not(.card-disabled):hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md, 0 4px 12px rgba(0, 0, 0, 0.1));
  }

  .bundle-card:not(.card-disabled):focus-visible {
    outline: 2px solid var(--color-ui-accent-primary, #2e5bff);
    outline-offset: 2px;
  }

  .card-selected {
    border-color: var(--color-ui-accent-primary, #2e5bff);
    background: var(--color-accent-soft, #eef2ff);
    color: var(--text-primary, var(--color-ui-text-primary, #111827));
  }

  .card-disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .card-label {
    font-weight: var(--typography-fontWeight-medium, 500);
    color: inherit;
  }

  .card-sub {
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
    color: var(--text-muted, var(--color-ui-text-muted, #7a7a90));
  }

  .card-available {
    color: var(--color-semantic-success, #10b981);
  }

  .card-unavailable {
    color: var(--color-semantic-error, #ef4444);
  }

  /* ── Divider ─────────────────────────────────────────────────────────────── */

  .divider {
    display: flex;
    align-items: center;
    gap: var(--space-sm, 0.5rem);
    margin: var(--space-lg, 1.5rem) 0;
  }

  .divider::before,
  .divider::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--color-border, var(--color-ui-bg-border, #2a2d37));
  }

  .divider-label {
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    color: var(--text-muted, var(--color-ui-text-muted, #7a7a90));
    white-space: nowrap;
  }

  /* ── Upload button ───────────────────────────────────────────────────────── */

  .upload-btn {
    align-self: flex-start;
    padding: var(--space-md, 1rem) var(--space-lg, 1.5rem);
    border: 2px dashed var(--color-border, var(--color-ui-bg-border, #2a2d37));
    border-radius: var(--radius-md, 8px);
    background: transparent;
    color: var(--text-secondary, var(--color-ui-text-secondary, #a8a8b8));
    font-family: inherit;
    font-size: inherit;
    cursor: pointer;
    transition: border-color 0.15s ease, color 0.15s ease;
  }

  .upload-btn:hover {
    border-color: var(--color-ui-accent-primary, #2e5bff);
    color: var(--text-primary, var(--color-ui-text-primary, #eaeaf0));
  }

  .upload-btn:focus-visible {
    outline: 2px solid var(--color-ui-accent-primary, #2e5bff);
    outline-offset: 2px;
  }

  /* ── Selected indicator ──────────────────────────────────────────────────── */

  .selected-indicator {
    margin: 0;
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    color: var(--text-secondary, var(--color-ui-text-secondary, #a8a8b8));
  }

  .selected-indicator strong {
    color: var(--text-primary, var(--color-ui-text-primary, #eaeaf0));
  }

  /* ── prefers-reduced-motion ──────────────────────────────────────────────── */

  @media (prefers-reduced-motion: reduce) {
    .bundle-card {
      transition: none;
    }
    .bundle-card:not(.card-disabled):hover {
      transform: none;
    }
    .upload-btn {
      transition: none;
    }
  }
</style>
