// Aurora Launch — tokens.json → CSS custom properties.
//
// Reads canonical tokens from `06_Aurora_Design_system/01_Tokens/tokens.json`
// (SSOT) и emits `src/lib/styles/tokens.css` consumed by app.css. Fails fast
// если SSOT path moved или schema changed.
//
// Run via `npm run gen:tokens`. Auto-runs в build script.

import { promises as fs } from 'node:fs';
import path from 'node:path';
import url from 'node:url';

const HERE = path.dirname(url.fileURLToPath(import.meta.url));
const FRONTEND_ROOT = path.resolve(HERE, '..');
const PROJECT_ROOT = path.resolve(FRONTEND_ROOT, '..');
const TOKENS_PATH = path.resolve(
  PROJECT_ROOT,
  '..',
  '06_Aurora_Design_system',
  '01_Tokens',
  'tokens.json'
);
// CI fallback: external SSOT sibling dir doesn't exist в runners. Vendored copy
// committed adjacent к этому script — sync на любое изменение upstream tokens.json.
// Dev workflow preferentially читает SSOT (внешний sibling); если missing —
// vendored fallback (с warning).
//
// #51: vendored — производный артефакт. После изменения SSOT запусти
// `npm run sync:tokens` (regenerate vendored). `npm run check:tokens`
// (pre-commit gate) падает, если vendored разошёлся с SSOT.
const VENDORED_PATH = path.resolve(HERE, 'tokens.vendored.json');
const OUT_PATH = path.resolve(FRONTEND_ROOT, 'src/lib/styles/tokens.css');

function flattenTokens(obj, prefix = '') {
  const out = [];
  for (const [key, value] of Object.entries(obj)) {
    if (key.startsWith('$')) continue;
    const k = prefix ? `${prefix}-${key}` : key;
    if (value && typeof value === 'object' && '$value' in value) {
      out.push([k, value.$value]);
    } else if (value && typeof value === 'object') {
      out.push(...flattenTokens(value, k));
    }
  }
  return out;
}

function resolveAlias(value, allTokens) {
  // {color.brand.deep.100} → look up
  if (typeof value !== 'string') return value;
  const m = value.match(/^\{(.+)\}$/);
  if (!m) return value;
  const path = m[1];
  // Find by transformation (paths are dotted в tokens.json, dashed в CSS)
  const dashed = path.replaceAll('.', '-');
  const found = allTokens.find(([k]) => k === dashed);
  return found ? `var(--${dashed})` : value;
}

function toCssVar(name) {
  return `--${name}`;
}

