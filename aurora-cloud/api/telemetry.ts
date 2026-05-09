// /api/telemetry — opt-in diagnostics receiver.
//
// POST /api/telemetry
// Authorization: Bearer <license_jwt>  (any tier — telemetry available к всем
//                                         с активной лицензией для improvement)
// Body: { events: [{event_type, timestamp, payload}, ...] }
//
// Storage: Vercel KV. Per-seat rate limit (1000 events/hour) prevents flood.
// Aggregation runs offline (separate analytics job, не Edge function).

import { requireLicense } from '../lib/license';
import {
  errorResponse,
  isValidTelemetryBatch,
  jsonResponse,
  type TelemetryEventBatch
} from '../lib/schema';

export const config = { runtime: 'edge' };

const MAX_EVENTS_PER_HOUR_PER_SEAT = 1000;

export default async function handler(request: Request): Promise<Response> {
  if (request.method !== 'POST') {
    return errorResponse('method_not_allowed', 'POST only', 405);
  }

  // Telemetry gated by ANY active license (not feature-specific) — opt-in
  // diagnostics goes к любой paying customer.
  const auth = await requireLicense(request, 'launch_proxy_single');
  if (auth instanceof Response) return auth;
  const { claims } = auth;

  let body: unknown;
  try {
    body = await request.json();
  } catch (e) {
    return errorResponse('invalid_json', String(e), 400);
  }

  if (!isValidTelemetryBatch(body)) {
    return errorResponse('invalid_input', 'invalid telemetry batch shape', 400);
  }
  const batch = body as TelemetryEventBatch;

  const seatId = claims.seat_id;

  // Rate limit per seat — Vercel KV INCRBY с TTL
  try {
    const { kv } = await import('@vercel/kv');
    const hourBucket = Math.floor(Date.now() / 3_600_000);
    const rateKey = `aurora:telemetry:rate:${seatId}:${hourBucket}`;
    const newCount = await kv.incrby(rateKey, batch.events.length);
    if (newCount === batch.events.length) {
      // First insert this bucket — set TTL
      await kv.expire(rateKey, 3700);
    }
    if (newCount > MAX_EVENTS_PER_HOUR_PER_SEAT) {
      return errorResponse(
        'rate_limited',
        `seat ${seatId} exceeded ${MAX_EVENTS_PER_HOUR_PER_SEAT} events/hour`,
        429
      );
    }

    // Append events to seat-scoped list (cap 50000 entries)
    const listKey = `aurora:telemetry:events:${seatId}`;
    const enriched = batch.events.map((e) => ({
      ...e,
      _seat_id: seatId,
      _received_at: new Date().toISOString(),
      _aurora_app_version: claims.tier // helpful for cohort analysis
    }));
    for (const ev of enriched) {
      await kv.lpush(listKey, ev);
    }
    await kv.ltrim(listKey, 0, 49_999);
  } catch (e) {
    // F1 audit S2 fix: scrub to e.message only (prevent JWT/header bytes
    // leaking into logs through default exception serialisation).
    const msg = e instanceof Error ? e.message : 'unknown';
    console.error('[telemetry] KV store failed:', msg);
    return errorResponse('storage_unavailable', 'telemetry store offline', 503);
  }

  return jsonResponse({ accepted: batch.events.length, seat_id: seatId });
}
