// #51 — tokens.vendored.json must stay in sync with the design-system SSOT.
// Verifies the normalization/compare logic and (when the SSOT sibling is
// present, i.e. dev machines) the actual vendored↔SSOT equality.

import { describe, it, expect } from 'vitest';
import { promises as fs } from 'node:fs';
import {
  SSOT_PATH,
  VENDORED_PATH,
  VENDORED_ANNOTATION_KEY,
  normalizeVendored,
  tokensMatch,
} from '../../scripts/check-tokens-vendored.mjs';

async function readJson(p: string): Promise<any> {
  return JSON.parse(await fs.readFile(p, 'utf-8'));
}

async function exists(p: string): Promise<boolean> {
  try {
    await fs.access(p);
    return true;
  } catch {
    return false;
  }
}

describe('tokens vendored sync (#51)', () => {
  it('normalizeVendored strips the vendored annotation without mutating the input', async () => {
    const vendored = await readJson(VENDORED_PATH);
    expect(vendored.$metadata?.[VENDORED_ANNOTATION_KEY]).toBeDefined();

    const norm = normalizeVendored(vendored);
    expect(norm.$metadata?.[VENDORED_ANNOTATION_KEY]).toBeUndefined();
    // Original untouched (deep clone, not in-place delete).
    expect(vendored.$metadata?.[VENDORED_ANNOTATION_KEY]).toBeDefined();
  });

  it('tokensMatch is true for identical content and detects a value drift', async () => {
    const vendored = await readJson(VENDORED_PATH);
    const ssotLike = normalizeVendored(vendored); // identical content, sans annotation
    expect(tokensMatch(ssotLike, vendored)).toBe(true);

    const drifted = structuredClone(vendored);
    drifted.color.brand.deep['100'].$value = '#000000';
    expect(tokensMatch(ssotLike, drifted)).toBe(false);
  });

  it('tokensMatch ignores incidental key reordering', async () => {
    const vendored = await readJson(VENDORED_PATH);
    const ssotLike = normalizeVendored(vendored);
    const reordered = Object.fromEntries(Object.entries(ssotLike).reverse());
    expect(tokensMatch(reordered, vendored)).toBe(true);
  });

  it('vendored matches the design-system SSOT (skipped on CI without the sibling dir)', async () => {
    if (!(await exists(SSOT_PATH))) {
      // CI runner has no 06_Aurora_Design_system sibling — the pre-commit gate
      // covers this case on dev machines. Nothing to assert here.
      return;
    }
    const ssot = await readJson(SSOT_PATH);
    const vendored = await readJson(VENDORED_PATH);
    expect(tokensMatch(ssot, vendored)).toBe(true);
  });
});
