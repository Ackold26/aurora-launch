# Phase A Spec — Self-Audit Report (Session 3)

**Date:** 2026-05-05 evening (post-Phase A spec v0.2 + post-Маша-небесная-foundation handover)
**Scope:** аудит изменений после Session 2:
1. PHASE_A_REQUIREMENTS.md v0.2 (commit `fc2da29`) — 5 ответов Антона + Ed25519 rewrite + C8 NEW + Phi/Vercel changes.
2. DONOR_LIBRARY_SHORTLIST.md (commit `3e369a5`) — Биннофарм + BIN-2024.
3. INBOX_TO_MN entry 06:30 МСК — ack + COORDINATION inline.
4. Memory updates.
5. Cross-document consistency с Маши небесной commits (RISKS-PHASE-A R10/R11-R16, ADR-003 ICP shift, SALES materials).

**Method:** перечитала v0.2 changes critical lens'ом + cross-checked vs ADR-005 / ADR-006 / ADR-003 / RISKS-PHASE-A.md / WORKING-AGREEMENT.md.

**Outcome:** 11 finding'ов: **1 BLOCKER + 8 HIGH + 3 MEDIUM**. BLOCKER + HIGH applied.

---

## 1. BLOCKER

### B11 — Phi-3.5 (~2.5 GB) hosting через Vercel CDN — infrastructure inadequate

**Где:** Section 2.1 Tier 2 distribution + DoD + 2.5 dependencies.

**Проблема:** Spec говорит «Background download с CDN endpoint `https://cdn.auroraai.pro/models/phi-3.5-mini-q4_k_m.gguf`» с подразумеваемым Vercel hosting (line 652 «CDN hosting на Vercel infrastructure»). Vercel's actual limits:
- **Free tier:** 100 GB bandwidth/month, deployment max ~100 MB per file.
- **Pro tier:** 1 TB bandwidth/month, single asset up to 5 GB technically possible но не предназначено для serving large model blobs.
- Each customer download = 2.5 GB. **100 customers = 250 GB. Pro tier 1 TB = ~400 customer downloads/month total.** Bandwidth cost prohibitive at scale.
- Vercel storage не optimized для multi-GB binary serving (serverless paradigm).

**Impact:** Aurora hits Vercel limits at modest customer growth. Pivot к alternative CDN mid-Phase A = scope creep.

**Fix:** primary mirror = **HuggingFace Hub directly** (`https://huggingface.co/microsoft/Phi-3.5-mini-instruct/resolve/main/Phi-3.5-mini-instruct-Q4_K_M.gguf`):
- Already has CDN, free, fast (~5-50 Mbps user perceives).
- No Aurora bandwidth liability.
- Microsoft's own distribution channel — authoritative source.

Aurora's `cdn.auroraai.pro/models/` keeps **only** lightweight files:
- `MANIFEST.json` (SHA-256 expected hash + version metadata, ~1 KB).
- Optionally fallback URL list (if HuggingFace unreachable от РФ → Yandex Object Storage mirror).

**Update C2 Section 2.1 + DoD + Dependencies + 2.6 Q2.**

---

## 2. HIGH

### H15 — Public key archive endpoint = explicit network call during verification (privacy invariant)

**Где:** Section 7.1.C verifier functionality.

**Проблема:** Spec говорит «Looks up Aurora public key by /AuroraPublicKeyId: First check: embedded current key. Fallback: fetch `https://verify.auroraai.pro/keys/archive/<key_id>.pem`». Это **explicit HTTPS GET** во время verification — нарушает claim «client-side only / no network calls during verification».

**Impact:** marketing «no data uploaded» оставаt corret (only public key fetched, не user content). Но privacy-conscious customers могут спрашивать — нужен explicit explanation.

**Fix:** clarify в Section 7.1.C + privacy banner:
- «Verifier runs entirely client-side. **Только** public key fetch (один HTTPS GET к verify.auroraai.pro) если PDF references rotated key — public key — это публично доступная информация, не user data. Customer's PDF + bundle никогда не покидают browser».

