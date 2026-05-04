# Aurora Launch - Data Privacy & Local-First Architecture

**Status:** v1.0 (2026-05-04)
**Authority:** Audit finding A8 (multi-tenant data privacy)
**Source:** Memory `feedback_online_only_license.md` (online license patterns) + Econometrica local-first model

## Контекст

Aurora Launch обрабатывает чувствительные данные клиентов:
- DSM Group выгрузки (commercial intelligence о категории)
- Mediascope ratings + budgets (чувствительная медиа-информация)
- Recipient anchors (стратегические бизнес-цели)
- Forecast outputs (бизнес-прогнозы)

Кроме того, клиенты могут быть **competitors** (Wavemaker и Mindshare оба клиенты Aurora). Их proxy-данные могут пересекаться. Без чёткой data privacy framework - reputational risk + legal exposure.

Этот документ - operational principles + DPA framework.

---

## 1. Local-First Architecture (Core Principle)

### 1.1 Где хранятся данные

**Все клиентские данные хранятся ЛОКАЛЬНО на машине клиента:**
- DSM/Mediascope выгрузки - в `Aurora Launch projects/` папке клиента
- `.aurora` project files - там же
- Pickle/SQLite model artifacts - там же
- Forecast reports (PPTX/HTML/XLSX/PDF) - там же

**Ничто не отправляется в Aurora cloud без explicit consent.**

### 1.2 Online connectivity (что Aurora отправляет)

Aurora Launch требует online connection для:
- **License validation** (online-only license, как Econometrica) - отправляет licence key + machine fingerprint
- **Update checks** - отправляет current version, downloads installer
- **Consulting hours sync** (opt-in) - отправляет anonymized event log (NOT data content)
- **Performance telemetry** (opt-in) - отправляет timings + error counts (NOT data content)

**Что Aurora НЕ отправляет:**
- ❌ Raw DSM/Mediascope data
- ❌ Recipient anchors
- ❌ Forecast outputs
- ❌ Proxy brand identity (only category metadata если opt-in)
- ❌ Project file contents

### 1.3 Sync between machines (для команд клиента)

Клиент может sync .aurora projects через свой собственный mechanism:
- Локальная сеть / file share
- Корпоративный cloud (OneDrive, Dropbox, SharePoint)
- Source control (Git LFS если применимо)

Aurora не predusматривает sync - это **client's responsibility и infrastructure**.

---

## 2. Aurora Team Access (Антон / эксперт)

### 2.1 Consulting hours - что мы видим

Антон при consulting session с клиентом access ТОЛЬКО через:
- **Shared screen** (клиент демонстрирует)
- **Anonymized data exports** (если клиент отправил)
- **Sample data** в onboarding

**Антон НЕ имеет direct access к raw client data** через Aurora cloud / backend.

### 2.2 Proxy review session protocol

Workflow:
1. Клиент инициирует proxy review session (запрос через UI или email)
2. Антон + клиент join screen share
3. Клиент демонстрирует свой Aurora Launch project
4. Антон reviews proxy choice + similarity scores + anchor data
5. Recommendations записываются в session notes (отдельный document, не в .aurora project)
6. Hours logged в client's local consulting tracker
7. Session ends - Антон не имеет copy данных

### 2.3 Aggregate anonymized analytics (opt-in only)

Aurora Launch может collect (с opt-in консент):
- Usage patterns (which workflows, how often)
- Performance metrics (training times, forecast horizons)
- Error rates (anonymized)
- Feature adoption

NEVER collected:
- Brand names (proxy or recipient)
- Specific values from anchors
- Forecast numbers
- Client identifiers (beyond license key hash)

---

## 3. Multi-Tenant Considerations

### 3.1 Конкуренты как клиенты Aurora

Сценарий: Wavemaker и Mindshare оба - клиенты Aurora Launch. Их работа с Aurora должна быть isolated:

**Solution: per-license sandboxing**
- Каждый license key = отдельный installation context
- Local data НЕ shared между licenses
- Aurora team НЕ видит cross-client patterns в raw data
- Proxy reviews по одному client - separate sessions

### 3.2 Common proxy data (DSM panel data)

DSM Group + Mediascope - это **syndicated data**. Множество клиентов имеют ту же подписку и могут использовать те же proxy brands.

**This is acceptable** - syndicated data publicly available по subscription. Aurora просто помогает клиенту **обработать** эти данные.

**Важно:** Aurora НЕ caches DSM/MS data centrally. Каждый клиент ingests свои выгрузки локально.

