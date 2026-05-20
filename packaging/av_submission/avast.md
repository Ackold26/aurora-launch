# Avast / AVG — False Positive Whitelist Submission

**Vendor parent:** Gen Digital (Avast + NortonLifeLock merger, 2022)
**Brands covered here:** Avast Free Security / Avast Premium Security, AVG AntiVirus Free / AVG Internet Security
**Norton / LifeLock:** separate submission path — see `symantec.md`

> Speed note: Avast / AVG are among the fastest major AV vendors for whitelist decisions. Expected
> full turnaround 2-5 business days vs. 14-30 days for Symantec / Kaspersky — positive Sprint 3 finding.

---

## 1. Portal URLs

| Brand | Submission URL |
|---|---|
| Avast false positive | https://www.avast.com/false-positive-file-form.php |
| AVG false positive | https://www.avg.com/en/signal/report-a-false-positive |
| Gen Digital threat research (escalation) | https://support.gendigital.com |
| Avast threat lab email (detailed dialogue) | virus@avast.com |

Submit to **both** Avast and AVG portals — they share the Gen Digital reputation engine post-merger,
but customer-facing whitelist propagation is tracked per brand.

---

## 2. Account requirements

Both Avast and AVG false-positive forms accept **anonymous submissions** — no pre-existing account
required. Provide a valid email address for notification reply.

---

## 3. Required artifacts

| Artifact | Notes |
|---|---|
| Installer file | `.exe` (NSIS) or `.msi`. Typical file upload limit ~50 MB per submission. Aurora Launch installer is expected ~30-60 MB depending on PyInstaller bundle — verify size pre-submission; if >50 MB, apply `upx --best` compression on sidecar or split NSIS stub + payload |
| Submitter email | Required for vendor notification reply. Use `security@auroraai.pro` |
| SHA-256 hash | Record in `SUBMISSION_LOG.md` |
| Reason statement | "I believe this file is incorrectly detected as malware / false positive" |
| Publisher info | Aurora AI (Russia), `auroraai.pro` |
| Product description | Paste EN summary from `BUSINESS_JUSTIFICATION.md` (1000–2000 chars) |
| Detection signature name | Optional but useful if Avast UI shows label (e.g., `Generic.Heur.XXXXXX`) |

---

## 4. Avast portal form fields

Typical fields at `avast.com/false-positive-file-form.php`:

1. **Email** (required — for notification)
2. **File upload** (drag-drop or browse; size limit ~50 MB)
3. **"Why do you believe this is a false positive?"** — free-text field.
   Paste the EN summary block from `BUSINESS_JUSTIFICATION.md`; target 1000–1500 chars.
   Lead with the PyInstaller note — it directly names the heuristic trigger:

   > "Aurora Launch is a legitimate Tauri 2 desktop B2B application (Rust + TypeScript + bundled
   > Python sidecar via PyInstaller). The PyInstaller `pyz` archive format is a known false-positive
   > signal in several AV engines. The bundled Python sidecar (`aurora-sidecar.exe`) runs
   > econometric/Bayesian modeling locally; it does not access the network, inject into processes,
   > or modify the system outside its install directory. Full justification and technical detail
   > are included below. [paste BUSINESS_JUSTIFICATION.md EN section]"

4. **Comments / notes** — include SHA-256 hash of submitted file and signing key fingerprint
5. **CAPTCHA** verification

---

## 5. AVG portal differences

AVG form at `avg.com/en/signal/report-a-false-positive` follows the same structure. Use identical
justification text. In the **product name** field enter: `Aurora Launch v0.1.4`.

---

## 6. Email escalation channel

For cases requiring detailed technical dialogue or when no portal acknowledgment is received
within 3 business days:

**To:** virus@avast.com
**Subject:** `Aurora Launch v0.1.4 — False Positive Submission [PyInstaller sidecar]`

Include: SHA-256 hash, publisher name, product URL, brief technical summary from
`BUSINESS_JUSTIFICATION.md` EN section.

---

