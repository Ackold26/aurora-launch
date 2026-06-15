"""Launch Forecast report composition (Sprint B4).

Launch-local layer that composes the 8-section Launch Forecast Report on top of
the Core `aurora_reporting` primitives (charts / styled-tables / fonts / WeasyPrint
cert scaffold). Per the CPI boundary: Core owns generic rendering primitives,
Launch owns this product-specific template + copy + the forecast→context adapter.

- `copy`    — customer-facing RU phrases + forbidden-phrase guard (spec §4.2/§4.3)
- `context` — forecast result + project metadata → neutral 8-section report context
"""