### H16 — WASM bundle key rotation: explicit redeploy procedure missing

**Где:** Section 7.3 DoD + Section 7.1.B KMS.

**Проблема:** Public key embedded `compile-time include_bytes!`. При key rotation (раз в 2 года per ADR-005) — WASM bundle needs **rebuild + Vercel redeploy** для embed нового current key. Также old archive endpoint должен быть populated.

**Impact:** missed redeploy → verifier с stale embedded key + new PDFs signed с new key → mismatch → false-negative «Untrusted issuer».

**Fix:** add to Section 7.1.B + DoD:
- «**Key rotation procedure** (раз в 2 года):
  1. KMS generate new Ed25519 keypair.
  2. Update Vercel signing service env var к new key_id.
  3. Publish new public key к `verify.auroraai.pro/aurora-public-key.pem` + add к archive `keys/archive/<new_key_id>.pem`.
  4. Move previous current key к archive.
  5. Rebuild WASM bundle с new embedded current key + redeploy Vercel.
  6. Old PDFs (signed с previous key) verify через archive fallback.
- Tested annually in staging.»

### H17 — Ed25519 deterministic vs randomized — AC7.10 reproducibility assumption needs explicit statement

**Где:** Section 7.2 AC7.10 reproducibility test.

**Проблема:** AC7.10 says «sign service called twice → both receive same Ed25519 signature». Это работает **только** при deterministic Ed25519 (RFC 8032 standard signature scheme). `ed25519-dalek` crate v2.x использует deterministic signatures by default. Но KMS providers (AWS KMS / Yandex.Cloud KMS) могут implement randomized variant (NIST FIPS 186-5 allows both deterministic and randomized).

**Impact:** если KMS uses randomized → same canonical_hash returns DIFFERENT signatures каждый раз → AC7.10 fails → reproducibility claim broken.

**Fix:** add explicit requirement в Section 7.1.B:
- «**Aurora signing service uses deterministic Ed25519** (RFC 8032 standard) — same canonical_hash always returns same signature. KMS provider must support deterministic signing OR signing service uses non-KMS deterministic Ed25519 implementation (e.g., ed25519-dalek server-side с private key fetched via KMS one-time decrypt + held in encrypted memory)».
- Add to AC7.10 explicit assumption.
- Add to DoD: «KMS deterministic Ed25519 signing verified — same input always produces same output».

### H18 — AC2.x first-run Phi download flow missing dedicated AC

**Где:** Section 2.2 Acceptance Criteria.

**Проблема:** Spec adds first-run download к Section 2.1.B + DoD bullets, но НЕТ dedicated AC testing flow. Existing AC2.1-2.10 предполагают Tier 2 functional during tests — но при first-run, Phi не downloaded yet → AC2.2 (Tier 2 fallthrough) fails.

**Impact:** test order issue. AC suite не covers first-run scenario explicitly.

**Fix:** add **AC2.11 — First-run Phi download UX**:
- GIVEN clean install + first launch.
- WHEN user opens Studio.
- THEN welcome screen displays «Studio загружает локальную модель Phi-3.5» с progress bar; download starts c HuggingFace Hub primary OR `cdn.auroraai.pro/models/MANIFEST.json` для fallback URL list; SHA-256 verified post-download; Studio становится usable; «Cancel and continue с Tier 1+3 only» option works.
- Edge cases: corporate firewall blocks HF + cdn.auroraai.pro → manual install path UI визарда.

### H19 — Vercel US hosting + 152-ФЗ compliance ambiguous

**Где:** Section 5.1.D Telemetry hosting Vercel.

**Проблема:** Russian Federal Law 152-ФЗ requires personal data localization for Russian citizens. Spec disclaimer mentions «обезличенные usage events / без brand names / без model parameters / без файлов» — но `user_id_anon` (UUID per install) **technically может** считаться personal data в strict interpretation, если correlatable с другой info (timestamp + machine fingerprint + install date = potentially identifiable).

