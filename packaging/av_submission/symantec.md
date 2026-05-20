# Symantec / Norton — AV Whitelist Submission Guide

Aurora Launch v0.1.4 · Sprint 3 D8 · Operational reference

---

## 1. Vendor ownership context

**Broadcom acquired Symantec Enterprise Security** (Symantec Endpoint Protection, SEP
Cloud, Symantec DLP) in November 2019. The enterprise product line now operates as
**Broadcom Symantec Enterprise**.

**Norton consumer line** (Norton 360, Norton AntiVirus Plus, Norton Security) was
divested to **Gen Digital** (formerly NortonLifeLock) and operates independently.
Gen Digital also owns Avast and AVG — but Norton submissions do NOT cross into
Avast/AVG queues; each requires a separate submission (see `avast.md`).

**Practical impact:** An installer hash whitelisted by Broadcom Symantec Enterprise
does NOT automatically propagate to Norton consumer definitions, and vice versa.
Both submissions are required for full coverage.

---

## 2. Submission portals

| Product line | Portal URL |
|---|---|
| **Symantec Enterprise (Broadcom SEP / SEP Cloud)** | https://submit.symantec.com/false_positive/ |
| **Norton consumer (Gen Digital)** | https://submit.norton.com/ |
| Broadcom support fallback | https://support.broadcom.com (file a case under "Security Software") |

Submit to **both portals** in the same session. They are independent queues.

---

## 3. Account requirements

**Symantec Enterprise (Broadcom):**
- No pre-existing Symantec/SEP customer account required for false-positive submission.
- Free submission allowed for any software publisher.
- Optional: create a Broadcom Support Portal account at https://support.broadcom.com
  for case tracking and status updates. Recommended — enables ticket lookup without
  waiting for email replies.

**Norton consumer (Gen Digital):**
- No paid Norton subscription required for submission.
- Free submission allowed. No account registration required to submit.
- Optional: Gen Digital partner program account for higher-priority queue — not
  applicable at current scale.

---

## 4. Required artifacts per submission

Prepare the following before opening either portal form:

| Artifact | Notes |
|---|---|
| **Installer binary** | `aurora-launch-setup-v0.1.4.exe` (NSIS). Upload both .exe and .msi if MSI variant built. |
| **SHA-256 hash** | Compute via `certutil -hashfile aurora-launch-setup-v0.1.4.exe SHA256` (Windows). Record in SUBMISSION_LOG.md. |
| **Signing certificate info** | Ed25519 fingerprint `[to be filled at release time]` — state "local-dev Ed25519 provenance, EV (Comodo/Sectigo) pending within 6 weeks" |
| **Detection name** | If a prior scan returned a specific detection string (e.g. "Heur.AdvML.B", "Trojan.Gen.2"), include it verbatim — accelerates routing to correct analysis team. |
| **Business justification text** | Paste EN section from `BUSINESS_JUSTIFICATION.md` verbatim into the "Explanation" / "Additional details" field. |
| **Product URL** | https://auroraai.pro/launch |
| **Submitter contact** | anton@auroraai.pro + security@auroraai.pro |

> Note on x509: Symantec portal may request "Code signing certificate" details.
> Until EV is provisioned, answer: "Self-signed Ed25519 (local-dev), EV Comodo/Sectigo
> certificate in provisioning (ETA 6 weeks)." This is an acceptable answer —
> Symantec accepts pre-EV submissions.

---

## 5. Form fields — typical Symantec false-positive form

Fill as follows (field names may differ slightly between enterprise and consumer portals):

| Form field | Value |
|---|---|
| **File name** | `aurora-launch-setup-v0.1.4.exe` |
| **File SHA-256** | `<HASH>` (compute before submission) |
| **File type** | PE32 executable / Windows Installer (NSIS) |
| **Detection name** | `<detection string from SEP alert, if available>` — leave blank if unknown |
| **Submission reason** | False positive — legitimate software |
| **Company name** | Aurora AI |
| **Submitter name** | Anton Kovalenko |
| **Role / title** | CEO |
| **Email** | anton@auroraai.pro |
| **Product name** | Aurora Launch |
| **Product URL** | https://auroraai.pro/launch |
| **Application description / Explanation** | Paste EN section from BUSINESS_JUSTIFICATION.md |
| **Code signing** | Ed25519 self-signed (local-dev); EV certificate (Comodo/Sectigo) in provisioning, ETA 6 weeks |
| **Distribution channel** | HTTPS authenticated download from auroraai.pro — no third-party stores |

---

## 6. Email submission alternative

For enterprise Symantec (Broadcom), if the web portal is unavailable or the upload
fails due to file size limits:

**Email:** symantecsupport@broadcom.com
**Subject line format:** `False Positive Submission — Aurora Launch v0.1.4 [PE32 installer]`

For Norton consumer (Gen Digital), if the portal is unavailable:
**Contact form:** https://norton.com/contact-us
Select: "Report a false positive"

---

## 7. Expected review timeline

| Stage | Symantec Enterprise (Broadcom) | Norton consumer (Gen Digital) |
|---|---|---|
| Automated triage | 1–3 business days | 1–2 business days |
| Manual security review | 5–14 business days | 5–10 business days |
| Whitelist decision | **7–21 business days total** | **5–14 business days total** |

