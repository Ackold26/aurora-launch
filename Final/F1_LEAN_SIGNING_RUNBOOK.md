# F1 Lean Signing Runbook — Pilot Edition

**Phase:** Σ.1 — Lean F1 signing (audit-revised v3.0 §F)
**Owner:** Маша (key generation + build), Антон (custody approval)
**Time:** ~3h Маша + 1h Антон
**Status:** Documented 2026-05-14

---

## Цель

Подписывать Methodology Certificate + bundle artefacts локально (без cloud
KMS), чтобы пилот стартовал без блокировки на Yandex KMS / Vercel infra.
Cloud upgrade — Phase X M-CS module, deploys в 2 дня если customer
explicitly requests.

**НЕ ЗАМЕНЯЕТ** production-grade KMS for v0.1.x. Это **pilot release** path —
Materia Medica Кагоцел/Венарус принимают dev-signed cert с явным disclosure.

---

## Σ.1.0 Key custody ceremony (1h, Антон + Маша)

**Когда:** перед первой подписью pilot bundle.

**Что делается:**
1. Открыть Veracrypt — создать new encrypted container `aurora-launch-signer.vc` (512 MB, AES-256, passphrase 24+ chars known только Антону)
2. Generate Ed25519 keypair в этом container (см. §Σ.1.1)
3. Container скопировать на 2 USB drive:
   - **Primary:** USB в safe Антона
   - **Backup:** USB в safe Маши (или другое физически разделённое место)
4. Public key extract → `auroraai.pro/keys/pilot-v0.1.0.pub` (опубликовать после deploy)
5. Логи операций: text file `key-custody-log.txt` в каждом safe — кто, когда, что делал
6. Working copy (decrypted) живёт только в memory во время signing operation, удаляется after

**Compromise response (документировано):**
- Маша подозревает компрометацию (lost machine, theft) → немедленно Антон
- Антон signs revocation cert master key → publish `auroraai.pro/revocations/`
- Notify Materia Medica email + call с явным disclosure
- Re-sign все active certs с new keypair
- Old keypair retired в `aurora-launch-signer-retired-{date}.vc`

