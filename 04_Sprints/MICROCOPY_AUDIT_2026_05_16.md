# Microcopy Audit — Aurora Launch — 2026-05-16

## Stats

- **Total keys audited:** 112 (ru.json) + 14 hardcoded svelte strings
- **OK (no change):** 74
- **IMPROVE (minor tone):** 21
- **REWRITE (full sentence):** 17
- **Skipped per scope exclusion:** Phase 1.A / 2.A / 2.D / 2.D.2 / Settings / Palette actions

---

## ru.json — Key-level audit

| Key | ДО | ПОСЛЕ | Tier |
|---|---|---|---|
| `welcome.subtitle` | Bayesian-прогноз для новых брендов на основе proxy-передачи | Прогноз продаж нового бренда на основе реальных данных похожего игрока рынка | 🔴 REWRITE |
| `welcome.feature.forecast` | Прогноз на 12/26/52 недели с conformal-интервалами | Прогноз на 12, 26 или 52 недели с доверительным интервалом | 🟡 IMPROVE |
| `welcome.feature.cert` | Сертификат методологии с Ed25519 подписью | Сертификат методологии с криптографической подписью | 🟡 IMPROVE |
| `wizard.step.proxy` | Выбор proxy | Выбор прокси-бренда | 🟡 IMPROVE |
| `wizard.step.anchors` | Якорные параметры | Параметры запуска | 🟡 IMPROVE |
| `wizard.unsaved_changes` | Есть несохранённые изменения | Изменения не сохранены | 🟡 IMPROVE |
| `verdict.explainer` | Похожесть рассчитана по 8 измерениям с весовыми коэффициентами | Оценка похожести рассчитана по 8 характеристикам с учётом их значимости | 🟡 IMPROVE |
| `compare.title` | Сравнение proxy | Сравнение прокси-брендов | 🟡 IMPROVE |
| `modeBadge.pure_transfer.explanation` | Прогноз построен через scaled proxy posterior + recipient anchors. Никаких compromises — это первичный сценарий Launch Planner. | Прогноз построен на данных прокси-бренда с учётом ваших параметров запуска. Это основной режим Aurora Launch — максимальная точность без компромиссов. | 🔴 REWRITE |
| `modeBadge.transfer_bias.explanation` | Pure Transfer + проверка observed vs. predicted на доступных recipient точках. Если bias >30%, в результате будет warning. | Базовый прогноз дополнен проверкой на имеющихся данных вашего бренда. Если расхождение превышает 30%, Aurora выдаст предупреждение. | 🔴 REWRITE |
| `modeBadge.ols_priors.explanation` | Текущая версия (v0.1.0-rc2) использует Pure Transfer с tighter similarity inflation. Полная OLS-регрессия с proxy posterior priors реализуется в v0.1.1. CI bands conservative — прогноз можно использовать. | Aurora использует прогноз на основе прокси-бренда. Расширенный режим регрессии появится в следующем обновлении. Доверительный интервал немного шире — прогноз пригоден для принятия решений. | 🔴 REWRITE |
| `modeBadge.bayesian_priors.explanation` | Текущая версия (v0.1.0-rc2) использует Pure Transfer. Полная Bayesian-регрессия с informative priors реализуется в v0.1.1. Прогноз надёжен, но не максимально точен для большого recipient dataset. | Aurora строит прогноз на основе прокси-бренда. Полный байесовский режим с вашими историческими данными появится в следующем обновлении. Прогноз надёжен — точность вырастет с обновлением. | 🔴 REWRITE |
| `modeBadge.mode_identifier_label` | Mode identifier: | Идентификатор режима: | 🟡 IMPROVE |
| `trustScore.verdict_label` | Вердикт | Оценка | 🟡 IMPROVE |
| `trustScore.aria_score` | Trust score: {score} из 100 | Уровень доверия: {score} из 100 | 🟡 IMPROVE |
| `trustScore.diagnostics_title` | Диагностика (Expert mode) | Расширенная диагностика | 🟡 IMPROVE |
| `trustScore.tier.unconfirmed` | Не подтверждён | Пока не рассчитан | 🟡 IMPROVE |
| `onboarding.tutorial.slide2.body` | Принимаем XLSX из Эконометрики, .aurora-бандлы из Data Studio, или подключение к корпоративным источникам. | Загружайте XLSX из Эконометрики, файлы .aurora из Aurora Data Studio или подключайтесь к корпоративным данным. | 🔴 REWRITE |
| `onboarding.tutorial.slide3.body` | Алгоритм даёт точечный прогноз + доверительный интервал. Шкала «Доверие» оценивает надёжность одним числом (0–100). | Aurora рассчитывает точечный прогноз и диапазон возможных значений. Шкала «Доверие» оценивает надёжность одним числом от 0 до 100. | 🔴 REWRITE |
| `onboarding.tutorial.slide4.body` | Один клик — три сценария: пессимистичный, базовый, оптимистичный. Эксперт-режим разворачивает 6 параметров чувствительности. | Один клик — три сценария: пессимистичный, базовый, оптимистичный. Расширенный режим открывает 6 дополнительных параметров. | 🔴 REWRITE |
| `palette.nav.inspector.desc` | Просмотр содержимого .aurora bundle | Просмотр содержимого файла проекта | 🟡 IMPROVE |
| `perf.cold_start` | Запуск {ms} мс | Запуск за {ms} мс | 🟡 IMPROVE |
| `errors.bundle_not_found` | Файл не найден: {path} | Не нашли файл: {path} | 🟡 IMPROVE |
| `errors.bundle_format` | Не удалось разобрать .aurora-файл: {reason} | Не удалось прочитать файл проекта: {reason} | 🟡 IMPROVE |
| `errors.bundle_integrity` | Ошибка целостности: {reason} | Файл повреждён или изменён: {reason} | 🟡 IMPROVE |
| `errors.compare_failed` | Ошибка сравнения: {reason} | Не удалось сравнить версии: {reason} | 🟡 IMPROVE |
| `history.compare_error` | Ошибка сравнения: {reason} | Не удалось сравнить версии: {reason} | 🟡 IMPROVE |
| `cert.bundle_hash` | Хеш пакета | Контрольная сумма файла | 🟡 IMPROVE |
| `forecast.completed` | Прогноз готов за {seconds, plural, ...} | OK — уже хорошо написано | ✅ OK |