## 7. Expected review timeline

| Stage | Typical duration |
|---|---|
| Automated triage (hash lookup + signature match) | Same day, within 24 h |
| Manual security analyst review | 1–3 business days |
| Whitelist decision communicated | Within 24 h of analyst decision |
| Signature distribution (Avast Streaming Updates, hourly push) | 24 h after decision |
| **Typical full turnaround** | **2–5 business days** |

These are expected / typical ranges based on vendor documentation — not guaranteed SLAs.

---

## 8. Re-submission protocol

Each new installer hash requires a new submission. When submitting an updated version:

- Reference prior ticket number in the **Comments** field: `"Follow-up to ticket #XXXX submitted
  YYYY-MM-DD for v0.1.3 — hash change only, methodology and codebase unchanged"`
- Avast permits cross-referencing prior tickets to accelerate analyst review

Track all ticket IDs in `SUBMISSION_LOG.md`.

---

## 9. Known troubleshooting

**"File too large" upload error**
Installer >50 MB. Options: (a) apply UPX compression to `aurora-sidecar.exe` before NSIS packaging;
(b) submit NSIS stub `.exe` (main launcher) and `aurora-sidecar.exe` as separate samples with
a shared explanatory note; (c) contact via `virus@avast.com` and attach via secure upload link.

**"Identical sample previously analyzed" message**
Confirms AV-engine signature already updated for a prior submission of the same hash. Verify that
the whitelist entry applies to the *current* installer hash specifically before closing the ticket.

**Detection label `Generic.Heur.*` or `Win32:Evo-gen`**
PyInstaller heuristic trigger — common and expected. In the justification text, include:
> "PyInstaller bundling is an industry-standard method for distributing Python applications
> outside developer environments (used by Dropbox, Calibre, and thousands of open-source projects).
> The bundled `pyz` archive contains no self-modifying or process-injection code."

**Russian-origin vendor concern**
Avast and AVG apply no geographic restrictions to false-positive submissions. Aurora AI (Russia)
is treated identically to any other publisher. No special handling required.

---

## 10. Follow-up email template (use if no reply after 5 business days)

```
To: virus@avast.com
Subject: Aurora Launch v0.1.4 — False Positive Whitelist [Ref. #XXXX]

Dear Avast / AVG Threat Research Team,

I submitted a false-positive report for the Aurora Launch installer v0.1.4
on [DATE], reference ticket #XXXX. As 5 business days have elapsed without
a status update, this email serves as a follow-up.

File identifiers:
  Filename:   aurora-launch-setup-v0.1.4.exe
  SHA-256:    <HASH>
  File size:  ~[BYTES]
  Publisher:  Aurora AI (Russia)

Aurora Launch is targeting a pilot customer launch in approximately 6 weeks;
confirmation of whitelist status would be appreciated.

Canonical justification (full text):
[paste BUSINESS_JUSTIFICATION.md EN section verbatim]

Please advise if additional artifacts are needed — signed executable,
source code reference, or additional sample variants can be provided.

Best regards,
Anton Kovalenko (CEO, Aurora AI)
anton@auroraai.pro
security@auroraai.pro
```

---

## 11. Notes

**EV certificate fast path**
After EV certificate provisioning (Comodo / Sectigo, target Sprint 5), Gen Digital's reputation
engine automatically whitelists EV-signed binaries. Subsequent minor releases (v0.1.5, v0.1.6,
etc.) signed with the same EV certificate will not require manual submissions to Avast or AVG.
This is the primary motivation for prioritizing EV provisioning in Sprint 5.

**Combined install base**
Avast + AVG combined consumer install base ~400 million users globally, with significant
Russia-region presence. Whitelist coverage from this single vendor pair removes a substantial
fraction of false-positive risk for Aurora Launch pilot customers.

**Parallel submission**
Submit to Avast and AVG portals in the same session — they are independent web forms, and
parallel submission does not affect review priority. Log both ticket IDs in `SUBMISSION_LOG.md`
under the same submission date entry.
