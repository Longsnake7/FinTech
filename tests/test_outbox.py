"""Outbox worker tests."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.domain.enums import OutboxEventType, OutboxStatus
from app.messaging.outbox_worker import OutboxWorker
from app.models import OutboxMessage


def _outbox_message(**overrides) -> OutboxMessage:
    data = {
        "id": uuid4(),
        "event_type": OutboxEventType.PAYMENTS_NEW.value,
        "aggregate_type": "payment",
        "aggregate_id": uuid4(),
        "payload": {"event_id": "1", "payment_id": str(uuid4())},
        "status": OutboxStatus.PENDING,
        "attempts": 0,
        "available_at": datetime.now(UTC),
        "created_at": datetime.now(UTC),
    }
    data.update(overrides)
    return OutboxMessage(**data)


@pytest.mark.asyncio
async def test_outbox_successful_publish(settings, mock_publisher) -> None:
    message = _outbox_message()
    uow = MagicMock()
    uow.outbox = AsyncMock()
    uow.outbox.list_pending = AsyncMock(return_value=[message])
    uow.outbox.mark_processing = AsyncMock(return_value=message)
    uow.outbox.get_by_id = AsyncMock(return_value=message)
    uow.outbox.mark_published = AsyncMock(return_value=message)
    uow.commit = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)

    worker = OutboxWorker(
        settings=settings,
        uow_factory=lambda: uow,
        publisher=mock_publisher,
    )
    published = await worker.publish_batch()
    assert published == 1
    mock_publisher.publish_payments_new.assert_awaited_once()
    uow.outbox.mark_published.assert_awaited()


@pytest.mark.asyncio
async def test_outbox_publish_failure_schedules_retry(settings, mock_publisher) -> None:
    message = _outbox_message(attempts=1)
    mock_publisher.publish_payments_new = AsyncMock(side_effect=RuntimeError("broker down"))

    uow = MagicMock()
    uow.outbox = AsyncMock()
    uow.outbox.list_pending = AsyncMock(return_value=[message])
    uow.outbox.mark_processing = AsyncMock(side_effect=lambda m, lock_token: m)
    uow.outbox.get_by_id = AsyncMock(return_value=message)
    uow.outbox.mark_retry = AsyncMock(return_value=message)
    uow.commit = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)

    worker = OutboxWorker(
        settings=settings,
        uow_factory=lambda: uow,
        publisher=mock_publisher,
    )
    published = await worker.publish_batch()
    assert published == 0
    uow.outbox.mark_retry.assert_awaited()
    kwargs = uow.outbox.mark_retry.await_args.kwargs
    assert kwargs["failed"] is False
    assert "broker down" in kwargs["error"]


@pytest.mark.asyncio
async def test_outbox_republish_after_failure(settings, mock_publisher) -> None:
    """Second poll publishes successfully after a previous failure path."""
    message = _outbox_message(attempts=2, status=OutboxStatus.PENDING)
    uow = MagicMock()
    uow.outbox = AsyncMock()
    uow.outbox.list_pending = AsyncMock(return_value=[message])
    uow.outbox.mark_processing = AsyncMock(side_effect=lambda m, lock_token: m)
    uow.outbox.get_by_id = AsyncMock(return_value=message)
    uow.outbox.mark_published = AsyncMock(return_value=message)
    uow.commit = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)

    worker = OutboxWorker(
        settings=settings,
        uow_factory=lambda: uow,
        publisher=mock_publisher,
    )
    assert await worker.publish_batch() == 1
    mock_publisher.publish_payments_new.assert_awaited_once_with(
        dict(message.payload),
        message_id=str(message.id),
    )


@pytest.mark.asyncio
async def test_outbox_empty_batch(settings, mock_publisher) -> None:
    uow = MagicMock()
    uow.outbox = AsyncMock()
    uow.outbox.list_pending = AsyncMock(return_value=[])
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)

    worker = OutboxWorker(
        settings=settings,
        uow_factory=lambda: uow,
        publisher=mock_publisher,
    )
    assert await worker.publish_batch() == 0
    mock_publisher.publish_payments_new.assert_not_awaited()
