# Aurora Launch — Kaspersky Whitelist Submission

**Вендор:** Kaspersky Lab (Москва, Россия)
**Покрытие:** Kaspersky Security Network (KSN) ~400M endpoints глобально,
~70% российского enterprise-рынка (Kaspersky Endpoint Security for Business) +
consumer (Kaspersky Internet Security / Total Security)
**Приоритет для Aurora:** Kaspersky локально в России, поддерживает русскоязычные
submissions, имеет ускоренный SLA для российских software publishers.

---

## Порталы для подачи

| Канал | URL | Назначение |
|---|---|---|
| VirusDesk (RU) | https://virusdesk.kaspersky.ru/ | **Основной.** Русскоязычный портал false-positive submissions |
| VirusDesk (EN) | https://virusdesk.kaspersky.com/ | Резервный англоязычный |
| OpenTIP | https://opentip.kaspersky.com/ | Threat Intelligence Portal — reputation lookup |
| KBWP (whitelist email) | whitelist@kaspersky.com | Kaspersky Business Whitelisting Program — proactive |
| Enterprise RU | enterprise@kaspersky.com | B2B Russian inquiries, escalation |
| KSN whitelisting | https://company.kaspersky.com/ru/threat-intelligence/ | Vendor whitelisting программа |

**Рекомендация:** подавать через **virusdesk.kaspersky.ru** (RU portal) как
primary channel — ожидаемый SLA быстрее для российских publisher'ов, чем
через international portal. Параллельно — email в KBWP (proactive program).

---

## Требования к аккаунту

- **VirusDesk** — бесплатно, регистрация аккаунта не обязательна для разовой
  подачи. Рекомендуется зарегистрироваться для отслеживания case history.
- **Threat Intelligence Portal** — требует Kaspersky Business аккаунт
  для расширенного функционала (file reputation API, bulk lookup).
- **Russian-language portal** — иногда требует phone-verified Russian account
  для submission. Подготовить: russian mobile number (соотнести с
  anton@auroraai.pro auth).
- **KBWP** — email-based, аккаунт не требуется, достаточно email из
  корпоративного домена.

---

## Обязательные артефакты

- [ ] Installer file — `aurora-launch-setup-v0.1.4.exe` (~[РАЗМЕР_МБ] МБ,
      лимит VirusDesk 256 МБ — комфортный для Aurora Launch)
- [ ] SHA-256 хэш установщика (обязателен)
- [ ] MD5 хэш (опционально, VirusDesk принимает оба)
- [ ] Описание продукта ~300 символов (краткое summary)
- [ ] Полное обоснование (вставить RU-раздел из `BUSINESS_JUSTIFICATION.md`)
- [ ] Контактный email: `anton@auroraai.pro`
- [ ] Юридическое лицо издателя: Aurora AI (Россия), ИНН [TBD], ОГРН [TBD]
- [ ] Ed25519 отпечаток ключа подписи: [заполняется при релизе]

---

## Заполнение формы VirusDesk (русскоязычный портал)

| Поле | Значение |
|---|---|
| **Тип файла** | Приложение для Windows |
| **Файл** | `aurora-launch-setup-v0.1.4.exe` (upload) |
| **Хэш файла** | SHA-256: `<HASH>` |
| **Причина обращения** | Ложное срабатывание (legitimate приложение) |
| **Подробное описание** | *(вставить RU-секцию из BUSINESS_JUSTIFICATION.md)* |
| **Издатель** | Aurora AI |
| **Контактный email** | anton@auroraai.pro |
| **Согласие на обработку персональных данных** | Отметить (российский аналог GDPR) |

---

## Kaspersky Business Whitelisting Program (KBWP)

**KBWP** — отдельная программа для российских и международных software vendors,
позволяющая proactive whitelisting ДО первого detection event.

**Преимущества:**
- Ускоренный SLA через локализованный security team Kaspersky
- Переключает бинарь на KSN-статус «trusted publisher» — последующие релизы
  под тем же publisher identity проходят автоматически быстрее
- Особо ценно для российских B2B-продуктов: клиенты Aurora Launch (enterprise
  pharma / FMCG) типично используют Kaspersky Endpoint Security