**Rotation (Phase X M-CS):** при переходе на Yandex KMS → новый keypair generated через KMS, customer-side public key updated через auto-updater bundle (если deploy'd) или manual install.

---

## Σ.1.1 Local Ed25519 keypair generation (~30 min, Маша)

**Prerequisites:** Veracrypt container открыт, Python 3.12+ с `cryptography` library.

**Шаги:**

```python
# В Veracrypt-mounted folder (E:\aurora-signer\ для example):
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

# Generate keypair
private_key = ed25519.Ed25519PrivateKey.generate()

# Save private (PKCS8 unencrypted — already в encrypted container)
private_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)
with open("E:/aurora-signer/private.pem", "wb") as f:
    f.write(private_pem)

# Save public PEM (this gets embedded in release build)
public_key = private_key.public_key()
public_pem = public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)
with open("E:/aurora-signer/public.pem", "wb") as f:
    f.write(public_pem)
print("Public key (copy this к env var):\n")
print(public_pem.decode("utf-8"))
```

**Verification после generation:**

```python
# Smoke test: sign + verify round-trip
message = b"Aurora Launch test signature"
signature = private_key.sign(message)
public_key.verify(signature, message)  # raises if invalid
print("Keypair OK")
```

---

## Σ.1.2 Embed pubkey в release build (~30 min, Маша)

Production build embeds public PEM via env var, проверка происходит в Rust
`methodology_cert.rs` (Block 2C).

**Build command:**

```powershell
# In aurora-launch checkout:
$env:AURORA_BUILD_PROFILE = "production"
$env:AURORA_CLOUD_PUBLIC_KEY_PEM = (Get-Content "E:\aurora-signer\public.pem" -Raw)
# Updater pubkey not needed для pilot (auto-updater отключен — см. Σ.1.3)
$env:AURORA_UPDATER_PUBKEY = "0000000000000000000000000000000000000000000000000000000000000000"
npm run tauri build -- --target x86_64-pc-windows-msvc
```

**Output:** `src-tauri/target/release/bundle/nsis/Aurora Launch_0.1.0_x64-setup.exe`

**Smoke test on clean Windows VM:**
1. Install Aurora Launch
2. Open sample bundle (Σ.0.4 pre-shipped Кагоцел→Венарус demo)
3. Generate Methodology Certificate
4. Verify cert через verify_bundle_signature IPC — должен показать
   `trust_badge="local_dev_pilot"` + green checkmark + customer-visible
   "Подпись разработчика (pilot release)" disclosure

---

## Σ.1.3 Disable auto-updater в pilot tauri.conf.json (~10 min)

For pilot Materia Medica we ship manual update procedure (Phase X M-AU
will add Vercel-backed auto-updater).

**Edit `src-tauri/tauri.conf.json`:**

```json
"plugins": {
  "updater": {
    "active": false,
    "_comment": "Pilot v0.1.0: manual updates only. Phase X M-AU module ships Vercel auto-updater."
  }
}
```

Customer-facing update flow для pilot:
1. Маша emails customer: «v0.1.1 available, скачайте https://aurora-launch-releases.s3...»
2. Customer downloads new installer, runs
3. Auto-installer detects existing install и upgrades в place (NSIS default)
4. Workspace data в `%LOCALAPPDATA%/Aurora Launch/` preserved
5. Customer opens app — version banner shows new version

---

## Σ.1.4 Sign Methodology Certificate locally + visible chain (~30 min, Маша)

Customer-facing UI requirement: chain of trust visible на cert badge so
customer sees what's signing the document.

**Existing implementation:** `src-tauri/src/commands/methodology_cert.rs`
(Block 2C) — verify_bundle_signature returns trust_badge field.

**Pilot release values:**

```json
{
  "valid": true,
  "trust_badge": "local_dev_pilot",
  "provenance": "Aurora Launch dev key (sealed envelope)",
  "verifier_endpoint": "local CLI: aurora-launch-verify <bundle.aurora>",
  "customer_visible_text": "Подпись разработчика (pilot release)",
  "upgrade_path": "Phase X M-CS — cloud KMS verifier (2 дня deploy при customer request)"
}
```

**UI Inspector tab (Block 2D Methodology Certificate component):**

```
┌────────────────────────────────────────────────┐
│ ✅ ПОДПИСЬ ВЕРИФИЦИРОВАНА                       │
│                                                │
│ Метод: Ed25519                                 │
│ Источник: Aurora Launch dev key                │
│ Версия: v0.1.0 (pilot release)                 │
│ Время: 2026-08-15T10:23:45Z                    │
│                                                │
│ ⓘ Пилотный режим: подпись хранится локально.   │
│   Cloud verifier (любой 3-й стороной)           │
│   доступен в v0.1.1 после M-CS deploy.         │
│                                                │
│ [Просмотреть полную цепочку →]                 │
└────────────────────────────────────────────────┘
```

---

## Σ.1.5 Smoke test checklist (Антон, ~1h)

Перед отправкой installer Materia Medica:

- [ ] Clean Windows 11 VM (без Aurora Launch previously installed)
- [ ] Install NSIS installer — UAC prompt, install completes без error
- [ ] App launches < 2s к webview ready
- [ ] First-run welcome animation works
- [ ] Open Sample Кагоцел → Венарус — forecast generates < 5s
- [ ] Methodology Certificate generates — PDF opens, signature badge shown
- [ ] Verify cert via local CLI tool (если deployed) — green checkmark
- [ ] Diagnostics: Help → Send Diagnostics → ZIP создан в %TEMP%
- [ ] mailto: link opens default mail client с pre-filled subject/body
- [ ] Crash test: force-kill sidecar via Task Manager → app shows crash dialog on next start, offers recovery
- [ ] Uninstall — firewall rules removed, %LOCALAPPDATA% data preserved (or asked to remove)

**Если все green → Сборка готова к F2a installer ship (Phase Σ.2).**

---

## Что НЕ входит в lean F1 (Phase X deferred)

- Yandex.Cloud KMS integration (M-CS module, ~9h Антон)
- Vercel signing endpoint + auto-rotation
- verify.auroraai.pro public WASM verifier (M-WV module, ~25h)
- Auto-updater manifest signing (M-AU, ~3h after M-CS)
- Code signing certs для Authenticode (M-CS-S, после юрлица)

Customer disclosure (per AQ-02 honest baseline):
> «v0.1.0 pilot release использует локальное подписание (sealed envelope
> процедура). Cloud-verifiable signature через verify.auroraai.pro
> доступна в v0.1.1+ (~2 weeks deploy при запросе).»

---

**Approval:** Маша signs after key generation done. Антон signs after smoke test green.

**Tag trigger:** Σ.1.0-Σ.1.5 ✅ → Σ.2 installer build → tag `v0.1.0-rc2`.
