# Coordination: Aurora Launch ↔ Aurora Data Studio

> ⚠️ **Superseded by `aurora-meta/COORDINATION-LAUNCH-STUDIO.md` v0.2 (2026-05-08).** Этот файл retained для historical reference. Source-of-truth — aurora-meta. v0.2 включает D002 reflection (post-2026-05-06 PROXY_INTAKE_PROTOCOL), Decision Index (§0), Phase A timeline coordination (§9), Escalation paths (§10), и telemetry events scope-honest restructure (§4).

**Status:** Draft v0.1 (2026-05-05) — Маша маленькая. **Superseded 2026-05-08.** Финальная версия в `aurora-meta/COORDINATION-LAUNCH-STUDIO.md` v0.2.

**Цель документа:** зафиксировать границы ответственности, versioning, feature split (Этап 1 / Этап 2), telemetry, migration rules и consumption pattern между Aurora Launch и Aurora Data Studio в Phase A → Phase B.

**Базовые источники:**
- Aurora Launch `03_Architecture/REUSE_FROM_ECONOMETRICA.md`
- Aurora Data Studio `03_Architecture/REUSE_FROM_ECONOMETRICA.md`
- Memory `project_aurora_launch_principles.md` (Маша небесная strategic corrections 2026-05-05)
- Memory `project_aurora_data_studio_concept.md` (2-stage freemium → premium)
- Aurora Launch ADR-002 (`.aurora` ZIP storage), Studio ADR-001 (tiered hybrid AI)

---

## 1. Owners

