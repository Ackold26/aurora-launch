// /api/updater/<target>/<arch>/<current_version>
//
// tauri-plugin-updater manifest endpoint. Returns latest version + signed
// installer URL per platform. Cache-Control: 5 min (Vercel CDN edge cache).
//
// Block 3 BLOCKER-3 fix arrives here: real Ed25519 signature embedded в
// `signature` field. Aurora Launch verifies против AURORA_UPDATER_PUBKEY
// constant baked into release builds (build.rs gate).
//
// Per https://v2.tauri.app/plugin/updater/ format spec.

import { errorResponse, jsonResponse } from '../../../../lib/schema';

export const config = { runtime: 'edge' };

interface UpdateRecord {
  version: string;
  notes: string;
  pub_date: string;
  platforms: {
    [target_arch: string]: {
      signature: string;
      url: string;
    };
  };
}

// In-memory snapshot — for single-tenant Aurora Launch this can be a static
// const refreshed by the release pipeline (which redeploys the function).
// Multi-tenant or rapid-cadence ships would store в Vercel KV.
const LATEST: UpdateRecord = {
  version: process.env.AURORA_LATEST_VERSION ?? '0.1.0',
  notes: process.env.AURORA_LATEST_NOTES ?? 'Initial pilot release',
  pub_date: process.env.AURORA_LATEST_PUB_DATE ?? new Date().toISOString(),
  platforms: parsePlatforms(process.env.AURORA_LATEST_PLATFORMS_JSON ?? '{}')
};

function parsePlatforms(json: string): UpdateRecord['platforms'] {
  try {
    return JSON.parse(json) as UpdateRecord['platforms'];
  } catch {
    return {};
  }
}

export default function handler(
  _request: Request,
  context: { params: { target?: string; arch?: string; current_version?: string } }
): Response {
  const { target, arch, current_version } = context.params;
  if (!target || !arch || !current_version) {
    return errorResponse('invalid_input', 'target/arch/current_version path params required', 400);
  }

  // Tauri convention: updater path is <target>-<arch>, e.g., "windows-x86_64".
  const platformKey = `${target}-${arch}`;
  const platformEntry = LATEST.platforms[platformKey];

  if (!platformEntry) {
    return errorResponse(
      'platform_not_supported',
      `no signed update artifact for ${platformKey}`,
      404
    );
  }

  // If client already on latest version, return 204 No Content per Tauri spec
  if (compareSemver(current_version, LATEST.version) >= 0) {
    return new Response(null, { status: 204 });
  }

  return jsonResponse(
    {
      version: LATEST.version,
      notes: LATEST.notes,
      pub_date: LATEST.pub_date,
      url: platformEntry.url,
      signature: platformEntry.signature
    },
    200,
    { 'cache-control': 'public, max-age=300' }
  );
}

function compareSemver(a: string, b: string): number {
  const partsA = a.split('.').map((s) => parseInt(s, 10) || 0);
  const partsB = b.split('.').map((s) => parseInt(s, 10) || 0);
  for (let i = 0; i < Math.max(partsA.length, partsB.length); i++) {
    const ai = partsA[i] ?? 0;
    const bi = partsB[i] ?? 0;
    if (ai !== bi) return ai - bi;
  }
  return 0;
}
