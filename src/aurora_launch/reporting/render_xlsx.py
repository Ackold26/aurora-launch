"""Launch Forecast → XLSX renderer (Sprint B4 deliverable #3, data drill-down).

The analyst-facing workbook (spec §2.3), composed by CONSUMING the Core
``aurora_reporting`` xlsx SSOT (``new_workbook`` / ``add_table_sheet`` / ``Column`` /
``add_color_scale`` / ``tier_fill``, surfaced on the ``primitives`` facade) — same
``consume > copy`` boundary as the PPTX/HTML deliverables. Core owns the themed
table primitive (frozen branded header, per-column number formats, conditional
formatting); Launch owns the 8-sheet composition.

Conditional formatting (spec §2.3): a per-week CI-width column carries a 3-colour
scale (widest = most uncertain), and the Summary confidence cells take the tier
badge colour.

Channel decomposition lands via the per-channel path, and Anchors via the recipient
launch-assumptions context-enrichment. Diagnostics stays a present-but-flagged
placeholder (header + note, reported in the manifest, never silently dropped):
posterior convergence diagnostics (R-hat/ESS) exist only on the recipient-fit path,
not the pure-transfer baseline — emitting r_hat=1.0 "by construction" would
misrepresent convergence (INV-50).
"""

from __future__ import annotations

from typing import Any

from aurora_reporting.primitives import (
    Column,
    add_color_scale,
    add_table_sheet,
    new_workbook,
    tier_fill,
)
from openpyxl.utils import get_column_letter

# Core's table/colour helpers default to the AURORA_HYBRID theme (the single
# deliverable theme), so Launch consumes that default — no per-call theme needed.
_RUB = '# ##0 "₽"'
_PCT = "0.0"


def _col_letter(idx: int) -> str:
    """1-based column index → Excel letter."""
    return str(get_column_letter(idx))


def _sheet_summary(wb: Any, ctx: dict[str, Any]) -> None:
    km = ctx["executive_summary"]["key_metrics"]
    tier_key = ctx["executive_summary"]["tier"]["key"]
    cols = [
        Column("Горизонт", "period", width=14),
        Column("Прогноз продаж, ₽", "total", number_format=_RUB, width=22, align="right"),
        Column("95% ДИ, %", "ci", number_format=_PCT, width=12, align="right"),
        Column("Уверенность", "tier", width=24),
    ]
    rows = [
        {"period": f"{r['period_weeks']} нед.", "total": r["total_rub"], "ci": r["ci_pct"],
         "tier": r["tier_label"]}
        for r in km
    ]
    ws = add_table_sheet(wb, "Summary", cols, rows)
    # Confidence cells take the tier badge colour (col 4, data rows 2..N).
    for ri in range(len(rows)):
        tier_fill(ws, f"D{ri + 2}", tier_key)


def _sheet_weekly(wb: Any, ctx: dict[str, Any], section_key: str, title: str) -> bool:
    section = ctx.get(section_key)
    cols = [
        Column("Неделя", "week", width=10),
        Column("Среднее, ₽", "mean", number_format=_RUB, width=18, align="right"),
        Column("Нижняя 95%, ₽", "lo", number_format=_RUB, width=18, align="right"),
        Column("Верхняя 95%, ₽", "hi", number_format=_RUB, width=18, align="right"),
        Column("Ширина 95% ДИ, ₽", "width", number_format=_RUB, width=20, align="right"),
    ]
    if section is None:
        add_table_sheet(wb, title, cols, [{"week": "Горизонт не рассчитан."}])
        return False
    rows = [
        {"week": r["week"], "mean": r["mean"], "lo": r["ci_lower"], "hi": r["ci_upper"],
         "width": r["ci_upper"] - r["ci_lower"]}
        for r in section["weekly_breakdown"]
    ]
    ws = add_table_sheet(wb, title, cols, rows)
    # §2.3 conditional formatting: colour-scale the CI-width column (widest = reddest).
    width_col = _col_letter(len(cols))
    add_color_scale(ws, f"{width_col}2:{width_col}{len(rows) + 1}")
    return True


def _sheet_channel(wb: Any, ctx: dict[str, Any]) -> bool:
    section = ctx.get("forecast_12w") or ctx.get("forecast_26w") or ctx.get("forecast_52w")
    cd = (section or {}).get("channel_decomposition")
    channel_ids = list(cd["channels"]) if cd else []
    cols = [
        Column("Период", "period", width=10),
        Column("Baseline, ₽", "baseline", number_format=_RUB, width=16, align="right"),
        *[Column(f"{c}, ₽", c, number_format=_RUB, width=14, align="right") for c in channel_ids],
        Column("Итого, ₽", "total", number_format=_RUB, width=16, align="right"),
    ]
    if not cd:
        add_table_sheet(wb, "Channel decomposition", cols, [{"period": "Горизонт не рассчитан."}])
        return False
    rows = []
    for i, period in enumerate(cd["periods"]):
        base = cd["baseline"][i]
        chan = {c: cd["channels"][c][i] for c in channel_ids}
        rows.append({"period": period, "baseline": base, **chan,
                     "total": base + sum(chan.values())})
    add_table_sheet(wb, "Channel decomposition", cols, rows)
    return True