**Подача:** email на `whitelist@kaspersky.com` — использовать шаблон ниже.
**Срок:** ожидаемо 7-14 рабочих дней (обычно faster для российских компаний).

---

## Ожидаемые сроки рассмотрения

| Этап | Типичный срок |
|---|---|
| VirusDesk automated triage | 24-48 часов |
| Manual analyst review | 5-10 рабочих дней |
| KSN whitelist propagation | 24-72 часов после решения |
| **Итого (RU portal)** | **7-14 дней** (обычно, для российских publishers) |
| **Итого (international)** | 14-30 дней (типично) |
| KBWP proactive program | 7-14 рабочих дней |

---

## Шаблон email-заявки — KBWP / эскалация

```
Subject (RU): Aurora Launch v0.1.4 — Запрос whitelist [Ticket #XXXX]
Subject (EN): Aurora Launch v0.1.4 — Whitelist Inquiry [Case #XXXX]

Уважаемая команда безопасности Kaspersky,

Обращаюсь с запросом о внесении в whitelist (или со статусом ложного
срабатывания) для установщика Aurora Launch v0.1.4, поданного [ДАТА],
ссылочный тикет #XXXX.

Идентификаторы файла:
  - Имя файла: aurora-launch-setup-v0.1.4.exe
  - SHA-256: <HASH>
  - Размер: ~[РАЗМЕР_МБ] МБ
  - Издатель: Aurora AI (Россия), ИНН [TBD]

Обоснование (полный текст):
[вставить RU-секцию BUSINESS_JUSTIFICATION.md полностью]

Aurora Launch готовится к pilot-запуску с корпоративными клиентами
через ~6 недель. Подтверждение whitelist-статуса позволит избежать
false-positive блокировок у клиентов, использующих Kaspersky Endpoint
Security for Business.

С уважением,
Антон Коваленко (CEO, Aurora AI)
anton@auroraai.pro
```

---

## Протокол повторной подачи

Каждый новый хэш (новый minor release) требует отдельной submission.
VirusDesk хранит case history по publisher info — в поле «Комментарий»
указывать предыдущий ticket для контекста:

```
Предыдущий тикет: #XXXX (v0.1.3, дата [ДАТА]).
Данная заявка — обновление хэша для v0.1.4, методология не изменилась.
```

---

## Известные проблемы и решения

**«Файл уже проанализирован — без обнаружения»**
Означает: в KSN отсутствует сигнатура, возможен случайный ML-classifier fluke.
Всё равно подавать — proactive whitelisting предотвращает future false-positive
при добавлении новых ML-правил в KSN.

**«Подозрительная сигнатура PyInstaller»**
Распространённая ситуация. В justification указывать:
> «Aurora Launch использует PyInstaller для упаковки Python-сайдкара
> (эконометрические расчёты NumPy/PyMC), что является industry-standard
> подходом для распространения Python-приложений. PyInstaller pyz-архивы
> известны как источник false-positive у ряда AV-движков — их происхождение
> документировано в открытой документации PyInstaller.»

**«Local-dev signature insufficient»**
Kaspersky enterprise review строже по signature provenance.
Объяснить: «local-dev provenance — переходное состояние, EV-сертификат
от Comodo/Sectigo запланирован к получению в течение 6 недель».

**Запрос документов юридического лица**
Kaspersky может запросить ИНН, ОГРН для verified-publisher status в KSN.
Подготовить заранее — это ускоряет финальное решение.

---

## После получения EV-сертификата

После получения EV cert от Comodo/Sectigo повторно подать через KBWP
с обновлённой signature info — это переключает Aurora Launch на automatic
whitelist через KSN reputation (последующие релизы проходят без manual
submission).

---

## Дополнительные заметки

- **KSN reach:** ~400M endpoints глобально, ~70% российского enterprise-рынка —
  critical для Aurora Launch pilot customers (FMCG / pharma enterprise Russia).
- **Параллельная подача:** Kaspersky submission не зависит от других вендоров
  (Symantec / McAfee / Avast / Defender) — подавать в один день.
- **Логирование:** после подачи записать ticket ID в `SUBMISSION_LOG.md`
  согласно шаблону из `README.md`.
