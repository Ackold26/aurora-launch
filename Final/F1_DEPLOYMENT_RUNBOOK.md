# Final F1 — Deployment Runbook

**Owner:** Антон (infrastructure provisioning) + Маша (code shipped, this commit)
**Tag entering:** `v0.1.0-rc1` (Block 4 sidecar shipped)
**Tag exiting:** `v0.1.0-rc2` (cloud signing live, ready для F2 installer + F3 pilot)
**Estimated:** ~6h Антон + ~3h Маша smoke verification

## Why F1

Three Block 3 BLOCKERs deferred their fix к F1:
- **BLOCKER-2:** `AURORA_CLOUD_PUBLIC_KEY_PEM` placeholder — Aurora Launch verifier returns "key unavailable" until production cloud KMS public key embedded в release builds
- **BLOCKER-3:** `AURORA_UPDATER_PUBKEY` placeholder — production updater would accept any signature без real pubkey

Plus net-new infra:
- Vercel Edge Functions для signing / telemetry / feedback / updater manifest endpoints
- Yandex.Cloud KMS для Ed25519 signing key (private part never leaves KMS)
- DNS records под `auroraai.pro` umbrella

After F1: Aurora Launch produces signed `.aurora` bundles, end-to-end Methodology Cert verification works cross-machine.

---

## Step 0 — Prerequisites checklist

- [ ] Yandex.Cloud account active с billing enabled (KMS = ~$1/month per key + $0.001 per sign)
- [ ] Vercel Pro account (for KV storage + production environment)
- [ ] DNS control over `auroraai.pro` (Cloudflare / your registrar)
- [ ] GitHub Personal Access Token (PAT) с `repo` scope для feedback issue creation
- [ ] Email на `support@auroraai.pro` configured (для license notifications, F3 pilot)

---

## Step 1 — Yandex.Cloud KMS setup (~30 мин Антон)

### 1.1 Create service account

```bash
yc iam service-account create --name aurora-cloud-signer \
  --description "Aurora Launch C7 methodology cert signing"
```

Note the SA id (looks like `ajeXXXXXXXXX`).

### 1.2 Create asymmetric Ed25519 key

```bash
yc kms asymmetric-signature-key create \
  --name aurora-launch-cert-signer \
  --signature-algorithm ed25519 \
  --description "Aurora Launch v0.1.0 methodology cert signing — Final F1"
```

Note the key id (`abjXXXXXXXXX`). This goes к `AURORA_KMS_KEY_ID` env var.

### 1.3 Grant SA access к key

```bash
yc kms asymmetric-signature-key add-access-binding \
  --name aurora-launch-cert-signer \
  --service-account-id ajeXXXXXXXXX \
  --role kms.keys.encrypterDecrypter
```

### 1.4 Export public key (PEM + hex)

```bash
yc kms asymmetric-signature-key get-public-key \
  --name aurora-launch-cert-signer \
  --format pem > aurora-cloud-public-key.pem

# Convert PEM SPKI к raw 32-byte hex (для Aurora Launch build env)
python3 - <<'PY'
import base64
import re
pem = open('aurora-cloud-public-key.pem').read()
body = re.sub(r'-----[^-]+-----|\\s', '', pem)
der = base64.b64decode(body)
# Find OID 1.3.101.112 (06 03 2b 65 70) и extract 32 bytes after BIT STRING tag
prefix = bytes.fromhex('06032b6570')
idx = der.index(prefix)
bit_string_start = idx + len(prefix)
# Expect 03 21 00 <32 raw bytes>
assert der[bit_string_start] == 0x03 and der[bit_string_start+1] == 0x21 and der[bit_string_start+2] == 0x00
raw = der[bit_string_start+3:bit_string_start+35]
print('hex:', raw.hex())
PY
```

Save outputs:
- `aurora-cloud-public-key.pem` — paste full PEM (с BEGIN/END markers) → `AURORA_CLOUD_PUBLIC_KEY_PEM` (Aurora Launch release env, replaces Block 3 placeholder)
- hex output → `AURORA_CLOUD_PUBLIC_KEY_HEX` (Vercel signing function env)

### 1.5 Generate SA JWT для Vercel cold-start

