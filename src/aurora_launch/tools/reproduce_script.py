"""Phase Magic M-09: Generate Python script that reproduces a forecast bit-exact.

Customer pain: "Я не понимаю как Aurora получила 1 240 000. Хочу проверить
сам в Python — но как?"

M-09 answer: одна кнопка → copy-paste Python script. Customer runs script
с saved bundle file → identical forecast. Open transparency + reproducibility
сертификат + academic credibility = category-defining feature.

Output template:
    1. Aurora Launch + Python deps version header
    2. Imports
    3. Bundle path placeholder (user fills)
    4. Proxy posterior deserialization
    5. Recipient anchors from inputs
    6. Orchestrator call с exact params
    7. Print per-period forecast + CI

Customer needs:
    - aurora-launch installed (`pip install aurora-launch`)
    - .aurora bundle file (exported from app via "Save bundle")
    - This script run в Python 3.11+

Per master-plan §④ M-09 + §⑧ "Reproduce-this-forecast Python code generator".
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from aurora_launch import __version__


def generate_reproduce_script(
    *,
    bundle_path: str,
    anchors: dict[str, Any],
    spend_plan: dict[str, list[float]],
    horizon_periods: int,
    granularity: str = "monthly",
    coverage_target: float = 0.95,
    n_recipient: int = 0,
    seed: int = 42,
) -> str:
    """Generate executable Python script reproducing the forecast.

    Returns a self-contained script (string) that customer can save к .py
    file и run с only Aurora Launch + their .aurora bundle file.

    Args:
        bundle_path: path к .aurora bundle file (customer-side path,
            relative or absolute). Script will reference это literally.
        anchors: RecipientAnchors fields dict (market_size, market_size_cv,
            planned_share_trajectory, distribution_trajectory, pricing_index,
            elasticity, seasonality). Same shape as passed to
            LaunchOrchestrator.forecast_recipient.
        spend_plan: per-channel spend dict {channel_id: [period values]}.
        horizon_periods: int — forecast horizon.
        granularity: 'monthly' | 'weekly'.
        coverage_target: CI coverage (0.80/0.90/0.95/0.99).
        n_recipient: observed periods count (for mode selection by router).
        seed: random seed для deterministic reproduction.

    Returns:
        Python script source as multiline string. Includes shebang +
        encoding declaration + structured imports. Triple-quoted comments
        document intent.
    """
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # Pretty-print params для readability в generated script
    anchors_repr = json.dumps(anchors, ensure_ascii=False, indent=8)
    spend_plan_repr = json.dumps(spend_plan, ensure_ascii=False, indent=8)
    # B-1 security: bundle_path как Python string literal, не raw insertion.
    # json.dumps даёт valid Python-совместимый string literal с escaped
    # quotes/backslashes/newlines. Защита от injection вида:
    #   bundle_path='x"); import os; os.system("..."); Path("y'
    # которая иначе вышла бы за пределы строки и стала executable Python.
    bundle_path_literal = json.dumps(bundle_path)
    version_literal = json.dumps(__version__)

    return f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aurora Launch Planner — reproducible forecast script.

Generated: {timestamp}
Aurora Launch version: {__version__}

Reproducibility guarantee: this script + the referenced .aurora bundle
produce identical forecast (same point_forecast + CI bounds) when run on
any machine with `pip install aurora-launch=={__version__}`.

Run:
    python reproduce_forecast.py

If you change spend_plan, anchors, OR horizon_periods, you get a different
forecast — by design (same model, different inputs).

If the forecast differs from the one в the original Aurora Launch session,
something is wrong: either the bundle was tampered с, OR Aurora Launch
version mismatch. Check `aurora-launch --version`.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Verify Aurora Launch version (warn if mismatch)
try:
    from aurora_launch import __version__ as _av
except ImportError:
    print("ERROR: aurora-launch not installed. Run: pip install aurora-launch")
    sys.exit(1)

EXPECTED_VERSION = {version_literal}
if _av != EXPECTED_VERSION:
    print(
        f"WARNING: Aurora Launch version mismatch. "
        f"Script generated with {{EXPECTED_VERSION}}, you have {{_av}}. "
        f"Forecast may differ slightly."
    )


from aurora_launch.engines.bundle_streaming import open_lazy
from aurora_launch.engines.launch_orchestrator import (
    LaunchOrchestrator,
    make_proxy_bundle,
)
from aurora_launch.engines.pure_transfer_engine import RecipientAnchors
from aurora_launch.persistence.safe_serializer import deserialize


# ---------------------------------------------------------------------------
# Bundle path — edit if your file is elsewhere
# ---------------------------------------------------------------------------

BUNDLE_PATH = Path({bundle_path_literal})

if not BUNDLE_PATH.exists():
    print(f"ERROR: bundle file not found: {{BUNDLE_PATH}}")
    print(
        "Export bundle from Aurora Launch via Cmd+S, copy file path к BUNDLE_PATH."
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Load proxy posterior from bundle (deserialised msgpack + Ed25519 verified)
# ---------------------------------------------------------------------------

with open_lazy(BUNDLE_PATH) as bundle:
    # Find posterior blob (entry name may vary; common: "proxy_posterior.msgpack")
    posterior_entry = None
    for entry in bundle.list_entries():
        if "posterior" in entry.lower() or "proxy" in entry.lower():
            posterior_entry = entry
            break
    if posterior_entry is None:
        print("ERROR: no proxy posterior entry в bundle")
        sys.exit(2)
    posterior_bytes = bundle.get_bytes(posterior_entry)

posterior_data = deserialize(posterior_bytes)

proxy = make_proxy_bundle(
    posterior_samples=posterior_data["posterior_samples"],
    media_cols=posterior_data["media_cols"],
    normalization=posterior_data.get("normalization", {{}}),
    config=posterior_data.get("config", {{}}),
    n_proxy_observations=int(posterior_data.get("n_proxy_observations", 0)),
)


# ---------------------------------------------------------------------------
# Recipient anchors (from original Aurora Launch session)
# ---------------------------------------------------------------------------

anchors = RecipientAnchors(
    **{anchors_repr}
)


# ---------------------------------------------------------------------------
# Spend plan (from original Aurora Launch session)
# ---------------------------------------------------------------------------

spend_plan = {spend_plan_repr}


# ---------------------------------------------------------------------------
# Run forecast (identical к Aurora Launch UI invocation)
# ---------------------------------------------------------------------------

orchestrator = LaunchOrchestrator()
result = orchestrator.forecast_recipient(
    proxy=proxy,
    anchors=anchors,
    spend_plan=spend_plan,
    horizon_periods={horizon_periods},
    granularity="{granularity}",
    coverage_target={coverage_target!r},
    n_recipient={n_recipient},
)


# ---------------------------------------------------------------------------
# Print per-period forecast — verify by eye OR programmatic compare
# ---------------------------------------------------------------------------

if result.forecast is None:
    print("ERROR: forecast returned None (bias check hard-fail?)")
    print("Warnings:", result.warnings)
    sys.exit(2)

print(f"=" * 70)
print(f"Aurora Launch Reproducibility Check")
print(f"=" * 70)
print(f"Mode:       {{result.engine_config.mode.value}}")
print(f"Signature:  {{result.methodology_signature}}")
print(f"Granularity:{granularity!r}")
print(f"Horizon:    {{len(result.forecast.points)}} periods")
print(f"Coverage:   {coverage_target!r}")
print()
print(f"{{'Period':<8}} {{'Point':<15}} {{'CI lower':<15}} {{'CI upper':<15}}")
print(f"-" * 60)
for p in result.forecast.points:
    print(
        f"{{p.period_index:<8}} "
        f"{{p.point_forecast:<15.2f}} "
        f"{{p.ci_lower:<15.2f}} "
        f"{{p.ci_upper:<15.2f}}"
    )

if result.warnings:
    print()
    print("Warnings:")
    for w in result.warnings:
        print(f"  - {{w}}")
'''


def reproduce_script_to_filename(timestamp: str | None = None) -> str:
    """Suggest filename for the generated script (used by UI Save As)."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"aurora_reproduce_{timestamp}.py"
