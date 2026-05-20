# Microsoft Defender — Whitelist Submission Guide

> **HIGHEST PRIORITY VENDOR.** Microsoft Defender is the default real-time protection
> built into every Windows 10/11 machine (~1.4B installs globally). Without Defender
> whitelist, Sprint 5 pilot customers will see a blocked download at first attempt.
> **Sprint 5 critical path: submission must be in late-stage review by Sprint 5 pilot
> start. Do not defer.**

---

## 1. Vendor overview

| Tier | Product | Coverage |
|---|---|---|
| Default (all Windows) | Microsoft Defender Antivirus | Real-time protection, on-demand scans |
| Default (all Windows) | Microsoft Defender SmartScreen | Download reputation layer (browser + Windows) |
| Paid enterprise | Microsoft Defender for Business | SMB tier with centralized management |
| Paid E5 enterprise | Microsoft Defender for Endpoint (MDE) | Advanced threat analytics + indicator management |

All tiers share the **Microsoft Security Intelligence** (formerly MMPC) reputation
engine. A whitelist decision propagates to the global Defender install base via
4-hour intelligence update cycles once approved.

---

## 2. Portal URLs

| Purpose | URL |
|---|---|
| **Primary submission (malware / false positive)** | https://www.microsoft.com/en-us/wdsi/filesubmission |
| SmartScreen reputation request (same portal, distinct category) | https://www.microsoft.com/en-us/wdsi/filesubmission |
| WDSI portal home | https://www.microsoft.com/en-us/wdsi |
| Microsoft Security Intelligence threat info | https://www.microsoft.com/en-us/wdsi/threats |

> **Note:** Microsoft Defender has no public security@ email for direct submissions.
> All public submissions go through the WDSI portal above.
> Partner Network channel: **winpartner@microsoft.com** (Microsoft Partner Network
> members only — see Section 3).

---

## 3. Account requirements

- **Minimum:** Free Microsoft account (outlook.com / live.com / work M365 account).
  Sufficient for public submissions.
- **Preferred:** Microsoft tenant admin account — marks submission as business/
  organizational, surfaces in a distinct queue.
- **Accelerated channel:** Microsoft Partner Network (MPN) membership. The free
  "Partner" tier grants access to the **winpartner@microsoft.com** channel, which
  typically receives prioritized review over anonymous portal submissions.
  Apply at: https://partner.microsoft.com/en-us/membership

> **Recommendation:** Apply for MPN free tier before Sprint 5. Application is
> straightforward for registered legal entities. Speeds review by removing anonymous-
> submitter friction.

---

## 4. Required artifacts

Prepare the following before opening the WDSI submission form:

| Artifact | Details |
|---|---|
| Installer file | `aurora-launch-setup-v0.1.4.exe` (NSIS) or `.msi` — upload limit 100 MB per file |
| SHA-256 hash | Compute with `certutil -hashfile <file> SHA256` on Windows |
| Detection name | If Defender already flagged the file (e.g., `Trojan:Win32/Sabsik.FL.B!ml` or `Wacatac.B!ml`). Proactive submissions: leave blank or write "None — proactive submission" |
| Business justification text | Paste EN section from `BUSINESS_JUSTIFICATION.md` verbatim |
| Publisher info | Aurora AI (Russia), anton@auroraai.pro, https://auroraai.pro/launch |
| Source code reference | github.com/Ackold26/aurora-launch — note: private repo, NDA-gated. State this explicitly in justification; do not share credentials |

---

## 5. WDSI portal form fields

When filling the submission form at https://www.microsoft.com/en-us/wdsi/filesubmission:

| Field | Value to enter |
|---|---|
| Submission type | **"Software developer or vendor"** (preferred — distinct review queue) |
| File upload | Upload installer .exe or .msi |
| "What kind of file is this?" | "Application (.exe) — commercial software" |
| Detection name | If flagged: paste exact detection string. If proactive: "Proactive whitelist request — no current detection" |
| "Why do you think this file was detected incorrectly?" | Paste summary from BUSINESS_JUSTIFICATION.md (PyInstaller pattern, ML libs, Ed25519 crypto — standard false-positive triggers). See template in Section 9 |
| Microsoft account email | anton@auroraai.pro or the submitting account |
| Privacy notice + sample submission terms | Acknowledge both checkboxes |

