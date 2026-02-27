# Copyright (C) 2024 RompMusic Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Email sending service. Logs to console when SMTP not configured."""

import logging
from email.mime.text import MIMEText

from rompmusic_server.config import settings

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, body: str) -> None:
    """Send an email. Logs to console if SMTP not configured."""
    if settings.smtp_host and settings.smtp_user:
        try:
            import smtplib
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
