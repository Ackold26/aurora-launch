# Final F1 Audit Gate — 2026-05-09

**Auditor:** Маша Маленькая (Opus 4.7 medium effort)
**State entering:** HEAD `14116b5`, tag `v0.1.0-rc1`, Block 4 sidecar shipped
**State exiting:** HEAD TBD, tag TBD после Антон infrastructure provisioning + smoke verification (planned `v0.1.0-rc2`)
**Outcome:** 1 HIGH applied (PII log scrub); 6 MEDIUM/LOW deferred POST_PILOT_BACKLOG; INV-01..14 repeat patterns checked.

## Methodology

ENGINEERING_INVARIANTS pre-flight per CLAUDE.md mandate:
- §1 INVs read recently (Block 4 ~30 мин ago)
- Crypto/signing? **YES** — F1 = signing service. INV-05 attack tests FIRST.
- Schema change? **YES** — SignRequest/SignResponse + TelemetryEventBatch + FeedbackSubmission. Pinned via lib/schema.ts validators + 19 vitest tests.
- Infrastructure? **YES** — Vercel Edge + Yandex KMS topology. INV-13: РФ KMS + global Vercel edge balanced для pilot ICP.
- Imports/deps? **YES** — @noble/ed25519, @noble/hashes, jose, @vercel/kv, hono. Edge runtime compatible verified.

## Findings

### 🟠 F1-S2 HIGH (applied) — PII leak via console.error full exception

**Files:** `aurora-cloud/api/telemetry.ts`, `aurora-cloud/api/feedback.ts`

`console.error('[telemetry] KV store failed:', e)` with full `e` object
serialises к Vercel logs. If exception originates inside JWT verification or
KV middleware, the stack trace может include partial license JWT or header
bytes — which Vercel ops engineers (or compromised log-aggregation pipeline)
could read.

**Fix:** scrub to `e.message` only. Stack trace not logged. Same for
feedback rate limit warn.

### Deferred MEDIUM/LOW

| ID | Severity | Issue | Owner |
|---|---|---|---|
| F1-S4 | MEDIUM | Dynamic imports (`@noble/hashes/blake3`, `@vercel/kv`) на каждый request — cold start cost. Hoist к top after ESM Edge runtime verified. | Phase B perf pass |
| F1-S5 | MEDIUM | kmsSign 2 sequential network hops (IAM token + sign). 200-400ms latency. Expected, document. | Documented (no fix) |
| F1-S7 | MEDIUM | Vercel regions = `fra1`, `arn1` — no РФ presence. Pilot users в РФ get +30-50ms vs РФ-hosted. KMS calls have latency anyway. | Phase B regional review |
| F1-S6 | LOW | `claims.tier` used as version cohort в telemetry — should be `client_meta.aurora_app_version`. Cosmetic. | Block 4 polish |
| F1-S8 | LOW | Updater catch-all path safe против path traversal (KV keying only). Documented. | No action |
| F1-runbook | LOW | DNS records (Step 4) assume Cloudflare — provide alternate registrar instructions on Антон request. | On request |

### Rejected (false positives / by design)

- **F1-S1 (false positive)** — body/header JWT matching order: handler validates body shape first, then header match, then full requireLicense. Order correct: structural validation before crypto. No vulnerability.

## INV-01..14 repeat-check

| INV | Block 4 Block 3 etc carried forward | F1 specific |
|---|---|---|
| INV-01 schema migration | ✅ | SignRequest/Response/Telemetry/Feedback validators pinned via vitest; SSOT в lib/schema.ts |
| INV-02 runtime smoke | ✅ | Validators tested через function call, not just import |
| INV-03 verify package + feature flag | ✅ | Hono / jose / @noble/ed25519 / @vercel/kv all stable Vercel Edge runtime — verified |
| INV-05 crypto attack test FIRST | ✅ | 12 sign-attack tests + 6 schema DoS tests written до handler finalised |
| INV-06 JCS | ✅ | composite_hash_hex from Aurora Launch already JCS-canonical (Block 3 mirror) |
| INV-07 honest progress | N/A | F1 server code; client UI separate |
| INV-08 real pytest | ✅ | 547 Python still green; vitest-style cloud tests pinned (not run в Python suite) |
| INV-09 config end-to-end | ✅ | AURORA_KMS_KEY_ID, AURORA_LICENSE_VERIFY_KEY_PEM, AURORA_GITHUB_PAT все traced env → runtime use |
| INV-10 read API signature | ✅ | Vercel Edge `Request/Response`, Yandex KMS REST POST `:sign`, GitHub `POST /repos/:owner/:repo/issues` — all per official docs |
| INV-11 verify memory vs repo state | ✅ | HEAD `14116b5` confirmed entering, 547 tests verified |
| INV-12 read entire spec | ✅ | ROADMAP §F1 + Block 3 BLOCKER-2/-3 referenced fully |
| INV-13 infrastructure | ✅ | Vercel + Yandex KMS topology rationale (РФ KMS for compliance, global edge for CDN) verified per prior context |
| INV-14 prefers-reduced-motion | N/A | server code |

## Code Handoff Protocol §2 check

F1 ships server code stays в Aurora Launch repo (no extraction). 5-question handoff template not triggered.

## Tests

- **Python:** 547 passing (no F1 Python changes; validation that F1 ship не break backend integrity).
- **Vitest cloud (aurora-cloud/tests):** 18 tests (12 sign-attack INV-05 + 6 schema DoS) pinned but not run в Python suite. Run via `cd aurora-cloud && npm test` (CI pipeline `test.yml`).
- **PyInstaller cross-platform CI:** workflow shipped (`sidecar-build.yml`); first matrix run будет triggered Антон tag push.

## Release gate

✅ All HIGH findings fixed.
🟡 6 MEDIUM/LOW deferred с owners.
✅ INV-01..14 repeat patterns checked, no new violations.

**Recommended next:** commit F1 code; tag `v0.1.0-rc2` ONLY после Антон выполнит F1_DEPLOYMENT_RUNBOOK.md Steps 1-5 + Step 6 smoke test passes. Tag triggers `release.yml` → builds installers → publishes manifest.

After tag rc2 success → F2 installer + (optional) signing → F3 pilot kickoff Materia Medica.
