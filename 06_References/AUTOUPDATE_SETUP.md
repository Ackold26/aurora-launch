# Aurora Launch — Auto-update setup guide

Этап 2.9 ROADMAP_POST_V0_1_0.md.

Приложение использует `tauri-plugin-updater` для проверки и установки обновлений.
Обновления подписаны Ed25519 — подпись верифицируется клиентом перед установкой.
Manifest хранится в Vercel Edge Function, подписывается в CI через GitHub Secrets.

---

## Архитектура

```
GitHub Actions release job
  → pyinstaller + tauri build (signing via TAURI_SIGNING_PRIVATE_KEY)
  → updater-manifest.json (version + platform URLs + Ed25519 signatures)
  → Vercel env vars (AURORA_LATEST_VERSION / AURORA_LATEST_PLATFORMS_JSON)
  → forced Vercel redeploy → Edge Function подаёт manifest

Aurora Launch (клиент)
  → onMount → check('https://updates.auroraai.pro/launch/{{target}}/{{arch}}/{{current_version}}')
  → tauri-plugin-updater проверяет: version > current + Ed25519 signature valid
  → если ok → UpdateAvailableBanner показывает banner
  → пользователь нажимает «Скачать и установить» → downloadAndInstall → relaunch
```

---

## Шаги первоначальной настройки (один раз, делает Антон)

### 1. Сгенерировать Ed25519 ключевую пару

```bash
# Установить Tauri CLI если нет
cargo install tauri-cli --version "^2"

# Генерация ключевой пары (выведет pubkey + privkey)
cargo tauri signer generate
```

Вывод будет примерно таким:
```
Public key:  dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXkgODlBNDFCNDRBMjUyQ0Q5OQ...
Private key: (base64-encoded private key, SAVE SECURELY)
```

**Сохрани в надёжном месте (1Password / Bitwarden / Yandex.Cloud KMS).** Если ключ потерян — пользователи не смогут получать автообновления без полной переустановки.

### 2. Добавить GitHub Secrets

Перейди: `github.com/Ackold26/aurora-launch → Settings → Secrets and variables → Actions`

Добавь три секрета:

| Secret name | Значение |
|---|---|
| `AURORA_UPDATER_PUBKEY` | Публичный ключ из шага 1 (64-char hex или base64 строка) |
| `AURORA_UPDATER_PRIVATE_KEY` | Приватный ключ из шага 1 |
| `AURORA_UPDATER_KEY_PASSWORD` | Парольная фраза (если задавал при генерации, иначе пустая строка) |

> Эти секреты уже используются в `.github/workflows/release.yml` (переменные
> `TAURI_SIGNING_PRIVATE_KEY` / `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`).

### 3. Вставить pubkey в tauri.conf.json

`src-tauri/tauri.conf.json` содержит:
```json
"plugins": {
  "updater": {
    "pubkey": "EMBED_AT_RELEASE_TIME"
  }
}
```

Замени `"EMBED_AT_RELEASE_TIME"` на реальный публичный ключ. Это build-time значение
которое вкомпилируется в бинарник. **Не добавляй в .gitignore — pubkey публичный.**

Пример готового значения:
```json
"pubkey": "dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXkgODlBNDFCNDRBMjUyQ0Q5OQ=="
```

### 4. Настроить Vercel проект для updater endpoint

Vercel Edge Function отдаёт updater manifest по URL:
`https://updates.auroraai.pro/launch/{target}/{arch}/{current_version}`

**Если Vercel проект ещё не создан:**

1. Создай Vercel project (`aurora-updates` или аналогичный) в Vercel dashboard.
2. Добавь GitHub Secrets для Vercel:
   - `VERCEL_TOKEN` — Vercel API token (Settings → Tokens)
   - `VERCEL_ORG_ID` — твой Vercel team/org ID
   - `VERCEL_PROJECT_ID` — ID проекта

3. Создай Edge Function `api/[target]/[arch]/[version].ts`:

```typescript
// api/[target]/[arch]/[version].ts
import type { VercelRequest, VercelResponse } from '@vercel/node';

export default function handler(req: VercelRequest, res: VercelResponse) {
  const latestVersion = process.env.AURORA_LATEST_VERSION ?? '';
  const platformsJson = process.env.AURORA_LATEST_PLATFORMS_JSON ?? '{}';
  const pubDate = process.env.AURORA_LATEST_PUB_DATE ?? new Date().toISOString();

  const requestedVersion = req.query['version'] as string;
  const target = req.query['target'] as string;
  const arch = req.query['arch'] as string;
  const platform = `${target}-${arch}`;

  // Если текущая версия >= latest — нет обновления (Tauri plugin сам сравнивает,
  // но возврат 204 быстрее).
  if (!latestVersion) {
    return res.status(204).end();
  }

  const platforms = JSON.parse(platformsJson) as Record<string, unknown>;
  const platformData = platforms[platform];

  if (!platformData) {
    return res.status(204).end(); // нет бинарника для этой платформы
  }

  return res.status(200).json({
    version: latestVersion,
    notes: `Aurora Launch v${latestVersion}`,
    pub_date: pubDate,
    platforms: { [platform]: platformData },
  });
}
```

4. Настрой домен `updates.auroraai.pro` на Vercel проект.

### 5. Необязательно: Yandex.Cloud KMS для хранения ключей

Если хочешь централизованное хранилище вместо GitHub Secrets:

1. Создай Yandex.Cloud KMS ключ:
   ```bash
   yc kms symmetric-key create \
     --name aurora-updater-key \
     --default-algorithm aes-256 \
     --rotation-period 8760h
   ```

2. Зашифруй приватный ключ:
   ```bash
   yc kms symmetric-crypto encrypt \
     --key-name aurora-updater-key \
     --plaintext-file private_key.pem \
     --ciphertext-file private_key.enc
   ```

3. В GitHub Actions добавь шаг расшифровки перед build:
   ```yaml
   - name: Decrypt updater key via Yandex KMS
     env:
       YC_TOKEN: ${{ secrets.YC_SERVICE_ACCOUNT_TOKEN }}
     run: |
       yc kms symmetric-crypto decrypt \
         --key-name aurora-updater-key \
         --ciphertext-file private_key.enc \
         --plaintext-file /tmp/updater_key.pem
       echo "TAURI_SIGNING_PRIVATE_KEY=$(cat /tmp/updater_key.pem)" >> $GITHUB_ENV
   ```

> Для v0.1 достаточно прямых GitHub Secrets — Yandex KMS нужен при команде 3+
> или требованиях key rotation audit trail.

---

## Проверка работы

После настройки и первого tagged release:

1. Убедись что `updater-manifest.json` создан в release artifacts.
2. Убедись что Vercel env vars обновились (`AURORA_LATEST_VERSION` etc).
3. Установи старую версию приложения → запусти → должен появиться banner.
4. Нажми «Скачать и установить» → прогресс → «Перезапустить».

---

## Troubleshooting

| Проблема | Решение |
|---|---|
| Banner не появляется | Проверь `AURORA_UPDATER_PUBKEY` в tauri.conf.json совпадает с секретом |
| `Signature verification failed` | Pubkey в конфиге и privkey в CI должны быть из одной пары |
| `Could not check for updates` | CSP в tauri.conf.json уже включает `https://updates.auroraai.pro` — проверь DNS |
| Vercel возвращает 204 | `AURORA_LATEST_PLATFORMS_JSON` не обновился — проверь publish job logs |
| Manifest не имеет нужной платформы | Проверь что build-app job завершился для нужного target |