Norton consumer typically resolves faster due to a larger consumer-facing team.
Symantec Enterprise reviews are more thorough given the corporate endpoint protection
context — expect the longer end of the range for a first-time submission from a
new publisher.

**Neither portal publishes a formal SLA for false-positive submissions.** The ranges
above are based on published community reports and AV researcher forums as of 2024–2025.
When the portal provides a confirmation number, it may show an "estimated response"
date — use that over the ranges above if available.

---

## 8. Re-submission protocol for new releases

Symantec requires a new submission for every new installer hash. Their whitelisting
is **hash-bound**, not publisher-bound (until EV certificate is in place).

Workflow for each minor release (v0.1.5, v0.1.6, …):

1. Build production installer → compute new SHA-256.
2. Open submit.symantec.com + submit.norton.com.
3. In the "Additional details" field add: `"Update to v0.X.Y — hash change only,
   methodology and behavior unchanged. Prior submission [CASE_ID_FROM_PORTAL] approved
   for v0.X.Z."` Reference the previous ticket ID.
4. Log new case IDs in `SUBMISSION_LOG.md`.

**After EV certificate provisioning:** EV-signed binaries from a recognized CA
(Comodo/Sectigo) typically receive automatic reputation bypass in Symantec SEP and
Norton. Manual re-submission per release becomes unnecessary. Confirm this with the
Broadcom support portal after EV certificate is provisioned.

---

## 9. Known troubleshooting

**"Auto-detected as suspicious" or upload rejected:**
- Compress installer into a password-protected .zip (password: `infected` — this is
  the standard malware researcher convention, Symantec portals accept it).
- Include the password in the submission notes field.

**PyInstaller-bundled binary challenged:**
- Symantec may ask for justification of the PyInstaller sidecar bundling.
- Prepared answer: "Aurora Launch ships a Python sidecar (`aurora-sidecar.exe`) for
  its econometric/Bayesian modeling pipeline (NumPy, PyMC). PyInstaller is used to
  produce a self-contained executable that isolates scientific Python dependencies
  from the main Rust binary. The sidecar performs local-only computation; it opens
  no network connections and does not modify the file system outside the application's
  own project directories."
- Attach or reference the EN section of BUSINESS_JUSTIFICATION.md as supporting
  documentation.

**No reply after 10 business days:**
- Use the follow-up email template in section 10 below.
- Reference the case ID from the submission confirmation email.
- Broadcom enterprise: reply to the original confirmation email — it preserves the
  thread in their ticketing system.
- Norton consumer: reply via the same confirmation email thread.

**Enterprise vs consumer separation:**
- Symantec Enterprise (Broadcom) and Norton consumer (Gen Digital) are fully separate
  review teams with separate databases. Whitelisting in one does NOT propagate to the
  other.
- Russia is a significant Norton consumer market. Prioritize the Norton submission
  equally with the enterprise submission.

**Detection survives after whitelist confirmation:**
- Definition update propagation typically takes 24–72 hours after whitelist decision.
- If detection persists >72 hours after confirmation email, reply to the case thread
  with: "Detection persists post-confirmation — requesting forced definition update
  for SHA-256 <HASH>."

---

## 10. Follow-up email template

Send if no response received within **7 business days** of submission confirmation.

```
To: symantecsupport@broadcom.com
[For Norton: use norton.com/contact-us → "False positive follow-up"]

Subject: Aurora Launch v0.1.4 — False positive whitelist follow-up
         [Case #[CASE_ID_FROM_PORTAL]]

Dear Symantec Security Response Team,

I am following up on case #[CASE_ID_FROM_PORTAL], submitted on [DATE] for
Aurora Launch installer v0.1.4.

Submission summary:
  - Filename:   aurora-launch-setup-v0.1.4.exe
  - SHA-256:    <HASH>
  - Signature:  Ed25519 local-dev provenance; EV certificate (Comodo/Sectigo)
                in provisioning, ETA [DATE+6 WEEKS]
  - Submitted:  [DATE]

Aurora Launch is a legitimate B2B sales forecasting desktop application
developed by Aurora AI (Russia). It is distributed exclusively via authenticated
HTTPS download from auroraai.pro. Full product description and technical
justification were included in the original submission (reference case above).

Please confirm:
  1. Current review status of the submission
  2. Whether any additional artifacts (source build logs, signing certificates,
     behavioral reports) are required to complete the review
  3. Estimated whitelist decision date

Technical contact: anton@auroraai.pro
Security inquiries: security@auroraai.pro
Product URL: https://auroraai.pro/launch

Best regards,
Anton Kovalenko
CEO, Aurora AI
```

---

## 11. Operational notes

- **Log all case IDs** in `packaging/av_submission/SUBMISSION_LOG.md` immediately
  upon receiving submission confirmation. Required for re-submission references.
- **Parallel submission recommended:** Submit to Symantec Enterprise + Norton in the
  same session on the same day. Independent queues, parallel review clears both faster.
- **EV certificate supersedes all of the above:** Once Comodo/Sectigo EV is
  provisioned, EV-signed installers are auto-whitelisted by Symantec SEP and Norton
  without manual submission. File a final "EV transition" note to open cases when
  that milestone is reached.
- **Broadcom ownership reminder:** When searching for portal support docs, use
  "Broadcom Symantec" or "Broadcom Security" — old Symantec.com URLs redirect to
  Broadcom, but some legacy docs still surface in search under the Symantec brand.
