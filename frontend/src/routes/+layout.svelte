<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import { _, isLoading } from 'svelte-i18n';
  import { fly } from 'svelte/transition';

  import { initI18n } from '$lib/i18n';
  import { themeMode, resolvedTheme } from '$lib/stores/theme';
  import { refreshLicense, licenseStatus } from '$lib/stores/license';
  import { activeBundle } from '$lib/stores/bundle';
  import { ipc } from '$ipc/client';
  import { pushToast } from '$lib/stores/toast';

  import Toaster from '$lib/components/Toaster.svelte';
  import PerfFooter from '$lib/components/PerfFooter.svelte';
  import Badge from '$lib/components/Badge.svelte';
  import SaveIndicator from '$lib/components/SaveIndicator.svelte';

  let { children } = $props();

  let feedbackOpen = $state(false);
  let feedbackText = $state('');

  initI18n();

  onMount(async () => {
    document.documentElement.dataset.theme = $resolvedTheme;
    try {
      await refreshLicense();
    } catch (e) {
      console.warn('License refresh failed', e);
    }

    // Cmd+Shift+F → in-app feedback (PREMIUM P10)
    function onKey(e: KeyboardEvent) {
      const isMod = e.metaKey || e.ctrlKey;
      if (isMod && e.shiftKey && (e.key === 'F' || e.key === 'f' || e.code === 'KeyF')) {
        e.preventDefault();
        feedbackOpen = true;
      }
      if (e.key === 'Escape' && feedbackOpen) {
        feedbackOpen = false;
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  async function submitFeedback() {
    if (!feedbackText.trim()) return;
    try {
      await ipc.captureFeedback({ text: feedbackText });
      pushToast({ level: 'success', title: $_('feedback.captured') });
      feedbackText = '';
      feedbackOpen = false;
    } catch (e) {
      pushToast({
        level: 'danger',
        title: 'Feedback capture failed',
        body: String(e)
      });
    }
  }
</script>

<div class="app-layout" data-theme={$resolvedTheme}>
  <header class="app-header">
    <div class="brand">
      <span class="logo" aria-hidden="true">◆</span>
      <span class="brand-name">Aurora Launch</span>
      {#if $licenseStatus.tier === 'dev_bypass'}
        <Badge variant="warning" size="sm">
          {#snippet children()}DEV BYPASS{/snippet}
        </Badge>
      {/if}
    </div>

    <nav class="app-nav" aria-label="Primary navigation">
      <a href="/" data-sveltekit-preload-data="hover">{$_('nav.welcome')}</a>
      <a href="/wizard">{$_('nav.wizard')}</a>
      <a href="/inspector">{$_('nav.inspector')}</a>
      <a href="/compare">{$_('nav.compare')}</a>
      <a href="/history">{$_('nav.history')}</a>
      <a href="/settings">{$_('nav.settings')}</a>
    </nav>

    <div class="header-meta">
      {#if $activeBundle}
        <Badge variant="info" size="sm">
          {#snippet children()}r{$activeBundle.revision}{/snippet}
        </Badge>
      {/if}
    </div>
  </header>

  <main class="app-main">
    {#if $isLoading}
      <div class="loading-screen" aria-busy="true">
        <span class="logo big">◆</span>
        <span>Loading…</span>
      </div>
    {:else}
      {@render children()}
    {/if}
  </main>

  <!-- TODO: wire to wizard save state in Phase Premium P-02 follow-up -->
  <div class="app-footer">
    <SaveIndicator state="unsaved" lastSavedAt={null} />
    <PerfFooter />
  </div>
  <Toaster />

  {#if feedbackOpen}
    <div
      class="feedback-overlay"
      role="dialog"
      aria-labelledby="feedback-title"
      aria-modal="true"
      transition:fly={{ y: 20, duration: 220 }}
    >
      <div class="feedback-card">
        <h3 id="feedback-title">{$_('feedback.title')}</h3>
        <textarea
          bind:value={feedbackText}
          placeholder={$_('feedback.placeholder')}
          rows={6}
        ></textarea>
        <div class="feedback-actions">
          <button type="button" onclick={() => (feedbackOpen = false)}>
            {$_('wizard.cancel')}
          </button>
          <button
            type="button"
            class="primary"
            onclick={submitFeedback}
            disabled={!feedbackText.trim()}
          >
            {$_('feedback.submit')}
          </button>
        </div>
        <p class="feedback-hint">Cmd+Shift+F · Esc to close</p>
      </div>
    </div>
  {/if}
</div>

<style>
  .app-layout {
    display: grid;
    grid-template-rows: auto 1fr auto;
    height: 100vh;
    background: var(--bg-main);
    color: var(--text-primary);
  }

  .app-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--spacing-4);
    padding: 0 var(--spacing-4);
    border-top: 1px solid var(--border-subtle);
    background: var(--bg-surface);
    /* PerfFooter carries its own border-top — neutralise it when nested here */
    :global(.perf-footer) {
      border-top: none;
    }
  }

  .app-header {
    display: grid;
    grid-template-columns: auto 1fr auto;
    align-items: center;
    gap: var(--spacing-6);
    padding: var(--spacing-3) var(--spacing-6);
    background: var(--bg-surface);
    border-bottom: 1px solid var(--border-subtle);
    -webkit-app-region: drag;
  }

  .brand {
    display: flex;
    align-items: center;
    gap: var(--spacing-2);
  }

  .logo {
    color: var(--accent);
    font-size: 20px;
    line-height: 1;
  }

  .logo.big {
    font-size: 64px;
  }

  .brand-name {
    font-family: var(--font-display);
    font-weight: 600;
    font-size: var(--typography-fontSize-ui-h3);
    letter-spacing: -0.01em;
  }

  .app-nav {
    display: flex;
    gap: var(--spacing-4);
    -webkit-app-region: no-drag;
  }

  .app-nav a {
    color: var(--text-secondary);
    text-decoration: none;
    padding: var(--spacing-1) var(--spacing-2);
    border-radius: var(--border-radius-md);
    transition: color var(--motion-fast) var(--easing-smooth);
  }

  .app-nav a:hover,
  .app-nav a[aria-current='page'] {
    color: var(--text-primary);
    background: color-mix(in srgb, var(--accent) 12%, transparent);
  }

  .header-meta {
    display: flex;
    gap: var(--spacing-2);
    -webkit-app-region: no-drag;
  }

  .app-main {
    overflow: auto;
    padding: var(--spacing-6);
    -webkit-app-region: no-drag;
  }

  .loading-screen {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-muted);
    gap: var(--spacing-3);
  }

  /* Feedback overlay */
  .feedback-overlay {
    position: fixed;
    inset: 0;
    background: color-mix(in srgb, var(--bg-main) 70%, transparent);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1100;
  }

  .feedback-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-lg);
    padding: var(--spacing-6);
    width: min(560px, 90%);
    box-shadow: var(--shadow-lg);
    display: flex;
    flex-direction: column;
    gap: var(--spacing-3);
  }

  .feedback-card textarea {
    width: 100%;
    background: var(--bg-main);
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-lg);
    padding: var(--spacing-3);
    color: var(--text-primary);
    font-family: var(--font-sans);
    font-size: var(--typography-fontSize-ui-body);
    resize: vertical;
  }
  .feedback-card textarea:focus {
    outline: none;
    border-color: var(--accent);
  }

  .feedback-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--spacing-2);
  }

  .feedback-actions button {
    background: transparent;
    border: 1px solid var(--border-subtle);
    color: var(--text-primary);
    padding: var(--spacing-2) var(--spacing-4);
    border-radius: var(--border-radius-lg);
    font-family: var(--font-sans);
    cursor: pointer;
  }

  .feedback-actions button.primary {
    background: var(--accent);
    border-color: var(--accent);
    color: white;
  }
  .feedback-actions button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .feedback-hint {
    color: var(--text-muted);
    font-family: var(--font-mono);
    font-size: var(--typography-fontSize-ui-xs);
    text-align: right;
    margin: 0;
  }
</style>