Submit **two separate submissions** in the same session:
1. **Malware / false-positive submission** — for AV engine detection
2. **SmartScreen reputation submission** — distinct category in the same portal; select "SmartScreen" when the form offers the option

---

## 6. SmartScreen-specific considerations

SmartScreen is a **separate reputation layer** from Defender AV. Even if the binary
passes AV scan, SmartScreen will show "Not commonly downloaded" warning to users
downloading from the web on first releases. This disrupts pilot onboarding.

**Resolution options (in order of priority):**

1. **EV code-signing certificate (most effective):** EV-signed installers receive
   immediate SmartScreen pass — no reputation warm-up required. This is the primary
   reason to prioritize EV cert in Sprint 4 or earlier.
   - Provider: Comodo / Sectigo express-track
   - Timeline: ~7 business days with express option
   - Cost: ~$300–500/year
   - Once EV-signed, Aurora Launch installers skip SmartScreen warning automatically
     on every future release without per-release manual submission.

2. **WDSI SmartScreen submission:** Submit proactively via WDSI portal (separate
   submission type from AV false-positive). Microsoft may accelerate reputation for
   explicitly submitted new software publishers.

3. **Organic reputation build:** SmartScreen warning disappears after sufficient
   download volume (~100–1000 successful installs without AV block signals). Pilot
   cohort of 5–10 customers is insufficient on its own.

4. **Pilot customer workaround (fallback):** Instruct pilot customers to click
   "More info → Run anyway" when SmartScreen warning appears. Document in Sprint 5
   pilot onboarding guide.

---

## 7. Enterprise (MDE) local whitelist

Microsoft Defender for Endpoint customers with E5 license can whitelist Aurora
Launch **independently** from the global Microsoft decision, via MDE Indicator
Management. If any Sprint 5 pilot customer is an MDE/E5 tenant:

- Guide their IT admin to: **Microsoft 365 Defender portal → Settings →
  Endpoints → Indicators → Add indicator → File hash (SHA-256)**
- This is a local enterprise decision and does not require Microsoft global approval.
- Relevant if global whitelist is still in review at Sprint 5 start.

---

## 8. Expected review timeline

| Stage | Typical duration | Notes |
|---|---|---|
| Cloud protection (real-time at download) | Immediate | Hash + metadata lookup; new publisher = unknown = flagged |
| WDSI manual review | 7–14 business days | Faster for signed binaries and Partner Network submissions; slower if flagged as active malware |
| SmartScreen reputation update | Varies widely | Instant for EV-signed; 4+ weeks for local-dev signed without EV |
| Global intelligence propagation (once approved) | ~4 hours | Defender update cycle after whitelist decision added to MSSI |

> Timeline is advisory, not guaranteed. Microsoft does not provide SLA commitments
> for WDSI public submissions.

---

## 9. Submission email template (MPN channel)

Use this template when emailing **winpartner@microsoft.com** (Microsoft Partner
Network members). Reference the WDSI portal ticket in the subject line.

