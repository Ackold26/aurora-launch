/**
 * Tiered PII redaction for telemetry payloads (Phase 2.D.2 HE-6).
 *
 * Three tiers:
 *   basic    (default) — email, phone (RUS +7/8 + 10 digits), IPv4
 *   strict   — basic + customer_name + file paths (C:/... or /home/...)
 *   paranoid — strict + UUIDs, 32/64-char hex hashes, ISO timestamps
 *
 * The existing scrubPii() in telemetry.ts (field-name allow-list) is
 * complementary. This module operates on *string values* inside payloads.
 *
 * Backwards compat: calling scrubPiiValue(v) without tier defaults to 'basic'.
 * Existing callers that pass payload objects to the old scrubPii() are
 * unaffected — that function is not modified.
 */

export type RedactionTier = 'basic' | 'strict' | 'paranoid';

// ─── Regex patterns ───────────────────────────────────────────────────────────

/** RFC-5322-ish email (local@domain.tld). */
const RE_EMAIL = /[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/g;

/**
 * Russian phone numbers:
 *   +7XXXXXXXXXX  (10 digits after country code)
 *   8XXXXXXXXXX   (10 digits after leading 8)
 * Also handles spaces/dashes inside the number.
 */
const RE_PHONE_RU = /(?:\+7|8)[\ \-]?\(?\d{3}\)?[\ \-]?\d{3}[\ \-]?\d{2}[\ \-]?\d{2}/g;

/** IPv4 addresses. False-positive guard: must be preceded by non-digit. */
const RE_IPV4 = /(?<![0-9])(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)(?![0-9])/g;

/** Windows absolute paths (C:\... or C:/...) and Unix paths (/home/... /Users/...). */
const RE_FILEPATH =
  /(?:[A-Za-z]:[\\\/][^\s"',;|]{3,}|\/(?:home|Users|root|tmp|var|etc|opt|mnt)[^\s"',;|]{2,})/g;

/** Customer name field — only matched in strict+ as a JSON key. */
const RE_CUSTOMER_NAME_KEY = /(?:"customer_name"\s*:\s*)"([^"]{1,200})"/g;

/** UUID v4 (8-4-4-4-12). */
const RE_UUID =
  /[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}/gi;

/** 32-char hex (MD5) or 64-char hex (SHA-256). */
const RE_HEX_HASH = /\b[0-9a-f]{64}\b|\b[0-9a-f]{32}\b/g;

/**
 * ISO 8601 timestamps: 2026-05-16T12:34:56Z or 2026-05-16T12:34:56.789Z
 * or 2026-05-16T12:34:56+03:00. Does NOT match plain dates (2026-05-16)
 * to avoid clobbering date fields that are not PII.
 */
const RE_ISO_TIMESTAMP =
  /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})/g;

// ─── Core scrubber ────────────────────────────────────────────────────────────

/**
 * Scrub PII from a string value according to the given tier.
 *
 * @param value - Any string that may contain PII.
 * @param tier  - Redaction aggressiveness. Defaults to 'basic'.
 * @returns     - Redacted copy of the string.
 */
export function scrubPiiString(value: string, tier: RedactionTier = 'basic'): string {
  // basic: email, phone (RUS), IPv4
  let out = value
    .replace(RE_EMAIL, '[EMAIL]')
    .replace(RE_PHONE_RU, '[PHONE]')
    .replace(RE_IPV4, '[IP]');

  if (tier === 'basic') return out;

  // strict: basic + file paths + customer_name JSON key
  out = out
    .replace(RE_FILEPATH, '[PATH]')
    .replace(RE_CUSTOMER_NAME_KEY, '"customer_name":"[NAME]"');

  if (tier === 'strict') return out;

  // paranoid: strict + UUIDs, hex hashes, ISO timestamps
  out = out
    .replace(RE_UUID, '[UUID]')
    .replace(RE_HEX_HASH, '[HASH]')
    .replace(RE_ISO_TIMESTAMP, '[TS]');

  return out;
}

/**
 * Recursively scrub PII from an arbitrary value (string, object, array).
 *
 * - strings: scrubPiiString()
 * - objects: recurse over values (keys are not scrubbed — field names are not PII)
 * - arrays: recurse over elements
 * - primitives: pass through unchanged
 */
export function scrubPii(value: unknown, tier: RedactionTier = 'basic'): unknown {
  if (typeof value === 'string') {
    return scrubPiiString(value, tier);
  }
  if (Array.isArray(value)) {
    return value.map((el) => scrubPii(el, tier));
  }
  if (value !== null && typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      out[k] = scrubPii(v, tier);
    }
    return out;
  }
  return value;
}
