"""Notification service — Slack webhook + email.

Both channels are optional: the service gracefully no-ops when credentials
are not configured.
"""

from __future__ import annotations

import logging
import uuid

logger = logging.getLogger(__name__)


class NotificationService:
    """Send notifications via Slack and/or email.

    All send methods are fire-and-forget: errors are logged but not re-raised
    so that notification failures never break the pipeline.

    Args:
        slack_webhook_url: Slack incoming webhook URL. ``None`` disables Slack.
        smtp_host: SMTP server hostname. ``None`` disables email.
        smtp_port: SMTP port (default 587).
        smtp_username: SMTP auth username.
        smtp_password: SMTP auth password.
        from_address: Sender email address.
        to_address: Recipient email address.
    """

    def __init__(
        self,
        *,
        slack_webhook_url: str | None = None,
        smtp_host: str | None = None,
        smtp_port: int = 587,
        smtp_username: str | None = None,
        smtp_password: str | None = None,
        from_address: str | None = None,
        to_address: str | None = None,
    ) -> None:
        self._slack_url = slack_webhook_url
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._smtp_username = smtp_username
        self._smtp_password = smtp_password
        self._from = from_address
        self._to = to_address

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send_slack(self, message: str) -> None:
        """Post *message* to the configured Slack webhook.

        No-ops silently if no webhook is configured.
        """
        if not self._slack_url:
            return
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    self._slack_url,
                    json={"text": message},
                    timeout=10.0,
                )
                resp.raise_for_status()
        except Exception as exc:
            logger.error("Slack notification failed: %s", exc)

    async def send_email(self, *, subject: str, body: str) -> None:
        """Send a plain-text email.

        No-ops silently if SMTP is not configured.
        """
        if not self._smtp_host or not self._from or not self._to:
            return
        try:
            import aiosmtplib
            from email.message import EmailMessage

            msg = EmailMessage()
            msg["From"] = self._from
            msg["To"] = self._to
            msg["Subject"] = subject
            msg.set_content(body)

            await aiosmtplib.send(
                msg,
                hostname=self._smtp_host,
                port=self._smtp_port,
                username=self._smtp_username,
                password=self._smtp_password,
                start_tls=True,
            )
        except Exception as exc:
            logger.error("Email notification failed: %s", exc)

    async def notify_pipeline_complete(
        self,
        *,
        query_name: str,
        articles_found: int,
        articles_extracted: int,
        synthesis_id: uuid.UUID | None,
    ) -> None:
        """Send a pipeline-complete notification to all configured channels."""
        synthesis_note = (
            f"Synthesis ID: {synthesis_id}" if synthesis_id else "No synthesis produced"
        )
        message = (
            f"Pipeline complete for *{query_name}*\n"
            f"• Articles found: {articles_found}\n"
            f"• Articles extracted: {articles_extracted}\n"
            f"• {synthesis_note}"
        )
        await self.send_slack(message)
        await self.send_email(subject=f"Pipeline complete: {query_name}", body=message)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def from_settings() -> NotificationService:
    """Create a NotificationService from application settings."""
    from src.core.config import settings

    return NotificationService(
        slack_webhook_url=settings.slack_webhook_url,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_username=settings.smtp_username,
        smtp_password=settings.smtp_password,
        from_address=settings.smtp_from_address,
        to_address=settings.notification_email_to,
    )
