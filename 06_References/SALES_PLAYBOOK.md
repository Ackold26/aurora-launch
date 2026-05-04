# Aurora Launch - Sales Playbook

**Status:** Accepted (S010 closed 2026-05-04)
**Sprint context:** Sprint B6 + commercial ship
**Owner:** Антон (sales)
**Coordinated с:** S008 PILOT_CLIENT_PLAN + S009 PRICING_TIERS + S006 REPORT_SECTIONS_SPEC

## Контекст

Aurora Launch sales = solo (Антон), РФ-рынок, premium-tier subscription (1.5-3.5M ₽/год).

**Sales motion priority (per ADR launch-as-econometrica-upsell):**

1. **PRIMARY (Phase B первый сезон):** upsell к существующим клиентам Aurora Эконометрика. Клиент уже видел качество, доверяет математике, готов к next step (новый запуск). Conversion rates ожидаемо высокие (50%+ в первый сезон).

2. **SECONDARY (Phase B+ stabilization):** warm intros от existing customers - peer recommendations внутри industry segments.

3. **TERTIARY (Phase C+):** cold outreach (Pharma / FMCG broader market) - после стабилизации первичного канала + наличия ≥3 case studies.

Этот документ финализирует:

1. **Outreach channels** + templates (cold email + LinkedIn DM + warm intros)
2. **Discovery call flow** (30 min) + qualifying questions
3. **Demo flow** (45-60 min) с sample dataset
4. **Pilot kickoff checklist** (post-discovery, pre-pilot)
5. **Conversion / contract** flow
6. **Post-conversion onboarding** (kickoff session + training + quarterly reviews)
7. **Sales operations** (CRM, calendar, follow-up cadences)

---

## 1. Sales Funnel Overview

```
Cold Outreach → Discovery Call (30 min) → Demo (45-60 min) →
Pilot Offer → Pilot Kickoff (1.5h) → Pilot Execution (12 weeks) →
Conversion Offer → Subscription Contract → Onboarding → Quarterly Reviews
```

**Conversion benchmarks (Phase B initial):**
- Outreach → Discovery: 5-10% response rate
- Discovery → Demo: 40-60% (qualified leads)
- Demo → Pilot offer: 30-50% (interested + qualifying signals)
- Pilot kickoff → Pilot completion: 80%+ (pilot drops rare)
- Pilot completion → Conversion: 60-80% (Path B free pilot is high-conversion)

**Net cold-to-conversion:** ~3-5% expected. ~30-50 outreaches needed для 1 conversion. Phase B target: 3-5 conversions Q1 = 100-200 outreaches.

---

## 2. Outreach Channels + Templates

### 2.1 Channel Mix

**Primary channels (Phase B первый сезон, in priority order):**

1. **Эконометрика upsell conversation (highest conversion - 50%+)** - existing Aurora Эконометрика clients завершают свой текущий проект и обсуждают next step. "У вас планируется новый запуск? Aurora Launch - естественное расширение того, что вы уже видели в Эконометрике. Те же команды, та же методология, те же отчёты."
2. **Warm intros от existing customers** - peer recommendations within industry segments (например, Materia Medica → ATC peer brand).
3. **Cold email + LinkedIn DM** - secondary channels, активируются после Sprint B6 ship + ≥1 case study.
4. **Industry events** - АКАР, IAA Russia, FMCG conferences, pharma events (Антон attends 2-4 events/year).

**Phase C+ (после стабилизации):** cold outreach становится primary через broader market entry.

**Secondary (Phase C+):**
- Content marketing (blog posts, case studies, methodology articles)
- SEO (auroraai.pro/launch landing)
- Paid ads (Yandex Direct - test budget 50K/мес для разных segments)
- Webinars (methodology deep-dives, ~quarterly)

### 2.1.1 Эконометрика Upsell Conversation (PRIMARY channel)

**Контекст:** клиент завершает свой Эконометрика-проект (например quarterly review session) - естественный момент для upsell-разговора про Aurora Launch.

