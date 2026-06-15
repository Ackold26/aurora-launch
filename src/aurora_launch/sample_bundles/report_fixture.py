"""Sample Launch Forecast report fixture — REAL forecast data for the report engine.

Produces a deterministic, end-to-end forecast (proxy → anchors → orchestrator)
across the 12 / 26 / 52-week horizons plus representative project metadata
(similarity, anchors, proxy identity). This is the input the Sprint B4 report
engine renders — and, run as a script, it doubles as an E2E smoke of the forecast
pipeline (`python -m aurora_launch.sample_bundles.report_fixture`).

The proxy mirrors the pilot demo (Кагоцел-anonymized OTC antiviral); the recipient
is a premium-tier launch (Венарус-like). Numbers are representative, not a real
engine-fit — the report engine only needs the SHAPE + plausible magnitudes here.
The forecast itself IS a real orchestrator run (pure-transfer baseline, n_recipient=0).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from aurora_launch.engines.launch_orchestrator import LaunchOrchestrator, make_proxy_bundle
from aurora_launch.engines.pure_transfer_engine import RecipientAnchors

# Horizons the report covers (weeks). 52 is presented monthly in the report, but
# the fixture runs weekly periods and the renderer down-samples for display.
_HORIZONS = (12, 26, 52)

# Media channels carried by the proxy posterior.
_MEDIA_COLS = ("tv", "digital")


def _proxy_bundle():
    """A Кагоцел-anonymized OTC proxy posterior (deterministic, seed=42).

    Mirrors the orchestrator integration-test posterior so the forecast is a real,
    validated run — not a hand-faked curve.
    """
    rng = np.random.default_rng(42)
    n_samples = 5000
    beta_means = (0.20, 0.10)
    beta_stds = (0.05, 0.02)
    alpha_values = (2.0, 1.5)
    gamma_values = (100.0, 50.0)
    decay_values = (0.5, 0.2)

    def _draw(loc: float, scale: float) -> np.ndarray:
        return rng.normal(loc=loc, scale=scale, size=n_samples)

    return make_proxy_bundle(
        posterior_samples={
            "media_betas": np.array([_draw(beta_means[i], beta_stds[i]) for i in range(2)]),
            "alphas": np.array([_draw(alpha_values[i], 0.1) for i in range(2)]),
            "gammas": np.array([_draw(gamma_values[i], 5.0) for i in range(2)]),
            "adstock_decay": np.array(
                [np.clip(_draw(decay_values[i], 0.05), 0.0, 1.0) for i in range(2)]
            ),
        },
        media_cols=list(_MEDIA_COLS),
        normalization={"y_mean": 500_000.0, "y_std": 50_000.0},
        config={},
        proxy_brand_id="KAG-2024-anonymized",
        n_proxy_observations=104,
    )


def _anchors(horizon: int) -> RecipientAnchors:
    """Premium-tier launch recipient: ramping share + distribution, +20% price."""
    # Distribution ramps 30% → 90% over the first ~12 periods, then plateaus.
    dist = [min(0.30 + 0.05 * t, 0.90) for t in range(horizon)]
    # Planned share ramps 2% → 8% over the horizon.
    share = [min(0.02 + 0.005 * t, 0.08) for t in range(horizon)]
    return RecipientAnchors(
        market_size=500_000_000.0,
        market_size_cv=0.12,
        planned_share_trajectory=share,
        distribution_trajectory=dist,
        pricing_index=1.20,
        elasticity=0.5,
        seasonality=[1.0] * horizon,
    )


def _spend_plan(horizon: int) -> dict[str, list[float]]:
    return {"tv": [200.0] * horizon, "digital": [80.0] * horizon}


def _run_horizon(horizon: int) -> dict[str, Any]:
    """Run a real orchestrator forecast for one horizon → per-period points."""
    result = LaunchOrchestrator().forecast_recipient(
        proxy=_proxy_bundle(),
        anchors=_anchors(horizon),
        spend_plan=_spend_plan(horizon),
        horizon_periods=horizon,
        granularity="weekly",
        n_recipient=0,
    )
    points = [
        {
            "period": i + 1,
            "mean": float(p.point_forecast),
            "ci_lower": float(p.ci_lower),
            "ci_upper": float(p.ci_upper),
        }
        for i, p in enumerate(result.forecast.points)
    ]
    total = sum(pt["mean"] for pt in points)
    # CI width as % of total (mean of per-period relative half-widths).
    rel_widths = [
        (pt["ci_upper"] - pt["ci_lower"]) / (2.0 * pt["mean"])
        for pt in points
        if pt["mean"] > 0
    ]
    ci_pct = round(100.0 * (sum(rel_widths) / len(rel_widths)), 1) if rel_widths else 0.0
    return {
        "horizon_weeks": horizon,
        "mode": result.engine_config.mode.value,
        "methodology_signature": result.methodology_signature,
        "warnings": list(result.warnings),
        "points": points,
        "total_forecast": round(total, 2),
        "ci_pct": ci_pct,
    }


# Representative project metadata the forecast engine does NOT compute — the
# report reads it from the project (similarity, proxy identity, tier verdict).
def _metadata() -> dict[str, Any]:
    dimensions = {
        "Категория": 1.00,
        "Ценовой tier": 0.50,
        "Размер бренда": 0.30,
        "Дистрибуция": 1.00,
        "Медиа-зрелость": 0.50,
        "Lifecycle": 0.30,
    }
    # Aggregate is the WEIGHTED similarity-framework output (SIMILARITY_FRAMEWORK.md),
    # not a naive mean of the dimensions — matches spec §3.2's "S = 0.70 (Medium)".
    aggregate = 0.70
    return {
        "recipient_brand": "Образец Премиум (демо)",
        "proxy_brand": "KAG-2024-anonymized",
        "proxy_category": "OTC.cold_flu.antiviral",
        "proxy_data_period": "DSM 2022-01 — 2024-12 (36 месяцев)",
        "similarity": {
            "dimensions": dimensions,
            "aggregate": aggregate,  # 0.60 → Medium
            "verdict": "Medium",
            "tier": "silver",
        },
        "uncertainty_decomposition": {
            "proxy": 0.30,
            "transfer": 0.40,
            "anchor": 0.15,
            "sampling": 0.15,
        },
        "inflation_factor": 1.5,
    }


def build_sample_forecast_fixture() -> dict[str, Any]:
    """The full report input: real multi-horizon forecast + project metadata."""
    horizons = [_run_horizon(h) for h in _HORIZONS]
    return {
        "schema": "launch_forecast_report_fixture_v1",
        "metadata": _metadata(),
        "horizons": horizons,
        "summary": {
            f"total_forecast_{h['horizon_weeks']}w": h["total_forecast"] for h in horizons
        }
        | {f"ci_pct_{h['horizon_weeks']}w": h["ci_pct"] for h in horizons},
    }


def _main() -> None:
    import json

    fx = build_sample_forecast_fixture()
    s = fx["summary"]
    print("Launch Forecast report fixture — E2E forecast smoke")
    print("-" * 52)
    for h in fx["horizons"]:
        print(
            f"  {h['horizon_weeks']:>2}w  mode={h['mode']:<14} "
            f"total={h['total_forecast']:>16,.0f} ₽  ±{h['ci_pct']}%  "
            f"points={len(h['points'])}"
        )
    print("-" * 52)
    print(f"  similarity S={fx['metadata']['similarity']['aggregate']} "
          f"({fx['metadata']['similarity']['verdict']})")
    print(json.dumps(s, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _main()
