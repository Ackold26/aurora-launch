// Aurora Launch — verify tokens.vendored.json matches the design-system SSOT.
//
// #51 (shared-lib audit Sprint 0 follow-up). `tokens.vendored.json` — это
// CI-only зеркало `06_Aurora_Design_system/01_Tokens/tokens.json` (SSOT).
// Внешний SSOT-каталог отсутствует в CI runner'ах, поэтому фронтенд держит
// vendored-копию для fallback (см. generate-tokens-css.mjs). Без gate они
// могут разойтись молча: правят SSOT, забывают пересинхронить vendored → CI
// собирает устаревшие токены, а локальный dev-билд — свежие.
//
// Этот gate запускается в pre-commit на dev-машине, где SSOT-sibling
// существует. В CI runner (SSOT отсутствует) — graceful skip: vendored
// используется как есть.
//
// Сравнение идёт по РАСПАРСЕННОМУ контенту (формат-агностично — иммунно к
// prettier-реформату любого из файлов), с нормализацией vendored-only
// аннотации в `$metadata`.
//
// Run: `npm run check:tokens`. Fix drift: `npm run sync:tokens`.

import { promises as fs } from 'node:fs';
import path from 'node:path';
import url from 'node:url';

const HERE = path.dirname(url.fileURLToPath(import.meta.url));
const FRONTEND_ROOT = path.resolve(HERE, '..');
const PROJECT_ROOT = path.resolve(FRONTEND_ROOT, '..');

// External design-system SSOT (sibling of the Launch project root).
export const SSOT_PATH = path.resolve(
  PROJECT_ROOT,
  '..',
  '06_Aurora_Design_system',
  '01_Tokens',
  'tokens.json'
);
export const VENDORED_PATH = path.resolve(HERE, 'tokens.vendored.json');

// Annotation key injected into the vendored copy's `$metadata` to self-document
// its mirror status. Stripped before the equality compare.
export const VENDORED_ANNOTATION_KEY = 'vendored';

// Deep-clone the vendored token tree with the vendored-only annotation removed,
// so it can be compared 1:1 against the SSOT content.
/**
 * @param {any} vendoredObj
 * @returns {any}
 */
export function normalizeVendored(vendoredObj) {
  const clone = structuredClone(vendoredObj);
  if (clone && typeof clone === 'object' && clone.$metadata) {
    delete clone.$metadata[VENDORED_ANNOTATION_KEY];
  }
  return clone;
}

// Order-independent canonical JSON (recursively sorted keys) so incidental key
// reordering doesn't trip the gate — only token values/structure matter.
/**
 * @param {any} value
 * @returns {any}
 */
function sortKeys(value) {
  if (Array.isArray(value)) return value.map(sortKeys);
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((k) => [k, sortKeys(value[k])])
    );
  }
  return value;
}

/**
 * @param {any} obj
 * @returns {string}
 */
export function canonical(obj) {
  return JSON.stringify(sortKeys(obj));
}

/**
 * @param {any} ssotObj
 * @param {any} vendoredObj
 * @returns {boolean}
 */
export function tokensMatch(ssotObj, vendoredObj) {
  return canonical(ssotObj) === canonical(normalizeVendored(vendoredObj));
}

async function main() {
  let ssotRaw;
  try {
    ssotRaw = await fs.readFile(SSOT_PATH, 'utf-8');
  } catch (e) {
    const err = /** @type {any} */ (e);
    if (err.code === 'ENOENT') {
      console.log(
        `[check:tokens] SSOT not present at ${SSOT_PATH} — skipping vendored equality check ` +
          `(CI runner without 06_Aurora_Design_system sibling).`
      );
      return;
    }
    throw e;
  }

  const vendoredRaw = await fs.readFile(VENDORED_PATH, 'utf-8');
  const ssot = JSON.parse(ssotRaw);
  const vendored = JSON.parse(vendoredRaw);

  if (tokensMatch(ssot, vendored)) {
    console.log('[check:tokens] OK — tokens.vendored.json matches design-system SSOT.');
    return;
  }

  console.error('[check:tokens] DRIFT — tokens.vendored.json is out of sync with the SSOT.');
  console.error(`[check:tokens]   SSOT:     ${SSOT_PATH}`);
  console.error(`[check:tokens]   Vendored: ${VENDORED_PATH}`);
  console.error(
    '[check:tokens] Fix: `npm run sync:tokens`, then commit the updated vendored copy.'
  );
  process.exit(1);
}

// Run only when invoked directly (CLI), not when imported by tests.
if (process.argv[1] && import.meta.url === url.pathToFileURL(process.argv[1]).href) {
  main().catch((e) => {
    console.error('[check:tokens] failed:', e);
    process.exit(2);
  });
}
