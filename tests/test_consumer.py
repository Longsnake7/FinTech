"""Consumer handler: success, retry, DLQ, missing mapping."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.domain.exceptions import PaymentGatewayError, UnknownEventMappingError
from app.messaging.consumer import MessageConsumerHandler


def _payload(**overrides) -> dict:
    base = {
        "event_id": str(uuid4()),
        "event_type": "payments.new",
        "payment_id": str(uuid4()),
        "attempt": 1,
        "amount": "10.00",
        "currency": "USD",
        "description": "x",
        "metadata": {},
        "webhook_url": "https://example.com/hook",
        "idempotency_key": "k",
        "created_at": "2026-10-05T00:00:00+00:00",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_successful_processing(settings, mock_publisher) -> None:
    processor = AsyncMock()
    processor.process = AsyncMock()
    handler = MessageConsumerHandler(
        settings=settings,
        processor=processor,
        publisher=mock_publisher,
    )
    await handler.handle(_payload())
    processor.process.assert_awaited_once()
    mock_publisher.publish_retry.assert_not_awaited()
    mock_publisher.publish_dlq.assert_not_awaited()


@pytest.mark.asyncio
async def test_processing_error_schedules_retry(settings, mock_publisher) -> None:
    processor = AsyncMock()
    processor.process = AsyncMock(side_effect=PaymentGatewayError("boom"))
    handler = MessageConsumerHandler(
        settings=settings,
        processor=processor,
        publisher=mock_publisher,
    )
    payload = _payload(attempt=1)
    await handler.handle(payload)

    mock_publisher.publish_retry.assert_awaited_once()
    args, kwargs = mock_publisher.publish_retry.await_args
    assert args[0]["attempt"] == 2
    assert kwargs["delay_seconds"] >= settings.retry_base_delay_seconds
    mock_publisher.publish_dlq.assert_not_awaited()


@pytest.mark.asyncio
async def test_exactly_three_attempts_then_dlq(settings, mock_publisher) -> None:
    settings.message_max_attempts = 3
    processor = AsyncMock()
    processor.process = AsyncMock(side_effect=PaymentGatewayError("boom"))
    processor.mark_payment_failed = AsyncMock()
    handler = MessageConsumerHandler(
        settings=settings,
        processor=processor,
        publisher=mock_publisher,
    )

    await handler.handle(_payload(attempt=1))
    await handler.handle(_payload(attempt=2))
    assert mock_publisher.publish_retry.await_count == 2
    assert mock_publisher.publish_dlq.await_count == 0

    await handler.handle(_payload(attempt=3))
    assert mock_publisher.publish_retry.await_count == 2
    mock_publisher.publish_dlq.assert_awaited_once()
    processor.mark_payment_failed.assert_awaited_once()
    dlq_payload = mock_publisher.publish_dlq.await_args.args[0]
    assert dlq_payload["attempts"] == 3
    assert dlq_payload["reason"] == "max_attempts_exceeded"
    assert "original_event" in dlq_payload


@pytest.mark.asyncio
async def test_missing_mapping_goes_to_dlq(settings, mock_publisher) -> None:
    processor = AsyncMock()
    processor.process = AsyncMock(side_effect=UnknownEventMappingError("unknown.event"))
    handler = MessageConsumerHandler(
        settings=settings,
        processor=processor,
        publisher=mock_publisher,
    )
    await handler.handle(_payload(event_type="unknown.event"))
    mock_publisher.publish_dlq.assert_awaited_once()
    dlq_payload = mock_publisher.publish_dlq.await_args.args[0]
    assert dlq_payload["reason"] == "no_mapping"
    mock_publisher.publish_retry.assert_not_awaited()
