"""Launch Forecast → HTML renderer (Sprint B4 deliverable #2, standalone report).

The web-facing deliverable (spec §2.2). Core `aurora_html.build_html` is an
Эконометрика MMM-pipeline-shaped builder (channels / decompose / optimize) — the
wrong shape for Launch's 8-section forecast. Per the CPI boundary (Core = design
layer, Launch = composition), Launch owns this launch_forecast composition and now
CONSUMES the Core design SSOT via `aurora_reporting.aurora_html.design_shell`
(`render_shell` + `layout.css` components) — no copy-lift, no drift with the PPTX
canon, and a hash-based CSP for free. This replaces the earlier hand-rolled layer.

Charts are the same Core matplotlib→PNG primitives the PPTX deck uses (cone / radar
/ pie), base64-inlined as <img>. ECharts interactivity is intentionally off (static
PNG charts); the page is a branded, accessible, self-contained static report.

Data-gated sections (channel decomposition §5.3, sensitivity §5.4) are reported in
the manifest, never silently dropped.
"""

from __future__ import annotations

from typing import Any

from aurora_reporting.aurora_html import design_shell, security
from aurora_reporting.primitives import (
    forecast_cone,
    hill_curve,
    pie_breakdown,
    similarity_radar,
    tornado,
)

from aurora_launch.reporting import copy
from aurora_launch.reporting.render_pptx import _derive_bands

_esc = security.escape


def _png_img(png_bytes: bytes, alt: str) -> str:
    import base64

    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f'<img alt="{_esc(alt)}" style="max-width:100%;height:auto;display:block" ' \
           f'src="data:image/png;base64,{b64}">'


def _section(sid: str, kicker: str, title: str, body: str) -> str:
    return (
        f'<section class="section" id="{sid}">'
        f'<div class="section-kicker">{_esc(kicker)}</div>'
        f'<h2 class="action-title">{_esc(title)}</h2>'
        f'<span class="sacred-lime"></span>'
        f"{body}</section>"
    )


def _ul(items: list[str], cls: str = "") -> str:
    c = f' class="{cls}"' if cls else ""
    return f"<ul{c}>" + "".join(f"<li>{_esc(i)}</li>" for i in items) + "</ul>"


def _action_table(headers: list[str], rows: list[list[object]], *, num_cols: set[int],
                  caption: str = "") -> str:
    cap = f"<caption>{_esc(caption)}</caption>" if caption else ""
    head = "".join(
        f'<th class="{"num" if i in num_cols else ""}">{_esc(h)}</th>' for i, h in enumerate(headers)
    )
    body = []
    for row in rows:
        cells = "".join(
            f'<td class="{"num" if i in num_cols else ""}">{_esc(v)}</td>' for i, v in enumerate(row)
        )
        body.append(f"<tr>{cells}</tr>")
    return (f'<table class="action-table">{cap}<thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table>')


def _chart_block(title: str, png_bytes: bytes, alt: str, subtitle: str = "") -> str:
    sub = f'<div class="chart-subtitle">{_esc(subtitle)}</div>' if subtitle else ""
    return (
        f'<div class="chart-container"><div class="chart-title-bar">'
        f'<div><div class="chart-title">{_esc(title)}</div>{sub}</div></div>'
        f'{_png_img(png_bytes, alt)}</div>'
    )


# ── Section builders ─────────────────────────────────────────────────────────


def _sec_cover(ctx) -> str:
    c = ctx["cover"]
    cells = [
        ("Версия", c.get("aurora_version") or "—"),
        ("Сгенерирован", c.get("date_generated") or "—"),
        ("ID проекта", (c.get("project_id") or "—")[:8]),
        ("Hash (SHA-256)", (c.get("hash_signature") or "—")[:12]),
    ]
    meta = "".join(
        f'<div class="cover-meta-cell"><div class="cover-meta-label">{_esc(lbl)}</div>'
        f'<div class="cover-meta-value">{_esc(val)}</div></div>'
        for lbl, val in cells
    )
    return (
        f'<section class="section" id="cover"><div class="cover">'
        f'<div class="cover-brand-mark">{design_shell.brand_mark_svg()}</div>'
        f'<h1>{_esc(c["recipient_brand"])}</h1>'
        f'<p class="subtitle">{_esc(c["tagline"])}</p>'
        f'<div class="cover-meta">{meta}</div>'
        f"</div></section>"
    )


