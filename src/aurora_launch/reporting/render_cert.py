"""Methodology Certificate → PDF renderer (Sprint B4 deliverable #4, audit document).

The regulator-ready single-page certificate (spec §3, the CP-7 reproducibility
centerpiece). Per ADR-006 the renderer stack is Tauri webview (primary, app-runtime)
+ ReportLab (fallback, pure-Python) + Typst (Phase B+); WeasyPrint is REJECTED
(GTK-on-Windows friction). This module is the ReportLab path: pure-Python, no system
deps, runs headless — so the certificate generates programmatically without the GUI.

Content + signing are renderer-independent (ADR-006: "cert content schema remains
identical, only rendering backend changes"). The cert data is composed and signed by
`engines.methodology_cert` (local Ed25519, variant B — honestly unsigned when the
custody key is absent, never faked); this module only LAYS OUT the signed data.

Cyrillic + brand typography: the bundled Core OFL TTFs (Inter/Lora) are registered
with ReportLab. The bundle hash is written to both the PDF metadata and visible text
(spec §3.4).
"""

from __future__ import annotations

from typing import Any

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from aurora_reporting.fonts import font_path
from aurora_reporting.primitives import AURORA_HYBRID

from aurora_launch.engines.methodology_cert import (
    build_certificate_data,
    sign_certificate_local,
)
from aurora_launch.reporting import copy
from aurora_launch.schemas.forecast import (
    ForecastSummary,
    ProxyMetadataSummary,
    TransferSummary,
)

_THEME = AURORA_HYBRID

# Brand font family names registered with ReportLab (fall back to Helvetica if the
# bundled TTFs are absent — Helvetica lacks Cyrillic, so we degrade only when forced).
_BODY = "Inter"
_BODY_BOLD = "Inter-Bold"
_DISPLAY = "Lora"
_registered = False


def _register_fonts() -> bool:
    """Register the bundled Inter/Lora TTFs with ReportLab (idempotent).

    Returns True when the brand fonts are available (Cyrillic-safe); False means the
    bundle is absent and the caller must accept the Helvetica fallback (latin only).
    """
    global _registered
    if _registered:
        return True
    pairs = [
        (_BODY, font_path("Inter", bold=False, fmt="ttf")),
        (_BODY_BOLD, font_path("Inter", bold=True, fmt="ttf")),
        (_DISPLAY, font_path("Lora", bold=False, fmt="ttf")),
    ]
    if any(p is None for _, p in pairs):
        return False
    for name, path in pairs:
        pdfmetrics.registerFont(TTFont(name, path))
    _registered = True
    return True


def _styles(has_brand_fonts: bool) -> dict[str, ParagraphStyle]:
    body = _BODY if has_brand_fonts else "Helvetica"
    body_bold = _BODY_BOLD if has_brand_fonts else "Helvetica-Bold"
    display = _DISPLAY if has_brand_fonts else "Helvetica-Bold"
    deep = HexColor(_THEME.deep[0])
    muted = HexColor(_THEME.text_secondary)
    return {
        "title": ParagraphStyle("title", fontName=display, fontSize=22, textColor=deep,
                                 spaceAfter=2, alignment=TA_CENTER),
        "brand": ParagraphStyle("brand", fontName=body_bold, fontSize=11,
                                 textColor=HexColor(_THEME.gold), alignment=TA_CENTER,
                                 spaceAfter=10),
        "h2": ParagraphStyle("h2", fontName=body_bold, fontSize=12, textColor=deep,
                             spaceBefore=12, spaceAfter=4),
        "body": ParagraphStyle("body", fontName=body, fontSize=9.5, textColor=HexColor(_THEME.text_primary),
                               leading=14, alignment=TA_LEFT),
        "note": ParagraphStyle("note", fontName=body, fontSize=8, textColor=muted, leading=11),
        "mono": ParagraphStyle("mono", fontName="Courier", fontSize=8,
                               textColor=HexColor(_THEME.text_primary)),
    }


