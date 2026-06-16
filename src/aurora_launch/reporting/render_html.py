"""Launch Forecast → HTML renderer (Sprint B4 deliverable #2, standalone report).

The web-facing deliverable (spec §2.2). The Core `aurora_html.build_html` is an
Эконометрика-shaped tier-1 MMM builder (its `data` is a narrative_adapter pipeline
dump with channels / decompose / optimize / scenarios) — the wrong shape for
Launch's 8-section forecast. Per the CPI boundary (Core = primitives + design
tokens, Launch = composition), Launch owns this 8-section launch_forecast HTML and
reuses the Core design layer two ways, DRY with the token SSOT:

  - the ``:root`` CSS custom properties are generated from the Core ``AURORA_HYBRID``
    theme object at render time (so the palette tracks Core, never a stale copy);
  - the OFL fonts (Inter/Lora) are @font-face'd from the woff2 already bundled in
    ``aurora_html/templates/fonts`` and base64-inlined → a single standalone file.

Charts are the same Core matplotlib→PNG primitives the PPTX deck uses (cone / radar
/ pie), base64-inlined as <img>. Interactive ECharts + animations (spec §2.2) are a
v2 enhancement; v1 is a branded, accessible, self-contained static report.

Data-gated sections (channel decomposition §5.3, sensitivity §5.4) are reported in
the manifest, never silently dropped — same honesty as the deck/workbook.
"""

from __future__ import annotations

import base64
import html
from pathlib import Path
from typing import Any

import aurora_reporting
from aurora_reporting.primitives import (
    AURORA_HYBRID,
    forecast_cone,
    pie_breakdown,
    similarity_radar,
    tier_for,
)

from aurora_launch.reporting import copy
from aurora_launch.reporting.render_pptx import _derive_bands

_THEME = AURORA_HYBRID

# Core's bundled subsetted woff2 (HTML layer) — no brotli needed, already on disk.
_FONT_DIR = Path(aurora_reporting.__file__).parent / "aurora_html" / "templates" / "fonts"
_FONT_FACES = (
    # (family, weight, unicode-range label, filename)
    ("Inter", 400, "latin", "inter-400-latin.woff2"),
    ("Inter", 400, "cyrillic", "inter-400-cyrillic.woff2"),
    ("Inter", 600, "latin", "inter-600-latin.woff2"),
    ("Inter", 600, "cyrillic", "inter-600-cyrillic.woff2"),
    ("Lora", 400, "latin", "lora-400-latin.woff2"),
    ("Lora", 400, "cyrillic", "lora-400-cyrillic.woff2"),
)
# Cyrillic / latin unicode-ranges (Google Fonts subset convention).
_UNICODE_RANGE = {
    "cyrillic": "U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116",
    "latin": "U+0000-00FF, U+0131, U+0152-0153, U+2000-206F, U+2122, U+2191, U+2193, U+2212",
}


def _esc(s: object) -> str:
    return html.escape(str(s))


def _png_img(png: bytes, alt: str, *, max_h: int | None = None) -> str:
    b64 = base64.b64encode(png).decode("ascii")
    style = f"max-height:{max_h}px;" if max_h else ""
    return f'<img class="chart" alt="{_esc(alt)}" style="{style}" src="data:image/png;base64,{b64}">'


def _font_faces_css() -> str:
    faces = []
    for family, weight, rangekey, fname in _FONT_FACES:
        p = _FONT_DIR / fname
        if not p.exists():
            continue
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        faces.append(
            f"@font-face{{font-family:'{family}';font-style:normal;font-weight:{weight};"
            f"font-display:swap;unicode-range:{_UNICODE_RANGE[rangekey]};"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2');}}"
        )
    return "\n".join(faces)


