# Aurora Launch - Threat Model

**Status:** v1.0 (2026-05-04)
**Authority:** Audit enhancement E5
**Source:** STRIDE methodology + Aurora Suite security context

## Контекст

Premium product (1.5-3M/год) с sensitive data (DSM/Mediascope, recipient anchors) требует explicit threat modeling. Aurora Launch local-first architecture снимает большинство cloud risks но не all - надо думать systematically.

---

## 1. STRIDE Threat Categories

### S - Spoofing
Атакующий выдаёт себя за легитимного user'а.

### T - Tampering
Изменение data / code в transit или at rest.

### R - Repudiation
User отказывается от своих действий (нет audit trail).

### I - Information Disclosure
Утечка sensitive data.

### D - Denial of Service
Блокирование legitimate access.

### E - Elevation of Privilege
Получение прав выше intended.

---

## 2. Assets

| Asset | Sensitivity | Storage | Mitigation Priority |
|---|---|---|---|
| Client DSM data | High | Local %USERPROFILE% | Local-first + DPA |
| Client Mediascope data | High | Local | Local-first + DPA |
| Recipient anchors | Medium-High | Local .aurora bundle | Local-first |
| Forecast outputs | Medium | Local + reports | Optional .aurora encryption |
| Aurora license keys | Medium | Local %LOCALAPPDATA% (encrypted) | Ed25519 signed + AES cached |
| Proxy brand identity | Low (синдицировано) | Local | No special handling |
| Consulting log | Low-Medium | Local SQLite | Per-license isolation |
| Aurora cloud telemetry (opt-in) | Low | Aurora cloud (no PII) | Aggregate only, opt-in |
| Aurora codebase | Critical (IP) | GitHub private | Code signing release |

---

## 3. Attack Vectors

### 3.1 License Bypass

**Threat:** Атакующий обходит online license validation для использования Aurora без подписки.

**Vectors:**
- Modify local license file (Ed25519 sig validation bypass)
- Block license validation endpoint (DNS hijack)
- Reverse engineer license format
- Share license keys между unrelated machines

**Mitigations:**
- Ed25519 signature на license key (cryptographically infeasible to forge)
- Online validation required (initial activation + monthly heartbeat)
- Machine fingerprint binding (license tied to specific hardware)
- Code signing prevents modified executables (Windows SmartScreen warns)
- License revocation mechanism (Aurora cloud blacklist)

**Residual risk:** medium. Determined attacker может delay strategies, но не полностью bypass для extended period. Acceptable - target market enterprise что pay anyway.

### 3.2 Data Exfiltration

**Threat:** Sensitive client data leaves machine without consent.

**Vectors:**
- Malicious code в Aurora Launch (supply chain)
- Compromised dependencies (npm / PyPI / Cargo crates)
- Unintended logging (raw client data в logs)
- Update mechanism abused для backdoor

**Mitigations:**
- **No telemetry of raw data** (only aggregates, opt-in)
- Dependency pinning + audit (`cargo audit`, `npm audit`, `pip-audit` в CI)
- Code review для все merge to main
- Code signing (signed installer prevents modification)
- Update mechanism uses signed releases (Aurora private key)
- Logs scrubbed of values (only types + counts)
- Local-only operation by default

**Residual risk:** low. Threat requires compromise Aurora's release pipeline OR major dependency.

### 3.3 Supply Chain Attack

**Threat:** Compromised dependency injects malicious code.

**Vectors:**
- npm package compromised (Svelte ecosystem)
- PyPI package compromised (Pydantic, NumPyro, JAX, pandas)
- Cargo crate compromised (Tauri ecosystem)
- Build environment compromised (CI server, signing key)

**Mitigations:**
- Lockfile pinning (`Cargo.lock`, `package-lock.json`, `requirements.lock` strict)
- Vulnerability scanning в CI (`cargo audit`, `npm audit`, `pip-audit`)
- SBOM generation per release (Software Bill of Materials)
- Reproducible builds (where possible)
- Signing key offline storage (HSM or hardware token)
- Multi-factor signing process (Антон confirmation)

**Residual risk:** medium. Industry-wide problem, mitigations standard practice.

### 3.4 Insider Threat (Aurora Team)

**Threat:** Aurora team member misuses access to client data.

**Vectors:**
- Антон uses screen-share session content для другого клиента
- Маша sees client data в bug reports
- Compromised Aurora team member accounts

**Mitigations:**
- **Aurora team has NO direct access к client raw data** (local-first principle)
- Bug reports don't include data (only error types + line numbers)
- Screen-share sessions: client controls what's shared
- DPA contractually limits use of seen data
- Aurora team accounts use 2FA + device-bound keys
- Background checks для key team members (Phase D scaling)

**Residual risk:** low (small team, accountable, technical mitigations).

### 3.5 Multi-tenant Cross-Client Data Mix

**Threat:** Client X's data accidentally appears в Client Y's project.

**Vectors:**
- File collision на shared machine (e.g., agency analyst has both clients on same Windows account)
- Cache contamination
- Default file paths default to single location
- Aurora cloud (если used) mixes data

