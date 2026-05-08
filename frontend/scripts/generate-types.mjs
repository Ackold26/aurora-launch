// Aurora Launch — Pydantic schemas → TypeScript types.
//
// Wraps existing `tools/export_typescript.py` CLI; emits to
// `src/lib/types/aurora-schemas.d.ts` consumed by IPC client + components.
// Run via `npm run gen:types`, auto-invoked в build script (gen runs first).
//
// If the Python tool isn't available (CI without Python), emits a stub с
// minimal types so frontend still type-checks.

import { execSync } from 'node:child_process';
import { existsSync, writeFileSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import url from 'node:url';

const HERE = path.dirname(url.fileURLToPath(import.meta.url));
const FRONTEND_ROOT = path.resolve(HERE, '..');
const PROJECT_ROOT = path.resolve(FRONTEND_ROOT, '..');
const OUT_PATH = path.resolve(FRONTEND_ROOT, 'src/lib/types/aurora-schemas.d.ts');

mkdirSync(path.dirname(OUT_PATH), { recursive: true });

// Try to invoke Python tool; fall back to stub on failure.
let pythonOk = false;
try {
  execSync(
    `python -m aurora_launch.tools.export_typescript --output "${OUT_PATH}"`,
    {
      cwd: PROJECT_ROOT,
      stdio: 'inherit',
      env: { ...process.env, PYTHONPATH: path.resolve(PROJECT_ROOT, 'src') }
    }
  );
  pythonOk = true;
} catch (e) {
  console.warn(`[types] Python export_typescript failed; emitting stub. Reason: ${e.message}`);
}

if (!pythonOk) {
  // Minimal stub — keep frontend type-checking working.
  const stub = `// Aurora Launch — Pydantic schema TypeScript types (STUB).
// The Python tool 'aurora_launch.tools.export_typescript' was unavailable
// at build time; this stub keeps the frontend type-checker happy. Real
// types regenerate via 'npm run gen:types' when Python toolchain is present.

export type IntegrityMode = 'strict' | 'warn' | 'disabled';
export type CompressionMode = 'store' | 'deflate';

export interface BundleFileEntry {
  sha256: string;
  size_bytes: number;
  schema_version: string | null;
}

export interface BundleManifest {
  manifest_version: string;
  schema_version: string;
  aurora_app: string;
  aurora_app_version: string;
  min_app_version: string;
  created_at: string;
  last_modified: string;
  project_id: string;
  revision: number;
  files: Record<string, BundleFileEntry>;
  integrity_check: IntegrityMode;
  compression: CompressionMode;
  aurora_launch_schema_version?: string | null;
  aurora_launch_migration_history?: Array<Record<string, string>>;
}

export type Verdict = 'High' | 'Medium' | 'Low' | 'Insufficient';

export interface SimilarityDimensionScores {
  category_l1_match: number;
  category_l2_match: number;
  category_l3_match: number;
  pricing_tier_match: number;
  brand_size_match: number;
  distribution_match: number;
  media_maturity_match: number;
  lifecycle_match: number;
  weights_used: Record<string, number>;
}

export interface ProxyEntry {
  proxy_brand_name: string;
  proxy_brand_code: string;
  category_l1: string;
  category_l2: string;
  category_l3: string;
  pricing_tier: 'ECONOMY' | 'MAINSTREAM' | 'PREMIUM' | 'LUXURY';
  brand_size: 'LEADER' | 'CHALLENGER' | 'NICHE';
  distribution: 'NATIONAL' | 'REGIONAL' | 'NICHE';
  media_maturity: 'ALWAYS_ON' | 'PULSING' | 'PROMO_DRIVEN' | 'DORMANT';
  lifecycle: 'NEW' | 'GROWING' | 'MATURE' | 'DECLINING';
}

export interface ConformalInterval {
  week_index: number;
  point_forecast: number;
  lower_bound: number;
  upper_bound: number;
  coverage_target: number;
}

export interface ForecastTrajectory {
  weekly_values: number[];
  sample_index: number;
}

export type LicenseState =
  | 'active'
  | 'grace'
  | 'expired'
  | 'invalid'
  | 'no_license'
  | 'degraded';
`;
  writeFileSync(OUT_PATH, stub, 'utf-8');
  console.log(`[types] Wrote stub to ${path.relative(FRONTEND_ROOT, OUT_PATH)}`);
}
