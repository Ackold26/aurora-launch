# F1 Key Custody Playbook

**Phase:** Σ.1.0 (audit P-04 fix)
**Owner:** Антон (custody primary), Маша (operational holder)
**Status:** Procedure documented 2026-05-14

---

## Threat model

| Threat | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Маша's machine lost/stolen | LOW | HIGH (key compromise) | BitLocker disk encryption + Veracrypt container passphrase |
| Маша leaves project | MEDIUM | MEDIUM (custody transition) | Backup USB Антона, generate new keypair, retire old |
| Customer suspects forgery | LOW | HIGH (trust chain break) | Revocation cert published, customer notified |
| Veracrypt container corruption | LOW | HIGH (key permanently lost) | 2 physical USB copies, geographic separation |
| Phishing / malware на Маша's machine | MEDIUM | HIGH (private key exfil) | Container only mounted during sign operation, never persistent |

---

## Key generation ceremony

**Когда:** один раз, перед первым pilot release.

**Кто:** Антон (passphrase), Маша (operational).

**Где:** Маша's dev machine, BitLocker-encrypted disk.

**Шаги:**

1. **Setup Veracrypt container** (Антон + Маша вместе):
   - Container path: `E:\aurora-signer.vc` (или похожее — на encrypted disk)
   - Size: 512 MB
   - Encryption: AES-256-XTS
   - Hash: SHA-512
   - Passphrase: ≥24 chars, диктуется Антоном Маше **только устно**, не в чате
   - Filesystem: NTFS (Windows)

2. **Mount container** на drive letter `E:` (или другой).

3. **Generate keypair** через Python (см. F1_LEAN_SIGNING_RUNBOOK Σ.1.1).

4. **Backup ceremony:**
   - Antоn копирует `aurora-signer.vc` (encrypted, can be copied without unlocking) на USB drive #1 — physically stores в safe
   - Маша копирует на USB drive #2 — в свой safe (или офисный)
   - Both USB drives helped только эту container — не used для general data

5. **Public key publish:**
   - Маша extracts `public.pem`
   - Antоn signs commit на GitHub: `auroraai.pro/keys/pilot-v0.1.0.pub` (or pinned tag в repo)
   - Customer Materia Medica может download + verify manually

6. **Logging:** `custody-log.txt` (text file в каждом safe USB):
   ```
   2026-05-15 09:30 МСК | Generation ceremony | Антон + Маша | aurora-signer.vc v1.0
   2026-05-15 09:45 МСК | Public key published к GitHub commit abc123 | Антон
   ```

---

## Signing operation procedure (ежедневная)

**Когда:** при сборке release build или подписи Methodology Certificate.

1. **Маша:** Mount Veracrypt container на dev machine
2. **Подпись:** Run signing operation (build command per F1_LEAN_SIGNING_RUNBOOK Σ.1.2)
3. **Audit log:** Append к custody-log.txt:
   ```
   2026-08-15 14:30 МСК | sign methodology_cert | KAG-2024-anon → VEN-recipient | bundle_hash abcdef123
   ```
4. **Dismount:** Veracrypt container ➜ закрыть. Working copy memory cleared.

**НЕ ДЕЛАТЬ:**
- ❌ Хранить decrypted private key на диске
- ❌ Копировать private key на cloud (Google Drive, Dropbox)
- ❌ Отправлять private key по email или Slack
- ❌ Делать screenshots с visible private key

---

## Compromise response procedure

**Когда Маша подозревает компрометацию:**

1. **Immediate:** Маша → Антон call, не email/chat
2. **Within 1 hour:** Антон signs revocation certificate с master key
   - Format: JSON `{"revoked_pubkey": "...", "revocation_date": "...", "reason": "..."}`
   - Signed by master Ed25519 key (separate keypair, sealed в Антон's safe)
3. **Within 24 hours:** Publish revocation:
   - `auroraai.pro/revocations/pilot-v0.1.0.json` (если static hosting)
   - GitHub commit с tag `revocation-2026-08-15`
4. **Customer notification:**
   - Email Materia Medica contact + phone call
   - Disclosure: which certs affected, what action needed
5. **New keypair generation:** Repeat key generation ceremony with fresh container
6. **Re-sign affected certs:**
   - All active bundles re-generated с new keypair
   - Customers receive new installer + cert files
7. **Update GitHub `auroraai.pro/keys/pilot-v0.1.0.pub`** to new key
8. **Retire old:** rename Veracrypt container `aurora-signer-retired-2026-08-15.vc`, keep in safe (audit trail)

---

## Rotation schedule (planned)

| Trigger | Action | Owner |
|---|---|---|
| Phase X M-CS deploy | Migrate signing к Yandex KMS; retire local keypair | Антон |
| Annual review | Generate fresh keypair, parallel run 60 days, retire old | Антон + Маша |
| Маша off-project | Transfer custody, fresh ceremony, retire all old keys | Антон → new operator |

---

## Recovery от lost passphrase

**Если Антон забыл passphrase:**

⚠️ **No recovery possible.** Veracrypt container without passphrase = permanent loss.

**Mitigation:**
- Passphrase stored в Антон's password manager (Bitwarden Org Vault).
- Hint about passphrase format письменно в Антон's safe (НЕ сам passphrase).
- Quarterly drill: Маша + Антон verify passphrase still works.

**Если container lost полностью (USB #1 + #2 + Маша's working machine):**
- Same as compromise response — generate new keypair, re-sign all active certs.
- Notify Materia Medica.
- Update GitHub public key.

---

## Phase X M-CS upgrade path

When ready к migrate (post-pilot или customer demand):

1. Yandex Cloud KMS provisioned (per F1_DEPLOYMENT_RUNBOOK)
2. Generate new keypair INSIDE KMS (private key never leaves Yandex secure HSM)
3. Public key extracted, embedded в new release build
4. Old local keypair retired (kept in safe для historical signature verification)
5. New certs signed via KMS Vercel Edge Function
6. Customer migration: receive update notification, install new version

**Customer impact:** mostly transparent. UI badge updates from "Подпись разработчика
(pilot release)" к "Подпись Yandex KMS (cloud-verifiable)".

---

**Status:** Procedure ready. Awaiting key generation ceremony (Антон approve calendar).
