<!--
  Project history route — wraps ForecastHistory component with route params.
  Phase Premium P-02.
-->

<script lang="ts">
  import { page } from '$app/state';
  import ForecastHistory from '$lib/components/ForecastHistory.svelte';

  // Svelte 5: page.params is reactive automatically
  const projectUuid = $derived(page.params.uuid ?? '');

  // TODO: wire expert mode store when global preference exists (P-Premium UX track)
  let expertMode = $state(false);
</script>

<section class="page">
  <nav class="breadcrumb" aria-label="Навигация">
    <a href="/">Проекты</a>
    <span aria-hidden="true">/</span>
    <a href={`/project/${projectUuid}`}>{projectUuid.slice(0, 8)}…</a>
    <span aria-hidden="true">/</span>
    <span>История</span>
  </nav>

  <div class="page-actions">
    <label class="expert-toggle">
      <input type="checkbox" bind:checked={expertMode} />
      <span>Расширенный режим</span>
    </label>
  </div>

  {#if projectUuid}
    <ForecastHistory {projectUuid} {expertMode} />
  {:else}
    <p role="alert">Не указан идентификатор проекта.</p>
  {/if}
</section>

<style>
  .page {
    max-width: 1080px;
    margin: 0 auto;
    padding: var(--spacing-4, 1rem);
    display: flex;
    flex-direction: column;
    gap: var(--spacing-4, 1rem);
  }

  .breadcrumb {
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    color: var(--text-secondary, #6b7280);
    display: flex;
    gap: var(--spacing-2, 0.5rem);
    align-items: center;
  }

  .breadcrumb a {
    color: var(--text-link, #2563eb);
    text-decoration: none;
  }

  .breadcrumb a:hover {
    text-decoration: underline;
  }

  .page-actions {
    display: flex;
    justify-content: flex-end;
  }

  .expert-toggle {
    display: inline-flex;
    align-items: center;
    gap: var(--spacing-2, 0.5rem);
    font-size: var(--typography-fontSize-ui-sm, 0.875rem);
    color: var(--text-secondary, #374151);
    cursor: pointer;
  }
</style>
