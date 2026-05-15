<!-- Welcome / Onboarding entry — Block 2B premium upfront. -->

<script lang="ts">
  import { _ } from 'svelte-i18n';
  import { goto } from '$app/navigation';

  import Card from '$lib/components/Card.svelte';
  import Button from '$lib/components/Button.svelte';
  import DailyInsightBanner from '$lib/components/DailyInsightBanner.svelte';
  import { pushToast } from '$lib/stores/toast';
  import { openBundleAt } from '$lib/stores/bundle';

  async function openSample() {
    try {
      // Sample bundle is shipped с installer at <appdata>/aurora-launch/sample.aurora
      // For dev mode + first run we resolve from app resource path. This will be
      // wired в Block 4 with proper Tauri resource bundling. For now, allow user
      // to pick file дя rapid dev iteration.
      const { open } = await import('@tauri-apps/plugin-dialog');
      const selected = await open({
        title: 'Pick Aurora bundle (.aurora)',
        filters: [{ name: 'Aurora bundle', extensions: ['aurora', 'json'] }]
      });
      if (typeof selected === 'string') {
        await openBundleAt(selected);
        await goto('/inspector');
      }
    } catch (e) {
      pushToast({ level: 'danger', title: 'Failed to open sample', body: String(e) });
    }
  }

  async function importExisting() {
    try {
      const { open } = await import('@tauri-apps/plugin-dialog');
      const selected = await open({
        title: $_('welcome.cta.import'),
        filters: [{ name: 'Aurora bundle', extensions: ['aurora', 'json'] }]
      });
      if (typeof selected === 'string') {
        await openBundleAt(selected);
        await goto('/inspector');
      }
    } catch (e) {
      pushToast({ level: 'danger', title: 'Import failed', body: String(e) });
    }
  }

  function newLaunch() {
    goto('/wizard');
  }
</script>

<section class="welcome">
  <DailyInsightBanner />
  <div class="hero">
    <h1>{$_('welcome.title')}</h1>
    <p class="subtitle">{$_('welcome.subtitle')}</p>
  </div>

  <div class="entries">
    <Card title={$_('welcome.cta.sample')} interactive onclick={openSample}>
      {#snippet children()}
        <p>60 секунд от установки до первого прогноза. Synthetic FMCG bundle с заранее посчитанной похожестью и прогнозом.</p>
      {/snippet}
    </Card>

    <Card title={$_('welcome.cta.import')} interactive onclick={importExisting}>
      {#snippet children()}
        <p>Открыть существующий <code>.aurora</code> файл из предыдущей работы или из Aurora Data Studio.</p>
      {/snippet}
    </Card>

    <Card title={$_('welcome.cta.new')} interactive onclick={newLaunch} accent="info">
      {#snippet children()}
        <p>Запустить мастер — 7 шагов: импорт → сопоставление → proxy → похожесть → якоря → прогноз → сертификат.</p>
      {/snippet}
    </Card>
  </div>

  <div class="features">
    <ul>
      <li>{$_('welcome.feature.proxy')}</li>
      <li>{$_('welcome.feature.forecast')}</li>
      <li>{$_('welcome.feature.cert')}</li>
    </ul>
  </div>
</section>

<style>
  .welcome {
    max-width: var(--sizing-ui-containerMax);
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-8);
  }

  .hero {
    text-align: center;
    margin-top: var(--spacing-8);
  }

  .hero h1 {
    font-family: var(--font-display);
    font-size: 3rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    margin-bottom: var(--spacing-2);
  }

  .subtitle {
    color: var(--text-secondary);
    font-size: var(--typography-fontSize-ui-h3);
    max-width: 640px;
    margin: 0 auto;
  }

  .entries {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: var(--spacing-4);
  }

  .features {
    text-align: center;
    color: var(--text-muted);
  }

  .features ul {
    list-style: none;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: var(--spacing-4);
    justify-content: center;
  }

  .features li::before {
    content: '◆ ';
    color: var(--accent);
    margin-right: var(--spacing-1);
  }
</style>
