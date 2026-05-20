# McAfee / Trellix — Whitelist Submission Guide

Aurora Launch v0.1.4 | Sprint 3 D8 | Submitter: Anton Kovalenko (anton@auroraai.pro)

---

## 1. Vendor Structure Context

McAfee split into two independent entities in 2022 following the STG/Symphony Technology
Group acquisition of McAfee Enterprise:

| Entity | Scope | Submission system |
|---|---|---|
| **McAfee LLC** | Consumer line: McAfee LiveSafe, McAfee Total Protection, McAfee+ | McAfee consumer portal (free account) |
| **Trellix** | Enterprise line: formerly McAfee Endpoint Security / MVISION | Trellix enterprise portal (may require customer status) |

Both share the **GTI (Global Threat Intelligence)** reputation backend. A whitelist decision
in GTI propagates to both consumer and enterprise endpoints on the standard 4-hour update
cycle. Submit to both portals independently for full coverage.

---

## 2. Submission Portals

### McAfee Consumer (LiveSafe / Total Protection)

- **False Positive support article:** https://www.mcafee.com/support/?articleId=TS101463
- **Sample submission portal:** https://www.mcafee.com/enterprise/en-us/threat-center/threat-resources/submit-sample.html
- **Account requirement:** Free McAfee account required. Register at account.mcafee.com.
- **Alternative email:** virus_research@mcafee.com — route to the same research team;
  useful when portal upload fails or file size exceeds portal limit.

### Trellix (Enterprise / Endpoint Security)

- **Trellix sample submission (TIE):** https://www.trellix.com/services/threat-services/submit-sample/
- **Trellix support portal:** https://support.trellix.com
- **Account requirement:** Trellix enterprise portal may require an active Trellix customer
  account. If access is denied: contact support.trellix.com and request researcher access,
  or use the email path (see Section 6).
- **GTI reputation lookup:** integrated into TIE submission flow — no separate step needed.

---

## 3. Required Artifacts

Prepare before opening either portal:

| Artifact | Notes |
|---|---|
| `aurora-launch-setup-v0.1.4.exe` | NSIS installer binary (production build from CI) |
| SHA-256 hash | `<HASH>` — fill from `certutil -hashfile aurora-launch-setup-v0.1.4.exe SHA256` |
| MD5 hash | `<HASH_MD5>` — McAfee may request all three hash formats |
| SHA-1 hash | `<HASH_SHA1>` |
| Publisher legal entity | Aurora AI (Russia) |
| Product URL | https://auroraai.pro/launch |
| Installer download URL | https://auroraai.pro/launch/download |
| Detection name (if shown) | e.g., `Generic.Trojan.GenericKD` / `Artemis!<hash>` — copy from McAfee scan result |
| Business justification text | EN section from `BUSINESS_JUSTIFICATION.md` (verbatim paste) |
| Submitter contact | anton@auroraai.pro + security@auroraai.pro |

---

## 4. Form Fields — McAfee Sample Submission

When filling the submission form at the McAfee sample submission portal:

| Field | Value to enter |
|---|---|
| **Submission type** | "Application — False Positive" |
| **File name** | `aurora-launch-setup-v0.1.4.exe` |
| **SHA-256** | `<HASH>` |
| **MD5 / SHA-1** | `<HASH_MD5>` / `<HASH_SHA1>` |
| **Vendor / Publisher name** | Aurora AI |
| **Product name** | Aurora Launch |
| **Product description** | Aurora Launch is a B2B desktop application for sales forecasting of new consumer-brand launches using econometric / Bayesian (PyMC) modeling. Publisher: Aurora AI, Russia. Distribution: authenticated HTTPS download from auroraai.pro. No telemetry, no cloud data upload, offline-capable. |
| **Detailed justification** | Paste full EN section from `BUSINESS_JUSTIFICATION.md` |
| **Submitter name** | Anton Kovalenko |
| **Submitter email** | anton@auroraai.pro |
| **Company / organization** | Aurora AI |