**Template (in-session conversation, не email):**

> "Спасибо за работу над [текущий проект]. Видим что у вас в pipeline новый запуск [бренд / продукт] в [период] - правильно?
>
> Aurora Launch - расширение того, что вы уже видели в Эконометрике, для нового бренда без исторических данных. Используется индивидуально подобранный proxy-бренд + recipient anchors. Methodology Certificate в том же формате что вы знаете.
>
> Ключевая интеграция: ваш текущий Эконометрика-проект [бренд] может стать proxy для нового запуска - lossless transfer adstock + hill параметров. Не нужно собирать новые DSM/Mediascope данные.
>
> Subscription 1.5-3M ₽/год + 20-40h consulting. Pilot первого launch FREE с case-study consent.
>
> Готовы рассмотреть на следующей сессии?"

**Follow-up email (через 24h):**

```
Здравствуйте, [имя],

Спасибо за разговор. Прикрепляю one-pager Aurora Launch + Methodology
Certificate sample.

Если интересно попробовать на пилоте вашего следующего запуска:
1. NDA + pilot agreement (можем подписать на этой неделе)
2. Kickoff session 1.5h - подбор proxy-бренда (логично использовать
   ваш текущий Эконометрика-проект)
3. 12-week pilot, free, с case-study consent

[Calendly: kickoff slot]

С уважением,
Антон
```

### 2.2 Cold Email Template (Russian) - SECONDARY channel

**ВАЖНО:** cold outreach = secondary channel. Primary - Эконометрика upsell conversation (раздел 2.1.1 ниже). Cold templates ниже activate после стабилизации primary канала + наличия ≥1 case study.

**Subject lines для cold (A/B testing):**
- "Прогноз запуска [бренд] - 2 недели вместо 3 месяцев"
- "MMM-прогноз для нового бренда без исторических данных"
- "Как [конкурент] запускался в вашей категории - методология Aurora"

**Email body (Pharma OTC variant):**

```
Здравствуйте, [имя],

Запускаете новый OTC-бренд в [категория, например: противовирусные]?

Aurora Launch генерирует sales forecast для нового бренда без
исторических данных - используя индивидуально подобранный прокси-бренд
в той же ATC-категории + recipient anchors.

В отличие от Nielsen BASES (5-15M ₽/launch) или Kantar/Ipsos консалтинга
(1-3M ₽/проект), Aurora Launch - subscription 1.5-3M ₽/год с unlimited
launches + 20-40h consulting hours.

Формат прогноза: 8-секционный отчёт + Methodology Certificate PDF
(аудит-готовый документ для CFO).

Готов на 30-минутный discovery call показать как Aurora работает с
пилотным проектом для вашего бренда.

[Calendly link к discovery slot]

С уважением,
Антон Сипович
Founder, Aurora AI
ackold@yandex.ru
auroraai.pro
```

**Email body (FMCG variant):**

```
Здравствуйте, [имя],

В FMCG-снэках доступ к Mediascope TV + DSM Retail data позволяет 
прогнозировать запуск нового бренда с similarity-based transfer от 
established competitor.

Aurora Launch финализирует прогноз за 2 недели:
- Подбор прокси-бренда (similarity по 6 dimensions: категория, 
  ценовой tier, размер, дистрибуция, медиа-зрелость, lifecycle)
- Recipient anchors (market_size, planned_share, distribution_target, 
  pricing_index)
- 12/26/52-week sales forecast с 95% CI
- Уверенность отчёта: Gold/Silver/Bronze

Subscription 1.5-3M ₽/год + 20-40h consulting hours = unlimited 
launches per год.

Готов на 30-минутный discovery call для вашего следующего запуска.

[Calendly link]

С уважением,
Антон Сипович
auroraai.pro
```

**Personalization tokens (always fill):**
- [имя] - first name
- [категория] - specific category знание (research before send)
- [бренд] - if known launching brand from press / LinkedIn