def _sec_executive(ctx) -> str:
    es = ctx["executive_summary"]
    km = {r["period_weeks"]: r for r in es["key_metrics"]}
    h12 = km[12]
    key_message = (
        f'<div class="key-message"><div>'
        f'<div class="big-number">{_esc(h12["total_display"])}</div>'
        f'<div class="big-number-label">Прогноз продаж · {h12["period_weeks"]} недель</div>'
        f'<div class="big-number-support">± {h12["ci_pct"]:g}% (95% доверительный интервал)</div>'
        f'</div><div class="commentary"><div class="commentary-block">'
        f'<div class="commentary-lead">{_esc(es["tier"]["label"])}</div>'
        f'<div class="commentary-body">{_esc(es["tier"]["verdict"])}</div></div>'
        f'<div class="commentary-block"><div class="commentary-body">'
        f'{_esc(es["similarity_one_liner"])}</div></div></div></div>'
    )
    rows = [[f'{r["period_weeks"]} нед.', r["total_display"], f'±{r["ci_pct"]:g}%', r["tier_label"]]
            for r in es["key_metrics"]]
    table = _action_table(["Горизонт", "Прогноз продаж", "95% ДИ", "Уверенность"], rows,
                          num_cols={1, 2}, caption="Ключевые метрики по горизонтам")
    return _section("executive", "Резюме для руководства", "Ключевой прогноз",
                    key_message + table)


def _sec_proxy(ctx) -> str:
    pq = ctx["proxy_quality"]
    radar = pq["radar"]
    png = similarity_radar(dimensions=list(radar["dimensions"]),
                           scores=list(radar["dimensions"].values()),
                           aggregate=radar["aggregate"])
    mqs = (
        f'<div class="mqs-card"><div class="mqs-label">Итоговая близость</div>'
        f'<div class="mqs-score">{radar["aggregate"]:g}</div>'
        f'<div class="mqs-tier">{_esc(radar["verdict"])}</div></div>'
    )
    facts = _ul([
        f'Прокси-бренд: {pq["proxy_brand"]}',
        f'Категория: {pq.get("proxy_category") or "—"}',
        f'Период данных: {pq.get("proxy_data_period") or "—"}',
    ], cls="sources-list")
    body = (
        f'<div class="sources-grid">{mqs}<div>{facts}</div></div>'
        + _chart_block("Карта близости (6 измерений)", png, "Карта близости прокси")
    )
    return _section("proxy", "Качество прокси", "Выбранный прокси-бренд и близость", body)


def _sec_caveats(ctx) -> str:
    tc = ctx["transfer_caveats"]
    scqar = (
        f'<div class="scqar"><div class="scqar-block accent"><div class="scqar-label">Переносится</div>'
        f'<div class="scqar-body">{_ul(tc["transfers"])}</div></div>'
        f'<div class="scqar-block"><div class="scqar-label">НЕ переносится</div>'
        f'<div class="scqar-body">{_ul(tc["not_transfers"])}</div></div>'
        f'<div class="scqar-block"><div class="scqar-label">Из anchors</div>'
        f'<div class="scqar-body">{_ul(tc["reconstructed"])}</div></div></div>'
    )
    unc = tc["uncertainty"]
    label_ru = {"proxy": "Прокси", "transfer": "Трансфер", "anchor": "Anchors", "sampling": "Сэмплинг"}
    pie = pie_breakdown(slices={label_ru.get(k, k): v for k, v in unc.items()}, donut=True)
    infl = tc.get("inflation_factor")
    infl_block = ""
    if infl:
        infl_block = (f'<div class="commentary"><div class="commentary-block">'
                      f'<div class="commentary-lead">Inflation factor: ×{infl:g}</div>'
                      f'<div class="commentary-body">Вердикт Medium → расширение 95% '
                      f'доверительного интервала.</div></div></div>')
    body = (
        scqar
        + f'<p class="pull-quote">{_esc(tc["caveat_text"])}</p>'
        + _chart_block("Декомпозиция неопределённости", pie, "Декомпозиция неопределённости")
        + infl_block
    )
    return _section("caveats", "Оговорки трансфера", "Что переносится, что — нет", body)


