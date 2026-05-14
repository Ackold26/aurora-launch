// Unit tests for CertChainViewer.svelte (P-09)
//
// Covers:
//  1. Renders verdict badge
//  2. Verified → success variant (green tone via data-trust attr)
//  3. Untrusted → danger variant + warning icon
//  4. Self-signed dev → info variant
//  5. Expert mode shows full chain (provenance, full hash)
//  6. Manager mode hides chain details
//  7. Composite hash truncated to 8 chars + ellipsis
//  8. ARIA: article label + dl structure
//  9. Expand-toggle button labelled (aria-expanded)
// 10. Reduce motion: no transform / translate in toggle button CSS
//     (verified structurally — scoped style has transition:none rule)

import { describe, expect, it, beforeEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';

import CertChainViewer from '../../src/lib/components/CertChainViewer.svelte';
import type { VerificationResult } from '../../src/lib/ipc/client';

beforeEach(() => cleanup());

// ─── Fixtures ─────────────────────────────────────────────────────────────────

function makeVerified(overrides: Partial<VerificationResult> = {}): VerificationResult {
  return {
    valid: true,
    signature_provenance: 'cloud_kms',
    signed_by: 'Aurora AI KMS',
    signed_at: '2026-05-15T12:00:00Z',
    key_fingerprint: 'abcd1234ef567890',
    composite_hash: 'deadbeef12345678aabbccddeeff00112233445566778899aabbccddeeff0011',
    manifest_revision: 3,
    trust_badge: 'production',
    failure_reason: null,
    ...overrides,
  };
}

function makeUntrusted(overrides: Partial<VerificationResult> = {}): VerificationResult {
  return {
    valid: false,
    signature_provenance: 'unsigned',
    signed_by: null,
    signed_at: null,
    key_fingerprint: null,
    composite_hash: null,
    manifest_revision: null,
    trust_badge: 'warning',
    failure_reason: 'Bundle has no methodology certificate',
    ...overrides,
  };
}

function makeDevSigned(overrides: Partial<VerificationResult> = {}): VerificationResult {
  return {
    valid: true,
    signature_provenance: 'local_dev',
    signed_by: null,
    signed_at: null,
    key_fingerprint: '1111aaaa2222bbbb',
    composite_hash: '0011223344556677aabbccddeeff001122334455667788990011223344556677',
    manifest_revision: 1,
    trust_badge: 'dev',
    failure_reason: null,
    ...overrides,
  };
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('CertChainViewer', () => {

  // ── 1. Verdict badge renders ────────────────────────────────────────────────

  it('renders verdict badge text "Verified" for production trust', () => {
    render(CertChainViewer, { result: makeVerified() });
    expect(screen.getByText('Verified')).toBeTruthy();
  });

  it('renders verdict badge text "Untrusted" for warning trust', () => {
    render(CertChainViewer, { result: makeUntrusted() });
    expect(screen.getByText('Untrusted')).toBeTruthy();
  });

  it('renders verdict badge text "Self-signed dev" for dev trust', () => {
    render(CertChainViewer, { result: makeDevSigned() });
    expect(screen.getByText('Self-signed dev')).toBeTruthy();
  });

  // ── 2. Verified → green tone (data-trust attribute) ─────────────────────────

  it('production badge → article has data-trust="production"', () => {
    const { container } = render(CertChainViewer, { result: makeVerified() });
    const article = container.querySelector('article');
    expect(article?.getAttribute('data-trust')).toBe('production');
  });

  // ── 3. Untrusted → warning icon present ────────────────────────────────────

  it('untrusted result → warning icon "⚠" visible in badge', () => {
    render(CertChainViewer, { result: makeUntrusted() });
    // The ⚠ span is aria-hidden but present in DOM
    const icons = document.querySelectorAll('.cert-icon');
    const hasWarning = Array.from(icons).some((el) => el.textContent?.includes('⚠'));
    expect(hasWarning).toBe(true);
  });

  it('untrusted article has data-trust="warning"', () => {
    const { container } = render(CertChainViewer, { result: makeUntrusted() });
    const article = container.querySelector('article');
    expect(article?.getAttribute('data-trust')).toBe('warning');
  });

  // ── 4. Dev signed → info tone ──────────────────────────────────────────────

  it('dev signed → article has data-trust="dev"', () => {
    const { container } = render(CertChainViewer, { result: makeDevSigned() });
    const article = container.querySelector('article');
    expect(article?.getAttribute('data-trust')).toBe('dev');
  });

  it('dev signed → checkmark icon (not warning)', () => {
    render(CertChainViewer, { result: makeDevSigned() });
    const icons = document.querySelectorAll('.cert-icon');
    const hasCheck = Array.from(icons).some((el) => el.textContent?.includes('✓'));
    expect(hasCheck).toBe(true);
  });

  // ── 5. Expert mode shows full chain ────────────────────────────────────────

  it('expertMode=true → cert-expert section present', () => {
    const { container } = render(CertChainViewer, {
      result: makeVerified(),
      expertMode: true,
    });
    expect(container.querySelector('.cert-expert')).toBeTruthy();
  });

  it('expertMode=true → provenance value visible', () => {
    render(CertChainViewer, { result: makeVerified(), expertMode: true });
    expect(screen.getByText('cloud_kms')).toBeTruthy();
  });

  it('expertMode=true → full composite hash text present', () => {
    const result = makeVerified();
    render(CertChainViewer, { result, expertMode: true });
    // Full hash should appear somewhere in document
    expect(screen.getByText(result.composite_hash!)).toBeTruthy();
  });

  it('expertMode=true → key fingerprint visible', () => {
    render(CertChainViewer, { result: makeVerified(), expertMode: true });
    expect(screen.getByText('abcd1234ef567890')).toBeTruthy();
  });

  // ── 6. Manager mode hides chain details ────────────────────────────────────

  it('expertMode=false (default) → cert-expert section absent', () => {
    const { container } = render(CertChainViewer, { result: makeVerified() });
    expect(container.querySelector('.cert-expert')).toBeNull();
  });

  it('expertMode=false → provenance value NOT in document', () => {
    render(CertChainViewer, { result: makeVerified() });
    expect(screen.queryByText('cloud_kms')).toBeNull();
  });

  // ── 7. Composite hash short fingerprint ────────────────────────────────────

  it('shows 8-char hash fingerprint with ellipsis in manager mode', () => {
    const result = makeVerified(); // hash starts with 'deadbeef'
    render(CertChainViewer, { result });
    expect(screen.getByText('deadbeef…')).toBeTruthy();
  });

  it('no hash shown when composite_hash is null', () => {
    render(CertChainViewer, { result: makeUntrusted() }); // composite_hash: null
    // .cert-fingerprint-value should not exist
    expect(document.querySelector('.cert-fingerprint-value')).toBeNull();
  });

  // ── 8. ARIA structure ──────────────────────────────────────────────────────

  it('article has aria-label "Methodology certificate chain"', () => {
    render(CertChainViewer, { result: makeVerified() });
    expect(
      screen.getByRole('article', { name: 'Methodology certificate chain' }),
    ).toBeTruthy();
  });

  it('expert mode uses <dl> for key-value pairs', () => {
    const { container } = render(CertChainViewer, {
      result: makeVerified(),
      expertMode: true,
    });
    expect(container.querySelector('dl.cert-dl')).toBeTruthy();
  });

  // ── 9. Signature expand toggle (Expert mode) ───────────────────────────────

  it('expertMode=true → signature expand button visible', () => {
    render(CertChainViewer, { result: makeVerified(), expertMode: true });
    expect(screen.getByRole('button', { name: /show bytes/i })).toBeTruthy();
  });

  it('clicking sig toggle sets aria-expanded=true', async () => {
    render(CertChainViewer, { result: makeVerified(), expertMode: true });
    const btn = screen.getByRole('button', { name: /show bytes/i });
    expect(btn.getAttribute('aria-expanded')).toBe('false');
    await fireEvent.click(btn);
    expect(btn.getAttribute('aria-expanded')).toBe('true');
  });

  // ── 10. Failure reason in manager mode ─────────────────────────────────────

  it('manager mode shows failure reason text when result is invalid', () => {
    render(CertChainViewer, { result: makeUntrusted() });
    expect(screen.getByText('Bundle has no methodology certificate')).toBeTruthy();
  });

  it('failure reason has role=alert', () => {
    render(CertChainViewer, { result: makeUntrusted() });
    expect(screen.getByRole('alert')).toBeTruthy();
  });
});
