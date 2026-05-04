# Aurora Launch - Developer Setup Guide

**Status:** v1.0 (2026-05-04) - prep document, will be refined during Sprint B0.5 / B1
**Audience:** new developer onboarding на Aurora Launch project

## Prerequisites

### System

- **OS:** Windows 10/11 64-bit (Aurora Launch primary target Phase B)
- **CPU:** 8+ cores recommended (Bayesian MCMC)
- **RAM:** 16GB+ recommended (training requires ~2GB peak)
- **Disk:** 5GB+ free для dependencies + dev artifacts

### Toolchains

- **Python:** 3.11+ (для NumPyro JAX support, Pydantic v2)
- **Node.js:** 20.x LTS (для Svelte 5 + Tauri)
- **Rust:** stable 1.75+ (для Tauri shell + WASM module)
- **Git:** any recent version
- **Visual Studio Build Tools 2022** (для JAX speedups - см. Aurora Econometrica session 4 memory)
  - Workload "Desktop development with C++"
  - vswhere.exe + vcvars64.bat needed для NumPyro acceleration

### IDE Recommendations

- **VS Code** с extensions:
  - Python
  - Svelte for VS Code
  - rust-analyzer
  - Pydantic Helper (для schemas)
  - Even Better TOML
- Alternative: PyCharm Professional + WebStorm

---

## Initial Setup

### 1. Clone репо (TBD git location after OQ003 decision)

```powershell
git clone <aurora-launch-repo-url> Aurora_Launch
cd Aurora_Launch
```

### 2. Python sidecar setup

```powershell
cd sidecar
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.lock  # pinned versions
pip install -e .  # editable install для dev
```

### 3. Node frontend setup

```powershell
cd ..\src
npm ci  # use lockfile (deterministic install)
```

### 4. Rust Tauri shell

```powershell
cd ..\src-tauri
cargo build  # downloads dependencies
```

### 5. WASM module (similarity calculator - Sprint B2)

```powershell
cd ..\wasm-similarity
wasm-pack build --target web --release
```

---

## Running в Dev Mode

### Backend sidecar standalone:

```powershell
cd sidecar
.venv\Scripts\Activate.ps1
python -m aurora_launch.main --port 5180  # dev port
```

Health check: `http://localhost:5180/health`

### Frontend dev server:

```powershell
cd src
npm run dev  # Vite dev server, hot reload
```

### Full Tauri dev mode:

```powershell
cd ..  # project root
npm run tauri dev  # builds Rust shell + connects к Python sidecar
```

---

## Testing

### Python tests (pytest):

```powershell
cd sidecar
.venv\Scripts\Activate.ps1
pytest -v                                    # all tests
pytest -v -m "not slow"                      # skip slow (MCMC) tests
pytest -v --cov=aurora_launch --cov-report=html  # с coverage
pytest -n auto                               # parallel
```

### Frontend tests (Vitest):

```powershell
cd src
npm test           # watch mode
npm run test:run   # single run
npm run test:coverage  # с coverage
```

### Property-based tests (Hypothesis):

```powershell
cd sidecar
pytest tests/property/ -v --hypothesis-show-statistics
```

### Performance benchmarks:

```powershell
pytest tests/performance/ -v -m performance --benchmark
# Compares to baseline; fails if > 25% regression
```

### E2E (Tauri WebDriver - alpha):

```powershell
# Requires tauri-driver installed
cargo install tauri-driver
npm run test:e2e
```

---

## Build Production

### NSIS Windows installer:

```powershell
npm run tauri build
# Output: src-tauri\target\release\bundle\nsis\Aurora-Launch_X.Y.Z_x64-setup.exe
```

Build steps:
1. `npm run build` - Svelte production build
2. `cargo build --release` - Tauri shell
3. PyInstaller bundles Python sidecar (см. Aurora Econometrica V29 memory для PyInstaller flags)
4. NSIS installer compiles all together
5. SHA-256 hash auto-computed

---

## Common Pitfalls

### JAX / NumPyro slow on Windows

**Symptom:** training takes 60s instead of 20s.

**Fix:** install Visual Studio Build Tools 2022, ensure vswhere.exe finds vcvars64.bat. Aurora Econometrica session 4 documented this.

### "WebView2 not found"

**Symptom:** Tauri app не starts.

**Fix:** install Microsoft Edge WebView2 Runtime (auto-installed на Windows 11, но Windows 10 needs manual install).

### Schema migration tests fail

**Symptom:** `test_v1_to_v3_migration_preserves_data` fails after schema change.

**Fix:** add corresponding entry в SchemaRegistry + migration function. См. `engines/schema_registry.py`.

### "Cannot find module 'aurora_platform_core'"

**Symptom:** Python import error.

**Fix:** Phase A platform foundation должна быть completed первой. Aurora Launch dev requires `aurora-platform-core` package installed:
```powershell
pip install aurora-platform-core  # from internal Aurora private PyPI
```

### Sidecar exe not refreshed after Python changes

**Symptom:** changes к Python code не reflect в Tauri app.

**Fix:** Aurora pattern - `npm run tauri build` does NOT rebuild Python sidecar. Run `python tools/build_sidecar.py` separately when Python files changed. См. memory `feedback_sidecar_rebuild_required.md`.

---

## Project Structure

```
Aurora_Launch/
├── sidecar/                  # Python backend
│   ├── aurora_launch/
│   │   ├── engines/          # math layer
│   │   │   ├── launch_adapt.py
│   │   │   ├── launch_validators.py
│   │   │   ├── single_proxy_transfer.py
│   │   │   ├── multi_proxy_hierarchical.py
│   │   │   └── ...
│   │   ├── routes/           # FastAPI endpoints
│   │   ├── data_adapters/    # DSM/Mediascope parsers
│   │   └── main.py
│   ├── tests/
│   ├── requirements.lock
│   └── pyproject.toml
├── src/                      # Svelte frontend
│   ├── lib/
│   │   ├── components/
│   │   ├── stores/
│   │   ├── types/            # auto-gen from JSON Schema
│   │   └── api/
│   ├── routes/
│   └── package.json
├── src-tauri/                # Rust Tauri shell
│   ├── src/
│   ├── Cargo.toml
│   └── tauri.conf.json
├── wasm-similarity/          # Rust → WASM module
│   ├── src/
│   └── Cargo.toml
├── 02_Data_Spec/             # JSON Schemas (SSoT)
│   └── *.schema.json
├── tools/                    # build / migration / utility scripts
└── tests/
    ├── unit/
    ├── integration/
    ├── e2e/
    └── property/
```

---

## Related Documents

- `CONTRIBUTING.md` - code style + PR process
- `../03_Architecture/REUSE_FROM_ECONOMETRICA.md` - shared engines layer
- `../03_Architecture/TEST_STRATEGY.md` - testing approach
- Memory: `project_econometrica_session4.md` - JAX setup pattern
- Memory: `feedback_sidecar_rebuild_required.md` - sidecar build gotcha
