# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Email sending service. Logs to console when SMTP not configured."""

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from rompmusic_server.config import settings

logger = logging.getLogger(__name__)


def _logo_url() -> str:
    """Base URL for logo image in emails (must be publicly reachable)."""
    base = (settings.app_base_url or settings.base_url or "http://localhost:8080").rstrip("/")
    return f"{base}/logo.png"


def wrap_body_with_logo_html(plain_body: str) -> str:
    """Wrap plain text body in minimal HTML with logo at top."""
    body_escaped = plain_body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>\n")
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: system-ui, sans-serif; color: #333; max-width: 560px;">
<p><img src="{_logo_url()}" alt="RompMusic" width="120" height="120" style="display: block;" /></p>
<div style="white-space: pre-wrap;">{body_escaped}</div>
</body>
</html>"""


async def send_email(to: str, subject: str, body: str, html: bool = True) -> None:
    """Send an email (plain and HTML with logo). Logs to console if SMTP not configured."""
    if settings.smtp_host and settings.smtp_user:
        try:
            import smtplib
            if html:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = settings.smtp_from
                msg["To"] = to
                msg.attach(MIMEText(body, "plain"))
                msg.attach(MIMEText(wrap_body_with_logo_html(body), "html"))
            else:
                msg = MIMEText(body, "plain")
                msg["Subject"] = subject
                msg["From"] = settings.smtp_from
                msg["To"] = to
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password or "")
                server.sendmail(settings.smtp_from, [to], msg.as_string())
        except Exception as e:
            logger.exception("Failed to send email: %s", e)
    else:
        logger.info("Email (SMTP not configured): To=%s Subject=%s Body=%s", to, subject, body[:200])
