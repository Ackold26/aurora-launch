<!--
  CertChainViewer — Inspector "Certificate" tab (P-09).

  Displays the full Ed25519 methodology cert chain for an .aurora bundle.

  INV-25 dual-mode UX:
  - Manager mode (default):  verdict badge + short composite hash fingerprint.
  - Expert mode (opt-in):    full chain — signature hex, public key fingerprint,
                             provenance, signed-by, signed-at, manifest revision.

  ARIA: <dl> for key-value pairs; expand button labelled via aria-expanded.
  Reduce motion: no transform/transition animations when
  `prefers-reduced-motion: reduce`.

  Tooltips: native <title> elements inside <abbr> — zero external deps.
-->

<script lang="ts">
  import Badge from './Badge.svelte';
  import type { VerificationResult } from '$lib/ipc/methodology';

  // ─── Props ─────────────────────────────────────────────────────────────────

  interface Props {
    /** Result from verify_bundle_signature IPC call. */
    result: VerificationResult;
    /** INV-25: show full chain details (hex bytes, provenance, etc.). */
    expertMode?: boolean;
  }

  let { result, expertMode = false }: Props = $props();

  // ─── State ──────────────────────────────────────────────────────────────────

  /** Controls visibility of signature bytes section (Expert mode only). */
  let sigExpanded = $state(false);

  // ─── Derived ────────────────────────────────────────────────────────────────

  /**
   * Map trust_badge → Badge variant.
   * production → success (green)
   * dev        → info   (blue/amber per theme)
   * sample     → sigil  (sigil accent)
   * warning    → danger (red)
   */
  const badgeVariant = $derived(
    result.trust_badge === 'production'
      ? 'success'
      : result.trust_badge === 'dev'
        ? 'info'
        : result.trust_badge === 'sample'
          ? 'sigil'
          : 'danger',
  );

  /** Human-readable verdict label (locale-neutral; parent can i18n-wrap). */
  const verdictLabel = $derived(
    result.trust_badge === 'production'
      ? 'Verified'
      : result.trust_badge === 'dev'
        ? 'Self-signed dev'
        : result.trust_badge === 'sample'
          ? 'Educational sample'
          : 'Untrusted',
  );

  /**
   * Composite hash short fingerprint — first 8 hex chars + ellipsis.
   * Returns null if hash unavailable.
   */
  const shortHash = $derived(
    result.composite_hash ? result.composite_hash.slice(0, 8) + '…' : null,
  );

  /** Tooltip for trust verdict. */
  const verdictTooltip = $derived(
    result.trust_badge === 'production'
      ? 'Ed25519 signature verified against Aurora AI cloud key'
      : result.trust_badge === 'dev'
        ? 'Signed with a local development key — not for production distribution'
        : result.trust_badge === 'sample'
          ? 'Educational sample bundle signed with a bundled key'
          : result.failure_reason ?? 'Signature missing or failed verification',
  );
</script>

<!-- ─── Markup ──────────────────────────────────────────────────────────────── -->
<article
  class="cert-chain"
  data-trust={result.trust_badge}
  data-valid={result.valid}
  aria-label="Methodology certificate chain"