**Best practices:**
- Send Tuesday-Thursday 10-12 AM Moscow time
- Subject line max 50 chars
- Body 100-150 words максимум
- Calendly link в каждом outreach (low friction)
- Follow-up sequence (Section 2.5)

### 2.3 LinkedIn DM Template

**Connection request с note (300 chars):**

```
Здравствуйте, [имя]. Aurora AI запускает MMM-прогнозы для нового
бренда без исторических данных - через similarity-based transfer
от прокси-бренда. В РФ нет аналогов в этом ценовом сегменте.
Готов на 30-мин звонок если запускаете новый продукт.
```

**Follow-up DM after connection accepted:**

```
Спасибо за коннект! 

Aurora Launch - subscription tool для launch forecasting. Использует 
DSM + Mediascope (через вашу подписку) для подбора прокси-бренда 
и переноса структурных параметров (adstock, hill saturation, 
сезонность). Magnitudes калибруются от ваших recipient anchors.

Делаем pilot first launch FREE с case-study consent.

[Calendly: 30-мин discovery call]

Если у вас планируется запуск в 2-6 месяцев - давайте поговорим.
```

### 2.4 Warm Intro Template

**Email к existing customer asking for intro:**

```
Привет, [имя],

Знаешь кого-то в [компания / категория] кто запускает новый бренд?

Aurora Launch специализируется на forecasting для new brand launches 
без historical data. Pilot first launch бесплатно с case-study consent.

Если знаешь подходящий контакт - готов сделать intro? Email или 
LinkedIn DM - что удобнее.

Спасибо!
Антон
```

### 2.5 Follow-up Cadence

**Cold email sequence:**
- Day 0: Initial outreach
- Day 5: Soft follow-up "напоминаю про возможность discovery call"
- Day 12: Final follow-up "если не подходит - дайте знать чтобы не беспокоить"
- Day 30: Mark "no response" - re-attempt в 6 месяцев

**LinkedIn:**
- Day 0: Connection request
- Day 3 (если accepted): DM с pitch
- Day 10: DM follow-up если no response
- Day 20: Soft engagement (like a post, comment) - не direct sell

**После discovery call:**
- Same day: thank-you email + summary + Calendly link для demo
- Day 3: nudge если demo не scheduled
- Day 7: re-engagement if no demo booking

---

## 3. Discovery Call (30 min)

### 3.1 Pre-Call Preparation

Антон researches prospect:
- LinkedIn profile (current role, tenure, prior brands)
- Company news (recent launches, funding, expansions)
- Category context (current market leaders, challengers, recent launches)
- Identify likely pain points

### 3.2 Discovery Call Structure

**Opening (5 min):**
- Брief intro Антон + Aurora AI
- Mutual time confirmation (30 min hard stop)
- "Цель сегодня: понять ваш контекст + если fit - schedule full demo"

**Discovery questions (15 min):**

Use S008 PILOT_CLIENT_PLAN Section 4 questions, prioritized:
1. Запуск планируется в 2-6 месяцев? (timing fit)
2. Это новый бренд / SKU? (use case fit)
3. Бренд имеет history продаж 12+ месяцев? (qualifying)
4. Подписки DSM / Mediascope? (data path)
5. Established competitor с history в категории? (proxy availability)
6. Pre-test creative данные есть? (Aurora boost)
7. Decision-makers по procurement? (sales process)

**Aurora pitch (5 min):**

Brief framing:
- "Aurora Launch - subscription, не one-time consulting"
- "Methodology прозрачна - показываем similarity, uncertainty, transfer caveats explicit"
- "В отличие от Nielsen BASES (5-15M / launch), unlimited launches per год"
- "Pilot first launch FREE с case-study consent - можем начать без commitment"

**Next steps (5 min):**
- Если fit confirmed → schedule full demo (45-60 min)
- Если budget concerns → offer Pilot Path B детали
- Если timing concern → "выйду на связь когда запуск приближается"
- Если disqualified (use case wrong) → handoff к Aurora Optimize OR friendly cancel

