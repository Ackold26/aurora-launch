/**
 * Unit tests for frontend/src/lib/services/tiered_redact.ts
 * Phase 2.D.2 HE-6.
 *
 * Tests:
 *  1. basic scrubs email
 *  2. basic scrubs Russian phone (+7XXXXXXXXXX)
 *  3. basic scrubs Russian phone (8XXXXXXXXXX)
 *  4. basic scrubs IPv4
 *  5. basic preserves customer_name field value (not scrubbed at basic)
 *  6. strict additionally scrubs customer_name JSON key
 *  7. strict additionally scrubs Windows file path
 *  8. strict additionally scrubs Unix file path
 *  9. strict does NOT scrub UUID (paranoid only)
 * 10. paranoid scrubs UUID
 * 11. paranoid scrubs 32-char hex (MD5)
 * 12. paranoid scrubs 64-char hex (SHA-256)
 * 13. paranoid scrubs ISO timestamp (with Z suffix)
 * 14. paranoid does NOT scrub plain date (2026-05-16)
 * 15. default tier is 'basic' (no tier argument)
 * 16. scrubPii recurses into nested objects
 * 17. scrubPii recurses into arrays
 * 18. scrubPii passes non-string primitives unchanged
 */

import { describe, it, expect } from 'vitest';
import { scrubPii, scrubPiiString } from '../../src/lib/services/tiered_redact';

// ─── 1. basic: email ─────────────────────────────────────────────────────────

describe('basic tier — email', () => {
  it('scrubs a plain email address', () => {
    const out = scrubPiiString('contact: test@example.com', 'basic');
    expect(out).not.toContain('test@example.com');
    expect(out).toContain('[EMAIL]');
  });

  it('scrubs multiple emails in one string', () => {
    const out = scrubPiiString('from: a@x.io to: b@y.com', 'basic');
    expect(out).not.toContain('a@x.io');
    expect(out).not.toContain('b@y.com');
  });
});

// ─── 2–3. basic: Russian phone ───────────────────────────────────────────────

describe('basic tier — Russian phone', () => {
  it('scrubs +7XXXXXXXXXX format', () => {
    const out = scrubPiiString('phone: +79161234567', 'basic');
    expect(out).not.toContain('79161234567');
    expect(out).toContain('[PHONE]');
  });

  it('scrubs 8XXXXXXXXXX format', () => {
    const out = scrubPiiString('tel: 89161234567', 'basic');
    expect(out).not.toContain('89161234567');
    expect(out).toContain('[PHONE]');
  });
});

// ─── 4. basic: IPv4 ──────────────────────────────────────────────────────────

describe('basic tier — IPv4', () => {
  it('scrubs an IPv4 address', () => {
    const out = scrubPiiString('client 192.168.1.100 connected', 'basic');
    expect(out).not.toContain('192.168.1.100');
    expect(out).toContain('[IP]');
  });
});

// ─── 5. basic: preserves customer_name ───────────────────────────────────────

describe('basic tier — customer_name preserved', () => {
  it('does NOT scrub customer_name field value at basic tier', () => {
    const out = scrubPiiString('{"customer_name": "Иванов Иван"}', 'basic');
    expect(out).toContain('Иванов Иван');
  });
});

// ─── 6–8. strict tier ────────────────────────────────────────────────────────

describe('strict tier — customer_name', () => {
  it('scrubs customer_name JSON key value', () => {
    const out = scrubPiiString(
      '{"customer_name": "Petrov Pavel", "event": "login"}',
      'strict',
    );
    expect(out).not.toContain('Petrov Pavel');
    expect(out).toContain('[NAME]');
    expect(out).toContain('login'); // other fields preserved
  });
});

describe('strict tier — file paths', () => {
  it('scrubs Windows absolute path', () => {
    const out = scrubPiiString(
      'file opened C:/Users/john/Documents/data.xlsx',
      'strict',
    );
    expect(out).not.toContain('C:/Users/john/Documents/data.xlsx');
    expect(out).toContain('[PATH]');
  });

  it('scrubs Unix /home/... path', () => {
    const out = scrubPiiString('reading /home/ubuntu/aurora/data.csv', 'strict');
    expect(out).not.toContain('/home/ubuntu/aurora/data.csv');
    expect(out).toContain('[PATH]');
  });
});

