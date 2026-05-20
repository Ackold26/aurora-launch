<!--
  AuditTab — Inspector audit panel.

  Sprint 3 D6: verify_reproducibility — re-hashes every file inside the bundle
  ZIP against the manifest's per-file sha256 claims.  Verified means bundle
  bytes haven't been altered since manifest creation (the Aurora Launch
  reproducibility guarantee).
-->

<script lang="ts">
  import { _ } from 'svelte-i18n';
  import Card from '$lib/components/Card.svelte';
  import { ipc } from '$ipc/client';
  import type { ReproducibilityResult } from '$ipc/client';

  interface Props {
    /** Absolute path to .aurora bundle (passed from Inspector). */
    bundlePath: string;
  }

  let { bundlePath }: Props = $props();

  // ── Verification state ──────────────────────────────────────────────────
  type Phase = 'idle' | 'running' | 'done' | 'error';

  let phase = $state<Phase>('idle');
  let result = $state<ReproducibilityResult | null>(null);
  let errorMessage = $state<string | null>(null);

  async function runVerification(): Promise<void> {
    if (phase === 'running' || !bundlePath) return;
    phase = 'running';
    result = null;
    errorMessage = null;
    try {
      result = await ipc.verifyReproducibility(bundlePath);
      phase = 'done';
    } catch (e) {
      errorMessage = e instanceof Error ? e.message : String(e);
      phase = 'error';
    }
  }

  // Status badge — null when no result; both tone + label always paired.
  const statusDisplay = $derived.by(() => {
    if (!result) return null;
    if (result.status === 'verified') return {
      tone: 'success',
      label: $_('audit.repro.status_verified', { default: 'Воспроизводимо' }),
    };
    if (result.status === 'diverged') return {
      tone: 'danger',
      label: $_('audit.repro.status_diverged', { default: 'Расхождение' }),
    };
    return {
      tone: 'warning',
      label: $_('audit.repro.status_error', { default: 'Ошибка' }),
    };
  });
</script>