def _sec_forecast(ctx, key: str, weeks: int) -> str | None:
    section = ctx.get(key)
    if section is None:
        return None
    cone = section["cone"]
    png = forecast_cone(periods=[p["x"] for p in cone], mean=[p["mean"] for p in cone],
                        bands=_derive_bands(cone), ylabel="Продажи, ₽", size_px=(1600, 720))
    wb = section["weekly_breakdown"][:12]
    rows = [[r["week"], f'{r["mean"]:,.0f}'.replace(",", " "),
             f'{r["ci_lower"]:,.0f}'.replace(",", " "), f'{r["ci_upper"]:,.0f}'.replace(",", " ")]
            for r in wb]
    table = _action_table(["Неделя", "Среднее, ₽", "Нижняя 95%", "Верхняя 95%"], rows,
                          num_cols={1, 2, 3}, caption=f"Понедельная разбивка · {weeks} недель")
    note = ("" if len(section["weekly_breakdown"]) <= 12 else
            f'<div class="footnotes"><ul class="footnotes-list"><li>Показаны первые 12 из '
            f'{len(section["weekly_breakdown"])} недель (полная разбивка — в XLSX).</li></ul></div>')
    cd = section.get("channel_decomposition")
    channel = _channel_table(cd) if cd else ""
    body = _chart_block(f"Веер прогноза · {weeks} недель", png, f"Веер прогноза {weeks} недель") \
        + table + note + channel
    return _section(f"forecast-{weeks}", f"Прогноз · {weeks} недель",
                    "Веер прогноза, понедельная разбивка и каналы", body)


def _sec_tornado(ctx) -> str | None:
    sens = ctx.get("sensitivity")
    if not sens:
        return None
    png = tornado(factors=[(f["label"], f["low"], f["high"]) for f in sens["factors"]],
                  baseline=sens["baseline"], size_px=(1600, 760))
    body = _chart_block(f"Влияние anchors на прогноз (±{sens['delta_pct']}%)", png,
                        "Тонадо чувствительности")
    return _section("sensitivity", "Чувствительность", "Влияние входных предпосылок", body)


def _sec_hill(ctx) -> str | None:
    hills = ctx.get("hill_curves")
    if not hills:
        return None
    curves = [(h["label"], h["beta"], h["gamma"], h["k"]) for h in hills]
    png = hill_curve(curves=curves, x_max=max(h["k"] for h in hills) * 3.0, size_px=(1600, 760))
    body = _chart_block("Кривые насыщения по каналам (Hill)", png, "Кривые Hill")
    return _section("hill", "Методология", "Кривые насыщения каналов", body)


def _channel_table(cd: dict) -> str:
    base_total = sum(cd["baseline"])
    chan_totals = {c: sum(v) for c, v in cd["channels"].items()}
    grand = base_total + sum(chan_totals.values())
    rows = [["Baseline", f'{base_total:,.0f}'.replace(",", " "), f"{100 * base_total / grand:.1f}%"]]
    rows += [[c.upper(), f'{t:,.0f}'.replace(",", " "), f"{100 * t / grand:.1f}%"]
             for c, t in chan_totals.items()]
    return _action_table(["Источник", "Вклад, ₽", "Доля"], rows, num_cols={1, 2},
                         caption="Декомпозиция по каналам (сумма за горизонт)")