### 3.3 Discovery Call Outcome Categorization

**Hot (10-20% of calls):** schedule demo within 7 days, pilot offer ready
**Warm (30-40%):** follow-up in 1-3 months, send case study materials, stay in touch
**Cold (30-40%):** no fit currently, mark for 6-month re-attempt
**Disqualified (10-20%):** wrong use case, refer к alternative (Aurora Optimize, in-house solution, или нет fit)

---

## 4. Demo (45-60 min)

### 4.1 Pre-Demo Preparation

**Primary demo path: real client data** (per ADR launch-demo-strategy-real-client-data-first):
- Если prospect = existing Эконометрика-клиент → демо на ЕГО собственном проекте (perfect fit, максимальный impact)
- Если prospect = warm intro → запросить у refer'ера согласие показать его данные (anonymized brand name)
- Если prospect = cold + категория совпадает с существующим case study → анонимизированная копия real проекта

**Secondary demo path: synthetic** (только когда нужен):
- Cold outreach к новой категории без case study
- Конференция / контент-маркетинг
- 2-3 дня работы (lightweight, не неделя)
- ОБЯЗАТЕЛЬНО помечать "Demo data" в углу слайдов - не выдавать за реальный кейс

Антон prepares:
- Real client project (ОПТИМАЛЬНО) или anonymized real или synthetic
- Recipient anchors filled-in example matching prospect's launch context
- Similarity radar pre-computed (showing realistic verdict for prospect's likely scenario)
- Sample Methodology Certificate PDF (printed if in-person)

### 4.2 Demo Flow

**Opening (5 min):**
- Recap discovery call findings
- Confirm what they want to see (full flow vs specific feature)

**Live forecast generation (25-30 min):**

1. **Project setup (3 min)** - new project, recipient brand metadata
2. **Proxy selection (8 min)** - upload DSM + Mediascope data, fill 6 dimensions, similarity radar live update, verdict tier displayed
3. **Recipient anchors (5 min)** - form filling demo, semantic validator real-time feedback
4. **Transfer validation (4 min)** - prior predictive checks, sensitivity analysis, tier badge confirmation
5. **Training (2 min)** - streaming MCMC trace UI, ~30s wait
6. **Forecast generation (3 min)** - 12/26/52 cone visualization, decomposition stacked area
7. **Report generation (3 min)** - PPTX/HTML/XLSX/PDF Methodology Certificate sample

**Q&A + objections (10-15 min):**

Common objections + responses:

**"Forecast accuracy?"**
> "MAPE 12% типично для Medium verdict (95% CI). Aurora explicitly shows uncertainty decomposition - 30% proxy / 40% transfer / 15% anchor / 15% sampling. Нет иллюзий точности."

**"А если прокси не идеальный?"**
> "Aurora блокирует forecast generation если similarity < 0.50 (Insufficient verdict). Better to admit data insufficient than generate misleading forecast. Также есть multi-proxy mode для volatile categories."

**"Сравнение с Nielsen BASES?"**
> "BASES 5-15M ₽ per launch одноразовый. Aurora 1.5-3M ₽/год = unlimited launches. У вас 3+ launches/year - окупается за первый год. Plus Aurora методология transparent (BASES black box)."

**"Что если у нас нет MMM expertise?"**
> "Subscription включает 20-40h consulting hours - Антон лично работает с командой через proxy review, anchors workshop, posterior update sessions. Aurora - assisted product, не self-serve."

**"Time to first forecast?"**
> "2 недели от data upload до Methodology Certificate. Pilot first launch FREE с case-study consent - можете попробовать без commitment."

**Closing (5-10 min):**
- Recap: "Видите fit для вашей задачи?"
- Pilot offer: "Готов начать pilot. NDA + pilot agreement = 1 week, kickoff session - 2 weeks из подписания. Total - 2 недели до start."
- Next steps: pilot agreement template send today, NDA signed within 1 week, kickoff scheduled.

### 4.3 Post-Demo Follow-up

Same day:
- Thank-you email + recap
- Demo recording (если customer agreed)
- Pilot agreement template attached
- Calendly link for kickoff session
- Methodology Certificate sample PDF attached

Day 3 (если no response):
- Nudge: "Готовы ли подписать pilot agreement? Готов ответить на вопросы."

Day 7:
- Final attempt: "Если в этом квартале не подходит - дайте знать когда вернуться."

---

## 5. Pilot Kickoff Checklist (1.5h session)

Per S008 PILOT_CLIENT_PLAN Section 6.2.

**Pre-kickoff (Antón):**
- [ ] NDA signed (1 page standard)
- [ ] Pilot agreement signed (Path B free first launch с case-study consent)
- [ ] Calendly slot booked (1.5h)
- [ ] Aurora Launch software access provided (license key или local install instructions)
- [ ] Customer team assigned (1-2 contacts identified)
- [ ] Data extraction guidance shared (DSM/Mediascope export instructions document)

**During kickoff (1.5h):**
- [ ] Aurora Launch overview presentation (15 min)
- [ ] Customer presents recipient brand context (15 min)
- [ ] Proxy discovery collaboration (30 min)
- [ ] Anchors collection plan (15 min)
- [ ] Timeline + check-in schedule confirmed (15 min)

**Post-kickoff (within 24h):**
- [ ] Kickoff session notes shared (1-page summary)
- [ ] Calendar invites for 4-weekly check-ins sent
- [ ] Calendly link for ad-hoc questions provided
- [ ] Customer slack-equivalent channel established (Telegram group чаще всего)

---

## 6. Conversion (Post-Pilot)

### 6.1 Conversion Conversation (Final Pilot Review, 1h)

Per S008 Section 6.5.

**Agenda:**
1. Pilot results review (15 min) - forecast vs actuals, learnings
2. Methodology validation (10 min) - Methodology Certificate accepted by their CFO?
3. Customer satisfaction check (10 min) - NPS-style, what worked / didn't
4. **Conversion offer presentation (20 min)** - tier recommendation + pricing
5. Q&A + decision (5 min) - sign or "we'll think"

### 6.2 Tier Recommendation Logic

Antón recommends tier based on customer's expected launch frequency:

**Starter (1.35M / 1.5M)** if:
- 1-3 launches/year expected
- Single team, 1-2 users
- Standard methodology certificate sufficient

**Pro (2.25M / 2.5M)** if:
- 4-8 launches/year expected
- Larger team (3-5 users)
- Wants 2-page Methodology Certificate (CFO defense)
- Pre-test creative integration valuable

**Enterprise (3.15M / 3.5M)** if:
- Strategic partnership signal
- Multi-team / multi-launch portfolio
- Needs white-label deliverables
- Custom contract terms (NDA, data residency)
- On-site training valuable

### 6.3 Contract Templates

**Standard subscription agreement** (1-year default, multi-year extension):

Aurora has 3 contract templates:
1. **Solo (Russian юр.лицо ИП)** - simple terms, payment via bank transfer, RUB
2. **Mid-corp (LLC, ООО)** - includes data residency clause, NDA appendix, RUB
3. **Enterprise (large pharma / FMCG)** - custom terms, multi-year, USD optional, dedicated SM clause

**Standard appendices:**
- Pricing schedule
- Service Level Agreement (response times per tier)
- Data Privacy Addendum (per GDPR + Russian Federal Law 152-FZ)
- NDA (mutual confidentiality)
- Renewal terms (per S009 PRICING_TIERS Section 5)

### 6.4 Approval Matrix

**Antón approves:**
- Standard Starter / Pro / Enterprise contracts
- Up to -15% discount (combined multi-year + pilot conversion)
- Up to 60-day payment terms (Net 60 для large clients)

**Antón consults legal counsel (внешний юрист) для:**
- Custom contract terms beyond templates
- Discounts > -20% (rare)
- Multi-year deals > 3 years
- White-label IP terms (Enterprise)

---

## 7. Onboarding (Post-Conversion)

### 7.1 Onboarding Session (1.5-2h)

**Within 7 days** of contract signing.

**Agenda:**
1. License activation (15 min) - cross_app_license framework setup, multi-seat config
2. Aurora Launch deep-dive (30 min) - features beyond pilot, advanced workflows
3. Team training (30 min) - hands-on with full team, Q&A
4. Roadmap preview (15 min) - upcoming Aurora products (Optimize / Brand) + Suite bundle option
5. Quarterly review schedule confirmation (10 min) - 4 sessions через год

**Deliverables:**
- License keys provided
- User seats provisioned
- Custom Slack/Telegram channel created (если Pro+)
- Welcome email с consultant contact info

### 7.2 Quarterly Reviews (Pro+)

**Each quarter, 1.5h session:**
- Customer projects review (active launches, posterior updates)
- Aurora performance feedback
- Roadmap input (customer wishes для next versions)
- Renewal planning (3 months before expiration)

**Q4 review = pre-renewal conversation:**
- Tier upgrade / downgrade discussion
- Multi-year extension consideration
- Suite bundle option (Aurora Optimize / Brand если applicable)

### 7.3 Annual Review (Enterprise)

Beyond quarterly, additional 2h annual:
- Strategic relationship review
- Custom feature requests prioritized
- Multi-year renewal с specific clauses
- Reference / case study renewal
- On-site session scheduling (если Enterprise)

---

## 8. Sales Operations

### 8.1 CRM (Notion)

Pipeline stages tracked:
- **Outreach sent** (date, channel, response status)
- **Discovery scheduled** (date, channel, prospect role)
- **Discovery completed** (notes, qualification result)
- **Demo scheduled** (date, version of pilot offer)
- **Demo completed** (notes, follow-up plan)
- **Pilot agreement signed** (date, contract version)
- **Pilot active** (kickoff date, check-in cadence)
- **Pilot completed** (date, success criteria met, conversion offer)
- **Subscription signed** (tier, term, value)
- **Active customer** (renewal date, quarterly review schedule)

### 8.2 Calendar (Calendly)

Public Calendly: anton-sipovich/aurora-launch:
- **30-min discovery call** slots
- **1h demo** slots
- **1.5h kickoff** slots (pilot kickoff + onboarding)
- **30-min check-in** slots (pilot mid-points, ad-hoc Q&A)

### 8.3 Communication

Primary channels:
- Email (ackold@yandex.ru) - formal
- Telegram (@anton_sipovich или channel) - quick questions
- Zoom - sessions (calls / demos / kickoffs / reviews)
- LinkedIn - relationship maintenance

### 8.4 Document Management

All sales documents в Aurora-Sales folder (locally):
- `templates/` - email + LinkedIn DM + contracts
- `pipeline/` - per-prospect folders with research + notes
- `customers/` - active customer files (contract + onboarding + reviews)
- `case-studies/` - approved customer stories для marketing

### 8.5 Metrics Tracked

**Monthly:**
- Outreaches sent (target 30-50/month sustained)
- Discovery calls completed (target 5-10/month)
- Demos completed (target 3-5/month)
- Pilots active (target 3-5 ongoing)
- Conversions closed (target 1-2/month)

**Annually:**
- Customer Lifetime Value (LTV)
- Churn rate (target <10% Phase B)
- Net Revenue Retention (target >100% with upsells)
- Net Promoter Score (target >40)

---

## 9. Sales Documentation Library

**Templates (versioned):**
- `email_pharma_v1.0.txt` (Russian cold email - pharma variant)
- `email_fmcg_v1.0.txt` (FMCG variant)
- `email_cosmetics_v1.0.txt` (cosmetics variant)
- `linkedin_dm_v1.0.txt`
- `warm_intro_request_v1.0.txt`

**Decks (PPTX):**
- `aurora_launch_pitch_15min.pptx` - condensed pitch для warm intros
- `aurora_launch_demo_45min.pptx` - full demo (used as backdrop)
- `methodology_deep_dive_30min.pptx` - для technical buyers

**Datasheets (PDF):**
- `aurora_launch_one_pager.pdf` - tier comparison + offer
- `aurora_launch_methodology_summary.pdf` - 2-page для technical reviewers
- `aurora_launch_case_study_template.pdf` - filled per pilot success

**Contract templates:**
- `subscription_agreement_starter_v1.0.docx`
- `subscription_agreement_pro_v1.0.docx`
- `subscription_agreement_enterprise_v1.0.docx`
- `nda_mutual_v1.0.docx`
- `pilot_agreement_v1.0.docx` (Path A or Path B)

---

## 10. Common Sales Scenarios

### 10.1 Scenario: Customer wants Path A 60-day evaluation but launches in 8 weeks

**Response:** "Path B better fits your timeline - free first launch, 12-week pilot covers your launch window. Conversion offer at end. Better than Path A which expires before launch."

### 10.2 Scenario: Customer's category lacks suitable proxy

**Response:** "Aurora correctly blocks forecast в этой ситуации (Insufficient verdict) - showing intellectual honesty. Можем pivot к category prior fallback (упрощённая версия) OR suggest other Aurora products (Optimize если есть other SKU данные). Better to be honest than generate misleading forecast."

### 10.3 Scenario: Customer wants white-label but не Enterprise

**Response:** "White-label - Enterprise tier feature. Если объём оправдывает - давайте обсудим Enterprise. Альтернатива - можем убрать Aurora wordmark вручную для отдельных deliverables (manual one-off, не в стандартном flow)."

### 10.4 Scenario: Customer wants USD pricing but Pro tier

**Response:** "USD optional только Enterprise. Если важно - можем negotiate Enterprise tier с adjusted pricing (~$35K USD = 3.5M RUB locked at signing rate)."

### 10.5 Scenario: Customer doesn't sign после positive pilot

**Common reasons + responses:**
- **Budget tight:** "Multi-year discount 5-10% available. Quarterly billing vs annual - cash flow easier?"
- **Internal champion gone:** "Готов re-engage с successor. Можем re-pilot если нужно."
- **Competing tool:** "Аналогов в Aurora ценовом сегменте нет в РФ. Nielsen BASES 5-10× дороже. Что конкретно конкурента предлагает что Aurora не имеет?"
- **Wait for budget cycle:** "Calendar set follow-up к [next budget cycle date]. Стартуй pilot follow-up уже сейчас - free until conversion."

### 10.6 Scenario: Renewal at risk

**Indicators:**
- Customer used <20% of consulting hours (signal: not engaged)
- 0 launches executed in year (signal: subscription wasted)
- Negative feedback в quarterly reviews

**Response:**
- 60 days before renewal: outreach with retention offer
- Tier downgrade (Pro → Starter) instead of churn
- Suite bundle offer (Optimize если applicable)
- Free quarterly review intensive (Антон bonus 5h consulting)
- Last-resort: -25% discount one-time saver (rare)

---

## 11. Связанные документы

- `../05_Sessions/SESSION_NEXT_QUESTIONS.md` S010 closed reference + S008 pilot client
- `../06_References/PRICING_TIERS.md` (S009) - tier numbers + discounts + pilot pricing
- `../04_Sprints/PILOT_CLIENT_PLAN.md` (S008) - pilot candidates + 12-week engagement
- `../00_Overview/PRODUCT_BOUNDARIES.md` - decision tree для qualification
- `../02_Data_Spec/REPORT_SECTIONS_SPEC.md` (S006) - deliverable demo materials
- Memory: `project_aurora_analytics_suite_strategy.md` - Suite bundle pricing + cross-sell context
- Memory: `project_aurora_suite_landing_stage1a.md` - auroraai.pro landing + GA4 + Yandex Metrica setup
- Memory: `project_platforma_aurora_company.md` - юр.лицо setup для contracts
