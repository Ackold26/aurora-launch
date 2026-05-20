# Pharma Pilot Bundles — Sprint 4 Batch 3

Three synthetic pharma scenarios for pilot testing.

| Bundle | Scenario | Category (actual) | Variant | Key params |
|---|---|---|---|---|
| `pharma_otc_immune.aurora.json` | OTC иммунитет (Кагоцел-class) | OTC_pharma.OTC_cold_flu | high_seasonality | MAINSTREAM, CHALLENGER, ALWAYS_ON, 156wk |
| `pharma_rx_cardio.aurora.json` | Rx кардиология | OTC_pharma.OTC_cold_flu* | baseline | PREMIUM, LEADER, DORMANT, 104wk |
| `pharma_generic_painkiller.aurora.json` | generic анальгетик | OTC_pharma.OTC_pain | volatile | ECONOMY, NICHE, PROMO_DRIVEN, 104wk |

\* Sprint 4 schema doesn't include a proper Rx_pharma.* category — Sprint Buffer
candidate for Sprint 5 (add Rx_pharma.Rx_cardiology + cardio-specific seasonality
parameters). For pilot testing, OTC_pharma.OTC_cold_flu with PREMIUM + DORMANT
profile proxies Rx semantics adequately (DORMANT media_maturity reflects DTC
advertising restrictions on Rx in RF; PREMIUM pricing_tier reflects Rx price segment).

## Regenerate

Bundles are deterministic (seed-based). To regenerate:

```bash
uv run python -m aurora_launch.tools.corpus_cli generate-pharma-pilot
```

Output overwrites `tests/fixtures/pharma_pilot/*.aurora.json` byte-for-byte
identical to the previous run.

## Pilot UX

Pilot user selects bundle in onboarding wizard ("Try a sample") → wizard
loads bundle metadata + runs forecast. Three scenarios cover key pharma
sub-domains for pilot validation across decision contexts:

- **pharma_otc_immune**: seasonal OTC with year-round media — tests high-seasonality
  decomposition and 3-year lifecycle dynamics.
- **pharma_rx_cardio**: low-media Rx profile — tests DORMANT media_maturity path
  (few spend weeks at end), premium pricing signal.
- **pharma_generic_painkiller**: price-volatile generic — tests PROMO_DRIVEN
  spend pattern (sparse high-spike weeks) and volatile noise.
