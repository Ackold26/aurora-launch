# ADR-006: PDF Rendering Tech Stack для Methodology Certificate

**Status:** Accepted
**Date:** 2026-05-08
**Decision:** Tauri webview print API as **primary**, ReportLab as **fallback**, Typst evaluated and deferred к Phase B+ premium polish.
**Sprint context:** B0.5 PDF rendering spike (per HIGH H1 fix in plan v1.1)

## Context

Methodology Certificate (B4 deliverable) — single-page или 2-page PDF с
Ed25519 dual-signature footer + reproducibility recipe + verifier URLs. Это
centerpiece artifact of CP-7 Reproducibility Ceremony. Выбор PDF generator
определяет:
- Cross-platform compatibility (Windows + Linux mandatory, macOS Phase B+)
- Customer install footprint (extra deps undesired)
- Typography quality (premium feel)
- Long-term maintenance burden

## Considered options

### Option A — Tauri webview print API (chosen primary)

**Mechanism:** Aurora Launch is Tauri desktop app. Webview уже встроена в
binary. HTML template rendered в hidden window → `window.print()` headless
с `@page` CSS rules → PDF saved to disk.

**Pros:**
- ✅ Zero extra deps (webview уже есть в каждом install)
- ✅ Cross-platform automatic (Tauri handles OS PDF backend)
- ✅ HTML/CSS templating familiar
- ✅ Per-customer custom branding via CSS overrides trivial
- ✅ Customer can preview Cert в HTML before PDF export

**Cons:**
- ⚠ CSS print spec coverage varies per OS webview backend
- ⚠ Custom fonts require web font loading (works но adds bytes)
- ⚠ PDF metadata (title, author) needs explicit setting

**Mitigation:** B4 implementation includes regression test suite verifying
PDF rendering across Windows + Linux WebViews. Fonts bundled in app
resources.

### Option B — Typst (evaluated, deferred Phase B+)

**Mechanism:** Single binary (~30 MB embedded), modern typesetting (Rust-based,
better than LaTeX), no GTK dep.

**Pros:**
- ✅ Premium typography (best-in-class)
- ✅ Reproducible PDFs (Typst guarantees byte-stable output for identical input)
- ✅ Single binary — no runtime deps

**Cons:**
- ⚠ +30 MB to installer footprint
- ⚠ Templating language (Typst-specific) — learning curve
- ⚠ Customer customization harder (markup, не HTML/CSS)

**Verdict:** **Defer к Phase B+** premium upgrade. Если customer feedback
indicates Methodology Cert PDF quality matters more чем installer size —
swap to Typst. Phase B ships Tauri webview, Phase B+ может migrate.

### Option C — ReportLab (fallback if A fails on edge case)

**Mechanism:** Pure Python PDF library, programmatic API.

**Pros:**
- ✅ Pure Python — no system deps
- ✅ Mature, proven
- ✅ Already used в Aurora ecosystem (Эконометрика legacy reports)

**Cons:**
- ❌ Programmatic API — no HTML/CSS templating
- ❌ Less premium typography
- ❌ Per-tier customization requires Python code, не template files

**Verdict:** **Fallback** — used only if Tauri webview hits compatibility issue
on specific OS variant. Maintained as reference implementation in code.

### Option D — WeasyPrint (rejected)

**Mechanism:** Python HTML/CSS → PDF, GTK-based.

**Pros:** HTML/CSS templating like Option A.

**Cons:**
- ❌ GTK runtime install required on Windows (multi-step customer setup)
- ❌ Per memory `feedback_third_party_api_verify` — verify dep stability
- ❌ Larger footprint than Option A

**Verdict:** **Rejected.** GTK dep on Windows = customer friction unacceptable.

## Decision

**Tauri webview print API** as primary. **ReportLab** as fallback (kept in
code as alt path для regression tests). **Typst** considered Phase B+ premium
upgrade if customer feedback warrants.

## Implementation guidance for B4

```python
# engines/methodology_cert.py
def render_certificate_pdf(
    cert_data: MethodologyCertificateData,
    pdf_renderer: Literal["tauri_webview", "typst", "reportlab"] = "tauri_webview",
) -> bytes:
    if pdf_renderer == "tauri_webview":
        return _render_via_webview(cert_data)
    elif pdf_renderer == "reportlab":
        return _render_via_reportlab(cert_data)
    elif pdf_renderer == "typst":
        raise NotImplementedError("Typst rendering deferred Phase B+")
    raise ValueError(f"Unknown renderer: {pdf_renderer}")
```

## Acceptance criteria

- AC4.2 — PDF Methodology Cert ≤10s p95 Warm — verified per renderer
- AC6.6 — Verifier supply chain trust — PDF includes hash of WASM verifier
- B6 cross-platform regression tests pass on Windows + Linux

## Reversibility

Decision **reversible** в Phase B+ если pilot feedback indicates premium
typography matters more чем install footprint. Architecture supports renderer
swap via parameter. Cert content schema (`MethodologyCertificateData`) remains
identical — только rendering backend changes.

## Related

- Plan v1.1 HIGH H1 fix (PDF tech stack — B0.5 spike)
- PHASE_B_REQUIREMENTS.md §4.6 B4 (Methodology Certificate centerpiece)
- CP-7 Reproducibility Ceremony (cross-cutting principle)

— Маша, 2026-05-08
