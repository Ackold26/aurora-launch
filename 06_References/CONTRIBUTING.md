# Aurora Launch - Contributing Guide

**Status:** v1.0 (2026-05-04)
**Audience:** Aurora team contributors (Маша + Антон + future contributors)

## Code Style

### Python (Pydantic v2 era)

**Conventions:**
- **Pydantic v2 patterns:** `model_validator(mode="after")` для cross-field, не deprecated `field_validator(values=)`
- Type hints обязательны для public APIs
- Docstrings: Google-style для классов и публичных функций
- `from __future__ import annotations` где applicable (forward refs)

**Format:**
- Black (line length 88)
- isort (alphabetical imports, grouped stdlib/3rd-party/local)
- Ruff для linting
- mypy strict mode для math layer

**Example (good):**
```python
from datetime import date
from pydantic import BaseModel, Field, model_validator
from typing_extensions import Self

class RecipientAnchorsV1(BaseModel):
    """Recipient brand anchors для transfer modeling."""

    schema_version: Literal["1.0"] = "1.0"
    market_size_rub: float = Field(gt=0)
    launch_date: date

    @model_validator(mode="after")
    def validate_launch_date_future(self) -> Self:
        if self.launch_date < date.today():
            raise ValueError("launch_date must be in future or today")
        return self
```

**Anti-patterns:**
- ❌ Pydantic v1 `Config` class - use `model_config = ConfigDict(...)`
- ❌ `dict()` method - use `model_dump()`
- ❌ `parse_obj()` - use `model_validate()`
- ❌ Direct mutation of validated model - use `model_copy(update={...})`

### Svelte (Svelte 5 runes era)

**Conventions:**
- **Svelte 5 runes:** `$state`, `$derived`, `$effect` - не legacy `$:`
- TypeScript обязателен (`<script lang="ts">`)
- Stores - declared с `$state` + exported
- Component props через `$props()` rune

**Example:**
```svelte
<script lang="ts">
  import type { RecipientAnchorsV1 } from "$lib/types/recipientAnchors";

  let { anchors = $bindable() }: { anchors: RecipientAnchorsV1 } = $props();

  let isValid = $derived(anchors.market_size_rub > 0);

  $effect(() => {
    console.log("anchors changed:", anchors);
  });
</script>
```

**Format:**
- Prettier с svelte plugin
- ESLint с svelte plugin

### Rust (Tauri + WASM)

**Conventions:**
- Edition 2021
- `cargo fmt` для formatting
- `cargo clippy --all-targets -- -D warnings`
- Error types: thiserror для library code, anyhow для applications
- Async runtime: tokio (Tauri requirement)

### General

- **Russian + English mix:** comments in Russian для project-specific business logic, English для technical / architectural
- **No em dashes (—):** use hyphen `-` everywhere (per `feedback_no_em_dash.md`)
- **Magic numbers** в named constants
- **No commented-out code** - delete or use git history

---

## Commit Messages

**Format:** Conventional Commits style:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: new feature
- `fix`: bug fix
- `docs`: documentation only
- `refactor`: code change that не fixes bug, не adds feature
- `test`: adding tests
- `chore`: maintenance (deps, build config)
- `perf`: performance improvement
- `style`: formatting only

**Scopes:**
- `engines`: math layer
- `ui`: Svelte components
- `tauri`: Rust shell
- `schemas`: JSON Schema / Pydantic
- `tests`: test infrastructure
- `docs`: documentation
- `ci`: CI/CD

**Example:**
```
feat(engines): add multi-proxy hierarchical transfer

Implement true hierarchical Bayesian с N>=2 proxies per ADR-003.
Avoids mathematical degeneracy of single-proxy hierarchical (audit F4).

Closes Sprint B3 deliverable.
```

---

## PR Process

### Before opening PR

- [ ] Tests pass locally (`pytest` + `npm test`)
- [ ] Linters pass (`ruff`, `mypy`, `eslint`)
- [ ] Coverage не decreased (CI gate)
- [ ] Performance benchmarks не regress (CI gate)
- [ ] Documentation updated если applicable
- [ ] CHANGELOG.md entry (если customer-facing change)
- [ ] ADR создана если architectural decision

### PR template

```markdown
## Summary
<one-paragraph description>

## Sprint context
B0.5 / B1 / etc.

## Changes
- Bullet list of changes

## Tests
- [ ] Unit tests added
- [ ] Integration tests added
- [ ] Manual testing performed
- [ ] Performance budgets met

## Documentation
- [ ] Updated relevant .md files
- [ ] ADR created (если decision)
- [ ] Memory updated (если cross-product)

## Related
- Closes Sprint deliverable: ...
- ADR: ADR-NNN-xxx (если applicable)
- Audit findings addressed: F##
```