>
  <!-- ── Manager-mode header: verdict badge + short hash ───────────────────── -->
  <header class="cert-header">
    <div class="cert-verdict">
      <abbr title={verdictTooltip} class="cert-verdict-abbr">
        <Badge variant={badgeVariant} size="md">
          {#snippet children()}
            {#if result.trust_badge === 'warning' || !result.valid}
              <span class="cert-icon" aria-hidden="true">⚠</span>
            {:else}
              <span class="cert-icon cert-icon--ok" aria-hidden="true">✓</span>
            {/if}
            {verdictLabel}
          {/snippet}
        </Badge>
      </abbr>
    </div>

    {#if shortHash}
      <div class="cert-fingerprint">
        <abbr title="Composite bundle hash (SHA-256 over manifest + file hashes + version, length-prefix encoded)">
          <span class="cert-fingerprint-label">Hash</span>
          <code class="cert-fingerprint-value" aria-label="Bundle hash fingerprint {shortHash}">
            {shortHash}
          </code>
        </abbr>
      </div>
    {/if}
  </header>

  <!-- ── Expert-mode full chain ────────────────────────────────────────────── -->
  {#if expertMode}
    <section class="cert-expert" aria-label="Full certificate chain (Expert mode)">
      <dl class="cert-dl">
        <!-- Provenance -->
        <div class="cert-row">
          <dt>
            <abbr title="How this bundle was signed: cloud_kms (production Aurora AI), local_dev (developer machine), sample (bundled educational key), unsigned">
              Provenance
            </abbr>
          </dt>
          <dd class="cert-mono">{result.signature_provenance}</dd>
        </div>

        <!-- Full composite hash -->
        {#if result.composite_hash}
          <div class="cert-row">
            <dt>
              <abbr title="Full 64-char SHA-256 composite hash covering manifest canonical bytes, per-file hashes, and app version. Algorithm mirrors Python BundleManifest.composite_bundle_hash() byte-for-byte.">
                Composite hash
              </abbr>
            </dt>
            <dd class="cert-mono cert-hash-full" aria-label="Full composite hash">
              {result.composite_hash}
            </dd>
          </div>
        {/if}

        <!-- Key fingerprint -->
        {#if result.key_fingerprint}
          <div class="cert-row">
            <dt>
              <abbr title="BLAKE3 fingerprint of the Ed25519 verifying key (first 16 hex chars). Identifies the signing keypair.">
                Key fingerprint
              </abbr>
            </dt>
            <dd class="cert-mono">{result.key_fingerprint}</dd>
          </div>
        {/if}

        <!-- Signature bytes (collapsed by default) -->
        <div class="cert-row cert-row--sig">
          <dt>
            <abbr title="Raw Ed25519 signature (64 bytes, hex-encoded). Signs the composite bundle hash.">
              Signature
            </abbr>
          </dt>
          <dd>
            <button
              type="button"
              class="cert-sig-toggle"
              onclick={() => (sigExpanded = !sigExpanded)}
              aria-expanded={sigExpanded}
              aria-controls="cert-sig-bytes"
            >
              {sigExpanded ? '▲ Hide bytes' : '▼ Show bytes'}
            </button>
            {#if sigExpanded}
              <div id="cert-sig-bytes" class="cert-sig-placeholder cert-mono" aria-label="Ed25519 signature bytes (available after bundle open)">
                <!-- Signature raw bytes are not returned by VerificationResult
                     (only validity + key fingerprint). Prompt user to call
                     generate_local_dev_signature for dev bundles, or check
                     the bundled signature.bin entry directly. -->
                <span class="cert-sig-note">
                  Signature bytes not exposed via verify IPC (B2C design).
                  Open bundle → read <code>signature.bin</code> entry for raw hex.
                </span>
              </div>
            {/if}
          </dd>
        </div>

        <!-- Signed by -->
        {#if result.signed_by}
          <div class="cert-row">
            <dt>
              <abbr title="Identity of the signing party, as recorded in the bundle methodology_cert metadata.">
                Signed by
              </abbr>
            </dt>
            <dd>{result.signed_by}</dd>
          </div>
        {/if}

        <!-- Signed at -->
        {#if result.signed_at}
          <div class="cert-row">
            <dt>
              <abbr title="Timestamp when the bundle was signed (ISO 8601, from manifest methodology_cert.signed_at).">
                Signed at
              </abbr>
            </dt>
            <dd>{result.signed_at}</dd>
          </div>
        {/if}

        <!-- Manifest revision -->
        {#if result.manifest_revision !== null && result.manifest_revision !== undefined}
          <div class="cert-row">
            <dt>
              <abbr title="Bundle manifest revision number. Increments on every save.">
                Revision
              </abbr>
            </dt>
            <dd class="cert-mono">r{result.manifest_revision}</dd>
          </div>
        {/if}

        <!-- Failure reason (shown even in expert mode) -->
        {#if result.failure_reason}
          <div class="cert-row cert-row--failure" role="alert">
            <dt>Failure</dt>
            <dd>{result.failure_reason}</dd>
          </div>
        {/if}
      </dl>
    </section>
  {:else if result.failure_reason}
    <!-- Manager mode: surface failure reason inline under badge -->
    <p class="cert-failure-manager" role="alert">{result.failure_reason}</p>
  {/if}
</article>

<!-- ─── Styles ─────────────────────────────────────────────────────────────── -->
<style>
  .cert-chain {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-3);
    padding: var(--spacing-4);
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-lg);
  }

  /* Accent border by trust level */
  .cert-chain[data-trust='production'] {
    border-left: 4px solid var(--color-success);
  }
  .cert-chain[data-trust='dev'] {
    border-left: 4px solid var(--color-info);
  }
  .cert-chain[data-trust='sample'] {
    border-left: 4px solid var(--accent-sigil, #ccff00);
  }
  .cert-chain[data-trust='warning'] {
    border-left: 4px solid var(--color-danger);
  }

  /* ── Header ── */
  .cert-header {
    display: flex;
    align-items: center;
    gap: var(--spacing-4);
    flex-wrap: wrap;
  }

  .cert-verdict {
    flex-shrink: 0;
  }

  .cert-verdict-abbr {
    text-decoration: none;
    cursor: default;
  }

  .cert-icon {
    font-style: normal;
    font-size: 0.85em;
  }

  .cert-icon--ok {
    color: inherit;
  }

  .cert-fingerprint {
    display: flex;
    align-items: center;
    gap: var(--spacing-2);
  }

  .cert-fingerprint abbr {
    display: flex;
    align-items: center;
    gap: var(--spacing-1);
    text-decoration: none;
    cursor: default;
  }

  .cert-fingerprint-label {
    font-size: var(--typography-fontSize-ui-xs);
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .cert-fingerprint-value {
    font-family: var(--font-mono);
    font-size: var(--typography-fontSize-ui-sm);
    color: var(--text-primary);
    background: var(--bg-elevated);
    padding: 0 var(--spacing-2);
    border-radius: var(--border-radius-sm);
    border: 1px solid var(--border-subtle);
    letter-spacing: 0.04em;
  }

  /* ── Expert DL ── */
  .cert-expert {
    border-top: 1px solid var(--border-subtle);
    padding-top: var(--spacing-3);
  }

  .cert-dl {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
    margin: 0;
  }

  .cert-row {
    display: grid;
    grid-template-columns: 148px 1fr;
    gap: var(--spacing-3);
    align-items: start;
  }

  .cert-row dt {
    font-size: var(--typography-fontSize-ui-sm);
    color: var(--text-secondary);
    margin: 0;
  }

  .cert-row dt abbr {
    text-decoration: underline dotted var(--border-subtle);
    cursor: help;
  }

  .cert-row dd {
    font-size: var(--typography-fontSize-ui-sm);
    color: var(--text-primary);
    margin: 0;
    word-break: break-all;
  }

  .cert-mono {
    font-family: var(--font-mono);
    font-size: 0.82em;
    letter-spacing: 0.02em;
  }

  .cert-hash-full {
    word-break: break-all;
    line-height: 1.5;
  }

  /* ── Signature toggle ── */
  .cert-sig-toggle {
    background: transparent;
    border: 1px solid var(--border-subtle);
    border-radius: var(--border-radius-sm);
    padding: var(--spacing-1) var(--spacing-2);
    font-size: var(--typography-fontSize-ui-xs);
    color: var(--text-secondary);
    cursor: pointer;
    /* transition only when motion allowed — INV-14 */
    transition: border-color 150ms ease, color 150ms ease;
  }

  .cert-sig-toggle:hover {
    border-color: var(--accent);
    color: var(--text-primary);
  }

  .cert-sig-placeholder {
    margin-top: var(--spacing-2);
    padding: var(--spacing-2) var(--spacing-3);
    background: var(--bg-elevated);
    border-radius: var(--border-radius-sm);
    border: 1px solid var(--border-subtle);
  }

  .cert-sig-note {
    font-size: var(--typography-fontSize-ui-xs);
    color: var(--text-muted);
    line-height: 1.5;
  }

  .cert-sig-note code {
    font-family: var(--font-mono);
  }

  /* ── Failure rows ── */
  .cert-row--failure dt {
    color: var(--color-danger);
  }

  .cert-row--failure dd {
    color: var(--color-danger);
  }

  .cert-failure-manager {
    font-size: var(--typography-fontSize-ui-sm);
    color: var(--color-danger);
    margin: 0;
  }

  /* ── Reduce motion — INV-14 ── */
  @media (prefers-reduced-motion: reduce) {
    .cert-sig-toggle {
      transition: none;
    }
  }
</style>
