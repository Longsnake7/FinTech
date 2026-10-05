"""RabbitMQ publisher abstractions."""

from __future__ import annotations

from typing import Any, Protocol

from app.config import Settings
from app.messaging.topology import build_exchange


class MessagePublisher(Protocol):
    """Port for publishing messages to the broker."""

    async def publish_payments_new(self, payload: dict[str, Any], *, message_id: str) -> None:
        """Publish a payments.new event."""

    async def publish_retry(
        self,
        payload: dict[str, Any],
        *,
        message_id: str,
        delay_seconds: float,
    ) -> None:
        """Publish a message to the retry queue with TTL delay."""

    async def publish_dlq(
        self,
        payload: dict[str, Any],
        *,
        message_id: str,
    ) -> None:
        """Publish a message to the dead letter queue."""


class RabbitMessagePublisher:
    """FastStream-based RabbitMQ publisher."""

    def __init__(self, broker: Any, settings: Settings) -> None:
        self._broker = broker
        self._settings = settings
        self._exchange = build_exchange(settings)

    async def publish_payments_new(self, payload: dict[str, Any], *, message_id: str) -> None:
        await self._broker.publish(
            payload,
            exchange=self._exchange,
            routing_key=self._settings.rabbitmq_routing_payments_new,
            message_id=message_id,
            persist=True,
        )

    async def publish_retry(
        self,
        payload: dict[str, Any],
        *,
        message_id: str,
        delay_seconds: float,
    ) -> None:
        # aio-pika/FastStream expiration is in milliseconds when int/float seconds
        # For aio-pika, expiration can be datetime or int milliseconds as string.
        expiration_ms = max(int(delay_seconds * 1000), 1)
        await self._broker.publish(
            payload,
            exchange=self._exchange,
            routing_key=self._settings.rabbitmq_routing_retry,
            message_id=message_id,
            persist=True,
            expiration=expiration_ms,
        )

    async def publish_dlq(self, payload: dict[str, Any], *, message_id: str) -> None:
        await self._broker.publish(
            payload,
            exchange=self._exchange,
            routing_key=self._settings.rabbitmq_routing_dlq,
            message_id=message_id,
            persist=True,
        )
