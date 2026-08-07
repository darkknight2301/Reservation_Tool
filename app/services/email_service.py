"""
Email service.

Sends outbound email via SMTP (``smtplib``, stdlib -- no extra dependency).
When ``SMTP_ENABLED`` is false (the default, since no organization's SMTP
credentials are known ahead of time), messages are structurally built and
logged instead of transmitted, so the calling code path is identical in
both modes and nothing is silently dropped.
"""
import smtplib
from email.mime.text import MIMEText
from typing import List

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class EmailService:
    """Sends plain-text email notifications via SMTP."""

    def send_email(self, to_addresses: List[str], subject: str, body: str) -> None:
        """
        Send an email to one or more recipients.

        If ``SMTP_ENABLED`` is False, the message is logged (not sent) --
        this keeps the notification call sites identical whether or not an
        organization has configured real SMTP credentials yet.
        """
        recipients = [address for address in to_addresses if address]
        if not recipients:
            return

        if not settings.SMTP_ENABLED:
            logger.info("Email (SMTP disabled, not sent): to=%s subject=%s body=%s" % (recipients, subject, body))
            return

        message = MIMEText(body)
        message["Subject"] = subject
        message["From"] = settings.SMTP_FROM_ADDRESS
        message["To"] = ", ".join(recipients)

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp_connection:
            if settings.SMTP_USE_TLS:
                smtp_connection.starttls()
            if settings.SMTP_USERNAME:
                smtp_connection.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp_connection.sendmail(settings.SMTP_FROM_ADDRESS, recipients, message.as_string())
