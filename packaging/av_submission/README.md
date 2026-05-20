# Aurora Launch — AV Whitelist Submission Guide

Coordinated submission package для подачи Aurora Launch installer на whitelist
в 5 AV-вендорах. **Submission timeline target: Sprint 3 end (Day 8-9), expected
review window 2-4 weeks → ready by Sprint 5 pilot launch.**

## Структура папки

```
packaging/av_submission/
├── README.md                     ← этот документ — submitter operational guide
├── BUSINESS_JUSTIFICATION.md     ← canonical EN + RU описание продукта (используется
│                                    как Justification block в каждом vendor portal)
├── symantec.md                   ← Symantec Endpoint Protection / Norton
├── mcafee.md                     ← McAfee Total Protection / Trellix
├── avast.md                      ← Avast / AVG (Gen Digital)
├── kaspersky.md                  ← Kaspersky Endpoint Security
└── defender.md                   ← Microsoft Defender (Windows built-in)
```

## Pre-submission checklist (выполнить ДО любой подачи)

- [ ] **Сборка production installer v0.1.4** — `npm run tauri:build` через CI
      pipeline (NSIS .exe + MSI), архивирован в release manifest на GitHub
- [ ] **SHA-256 hash установщика** — компонент каждой submission
- [ ] **Ed25519 отпечаток ключа подписи** — заполнить в `BUSINESS_JUSTIFICATION.md`
      placeholder `[to be filled at release time]`
- [ ] **EV-сертификат timeline** — подтвердить с Антоном expected дату
      провижионинга от Comodo / Sectigo (target: 6 weeks из Sprint 3 end)
- [ ] **Контактный email security@auroraai.pro** — настроить (если ещё не)
- [ ] **HTTPS canonical URL** — `auroraai.pro/launch/download` функционирует
- [ ] **Mailbox monitoring** — anton@auroraai.pro + security@auroraai.pro
      проверяются ежедневно для vendor reply

## Submission workflow (для каждого vendor)

Каждый `<vendor>.md` содержит:

1. **Portal URL** — куда загружать installer + submitting form
2. **Account requirements** — нужен ли pre-existing аккаунт, free / paid tier
3. **Required artifacts** — installer file, SHA-256 hash, signing certificate
   info, vendor-specific форма метаданных
4. **Business justification text** — копируется из `BUSINESS_JUSTIFICATION.md`
   (EN для Symantec/McAfee/Avast/Defender, RU для Kaspersky если portal
   принимает русский)
5. **Submission email template** — для vendor'ов без web-portal (или для
   follow-up)
6. **Expected review timeline** — типичный SLA vendor'а для whitelist requests
7. **Троублешутинг** — known issues + retry steps если submission отклонён

## Operational notes

- **Parallel submission** — все 5 vendors можно подавать в один день. Они
  независимы. Параллельность сокращает critical path до 4-недельного worst-
  case review.
- **Submission email tracking** — каждый submission'у присваивается ticket / case
  ID. Save them в `packaging/av_submission/SUBMISSION_LOG.md` (создаётся при
  первой подаче) с полями: vendor, date_submitted, ticket_id, status, last_update,
  reviewer_name (если известен).
- **Hash mismatch handling** — если installer hash изменится (новый minor release),
  re-submit с пометкой «v0.1.X update — hash change only, methodology unchanged».
- **AV vendor false-positive** — если vendor сообщает «detected as malware», это
  ОЖИДАЕМО (motivation submission). Vendor security team вручную проверит
  binary; результат typical 4-14 days для major vendors, 30+ days для Kaspersky.
- **Production EV cert замещение** — после получения EV сертификата от
  Comodo / Sectigo, **повторно подать в каждый vendor** с EV-подписанным
  installer. Большинство vendors автоматически whitelist EV-signed binaries
  от reputable issuer (отпадает необходимость в дальнейших manual submissions).

## Backup plan если timeline затягивается

**Risk:** AV vendor review >4 weeks → блокирует Sprint 5 pilot launch.

**Mitigation tiers:**

1. **Soft launch (preferred):** Sprint 5 pilot customers получают signed
   installer + предупреждение «AV vendor whitelist в процессе, временно может
   срабатывать false positive — добавьте в exception локально». Customer base
   small (5-10), tolerant.

2. **Comodo / Sectigo EV-cert express-track:** ~5-7 рабочих дней с экспресс-
   оплатой. Заменяет необходимость в manual vendor whitelist для большинства
   AV — EV signature пропускают automatic. Cost: ~$300-500/year. Документирован
   в Sprint 3 plan risk mitigation #3.

3. **Sandbox-mode демонстрация:** pilot customer запускает в virtual machine
   или WDAG (Windows Defender Application Guard) — изолированная среда без
   AV blocking. Деградация UX, но не блокирует demo.

## Submission report template

После каждой подачи копируйте в `SUBMISSION_LOG.md`:

```markdown
## YYYY-MM-DD — <Vendor name>

- **Portal:** <URL>
- **Account:** <login email используемый>
- **Ticket ID:** <vendor-specific case id>
- **Installer hash submitted:** SHA-256: <hex>
- **Justification text:** EN / RU (отметить)
- **Expected reply:** <date — обычно portal сам показывает SLA>
- **Notes:** <any quirks, errors during upload, vendor-specific fields filled>
```