**Product description note:** keep the summary under ~300 characters for fields with character
limits; use the detailed justification field for the full BUSINESS_JUSTIFICATION.md text.

---

## 5. Known Detection Triggers — Include in Justification

McAfee heuristics commonly flag Aurora Launch due to:

1. **PyInstaller pyz archive** — `aurora-sidecar.exe` bundles a Python interpreter via
   PyInstaller. The `.pyz` archive format triggers `Generic.Trojan.GenericKD` or
   `Artemis!` prefix detections. Include explicit statement: "Binary uses PyInstaller
   for legitimate Python sidecar packaging (econometric modeling pipeline)."
2. **Embedded ML/scientific libraries** — numpy, pymc, pytensor bundled inside sidecar.
   McAfee ML-malware heuristics occasionally flag large scientific C-extension bundles.
3. **Ed25519 cryptographic operations** — `ed25519-dalek` (Rust) + `cryptography` (Python).
   Used exclusively for signing Aurora's own output bundles; no encryption of third-party data.
4. **Local-dev Ed25519 signature (pre-EV)** — installer is not yet EV-signed. McAfee GTI
   gives lower initial trust score to non-EV-signed binaries. EV certificate from
   Comodo/Sectigo expected within 6 weeks (see Section 9).

---

## 6. Email Submission (Alternative / Follow-up)

Use email when: portal upload fails, file size limit exceeded, or Trellix portal requires
enterprise account you do not have.

- **McAfee research team:** virus_research@mcafee.com
- **Trellix support:** support@trellix.com (reference "false positive whitelist request"
  in subject)

Per McAfee published policy, files submitted via support email are routed to the same
research team as portal submissions. Response SLA is typically the same as portal track.

---

## 7. Expected Review Timeline

| Channel | Typical SLA |
|---|---|
| McAfee consumer portal — auto-triage | 2–5 business days |
| McAfee consumer portal — manual review (PyInstaller/heuristic cases) | 5–10 business days |
| Trellix enterprise portal | 7–14 business days |
| Combined GTI whitelist propagation to endpoints | 14–30 days from submission |
| GTI signature update distribution cycle (after whitelist decision) | ~4 hours |

**Pilot timeline note:** Submit by Sprint 3 end (Day 8–9) for expected whitelist clearance
before Sprint 5 pilot launch. If Trellix enterprise review runs to the 14-day upper bound,
clearance aligns with Sprint 4 end — within pilot window.

---

## 8. Re-Submission Protocol

McAfee GTI maintains hash-based signatures. A new installer build produces a new hash and
requires a new submission. Reference the previous submission when re-submitting:

- Reference field: "Prior submission for v0.1.X — hash change only, methodology and
  codebase unchanged. Previous case ID: [CASE_ID_FROM_PORTAL]."
- Re-submission is accepted without extended review if previous whitelist decision was
  positive. Expected fast-track: 2–5 business days.
- Log each re-submission in `packaging/av_submission/SUBMISSION_LOG.md`.

---

## 9. EV Certificate — Post-EV Submission

After receiving the Comodo / Sectigo EV code-signing certificate (expected Sprint 5,
~6 weeks from Sprint 3 end):

1. Build EV-signed installer (`aurora-launch-setup-v0.2.x.exe`).
2. Re-submit to both McAfee consumer portal and Trellix TIE with note:
   "Re-submission with EV-signed binary. Previous case ID: [CASE_ID_FROM_PORTAL]."
3. **McAfee GTI / Trellix TIE treat EV-signed binaries differently** — EV-signed
   binaries from a reputable issuer (Comodo/Sectigo) typically receive automatic
   whitelist through GTI reputation system, reducing dependency on manual review.
4. After EV whitelist decision propagates, future minor releases (v0.2.Y, v0.3.X)
   may not require re-submission if the EV certificate chain is unchanged — confirm
   this with the reviewer in your ticket reply.