// ─── 9. strict: does NOT scrub UUID ──────────────────────────────────────────

describe('strict tier — UUID preserved', () => {
  it('does NOT scrub UUID at strict tier', () => {
    const uuid = '550e8400-e29b-41d4-a716-446655440000';
    const out = scrubPiiString(`id=${uuid}`, 'strict');
    expect(out).toContain(uuid);
  });
});

// ─── 10–14. paranoid tier ────────────────────────────────────────────────────

describe('paranoid tier — UUID', () => {
  it('scrubs UUID v4', () => {
    const uuid = '550e8400-e29b-41d4-a716-446655440000';
    const out = scrubPiiString(`project_id=${uuid}`, 'paranoid');
    expect(out).not.toContain(uuid);
    expect(out).toContain('[UUID]');
  });
});

describe('paranoid tier — hex hashes', () => {
  it('scrubs 32-char hex (MD5-like)', () => {
    const md5 = 'd41d8cd98f00b204e9800998ecf8427e';
    const out = scrubPiiString(`hash=${md5}`, 'paranoid');
    expect(out).not.toContain(md5);
    expect(out).toContain('[HASH]');
  });

  it('scrubs 64-char hex (SHA-256)', () => {
    const sha256 =
      'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855';
    const out = scrubPiiString(`sha256=${sha256}`, 'paranoid');
    expect(out).not.toContain(sha256);
    expect(out).toContain('[HASH]');
  });
});

describe('paranoid tier — timestamps', () => {
  it('scrubs ISO timestamp with Z suffix', () => {
    const out = scrubPiiString(
      'occurred at 2026-05-16T12:34:56.789Z',
      'paranoid',
    );
    expect(out).not.toContain('2026-05-16T12:34:56.789Z');
    expect(out).toContain('[TS]');
  });

  it('scrubs ISO timestamp with +03:00 offset', () => {
    const out = scrubPiiString(
      'created 2026-05-16T09:00:00+03:00',
      'paranoid',
    );
    expect(out).not.toContain('2026-05-16T09:00:00+03:00');
    expect(out).toContain('[TS]');
  });

  it('does NOT scrub a plain date (no time component)', () => {
    const out = scrubPiiString('report date 2026-05-16', 'paranoid');
    expect(out).toContain('2026-05-16');
  });
});

// ─── 15. default tier is basic ───────────────────────────────────────────────

describe('scrubPiiString default tier', () => {
  it('defaults to basic when no tier passed', () => {
    const out = scrubPiiString('user@example.com');
    expect(out).not.toContain('user@example.com');
    expect(out).toContain('[EMAIL]');
  });
});

// ─── 16–18. scrubPii recursive behaviour ─────────────────────────────────────

describe('scrubPii — recursive object/array', () => {
  it('recurses into nested objects', () => {
    const input = {
      user: { email: 'admin@corp.io', name: 'Alice' },
      score: 42,
    };
    const out = scrubPii(input, 'basic') as typeof input;
    expect((out.user as { email: string }).email).not.toContain('admin@corp.io');
    expect((out.user as { email: string }).email).toContain('[EMAIL]');
    expect((out as { score: number }).score).toBe(42); // numbers pass through
  });

  it('recurses into arrays', () => {
    const input = ['info@x.com', 'hello world', 'test@y.org'];
    const out = scrubPii(input, 'basic') as string[];
    expect(out[0]).toContain('[EMAIL]');
    expect(out[1]).toBe('hello world');
    expect(out[2]).toContain('[EMAIL]');
  });

  it('passes non-string primitives unchanged', () => {
    expect(scrubPii(42, 'paranoid')).toBe(42);
    expect(scrubPii(true, 'paranoid')).toBe(true);
    expect(scrubPii(null, 'paranoid')).toBeNull();
  });
});
