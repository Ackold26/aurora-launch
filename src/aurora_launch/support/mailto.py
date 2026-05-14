"""mailto: support email URL builder (Phase Π.4.2).

Constructs mailto:// URL с pre-filled subject + body for customer's default
email client. Customer attaches diagnostics ZIP manually (most email clients
don't accept attachments в mailto: URLs per RFC 6068).

Zero infrastructure — works offline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping
from urllib.parse import quote

SUPPORT_EMAIL_DEFAULT = "support@auroraai.pro"
SUBJECT_PREFIX = "[Aurora Launch]"


_BODY_TEMPLATE_RU = """\
Здравствуйте,

Описание проблемы:
[опишите проблему здесь — что вы делали, что ожидали увидеть, что произошло]

---

Прикреплённый файл: aurora-diagnostics-{timestamp}.zip
Версия приложения: {app_version}
Время возникновения: {timestamp}

(Файл диагностики сохранён в: {diagnostics_path})

---

Diagnostics file path:
  {diagnostics_path}

Пожалуйста, прикрепите ZIP-файл вручную к этому письму перед отправкой.
"""


def format_support_email_body(
    *,
    diagnostics_path: str,
    timestamp: str,
    app_version: str = "0.1.0",
    customer_note: str | None = None,
) -> str:
    """Compose support email body (Russian, with diagnostics reference).

    Args:
        diagnostics_path: absolute path к diagnostics ZIP file (for customer
            к find and attach manually)
        timestamp: ISO timestamp когда issue occurred
        app_version: для inclusion в email body
        customer_note: optional pre-filled note (rare — usually customer types это)

    Returns:
        Plain text email body suitable для mailto: encoding.
    """
    body = _BODY_TEMPLATE_RU.format(
        timestamp=timestamp,
        app_version=app_version,
        diagnostics_path=diagnostics_path,
    )
    if customer_note:
        # Insert before [опишите проблему здесь]
        body = body.replace(
            "[опишите проблему здесь — что вы делали, что ожидали увидеть, что произошло]",
            customer_note.strip(),
            1,
        )
    return body


def build_support_mailto_url(
    *,
    diagnostics_path: str,
    timestamp: str | None = None,
    app_version: str = "0.1.0",
    customer_org: str | None = None,
    customer_note: str | None = None,
    support_email: str = SUPPORT_EMAIL_DEFAULT,
) -> str:
    """Build mailto: URL с pre-filled subject + body.

    Args:
        diagnostics_path: path к diagnostics ZIP (mentioned в body)
        timestamp: ISO timestamp string (defaults к now)
        app_version: для subject + body
        customer_org: optional org/brand name для subject ("[Aurora Launch] Issue from Materia Medica")
        customer_note: optional pre-filled description
        support_email: override (defaults к support@auroraai.pro)

    Returns:
        mailto: URL ready для opening в default email client.
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    subject_parts = [SUBJECT_PREFIX, "Issue Report"]
    if customer_org:
        subject_parts.append(f"from {customer_org}")
    subject_parts.append(f"v{app_version}")
    subject = " ".join(subject_parts)

    body = format_support_email_body(
        diagnostics_path=diagnostics_path,
        timestamp=timestamp,
        app_version=app_version,
        customer_note=customer_note,
    )

    # mailto: per RFC 6068 — subject + body URL-encoded.
    # Keep email address unquoted (safe="@") per RFC 6068 §3 — local-part/domain
    # need not be percent-encoded; quoting @ produces opaque URL что some
    # email clients reject.
    return (
        f"mailto:{quote(support_email, safe='@')}"
        f"?subject={quote(subject)}"
        f"&body={quote(body)}"
    )
