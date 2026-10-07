"""Repository unit tests with mocked SQLAlchemy session."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.domain.enums import Currency, OutboxEventType, OutboxStatus, PaymentStatus
from app.models import OutboxMessage, Payment, ProcessedMessage
from app.repositories import OutboxRepository, PaymentRepository, ProcessedMessageRepository


@pytest.mark.asyncio
async def test_payment_repository_add_and_get() -> None:
    session = MagicMock()
    session.flush = AsyncMock()
    payment = Payment(
        id=uuid4(),
        amount=Decimal("10.00"),
        currency=Currency.USD,
        description="",
        payment_metadata={},
        status=PaymentStatus.PENDING,
        idempotency_key="k",
        webhook_url="https://example.com/hook",
    )
    session.get = AsyncMock(return_value=payment)
    repo = PaymentRepository(session)

    saved = await repo.add(payment)
    assert saved is payment
    session.add.assert_called_once_with(payment)

    found = await repo.get_by_id(payment.id)
    assert found is payment


@pytest.mark.asyncio
async def test_payment_repository_get_by_idempotency_key() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)
    repo = PaymentRepository(session)
    assert await repo.get_by_idempotency_key("key") is None
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_outbox_repository_mark_published_and_retry() -> None:
    session = MagicMock()
    session.flush = AsyncMock()
    repo = OutboxRepository(session)
    message = OutboxMessage(
        id=uuid4(),
        event_type=OutboxEventType.PAYMENTS_NEW.value,
        aggregate_type="payment",
        aggregate_id=uuid4(),
        payload={},
        status=OutboxStatus.PROCESSING,
        attempts=1,
        available_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        lock_token="t",
        locked_at=datetime.now(UTC),
    )

    published = await repo.mark_published(message)
    assert published.status == OutboxStatus.PUBLISHED
    assert published.published_at is not None
    assert published.lock_token is None

    retry_at = datetime.now(UTC)
    retried = await repo.mark_retry(message, error="err", available_at=retry_at, failed=False)
    assert retried.status == OutboxStatus.PENDING
    assert retried.available_at == retry_at

    failed = await repo.mark_retry(message, error="fatal", available_at=retry_at, failed=True)
    assert failed.status == OutboxStatus.FAILED


@pytest.mark.asyncio
async def test_processed_message_repository_exists_and_add() -> None:
    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = uuid4()
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()
    repo = ProcessedMessageRepository(session)

    assert await repo.exists("msg-1") is True

    record = await repo.add(message_id="msg-2", event_type="payments.new")
    assert isinstance(record, ProcessedMessage)
    session.add.assert_called_once()


@pytest.mark.asyncio
async def test_processed_message_try_acquire_and_delete() -> None:
    session = MagicMock()
    session.flush = AsyncMock()

    acquired_result = MagicMock()
    acquired_result.scalar_one_or_none.return_value = uuid4()
    session.execute = AsyncMock(return_value=acquired_result)
    repo = ProcessedMessageRepository(session)
    assert await repo.try_acquire(message_id="m1", event_type="payments.new") is True

    missing_result = MagicMock()
    missing_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=missing_result)
    assert await repo.try_acquire(message_id="m1", event_type="payments.new") is False

    await repo.delete("m1")
    assert session.execute.await_count >= 2