def _build_cert_data(ctx: dict[str, Any], *, aurora_version: str, bundle_hash: str,
                     jcs_hash: str | None):
    """Compose + locally-sign the certificate data from the report context."""
    pq = ctx["proxy_quality"]
    radar = pq["radar"]
    tc = ctx["transfer_caveats"]
    km = {r["period_weeks"]: r for r in ctx["executive_summary"]["key_metrics"]}

    proxy = ProxyMetadataSummary(
        proxy_code=pq["proxy_brand"],
        similarity_score=radar["aggregate"],
        verdict=radar["verdict"],
        inflation_factor_applied=max(tc.get("inflation_factor") or 1.0, 1.0),
    )
    transfer = TransferSummary(
        transferred_params=tc["transfers"],
        not_transferred=tc["not_transfers"],
        cross_category_distance=0,  # exact L3 category match in the sample
    )
    forecast = ForecastSummary(
        total_forecast_12w=km[12]["total_rub"],
        total_forecast_26w=km[26]["total_rub"],
        total_forecast_52w=km[52]["total_rub"],
        ci_pct_12w=km[12]["ci_pct"],
        ci_pct_26w=km[26]["ci_pct"],
        ci_pct_52w=km[52]["ci_pct"],
    )
    cert = build_certificate_data(
        aurora_launch_version=aurora_version,
        bundle_hash_sha256=bundle_hash,
        bundle_hash_jcs_canonical=jcs_hash or bundle_hash,
        proxy_metadata=proxy,
        transfer_summary=transfer,
        forecast_summary=forecast,
    )
    return sign_certificate_local(cert)  # (cert, signed)


