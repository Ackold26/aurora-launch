"""Customer support workflow (Phase Π.4).

In-app diagnostics ZIP + mailto: support flow — zero-infrastructure helper
that converts customer issues к structured diagnostics bundles emailed
к Aurora support team.

Modules:
  * diagnostics.py — collect_diagnostics(): ZIP с system info + logs + audit
  * mailto.py — mailto_url(): pre-filled support email template

Privacy: customer reviews ZIP before sending. Никаких automatic uploads.
Cloud upload deferred к Phase X M-TF (post-GA module).
"""

from aurora_launch.support.diagnostics import (
    DiagnosticsBundle,
    DiagnosticsError,
    collect_diagnostics,
)
from aurora_launch.support.mailto import (
    build_support_mailto_url,
    format_support_email_body,
)

__all__ = [
    "DiagnosticsBundle",
    "DiagnosticsError",
    "build_support_mailto_url",
    "collect_diagnostics",
    "format_support_email_body",
]
