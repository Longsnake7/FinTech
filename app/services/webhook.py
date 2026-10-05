"""Webhook notification client."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.domain.exceptions import WebhookDeliveryError
from app.models import Payment


class WebhookClient:
    """Delivers payment result notifications to client webhook URLs."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> WebhookClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._settings.webhook_timeout_seconds)
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def notify(self, payment: Payment) -> None:
        """POST payment result to the configured webhook URL."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._settings.webhook_timeout_seconds)
            self._owns_client = True

        payload: dict[str, Any] = {
            "payment_id": str(payment.id),
            "status": payment.status.value
            if hasattr(payment.status, "value")
            else str(payment.status),
            "amount": str(payment.amount),
            "currency": payment.currency.value
            if hasattr(payment.currency, "value")
            else str(payment.currency),
            "processed_at": payment.processed_at.isoformat() if payment.processed_at else None,
        }
        try:
            response = await self._client.post(str(payment.webhook_url), json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise WebhookDeliveryError(f"Webhook delivery failed: {exc}") from exc