```
Subject: Aurora Launch v0.1.4 — Software Publisher Whitelist Request [WDSI Ref. #<TICKET_ID>]

Dear Microsoft Defender Threat Intelligence Team,

I am the publisher of Aurora Launch submitting the v0.1.4 installer through the
Windows Defender Security Intelligence portal on [DATE], reference ticket #<TICKET_ID>.

File identifiers:
  - Filename:  aurora-launch-setup-v0.1.4.exe
  - SHA-256:   <HASH — compute with: certutil -hashfile <file> SHA256>
  - File size: ~[SIZE] MB
  - Publisher: Aurora AI (Russia)
  - Signature: Ed25519 local-dev provenance (EV certificate provisioning
                in progress — Comodo/Sectigo, ETA ~6 weeks from this date)

This is a PROACTIVE submission for whitelist consideration ahead of Sprint 5
pilot customer launch (~6 weeks from current date). No malicious functionality
is present. Canonical justification is attached and pasted below.

[PASTE BUSINESS_JUSTIFICATION.md EN SECTION VERBATIM HERE]

Additional context:
  - Aurora Launch bundles a Python sidecar via PyInstaller (aurora-sidecar.exe)
    for econometric / PyMC modeling. This packaging pattern is industry-standard
    but is a known trigger for Defender ML heuristics (Sabsik/Wacatac family).
    Please review accordingly.
  - SmartScreen reputation request submitted in parallel via WDSI portal
    (separate submission, same date).
  - Source repository: github.com/Ackold26/aurora-launch (private, NDA-gated
    — available for Microsoft security team review under NDA upon request).

Please confirm:
  1. Current submission status and expected review completion date
  2. Whether additional artifacts (source code access, additional binary
     variants, test environment access) would accelerate review
  3. Whether MDE Indicator Management is available for pilot customers
     with E5 license as an interim whitelist path

Best regards,
Anton Kovalenko
CEO, Aurora AI
anton@auroraai.pro
security@auroraai.pro
https://auroraai.pro/launch
```

---

## 10. Known troubleshooting

### ML false-positive detections

**`Trojan:Win32/Sabsik.FL.B!ml`** and **`Trojan:Win32/Wacatac.B!ml`** are the most
common Defender ML detections for PyInstaller binaries. Both are false positives for
Aurora Launch. In the WDSI justification field, state explicitly:

> "Aurora Launch uses PyInstaller for bundling a Python sidecar
> (aurora-sidecar.exe). This packaging pattern is industry-standard (Electron,
> Nuitka, cx_Freeze use similar archive approaches) but triggers Defender ML
> heuristics. The binary contains no malicious code. PyInstaller pyz archive
> is a well-documented false-positive trigger — reference:
> github.com/pyinstaller/pyinstaller/issues (search 'Defender false positive')."

### SmartScreen "Not commonly downloaded" warning

This is separate from AV detection. Does not appear in WDSI malware scan results.
Resolution: EV certificate (Section 6). Fallback for Sprint 5 pilot: document
"More info → Run anyway" step in onboarding guide.

### Re-submission on each release

Microsoft Defender reputation is **hash-based**. Each new installer binary
(new version, new build) requires a new WDSI submission with updated SHA-256.
EV-signed binaries inherit publisher-level reputation — after EV cert is
provisioned, re-submission per release may not be required (verify with Microsoft
documentation at that time).

### Russian publisher flag

Microsoft Defender has no geographic publisher block. However, SmartScreen
reputation scoring may apply longer warm-up for new publishers from certain
geographies (this is undocumented behavior based on community reports). EV
certificate from a Western CA (Comodo/Sectigo) neutralizes this signal by
anchoring trust to the certificate issuer reputation.

---

## 11. Re-submission protocol

For each new minor release (v0.1.X → v0.1.X+1):

1. Compute new SHA-256 for updated installer
2. Submit new WDSI entry with updated hash and note: "Version update — SHA-256
   change only, methodology and code structure unchanged"
3. Log in `packaging/av_submission/SUBMISSION_LOG.md`: date, ticket ID, hash
4. After EV cert provisioned: confirm with Microsoft whether publisher-level
   reputation covers new hashes automatically

---

## 12. Sprint 5 backup plan

If global Defender whitelist is **not completed** by Sprint 5 pilot start:

1. **Primary mitigation:** Instruct pilot customers (IT admin / end user) to add
   Aurora Launch installation directory to Defender exceptions:
   > Windows Security → Virus & threat protection → Manage settings → Exclusions →
   > Add or remove exclusions → Add a folder → select Aurora Launch install directory
   Document this step with screenshots in Sprint 5 pilot onboarding guide.

2. **Secondary mitigation:** If any pilot customer is MDE/E5 tenant, guide their
   IT admin to add SHA-256 indicator via MDE portal (Section 7).

3. **Priority action to prevent this scenario:** Purchase EV certificate no later
   than Sprint 4 start (~$300–500/year, Comodo/Sectigo, ~7 business day express
   track). EV-signed installer receives automatic SmartScreen pass and significantly
   reduces Defender ML false-positive probability — substitutes for manual whitelist
   in most cases.