<div role="tabpanel" id="tab-audit" hidden={false}>
  <Card title={$_('inspector.tab.audit')}>
    {#snippet children()}
      <section class="audit-section">
        <header class="audit-section-header">
          <h3 class="audit-section-title">
            {$_('audit.repro.heading', { default: 'Проверка воспроизводимости' })}
          </h3>
          <p class="audit-section-desc">
            {$_('audit.repro.description', {
              default:
                'Сверяет SHA-256 каждого файла внутри бандла с заявленными в манифесте значениями. «Воспроизводимо» — все файлы соответствуют записанным хэшам.',
            })}
          </p>
        </header>

        <div class="audit-actions">
          <button
            type="button"
            class="audit-repro-btn"
            onclick={runVerification}
            disabled={phase === 'running' || !bundlePath}
          >
            {#if phase === 'running'}
              {$_('audit.repro.button_running', { default: 'Проверяется…' })}
            {:else}
              {$_('audit.repro.button_run', { default: 'Проверить воспроизводимость' })}
            {/if}
          </button>
        </div>

        <!--
          A4 (Sprint 4 Batch 4): persistent aria-live containers.
          JAWS/NVDA register live regions only when they're ALREADY in DOM
          at the moment content appears. If we conditionally render the
          .audit-error / .audit-result divs via {#if ...}, the screen reader
          doesn't see the appearance event reliably — announcement skipped.
          Fix: outer wrapper divs are ALWAYS in DOM с aria-live attributes;
          inner content is conditionally populated. When state transitions
          к 'error' or 'done', the new content appears WITHIN an existing
          live region — guaranteed announcement.
        -->
        <div class="audit-error-region" role="alert" aria-live="assertive">
          {#if phase === 'error' && errorMessage}
            <div class="audit-error">
              <strong>
                {$_('audit.repro.error_title', { default: 'Не удалось запустить проверку' })}:
              </strong>
              {errorMessage}
            </div>
          {/if}
        </div>

        <!--
          Sprint 4 Batch 7 A4-C1: aria-atomic removed (was over-announcing
          entire result block при details/summary toggle, including 50+ mismatch
          hashes — verbose UX). Inner .audit-result aria-live removed (was
          causing double-announce nested под outer aria-live="polite" — most
          AT read content twice). Outer wrapper alone is sufficient как
          persistent live region.
        -->
        <div class="audit-result-region" aria-live="polite">
          {#if phase === 'done' && result && statusDisplay}
            <div class="audit-result" data-tone={statusDisplay.tone}>
              <div class="audit-result-header">
                <span class="audit-result-badge" data-tone={statusDisplay.tone}>
                  {statusDisplay.label}
                </span>
                <span class="audit-result-summary">
                  {$_('audit.repro.files_checked', {
                    default: 'Проверено файлов: {count}',
                    values: { count: result.files_checked },
                  })}
                </span>
              </div>

              {#if result.reason}
                <p class="audit-result-reason">{result.reason}</p>
              {/if}

              <!--
                Sprint 4 Batch 7 C1: surface composite_hash к pilot user.
                Без UI rendering, INV-48 closure был incomplete at UX layer —
                pilot видел зелёный «Воспроизводимо» badge для forged bundle
                (per-file hashes recomputed). Surfacing the cross-binding hash
                с instructions enables pilot к manually verify против external
                signed methodology cert PDF. The composite_hash=null case
                (cross-binding unavailable) already surfaced through
                result.reason field above (set by Rust H1 fix when
                composite_bundle_hash_mirror returns Err).
              -->
              {#if result.composite_hash}
                <details class="audit-cross-binding">
                  <summary class="audit-cross-binding-summary">
                    {$_('audit.repro.cross_binding_heading', {
                      default: 'Кросс-привязка с сертификатом методологии',
                    })}
                  </summary>
                  <p class="audit-cross-binding-help">
                    {$_('audit.repro.cross_binding_help', {
                      default:
                        'Сверьте этот хеш с указанным в сертификате методологии — если совпадает, файлы не подменялись после подписи сертификата.',
                    })}
                  </p>
                  <code class="audit-cross-binding-hash">{result.composite_hash}</code>
                </details>
              {/if}

              {#if result.mismatches.length > 0}
                <details class="audit-mismatch-details" open>
                  <summary>
                    {$_('audit.repro.mismatches_heading', {
                      default: 'Расхождения ({n})',
                      values: { n: result.mismatches.length },
                    })}
                  </summary>
                  <ul class="audit-mismatch-list">
                    {#each result.mismatches as m (m.entry)}
                      <li class="audit-mismatch-item">
                        <code class="audit-mismatch-entry">{m.entry}</code>
                        <div class="audit-mismatch-hashes">
                          <div>
                            <span class="audit-mismatch-label">
                              {$_('audit.repro.expected', { default: 'Ожидалось:' })}
                            </span>
                            <code>{m.expected_sha256}</code>
                          </div>
                          <div>
                            <span class="audit-mismatch-label">
                              {$_('audit.repro.computed', { default: 'Получено:' })}
                            </span>
                            <code>{m.computed_sha256}</code>
                          </div>
                        </div>
                      </li>
                    {/each}
                  </ul>
                </details>
              {/if}
            </div>
          {/if}
        </div>
      </section>
    {/snippet}
  </Card>
</div>

<style>
  .audit-section {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-3, 0.75rem);
  }

  .audit-section-header {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-1, 0.25rem);
  }

  .audit-section-title {
    margin: 0;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary, #111);
  }

  .audit-section-desc {
    margin: 0;
    font-size: 0.875rem;
    color: var(--text-secondary, #555);
    line-height: 1.5;
  }

  .audit-actions {
    display: flex;
    gap: var(--spacing-2, 0.5rem);
  }

  .audit-repro-btn {
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

  .audit-repro-btn:hover:not(:disabled) {
    opacity: 0.9;
  }

  .audit-repro-btn:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }

  .audit-error {
    padding: var(--spacing-3, 0.75rem);
    background: color-mix(in srgb, var(--color-danger, #991b1b) 8%, transparent);
    border-left: 3px solid var(--color-danger, #991b1b);
    border-radius: 4px;
    color: var(--text-primary, #111);
    font-size: 0.875rem;
  }

  .audit-result {
    padding: var(--spacing-3, 0.75rem);
    border-radius: 6px;
    border: 1px solid var(--border-subtle, #d1d5db);
    background: var(--bg-elevated, #f8fafc);
  }

  .audit-result[data-tone='success'] {
    border-color: var(--color-success, #047857);
    background: color-mix(in srgb, var(--color-success, #047857) 6%, var(--bg-elevated, #f8fafc));
  }

  .audit-result[data-tone='danger'] {
    border-color: var(--color-danger, #991b1b);
    background: color-mix(in srgb, var(--color-danger, #991b1b) 6%, var(--bg-elevated, #f8fafc));
  }

  .audit-result-header {
    display: flex;
    align-items: center;
    gap: var(--spacing-3, 0.75rem);
    flex-wrap: wrap;
  }

  .audit-result-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 3px;
    font-weight: 600;
    font-size: 0.8125rem;
  }

  .audit-result-badge[data-tone='success'] {
    background: var(--color-success, #047857);
    color: #fff;
  }

  .audit-result-badge[data-tone='danger'] {
    background: var(--color-danger, #991b1b);
    color: #fff;
  }

  .audit-result-badge[data-tone='warning'] {
    background: var(--color-warning, #92400e);
    color: #fff;
  }

  .audit-result-summary {
    font-size: 0.875rem;
    color: var(--text-secondary, #555);
  }

  .audit-result-reason {
    margin: var(--spacing-2, 0.5rem) 0 0;
    font-size: 0.875rem;
    color: var(--text-primary, #111);
    font-style: italic;
  }

  /* Sprint 4 Batch 7 C1 — composite_hash cross-binding section */
  .audit-cross-binding {
    margin-top: var(--spacing-3, 0.75rem);
    padding: var(--spacing-2, 0.5rem);
    background: color-mix(in srgb, var(--color-ui-accent-primary, #2E5BFF) 4%, var(--bg-surface, #fff));
    border: 1px solid color-mix(in srgb, var(--color-ui-accent-primary, #2E5BFF) 20%, transparent);
    border-radius: 4px;
  }

  .audit-cross-binding-summary {
    cursor: pointer;
    font-weight: 500;
    color: var(--text-primary, #111);
    font-size: 0.875rem;
  }

  .audit-cross-binding-help {
    margin: var(--spacing-2, 0.5rem) 0 var(--spacing-2, 0.5rem);
    font-size: 0.8125rem;
    color: var(--text-secondary, #555);
    line-height: 1.45;
  }

  .audit-cross-binding-hash {
    display: block;
    padding: var(--spacing-2, 0.5rem);
    background: var(--bg-surface, #fff);
    border: 1px solid var(--border-subtle, #d1d5db);
    border-radius: 3px;
    font-family: var(--font-mono, monospace);
    font-size: 0.75rem;
    color: var(--text-primary, #111);
    word-break: break-all;
    user-select: all;
  }

  .audit-mismatch-details {
    margin-top: var(--spacing-3, 0.75rem);
  }

  .audit-mismatch-details summary {
    cursor: pointer;
    font-weight: 500;
    color: var(--text-primary, #111);
    font-size: 0.875rem;
  }

  .audit-mismatch-list {
    list-style: none;
    margin: var(--spacing-2, 0.5rem) 0 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2, 0.5rem);
  }

  .audit-mismatch-item {
    padding: var(--spacing-2, 0.5rem);
    background: var(--bg-surface, #fff);
    border: 1px solid var(--border-subtle, #d1d5db);
    border-radius: 4px;
  }

  .audit-mismatch-entry {
    display: block;
    font-family: var(--font-mono, monospace);
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--text-primary, #111);
    margin-bottom: var(--spacing-1, 0.25rem);
  }

  .audit-mismatch-hashes {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: 0.75rem;
    color: var(--text-secondary, #555);
  }

  .audit-mismatch-hashes code {
    font-family: var(--font-mono, monospace);
    color: var(--text-primary, #111);
    word-break: break-all;
  }

  .audit-mismatch-label {
    color: var(--text-muted, #6b7280);
    margin-right: 4px;
  }

  @media (prefers-reduced-motion: reduce) {
    .audit-repro-btn {
      transition: none;
    }
  }
</style>