def _root_tokens_css() -> str:
    """`:root` custom properties generated from the Core theme (single source)."""
    t = _THEME
    return (
        ":root{"
        f"--deep-100:{t.deep[0]};--deep-80:{t.deep[1]};--deep-60:{t.deep[2]};"
        f"--deep-40:{t.deep[3]};--deep-20:{t.deep[4]};"
        f"--gold:{t.gold};--gold-muted:{t.gold_muted};--lime:{t.sig_lime};"
        f"--bg:{t.bg_white};--surface:{t.bg_cream};--rule:{t.rule};"
        f"--text:{t.text_primary};--text-muted:{t.text_secondary};"
        f"--go:{t.go};--caution:{t.caution};--stop:{t.stop};"
        f"--font-sans:'{t.body_font[0]}',{','.join(t.body_font[1:])};"
        f"--font-serif:'{t.display_font[0]}',{','.join(t.display_font[1:])};"
        "}"
    )


_LAYOUT_CSS = """
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--font-sans);
  line-height:1.55;-webkit-font-smoothing:antialiased}
.cover{background:var(--deep-100);color:var(--bg);padding:72px 64px}
.cover .brand{color:var(--gold);font-weight:600;letter-spacing:.12em;font-size:15px}
.cover h1{font-family:var(--font-serif);font-size:48px;margin:24px 0 8px}
.cover .lime-rule{width:120px;height:3px;background:var(--lime);margin:16px 0}
.cover .subtitle{color:var(--gold);font-size:20px;margin:8px 0}
.cover .tagline{color:#C9D4E0;font-size:15px;max-width:680px}
.cover .meta{color:#7E92A8;font-size:12px;margin-top:40px}
main{max-width:1040px;margin:0 auto;padding:0 32px}
section{padding:48px 0;border-bottom:1px solid var(--rule-subtle,#D6DFE8)}
.kicker{color:var(--gold);font-weight:600;letter-spacing:.1em;font-size:12px;text-transform:uppercase}
h2{font-family:var(--font-serif);font-size:30px;color:var(--deep-100);margin:6px 0 4px}
.gold-rule{width:64px;height:2px;background:var(--gold);margin:10px 0 24px}
.headline{font-family:var(--font-serif);font-size:24px;color:var(--deep-100);font-weight:700}
.badge{display:inline-block;color:#fff;font-weight:700;border-radius:999px;
  padding:6px 18px;font-size:14px;vertical-align:middle}
table{border-collapse:collapse;width:100%;margin:8px 0;font-size:14px}
th{background:var(--deep-100);color:var(--bg);text-align:left;padding:8px 12px;font-weight:600}
td{padding:8px 12px;border-bottom:1px solid var(--rule)}
tr:nth-child(even) td{background:var(--surface)}
tr.focus td{background:var(--gold);font-weight:700}
td.num,th.num{text-align:right}
.chart{max-width:100%;height:auto;display:block;margin:16px 0}
.cols{display:flex;gap:32px;flex-wrap:wrap}
.col{flex:1;min-width:220px}
.col h3{font-size:15px;margin:0 0 8px}
.col.go h3{color:var(--go)} .col.stop h3{color:var(--stop)} .col.gold h3{color:var(--gold)}
ul{margin:6px 0;padding-left:20px} li{margin:4px 0}
.note{color:var(--text-muted);font-style:italic;font-size:13px}
.formula{font-family:var(--font-mono,monospace);background:var(--surface);
  padding:8px 14px;border-radius:8px;display:inline-block;margin:6px 0;color:var(--deep-100)}
@media (prefers-reduced-motion: reduce){*{transition:none!important;animation:none!important}}
"""