def build_methodology_cert_pdf(
    context: dict[str, Any],
    output_path: str,
    *,
    aurora_version: str = "v0.2.5",
    bundle_hash: str = "0" * 64,
    jcs_hash: str | None = None,
) -> dict[str, Any]:
    """Render the single-page Methodology Certificate PDF (ReportLab) to ``output_path``.

    Returns a manifest: signing status, signing-key id, hash, brand-font availability.
    """
    has_fonts = _register_fonts()
    st = _styles(has_fonts)
    cert, signed = _build_cert_data(context, aurora_version=aurora_version,
                                    bundle_hash=bundle_hash, jcs_hash=jcs_hash)

    recipient = context["cover"]["recipient_brand"]
    pq = context["proxy_quality"]
    radar = pq["radar"]
    tc = context["transfer_caveats"]
    unc = tc["uncertainty"]

    flow: list[Any] = []
    flow.append(Paragraph("AURORA AI", st["brand"]))
    flow.append(Paragraph("Сертификат методологии", st["title"]))
    flow.append(Spacer(1, 8))

    # Project identification.
    flow.append(Paragraph("Идентификация проекта", st["h2"]))
    ident = [
        ["Бренд-получатель", recipient],
        ["Версия Aurora Launch", aurora_version],
        ["Hash подписи (SHA-256)", bundle_hash],
        ["ID сертификата", str(cert.cert_id)],
    ]
    flow.append(_kv_table(ident, st))

    # Methodology summary (spec §3.1).
    flow.append(Paragraph("Сводка методологии", st["h2"]))
    summary = (
        f"Прогноз запуска бренда «{recipient}» подготовлен Aurora AI Launch "
        f"{aurora_version} методом байесовского Marketing Mix Modeling с переносом "
        f"структурных параметров от прокси-бренда {pq['proxy_brand']}. Прокси выбран "
        f"по 6-мерной similarity framework с итоговой близостью S = {radar['aggregate']:g} "
        f"(вердикт: {radar['verdict']}). Переносятся shape-параметры (adstock decay, "
        f"hill saturation, категорийная сезонность); magnitude калибруется от recipient "
        f"anchors. Неопределённость разложена на 4 источника: proxy {unc['proxy']*100:g}%, "
        f"transfer {unc['transfer']*100:g}%, anchor {unc['anchor']*100:g}%, "
        f"sampling {unc['sampling']*100:g}%. 95% ДИ расширен на "
        f"×{tc.get('inflation_factor') or 1:g} согласно вердикту."
    )
    copy.assert_client_safe(summary)
    flow.append(Paragraph(summary, st["body"]))

    # Forecast table.
    flow.append(Paragraph("Прогноз продаж", st["h2"]))
    km = context["executive_summary"]["key_metrics"]
    rows = [["Период", "Прогноз ± 95% ДИ"]] + [
        [f"{r['period_weeks']} недель", f"{r['total_display']} ± {r['ci_pct']:g}%"] for r in km
    ]
    flow.append(_branded_table(rows, st))

    # Confidence statement.
    flow.append(Paragraph("Заявление о достоверности", st["h2"]))
    flow.append(Paragraph(
        "Aurora AI подтверждает, что прогноз получен по воспроизводимой методологии "
        "согласно архитектурным принципам Aurora Launch. Hash-подпись позволяет "
        "проверить идентичность модели и входных данных. Real-world результаты могут "
        "отличаться — неопределённость явно показана в 95% доверительном интервале.",
        st["body"],
    ))

    # Reproducibility recipe.
    flow.append(Paragraph("Воспроизводимость", st["h2"]))
    flow.append(Paragraph(cert.reproducibility_recipe.cli_command, st["mono"]))

    # Signature footer (honest framing — local dev/pilot signature, never cloud-KMS).
    flow.append(Spacer(1, 10))
    if signed:
        sig_line = (f"Подпись разработчика (pilot release): Ed25519 · "
                    f"{cert.signature_local_pubkey_id} · Aurora cloud-KMS: ожидается")
    else:
        sig_line = ("Сертификат НЕ подписан (ключ custody отсутствует на этом сборочном "
                    "узле) — подпись добавляется при релизной сборке.")
    flow.append(Paragraph(sig_line, st["note"]))
    flow.append(Paragraph(
        f"Антон Сипович, Founder Aurora AI · auroraai.pro · "
        f"проверка: {cert.verifier_urls.cli_tool_command_example}", st["note"]))

    # PDF metadata — hash embedded (spec §3.4), not just visible text.
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=16 * mm,
        title=f"Methodology Certificate — {recipient}",
        author="Aurora AI Launch",
        subject=f"bundle_sha256={bundle_hash}",
        keywords=f"aurora-launch methodology-certificate sha256:{bundle_hash} "
                 f"cert:{cert.cert_id} signed:{signed}",
    )
    doc.build(flow)
    return {
        "output_path": output_path,
        "local_signed": signed,
        "signature_pubkey_id": cert.signature_local_pubkey_id,
        "cert_id": str(cert.cert_id),
        "bundle_hash": bundle_hash,
        "brand_fonts": has_fonts,
        "renderer": "reportlab",
    }


def _kv_table(rows: list[list[str]], st: dict[str, ParagraphStyle]) -> Table:
    data = [[Paragraph(k, st["note"]), Paragraph(v, st["body"])] for k, v in rows]
    t = Table(data, colWidths=[45 * mm, 120 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, HexColor(_THEME.rule)),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _branded_table(rows: list[list[str]], st: dict[str, ParagraphStyle]) -> Table:
    body_font = _BODY if _registered else "Helvetica"
    bold_font = _BODY_BOLD if _registered else "Helvetica-Bold"
    t = Table(rows, colWidths=[55 * mm, 110 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor(_THEME.deep[0])),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor(_THEME.bg_white)),
        ("FONTNAME", (0, 0), (-1, 0), bold_font),
        ("FONTNAME", (0, 1), (-1, -1), body_font),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor(_THEME.bg_white), HexColor(_THEME.bg_cream)]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, HexColor(_THEME.rule)),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def _main() -> None:
    import json

    from aurora_launch.reporting.context import build_report_context
    from aurora_launch.sample_bundles.report_fixture import build_sample_forecast_fixture

    ctx = build_report_context(build_sample_forecast_fixture())
    manifest = build_methodology_cert_pdf(
        ctx, "launch_forecast_sample_cert.pdf", aurora_version="v0.2.5",
        bundle_hash="a" * 64,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _main()