**Impact:** при regulatory audit (e.g., Roskomnadzor inquiry) — ambiguity. Фарма customers' compliance teams могут refuse opt-in even с anonymization, что снижает Этап 2 telemetry signal.

**Fix:** explicit 152-ФЗ compliance note + technical mitigation:
- В Section 5.1.D добавить: «**152-ФЗ compliance:** `user_id_anon` = random UUID generated client-side at first install, **не attached к Supabase user_id, не correlated с email или другими identifiers**. По букве 152-ФЗ это не персональные данные (нет ФИО / email / identifying info). По толкованию — арг защиты: anonymized at source, не reversible. Если регулятор требует localization → migrate Yandex.Cloud (re-visit trigger). Granularity opt-in: single boolean toggle Phase A; per-event-category Phase B+ если customer demand».

### H20 — C8 pdf_writer signing_callback abstract vs concrete: clarify build order

**Где:** Section 8.1 module table + Build order шапки.

**Проблема:** Build order revised: «Layer 2 (parallel after L1): C2 + C3 + C4 + C8 + Layer 3: C7». **C8 pdf_writer.render_methodology_certificate(signing_callback)** требует C7 signing service. Если C7 в Layer 3 (last), а C8 в Layer 2 — circular dependency apparent.

**Impact:** confusion в actual build order при Phase A start. Risk that team blocks waiting for C7 before C8 ship.

**Fix:** clarify в Section 8.1:
- «pdf_writer ships с **abstract signing_callback interface** (Protocol/ABC). Default placeholder callback returns deterministic mock signature для unit tests.
- **C7 implementation** provides concrete signing_callback wrapper around Vercel Edge Function client.
- **Integration test bridges Layer 2+3** — runs только after both C7 + C8 shipped. Until then C8 ships independently с placeholder for unit testing pdf_writer logic.»
- Update build order graph: C8 в Layer 2 (parallel) с note «pdf_writer abstract interface; concrete signing in Layer 3 C7».

### H21 — RISKS-PHASE-A R2 mentions «ROSST-категории» — Маша небесная не updated после моего INBOX clarification

**Где:** `aurora-meta/RISKS-PHASE-A.md` line 86.

**Проблема:** R2 «Donor library math gap» mitigation list says: «5 моделей выбираются из реальных клиентов Эконометрики (Кагоцел, Венарус, ROSST-категории) после anonymization». Но мой Audit Session 1 (commit `c5f81dd`) + INBOX_TO_MN 06:30 МСК clarified: **ROSST = white-label apps семейство, НЕ donor brand**. Маша небесная не приняла update в RISKS-PHASE-A после моего INBOX.

**Impact:** cross-document inconsistency. Если Машa небесная reads R2 как source of truth — продолжает believe «ROSST-категории» applicable.

**Fix:** ping в next INBOX_TO_MN (low-priority addendum) + record как pending update в memory. Не блокирует — это Маши небесной зона documents.

### H22 — Donor library pharma-only vs ICP shift Эконометрика (agencies + FMCG retail) — coverage mismatch

**Где:** Aurora Launch DONOR_LIBRARY_SHORTLIST.md + ADR-003 + R2 risks.

**Проблема:** ADR-003 (Маша небесная) zafиксировал Aurora Launch upsell-стратегию: «existing customers Эконометрики». RISKS-PHASE-A R2: «максимальное покрытие фарма + FMCG + ритейл-маркетинг категорий». 10-контактный pipeline = «AdWatch / Media Direction / Proximity / Alium / Progression / Родная Речь / Instinct / Магнит / X5 / Okkam» — преимущественно agencies + retail (Магнит, X5).

**Но мой DONOR_LIBRARY shortlist:** Кагоцел + Венарус = **только pharma OTC**.

Если Aurora Launch upsell flow goes через agencies + retail clients (per ICP shift), donors needed:
- Pharma donors usable если pharma agencies OR pharma retail клиенты в pipeline (TBD).
- FMCG retail brand donors needed для Магнит/X5 use cases.
- Agency-driven donor scenarios (multi-brand portfolio agencies).