```bash
yc iam key create --service-account-name aurora-cloud-signer \
  --output aurora-sa-key.json --algorithm rsa_4096

# Generate long-lived JWT (1-year expiry recommended)
python3 - <<'PY'
import json, jwt, time
with open('aurora-sa-key.json') as f:
    sa = json.load(f)
now = int(time.time())
payload = {
    'iss': sa['service_account_id'],
    'aud': 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
    'iat': now,
    'exp': now + 365 * 24 * 3600,
}
encoded = jwt.encode(payload, sa['private_key'], algorithm='PS256', headers={'kid': sa['id']})
print(encoded)
PY
```

Save output → `AURORA_KMS_SA_JWT` (Vercel env). **Rotate yearly.**

⚠️ **Securely delete `aurora-sa-key.json` after JWT generation** — private key leaks compromise the signing service.

---

## Step 2 — Updater pubkey generation (~5 мин Антон)

Tauri updater requires Ed25519 keypair (separate from cloud KMS — used для signing INSTALLERS, not bundles).

```bash
# Use Tauri CLI or npm script
cd frontend
npx @tauri-apps/cli signer generate -w ~/.aurora/updater-key.txt
```

Output: `~/.aurora/updater-key.txt` (private, password-protected) + `~/.aurora/updater-key.txt.pub` (public, hex).

Save:
- Public key (hex from `.pub` file) → GitHub Secret `AURORA_UPDATER_PUBKEY`
- Private key (full content of `.txt` file) → GitHub Secret `AURORA_UPDATER_PRIVATE_KEY`
- Password → GitHub Secret `AURORA_UPDATER_KEY_PASSWORD`

⚠️ Без `AURORA_UPDATER_PUBKEY` set — `cargo build --release` (production) fails per `build.rs::BLOCKER-3 GATE` panic. This is intentional defense.

---

## Step 3 — Vercel project setup (~1h Антон)

### 3.1 Create project

```bash
cd aurora-cloud
npm install
npx vercel link --project aurora-cloud
```

### 3.2 Set env variables

```bash
# License JWT verification (issued by aurora-platform-core)
npx vercel env add AURORA_LICENSE_VERIFY_KEY_PEM production  # paste platform-core public PEM

# KMS access (from Step 1)
npx vercel env add AURORA_KMS_KEY_ID production              # abjXXXXXXXXX
npx vercel env add AURORA_KMS_SA_JWT production              # JWT from 1.5
npx vercel env add AURORA_CLOUD_PUBLIC_KEY_HEX production    # 64-char hex from 1.4

# Feedback GitHub Issues
npx vercel env add AURORA_GITHUB_PAT production              # PAT with `repo` scope
npx vercel env add AURORA_FEEDBACK_REPO production           # Ackold26/aurora-launch-feedback

# Updater manifest (managed by release pipeline)
npx vercel env add AURORA_LATEST_VERSION production          # 0.1.0-rc2 (initial)
npx vercel env add AURORA_LATEST_PUB_DATE production
npx vercel env add AURORA_LATEST_PLATFORMS_JSON production   # {} initially
```

### 3.3 Vercel KV setup

```bash
npx vercel kv create aurora-launch-kv
# Vercel auto-injects KV_URL / KV_REST_API_URL / etc. env vars
```

### 3.4 Deploy

```bash
npx vercel deploy --prod
```

Endpoints active:
- `https://api.auroraai.pro/api/sign`
- `https://api.auroraai.pro/api/telemetry`
- `https://api.auroraai.pro/api/feedback`
- `https://api.auroraai.pro/api/updater/{target}/{arch}/{version}`

---

## Step 4 — DNS records (~15 мин Антон)

Add three CNAME records (Cloudflare / your registrar):

```
api.auroraai.pro     CNAME aurora-cloud.vercel.app
updates.auroraai.pro CNAME aurora-cloud.vercel.app
cdn.auroraai.pro     CNAME aurora-cloud.vercel.app
```

Or single `CNAME *.auroraai.pro → aurora-cloud.vercel.app`.

Verify Vercel domain attach:

```bash
npx vercel domains add api.auroraai.pro aurora-cloud
npx vercel domains add updates.auroraai.pro aurora-cloud
```

---

## Step 5 — GitHub repo secrets (~10 мин Антон)

Set в `Ackold26/aurora-launch` → Settings → Secrets and variables → Actions:

| Secret | Source |
|---|---|
| `AURORA_UPDATER_PUBKEY` | Step 2, hex |
| `AURORA_UPDATER_PRIVATE_KEY` | Step 2, txt content |
| `AURORA_UPDATER_KEY_PASSWORD` | Step 2 password |
| `VERCEL_TOKEN` | Vercel → Account Settings → Tokens |
| `VERCEL_ORG_ID` | `cat aurora-cloud/.vercel/project.json` |
| `VERCEL_PROJECT_ID` | same file |

