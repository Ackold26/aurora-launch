# Aurora Launch → Aurora Optimize Migration Guide

**Status:** v1.0 (2026-05-04)
**Audience:** Customer success - guidance для clients transitioning из Aurora Launch к Aurora Optimize standard MMM
**Authority:** Audit enhancement E6

## Когда мigrate?

После 12+ месяцев Aurora Launch usage с posterior updates ваша recipient model становится **standalone-capable** - proxy weight уменьшается до < 5%, recipient data достаточно для standard MMM.

В этот момент **Aurora Optimize** более подходит:
- Standard pricing (200-500k vs 1.5-3M Launch subscription)
- Workflows focused на ongoing optimization (not transfer learning)
- Larger feature set (multi-scenario library, advanced what-if)
- Long-history insights (year-over-year trends)

---

## Когда НЕ migrate?

Оставаться на Aurora Launch если:
- Запускаются **новые продукты** регулярно (Launch unlimited launches valuable)
- Нужна continuous methodology consulting (20-40h hours)
- Recipient data все ещё short (< 12 месяцев) или sparse
- Bundle Aurora Suite (Optimize + Launch + Brand) - Suite cheaper option

---

## Decision Matrix

| Сценарий | Recommended product |
|---|---|
| 1+ launches per год + ongoing optimization | **Suite Bundle** |
| 1-2 launches per год | Aurora Launch + standalone Optimize |
| Stable mature brand, no new launches планируются | Migrate to **Aurora Optimize** |
| Стартовали Launch, теперь хотим только optimization | Migrate to **Aurora Optimize** |
| Нужны и launch + brand awareness analysis | **Suite Bundle** (Launch + Brand) |

---

## Pre-Migration Checklist

Before migrating, confirm:

- [ ] Recipient brand имеет **18+ months** continuous DSM + Mediascope data
- [ ] Posterior weight schedule показывает proxy weight < 0.10
- [ ] Aurora Launch model R² > 0.7 standalone (без proxy reliance)
- [ ] No upcoming launches планируются в next 12 месяцев
- [ ] Quarterly review session с Антоном confirmed migration is right move

---

## Migration Process

### Step 1: Export Aurora Launch project (.aurora bundle)

```
File → Export → Save As (.aurora project)
```

Это создаёт portable project file со всеми historical data + posterior updates.

### Step 2: Open в Aurora Optimize

Aurora Optimize v1.4.0+ supports opening Aurora Launch .aurora bundles seamlessly.

```
File → Open Project → выберите Launch_project.aurora
```

При первой загрузке:
- Aurora Optimize распознает Launch fields (proxy_metadata, transfer_provenance)
- Automatic schema migration v3.0 → v4.0 (Optimize new schema)
- Launch context preserved (proxy info остаётся в metadata для historical reference)
- Proxy priors **archived** (no longer affecting active model)
- Recipient data **promoted** к primary model basis

### Step 3: Re-train standard MMM на recipient data

В Aurora Optimize:
- Run standard pipeline: Import → Validate → Model → Decompose → Optimize → Report
- Все proxy data archived (доступно для reference)
- Recipient data становится full training set
- Model fits using standard Bayesian MMM (no transfer)

### Step 4: Verify consistency

Compare:
- Decomposition в Launch (last forecast) vs Optimize (newly trained)
- ROI per channel - should be similar (within ~10-20% drift acceptable)
- Major directional differences → investigate (data anomaly или model issue)

Если significant differences → consult Антон's quarterly review session.

### Step 5: Subscription transition

Contact Aurora team (Антон) для subscription change:
- Cancel Aurora Launch subscription (end of current billing period)
- Activate Aurora Optimize license
- Pricing adjustment:
  - Aurora Launch: 1.5-3M/year
  - Aurora Optimize: 200-500k/year (mid-tier) или WL Premium 300-750k/year
- Loyalty discount возможен для multi-year clients

---

## Data Preservation

### What's preserved в migration

- All DSM/Mediascope historical data
- All recipient anchor data (now archived metadata)
- All forecasts ever generated (audit trail)
- All posterior update events (history)
- Model checkpoints (последние)

### What's archived (не active)

- Proxy brand metadata - доступно as "history" panel
- Transfer provenance - audit reference only
- Forecast horizons из Launch (replaced by Optimize forecasts)

### What's removed

- Posterior update workflow (Optimize не нужен - just regular training)
- Proxy weight schedule (proxy архивирован)

---

## What Stays The Same

- **.aurora file format** - both products use SQLite hybrid (audit decision F18)
- **Reports** (PPTX, HTML, XLSX) - same templates available, slight CFO-framing variations
- **Aurora Hybrid Design System** - same look and feel
- **Methodology Certificate PDF** - generated в обоих
- **Data sources** (DSM, Mediascope, AdIndex) - same parsers

---

## What Changes

### UI changes
- Aurora Launch cabinets (ProxySelection, RecipientAnchors, TransferValidate, PosteriorUpdate) - больше не accessible
- Aurora Optimize cabinets (Import, Validate, Model, Decompose, Optimize, Report) - standard pipeline
- Per-app accent: Electric Blue (Launch) → Sacred Lime (Optimize)

### Workflow changes
- No more "weighted с proxy" forecasts
- No more "posterior update" cycle (just retrain when new data)
- Standard scenario library (Optimize)

### Pricing changes
- Subscription downgrade: 1.5-3M (Launch) → 200-500k (Optimize standard) or 300-750k (WL premium)
- Consulting hours: 20-40h Launch → 8-15h Optimize per year
- Migration discount: 10-20% off first year Optimize subscription

---

## FAQ

**Q: Что если launch нового продукта в будущем?**
A: Re-subscribe Aurora Launch для that launch. Old Launch project preserved. Or покупайте Suite bundle для seamless workflow.

**Q: Lose Launch insights?**
A: No - all forecasts + posterior updates archived. Available для historical review.

**Q: Optimize forecasts отличаются от последних Launch forecasts - что не так?**
A: Two reasons:
1. Optimize trains standalone без proxy priors - small drift normal (< 20%)
2. Если significant - investigate. Антон может help debug в consulting session.

**Q: Можно ли revert обратно к Launch?**
A: Yes (within 90 days). After 90 days - re-subscription required + migration cost.

**Q: Suite Bundle option vs separate?**
A: Suite Bundle (Optimize + Launch + Brand) часто экономичнее для customers с 1-2 launches per year + ongoing optimization needs.

**Q: White-label tier (для агентств)?**
A: Aurora Optimize WL premium tier available - rebrand-возможность deliverables. Спросите Антона.

---

## Timeline

Typical migration:
- **Decision:** 1 quarter review session
- **Pre-migration check:** 2 недели (data verification)
- **Migration:** 1-2 days (file export/import + validation)
- **Verification:** 1 неделя (parallel run Launch + Optimize, compare outputs)
- **Subscription transition:** end of current billing period

---

## Contact

Migration support: support@auroraai.pro или Антон's direct contact (existing client).

---

## Related

- `../00_Overview/PRODUCT_BOUNDARIES.md` - Launch vs Optimize positioning
- `../00_Overview/ROADMAP.md` - Phase B context
- Memory: `project_aurora_analytics_suite_strategy.md` - Suite bundle pricing
- Aurora Optimize documentation: separate product (Phase B re-brand of Aurora Econometrica)