---

## Hardcoded svelte strings — audit

| Файл | ДО | ПОСЛЕ | Tier |
|---|---|---|---|
| `+page.svelte` (welcome) | 60 секунд от установки до первого прогноза. Synthetic FMCG bundle с заранее посчитанной похожестью и прогнозом. | 60 секунд от установки до первого прогноза — готовый пример FMCG-бренда с рассчитанной похожестью и прогнозом продаж. | 🟡 IMPROVE |
| `+page.svelte` (welcome) | Открыть существующий .aurora файл из предыдущей работы или из Aurora Data Studio. | Открыть файл проекта .aurora из предыдущей работы или из Aurora Data Studio. | 🟡 IMPROVE |
| `+page.svelte` (welcome) | Запустить мастер — 7 шагов: импорт → сопоставление → proxy → похожесть → якоря → прогноз → сертификат. | Создать новый прогноз за 7 шагов: импорт данных → сопоставление → прокси-бренд → похожесть → параметры → прогноз → сертификат. | 🔴 REWRITE |
| `wizard/+page.svelte` toast | Файл распознан: {adapter_id} | Файл загружен ({adapter_id}) | 🟡 IMPROVE |
| `wizard/+page.svelte` toast | Bundle сохранён | Файл проекта сохранён | 🟡 IMPROVE |
| `wizard/+page.svelte` toast | Сохранить bundle Aurora Launch (dialog title) | Сохранить файл проекта Aurora Launch | 🟡 IMPROVE |
| `wizard/+page.svelte` toast | Ошибка сохранения | Не удалось сохранить файл | 🟡 IMPROVE |
| `wizard/+page.svelte` toast | Сначала дождитесь окончания прогноза | Дождитесь завершения прогноза | 🟡 IMPROVE |
| `wizard/+page.svelte` UI | Мастер прогноза (h1 visually-hidden) | Создание прогноза | 🟡 IMPROVE |
| `wizard/+page.svelte` step 0 | Импортируйте DSM/Mediascope файлы или используйте Aurora Data Studio экспорт. | Загрузите файл DSM/Mediascope или экспорт из Aurora Data Studio. | 🟡 IMPROVE |
| `wizard/+page.svelte` step 0 | Choose file (button EN) | Выбрать файл | 🔴 REWRITE (EN→RU) |
| `wizard/+page.svelte` step 0 | Adapter: {id} (label) | Формат: {id} | 🟡 IMPROVE |
| `wizard/+page.svelte` step 1 | Сначала импортируйте файл на предыдущем шаге, чтобы Aurora узнала его структуру. | Сначала загрузите файл на шаге 1 — Aurora определит его структуру автоматически. | 🔴 REWRITE |
| `wizard/+page.svelte` step 3 | Compute (button EN) | Рассчитать похожесть | 🔴 REWRITE (EN→RU) |
| `wizard/+page.svelte` step 5 | Start forecast (button EN) | Запустить прогноз | 🔴 REWRITE (EN→RU) |
| `wizard/+page.svelte` cert step | Methodology Cert закрепляет reproducibility — Ed25519 подпись от Aurora AI. | Сертификат методологии фиксирует параметры прогноза — Aurora AI подписывает его криптографически. | 🔴 REWRITE |
| `wizard/+page.svelte` cert step | Bundle позволит Inspector → M-09 «Воспроизвести в Python» работать с реальным forecast.json. | Сохраните файл проекта, чтобы проверить расчёт в Python или вернуться к нему позже. | 🔴 REWRITE |
| `wizard/+page.svelte` cert step | ✓ Сертификат подписан (dev режим — local key) | ✓ Сертификат подписан | 🟡 IMPROVE |
| `wizard/+page.svelte` cert step | ✓ Bundle сохранён: {path} | ✓ Файл проекта сохранён: {path} | 🟡 IMPROVE |
| `wizard/+page.svelte` toast | Сеанс восстановлен / Продолжаем с шага {N} из {total} | Продолжаем с того места — шаг {N} из {total} | 🟡 IMPROVE |
| `+layout.svelte` header | Сохранить bundle (Ctrl+S) (aria-label) | Сохранить файл проекта (Ctrl+S) | 🟡 IMPROVE |
| `+layout.svelte` header rev tooltip | Текущая ревизия открытого bundle. Monotonic счётчик — растёт на 1 при каждом сохранении. Защищает от потери чужих правок в multi-process сценариях. | Версия файла проекта. Увеличивается при каждом сохранении — защищает от конфликтов при параллельной работе. | 🔴 REWRITE |
| `+layout.svelte` toast save | Сохранить Aurora bundle (dialog title) | Сохранить файл проекта | 🟡 IMPROVE |
| `HandshakeIncompatibleModal` | Sidecar (Python) не подходит к текущему shell (Rust). | Внутренний сервис расчётов не совместим с этой версией Aurora. | 🔴 REWRITE |
| `inspector/+page.svelte` | Не удалось сгенерировать объяснение: {err} | Не удалось подготовить объяснение прогноза: {err} | 🟡 IMPROVE |
| `inspector/+page.svelte` modal | Сгенерировать Python скрипт что воспроизведёт этот прогноз бит-в-бит (title) | Воспроизвести прогноз в Python | 🟡 IMPROVE (already OK as button label, title is redundant) |
| `inspector/+page.svelte` | anchors и план затрат пока заглушки — для точного воспроизведения подставьте свои значения. Bit-exact wiring придёт в v0.1.1. | параметры запуска и план медиа пока приближённые — скорректируйте их вручную. Точное воспроизведение появится в следующем обновлении. | 🔴 REWRITE |
| `ProxyPickerCard` | errorMsg (onMount catch) | Не удалось загрузить список примеров. Попробуйте перезапустить приложение. | 🟡 IMPROVE |

---

## Не тронутые области

- Phase 1.A `NotificationBanner` / wizard recovery texts — already polished
- Phase 2.A license empathetic messages
- Phase 2.D.2 telemetry tier texts
- Phase 2.D refresh consent (`refresh.optin.*`, `refresh.settings.*`) — recently rewritten for 152-FZ
- `settings.*` labels — short, clear
- `palette.*` command actions — jargon-free short labels
- `cert.*` cryptographic field names (Ed25519, подпись, открытый ключ) — customer must know these
- `verdict.High/Medium/Low/Insufficient` — brand vocabulary, keep as-is
- Test descriptions, comments, docstrings — not display strings
- EN-only strings in dev/internal contexts (inspector audit tab placeholder, `No similarity entry в bundle`)
