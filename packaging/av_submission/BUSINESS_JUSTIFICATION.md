# Aurora Launch — Business Justification для AV Whitelist Submission

Канонический текст для подачи Aurora Launch на whitelist в antivirus vendor portals.
Используется как блок «Justification» / «Application description» при submission.

---

## English version (для international portals)

### Product overview

**Aurora Launch** — production desktop application для B2B sales forecasting of new
consumer-brand launches based on proxy-brand analogy (econometric / Bayesian
methodology). Target customers: marketing departments of FMCG, pharma, and consumer
brand companies (~1000+ employee enterprise tier).

**Vendor:** Aurora AI (Russia, b2b SaaS)
**Distribution channel:** authenticated installer download from `auroraai.pro`
(HTTPS, customer-specific download tokens). No third-party app stores, no
sideloading distribution.

### Why the installer triggers AV detection

The installer is a **legitimate signed Tauri 2 desktop application** built from
fully open-source-style Rust + TypeScript codebase. Detection signals that may
trigger heuristic AV flagging:

1. **PyInstaller-bundled Python sidecar** — Aurora Launch ships a bundled
   Python interpreter as a sidecar process (`aurora-sidecar.exe`) for the
   econometric / Bayesian (PyMC) modeling pipeline. PyInstaller's `pyz` archive
   format is a known false-positive signal in some AV engines.
2. **Embedded ML / scientific libraries** — numpy, pandas, pymc, arviz, pytensor
   are bundled. These pure-Python+C-extension libraries occasionally trigger
   ML-malware heuristics, especially when bundled via PyInstaller.
3. **Self-signed update binaries (initial releases)** — early Aurora Launch
   releases use local-dev Ed25519 signatures (not yet provisioned with EV code-
   signing certificate from Comodo/Sectigo). Production releases will be EV-
   signed; pre-EV releases use local-dev signing as documented in ADR-002.
4. **Cryptographic primitives** — bundled `ed25519-dalek` (Rust) and `cryptography`
   (Python) for methodology certificate signing. Aurora Launch produces and
   verifies Ed25519 signatures on its own bundle outputs; no encryption of
   third-party data.

### Why Aurora Launch is NOT malicious

1. **No network access beyond explicitly user-initiated update checks.** Aurora
   Launch is a fully offline-capable desktop application. The only network
   activity is the version check against the vendor's published update manifest
   on GitHub Pages (`Ackold26/aurora-launch-updates`) and authenticated
   installer download from `auroraai.pro`. No telemetry of customer data, no
   tracking, no third-party domains.
2. **Local-only data processing.** Customer data (CSV / XLSX time-series sales
   data) is loaded, processed, and stored entirely on the customer's local
   machine. No cloud upload, no SaaS backend for forecasts.
3. **Open methodology, peer-reviewable.** Source code is available under
   private-source license to customers under NDA; methodology references
   (conformal prediction Tibshirani 2019, MCMC Kruschke 2014, MMM Hanssens
   2001) are cited in every output bundle. No proprietary obfuscation.
4. **No process injection, no system modification.** Aurora Launch operates
   solely within its installed directory + user's project directories. No
   registry modifications beyond standard Tauri/MSI/NSIS installer entries.
   No service installation, no startup hooks, no driver loading.
5. **Reproducibility-by-design.** Every Aurora Launch output bundle (`.aurora`
   ZIP container) ships with a `reproduce.py` Python script that reproduces
   the forecast bit-equal from raw input data — auditable artifact chain.
6. **Cryptographic provenance.** Each `.aurora` bundle is signed (Ed25519);
   methodology certificate includes bundle hash + manifest revision + signing
   key fingerprint, allowing third-party verification.

### Vendor contact

- **Technical contact:** anton@auroraai.pro (CEO, Aurora AI)
- **Security inquiries:** security@auroraai.pro
- **Software publisher legal entity:** Aurora AI (Russia)
- **Product URL:** https://auroraai.pro/launch
- **Source code repository (private, NDA-gated):** github.com/Ackold26/aurora-launch
- **Installer download URL:** https://auroraai.pro/launch/download (HTTPS only)
- **Updater feed URL:** https://ackold26.github.io/aurora-launch-updates/

### Installer signatures (current release v0.1.4 — pre-EV)

- **Signature scheme:** Ed25519 (local-dev provenance until EV certificate
  provisioned)
- **Signing key fingerprint:** [to be filled at release time]
- **EV certificate provisioning ETA:** Sprint 5 (Aurora Launch v0.2.x release
  cycle, ~4-6 weeks post-submission)

### Pre-submission disclosure

This submission is the **initial whitelist request** for Aurora Launch desktop
application. Aurora AI commits to:

- Re-submitting updated SHA-256 + Ed25519 fingerprints on every new minor
  release (v0.X.Y bumps)
