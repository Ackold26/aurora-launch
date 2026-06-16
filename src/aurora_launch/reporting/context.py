"""forecast → report context adapter (the `data → context object` pattern).

Turns a forecast fixture/result + project metadata into the neutral 8-section
report context the Sprint B4 renderer feeds to Core `aurora_reporting` primitives.
Core-API-independent: it produces the DATA (headline, table rows, chart-data
arrays); the renderer wires that data to Core's cone/radar/pie/table primitives.

Every client-facing string is passed through `copy.assert_client_safe` so a
forbidden phrase (spec §4.3) can never reach a deliverable.
"""

from __future__ import annotations

from typing import Any

from aurora_launch.reporting import copy

# What transfers / what does not — static methodology content (spec §1.4 / §4.1).
_TRANSFERS = [
    "Adstock decay (по каналам)",
    "Hill saturation shape",
    "Категорийная сезонность (52-недельный паттерн)",
    "Долгосрочный trend slope",
]
_NOT_TRANSFERS = [
    "β coefficients (масштаб)",
    "Baseline продаж",
    "ROI levels",
    "Cross-category competitive controls",
]
_RECONSTRUCTED = [
    "Magnitude calibration (market_size × planned_share × distribution × pricing)",
    "β priors (scaled от proxy effectiveness × recipient size)",
]

# Academic references (subset for the slide; full list in the Methodology Cert).
_REFERENCES = [
    "Robyn (Meta) — facebookexperimental.github.io/Robyn",
    "Konstantinopoulos & Massaro (2014) — ESS",
    "Tibshirani et al. (2019) — Conformal Prediction под shift",
    "Gelman et al. (2013) — Bayesian Data Analysis",
]

# Formulas (rendered as display math by the renderer).
_FORMULAS = {
    "adstock": r"A_t = X_t + \lambda \cdot A_{t-1}",
    "hill": r"H(x) = \beta \cdot x^{\gamma} / (k^{\gamma} + x^{\gamma})",
}


def _key_metrics_rows(horizons: list[dict[str, Any]], tier_label: str) -> list[dict[str, Any]]:
    """Key-metrics table rows (spec §2.2): period × total × CI × tier."""
    return [
        {
            "period_weeks": h["horizon_weeks"],
            "total_rub": h["total_forecast"],
            "total_display": copy.format_rub_millions(h["total_forecast"]),
            "ci_pct": h["ci_pct"],
            "tier_label": tier_label,
        }
        for h in horizons
    ]


def _weekly_breakdown(horizon: dict[str, Any]) -> list[dict[str, Any]]:
    """Weekly breakdown table rows (spec §5.2): period × mean × CI bands."""
    return [
        {
            "week": pt["period"],
            "mean": pt["mean"],
            "ci_lower": pt["ci_lower"],
            "ci_upper": pt["ci_upper"],
        }
        for pt in horizon["points"]
    ]


def _channel_decomposition(horizon: dict[str, Any]) -> dict[str, Any] | None:
    """§5.3 per-channel contribution + baseline per period (engine now surfaces it)."""
    pts = horizon["points"]
    if not pts or "channels" not in pts[0]:
        return None
    channel_ids = list(pts[0]["channels"])
    return {
        "periods": [pt["period"] for pt in pts],
        "baseline": [pt["baseline"] for pt in pts],
        "channels": {cid: [pt["channels"][cid] for pt in pts] for cid in channel_ids},
    }


def _forecast_section(horizon: dict[str, Any]) -> dict[str, Any]:
    """One forecast horizon (spec §1.5–1.7): cone chart-data + weekly table +
    per-channel decomposition (§5.3) now that the engine surfaces it. The §5.4
    sensitivity tornado is a project-level analysis (see `build_report_context`)."""
    cone = [
        {"x": pt["period"], "mean": pt["mean"], "lo": pt["ci_lower"], "hi": pt["ci_upper"]}
        for pt in horizon["points"]
    ]
    return {
        "horizon_weeks": horizon["horizon_weeks"],
        "cone": cone,  # → Core forecast-cone primitive (mean + CI bands)
        "weekly_breakdown": _weekly_breakdown(horizon),
        "mode": horizon["mode"],
        "warnings": horizon.get("warnings", []),
        "channel_decomposition": _channel_decomposition(horizon),  # §5.3 (engine data)
        "sensitivity": None,  # project-level tornado lives at context["sensitivity"]
    }