def _sheet_proxy(wb: Any, ctx: dict[str, Any]) -> None:
    pq = ctx["proxy_quality"]
    cols = [Column("Параметр", "k", width=28), Column("Значение", "v", width=40)]
    rows: list[dict[str, Any]] = [
        {"k": "Прокси-бренд", "v": pq["proxy_brand"]},
        {"k": "Категория", "v": pq.get("proxy_category") or "—"},
        {"k": "Период данных", "v": pq.get("proxy_data_period") or "—"},
        {"k": "Итоговая близость (S)", "v": pq["radar"]["aggregate"]},
        {"k": "Вердикт", "v": pq["radar"]["verdict"]},
    ]
    rows += [{"k": f"  — {dim}", "v": score} for dim, score in pq["radar"]["dimensions"].items()]
    add_table_sheet(wb, "Proxy summary", cols, rows)


def _sheet_anchors(wb: Any, ctx: dict[str, Any]) -> bool:
    anchors = ctx.get("recipient_anchors")
    cols = [Column("Допущение запуска", "k", width=36), Column("Значение", "v", width=44)]
    if not anchors:
        add_table_sheet(wb, "Anchors", cols,
                        [{"k": "Recipient anchors не входят в контракт контекста — context-enrichment follow-up."}])
        return False

    def _ramp(traj: list[float]) -> str:
        return f"{traj[0] * 100:.0f}% → {max(traj) * 100:.0f}% (рост за {len(traj)} нед.)"

    seasonality = anchors.get("seasonality")
    seasonality_v = (
        "плоская (1.0)"
        if not seasonality or len(set(seasonality)) == 1
        else f"{min(seasonality):.2f}–{max(seasonality):.2f}"
    )
    pricing = anchors["pricing_index"]
    rows: list[dict[str, Any]] = [
        {"k": "Размер рынка", "v": f"{anchors['market_size']:,.0f} ₽".replace(",", " ")},
        {"k": "Неопределённость размера рынка (CV)", "v": f"{anchors['market_size_cv'] * 100:.0f}%"},
        {"k": "Плановая доля рынка", "v": _ramp(anchors["planned_share_trajectory"])},
        {"k": "Дистрибуция", "v": _ramp(anchors["distribution_trajectory"])},
        {"k": "Ценовой индекс", "v": f"{pricing:.2f} (+{(pricing - 1) * 100:.0f}% к категории)"},
        {"k": "Ценовая эластичность", "v": f"{anchors['elasticity']:.2f}"},
        {"k": "Сезонность", "v": seasonality_v},
    ]
    add_table_sheet(wb, "Anchors", cols, rows)
    return True


def _sheet_diagnostics(wb: Any, ctx: dict[str, Any]) -> bool:
    diag = ctx["methodology"].get("diagnostics")
    cols = [Column("Метрика", "k", width=28), Column("Значение", "v", width=20)]
    if diag is None:
        add_table_sheet(wb, "Diagnostics", cols,
                        [{"k": "Posterior-диагностика (Gelman-Rubin/ESS/R²/MAPE) появится из реального постериора."}])
        return False
    add_table_sheet(wb, "Diagnostics", cols, [{"k": k, "v": v} for k, v in diag.items()])
    return True


def build_launch_forecast_xlsx(context: dict[str, Any], output_path: str) -> dict[str, Any]:
    """Render the 8-sheet Launch Forecast workbook to ``output_path``.

    Returns a manifest: sheet names + which sheets are pending (data-gated).
    """
    wb = new_workbook()

    pending: list[str] = []
    _sheet_summary(wb, context)
    for key, title in (("forecast_12w", "12w forecast"), ("forecast_26w", "26w forecast"),
                       ("forecast_52w", "52w forecast")):
        if not _sheet_weekly(wb, context, key, title):
            pending.append(title)
    if not _sheet_channel(wb, context):
        pending.append("Channel decomposition")
    if not _sheet_anchors(wb, context):
        pending.append("Anchors")
    _sheet_proxy(wb, context)
    if not _sheet_diagnostics(wb, context):
        pending.append("Diagnostics")

    wb.save(output_path)
    return {
        "output_path": output_path,
        "sheets": wb.sheetnames,
        "sheet_count": len(wb.sheetnames),
        "pending": pending,
    }


def _main() -> None:
    import json

    from aurora_launch.reporting.context import build_report_context
    from aurora_launch.sample_bundles.report_fixture import build_sample_forecast_fixture

    ctx = build_report_context(build_sample_forecast_fixture())
    manifest = build_launch_forecast_xlsx(ctx, "launch_forecast_sample.xlsx")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _main()