def _li(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{_esc(i)}</li>" for i in items) + "</ul>"


def _table(headers: list[str], rows: list[list[object]], *, focus_row: int | None = None,
           num_cols: set[int] | None = None) -> str:
    num_cols = num_cols or set()
    head = "".join(
        f'<th class="{"num" if i in num_cols else ""}">{_esc(h)}</th>'
        for i, h in enumerate(headers)
    )
    body = []
    for ri, row in enumerate(rows):
        cls = ' class="focus"' if focus_row == ri else ""
        cells = "".join(
            f'<td class="{"num" if i in num_cols else ""}">{_esc(v)}</td>'
            for i, v in enumerate(row)
        )
        body.append(f"<tr{cls}>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


# ── Section builders (return HTML strings) ───────────────────────────────────


def _sec_cover(ctx) -> str:
    c = ctx["cover"]
    meta = "  ·  ".join(p for p in [
        c.get("aurora_version") or "", c.get("date_generated") or "",
        f"ID {(c.get('project_id') or '')[:8]}" if c.get("project_id") else "",
        f"SHA {(c.get('hash_signature') or '')[:8]}" if c.get("hash_signature") else "",
    ] if p)
    return (
        f'<header class="cover"><div class="brand">AURORA AI</div>'
        f'<h1>{_esc(c["recipient_brand"])}</h1><div class="lime-rule"></div>'
        f'<div class="subtitle">{_esc(c["subtitle"])}</div>'
        f'<p class="tagline">{_esc(c["tagline"])}</p>'
        f'<div class="meta">{_esc(meta)}</div></header>'
    )


def _section(kicker: str, title: str, body: str) -> str:
    return (
        f'<section><div class="kicker">{_esc(kicker)}</div><h2>{_esc(title)}</h2>'
        f'<div class="gold-rule"></div>{body}</section>'
    )


def _sec_executive(ctx) -> str:
    es = ctx["executive_summary"]
    agg = ctx["proxy_quality"]["radar"]["aggregate"]
    badge_color = tier_for(agg).color
    badge = (f'<span class="badge" style="background:{badge_color}">'
             f'{_esc(es["tier"]["label"])}</span>')
    km = es["key_metrics"]
    rows = [[f'{r["period_weeks"]} нед.', r["total_display"], f'±{r["ci_pct"]:g}%', r["tier_label"]]
            for r in km]
    body = (
        f'<p class="headline">{_esc(es["headline"])}</p> {badge}'
        f'<p>{_esc(es["similarity_one_liner"])}</p>'
        f'<p class="note">{_esc(es["tier"]["verdict"])}</p>'
        + _table(["Горизонт", "Прогноз продаж", "95% ДИ", "Уверенность"], rows,
                 focus_row=0, num_cols={1, 2})
    )
    return _section("Резюме для руководства", "Ключевой прогноз", body)


def _sec_proxy(ctx) -> str:
    pq = ctx["proxy_quality"]
    radar = pq["radar"]
    png = similarity_radar(dimensions=list(radar["dimensions"]),
                           scores=list(radar["dimensions"].values()),
                           aggregate=radar["aggregate"],
                           title=f'S = {radar["aggregate"]:g} ({radar["verdict"]})',
                           theme=_THEME)
    facts = _li([
        f'Прокси-бренд: {pq["proxy_brand"]}',
        f'Категория: {pq.get("proxy_category") or "—"}',
        f'Период данных: {pq.get("proxy_data_period") or "—"}',
        f'Итоговая близость: S = {radar["aggregate"]:g} ({radar["verdict"]})',
    ])
    body = f'<div class="cols"><div class="col">{facts}</div><div class="col">' \
           f'{_png_img(png, "Карта близости прокси", max_h=420)}</div></div>'
    return _section("Качество прокси", "Выбранный прокси-бренд и близость", body)


def _sec_caveats(ctx) -> str:
    tc = ctx["transfer_caveats"]
    cols = (
        f'<div class="col go"><h3>Переносится (форма)</h3>{_li(tc["transfers"])}</div>'
        f'<div class="col stop"><h3>НЕ переносится</h3>{_li(tc["not_transfers"])}</div>'
        f'<div class="col gold"><h3>Восстанавливается из anchors</h3>{_li(tc["reconstructed"])}</div>'
    )
    unc = tc["uncertainty"]
    label_ru = {"proxy": "Прокси", "transfer": "Трансфер", "anchor": "Anchors", "sampling": "Сэмплинг"}
    pie = pie_breakdown(slices={label_ru.get(k, k): v for k, v in unc.items()},
                        donut=True, theme=_THEME)
    infl = tc.get("inflation_factor")
    infl_txt = (f'<p class="note">Inflation factor: ×{infl:g} (verdict Medium → расширение 95% CI)</p>'
                if infl else "")
    body = (
        f'<div class="cols">{cols}</div>'
        f'<p class="note">{_esc(tc["caveat_text"])}</p>'
        f'<h3>Декомпозиция неопределённости</h3>'
        f'{_png_img(pie, "Декомпозиция неопределённости", max_h=360)}{infl_txt}'
    )
    return _section("Оговорки трансфера", "Что переносится, что — нет", body)


def _sec_forecast(ctx, key: str, weeks: int) -> str | None:
    section = ctx.get(key)
    if section is None:
        return None
    cone = section["cone"]
    png = forecast_cone(periods=[p["x"] for p in cone], mean=[p["mean"] for p in cone],
                        bands=_derive_bands(cone), ylabel="Продажи, ₽", theme=_THEME,
                        size_px=(1600, 720))
    wb = section["weekly_breakdown"][:12]
    rows = [[r["week"], f'{r["mean"]:,.0f}'.replace(",", " "),
             f'{r["ci_lower"]:,.0f}'.replace(",", " "), f'{r["ci_upper"]:,.0f}'.replace(",", " ")]
            for r in wb]
    more = ("" if len(section["weekly_breakdown"]) <= 12 else
            f'<p class="note">Показаны первые 12 из {len(section["weekly_breakdown"])} недель '
            f'(полная разбивка — в XLSX).</p>')
    body = (
        _png_img(png, f"Веер прогноза {weeks} недель")
        + _table(["Неделя", "Среднее, ₽", "Нижняя 95%", "Верхняя 95%"], rows, num_cols={1, 2, 3})
        + more
    )
    return _section(f"Прогноз · {weeks} недель", "Веер прогноза и понедельная разбивка", body)


def _sec_methodology(ctx) -> str:
    m = ctx["methodology"]
    refs = _li(m["references"])
    body = (
        '<div class="formula">Adstock:  A_t = X_t + λ · A_(t−1)</div><br>'
        '<div class="formula">Hill:  H(x) = β · x^γ / (k^γ + x^γ)</div>'
        f'<h3>Академические источники</h3>{refs}'
        f'<p>{_esc(m["posterior_update_reminder"])}</p>'
        f'<p class="note">{_esc(m["cross_reference"])}</p>'
    )
    return _section("Методология", "Математика, источники и воспроизводимость", body)


def build_launch_forecast_html(
    context: dict[str, Any],
    output_path: str,
    *,
    aurora_version: str = "v0.2.5",
    project_id: str | None = None,
    date_generated: str | None = None,
    hash_signature: str | None = None,
) -> dict[str, Any]:
    """Render the standalone 8-section Launch Forecast HTML to ``output_path``."""
    cover = context["cover"]
    cover["aurora_version"] = aurora_version
    cover["project_id"] = project_id
    cover["date_generated"] = date_generated
    cover["hash_signature"] = hash_signature

    skipped: list[str] = []
    sections = [_sec_cover(context), "<main>", _sec_executive(context), _sec_proxy(context),
                _sec_caveats(context)]
    for key, weeks in (("forecast_12w", 12), ("forecast_26w", 26), ("forecast_52w", 52)):
        s = _sec_forecast(context, key, weeks)
        if s is None:
            skipped.append(key)
            continue
        sections.append(s)
        if (context[key] or {}).get("channel_decomposition") is None:
            skipped.append(f"{key}.channel_decomposition")
        if (context[key] or {}).get("sensitivity") is None:
            skipped.append(f"{key}.sensitivity")
    sections.append(_sec_methodology(context))
    sections.append("</main>")

    css = _root_tokens_css() + "\n" + _font_faces_css() + "\n" + _LAYOUT_CSS
    doc = (
        '<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>Launch Forecast — {_esc(cover["recipient_brand"])}</title>'
        f"<style>{css}</style></head><body>{''.join(sections)}</body></html>"
    )

    Path(output_path).write_text(doc, encoding="utf-8")
    return {
        "output_path": output_path,
        "bytes": len(doc.encode("utf-8")),
        "skipped": skipped,
        "fonts_inlined": sum(1 for *_, f in _FONT_FACES if (_FONT_DIR / f).exists()),
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