def build_report_context(fixture: dict[str, Any]) -> dict[str, Any]:
    """Assemble the neutral 8-section report context from a forecast fixture.

    Raises ValueError (via `copy.assert_client_safe`) if any composed client-facing
    string contains a forbidden phrase.
    """
    meta = fixture["metadata"]
    horizons = fixture["horizons"]
    sim = meta["similarity"]
    tier = copy.tier_from_similarity(sim["aggregate"])
    tier_label = copy.tier_label(tier)

    by_weeks = {h["horizon_weeks"]: h for h in horizons}
    h12 = by_weeks.get(12, horizons[0])

    headline = copy.headline_forecast(h12["horizon_weeks"], h12["total_forecast"], h12["ci_pct"])
    similarity_line = copy.similarity_one_liner(meta["proxy_brand"], sim["aggregate"])
    caveat = copy.transfer_caveat(meta["proxy_brand"])
    posterior = copy.posterior_update_reminder()
    method_xref = copy.methodology_cross_reference()

    # Client-surface hygiene gate — composed copy must be free of forbidden phrases.
    copy.assert_client_safe(headline, similarity_line, caveat, posterior, method_xref,
                            copy.tier_verdict(tier))

    return {
        "schema": "launch_forecast_report_context_v1",
        "cover": {
            "recipient_brand": meta["recipient_brand"],
            "subtitle": "Launch Forecast Report",
            "tagline": "Прогноз запуска бренда на основе индивидуально подобранного "
                       "прокси и recipient anchors",
            # filled by the renderer at emit time:
            "date_generated": None,
            "project_id": None,
            "hash_signature": None,
            "aurora_version": None,
        },
        "executive_summary": {
            "headline": headline,
            "tier": {"key": tier, "label": tier_label, "verdict": copy.tier_verdict(tier)},
            "similarity_one_liner": similarity_line,
            "key_metrics": _key_metrics_rows(horizons, tier_label),
        },
        "proxy_quality": {
            "proxy_brand": meta["proxy_brand"],
            "proxy_category": meta.get("proxy_category"),
            "proxy_data_period": meta.get("proxy_data_period"),
            "radar": {  # → Core radar primitive (6-dim)
                "dimensions": sim["dimensions"],
                "aggregate": sim["aggregate"],
                "verdict": sim["verdict"],
            },
        },
        "transfer_caveats": {
            "transfers": _TRANSFERS,
            "not_transfers": _NOT_TRANSFERS,
            "reconstructed": _RECONSTRUCTED,
            "uncertainty": meta["uncertainty_decomposition"],  # → Core pie primitive (4-source)
            "inflation_factor": meta.get("inflation_factor"),
            "caveat_text": caveat,
        },
        "forecast_12w": _forecast_section(by_weeks[12]) if 12 in by_weeks else None,
        "forecast_26w": _forecast_section(by_weeks[26]) if 26 in by_weeks else None,
        "forecast_52w": _forecast_section(by_weeks[52]) if 52 in by_weeks else None,
        "methodology": {
            "formulas": _FORMULAS,
            "references": _REFERENCES,
            "cross_reference": method_xref,
            "posterior_update_reminder": posterior,
            # model card / diagnostics filled from the real posterior at emit time:
            "diagnostics": None,
            "hash_signature": None,
        },
        # §5.4 sensitivity tornado (project-level, annual horizon) + §1.4 per-channel
        # hill curves — real engine data via the per-channel forecast path.
        "sensitivity": meta.get("sensitivity"),
        "hill_curves": meta.get("channel_hill"),
        # Recipient launch assumptions (anchors) — user-provided inputs the forecast
        # is built on; rendered as the XLSX Anchors sheet (context-enrichment).
        "recipient_anchors": meta.get("recipient_anchors"),
    }