**Mitigations:**
- License-key-scoped local storage (`%LOCALAPPDATA%\Aurora Launch\{license_hash}\`)
- Per-project isolated storage (`.aurora` bundle - explicit user choice path)
- No cloud data sharing default
- Project file picker prevents accidental cross-project loading

**Residual risk:** low. Local-first + per-project bundles inherently isolate.

### 3.6 Vulnerable Updates

**Threat:** Update mechanism delivers malicious or buggy build.

**Vectors:**
- Compromised release private key
- Man-in-the-middle на update channel
- Unverified update accepted
- Rollback attack (downgrade к vulnerable version)

**Mitigations:**
- Updates fetched через HTTPS (TLS 1.3)
- SHA-256 verification of downloaded installer
- Signature verification (Aurora signing cert)
- Version monotonicity check (no downgrade без explicit user action)
- Update channel rosst-updates (existing infrastructure)
- Staged rollout (10% → 50% → 100%) для major versions

**Residual risk:** low.

### 3.7 Physical Access (Lost Laptop)

**Threat:** Client laptop lost / stolen exposes data.

**Vectors:**
- Unencrypted Windows account (no BitLocker)
- Unlocked screen
- USB extraction

**Mitigations:**
- **Client responsibility** - Aurora не control client's machine security
- Recommendation в onboarding: Windows BitLocker + strong password
- Optional `.aurora` encryption (Phase C feature) - AES-256 client-side
- License revocation если known stolen (client reports → Antón disables key)

**Residual risk:** medium. Client-controlled, документировано в DPA.

### 3.8 DoS through Resource Exhaustion

**Threat:** Crafted input causes Aurora Launch to consume excessive resources.

**Vectors:**
- Massive XLSX import (hundred millions of rows)
- Pathological MCMC convergence (no timeout)
- Recursive schema migration loop

**Mitigations:**
- Input size limits (e.g., DSM Excel ≤ 50MB, ≤ 200K rows)
- MCMC timeout (30 minutes max, then bail с error)
- Schema migration max 10 hops (prevent infinite loop)
- Memory limits monitored (Aurora Launch ≤ 4GB RSS, kill if exceeded)

**Residual risk:** low (only affects user's own machine).

---

## 4. Top 10 Risks (Prioritized)

| # | Risk | Severity | Likelihood | Mitigation Status |
|---|---|---|---|---|
| 1 | Supply chain compromise | High | Low | Implemented (lockfile, audit, signing) |
| 2 | License key sharing / piracy | Medium | Medium | Implemented (Ed25519 + machine binding) |
| 3 | Update mechanism abused | High | Very Low | Implemented (signed releases) |
| 4 | Multi-client data mix on shared workstation | Medium | Medium | Implemented (license-scoped storage) |
| 5 | Lost laptop with unencrypted projects | High | Medium | Documented (BitLocker recommendation) |
| 6 | Compromised Antón/Маша account | High | Very Low | Implemented (2FA) |
| 7 | DSM/MS data leak through Aurora bug | Medium | Low | Mitigated (no telemetry of raw data) |
| 8 | Logs contain sensitive values | Low | Medium | Mitigated (logs scrubbed) |
| 9 | Cross-client analytics aggregate реверсимо | Low | Very Low | Mitigated (k-anonymity, no individual events) |
| 10 | Aurora cloud breach (opt-in telemetry) | Low | Very Low | Mitigated (no client raw data в cloud) |

---

## 5. Compliance Mapping

| Regulation | Aurora Launch Status |
|---|---|
| **РФ 152-ФЗ (личные данные)** | N/A - Aurora не processes PII (aggregate brand-level data только) |
| **GDPR** | Phase D consideration (если EU customers); DPA template aligns |
| **PCI DSS** | N/A - no payment card processing |
| **HIPAA** | N/A - no health data |
| **SOC 2** | Future Phase D goal (после establishment) |
| **ISO 27001** | Future Phase D goal |

---

## 6. Incident Response

См. DATA_PRIVACY.md Section 8 для full IR procedure. Quick summary:

**On detection:**
1. Assess scope (what data potentially affected)
2. Contain (block compromised credentials, revoke licenses)
3. Communicate (clients within 72h via email + product banner)
4. Remediate (patch, rotate keys, etc.)
5. Post-mortem (lessons learned, ADR)

---

## 7. Update Cadence

**Threat model review:**
- Major: per Sprint major (B6, Phase C, Phase D) - revisit assets + threats
- Minor: quarterly - review risks and mitigations
- Triggered: после security incident OR major dependency update

**Update mechanism:**
- Major versions every 6 months
- Patch versions every 2 weeks
- Critical security patches: immediate (within 24-48h discovery)
- Public changelog с CVE references если applicable

---

## Связанные документы

- `DATA_PRIVACY.md` - operational privacy + DPA
- `decisions/` - ADRs для security-related decisions
- `../00_Overview/PRINCIPLES.md` - P14 Local-first
