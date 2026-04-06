"""Tests for src/services/notifier.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.notifier import NotificationService


# ---------------------------------------------------------------------------
# No-op behaviour when unconfigured
# ---------------------------------------------------------------------------

async def test_send_slack_noop_when_no_webhook():
    svc = NotificationService(slack_webhook_url=None)
    # Must not raise
    await svc.send_slack("Test message")


async def test_send_email_noop_when_no_smtp():
    svc = NotificationService(
        smtp_host=None,
        smtp_username=None,
        smtp_password=None,
        from_address=None,
        to_address=None,
    )
    # Must not raise
    await svc.send_email(subject="Test", body="Body")


# ---------------------------------------------------------------------------
# Slack notification
# ---------------------------------------------------------------------------

async def test_send_slack_posts_to_webhook():
    svc = NotificationService(slack_webhook_url="https://hooks.slack.com/test")

    with patch("httpx.AsyncClient") as MockClient:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.post = AsyncMock(return_value=mock_resp)
        MockClient.return_value = mock_client_instance

        await svc.send_slack("Pipeline complete!")

    mock_client_instance.post.assert_called_once()
    call_kwargs = mock_client_instance.post.call_args
    assert "hooks.slack.com" in call_kwargs[0][0]


async def test_send_slack_includes_message_in_payload():
    svc = NotificationService(slack_webhook_url="https://hooks.slack.com/test")

    with patch("httpx.AsyncClient") as MockClient:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.post = AsyncMock(return_value=mock_resp)
        MockClient.return_value = mock_client_instance

        await svc.send_slack("My specific message")

    call_kwargs = mock_client_instance.post.call_args
    payload = call_kwargs[1].get("json") or call_kwargs[0][1] if len(call_kwargs[0]) > 1 else call_kwargs[1].get("json", {})
    assert "My specific message" in str(payload)


async def test_send_slack_does_not_raise_on_http_error():
    svc = NotificationService(slack_webhook_url="https://hooks.slack.com/test")

    with patch("httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.post = AsyncMock(side_effect=Exception("Connection refused"))
        MockClient.return_value = mock_client_instance

        # Should log error but not raise
        await svc.send_slack("test")


# ---------------------------------------------------------------------------
# notify_pipeline_complete helper
# ---------------------------------------------------------------------------

async def test_notify_pipeline_complete_sends_slack():
    svc = NotificationService(slack_webhook_url="https://hooks.slack.com/test")
    svc.send_slack = AsyncMock()

    await svc.notify_pipeline_complete(
        query_name="SGLT2 HF",
        articles_found=10,
        articles_extracted=8,
        synthesis_id=None,
    )

    svc.send_slack.assert_called_once()
    msg = svc.send_slack.call_args[0][0]
    assert "SGLT2 HF" in msg
    assert "10" in msg


async def test_notify_pipeline_complete_noop_when_no_webhook():
    svc = NotificationService(slack_webhook_url=None)
    # Must not raise
    await svc.notify_pipeline_complete(
        query_name="SGLT2 HF",
        articles_found=5,
        articles_extracted=5,
        synthesis_id=None,
    )
