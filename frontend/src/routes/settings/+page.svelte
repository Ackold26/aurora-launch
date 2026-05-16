<!-- Settings — theme, locale, telemetry opt-in, About. -->

<script lang="ts">
  import { onMount } from 'svelte';
  import { _, locale } from 'svelte-i18n';
  import Card from '$lib/components/Card.svelte';
  import Badge from '$lib/components/Badge.svelte';
  import { themeMode, type ThemeMode } from '$lib/stores/theme';
  import { setLocale, type SupportedLocale, SUPPORTED_LOCALES } from '$lib/i18n';
  import { ipc } from '$ipc/client';
  import type { BuildInfo } from '$ipc/client';
  import { track, notifyOptInChange } from '$lib/services/telemetry';
  import type { RefreshConsentSetting } from '$ipc/client';

  let telemetryOptIn = $state(false);
  let buildInfo = $state<BuildInfo | null>(null);
  let refreshConsent = $state<RefreshConsentSetting | null>(null);
  let refreshConsentLoading = $state(false);

  onMount(async () => {
    try {
      telemetryOptIn = await ipc.getTelemetryOptIn();
    } catch (e) {
      console.warn('telemetry opt-in fetch failed', e);
    }
    try {
      buildInfo = await ipc.getBuildInfo();
    } catch (e) {
      console.warn('build info fetch failed', e);
    }
    try {
      refreshConsent = await ipc.getRefreshConsent();
    } catch (e) {
      console.warn('refresh consent fetch failed', e);
    }
  });

  async function toggleTelemetry(e: Event) {
    const target = e.target as HTMLInputElement;
    telemetryOptIn = target.checked;
    try {
      await ipc.setTelemetryOptIn(telemetryOptIn);
      // Notify telemetry service of opt-in state change (flush or discard buffer).
      notifyOptInChange(telemetryOptIn);
      // TELEMETRY-P16: settings_changed (telemetry toggle itself)
      if (telemetryOptIn) {
        track('settings_changed', { setting_key: 'telemetry_opt_in' });
      }
    } catch (err) {
      console.error('telemetry opt-in toggle failed', err);
    }
  }

  function changeTheme(mode: ThemeMode) {
    themeMode.set(mode);
    // TELEMETRY-P16: settings_changed
    track('settings_changed', { setting_key: 'theme' });
  }

  function changeLocale(loc: SupportedLocale) {
    setLocale(loc);
    // TELEMETRY-P16: settings_changed
    track('settings_changed', { setting_key: 'locale' });
  }

  async function toggleRefreshConsent(e: Event) {
    const target = e.target as HTMLInputElement;
    const enabled = target.checked;
    refreshConsentLoading = true;
    try {
      refreshConsent = await ipc.setRefreshConsent(
        enabled,
        refreshConsent?.frequency ?? 'weekly',
      );
      track('settings_changed', { setting_key: 'refresh_consent' });
    } catch (err) {
      console.error('refresh consent toggle failed', err);
    } finally {
      refreshConsentLoading = false;
    }
  }

  async function changeRefreshFrequency(freq: RefreshConsentSetting['frequency']) {
    if (!refreshConsent) return;
    refreshConsentLoading = true;
    try {
      refreshConsent = await ipc.setRefreshConsent(refreshConsent.enabled, freq);
      track('settings_changed', { setting_key: 'refresh_frequency' });
    } catch (err) {
      console.error('refresh frequency change failed', err);
    } finally {
      refreshConsentLoading = false;
    }
  }
</script>