### 3.3 Client X uses Brand Y as proxy. Brand Y is also a client.

Сценарий: Wavemaker используют Кагоцел как прокси. Кагоцел - сами клиенты Aurora.

**Resolution:**
- Wavemaker имеют свою DSM/Mediascope subscription и legal access к DSM data о Кагоцел (it's syndicated)
- Кагоцел subscribe to Aurora с своим license key, своими locally stored проектами
- Wavemaker subscribe to Aurora с своим license key, локально модели
- Никакого cross-client data sharing через Aurora

---

## 4. Data Processing Agreement (DPA) Template

### 4.1 Структура DPA

Aurora Launch ships с DPA template (`06_References/DPA_TEMPLATE.docx` - prep Sprint B5):

**Sections:**
1. Definitions (Controller, Processor, Data Subject, Personal Data, Sensitive Commercial Data)
2. Subject Matter & Duration
3. Nature & Purpose of Processing
4. Categories of Data + Data Subjects
5. Obligations of Processor (Aurora):
   - Process only on documented instructions
   - Confidentiality (employees / contractors)
   - Security measures (см. Section 5)
   - Sub-processors (none default; explicit consent if added)
   - Data subject rights assistance
   - Notification of breaches
   - Deletion / return of data on termination
6. Obligations of Controller (Client):
   - Lawful basis for processing
   - Provide instructions in writing
7. Aurora Launch as Local-First Tool (key clause)
8. Audit rights
9. Liability
10. Governing law (РФ)

### 4.2 Aurora-specific clauses

Critical Aurora-specific DPA language:

> "Aurora Launch operates as a local-first software product. All client data (including but not limited to DSM Group data, Mediascope data, recipient anchors, forecast outputs) is stored exclusively on the Client's local machine. Aurora does not maintain a copy of client data on its infrastructure.
>
> Aurora's online services are limited to: license validation, software updates, opt-in usage telemetry (excluding data content), and consulting hours synchronization (excluding data content)."

### 4.3 When DPA required

- ✅ Enterprise clients (>500k turnover)
- ✅ Pharma clients (regulatory compliance)
- ✅ Banking / Fintech clients
- ✅ Any client request

Pro-active: include DPA в Aurora Launch onboarding kit.

---

## 5. Security Measures

### 5.1 Local data protection

- Aurora Launch installer signed with code signing certificate
- Installer integrity check (SHA256 verified at install)
- License key **signed** locally with Ed25519 (signature validates authenticity); online validation required для активации (Ed25519 - signing algorithm, не encryption)
- License token cached в зашифрованном виде в `%LOCALAPPDATA%` (AES-256 с machine-bound key)
- `.aurora` project files - no encryption by default (client's choice + responsibility)

### 5.2 Optional `.aurora` encryption (Phase C feature)

Phase C optional feature:
- AES-256 encryption per project с client-provided passphrase
- Useful для агентств с multi-tenant workflow (Phase D enables это properly)
- Trade-off: lost passphrase = lost project (no recovery)

### 5.3 Network security

- All Aurora online services use HTTPS (TLS 1.3)
- License keys never transmitted in plaintext
- Update downloads SHA-256 verified
- No credentials stored in client app config (license validates online each session)

### 5.4 Code signing

- Aurora Launch installer signed (Аврора corporate cert или EV cert)
- Anti-malware compatible (Defender exclusions documented в IT-doc для клиентов)

---

## 6. Compliance & Regulatory

### 6.1 РФ 152-ФЗ "О персональных данных"

Aurora Launch обычно НЕ обрабатывает personal data (PII):
- DSM/Mediascope data - aggregate brand-level
- Recipient anchors - business intelligence, не PII
- Forecast outputs - aggregate sales numbers

**Если клиент обрабатывает PII (e.g., individual customer purchase data в их workflow) - это НЕ in Aurora Launch scope.** Aurora doesn't ingest such data.

### 6.2 GDPR (если клиенты в EU)

Phase D consideration. Currently Aurora Launch focused на РФ market.

Если EU client:
- DPA align с GDPR Article 28
- Data Processing Records maintained
- DPO контактная информация
- Аналог 72-hour breach notification

### 6.3 ISO 27001 alignment (Phase D goal)

Practices align с ISO 27001:
- Information security policy
- Risk management
- Asset inventory
- Access control
- Cryptographic controls
- Physical security (Aurora team workstations)
- Operations security
- Communications security
- Acquisition / development / maintenance
- Supplier relationships
- Incident management
- Business continuity
- Compliance audits

Full ISO 27001 certification - Phase D goal (после establishment client base).

---

## 7. Data Retention & Deletion

### 7.1 Client data retention

- Client controls retention - data stored locally
- Aurora не имеет cloud-stored client data, поэтому retention question не applies к Aurora's responsibility
- Recommendation: client maintains backup strategy для .aurora projects

### 7.2 Aurora-side retention (cloud minimal)

What Aurora stores on cloud (per client):
- License key + activation history (retained life of subscription + 7 years for billing audit)
- Anonymized usage telemetry (retained 24 months max, then aggregated)
- Consulting hours log (retained life of subscription + 3 years)

### 7.3 Termination

When client subscription ends:
- License invalidated (online license check fails)
- Local Aurora Launch app continues working ~30 days (grace period)
- After 30 days - Aurora Launch refuses to start (license expired)
- **Client's local .aurora projects remain on their machine** - we never touch them
- **Consulting log остаётся** на client machine (для billing reconciliation)
- Client can re-subscribe and resume

**Permanent termination (>365 days no re-sub):**
- Client может request export of consulting log to CSV
- Client может request data deletion confirmation (GDPR-style право быть забытым)
- License keys deactivated permanently в Aurora cloud DB
- .aurora projects по-прежнему остаются на client machine (мы их не имеем)

---

## 8. Incident Response

### 8.1 Incident types

- Aurora cloud breach (license server, telemetry server)
- Software vulnerability (Aurora Launch CVE)
- Lost / stolen client machine с Aurora Launch installed
- Insider threat (Антон / Aurora team member misuse)

### 8.2 Response protocol

For each incident type:
- Detection mechanism (logging, monitoring)
- Response team (Антон + Маша)
- Communication template (notify clients within 72 hours)
- Remediation steps
- Post-incident review

### 8.3 Client notification template

If Aurora cloud breach:
> "Aurora Launch incident notification: [DATE]
>
> We detected unauthorized access to [SCOPE]. Your client data was [NOT/POTENTIALLY/CONFIRMED] affected.
>
> Aurora Launch operates as local-first - your business data (DSM/Mediascope/anchors/forecasts) remains stored locally on your machines. The breach was limited to: [CLOUD SCOPE].
>
> Recommendations: [ACTIONS].
>
> Contact: support@auroraai.pro"

---

## 9. Visibility to Client (Trust Signals)

### 9.1 Privacy dashboard в Aurora Launch UI

Settings → Privacy section shows:
- "Local-first: data stays on your machine ✓"
- "Online services: license + updates + telemetry (opt-in)"
- Telemetry toggle (opt-in/out)
- Consulting hours sync toggle
- Last sync timestamp
- "What we send" link к detailed list

### 9.2 Public privacy policy

`auroraai.pro/privacy` - human-readable policy:
- What we collect (cloud-side)
- What we DON'T collect
- Local-first commitment
- DPA available on request
- Контакты для privacy questions

### 9.3 Onboarding privacy notice

При first launch Aurora Launch:
- Brief privacy notice modal
- "Aurora Launch обрабатывает данные локально на вашей машине"
- "Никакие бизнес-данные не покидают вашу машину без явного согласия"
- "[Read full privacy policy] [Accept and continue]"

---

## 10. Audit Trail (Client-Side)

Per audit trail (`UX_PRINCIPLES.md` Section 1.5):
- Each significant action logged locally в SQLite event log
- Visible в Aurora Launch UI (sidebar timeline)
- Exportable to CSV для quarterly review
- Useful для client's own compliance / audit needs

---

## 11. Future Considerations

### 11.1 Multi-tenant Data Studio (Phase D)

Phase D will introduce multi-tenant Data Studio для агентского use case:
- Per-tenant workspace isolation (separate data folders)
- Permission model (who can see what within an agency)
- White-label option

This will require new privacy framework - this document covers Phase B base only.

### 11.2 Cloud sync option (Phase D, opt-in)

Phase D may offer optional Aurora cloud sync для команд с distributed workforce:
- Encrypted client-side before upload
- End-to-end encryption (Aurora не имеет ключ)
- Opt-in only, off by default
- Premium tier feature

---

## Связанные документы

- `../00_Overview/PRINCIPLES.md` - P6 (Assisted product principles)
- `UX_PRINCIPLES.md` - Privacy dashboard UI
- Memory: `feedback_online_only_license.md` - online license pattern
- DPA template (Sprint B5 prep): `06_References/DPA_TEMPLATE.docx`
- Public privacy policy (Sprint B6): `auroraai.pro/privacy`