---

## 10. Troubleshooting

| Symptom | Interpretation / Action |
|---|---|
| "Sample previously analyzed — no current detection" | GTI has no active signature for this hash. No immediate action required. Submit proactively to establish whitelist record for future heuristic-based detections. |
| "Heuristic detection — Generic.Trojan.GenericKD" or "Artemis!xxxx" | Expected for PyInstaller-bundled binaries. Include explicit PyInstaller justification (Section 5, point 1). This is the most common McAfee false-positive pattern for legitimate Python desktop apps. |
| "Submission queue exceeded" | McAfee consumer free-tier rate-limits submissions. Use the email channel (virus_research@mcafee.com) as fallback — same review team, no rate limit on incoming email. |
| Trellix portal requires customer account | Contact support.trellix.com, explain you are a software publisher requesting researcher access for a false-positive whitelist submission. Alternatively use Trellix support email. |
| No response after 14 business days | Send status inquiry email (template in Section 11) with case ID and SHA-256. McAfee research team typically replies within 2–3 business days of inquiry. |

---

## 11. Status Inquiry Email Template

Send after 7 business days (McAfee consumer) or 14 business days (Trellix enterprise)
with no response. Replace bracketed placeholders with actual values.

```
Subject: Aurora Launch v0.1.4 — Sample Submission Status Inquiry [Ticket #[CASE_ID_FROM_PORTAL]]

Dear McAfee / Trellix Threat Research Team,

I am writing to inquire about the status of the Aurora Launch installer
v0.1.4 false-positive whitelist submission filed [DATE_OF_SUBMISSION].

Reference identifiers:
  - Ticket / Case ID: [CASE_ID_FROM_PORTAL]
  - File name: aurora-launch-setup-v0.1.4.exe
  - SHA-256: <HASH>
  - Submission category: False Positive — whitelist request

Product summary:
Aurora Launch is a B2B desktop application for sales forecasting
(Rust + TypeScript + PyInstaller Python sidecar). Publisher: Aurora AI,
Russia. Distributed exclusively via authenticated HTTPS installer from
auroraai.pro. No telemetry, no cloud data upload, offline-capable.

Full justification:
[Paste EN section from BUSINESS_JUSTIFICATION.md verbatim]

Timeline context:
Aurora Launch is preparing for its Sprint 5 pilot customer launch
(approximately 6 weeks from the original submission date). Confirmation
of whitelist status, or indication of additional artifacts required,
would be appreciated.

Best regards,
Anton Kovalenko
CEO, Aurora AI
anton@auroraai.pro | security@auroraai.pro
https://auroraai.pro/launch
```

---

## 12. Submission Log Entry

After submitting, record in `packaging/av_submission/SUBMISSION_LOG.md`:

```markdown
## YYYY-MM-DD — McAfee Consumer

- **Portal:** https://www.mcafee.com/enterprise/en-us/threat-center/threat-resources/submit-sample.html
- **Account:** <login email used>
- **Ticket ID:** [CASE_ID_FROM_PORTAL]
- **Installer hash submitted:** SHA-256: <HASH>
- **Justification text:** EN (BUSINESS_JUSTIFICATION.md verbatim)
- **Expected reply:** YYYY-MM-DD (+5–10 business days)
- **Notes:** <any upload errors, detection name shown, fields left empty>

## YYYY-MM-DD — Trellix Enterprise (TIE)

- **Portal:** https://www.trellix.com/services/threat-services/submit-sample/
- **Account:** <login email used or "email submission">
- **Ticket ID:** [CASE_ID_FROM_PORTAL]
- **Installer hash submitted:** SHA-256: <HASH>
- **Justification text:** EN (BUSINESS_JUSTIFICATION.md verbatim)
- **Expected reply:** YYYY-MM-DD (+7–14 business days)
- **Notes:** <customer account required? email fallback used?>
```
