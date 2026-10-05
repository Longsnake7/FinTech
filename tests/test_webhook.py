"""Webhook client tests."""

import httpx
import pytest

from app.domain.exceptions import WebhookDeliveryError
from app.services.webhook import WebhookClient


@pytest.mark.asyncio
async def test_webhook_success(settings, sample_payment) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == sample_payment.webhook_url
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        webhook = WebhookClient(settings, client=client)
        sample_payment.status = sample_payment.status
        await webhook.notify(sample_payment)


@pytest.mark.asyncio
async def test_webhook_failure(settings, sample_payment) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"ok": False})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        webhook = WebhookClient(settings, client=client)
        with pytest.raises(WebhookDeliveryError):
            await webhook.notify(sample_payment)
