<script lang="ts">
  import { _ } from 'svelte-i18n';
  import Card from '$lib/components/Card.svelte';
  import Skeleton from '$lib/components/Skeleton.svelte';
  import TrustBadge from '$lib/components/TrustBadge.svelte';
  import CertExportModal from '$lib/components/inspector/CertExportModal.svelte';
  import type { VerificationResult } from '$ipc/client';

  interface Props {
    verification: VerificationResult | null;
    verifying: boolean;
    /** Absolute path to the .aurora bundle (passed from Inspector page). */
    bundlePath: string;
    /** Aurora Launch version stamped in bundle manifest. */
    appVersion: string;
  }

  let { verification, verifying, bundlePath, appVersion }: Props = $props();

  // Sprint 3 D5 — Cert PDF export state
  let exportModalOpen = $state(false);

  function openExportModal(): void {
    exportModalOpen = true;
  }

  function closeExportModal(): void {
    exportModalOpen = false;
  }
</script>

<div role="tabpanel" id="tab-cert" hidden={false}>
  <Card title={$_('inspector.tab.cert')}>
    {#snippet children()}
      {#if verifying}
        <Skeleton width="320px" height="40px" rounded />
      {:else if verification}
        <TrustBadge result={verification} />
        <div class="cert-export-row">
          <button
            type="button"
            class="cert-export-btn"
            onclick={openExportModal}
            disabled={!verification.valid && !verification.composite_hash}
          >
            {$_('cert.export.open_button', { default: 'Экспортировать сертификат (PDF)' })}
          </button>
        </div>
      {:else}
        <p>Open this tab to verify bundle signature.</p>
      {/if}
    {/snippet}
  </Card>
</div>

{#if verification}
  <CertExportModal
    open={exportModalOpen}
    {verification}
    {bundlePath}
    {appVersion}
    onClose={closeExportModal}
  />
{/if}

<style>
  .cert-export-row {
    margin-top: var(--spacing-4, 1rem);
    display: flex;
    gap: var(--spacing-2, 0.5rem);
  }

  .cert-export-btn {
    padding: 8px 16px;
    background: var(--accent, #2e5bff);
    color: #fff;
    border: 1px solid var(--accent, #2e5bff);
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.875rem;
    font-weight: 500;
    transition: opacity 120ms ease;
  }

  .cert-export-btn:hover:not(:disabled) {
    opacity: 0.9;
  }

  .cert-export-btn:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }

  @media (prefers-reduced-motion: reduce) {
    .cert-export-btn {
      transition: none;
    }
  }
</style>