<section class="settings">
  <h1>{$_('nav.settings')}</h1>

  <Card title={$_('settings.theme')}>
    {#snippet children()}
      <div class="seg">
        {#each ['system', 'dark', 'light', 'high-contrast'] as mode (mode)}
          <button
            class:active={$themeMode === mode}
            onclick={() => changeTheme(mode as ThemeMode)}
          >
            {$_(`settings.theme.${mode}`)}
          </button>
        {/each}
      </div>
    {/snippet}
  </Card>

  <Card title={$_('settings.locale')}>
    {#snippet children()}
      <div class="seg">
        {#each SUPPORTED_LOCALES as loc (loc)}
          <button
            class:active={$locale === loc}
            onclick={() => changeLocale(loc)}
          >
            {loc.toUpperCase()}
          </button>
        {/each}
      </div>
    {/snippet}
  </Card>

  <Card title={$_('settings.telemetry.opt-in')}>
    {#snippet children()}
      <label class="switch">
        <input type="checkbox" checked={telemetryOptIn} onchange={toggleTelemetry} />
        <span class="slider" aria-hidden="true"></span>
        <span class="switch-label">
          {telemetryOptIn ? 'On' : 'Off'}
        </span>
      </label>
      <p class="hint">{$_('settings.telemetry.detail')}</p>
    {/snippet}
  </Card>

  <!-- ROADMAP §3.5: Auto-refresh consent section -->
  <Card title={$_('refresh.settings.title')}>
    {#snippet children()}
      <label class="switch">
        <input
          type="checkbox"
          checked={refreshConsent?.enabled ?? false}
          disabled={refreshConsentLoading}
          onchange={toggleRefreshConsent}
        />
        <span class="slider" aria-hidden="true"></span>
        <span class="switch-label">
          {(refreshConsent?.enabled ?? false) ? $_('refresh.settings.on') : $_('refresh.settings.off')}
        </span>
      </label>
      <p class="hint">{$_('refresh.settings.detail')}</p>

      {#if refreshConsent?.enabled}
        <div class="refresh-freq">
          <span class="refresh-freq__label">{$_('refresh.settings.frequency')}</span>
          <div class="seg">
            {#each (['daily', 'weekly', 'monthly'] as const) as freq (freq)}
              <button
                class:active={refreshConsent.frequency === freq}
                disabled={refreshConsentLoading}
                onclick={() => changeRefreshFrequency(freq)}
              >
                {$_(`refresh.settings.freq.${freq}`)}
              </button>
            {/each}
          </div>
        </div>
      {/if}
    {/snippet}
  </Card>

  {#if buildInfo}
    {@const info = buildInfo}
    <Card title="About">
      {#snippet children()}
        <dl class="about">
          <dt>{$_('settings.about.version')}</dt>
          <dd>
            <code>{info.version}</code>
            {#if info.is_dev_build}
              <Badge variant="warning" size="sm">
                {#snippet children()}{info.build_profile}{/snippet}
              </Badge>
            {/if}
          </dd>
          <dt>{$_('settings.about.build_profile')}</dt>
          <dd><code>{info.build_profile}</code></dd>
          <dt>Rust</dt>
          <dd><code>{info.rust_version}</code></dd>
        </dl>
      {/snippet}
    </Card>
  {/if}
</section>

<style>
  .settings {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-4);
    max-width: 720px;
    margin: 0 auto;
  }

  .seg {
    display: inline-flex;
    background: var(--bg-main);
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-lg);
    padding: 2px;
    gap: 2px;
  }

  .seg button {
    background: transparent;
    border: none;
    color: var(--text-secondary);
    padding: var(--spacing-1) var(--spacing-3);
    border-radius: var(--border-radius-md);
    cursor: pointer;
    font-family: var(--font-sans);
    transition: all var(--motion-fast) var(--easing-smooth);
  }

  .seg button.active {
    background: var(--accent);
    color: white;
  }

  .seg button:not(.active):hover {
    color: var(--text-primary);
  }

  .switch {
    display: inline-flex;
    align-items: center;
    gap: var(--spacing-2);
    cursor: pointer;
  }

  .switch input {
    position: absolute;
    opacity: 0;
    pointer-events: none;
  }

  .slider {
    position: relative;
    width: 40px;
    height: 22px;
    background: var(--bg-main);
    border: 1px solid var(--border-subtle);
    border-radius: 999px;
    transition: background var(--motion-fast) var(--easing-smooth);
  }

  .slider::before {
    content: '';
    position: absolute;
    width: 16px;
    height: 16px;
    background: var(--text-muted);
    border-radius: 50%;
    top: 2px;
    left: 2px;
    transition:
      left var(--motion-fast) var(--easing-spring),
      background var(--motion-fast) var(--easing-smooth);
  }

  .switch input:checked + .slider {
    background: color-mix(in srgb, var(--accent) 28%, var(--bg-main));
    border-color: var(--accent);
  }

  .switch input:checked + .slider::before {
    left: 20px;
    background: var(--accent);
  }

  .hint {
    color: var(--text-muted);
    font-size: var(--typography-fontSize-ui-sm);
    margin: var(--spacing-2) 0 0 0;
    max-width: 480px;
  }

  .refresh-freq {
    margin-top: var(--spacing-3);
    display: flex;
    align-items: center;
    gap: var(--spacing-3);
    flex-wrap: wrap;
  }

  .refresh-freq__label {
    color: var(--text-secondary);
    font-size: var(--typography-fontSize-ui-sm);
  }

  .about {
    display: grid;
    grid-template-columns: 160px 1fr;
    gap: var(--spacing-2) var(--spacing-4);
    margin: 0;
  }

  .about dt {
    color: var(--text-muted);
  }

  .about dd {
    margin: 0;
    color: var(--text-primary);
  }
</style>
