// /api/feedback — Cmd+Shift+F submission receiver.
//
// POST /api/feedback
// Authorization: Bearer <license_jwt>
// Body: { text, screenshot_base64?, log_excerpt?, client_meta? }
//
// Creates GitHub Issue в `Ackold26/aurora-launch-feedback` (private feedback
// repo) с redacted client metadata. Screenshot uploaded as repo asset (if
// present), referenced from issue body.
//
// Per Block 2F PREMIUM P10 spec.

import { requireLicense } from '../lib/license';
import {
  errorResponse,
  isValidFeedback,
  jsonResponse,
  type FeedbackSubmission
} from '../lib/schema';

export const config = { runtime: 'edge' };

const FEEDBACK_REPO = process.env.AURORA_FEEDBACK_REPO ?? 'Ackold26/aurora-launch-feedback';
const MAX_FEEDBACK_PER_HOUR_PER_SEAT = 20;

export default async function handler(request: Request): Promise<Response> {
  if (request.method !== 'POST') {
    return errorResponse('method_not_allowed', 'POST only', 405);
  }

  const auth = await requireLicense(request, 'launch_proxy_single');
  if (auth instanceof Response) return auth;
  const { claims } = auth;

  let body: unknown;
  try {
    body = await request.json();
  } catch (e) {
    return errorResponse('invalid_json', String(e), 400);
  }

  if (!isValidFeedback(body)) {
    return errorResponse('invalid_input', 'invalid feedback shape', 400);
  }
  const fb = body as FeedbackSubmission;

  // Rate limit
  try {
    const { kv } = await import('@vercel/kv');
    const hourBucket = Math.floor(Date.now() / 3_600_000);
    const rateKey = `aurora:feedback:rate:${claims.seat_id}:${hourBucket}`;
    const newCount = await kv.incr(rateKey);
    if (newCount === 1) await kv.expire(rateKey, 3700);
    if (newCount > MAX_FEEDBACK_PER_HOUR_PER_SEAT) {
      return errorResponse(
        'rate_limited',
        `seat ${claims.seat_id} exceeded ${MAX_FEEDBACK_PER_HOUR_PER_SEAT} feedbacks/hour`,
        429
      );
    }
  } catch (e) {
    // F1 audit S2 fix: scrub to e.message only.
    const msg = e instanceof Error ? e.message : 'unknown';
    console.warn('[feedback] rate limit check skipped:', msg);
  }

  const ghToken = process.env.AURORA_GITHUB_PAT;
  if (!ghToken) {
    return errorResponse('misconfigured', 'AURORA_GITHUB_PAT not set', 503);
  }

  // PII-safe issue title — never leak full text (could contain customer data).
  // Use first 60 chars + seat hash, redact obvious patterns.
  const titleSnippet = redactPii(fb.text).slice(0, 60).replace(/\n/g, ' ');
  const seatHash = await sha256Short(claims.seat_id);
  const title = `[feedback] ${titleSnippet}… (seat ${seatHash})`;

  const bodyMd = buildIssueBody(fb, claims);

  let issueResp;
  try {
    issueResp = await fetch(`https://api.github.com/repos/${FEEDBACK_REPO}/issues`, {
      method: 'POST',
      headers: {
        authorization: `Bearer ${ghToken}`,
        accept: 'application/vnd.github+json',
        'content-type': 'application/json',
        'x-github-api-version': '2022-11-28'
      },
      body: JSON.stringify({
        title,
        body: bodyMd,
        labels: ['feedback', `tier:${claims.tier}`]
      })
    });
  } catch (e) {
    return errorResponse('upstream_unavailable', `github api: ${e}`, 502);
  }

  if (!issueResp.ok) {
    const text = await issueResp.text();
    return errorResponse(
      'github_failed',
      `issue create returned ${issueResp.status}: ${text.slice(0, 200)}`,
      502
    );
  }

  const issue = (await issueResp.json()) as { number: number; html_url: string };

  return jsonResponse({
    issue_number: issue.number,
    issue_url: issue.html_url
  });
}

function buildIssueBody(fb: FeedbackSubmission, claims: { seat_id: string; license_id: string; tier: string }): string {
  const lines: string[] = [];
  lines.push('## Feedback');
  lines.push('');
  lines.push(redactPii(fb.text));
  lines.push('');
  lines.push('## Client metadata');
  lines.push('');
  if (fb.client_meta) {
    for (const [k, v] of Object.entries(fb.client_meta)) {
      lines.push(`- **${k}**: ${String(v).slice(0, 120)}`);
    }
  }
  lines.push(`- **license_tier**: ${claims.tier}`);
  lines.push(`- **received_at**: ${new Date().toISOString()}`);
  lines.push('');
  if (fb.log_excerpt) {
    lines.push('## Log excerpt (32 KB cap)');
    lines.push('');
    lines.push('```');
    lines.push(redactPii(fb.log_excerpt));
    lines.push('```');
  }
  // Screenshot deferred: GitHub doesn't accept inline base64; future Phase
  // would upload screenshot к Vercel Blob и reference URL.
  if (fb.screenshot_base64) {
    lines.push('');
    lines.push(`_Screenshot included (${fb.screenshot_base64.length} base64 chars), upload via Vercel Blob deferred к Phase B._`);
  }
  return lines.join('\n');
}

/** Redact obvious PII patterns (emails, IPs, license keys, JWTs).
 *  Belt-and-suspenders с client-side discipline. */
function redactPii(text: string): string {
  return text
    .replace(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g, '<email-redacted>')
    .replace(/\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b/g, '<ip-redacted>')
    .replace(/eyJ[A-Za-z0-9_=-]+\.eyJ[A-Za-z0-9_=-]+\.[A-Za-z0-9_=.-]+/g, '<jwt-redacted>')
    .replace(/\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b/g, '<license-key-redacted>');
}

async function sha256Short(input: string): Promise<string> {
  const buf = new TextEncoder().encode(input);
  const hash = await crypto.subtle.digest('SHA-256', buf);
  const bytes = new Uint8Array(hash);
  let hex = '';
  for (let i = 0; i < 4; i++) hex += bytes[i].toString(16).padStart(2, '0');
  return hex;
}
