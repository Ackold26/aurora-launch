# PyInstaller spec для aurora-sidecar binary (Block 4 D1).
#
# Build с CI release pipeline:
#   pip install pyinstaller
#   pyinstaller packaging/aurora-sidecar.spec --distpath src-tauri/binaries/
#
# Output binary placed в `src-tauri/binaries/aurora-sidecar(.exe)`. Tauri
# externalBin entry в tauri.conf.json picks it up automatically (suffixed
# с -<target_triple> per platform).
#
# Cross-platform: Windows + macOS + Linux. PyInstaller spec only — actual
# cross-compile is platform-specific (build на каждой target separately
# in CI matrix).

# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

block_cipher = None

ROOT = Path(SPECPATH).parent
ENTRY = ROOT / "src" / "aurora_launch" / "sidecar" / "__main__.py"

a = Analysis(
    [str(ENTRY)],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[],
    # Force-collect packages с lazy / dynamic imports — INV-02 lazy import
    # protection. Numpy / scipy bring native libs PyInstaller may otherwise
    # miss.
    hiddenimports=[
        "aurora_launch",
        "aurora_launch.engines",
        "aurora_launch.engines.bundle_container",
        "aurora_launch.engines.bundle_streaming",
        "aurora_launch.engines.bundle_persistence",
        "aurora_launch.engines.bundle_lock",
        "aurora_launch.engines.bundle_manifest",
        "aurora_launch.engines.format_adapters",
        "aurora_launch.engines.format_adapters.dsm_v2023",
        "aurora_launch.engines.format_adapters.dsm_v2024",
        "aurora_launch.engines.format_adapters.dsm_v2025",
        "aurora_launch.engines.format_adapters.mediascope_adex",
        "aurora_launch.engines.format_adapters.mediascope_tv_index",
        "aurora_launch.engines.format_adapters.registry",
        "aurora_launch.engines.launch_validate",
        "aurora_launch.engines.launch_forecast",
        "aurora_launch.engines.launch_conformal",
        "aurora_launch.engines.similarity_calculator",
        "aurora_launch.schemas",
        "aurora_launch.schemas.adaptation",
        "aurora_launch.schemas.proxy",
        "aurora_launch.schemas.bundle",
        # Mini-audit M2-PYINSTALLER-1 fix: previously missing — used by
        # format_adapters/registry::FormatAdapterContract type imports.
        "aurora_launch.schemas.synthetic_corpus",
        # Schema modules used downstream by launch_forecast / launch_validate
        # (not currently sidecar-direct, but transitive). Eager-include для
        # PyInstaller robustness.
        "aurora_launch.schemas.forecast",
        "aurora_launch.sidecar.auth",
        "aurora_launch.sidecar.events",
        "aurora_launch.sidecar.methods",
        "aurora_launch.sidecar.protocol",
        "aurora_launch.sidecar.server",
        "rfc8785",
        "pydantic",
        # Mini-audit M2-PYINSTALLER-1: pydantic v2 has compiled Rust submodule
        # `pydantic_core` which PyInstaller's bundled hook may не detect on
        # all platforms. Force include для cross-platform reliability.
        "pydantic_core",
        "numpy",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude heavy ML packages until Phase A integration: PyTorch / TF
        # not used by core sidecar; Phi-3.5 download path will load lazily.
        "torch",
        "tensorflow",
        # Mini-audit M2-PYINSTALLER-2 / HIGH-4: dev tooling MUST NOT bundle
        # into production sidecar binary. CI release pipeline now does
        # `pip uninstall pytest hypothesis ruff mypy` before pyinstaller
        # invocation, but excludes here are belt-and-suspenders в случае
        # ad-hoc local builds use `pip install -e ".[dev]"`.
        "pytest",
        "_pytest",
        "pytest_cov",
        "hypothesis",
        "ruff",
        "mypy",
        "mypy_extensions",
        "pyinstaller",
        # Build/test tools rarely needed at runtime
        "pip",
        "setuptools",
        "wheel",
        # IDE / debugger imports if dev пуско установил
        "ipykernel",
        "jupyter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

import sys as _sys

# POST_PILOT_BACKLOG M2-PYINSTALLER-3 close (2026-05-10): persistent
# runtime_tmpdir per-user vs default None (extracts к OS temp at every launch).
# Default None → 1-2s cold start on Windows + repeated extraction churn.
# Setting к user-specific path keeps extracted bundle warm между launches.
# Path uses %LOCALAPPDATA% on Windows / ~/.cache on POSIX (XDG-compatible).
_RUNTIME_TMPDIR_WIN = r"%LOCALAPPDATA%\Aurora Launch\sidecar-runtime"
_RUNTIME_TMPDIR_POSIX = "~/.cache/aurora-launch/sidecar-runtime"
_RUNTIME_TMPDIR = _RUNTIME_TMPDIR_WIN if _sys.platform == "win32" else _RUNTIME_TMPDIR_POSIX

# POST_PILOT_BACKLOG M2-PYINSTALLER-5 close (2026-05-10): Windows .exe metadata
# (Company / Description / Copyright). Cosmetic для pilot trust signals.
_VERSION_FILE = str(ROOT / "packaging" / "version_info_win.txt") if _sys.platform == "win32" else None

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="aurora-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX compression sometimes triggers AV — disable
    runtime_tmpdir=_RUNTIME_TMPDIR,
    console=True,  # IPC через stdin/stdout — must be console binary
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=_VERSION_FILE,
)
