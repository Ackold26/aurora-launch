# Aurora Launch

**MMM forecasting product для запуска новых брендов via ad-hoc proxy intake.**

Phase B Aurora Analytics Suite product. Spec: [`03_Architecture/PHASE_B_REQUIREMENTS.md`](03_Architecture/PHASE_B_REQUIREMENTS.md).

## Status

- v0.1.0-b05 — Sprint B0.5 implementation (BC Test Corpus & Format Adapters + Reproducibility CLI)
- Phase B B1-B6 sprints — pending Phase A Weeks 4-7 completion

## Что внутри

```
aurora-launch/
├── 00_Overview/               Принципы, roadmap, product boundaries
├── 01_Concept/                Multi-proxy UX decision rules
├── 02_Data_Spec/              Pydantic schemas SSoT
├── 03_Architecture/           Architecture decisions, math reference
│   ├── decisions/             ADRs
│   ├── PHASE_B_REQUIREMENTS.md  ⭐ Implementation contract
│   └── PROXY_INTAKE_PROTOCOL.md  ⭐ D002 — ad-hoc proxy intake workflow
├── 04_Sprints/                Pilot client plan
├── 05_Sessions/               Session logs
├── 06_References/             Pricing, sales playbook, audit reports
├── src/aurora_launch/         Implementation
│   ├── engines/               Math + business logic
│   ├── tools/                 CLI tools
│   └── schemas/               Pydantic models
└── tests/                     Tests + synthetic corpus fixtures
```

## Quick start

```bash
# Install
uv sync --all-extras

# Run tests
uv run pytest

# Generate synthetic corpus project
uv run aurora-corpus generate fmcg_food_snacks_savoury baseline --seed 42 --output ./test_project.aurora

# Verify reproducibility of an .aurora bundle
uv run aurora-launch-reproduce <bundle.aurora> <expected_hash>
```

## Architectural foundation

- **D002 restored:** ad-hoc proxy intake (no donor library) per `03_Architecture/PROXY_INTAKE_PROTOCOL.md`
- **Trust Stack (CP-1):** every artifact signed Ed25519, every result reproducible, every metric с uncertainty
- **Privacy by Architecture (CP-4):** local-first, data never leaves customer machine
- **Reproducibility Ceremony (CP-7):** Methodology Certificate as artifact, public WASM verifier on `verify.auroraai.pro`

См. `03_Architecture/PHASE_B_REQUIREMENTS.md` §1 для full Cross-cutting Principles.

## Dependencies

- Python 3.11+
- aurora-platform-core v0.1.0+ (path-based dev, git+https in release)
- Phase A components: aurora_inference, aurora_studio, aurora_schema_registry

## License

Proprietary. Aurora Analytics, 2026.