---

## Step 6 — End-to-end smoke test (~30 мин Маша)

### 6.1 Verify signing endpoint manually

```bash
# Use a license JWT issued by aurora-platform-core staging environment
TOKEN="eyJ...staging license JWT..."
curl -X POST https://api.auroraai.pro/api/sign \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "composite_hash_hex": "abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234",
    "license_jwt": "'$TOKEN'",
    "client_meta": {"aurora_app_version":"0.1.0-rc2"}
  }'
```

Expected response: 200 с `{signature_hex, public_key_hex, signed_at, key_fingerprint}`. Если 503 `kms_misconfigured` → check Step 3.2 env vars.

### 6.2 Verify updater endpoint

```bash
curl https://updates.auroraai.pro/api/updater/windows/x86_64/0.0.1
```

Expected: 200 с `{version, signature, url}` (after release pipeline ran) или 404 `platform_not_supported` (until first release tag).

### 6.3 Tag v0.1.0-rc2 to trigger release pipeline

```bash
git checkout main && git pull
git tag -a v0.1.0-rc2 -m "Final F1 cloud signing live"
git push origin v0.1.0-rc2
```

GitHub Actions workflow `release.yml` builds sidecar binary cross-platform → builds Tauri installers (Win/Mac/Linux) → signs installers с updater key → publishes manifest к Vercel → creates GitHub Release с installer assets.

### 6.4 Aurora Launch verifier roundtrip

После release artifacts available:
1. Download Aurora Launch v0.1.0-rc2 installer (Mac или Win)
2. Install + launch
3. Open sample bundle (Welcome screen "Открыть пример")
4. Inspector → Cert tab → click verify → should display "Signed by Aurora AI" с production trust badge (replaces previous "Verifying key unavailable" warning)

If trust badge shows "production" → **F1 success**. Tag accordingly.

---

## Step 7 — Post-deployment hygiene

- [ ] Add Vercel function logs к monitoring (Datadog / Vercel built-in alerts)
- [ ] Set up KMS key rotation reminder (annual; private part never leaves KMS but JWT exchange rotates yearly)
- [ ] Set up GitHub PAT rotation reminder (90 days если fine-grained)
- [ ] Document `aurora-cloud` runbook URL в Aurora platform-core README

---

## Rollback plan

If F1 deploy breaks production:

1. **Immediate:** disable Vercel signing endpoint (set env var `AURORA_KMS_KEY_ID` to empty → all `/api/sign` returns `kms_misconfigured`). Aurora Launch frontend gracefully falls к `local_dev` provenance signature.
2. **Short term:** revert problematic env var via `vercel env rm` + redeploy.
3. **Code rollback:** revert tag, push older `v0.1.0-rc1`, GitHub Actions re-publishes manifest pointing к prior installer.

---

## Block 3 BLOCKER references resolved

After F1 deploy:
- ✅ BLOCKER-2 cloud KMS verification: `AURORA_CLOUD_PUBLIC_KEY_PEM` baked into Aurora Launch release builds via env var (Step 1.4 output). Frontend `verify_bundle_signature` для cloud_kms provenance now returns valid trust badge.
- ✅ BLOCKER-3 updater pubkey: `AURORA_UPDATER_PUBKEY` GitHub secret (Step 2) + GitHub Actions env passes к build.rs. Production builds compile (no `BLOCKER-3 GATE` panic).

---

## Maша scope (~3h coding) — DONE this commit

- ✅ Vercel Edge Functions: `/api/sign`, `/api/telemetry`, `/api/feedback`, `/api/updater/*`
- ✅ License JWT verification helper (jose / Ed25519)
- ✅ Yandex.Cloud KMS sign integration (IAM token cache)
- ✅ INV-05 attack scenario tests (sign request validators)
- ✅ Telemetry rate limiting (1000 events/hour/seat) + KV storage
- ✅ Feedback PII redaction + GitHub Issue creation
- ✅ GitHub Actions: `release.yml` (full pipeline) + `sidecar-build.yml` (PyInstaller matrix) + `test.yml` (unified PR gate)
- ✅ This runbook

---

## Антон scope (~6h infrastructure) — TODO выполнить шаги выше

Шаги 1–5 above. Step 6 = совместный smoke test. Когда всё green → tag `v0.1.0-rc2` и переходим в Final F2 (installer + signing).
