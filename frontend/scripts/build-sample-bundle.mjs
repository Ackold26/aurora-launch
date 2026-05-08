// Aurora Launch — generate synthetic FMCG sample bundle для onboarding wow.
// Block 2 audit decision D8: bundled с installer (1-2 MB, deterministic, license-free open).
//
// Invokes Python `aurora_launch.engines.corpus_generator.generator.generate_synthetic_project`
// и копирует output в frontend/static/sample.aurora; Tauri resource embed via tauri.conf.json
// `resources` field (set when bundling).

import { execSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, rmSync } from 'node:fs';
import path from 'node:path';
import url from 'node:url';

const HERE = path.dirname(url.fileURLToPath(import.meta.url));
const FRONTEND_ROOT = path.resolve(HERE, '..');
const PROJECT_ROOT = path.resolve(FRONTEND_ROOT, '..');
const STATIC_DIR = path.resolve(FRONTEND_ROOT, 'static');
const ASSETS_DIR = path.resolve(FRONTEND_ROOT, 'assets');
const SAMPLE_DEST = path.resolve(STATIC_DIR, 'sample.aurora');
const TMP_DIR = path.resolve(FRONTEND_ROOT, '.cache', 'sample-build');

mkdirSync(STATIC_DIR, { recursive: true });
mkdirSync(ASSETS_DIR, { recursive: true });
mkdirSync(TMP_DIR, { recursive: true });

try {
  execSync(
    `python -m aurora_launch.tools.corpus_cli generate FMCG_food.snacks_savoury baseline --seed 4242 --output "${path.join(TMP_DIR, 'sample.aurora.json')}"`,
    {
      cwd: PROJECT_ROOT,
      stdio: 'inherit',
      env: {
        ...process.env,
        PYTHONPATH: path.resolve(PROJECT_ROOT, 'src')
      }
    }
  );
  const generated = path.join(TMP_DIR, 'sample.aurora.json');
  if (existsSync(generated)) {
    copyFileSync(generated, SAMPLE_DEST);
    console.log(`[sample] copied to ${path.relative(FRONTEND_ROOT, SAMPLE_DEST)}`);
  } else {
    console.warn('[sample] expected file not produced; skipping copy.');
  }
} catch (e) {
  console.warn(`[sample] Python toolchain unavailable (${e.message}); sample bundle build skipped.`);
  console.warn('[sample] CI с Python (release pipeline) will produce the real file.');
}

try {
  rmSync(TMP_DIR, { recursive: true, force: true });
} catch {
  // no-op
}
