<!--
  CertExportModal — Sprint 3 D5 Methodology Certificate PDF export.

  Strategy: ADR-006-compliant Tauri webview print path.  Renders cert HTML in a
  full-screen overlay, then `window.print()` invokes Edge/Chromium's native
  print dialog where user picks "Save as PDF" — produces a clean ~100-500KB PDF
  без новых Rust crate-зависимостей (printpdf/genpdf отклонены as overkill для
  D5 scope).

  Cyrillic + Inter font handled by webview's existing @fontsource stack.

  Print CSS rules use :global() to penetrate Svelte scoped styles — when user
  triggers Print, ALL of body except .cert-print-area is hidden via visibility,
  then .cert-print-area is positioned absolutely.  No new windows opened, no
  side-channel data passed.
-->

<script lang="ts">
  import { _ } from 'svelte-i18n';
  import type { VerificationResult } from '$ipc/client';
  import { getFormula, type FormulaEntry } from '$lib/utils/formulas';

  interface Props {
    /** Visibility — controlled by parent. */
    open: boolean;
    /** Verification result (composite_hash, signature provenance, etc). */
    verification: VerificationResult;
    /** Absolute path to the bundle .aurora file. */
    bundlePath: string;
    /** App version (for cert footer). */
    appVersion: string;
    /** Close callback. */
    onClose: () => void;
  }

  let { open, verification, bundlePath, appVersion, onClose }: Props = $props();

  // ── Derived display values ──────────────────────────────────────────────

  const bundleFileName = $derived(
    bundlePath.split(/[\\\/]/).pop() ?? bundlePath,
  );

  const certIdFull = $derived(verification.composite_hash ?? '');
  const certIdShort = $derived(
    certIdFull.length > 16 ? certIdFull.slice(0, 16) + '…' : certIdFull || '—',
  );

  const generatedAt = $derived(
    new Date().toLocaleString('ru-RU', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }),
  );

  const trustBadgeLabel = $derived.by(() => {
    const map: Record<string, string> = {
      production: 'Production',
      dev: 'Development (Local-Dev)',
      sample: 'Demo / Sample',
      warning: 'Не подтверждён',
    };
    return map[verification.trust_badge] ?? verification.trust_badge;
  });

  // Pick a curated set of methodology references — 6 formulas most relevant
  // to the cert (similarity, conformal/MCMC intervals, baseline forecast,
  // signature, hash).  Order matches typical pipeline narrative.
  const METHODOLOGY_KEYS = [
    'similarity_jensen_shannon',
    'conformal_prediction_interval',
    'mcmc_credible_interval',
    'forecast_baseline_projection',
    'methodology_cert_signature_ed25519',
    'bundle_hash_sha256',
  ] as const;

  const methodologyRefs: FormulaEntry[] = METHODOLOGY_KEYS
    .map(getFormula)
    .filter((f): f is FormulaEntry => f !== null);

  // ── Actions ──────────────────────────────────────────────────────────────

  function printCert(): void {
    // Defer one tick so the print rules apply against fully-rendered DOM.
    requestAnimationFrame(() => window.print());
  }

  // ── Focus management ─────────────────────────────────────────────────────

  let overlayEl: HTMLElement | undefined = $state();

  /** Return all keyboard-focusable children of el. */
  function focusable(el: HTMLElement): HTMLElement[] {
    return Array.from(
      el.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ),
    );
  }

  function handleKeydown(e: KeyboardEvent): void {
    if (e.key === 'Escape') {
      onClose();
      return;
    }

    if (e.key === 'Tab' && overlayEl) {
      const items = focusable(overlayEl);
      if (items.length === 0) {
        e.preventDefault();
        return;
      }
      const first = items[0]!;
      const last = items[items.length - 1]!;
      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
  }

  // Focus the Print button on open (most likely user action).
  $effect(() => {
    if (open && overlayEl) {
      requestAnimationFrame(() => {
        const btn = overlayEl?.querySelector<HTMLButtonElement>('.cert-print-btn');
        btn?.focus();
      });
    }
  });
</script>

{#if open}
  <!-- Overlay covers app on screen; hidden entirely on print. -->
  <div
    class="cert-export-overlay"
    role="dialog"
    aria-modal="true"
    aria-labelledby="cert-export-title"
    onkeydown={handleKeydown}
    tabindex="-1"
    bind:this={overlayEl}
  >
    <header class="cert-export-toolbar">
      <h2 id="cert-export-title">{$_('cert.export.toolbar_title', { default: 'Экспорт сертификата' })}</h2>
      <div class="cert-export-actions">
        <button type="button" onclick={printCert} class="cert-print-btn">
          {$_('cert.export.print_button', { default: 'Сохранить PDF' })}
        </button>
        <button type="button" onclick={onClose} aria-label={$_('cert.export.close_aria', { default: 'Закрыть' })} class="cert-close-btn">
          ✕
        </button>
      </div>
    </header>

    <!-- Cert content — only this element survives @media print rules. -->
    <article class="cert-print-area">
      <header class="cert-header">
        <h1>{$_('cert.export.title', { default: 'Сертификат методологии' })}</h1>
        <p class="cert-subtitle">
          {$_('cert.export.subtitle', { default: 'Aurora Launch — прогноз продаж нового бренда на основе прокси-бренда' })}
        </p>
      </header>

      <section class="cert-section">
        <h2>{$_('cert.export.section_bundle', { default: 'Информация о бандле' })}</h2>
        <dl>
          <dt>Файл:</dt><dd>{bundleFileName}</dd>
          <dt>Cert ID:</dt><dd class="cert-mono" title={certIdFull}>{certIdShort}</dd>
          <dt>Manifest revision:</dt><dd>{verification.manifest_revision ?? '—'}</dd>
        </dl>
      </section>

      <section class="cert-section">
        <h2>{$_('cert.export.section_signature', { default: 'Электронная подпись' })}</h2>
        <dl>
          <dt>Уровень доверия:</dt>
          <dd>
            <span class="cert-badge cert-badge-{verification.trust_badge}">{trustBadgeLabel}</span>
          </dd>
          <dt>Источник подписи:</dt><dd>{verification.signature_provenance}</dd>
          <dt>Подписант:</dt><dd>{verification.signed_by ?? '—'}</dd>
          <dt>Дата подписи:</dt><dd>{verification.signed_at ?? '—'}</dd>
          <dt>Отпечаток ключа:</dt><dd class="cert-mono">{verification.key_fingerprint ?? '—'}</dd>
          <dt>Статус проверки:</dt>
          <dd class:cert-warn={!verification.valid}>
            {verification.valid ? '✓ Подпись валидна' : '✗ Подпись недействительна'}
          </dd>
          {#if verification.failure_reason}
            <dt>Причина расхождения:</dt>
            <dd class="cert-warn">{verification.failure_reason}</dd>
          {/if}
        </dl>
      </section>

      <section class="cert-section">
        <h2>{$_('cert.export.section_methodologies', { default: 'Используемые методологии' })}</h2>
        <ol class="cert-refs">
          {#each methodologyRefs as ref (ref.key)}
            <li>
              <strong>{ref.title}</strong>
              <p class="cert-ref-explanation">{ref.explanation}</p>
              <p class="cert-ref-citation">
                <em>{ref.provenance.citation}</em>
                {#if ref.provenance.url}<br /><span class="cert-mono cert-ref-url">{ref.provenance.url}</span>{/if}
              </p>
            </li>
          {/each}
        </ol>
      </section>

      <section class="cert-section">
        <h2>{$_('cert.export.section_reproducibility', { default: 'Воспроизводимость' })}</h2>
        <p>
          {$_('cert.export.repro_intro', { default: 'Для проверки бандла на bit-equal соответствие используйте CLI:' })}
        </p>
        <pre class="cert-cmd cert-mono">aurora-launch-reproduce "{bundleFileName}" {certIdFull || '<hash>'}</pre>
        <p class="cert-fineprint">
          {$_('cert.export.repro_explanation', {
            default: 'Команда сверит композитный hash бандла с зафиксированным в сертификате значением. Расхождение указывает на изменение содержимого бандла или версии Aurora Launch, использованной при его сборке.',
          })}
        </p>
      </section>

      <footer class="cert-footer">
        <p>
          {$_('cert.export.generated_at', { default: 'Сертификат сгенерирован:' })}
          <strong>{generatedAt}</strong>
        </p>
        <p>
          {$_('cert.export.app_version', { default: 'Версия Aurora Launch:' })}
          <strong>{appVersion || '—'}</strong>
        </p>
        <p class="cert-fineprint">
          {$_('cert.export.disclaimer', {
            default: 'Aurora Launch © Aurora AI. Документ не является юридически обязывающим, а отражает результаты статистической методологии прогнозирования.',
          })}
        </p>
      </footer>
    </article>
  </div>
{/if}

<style>
  /* ── Screen overlay (hidden on print) ──────────────────────────────────── */

  .cert-export-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    z-index: 1500;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    outline: none;
  }

  .cert-export-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--spacing-3, 0.75rem);
    padding: var(--spacing-3, 0.75rem) var(--spacing-6, 1.5rem);
    background: var(--bg-surface, #fff);
    border-bottom: 1px solid var(--border-subtle, #d1d5db);
    position: sticky;
    top: 0;
    z-index: 10;
  }

  .cert-export-toolbar h2 {
    margin: 0;
    font-size: 1.125rem;
    color: var(--text-primary, #111);
  }

  .cert-export-actions {
    display: flex;
    gap: var(--spacing-2, 0.5rem);
  }

  .cert-print-btn {
    padding: 6px 14px;
    background: var(--accent, #2e5bff);
    color: #fff;
    border: 1px solid var(--accent, #2e5bff);
    border-radius: 4px;
    cursor: pointer;
    font-weight: 500;
    font-size: 0.875rem;
    transition: opacity 120ms ease;
  }

  .cert-print-btn:hover {
    opacity: 0.9;
  }

  .cert-close-btn {
    padding: 6px 12px;
    background: transparent;
    border: 1px solid var(--border-subtle, #d1d5db);
    color: var(--text-muted, #6b7280);
    border-radius: 4px;
    cursor: pointer;
    transition: color 120ms ease, border-color 120ms ease;
  }

  .cert-close-btn:hover {
    color: var(--text-primary, #111);
    border-color: var(--text-secondary, #555);
  }

  /* ── Cert print area (visible on screen + on print) ───────────────────── */

  .cert-print-area {
    background: #fff;
    color: #111;
    max-width: 720px;
    margin: var(--spacing-6, 1.5rem) auto;
    padding: 48px 56px;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.2);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    line-height: 1.55;
    font-size: 0.9375rem;
  }

  .cert-header {
    border-bottom: 2px solid #2e5bff;
    padding-bottom: 16px;
    margin-bottom: 24px;
  }

  .cert-header h1 {
    font-size: 1.75rem;
    margin: 0;
    color: #111;
    font-weight: 700;
  }

  .cert-subtitle {
    margin: 6px 0 0;
    color: #555;
    font-size: 0.9375rem;
  }

  .cert-section {
    margin-bottom: 32px;
  }

  .cert-section h2 {
    font-size: 1.125rem;
    margin: 0 0 12px;
    color: #2e5bff;
    border-bottom: 1px solid #ddd;
    padding-bottom: 4px;
    font-weight: 600;
  }

  .cert-section dl {
    display: grid;
    grid-template-columns: 200px 1fr;
    gap: 6px 16px;
    margin: 0;
  }

  .cert-section dt {
    color: #555;
    font-weight: 500;
  }

  .cert-section dd {
    margin: 0;
    color: #111;
    word-break: break-word;
  }

  .cert-mono {
    font-family: 'JetBrains Mono', 'Consolas', 'Courier New', monospace;
    font-size: 0.875rem;
  }

  .cert-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 3px;
    font-size: 0.8125rem;
    font-weight: 600;
  }

  .cert-badge-production {
    background: #d1fae5;
    color: #047857;
  }

  .cert-badge-dev {
    background: #fef3c7;
    color: #92400e;
  }

  .cert-badge-sample {
    background: #e0e7ff;
    color: #3730a3;
  }

  .cert-badge-warning {
    background: #fee2e2;
    color: #991b1b;
  }

  .cert-warn {
    color: #991b1b;
    font-style: italic;
  }

  .cert-refs {
    margin: 0;
    padding-left: 20px;
  }

  .cert-refs li {
    margin-bottom: 14px;
  }

  .cert-ref-explanation {
    margin: 4px 0;
    color: #444;
  }

  .cert-ref-citation {
    margin: 4px 0 0;
    color: #666;
    font-size: 0.8125rem;
  }

  .cert-ref-url {
    color: #2e5bff;
  }

  .cert-cmd {
    background: #f3f4f6;
    padding: 10px 14px;
    border-radius: 4px;
    border: 1px solid #ddd;
    overflow-x: auto;
    margin: 8px 0;
    white-space: pre-wrap;
    word-break: break-all;
  }

  .cert-fineprint {
    color: #555;
    font-size: 0.8125rem;
  }

  .cert-footer {
    border-top: 1px solid #ddd;
    padding-top: 16px;
    margin-top: 32px;
  }

  .cert-footer p {
    margin: 0 0 4px;
  }

  /* ── Print rules (Tauri webview → Edge print → Save as PDF) ───────────── */

  @media print {
    /* Hide everything in body, then make cert content visible. */
    :global(body *) {
      visibility: hidden;
    }

    :global(.cert-print-area),
    :global(.cert-print-area *) {
      visibility: visible;
    }

    /* Position cert content absolutely so it occupies full page. */
    :global(.cert-print-area) {
      position: absolute;
      left: 0;
      top: 0;
      width: 100%;
      max-width: none;
      margin: 0;
      padding: 0;
      box-shadow: none;
    }

    /* Hide overlay backdrop in print output. */
    .cert-export-overlay {
      position: static;
      background: none;
      overflow: visible;
    }

    .cert-export-toolbar {
      display: none !important;
    }

    /* Strip URL hovers in print. */
    :global(.cert-print-area a) {
      color: #111;
      text-decoration: none;
    }

    /* A4 page setup. */
    @page {
      size: A4;
      margin: 1.2cm 1.5cm;
    }
  }

  /* ── INV-14 reduced motion ────────────────────────────────────────────── */

  @media (prefers-reduced-motion: reduce) {
    .cert-print-btn,
    .cert-close-btn {
      transition: none;
    }
  }
</style>