### Review process

- **Маша + Антон** review каждый PR
- **Math changes:** require math layer test pass + property-based check
- **Schema changes:** require BC test pass (Sprint B0.5 corpus)
- **UI changes:** require visual review (screenshots в PR)
- **Performance regression:** block merge if > 10% slower

### Merge strategy

- Squash and merge для feature branches
- Merge commit для release branches (preserve history)
- No force push to main (per Aurora team policy)

---

## ADR Process

When **architectural decision** needed:

1. Create `ADR-NNN-short-name.md` в `03_Architecture/decisions/` (template: `ADR_TEMPLATE.md`)
2. Status starts "Proposed"
3. Discuss с Антоном (Discovery call или Slack)
4. Update status: "Accepted" or "Rejected"
5. ADRs **immutable** после "Accepted"
6. Subsequent changes - new ADR с "Supersedes ADR-NNN" reference

When ADR needed (heuristic):
- Schema changes
- Storage layer choices
- Math algorithm decisions с trade-offs
- Major dependency additions
- Cross-product API changes
- Security model changes

When ADR NOT needed:
- Bug fixes
- Refactoring (no behavior change)
- Documentation updates
- Test additions

---

## Test Discipline

### Test pyramid (per TEST_STRATEGY.md)

- 80% unit
- 15% integration
- 5% E2E

### Math layer specific

- Property-based testing (Hypothesis) - math invariants
- Reference comparison - vs Robyn / pymc / Stan
- Coverage 70-80% (stochastic outputs)

### Naming convention

```python
def test_<what>_<expected_behavior>():
    ...

def test_<what>_when_<condition>_then_<result>():
    ...
```

### AAA pattern

```python
def test_extract_priors_returns_shape_only():
    # Arrange
    proxy_model = build_test_model()

    # Act
    priors = extract_proxy_priors(proxy_model)

    # Assert
    assert "adstock_decay" in priors
    assert "beta_magnitude" not in priors
```

---

## Documentation Discipline

### When to update docs

- **Always:** when adding / removing / renaming public API
- **Always:** when changing behavior visible к users
- **Always:** when adding ADR (cross-link)
- **Sometimes:** internal refactor если affects future contributors

### Where docs live

- **`00_Overview/`** - high-level (PRINCIPLES, ROADMAP, BOUNDARIES)
- **`02_Data_Spec/`** - schemas + data formats
- **`03_Architecture/`** - implementation details + ADRs
- **`05_Sessions/`** - session logs (immutable history)
- **`06_References/`** - external sources, INSTALL, CONTRIBUTING
- **Memory** - cross-product context

### Markdown conventions

- One sentence per line (better diffs)
- ASCII tables (no fancy unicode)
- Code blocks с language hints (```python, ```svelte, etc.)
- Cross-references explicit: `см. PRINCIPLES.md Section X`

---

## Security & Privacy Discipline

- **NEVER commit:** API keys, license keys, client data, .env files
- **NEVER log:** raw client values (use ranges / hashes)
- **ALWAYS:** privacy review для new telemetry / metrics (per OBSERVABILITY.md)
- **CI checks:** secret scanning (truffleHog or similar)

---

## Performance Discipline

- Performance budgets enforced в CI (per PERFORMANCE_BUDGETS.md)
- Benchmark suite runs per PR
- Budget exceeded → require approval
- Memory leaks = unacceptable (CI tracks RSS)

---

## Release Process

### Version numbering (semver)

- **Major (X.0.0):** breaking changes к public API / schema
- **Minor (1.X.0):** new features, additive
- **Patch (1.0.X):** bug fixes only

### Release cadence

- **Major:** every 6 months
- **Minor:** every 4-6 weeks (Sprint completion)
- **Patch:** every 1-2 weeks (bug rolls)
- **Security:** immediate (within 24-48h)

### Release checklist

- [ ] All tests green
- [ ] CHANGELOG updated
- [ ] Version bumped в Cargo.toml + package.json + pyproject.toml
- [ ] Tag created (`v1.4.0`)
- [ ] NSIS installer built
- [ ] SHA-256 verified
- [ ] GitHub release published
- [ ] Supabase app_versions updated
- [ ] rosst-updates latest.json updated
- [ ] PASHE_IT.MD / IT-doc updated если applicable
- [ ] Email customers (major versions only)

---

## Related Documents

- `INSTALL.md` - dev environment setup
- `../03_Architecture/TEST_STRATEGY.md` - testing approach
- `../03_Architecture/PERFORMANCE_BUDGETS.md` - budget enforcement
- `../03_Architecture/ADR_TEMPLATE.md` - ADR creation
- Memory: `feedback_no_em_dash.md` - hyphen-only style rule
- Memory: `feedback_econometrica_patterns.md` - reusable patterns