**Impact:** Aurora Launch B6 donor library coverage может оказаться **ICP-mismatched** при actual sales. Если pilot client = X5 retail, pharma donors дают low similarity verdict → forecast quality issue.

**Fix (Phase A scope):** add note в DONOR_LIBRARY_SHORTLIST.md Section 2.2:
- «Open question Антону: какой profile среди 10 контактов pipeline? Если ≥30% работают с pharma brands — pharma donors useful. Иначе — pivot донор coverage к agencies-portfolio + FMCG retail (Магнит/X5 type) brands. Phase B6 pilot client selection drives donor library composition».
- Не блокирует — Антон's call.

---

## 3. MEDIUM

### M12 — WASM bundle size budget breakdown в DoD

**Где:** Section 7.3 DoD «WASM bundle ≤ 500 KB gzipped».

ed25519-dalek (~50 KB) + lopdf (~250 KB) + zip (~50 KB) + sha2 (~30 KB) + i18n strings + glue code = **estimated 400-450 KB gzipped**. Tight margin. Adding logger / error handling boilerplate may exceed 500 KB.

**Fix:** add to DoD: «WASM bundle size budget breakdown documented (per crate contribution). If exceeds 500 KB → switch к smaller alternatives (lopdf-light fork, simplified i18n)».

### M13 — WeasyPrint Windows DLL distribution

**Где:** Section 8.5 Зависимости WeasyPrint >= 60.0.

WeasyPrint requires libpango / libcairo / libffi system libs on Windows. NSIS installer должен bundle DLLs OR rely on system installation.

**Fix:** add к DoD «WeasyPrint Windows installation verified — DLLs bundled с NSIS installer или auto-install on first PDF generation». Or alternative Rust printpdf consideration documented.

### M14 — Visual regression cross-platform pixel threshold

**Где:** Section 8.4 Test Data + AC8.6.

«Visual diff < 5% pixel difference» — но font rendering differs Windows ↔ Linux CI runner. Setup-specific golden screenshots needed; cross-platform fragile.

**Fix:** add в DoD «Visual regression baselines captured on Windows reference machine; Linux CI runner allowed 10% tolerance OR uses Wine для consistent rendering».

---

## 4. Applied Fixes (subsequent commits)

- B11 → C2 Section 2.1.B Phi distribution rewrite (HuggingFace primary + cdn.auroraai.pro MANIFEST only) + DoD + Section 2.5 dependencies + 2.6 Q2.
- H15 → C7 Section 7.1.C clarify «public key fetch only, не user data».
- H16 → C7 Section 7.1.B + DoD key rotation procedure 6-step.
- H17 → C7 Section 7.1.B + AC7.10 explicit deterministic Ed25519 (RFC 8032).
- H18 → C2 Section 2.2 NEW AC2.11 first-run Phi download flow.
- H19 → C5 Section 5.1.D 152-ФЗ compliance note.
- H20 → C8 Section 8.1 + build order graph clarify abstract signing_callback interface.
- H21 → INBOX_TO_MN ping для Маши небесной R2 update (next sync session).
- H22 → DONOR_LIBRARY Section 2.2 add ICP coverage open question.

MEDIUM (M12, M13, M14) — applied as DoD bullets where convenient, otherwise marked TBD.

---

## 5. Cross-session running totals

- Session 1 audit: 24 findings (8 BLOCKER + 9 HIGH + 7 MEDIUM).
- Session 2 audit: 11 findings (2 BLOCKER + 5 HIGH + 4 MEDIUM).
- **Session 3 audit: 11 findings (1 BLOCKER + 8 HIGH + 3 MEDIUM).**
- **Total session 2026-05-05: 46 findings (11 BLOCKER + 22 HIGH + 14 MEDIUM/Risk). All BLOCKER + HIGH applied.**

Spec quality post-3-audits: production-ready handoff к Phase A start, with clearly tracked open questions для Антона + Маши небесной.
