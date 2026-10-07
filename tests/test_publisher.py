"""RabbitMQ publisher tests."""

from unittest.mock import AsyncMock

import pytest

from app.messaging.publisher import RabbitMessagePublisher


@pytest.mark.asyncio
async def test_publisher_routes(settings) -> None:
    broker = AsyncMock()
    publisher = RabbitMessagePublisher(broker, settings)
    payload = {"event_type": "payments.new"}

    await publisher.publish_payments_new(payload, message_id="id-1")
    await publisher.publish_retry(payload, message_id="id-1", delay_seconds=1.5)
    await publisher.publish_dlq(payload, message_id="id-1")

    assert broker.publish.await_count == 3
    retry_call = broker.publish.await_args_list[1]
    assert retry_call.kwargs["routing_key"] == settings.rabbitmq_routing_retry
    assert retry_call.kwargs["expiration"] == 1500
