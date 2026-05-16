<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import { _, isLoading, locale } from 'svelte-i18n';
  import { fly } from 'svelte/transition';
  import { goto } from '$app/navigation';
  import { page } from '$app/state';

  import { initI18n } from '$lib/i18n';
  import { themeMode, resolvedTheme } from '$lib/stores/theme';
  import { refreshLicense, licenseStatus } from '$lib/stores/license';
  import { activeBundle, isDirty, lastSavedAt, saveBundleTo } from '$lib/stores/bundle';
  import { ipc } from '$ipc/client';
  import { pushToast } from '$lib/stores/toast';
  import { track, initTelemetryInternal } from '$lib/services/telemetry';

  import Toaster from '$lib/components/Toaster.svelte';
  import PerfFooter from '$lib/components/PerfFooter.svelte';
  import Badge from '$lib/components/Badge.svelte';
  import SaveIndicator from '$lib/components/SaveIndicator.svelte';
  import CommandPalette from '$lib/components/CommandPalette.svelte';
  import HandshakeIncompatibleModal from '$lib/components/HandshakeIncompatibleModal.svelte';
  import UpdateAvailableBanner from '$lib/components/UpdateAvailableBanner.svelte';
  import RefreshAvailableBanner from '$lib/components/RefreshAvailableBanner.svelte';

  let { children } = $props();

  let feedbackOpen = $state(false);
  let feedbackText = $state('');
  let commandPaletteOpen = $state(false);
  let saving = $state(false);

  // H-5 (audit 4.5 / Phase 1.A): focus management для feedback overlay.
  let feedbackTextareaEl = $state<HTMLTextAreaElement | undefined>(undefined);
  let feedbackSubmitButtonEl = $state<HTMLButtonElement | undefined>(undefined);

  /** Focus trap: Shift+Tab из textarea → submit; Tab из submit → textarea. */
  function feedbackTrapFocus(e: KeyboardEvent): void {
    if (e.key !== 'Tab') return;
    const active = document.activeElement;
    if (e.shiftKey && active === feedbackTextareaEl && feedbackSubmitButtonEl) {
      e.preventDefault();
      feedbackSubmitButtonEl.focus();
    } else if (!e.shiftKey && active === feedbackSubmitButtonEl && feedbackTextareaEl) {
      e.preventDefault();
      feedbackTextareaEl.focus();
    }
  }

  // Autofocus textarea когда overlay открывается. requestAnimationFrame даёт
  // transition'у смонтироваться — иначе focus игнорируется на element ещё не в DOM.
  $effect(() => {
    if (feedbackOpen && feedbackTextareaEl) {
      requestAnimationFrame(() => feedbackTextareaEl?.focus());
    }
  });

  // PA-A02 fix: derive SaveIndicator state from bundle stores (was hardcoded "unsaved")
  const saveState = $derived.by<'saved' | 'saving' | 'unsaved'>(() => {
    if (saving) return 'saving';
    if ($isDirty) return 'unsaved';
    if ($lastSavedAt) return 'saved';
    return 'unsaved';
  });

  // PA-A04 + QW4 i18n: CommandPalette commands reactive к locale.
  // $_ subscription makes commands re-derive when language switches.
  const commands = $derived([
    {
      id: 'nav-welcome',
      label: $_('palette.nav.welcome'),
      description: $_('palette.nav.welcome.desc'),
      category: $_('palette.category.nav'),
      action: () => goto('/'),
    },
    {
      id: 'nav-wizard',
      label: $_('palette.nav.wizard'),
      description: $_('palette.nav.wizard.desc'),
      category: $_('palette.category.nav'),
      action: () => goto('/wizard'),
    },
    {
      id: 'nav-inspector',
      label: $_('palette.nav.inspector'),
      description: $_('palette.nav.inspector.desc'),
      category: $_('palette.category.nav'),
      action: () => goto('/inspector'),
    },
    {
      id: 'nav-history',
      label: $_('palette.nav.history'),
      description: $_('palette.nav.history.desc'),
      category: $_('palette.category.nav'),
      action: () => goto('/history'),
    },
    {
      id: 'nav-settings',
      label: $_('palette.nav.settings'),
      description: $_('palette.nav.settings.desc'),
      category: $_('palette.category.settings'),
      action: () => goto('/settings'),
    },
    {
      id: 'nav-onboarding',
      label: $_('palette.nav.onboarding'),
      description: $_('palette.nav.onboarding.desc'),
      category: $_('palette.category.help'),
      action: () => goto('/onboarding'),
    },
    {
      id: 'feedback-open',
      label: $_('palette.feedback'),
      description: $_('palette.feedback.desc'),
      shortcut: 'Cmd+Shift+F',
      category: $_('palette.category.help'),
      action: () => {
        feedbackOpen = true;
      },
    },
  ]);

  // QW7: detect platform for shortcut hint label
  const shortcutLabel = $derived(
    typeof navigator !== 'undefined' && navigator.platform.toLowerCase().includes('mac')
      ? '⌘K'
      : 'Ctrl+K'
  );

  initI18n();

  // C-4 (audit 4.5 / Phase 1.A): set HTML <html lang="ru-RU"/"en-US"> dynamically.
  // Без этого NVDA выбирает TTS-движок по дефолтному locale OS — на русском
  // тексте без lang="ru" движок читает английским голосом, произношение
  // бессмысленное. Reactive к смене языка (settings page).
  $effect(() => {
    if (typeof document !== 'undefined' && $locale) {
      document.documentElement.lang = $locale.startsWith('ru') ? 'ru-RU' : 'en-US';
    }
  });

  onMount(() => {
    document.documentElement.dataset.theme = $resolvedTheme;

    // Async init: license, telemetry, onboarding gate. Fire-and-forget so
    // onMount can return its cleanup synchronously (fixes TS onMount return type).
    void (async () => {
      try {
        await refreshLicense();
      } catch (e) {
        console.warn('License refresh failed', e);
      }

      // TELEMETRY-P16: app_open — resolve opt-in, then track launch.
      try {
        await initTelemetryInternal();
        const buildInfo = await ipc.getBuildInfo().catch(() => null);
        track('app_open', { build_profile: buildInfo?.build_profile ?? 'unknown' });
      } catch (e) {
        console.debug('[telemetry] app_open failed', e);
      }

      // PA-A14 fix: First-run onboarding gate. Redirect к /onboarding если
      // user never seen it. /onboarding sets localStorage `aurora.onboarded`=1.
      try {
        const onboarded = window.localStorage.getItem('aurora.onboarded');
        const currentPath = page.url.pathname;
        // Only redirect from welcome page (/) — preserve direct deep-links.
        if (!onboarded && currentPath === '/') {
          await goto('/onboarding');
        }
      } catch {
        // localStorage may be disabled (private browsing, Tauri restrictions) — skip gate
      }
    })();

    // Keyboard shortcuts: Cmd/Ctrl+K (palette), Cmd/Ctrl+Shift+F (feedback),
    // Cmd/Ctrl+S (save active bundle).
    function onKey(e: KeyboardEvent) {
      const isMod = e.metaKey || e.ctrlKey;
      // Cmd+Shift+F → in-app feedback (PREMIUM P10)
      if (isMod && e.shiftKey && (e.key === 'F' || e.key === 'f' || e.code === 'KeyF')) {
        e.preventDefault();
        feedbackOpen = true;
        return;
      }
      // PA-A04 fix: Cmd+K → command palette toggle (do not block Cmd+Shift+K)
      if (isMod && !e.shiftKey && (e.key === 'k' || e.key === 'K' || e.code === 'KeyK')) {
        e.preventDefault();
        commandPaletteOpen = !commandPaletteOpen;
        return;
      }
      // QW9: Cmd/Ctrl+S → trigger save если active bundle exists и dirty
      if (isMod && !e.shiftKey && (e.key === 's' || e.key === 'S' || e.code === 'KeyS')) {
        if ($activeBundle && $isDirty && !saving) {
          e.preventDefault();
          void triggerSave();
        }
        return;
      }
      if (e.key === 'Escape' && feedbackOpen) {
        feedbackOpen = false;
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  function closeCommandPalette() {
    commandPaletteOpen = false;
  }

  // QW9: triggerSave wraps saveBundleTo с current bundle path resolution.
  // saveBundleTo saves IN-PLACE if bundle already has a known path (open-then-
  // save semantic); if bundle was created в memory only, prompts Save As dialog.
  async function triggerSave() {
    if (!$activeBundle || saving) return;
    saving = true;
    try {
      // If activeBundle has path → save in place; else Save As dialog.
      let targetPath = $activeBundle.path;
      if (!targetPath) {
        const { save } = await import('@tauri-apps/plugin-dialog');
        const picked = await save({
          title: 'Сохранить Aurora bundle',
          defaultPath: 'project.aurora',
          filters: [{ name: 'Aurora bundle', extensions: ['aurora'] }],
        });
        if (!picked) {
          saving = false;
          return;
        }
        targetPath = picked;
      }
      await saveBundleTo(targetPath);
      pushToast({
        level: 'success',
        title: 'Сохранено',
        body: targetPath,
      });
    } catch (e) {
      pushToast({
        level: 'danger',
        title: 'Не удалось сохранить',
        body: e instanceof Error ? e.message : String(e),
      });
    } finally {
      saving = false;
    }
  }

  async function submitFeedback() {
    if (!feedbackText.trim()) return;
    try {
      await ipc.captureFeedback({ text: feedbackText });
      // TELEMETRY-P16: support_diagnostics_sent
      track('support_diagnostics_sent', { has_screenshot: false, has_log: false });
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
  <!-- Этап 2.9: non-blocking update banner. Best-effort check at startup.
       Не блокирует UI — показывается только при наличии update. -->
  <UpdateAvailableBanner />
  <!-- ROADMAP §3.5: auto-refresh banner. Opt-in only (152-FZ).
       Reads consent from sidecar; shows prompt on first-run or new data.
       Audit H-03 fix (этап 4.5): передаём projectUuid из активного bundle —
       без этого 'available' branch в banner'е никогда не fires. -->
  <RefreshAvailableBanner projectUuid={$activeBundle?.manifest?.project_id ?? ''} />
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
        <!-- M-08: revision badge tooltip explains optimistic concurrency role -->
        <abbr title="Текущая ревизия открытого bundle. Monotonic счётчик — растёт на 1 при каждом сохранении. Защищает от потери чужих правок в multi-process сценариях.">
          <Badge variant="info" size="sm">
            {#snippet children()}r{$activeBundle.revision}{/snippet}
          </Badge>
        </abbr>
        <!-- QW9 audit fix: manual Save button + Cmd+S keybind. Без этого
             saveBundleTo() existed but был unreachable through UI. -->
        <button
          type="button"
          class="save-btn"
          onclick={triggerSave}
          disabled={saving || !$isDirty}
          aria-label="Сохранить bundle (Ctrl+S)"
          title="Ctrl+S"
        >
          {saving ? 'Сохранение…' : 'Сохранить'}
        </button>
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

  <!-- PA-A02 fix: SaveIndicator state derived from bundle stores. -->
  <!-- QW7: footer Cmd+K hint for discoverability. -->
  <div class="app-footer">
    <SaveIndicator state={saveState} lastSavedAt={$lastSavedAt} />
    <button
      type="button"
      class="palette-hint"
      onclick={() => (commandPaletteOpen = true)}
      aria-label={$_('app.footer.shortcut_hint', { values: { shortcut: shortcutLabel } })}
    >
      <kbd>{shortcutLabel}</kbd>
      <span class="palette-hint-label">{$_('app.footer.shortcut_hint', { values: { shortcut: '' } }).replace(' —', '').trim()}</span>
    </button>
    <PerfFooter />
  </div>
  <Toaster />

  <!-- PA-A04 fix: CommandPalette mounted globally; Cmd+K toggle wired в onKey. -->
  <CommandPalette {commands} open={commandPaletteOpen} onClose={closeCommandPalette} />

  <!-- Этап 2.8: blocking modal на handshake mismatch (Rust↔Python sidecar) -->
  <HandshakeIncompatibleModal />

  {#if feedbackOpen}
    <!-- H-5 (audit 4.5 / Phase 1.A): focus trap + autofocus textarea на mount.
         До правки overlay открывался без перемещения focus — NVDA анонсировал
         dialog но focus оставался на trigger button → customer не мог писать.
         tabindex="-1" на backdrop + bind textarea + autofocus through $effect. -->
    <div
      class="feedback-overlay"
      role="dialog"
      aria-labelledby="feedback-title"
      aria-modal="true"
      tabindex="-1"
      transition:fly={{ y: 20, duration: 220 }}
      onkeydown={feedbackTrapFocus}
    >
      <div class="feedback-card">
        <h3 id="feedback-title">{$_('feedback.title')}</h3>
        <textarea
          bind:this={feedbackTextareaEl}
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
            bind:this={feedbackSubmitButtonEl}
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
    /* update-banner (auto, collapses to 0 when hidden) + header + main + footer */
    grid-template-rows: auto auto 1fr auto;
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

  /* QW9 save button в header-meta */
  .save-btn {
    padding: 4px 12px;
    border-radius: 4px;
    border: 1px solid var(--color-info, #1D4ED8);
    background: var(--color-info, #1D4ED8);
    color: white;
    cursor: pointer;
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    font-weight: 500;
    transition: background-color 120ms ease, opacity 120ms ease;
  }
  .save-btn:hover:not(:disabled) {
    opacity: 0.9;
  }
  .save-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  /* QW7 palette discoverability hint в footer center */
  .palette-hint {
    display: inline-flex;
    align-items: center;
    gap: var(--spacing-2, 0.5rem);
    background: transparent;
    border: none;
    color: var(--text-muted, #6b7280);
    cursor: pointer;
    font-size: var(--typography-fontSize-ui-xs, 0.75rem);
    padding: var(--spacing-1, 0.25rem) var(--spacing-2, 0.5rem);
    border-radius: 4px;
    transition: background-color 120ms ease, color 120ms ease;
  }
  .palette-hint:hover {
    background: var(--surface-hover, #f9fafb);
    color: var(--text-primary, #111827);
  }
  .palette-hint kbd {
    font-family: var(--font-mono, monospace);
    font-size: 0.85em;
    padding: 2px 6px;
    border: 1px solid var(--border-default, #d1d5db);
    border-radius: 3px;
    background: var(--bg-surface, white);
    /* WCAG AA fix (A11Y-W05): palette-hint inherits text-muted (~3.6:1 on white).
       kbd has its own white bg so must set its own foreground for 4.5:1. */
    color: var(--text-secondary, #4a4d57);
  }
  .palette-hint-label {
    user-select: none;
    /* WCAG AA fix (A11Y-W06): inherits text-muted (~3.6:1) from parent button.
       Override to text-secondary (~7.6:1) for xs font-size compliance. */
    color: var(--text-secondary, #4a4d57);
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

  /* 4.3 a11y cleanup: aria-current='page' selector unused — app-nav links
     не получают этот атрибут (route awareness через page state). Оставляем
     только :hover. Когда добавится route-aware аттрибут — вернуть. */
  .app-nav a:hover {
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