- Transitioning to EV-signed installer (Comodo / Sectigo) within 6 weeks of
  this submission
- Notifying AV vendor security team of any newly-discovered malware-adjacent
  behavior in third-party dependencies (npm/pip supply chain monitoring active)

---

## Russian version (для российских vendor'ов — Kaspersky, Dr.Web)

### Описание продукта

**Aurora Launch** — настольное приложение корпоративного класса для прогнозирования
продаж нового бренда на основе прокси-бренда (эконометрика, байесовские модели).
Целевая аудитория: маркетинговые отделы крупных FMCG / фарма / потребительских
компаний (1000+ сотрудников).

**Издатель:** Aurora AI (Россия), B2B SaaS
**Канал распространения:** аутентифицированная загрузка установщика
с `auroraai.pro` (HTTPS, customer-specific tokens). Не распространяется через
сторонние магазины приложений, не используется sideloading.

### Почему установщик срабатывает на AV-эвристики

Установщик — это легитимное подписанное Tauri 2 настольное приложение, собранное
из открытого исходного кода (Rust + TypeScript + Python). Возможные триггеры
эвристического обнаружения:

1. **Python-сайдкар, упакованный PyInstaller** — Aurora Launch включает встроенный
   Python-интерпретатор (`aurora-sidecar.exe`) для эконометрических расчётов
   (NumPy, pandas, PyMC). PyInstaller `pyz`-архивы известны как источник false-
   positive у некоторых AV-движков.
2. **Встроенные ML / научные библиотеки** — numpy, pandas, pymc, arviz могут
   срабатывать на ML-malware heuristics при упаковке PyInstaller.
3. **Self-signed обновления (ранние релизы)** — текущая версия Aurora Launch
   использует локально-сгенерированные ключи Ed25519 (local-dev provenance).
   Переход на EV-сертификат Comodo / Sectigo запланирован в течение 6 недель.
4. **Криптографические примитивы** — `ed25519-dalek` (Rust), `cryptography`
   (Python). Aurora Launch подписывает только собственные выходные бандлы; не
   шифрует данные клиента.

### Aurora Launch — не вредоносное ПО

1. **Сетевая активность строго ограничена.** Только: (а) запрос версии
   обновления на GitHub Pages (`Ackold26/aurora-launch-updates`), (б) загрузка
   установщика с `auroraai.pro`. Нет телеметрии данных клиента, нет трекинга,
   нет обращений к сторонним доменам.
2. **Локальная обработка данных.** Файлы клиента (CSV / XLSX с временными
   рядами продаж) обрабатываются и хранятся только локально. Нет облачной
   выгрузки, нет SaaS-бэкенда для прогнозов.
3. **Открытая методология.** Исходный код доступен клиентам под NDA. Методология
   (conformal prediction, MCMC, MMM) цитируется в каждом выходном бандле.
4. **Никакой инъекции в процессы, никакой системной модификации.** Работает
   только внутри своей установочной директории и пользовательских проектов.
   Никаких записей в реестр сверх стандартных MSI/NSIS-установщиков.
   Не устанавливает службы, не загружает драйверы, не модифицирует автозапуск.
5. **Воспроизводимость встроена в дизайн.** Каждый выходной бандл `.aurora`
   содержит `reproduce.py` — Python-скрипт, побитно воспроизводящий прогноз
   из исходных данных (полная аудиторская цепочка артефактов).
6. **Криптографический provenance.** Каждый `.aurora` бандл подписан
   (Ed25519); сертификат методологии содержит хэш бандла, ревизию манифеста,
   отпечаток подписывающего ключа — позволяет внешнюю верификацию.

### Контакты

- **Технический контакт:** anton@auroraai.pro (CEO, Aurora AI)
- **Безопасность:** security@auroraai.pro
- **Юридическое лицо издателя:** Aurora AI (Россия)
- **URL продукта:** https://auroraai.pro/launch
- **Репозиторий (приватный, NDA):** github.com/Ackold26/aurora-launch
- **URL загрузки установщика:** https://auroraai.pro/launch/download (HTTPS)
- **URL канала обновлений:** https://ackold26.github.io/aurora-launch-updates/

### Подписи установщика (текущий релиз v0.1.4, pre-EV)

- **Схема подписи:** Ed25519 (local-dev provenance до получения EV-сертификата)
- **Отпечаток ключа подписи:** [заполняется при релизе]
- **Срок получения EV-сертификата:** Sprint 5 (~4-6 недель)

### Pre-submission disclosure

Это **первичная заявка на whitelist**. Aurora AI обязуется:

- Повторно подавать обновлённые SHA-256 + Ed25519 отпечатки при каждом minor-релизе
- Перейти на EV-подпись (Comodo / Sectigo) в течение 6 недель
- Уведомлять security-команду AV-вендора о любых новых уязвимостях
  в сторонних зависимостях (мониторинг supply chain npm/pip активирован)