| Component | Path | Owner | Change protocol |
|---|---|---|---|
| Format adapters package | `aurora-platform-core/source_adapters/` | **Studio team** | PR review Studio → Launch acceptance check |
| Adapter contract (base class + Result type) | `aurora-platform-core/source_adapters/adapter_contract.py` | **Studio team** | Через ADR (затрагивает Launch consumption) |
| Launch workflow config | `engines/launch_workflow.yaml` (Aurora Launch repo) | **Launch team** | Internal, без согласования |
| Schema Registry | `aurora-platform-core/schema_registry.py` | **Shared** | Изменения через ADR (схема bump = breaking для всех consumer'ов) |
| `.aurora` bundle composer | `aurora-platform-core/bundle_composer/` | **Studio team** | Launch consumes, не модифицирует |
| Pickle additive schema (v3.0) | `aurora-platform-core/schemas/` | **Shared** | Strict additive (Optional/None defaults), bump через ADR |
| `cross_app_license` framework | `aurora-platform-core/common_services/license/` | **Platform team (= Антон + Маша)** | License tier scaffolding (free/pro/team/agency) с Phase A |
| Telemetry framework | `aurora-platform-core/common_services/telemetry/` | **Platform team** | Studio + Launch регистрируют events через shared API |
| Feature flags | `aurora-platform-core/common_services/feature_flags.py` | **Platform team** | Per-feature flags, overridable через license tier |

**Принцип:** Studio team = data ingress (Phase A), Launch team = analytics workflow (Phase B). Shared platform components — через ADR.

---

## 2. Versioning rules

### 2.1 `aurora-platform-core` package

**SemVer:** MAJOR.MINOR.PATCH.
- **PATCH** (0.1.0 → 0.1.1): bug fix, backwards-compatible.
- **MINOR** (0.1.x → 0.2.0): additive features (новый адаптер, новое поле в schema, новое API endpoint). Backwards-compatible.
- **MAJOR** (0.x → 1.0): breaking changes. Только через ADR + 1 minor version deprecation cycle.

### 2.2 Adapter contract changes (Studio → Launch consumption)

| Change type | Allowed | Process |
|---|---|---|
| Новое поле в `AdapterResult` (Optional) | ✅ MINOR bump | PR + Launch tests pass |
| Новое поле required | ❌ Только MAJOR | ADR + 1 minor deprecation |
| Переименование existing field | ❌ Только MAJOR | ADR + alias через 1 minor |
| Удаление поля | ❌ Только MAJOR | Mark deprecated в N, удалить в N+1 minor |
| Новый адаптер (DSM v2025 etc.) | ✅ MINOR | PR review, Studio tests + Launch integration test |

### 2.3 `.aurora` bundle schema versioning

**Schema version в `manifest.json`:** строка `"3.0"` (per Launch ADR-002 + Studio bundle composer).

**Forward compat:** через `MIN_APP_FOR_SCHEMA` map (см. Launch REUSE Section 2.1) — bundle хранит `schema_version`, app проверяет минимальную версию для open. Несовместимость → explicit warning + `suggested_action`.

**Backward compat:** через `SchemaRegistry` BFS migration path (v1.0 → v2.0 → v3.0). Studio bundle composer всегда пишет latest schema; Launch read адаптируется через миграцию.

### 2.4 Deprecation cycle

- Минимум 1 minor version (≈4-6 недель) с deprecation warning в logs + docs.
- Удаление в следующем minor.
- Major bumps анонсируются за 2 minor versions через `aurora-meta/DECISIONS-REGISTER.md`.

---

## 3. Feature Split — Этап 1 vs Этап 2 (strategic correction Маши небесной 2026-05-05)

### 3.1 Этап 1: Studio = инфраструктурный компонент Aurora (Phase A → Phase B)

**Доступ:** все покупатели любого Suite app получают полный Studio access. НЕ продаётся отдельно. НЕ маркетируется как "free".

**Scope (всё что нужно Aurora Launch B0.5+):**

| Feature | Owner module | Launch usage |
|---|---|---|
| Импортёры DSM Group monthly XLSX | `source_adapters/dsm_group.py` | Proxy + recipient sales data |
| Mediascope AdEx (3 file variants V1/V2/V3) | `source_adapters/mediascope_adex.py` | Proxy categorical ad spend |
| Mediascope TV Index Polometers (multi-row header, variable audiences) | `source_adapters/mediascope_tv_index.py` | Proxy TV ratings TRPs/GRPs |
| DigitalBudget category exports | `source_adapters/digitalbudget.py` | Proxy digital ad spend (alternative to AdEx) |
| Tier 1 heuristic + signature match | `source_adapters/*` | Auto-detect format variant |
| Tier 2 local LLM parser (Phi-3.5-mini Q4) | `engines/llm_parser/` | Custom client XLSX parsing |
| Базовое column mapping (Assisted mode + manual override) | `cabinets/MappingReviewStep` | Recipient anchor data preparation |
| Format adapters (V1/V2/V3 routing) | `source_adapters/<src>/format_adapter.py` | Auto-applied per detected variant |
| Валидация данных (Pydantic + Quality Gates) | `engines/quality_gates/` | Pre-bundle validation |
| Bundle export к `.aurora` (ZIP container, manifest.json + Pydantic data + math artifacts) | `engines/bundle_composer/` | Output для Launch consumption |
| Provenance manifest (source files mapping, tier confidence per source) | `engines/bundle_composer/provenance.py` | Methodology Certificate input |
| SHA-256 signature | `engines/bundle_composer/signature.py` | Reproducibility verification |

**Phase A scaffolding обязательно (для Этапа 2 будущего):**
- Feature flags infrastructure — все Pro-кандидат фичи помечены, на Этапе 1 включены.
- Telemetry / usage events — локальный сбор + opt-in отправка (см. Section 4).
- License tier scaffolding — `cross_app_license` поддерживает tier'ы (free/pro/team/agency) с самого начала.
- Lossless migration — `.aurora` forward-compatible (см. Section 5).

### 3.2 Этап 2: Studio Pro standalone (Q4 2026 / Q1 2027 после пилота Launch)

**Решение принимается** на базе telemetry данных Этапа 1 (см. Section 4 для events списка). До решения — НЕ строить Pro features в Phase A.

**Кандидатные Pro-features (TBD после telemetry analysis):**
- Кастомные коннекторы (1С / SAP / GA4 / Yandex.Wordstat / Mediascope BrandPulse).
- Advanced charts в UI (pre-bundle visualization, EDA dashboard).
- PDF export reports (data quality summary, lineage diagrams).
- Multi-project workspaces.
- Team collaboration features (shared mappings, review workflows).
- Tier 3 cloud LLM unlimited usage (Phase A: opt-in, possibly capped).

**Aurora Launch НЕ зависит** ни от одной Pro-feature. Launch consumes только Этап 1 scope.

### 3.3 Bundle pricing скидки Launch+Studio = ОТМЕНЕНЫ

Studio = инфраструктура, не add-on. Скидывать нечего на Этапе 1. Скидки появятся когда Studio станет платной (Этап 2). Удалено из `06_References/PRICING_TIERS.md`.

---

## 4. Telemetry events Phase A (для Этапа 2 monetization decisions)

**Архитектура:** локальный сбор в `~/.aurora/telemetry/events.jsonl` + opt-in batched отправка через `common_services/telemetry/sender.py` (default OFF, toggle в Settings).

**Privacy:** anonymized user_id (random UUID per install), без PII, без data content. Только feature usage signals.

**Event schema (Pydantic v2):**

```python
class TelemetryEvent(BaseModel):
    event_name: str                          # snake_case identifier
    user_id_anon: str                        # UUID per install
    app: Literal["studio", "launch", "econometrica", ...]
    feature: str                             # subsystem identifier
    timestamp: datetime
    metadata: dict[str, str | int | float]   # event-specific, no PII
```

**Studio events для Этапа 2 monetization signals:**

| Event | Trigger | Metadata | Why (Этап 2 signal) |
|---|---|---|---|
| `studio.task_selected` | TaskSelectStep complete | `target_app`, `task_id` | Какие задачи самые востребованные → Pro tier feature ranking |
| `studio.source_uploaded` | UploadStep file accepted | `source_type`, `tier_used` (1/2/3), `file_size_kb` | LLM usage frequency → cloud cost projection |
| `studio.format_variant_detected` | Adapter inference complete | `source_type`, `variant` (V1/V2/V3), `confidence` | Adapter coverage → новые adapter ROI |
| `studio.mapping_intervention` | Manual override в MappingReviewStep | `field_name`, `auto_suggestion`, `user_choice` | Heuristic accuracy → Pro tier tier-3 unlimited monetization rationale |
| `studio.quality_gate_result` | QualityGatesStep gate run | `gate_name`, `result` (pass/warn/fail), `severity` | Data quality patterns → Pro tier advanced gates |
| `studio.bundle_exported` | BundleExportStep complete | `target_app`, `target_task`, `sources_count`, `time_to_complete_seconds` | TTV (time-to-value) → onboarding optimization |
| `studio.cloud_optin_toggle` | Settings toggle | `direction` (on/off) | Tier 3 demand signal |
| `studio.pro_feature_gated` | User attempts disabled feature | `feature_name`, `tier_required` | Pro feature demand ranking |

**Launch events для Studio coordination:**

| Event | Trigger | Metadata | Why |
|---|---|---|---|
| `launch.studio_bundle_imported` | Launch loads `.aurora` from Studio | `bundle_schema_version`, `sources_in_bundle`, `studio_version` | Cross-product coupling health |
| `launch.adapter_contract_violation` | Bundle data fails Launch validators | `expected_field`, `received_type`, `studio_version` | Drift detection |

**Storage retention:**
- Local: append-only, rotated daily, 90-day retention.
- Server (если opt-in): aggregated, anonymized, indefinite (для Этап 2 monetization analysis).

**Reference:** `aurora-knowledge/Architecture/phase-a-future-monetization-scaffold.md` (от Маши небесной).

---

## 5. Migration rules — lossless Studio Free → Studio Pro upgrade

### 5.1 Forward-compatibility invariants

`.aurora` bundle от Studio Free должен открываться в Studio Pro **без потери данных**, даже если Pro добавит новые поля.

**Rules:**
1. **Additive only** — новые поля только Optional с None/[]/{} defaults.
2. **Никогда не renaming** existing полей в additive bumps. Renaming = MAJOR bump через ADR.
3. **Никогда не required-promotion** — Optional поле не становится required в minor bump.
4. **Provenance preserved** — `provenance.tier_used`, `signature`, `quality_gates_results` сохраняются 1:1 при upgrade.

### 5.2 SchemaRegistry для Studio + Launch combined v3.0

**Combined v3.0 поля** (oба set'а живут в одной schema_version "3.0"):

```python
@SchemaRegistry.register("2.0", "3.0")
def migrate_v2_to_v3(data: dict) -> dict:
    """v2.0 -> v3.0: add Studio + Launch fields combined (additive)."""
    # Studio fields (см. Studio REUSE Section "Pickle additive schema")
    data.setdefault("bundle_metadata", None)
    data.setdefault("provenance", None)
    data.setdefault("quality_gates_results", None)
    data.setdefault("signature", None)
    # Launch fields (см. Launch REUSE Section 2.1)
    data.setdefault("proxy_brand_metadata", None)
    data.setdefault("recipient_anchors", None)
    data.setdefault("transfer_provenance", None)
    data.setdefault("forecast_horizons", None)
    data.setdefault("posterior_update_log", [])
    data.setdefault("consulting_hours_log", None)
    return data
```

**Coordinated bump policy:** Studio + Launch синхронизируют schema bumps через ADR в `aurora-knowledge/Decisions/`. Один schema_version covers both subsystems.

### 5.3 Studio Pro additive scenario (пример)

Гипотетически в Этапе 2 Studio Pro добавляет `multi_project_workspace_id`:
1. ADR в `aurora-knowledge/Decisions/`.
2. Pickle schema v3.0 → v3.1 minor bump (additive).
3. Migration `v3.0 → v3.1`: `data.setdefault("multi_project_workspace_id", None)`.
4. Studio Free bundle (v3.0) открывается в Studio Pro — поле = None, Pro UI graceful handling.
5. Studio Pro bundle (v3.1) открывается в Studio Free / Aurora Launch — `MIN_APP_FOR_SCHEMA` check, если current app < min → user обновляет.

### 5.4 Backup invariants (per Launch ADR-002)

`.aurora.bak.N` rolling 4 backups. Migration пишет в `.tmp` + atomic rename. Failure recovery: restore latest valid `.bak`.

---

## 6. Aurora Launch consumption pattern

### 6.1 Когда Launch consumes Studio

**Sprint B0.5 onwards:** Launch UI imports `.aurora` от Studio как proxy data candidate.

**Pipeline:**
```
1. User в Aurora Launch → ProxySelectionStep
2. UI: "Import from Aurora Data Studio" button
3. File picker → выбирает `.aurora` bundle
4. Launch reads bundle через aurora_platform_core.bundle_reader
   → SchemaRegistry.migrate(data, target_version="3.0")  # ensures forward-compat
   → check_forward_compatibility(data, current_app_version)
   → если can_open=False → show upgrade dialog с suggested_action
5. Launch validates: bundle_metadata.target_app in {"launch", "shared"}
6. Launch extracts: provenance.source_files (DSM/MS/etc.) + canonical schema data
7. ProxyDataValidator.validate() (Launch-specific) — sufficiency check для Launch use case
8. Если pass → данные доступны для proxy candidate scoring (similarity framework Sprint B2)
```

### 6.2 Adapter package versioning independence

`aurora-platform-core/source_adapters/` версионируется **независимо** от `aurora-launch` workflow.

**Implication:**
- Studio выпустит DSM v2025 adapter в `aurora-platform-core 0.5.0` — Launch consumes автоматически после `pip install --upgrade aurora-platform-core` (or Tauri sidecar redeploy).
- Launch workflow (`engines/launch_workflow.yaml`) не меняется при adapter additions.
- Breaking adapter changes → MAJOR bump platform-core → Launch обновляет deps в next release.

### 6.3 Cross-product navigation UX (Sprint B6, per strategic correction 2026-05-05)

В Aurora Эконометрика UI добавляется кнопка "Использовать как proxy в Aurora Launch" — exports current Эконометрика project как `.aurora` bundle (Studio composer reuse) → opens Aurora Launch → ProxySelectionStep с pre-filled bundle.

**Это primary demo strategy** для Aurora Launch (Эконометрика → Launch migration flow), вместо synthetic demo.

---

## 7. Unresolved coordination questions (для Маши небесной)

1. **Adapter ownership boundaries when Launch needs custom logic:** если Launch-specific validation требует адаптер изменения (e.g., нужен дополнительный field в `AdapterResult`), процесс negotiation? — Предлагаю default: Launch open ADR, Studio team accepts/rejects/modifies.

2. **Studio license tier UI behavior на Этапе 1:** все tiers одинаковы (всё включено), или есть смысл показывать tier badge в UI для signaling Этапа 2 готовности? — Предлагаю default: показывать tier silently (Solo / Team / Agency), без UI gates.

3. **Telemetry opt-in default:** ON или OFF? — фарма ICP читает "telemetry on" как privacy concern. Предлагаю default OFF + onboarding banner с opt-in CTA.

4. **Launch fallback при Studio adapter regression:** если new adapter version breaks Launch import, что делает Launch — block import или fallback к previous adapter version? — Предлагаю default: explicit error с suggested_action="downgrade_platform_core" + log в telemetry для quick detection.

5. **Cross-app feature flags propagation:** если Studio выключает фичу через flag, должен ли Launch это видеть? — Предлагаю default: feature flags scoped per app (studio.* / launch.*), shared flags только для cross-cutting concerns (telemetry.opt_in, license.tier).

---

## 8. References

- Launch REUSE: `Aurora Launch/03_Architecture/REUSE_FROM_ECONOMETRICA.md`
- Studio REUSE: `Aurora Data Studio/03_Architecture/REUSE_FROM_ECONOMETRICA.md`
- Launch ADR-002 (storage layer ZIP): `Aurora Launch/03_Architecture/decisions/ADR-002-storage-layer.md`
- Studio ADR-001 (tiered hybrid AI): `Aurora Data Studio/03_Architecture/decisions/ADR-001-tiered-hybrid-ai-parser.md`
- Studio ADR-003 (floating license): `Aurora Data Studio/03_Architecture/decisions/ADR-003-floating-license.md`
- Phase A monetization scaffold (Маша небесная): `aurora-knowledge/Architecture/phase-a-future-monetization-scaffold.md` (pending)
- Strategic corrections 2026-05-05 в memory: `project_aurora_launch_principles.md` + `project_aurora_data_studio_concept.md`