def _sec_methodology(ctx) -> str:
    m = ctx["methodology"]
    formulas = (
        '<div class="formula-box">Adstock:  A_t = X_t + λ · A_(t−1)\n'
        'Hill:     H(x) = β · x^γ / (k^γ + x^γ)</div>'
    )
    refs = "".join(f"<li>{_esc(r)}</li>" for r in m["references"])
    grid = (
        f'<div class="methodology-grid"><div>'
        f'<div class="method-col-label">Математика</div>{formulas}</div><div>'
        f'<div class="method-col-label">Академические источники</div>'
        f'<ul class="sources-list">{refs}</ul></div></div>'
    )
    body = (
        grid
        + f'<p>{_esc(m["posterior_update_reminder"])}</p>'
        + f'<p class="finding-support">{_esc(m["cross_reference"])}</p>'
        + '<a class="method-badge">Воспроизводимая методология</a>'
    )
    return _section("methodology", "Методология", "Математика, источники и воспроизводимость", body)


def build_launch_forecast_html(
    context: dict[str, Any],
    output_path: str,
    *,
    aurora_version: str = "v0.2.5",
    project_id: str | None = None,
    date_generated: str | None = None,
    hash_signature: str | None = None,
) -> dict[str, Any]:
    """Render the standalone 8-section Launch Forecast HTML to ``output_path``.

    Wraps the product sections in the Core design-shell (`render_shell`): embedded
    fonts, token + layout CSS, neutral chrome, and a hash-based CSP.
    """
    from pathlib import Path

    cover = context["cover"]
    cover["aurora_version"] = aurora_version
    cover["project_id"] = project_id
    cover["date_generated"] = date_generated
    cover["hash_signature"] = hash_signature

    skipped: list[str] = []
    section_specs = [
        ("cover", "Обложка", _sec_cover(context)),
        ("executive", "Резюме", _sec_executive(context)),
        ("proxy", "Качество прокси", _sec_proxy(context)),
        ("caveats", "Оговорки трансфера", _sec_caveats(context)),
    ]
    for key, weeks in (("forecast_12w", 12), ("forecast_26w", 26), ("forecast_52w", 52)):
        s = _sec_forecast(context, key, weeks)
        if s is None:
            skipped.append(key)
            continue
        section_specs.append((f"forecast-{weeks}", f"Прогноз {weeks} нед.", s))
        if (context[key] or {}).get("channel_decomposition") is None:
            skipped.append(f"{key}.channel_decomposition")
    tornado_html = _sec_tornado(context)
    if tornado_html:
        section_specs.append(("sensitivity", "Чувствительность", tornado_html))
    else:
        skipped.append("sensitivity")
    hill_html = _sec_hill(context)
    if hill_html:
        section_specs.append(("hill", "Кривые Hill", hill_html))
    else:
        skipped.append("hill_curves")
    section_specs.append(("methodology", "Методология", _sec_methodology(context)))

    sections_html = "".join(html for _, _, html in section_specs)
    toc_items = "".join(
        f'<li><a href="#{sid}">{_esc(label)}</a></li>' for sid, label, _ in section_specs
    )

    doc = design_shell.render_shell(
        doc_title=f'Launch Forecast — {cover["recipient_brand"]}',
        doc_description="Прогноз запуска бренда — Aurora AI Launch",
        sections_html=sections_html,
        toc_items_html=toc_items,
        version=aurora_version,
        report_id=(project_id or "")[:8],
        generated_human=date_generated or "",
        generated_iso=date_generated or "",
        confidentiality_label="Конфиденциально",
        copyright_line="© Aurora AI · auroraai.pro",
        include_echarts=False,  # charts are static PNG; no ECharts runtime needed
    )

    Path(output_path).write_text(doc, encoding="utf-8")
    return {
        "output_path": output_path,
        "bytes": len(doc.encode("utf-8")),
        "skipped": skipped,
        "sections": len(section_specs),
        "design_shell": True,
        "csp": "Content-Security-Policy" in doc,
    }


def _main() -> None:
    import json

    from aurora_launch.reporting.context import build_report_context
    from aurora_launch.sample_bundles.report_fixture import build_sample_forecast_fixture

    ctx = build_report_context(build_sample_forecast_fixture())
    manifest = build_launch_forecast_html(
        ctx, "launch_forecast_sample.html", aurora_version="v0.2.5",
        project_id="demo-0001-pilot-sample", date_generated="2026-06-15",
        hash_signature="0" * 64,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _main()