async function main() {
  let raw;
  let sourcePath = TOKENS_PATH;
  try {
    raw = await fs.readFile(TOKENS_PATH, 'utf-8');
  } catch (e) {
    if (e.code !== 'ENOENT') {
      console.error(`[tokens] FAILED to read SSOT at ${TOKENS_PATH}`);
      console.error(e);
      process.exit(2);
    }
    // External SSOT missing (typical CI runner without sibling design system dir).
    // Fall back к vendored copy.
    try {
      raw = await fs.readFile(VENDORED_PATH, 'utf-8');
      sourcePath = VENDORED_PATH;
      console.warn(`[tokens] external SSOT not found at ${TOKENS_PATH}`);
      console.warn(`[tokens] falling back to vendored copy: ${VENDORED_PATH}`);
    } catch (e2) {
      console.error(`[tokens] FAILED — neither SSOT nor vendored available.`);
      console.error(`[tokens]   SSOT path:     ${TOKENS_PATH}`);
      console.error(`[tokens]   Vendored path: ${VENDORED_PATH}`);
      console.error(e2);
      process.exit(2);
    }
  }
  const tokens = JSON.parse(raw);
  const flat = flattenTokens(tokens);

  const colorTokens = flat.filter(([k]) => k.startsWith('color-'));
  const typographyTokens = flat.filter(
    ([k]) => k.startsWith('typography-fontFamily') || k.startsWith('typography-fontSize-ui') || k.startsWith('typography-fontWeight') || k.startsWith('typography-lineHeight')
  );
  const spacingTokens = flat.filter(([k]) => k.startsWith('spacing-'));
  const sizingTokens = flat.filter(([k]) => k.startsWith('sizing-ui'));
  const borderTokens = flat.filter(([k]) => k.startsWith('border-'));

  const sections = [
    ['colors', colorTokens],
    ['typography', typographyTokens],
    ['spacing', spacingTokens],
    ['sizing', sizingTokens],
    ['borders', borderTokens]
  ];

  const lines = [
    '/* Aurora Launch — tokens.css',
    `   Generated from ${path.relative(PROJECT_ROOT, sourcePath)}`,
    `   Run \`npm run gen:tokens\` to regenerate. Do NOT hand-edit. */`,
    '',
    ':root {'
  ];

  for (const [sectionName, items] of sections) {
    if (items.length === 0) continue;
    lines.push(`  /* ${sectionName} */`);
    for (const [k, v] of items) {
      const resolved = resolveAlias(v, flat);
      lines.push(`  ${toCssVar(k)}: ${resolved};`);
    }
    lines.push('');
  }

  // Aurora Launch convenience aliases (Block 2 audit D2 — UX_PRINCIPLES synced)
  lines.push('  /* Aurora Launch convenience aliases (UX_PRINCIPLES.md §2.1) */');
  lines.push('  --bg-main: var(--color-ui-bg-main);');
  lines.push('  --bg-surface: var(--color-ui-bg-surface);');
  lines.push('  --border-subtle: var(--color-ui-bg-border);');
  lines.push('  --text-primary: var(--color-ui-text-primary);');
  lines.push('  --text-secondary: var(--color-ui-text-secondary);');
  lines.push('  --text-muted: var(--color-ui-text-muted);');
  lines.push('  --accent: var(--color-ui-accent-primary);');
  lines.push('  --accent-sigil: var(--color-ui-accent-secondary); /* sacred lime */');
  lines.push('  --color-success: var(--color-semantic-success);');
  lines.push('  --color-warning: var(--color-semantic-warning);');
  lines.push('  --color-danger: var(--color-semantic-danger);');
  lines.push('  --color-info: var(--color-semantic-info);');
  lines.push('  --font-sans: var(--typography-fontFamily-uiSans);');
  lines.push('  --font-serif: var(--typography-fontFamily-uiSerif);');
  lines.push('  --font-mono: var(--typography-fontFamily-uiMono);');
  lines.push('');
  lines.push('  /* Motion timings (Block 2D) */');
  lines.push('  --motion-fast: 150ms;');
  lines.push('  --motion-default: 200ms;');
  lines.push('  --motion-smooth: 320ms;');
  lines.push('  --easing-spring: cubic-bezier(0.34, 1.56, 0.64, 1);');
  lines.push('  --easing-smooth: cubic-bezier(0.4, 0, 0.2, 1);');
  lines.push('  --easing-emphasized: cubic-bezier(0.2, 0, 0, 1);');
  lines.push('}');
  lines.push('');

  // Light theme (Block 2 audit D9): CSS overrides; tokens.json остаётся dark SSOT
  lines.push('/* Light theme overrides (Block 2 D9) — tokens.json остаётся dark SSOT */');
  lines.push('[data-theme="light"] {');
  lines.push('  --bg-main: #FAFAFC;');
  lines.push('  --bg-surface: #FFFFFF;');
  lines.push('  --border-subtle: #E0E2E8;');
  lines.push('  --text-primary: #1A1D27;');
  lines.push('  --text-secondary: #4A4D57;');
  lines.push('  --text-muted: #7A7D87;');
  lines.push('}');
  lines.push('');

  // High contrast (a11y M7)
  lines.push('/* High contrast palette (a11y, ГОСТ Р 52872-2019) */');
  lines.push('[data-theme="high-contrast"] {');
  lines.push('  --bg-main: #000000;');
  lines.push('  --bg-surface: #0F0F0F;');
  lines.push('  --border-subtle: #FFFFFF;');
  lines.push('  --text-primary: #FFFFFF;');
  lines.push('  --text-secondary: #FFFF00;');
  lines.push('  --text-muted: #BBBBBB;');
  lines.push('  --accent: #00FFFF;');
  lines.push('}');
  lines.push('');

  // Reduced motion preference
  lines.push('@media (prefers-reduced-motion: reduce) {');
  lines.push('  :root {');
  lines.push('    --motion-fast: 0ms;');
  lines.push('    --motion-default: 0ms;');
  lines.push('    --motion-smooth: 0ms;');
  lines.push('  }');
  lines.push('}');
  lines.push('');

  await fs.mkdir(path.dirname(OUT_PATH), { recursive: true });
  await fs.writeFile(OUT_PATH, lines.join('\n'), 'utf-8');
  console.log(`[tokens] Generated ${path.relative(FRONTEND_ROOT, OUT_PATH)} (${lines.length} lines)`);
}

main().catch((e) => {
  console.error('[tokens] generation failed:', e);
  process.exit(1);
});
